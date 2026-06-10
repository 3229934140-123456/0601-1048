from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml
from rich.console import Console

from .models import (
    DeviceConfig,
    TestAccount,
    TestCaseConfig,
    TestRunReport,
)


console = Console()


class ConfigManager:
    DEFAULT_CONFIG: dict[str, Any] = {
        "project_name": "mobile_smoke_test",
        "version": "1.0.0",
        "build": "0001",
        "report_dir": "./reports",
        "screenshot_dir": "./reports/screenshots",
        "log_dir": "./reports/logs",
        "default_retry": 1,
        "devices": [],
        "accounts": [],
        "cases": [],
    }

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = Path(project_root or Path.cwd())
        self.config_file = self.project_root / "smoke_config.yaml"
        self._config: Optional[dict[str, Any]] = None

    @property
    def is_initialized(self) -> bool:
        return self.config_file.exists()

    @property
    def config(self) -> dict[str, Any]:
        if self._config is None:
            self.load()
        return self._config or {}

    def load(self) -> dict[str, Any]:
        if not self.config_file.exists():
            self._config = self.DEFAULT_CONFIG.copy()
            return self._config
        with open(self.config_file, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}
        return self._config

    def save(self) -> None:
        import copy
        self.project_root.mkdir(parents=True, exist_ok=True)
        data = copy.deepcopy(self._config or self.DEFAULT_CONFIG)

        def _clean(o):
            if isinstance(o, dict):
                return {k: _clean(v) for k, v in o.items()}
            if isinstance(o, list):
                return [_clean(v) for v in o]
            if hasattr(o, "value"):
                return o.value
            return o

        data = _clean(data)
        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False, Dumper=yaml.SafeDumper)

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if self._config is None:
            self.load()
        self._config[key] = value

    def get_devices(self) -> list[DeviceConfig]:
        return [DeviceConfig(**d) for d in self.config.get("devices", [])]

    def add_device(self, device: DeviceConfig) -> None:
        devices = self.config.get("devices", [])
        devices.append(device.model_dump(mode="json"))
        self.set("devices", devices)

    def get_accounts(self) -> list[TestAccount]:
        return [TestAccount(**a) for a in self.config.get("accounts", [])]

    def add_account(self, account: TestAccount) -> None:
        accounts = self.config.get("accounts", [])
        accounts.append(account.model_dump(mode="json"))
        self.set("accounts", accounts)

    def get_cases(self) -> list[TestCaseConfig]:
        return [TestCaseConfig(**c) for c in self.config.get("cases", [])]

    def add_case(self, case: TestCaseConfig) -> None:
        cases = self.config.get("cases", [])
        cases.append(case.model_dump(mode="json"))
        self.set("cases", cases)

    def update_case(self, case_name: str, case: TestCaseConfig) -> bool:
        cases = self.config.get("cases", [])
        for i, c in enumerate(cases):
            if c.get("name") == case_name:
                cases[i] = case.model_dump(mode="json")
                self.set("cases", cases)
                return True
        return False

    def get_case_by_name(self, name: str) -> Optional[TestCaseConfig]:
        for c in self.get_cases():
            if c.name == name:
                return c
        return None

    def get_default_device(self) -> Optional[DeviceConfig]:
        devices = self.get_devices()
        return devices[0] if devices else None

    def get_report_dir(self) -> Path:
        return self.project_root / self.config.get("report_dir", "./reports")

    def get_screenshot_dir(self, run_id: str) -> Path:
        base = self.project_root / self.config.get("screenshot_dir", "./reports/screenshots")
        return base / run_id

    def get_log_dir(self, run_id: str) -> Path:
        base = self.project_root / self.config.get("log_dir", "./reports/logs")
        return base / run_id

    def ensure_dirs(self, run_id: str) -> None:
        self.get_report_dir().mkdir(parents=True, exist_ok=True)
        self.get_screenshot_dir(run_id).mkdir(parents=True, exist_ok=True)
        self.get_log_dir(run_id).mkdir(parents=True, exist_ok=True)


class ReportManager:
    def __init__(self, config: ConfigManager):
        self.config = config

    def generate_run_id(self) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:6]
        return f"run_{ts}_{uid}"

    def save_report(self, report: TestRunReport) -> Path:
        report_dir = self.config.get_report_dir()
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{report.run_id}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
        return report_path

    def load_report(self, run_id: str) -> Optional[TestRunReport]:
        report_dir = self.config.get_report_dir()
        candidates = [
            report_dir / f"{run_id}.json",
            report_dir / run_id,
        ]
        for path in candidates:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return TestRunReport(**data)
        return None

    def list_reports(self) -> list[Path]:
        report_dir = self.config.get_report_dir()
        if not report_dir.exists():
            return []
        return sorted(
            [p for p in report_dir.glob("*.json") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def get_latest_report(self) -> Optional[TestRunReport]:
        reports = self.list_reports()
        if not reports:
            return None
        with open(reports[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        return TestRunReport(**data)


class Logger:
    def __init__(self, log_file: Optional[Path] = None):
        self.log_file = log_file
        self.entries: list[str] = []

    def log(self, level: str, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        entry = f"[{ts}] [{level.upper()}] {message}"
        self.entries.append(entry)
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")

    def info(self, msg: str) -> None:
        self.log("INFO", msg)

    def warn(self, msg: str) -> None:
        self.log("WARN", msg)

    def error(self, msg: str) -> None:
        self.log("ERROR", msg)

    def debug(self, msg: str) -> None:
        self.log("DEBUG", msg)
