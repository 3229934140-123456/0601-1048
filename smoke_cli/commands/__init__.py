from __future__ import annotations

from .init import app as init_app
from .record import app as record_app
from .run import app as run_app
from .report import app as report_app
from .compare import app as compare_app

__all__ = ["init_app", "record_app", "run_app", "report_app", "compare_app"]
