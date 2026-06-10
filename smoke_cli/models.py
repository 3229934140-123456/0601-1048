from __future__ import annotations

import time
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class RiskLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class StepAction(str, Enum):
    CLICK = "click"
    INPUT = "input"
    SWIPE = "swipe"
    ASSERT = "assert"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    BACK = "back"


class DevicePlatform(str, Enum):
    ANDROID = "android"
    IOS = "ios"


class TestStep(BaseModel):
    action: StepAction
    target: Optional[str] = None
    value: Optional[str] = None
    description: Optional[str] = None
    timeout: int = 10

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=True)


class TestAccount(BaseModel):
    username: str
    password: str
    role: str = "default"
    extra: dict[str, Any] = Field(default_factory=dict)


class DeviceConfig(BaseModel):
    platform: DevicePlatform = DevicePlatform.ANDROID
    platform_version: str = "13.0"
    device_name: str = "emulator-5554"
    app_package: str = "com.example.app"
    app_activity: str = ".MainActivity"
    udid: Optional[str] = None
    no_reset: bool = True
    auto_launch: bool = True
    extras: dict[str, Any] = Field(default_factory=dict)


class TestCaseConfig(BaseModel):
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    steps: list[TestStep] = Field(default_factory=list)
    account: Optional[str] = None
    enabled: bool = True
    timeout: int = 120


class TestResultStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    RETRYING = "retrying"


class StepResult(BaseModel):
    step: TestStep
    status: TestResultStatus
    message: str = ""
    duration_ms: int = 0
    screenshot: Optional[str] = None


class TestCaseResult(BaseModel):
    case: TestCaseConfig
    status: TestResultStatus
    start_time: float = Field(default_factory=time.time)
    end_time: float = 0.0
    duration_ms: int = 0
    retry_count: int = 0
    step_results: list[StepResult] = Field(default_factory=list)
    error_message: str = ""
    logs: list[str] = Field(default_factory=list)
    failure_screenshot: Optional[str] = None
    version: str = ""
    build: str = ""

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000.0


class TestRunReport(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    version: str
    build: str
    start_time: float
    end_time: float = 0.0
    device: DeviceConfig
    total_duration_ms: int = 0
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    skipped_cases: int = 0
    error_cases: int = 0
    results: list[TestCaseResult] = Field(default_factory=list)
    report_dir: str = ""

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return (self.passed_cases / self.total_cases) * 100.0

    @property
    def total_duration_seconds(self) -> float:
        return self.total_duration_ms / 1000.0


class VersionDiff(BaseModel):
    version_a: str
    version_b: str
    field_diffs: list[str] = Field(default_factory=list)
    new_cases: list[str] = Field(default_factory=list)
    removed_cases: list[str] = Field(default_factory=list)
    regression_cases: list[str] = Field(default_factory=list)
    fixed_cases: list[str] = Field(default_factory=list)
    pass_rate_a: float = 0.0
    pass_rate_b: float = 0.0
    duration_diff_ms: int = 0
