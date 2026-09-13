"""
Gerçek dalga formu indirdiğimiz olaylar için ISC Bulletin'den UZMAN
(analyst-reviewed) P/S faz okumalarını çeker.

Neden gerekli: `enrich_waveforms.py`'deki p_pick_time/s_pick_time otomatik
STA/LTA ile üretiliyor (S için sezgisel bir yöntemle) - DATA_CARD bunu
dürüstçe belirtiyor ama bu bir "ground-truth benchmark" değil. ISC'nin
FDSN olay servisi `includearrivals=True` ile sorgulandığında, dünya
genelindeki istasyonlardan (KOERI/KO dahil) sismoloji uzmanlarının elle
doğruladığı gerçek pick'leri (arrival) döndürüyor. Bu script sadece
gerçek waveform dosyası indirdiğimiz ~1000 olay için (tüm 84.000 olay
için değil - o çok ağır ve çoğunlukla gereksiz olurdu) bu pick'leri
çekip diske kaydediyor.

Sınırlama: ISC Bulletin'in nihai (reviewed) hale gelmesi genelde birkaç
ay sürüyor, bu yüzden çok yeni olaylarda pick bulunamayabilir. Ayrıca her
olay ISC'ye bildirilmiş/işlenmiş olmayabilir.

Kullanım:
    python scripts/fetch_isc_picks.py
"""
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from obspy import UTCDateTime
from obspy.clients.fdsn import Client
from obspy.clients.fdsn.header import FDSNException

PROCESSED = Path("data/processed")
OUT_PATH = PROCESSED / "isc_analyst_picks.csv"
PROGRESS_PATH = PROCESSED / "isc_picks_progress.csv"

TIME_WINDOW_SEC = 120  # olay zamanının +-2 dakikası içinde ISC kaydı ara
BBOX_MARGIN_DEG = 2.0  # olay konumunun etrafında +-2 derecelik kutu
SLEEP_BETWEEN_REQUESTS = 1.0  # ISC sunucusuna karşı nazik davran

client = Client("ISC")

P_PHASES = {"P", "Pg", "Pn", "PG", "PN"}
S_PHASES = {"S", "Sg", "Sn", "SG", "SN"}


def load_target_events():
    """Gerçek dalga formu indirdiğimiz olaylar + o olayda hangi
    istasyonların denendiği (sadece bu istasyonların pick'leriyle
    ilgileniyoruz)."""
    log = pd.read_csv(PROCESSED / "waveform_fetch_log.csv")
    ok = log[log["status"] == "ok"]
    events = pd.read_parquet(PROCESSED / "turkiye_deprem_katalogu_genisletilmis.parquet").rename(
        columns={"source_event_id": "event_id"}
    )
    merged = ok[["event_id", "station"]].merge(events, on="event_id", how="inner")
    grouped = merged.groupby("event_id").agg(
        stations=("station", lambda s: set(s)),
        latitude=("latitude", "first"), longitude=("longitude", "first"),
        time_utc=("time_utc", "first"), magnitude=("magnitude", "first"),
    ).reset_index()
    return grouped


def load_progress():
    if not PROGRESS_PATH.exists():
        return set()
    return set(pd.read_csv(PROGRESS_PATH)["event_id"])


def append_progress(event_id):
    is_new = not PROGRESS_PATH.exists()
    with open(PROGRESS_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["event_id"])
        writer.writerow([event_id])


def append_picks(rows):
    if not rows:
        return
    is_new = not OUT_PATH.exists()
    with open(OUT_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


def main():
    targets = load_target_events()
    done = load_progress()
    todo = targets[~targets["event_id"].isin(done)]
    print(f"{len(targets)} hedef olay, {len(done)} zaten denenmiş, {len(todo)} kaldı.")

    found_events, found_picks = 0, 0

    for i, ev in todo.iterrows():
        t0 = UTCDateTime(ev["time_utc"]) - TIME_WINDOW_SEC
        t1 = UTCDateTime(ev["time_utc"]) + TIME_WINDOW_SEC
        rows = []
        try:
            cat = client.get_events(
                starttime=t0, endtime=t1,
                minlatitude=ev["latitude"] - BBOX_MARGIN_DEG, maxlatitude=ev["latitude"] + BBOX_MARGIN_DEG,
                minlongitude=ev["longitude"] - BBOX_MARGIN_DEG, maxlongitude=ev["longitude"] + BBOX_MARGIN_DEG,
                includearrivals=True,
            )
            if len(cat) > 0:
                # Birden fazla aday varsa, büyüklüğü bizimkine en yakın olanı seç
                isc_ev = min(
                    cat, key=lambda e: abs((e.preferred_magnitude().mag if e.preferred_magnitude() else 0) - ev["magnitude"])
                )
                target_stations = ev["stations"]
                best_pick = {}  # (station, phase_type) -> en erken pick zamanı
                for pick in isc_ev.picks:
                    if pick.waveform_id.network_code != "KO":
                        continue
                    station = pick.waveform_id.station_code
                    if station not in target_stations:
                        continue
                    phase = (pick.phase_hint or "").strip()
                    if phase in P_PHASES:
                        phase_type = "P"
                    elif phase in S_PHASES:
                        phase_type = "S"
                    else:
                        continue
                    key = (station, phase_type)
                    if key not in best_pick or pick.time < best_pick[key][0]:
                        best_pick[key] = (pick.time, phase)

                for (station, phase_type), (pick_time, raw_phase) in best_pick.items():
                    rows.append(dict(
                        event_id=ev["event_id"], station=station, phase_type=phase_type,
                        phase_hint=raw_phase, pick_time=str(pick_time), source="isc_analyst",
                        fetched_at=datetime.now(timezone.utc).isoformat(),
                    ))
                if rows:
                    found_events += 1
                    found_picks += len(rows)
        except FDSNException:
            pass
        except Exception as e:
            print(f"[UYARI] {ev['event_id']}: {type(e).__name__}: {e}")

        append_picks(rows)
        append_progress(ev["event_id"])
        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if i % 20 == 0:
            print(f"[{i}/{len(targets)}] işlendi | pick bulunan olay={found_events}, toplam pick={found_picks}")

    print(f"\nTamamlandı. Pick bulunan olay: {found_events}, toplam pick: {found_picks}")
    print(f"Kaydedildi -> {OUT_PATH}")


if __name__ == "__main__":
    main()
