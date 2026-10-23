"""c16: a `report` job runs `optscan health` at 16:00, off by default."""

from datetime import time

from optscan.config import Settings
from optscan.jobs.schedule import jobs


def test_report_job() -> None:
    found = {job.key: job for job in jobs(Settings.model_construct())}
    assert "report" in found
    job = found["report"]
    assert job.at == time(16, 0)
    assert job.default_install is False
    assert "health" in job.arguments
