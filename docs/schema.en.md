# Data Schema

*[Türkçe](schema.md)*

## `data/processed/turkiye_deprem_katalogu_genisletilmis.parquet`

Extended, deduplicated catalog pulled from the FDSN event services of
USGS, EMSC and ISC. Produced by `scripts/expand_catalog.py`.

| Column | Type | Description |
|---|---|---|
| source_event_id | string | The representative source's own event id |
| time_utc | datetime (UTC) | Event time |
| magnitude | float | Magnitude |
| mag_type | string | Magnitude type (mb, ml, mw, md, etc.) |
| longitude, latitude | float | Epicenter coordinates |
| depth_km | float | Focal depth (km) |
| source | string | Institution the representative record came from (usgs/isc/emsc, in that priority order) |
| reported_by | string | Which institutions also reported this event (comma-separated) |
| magnitude_agreement_std | float | Standard deviation of the reported magnitudes when more than one institution reported this event. A value close to 0 means the institutions agree. |
| magnitude_report_count | int | Number of institutions that reported this event |
| cluster_size | int | Number of distinct (source, record) pairs that reported this event |
| cluster_max_time_diff_sec | float | Largest time difference between records in the cluster (seconds) |
| cluster_max_distance_km | float | Largest location difference between records in the cluster (km) |
| cluster_max_magnitude_diff | float | Largest magnitude difference between records in the cluster |
| dedup_confidence | float (0-1) | Confidence score for the cluster match. 1.0 for single-source clusters. Decreases as time/distance/magnitude difference grows. |

Deduplication method (v2): an event may join a cluster if the time
difference is <=30s, the distance is within a magnitude-scaled
threshold (50-150km, wider for larger earthquakes), and the magnitude
difference is <=1.5. An event from the SAME source that is already in
a cluster cannot join it (one institution never reports the same
earthquake twice; this rule removes v1's biggest source of incorrect
merges). If multiple candidate clusters match, the best match is
chosen. See `DATA_CARD.md` for details.

## `data/processed/event_id_cluster_map.csv`

Shows which representative record each original (source, event id)
pair was folded into. If a USGS event is merged into the same cluster
as another event during deduplication, its own id disappears from the
main dataset, but its waveform files are still on disk under the old
id; `build_dataset.py` uses this mapping to count waveforms correctly.

| Column | Description |
|---|---|
| source | Source institution (usgs/isc/emsc) |
| source_event_id | Original event id |
| representative_event_id | The cluster's surviving (representative) id |

## `data/processed/usgs_catalog_turkey.parquet`

Raw catalog from USGS only (one input to the extended catalog).

| Column | Type | Description |
|---|---|---|
| event_id | string | USGS event id |
| magnitude | float | Magnitude |
| mag_type | string | Magnitude type (mb, ml, mw, etc.) |
| place | string | USGS-generated place description (free text) |
| longitude, latitude | float | Epicenter coordinates |
| depth_km | float | Focal depth (km) |
| status | string | "reviewed" / "automatic" |
| source | string | Network code that reported the event |
| time_utc | datetime (UTC) | Event time |

## `data/processed/koeri_stations.csv`

| Column | Type | Description |
|---|---|---|
| network | string | Always "KO" (KOERI) |
| station | string | Station code |
| latitude, longitude | float | Station location |
| elevation | float | Elevation (m) |
| start_date | string | Station's recording start date |
| channel_codes | string | All channel codes at the station (comma-separated) |
| instrument_types | string | `strong_motion` / `broadband` / `short_period` (can be more than one) |
| has_strong_motion | bool | Whether the station has a real strong-motion (engineering-grade) sensor. True for 128 of 277 stations |
| vs30_ms | float | Site-class shear-wave velocity (m/s). Source: USGS Global Vs30 Mosaic (public domain) |
| nehrp_site_class | string | NEHRP site class: A (hard rock) - E (soft soil) |

## `data/processed/turkiye_deprem_veriseti_v3.parquet`

The union of the extended catalog, station matching, site class and
waveform features. The project's main, ready-to-use output.

| Column | Description |
|---|---|
| (all extended-catalog columns) | see the table above |
| magnitude_scale_group | `moment_magnitude` / `local_magnitude` / `body_wave_magnitude` / `duration_magnitude` / `surface_wave_magnitude` / `diger` (other). Different magnitude scales are not directly comparable - filter by this column. |
| mw_estimate | Estimated Mw for ML-type records via an empirical conversion (see build_dataset.py). Empty for mb/md/ms. |
| nearest_station, nearest_station_distance_km | Nearest KOERI station (any type) |
| nearest_strong_motion_station, nearest_strong_motion_distance_km | Nearest real strong-motion station. Use this for engineering analysis. |
| nearest_sm_vs30_ms, nearest_sm_site_class | Site class of the nearest strong-motion station |
| has_waveform, num_waveform_files | Whether a real waveform was actually downloaded for this event, and from how many stations |
| max_pga_g, max_pgv_cms | If a waveform exists, the highest PGA (g) and PGV (cm/s). Computed preferentially from strong-motion records; falls back to broadband/short-period if none exist (see pga_from_strong_motion). |
| pga_from_strong_motion | Whether the max_pga_g/max_pgv_cms on this row really came from a strong-motion sensor (True) or fell back to broadband/short-period (False) |
| best_snr_db | If a waveform exists, the best signal-to-noise ratio (dB) |
| has_phase_pick | Whether the automatic P-wave pick succeeded |

Note: a single `max_pga_g` value for an event represents the highest
value among MULTIPLE stations downloaded for that event, and it may
belong to a different station than `nearest_strong_motion_distance_km`.
To compare PGA and distance from the same station (e.g. for an
attenuation plot), use `event_station_table.csv`.

## `data/processed/waveforms/{event_id}_{station}.mseed`

Raw, multi-component waveforms pulled from KOERI stations for
earthquakes with M>=4.5 (based on mw_estimate). Each record spans from
10 seconds before to 200 seconds after the event time. Source catalog:
the extended/deduplicated catalog
(`turkiye_deprem_katalogu_genisletilmis.parquet`); not limited to
events reported by USGS alone (see `scripts/fetch_waveforms_bulk.py`).

Station selection: starting from the nearest, stations are tried in
order until 4 successful downloads are obtained per event (up to 12
candidates, within 400km) - if some of the first 4 stations have no
data, the script moves on to the 5th, 6th, etc. Whether the relevant
channel (HH/HN/EH/BH) was actually active at the station at the time of
the event is checked against `koeri_channels.csv` (a station having a
sensor TODAY does not mean it had one in 2005).

Read with ObsPy: `from obspy import read; st = read("file.mseed")`

See `waveform_fetch_log.csv` for which event/station pairs were tried
and their outcome (`ok` / `no_data`).

## `data/processed/koeri_channels.csv`

The channel-level, time-ranged version of `koeri_stations.csv`
(`scripts/fetch_orfeus_eida.py`). A station's overall summary
information can change over time (a new sensor is added, an old one is
removed); this table keeps each channel's real start/end dates.

| Column | Description |
|---|---|
| network, station, location, channel | Identifying information |
| instrument_type | `strong_motion` / `broadband` / `short_period` |
| latitude, longitude, sample_rate_hz | Channel location and sampling rate |
| start_date, end_date | Date range the channel was active (still active if end_date is empty) |

## `data/processed/waveform_features.csv`

Signal features and quality-control (QC) fields computed for each
waveform file (`scripts/enrich_waveforms.py`).

| Column | Description |
|---|---|
| file | Waveform file path |
| event_id, station | Event and station id |
| network, location | SEED network/location code |
| channel_used, instrument_type_used | Which channel and sensor type (`strong_motion`/`broadband`/`short_period`) was used for the PGA/PGV computation. Strong-motion channel takes priority if present, otherwise falls back to broadband. |
| pga_g | Peak ground acceleration (g), instrument response removed, from `channel_used` |
| pgv_cms | Peak ground velocity (cm/s), instrument response removed |
| snr_db | Signal-to-noise ratio (dB), RMS ratio of the windows before/after the P arrival |
| p_pick_time, s_pick_time | Automatic phase pick (STA/LTA). S is a heuristic estimate, not publication quality. |
| p_pick_confidence, s_pick_confidence | Rough confidence score (0-1) based on STA/LTA trigger strength |
| sampling_rate_hz, duration_sec | Record's sampling rate and duration |
| num_gaps, gap_fraction | Number of gaps in the miniSEED data and the fraction of the record that is gaps |
| is_clipped | Suspected digitizer saturation (clipping) |
| has_three_components | Whether three distinct components (e.g. Z/N/E) are present |
| response_removed_ok | Whether instrument response removal succeeded |
| usable_for_engineering | PGA came from a strong-motion sensor AND there is no critical QC issue |
| usable_for_phase_picking | A P-phase pick exists AND there is no Z-component/gap issue |
| qc_flags | Comma-separated list of detected quality issues (e.g. `clipping_şüphesi`, `has_gaps`, `eksik_bileşen` - Turkish flag names, kept as produced by the pipeline) |
| sa_g_0_1s ... sa_g_2_0s | Pseudo-acceleration response spectrum (g) for a 5%-damped SDOF system, at periods 0.1/0.2/0.5/1.0/2.0 seconds (Newmark-beta, average acceleration method) |
| arias_intensity_ms | Arias intensity (m/s) |
| cav_ms | Cumulative absolute velocity - CAV (m/s) |
| duration_5_95_sec | Time to go from 5% to 95% of Arias intensity (significant duration) |
| fas_dominant_freq_hz, fas_mean_freq_hz | Peak frequency and amplitude-weighted mean frequency of the Fourier amplitude spectrum |

## `data/processed/event_station_table.csv`

A table where each row represents exactly ONE (event_id, station)
pair, produced so relationships like PGA-vs-distance can be examined in
a physically consistent way (`scripts/build_event_station_table.py`).

| Column | Description |
|---|---|
| event_id, station, network, location, channel_used, instrument_type_used | Identity and sensor information |
| event_latitude, event_longitude, depth_km | Event location |
| station_latitude, station_longitude | Station location |
| epicentral_distance_km | Surface (epicentral) distance |
| hypocentral_distance_km | True distance to the focus (hypocenter), including depth |
| magnitude, mag_type | Event magnitude and type |
| mw_estimate, time_utc | Scale-homogeneous magnitude estimate and event time |
| pga_g, pgv_cms, snr_db | Signal features at this station |
| sa_g_0_1s ... sa_g_2_0s, arias_intensity_ms, cav_ms, duration_5_95_sec | Engineering features, see waveform_features.csv |
| fas_dominant_freq_hz, fas_mean_freq_hz | Fourier spectrum summary |
| p_pick_time, s_pick_time, p_pick_confidence, s_pick_confidence | Phase picks |
| vs30_ms, nehrp_site_class, has_strong_motion | Station's site/sensor information |
| response_removed_ok, usable_for_engineering, usable_for_phase_picking, qc_flags | Quality flags |
| file | Waveform file path |

## `data/processed/isc_analyst_picks.csv`

Real, analyst-reviewed P/S picks pulled from the ISC Bulletin (with
`includearrivals=True`) (`scripts/fetch_isc_picks.py`). Only pulled for
events with an actually downloaded waveform. Unlike
`enrich_waveforms.py`'s automatic STA/LTA picks, these are real labels
verified by a seismology expert - a genuine ground-truth source for
phase-picking models.

| Column | Description |
|---|---|
| event_id, station | Identity information |
| phase_type | `P` or `S` |
| phase_hint | ISC's raw phase label (e.g. `Pn`, `Pg`, `Sg`) |
| pick_time | Analyst-reviewed arrival time |
| source | Always `isc_analyst` |

Limitation: the ISC Bulletin typically takes several months to reach
its final (reviewed) state, so very recent events may have no picks
yet; not every event has been reported to/processed by ISC.

## `benchmarks/`

Event-based train/val/test splits for three ML tasks (ground_motion,
phase_picking, early_warning). See `docs/benchmarks.md` for details.

## `data/processed/waveform_fetch_log.csv`

| Column | Description |
|---|---|
| event_id | Event id (the representative id in the extended catalog) |
| station | KOERI station code that was tried |
| distance_km | Event-station distance |
| magnitude | Raw event magnitude |
| event_source | Which institution reported the event (`reported_by`, e.g. `emsc,isc`) |
| status | `ok` (file saved) / `no_data` (no data at the station at that time) / `error: ...` |
| file | File path, if successful |

## `data/processed/validation_report.json`, `validation_report.md`

The quality summary that `scripts/validate_dataset.py` produces on
every run: which checks passed/failed and their detail. Used to
archive the quality status of every released version.
