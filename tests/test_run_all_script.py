import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ALL = ROOT / "scripts" / "run_all.sh"


def run_with_fake_python(tmp_path: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    log_path = tmp_path / "python_calls.txt"
    fake_python = tmp_path / "python"
    fake_python.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> \"$RUN_ALL_CALL_LOG\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    env["RUN_ALL_CALL_LOG"] = str(log_path)

    result = subprocess.run(
        ["bash", str(RUN_ALL), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    return result, calls


def test_skip_isc_picks_runs_remaining_steps(tmp_path: Path) -> None:
    result, calls = run_with_fake_python(tmp_path, "--skip-isc-picks")

    assert result.returncode == 0
    assert "scripts/fetch_isc_picks.py" not in calls
    assert "scripts/build_event_station_table.py" in calls
    assert "scripts/build_benchmarks.py" in calls
    assert "--skip-isc-picks ile atlandı" in result.stdout


def test_default_run_keeps_isc_picks_step(tmp_path: Path) -> None:
    result, calls = run_with_fake_python(tmp_path)

    assert result.returncode == 0
    assert "scripts/fetch_isc_picks.py" in calls


def test_unknown_argument_fails_before_pipeline_starts(tmp_path: Path) -> None:
    result, calls = run_with_fake_python(tmp_path, "--bilinmeyen")

    assert result.returncode == 2
    assert calls == []
    assert "Bilinmeyen argüman: --bilinmeyen" in result.stderr
    assert "Kullanım:" in result.stderr


def test_ci_waveform_download_uses_the_revision_from_the_cache_key() -> None:
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

    assert 'key: waveforms-${{ steps.hf_rev.outputs.sha }}' in workflow
    assert 'HF_DATASET_REVISION: ${{ steps.hf_rev.outputs.sha }}' in workflow
    assert '--revision "$HF_DATASET_REVISION"' in workflow
