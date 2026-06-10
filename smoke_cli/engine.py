from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from rich.console import Console

from .config import ConfigManager, Logger
from .models import (
    DeviceConfig,
    RiskLevel,
    StepAction,
    StepResult,
    TestAccount,
    TestCaseConfig,
    TestCaseResult,
    TestResultStatus,
    TestRunReport,
    TestStep,
)
from .cases import get_builtin_case, list_builtin_cases


console = Console()


VARIABLE_PATTERN = re.compile(r"\{\{\s*([\w\.]+)\s*\}\}")


@dataclass
class ExecutionContext:
    run_id: str
    version: str
    build: str
    device: DeviceConfig
    accounts: list[TestAccount]
    screenshot_dir: Path
    log_dir: Path
    variables: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False
    fail_rate: float = 0.1
    random_seed: int = 42

    def get_account(self, role: Optional[str]) -> Optional[TestAccount]:
        if not role:
            return self.accounts[0] if self.accounts else None
        for a in self.accounts:
            if a.role == role:
                return a
        return None

    def resolve(self, text: Optional[str], account: Optional[TestAccount] = None) -> Optional[str]:
        if not text:
            return text
        def repl(m: re.Match) -> str:
            key = m.group(1)
            if key == "version":
                return self.version
            if key == "build":
                return self.build
            if account:
                if key == "username":
                    return account.username
                if key == "password":
                    return account.password
                if key.startswith("extra."):
                    k = key.split(".", 1)[1]
                    return str(account.extra.get(k, ""))
            return str(self.variables.get(key, m.group(0)))
        return VARIABLE_PATTERN.sub(repl, text)


class ExecutionEngine:
    def __init__(
        self,
        config_mgr: ConfigManager,
        retry: int = 1,
        high_risk_only: bool = False,
        tags: Optional[set[str]] = None,
        report_dir: Optional[Path] = None,
        dry_run: bool = False,
        use_builtin: bool = True,
        verbose: bool = False,
    ) -> None:
        self.config_mgr = config_mgr
        self.retry = max(1, retry)
        self.high_risk_only = high_risk_only
        self.tags = tags or set()
        self.report_dir = Path(report_dir or config_mgr.get("report_dir", "./reports"))
        self.dry_run = dry_run
        self.use_builtin = use_builtin
        self.verbose = verbose

        self._rng = random.Random(42)

    def _collect_cases(self) -> list[TestCaseConfig]:
        cases: list[TestCaseConfig] = list(self.config_mgr.get_cases())
        if self.use_builtin:
            existing_names = {c.name for c in cases}
            for bc in list_builtin_cases():
                if bc.name not in existing_names:
                    cases.append(bc)
        return [c for c in cases if c.enabled]

    def filter_cases(self, cases: list[TestCaseConfig]) -> list[TestCaseConfig]:
        result = []
        for c in cases:
            if self.high_risk_only and c.risk_level != RiskLevel.HIGH:
                continue
            if self.tags and not (set(c.tags) & self.tags):
                continue
            result.append(c)
        return result

    def _make_context(self, run_id: str) -> ExecutionContext:
        device = self.config_mgr.get_default_device() or DeviceConfig()
        ss_dir = self.report_dir / "screenshots" / run_id
        log_dir = self.report_dir / "logs" / run_id
        ss_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        return ExecutionContext(
            run_id=run_id,
            version=self.config_mgr.get("version", "1.0.0"),
            build=self.config_mgr.get("build", "0001"),
            device=device,
            accounts=self.config_mgr.get_accounts(),
            screenshot_dir=ss_dir,
            log_dir=log_dir,
            dry_run=self.dry_run,
        )

    def _should_fail(self, risk_level: RiskLevel) -> bool:
        weights = {RiskLevel.HIGH: 0.12, RiskLevel.MEDIUM: 0.08, RiskLevel.LOW: 0.04}
        prob = weights.get(risk_level, 0.08)
        return self._rng.random() < prob

    def _simulate_step(
        self,
        step: TestStep,
        ctx: ExecutionContext,
        case: TestCaseConfig,
        account: Optional[TestAccount],
        logger: Logger,
    ) -> tuple[TestResultStatus, str, Optional[str]]:
        target = ctx.resolve(step.target, account)
        value = ctx.resolve(step.value, account)
        desc = step.description or step.action.value

        logger.info(f"Step {step.action.value}: target={target}, value={value} ({desc})")

        start = time.time()
        if not ctx.dry_run:
            sleep_ms = min(step.timeout * 1000, 20 + self._rng.randint(5, 60))
            time.sleep(sleep_ms / 1000.0)

        fail = self._should_fail(case.risk_level)
        screenshot_path: Optional[str] = None

        if step.action == StepAction.SCREENSHOT:
            filename = f"{ctx.run_id}_{case.name}_{int(time.time()*1000)}.png"
            screenshot_path = str(ctx.screenshot_dir / filename)
            Path(screenshot_path).touch()
            logger.info(f"截图保存: {screenshot_path}")

        if fail and step.action == StepAction.ASSERT:
            err_msg = f"断言失败: 期望 {value}，实际不符合 (target={target})"
            logger.error(err_msg)
            filename = f"FAIL_{ctx.run_id}_{case.name}_{int(time.time()*1000)}.png"
            screenshot_path = str(ctx.screenshot_dir / filename)
            Path(screenshot_path).touch()
            return TestResultStatus.FAILED, err_msg, screenshot_path

        if fail and step.action in (StepAction.CLICK, StepAction.INPUT) and self._rng.random() < 0.3:
            err_msg = f"元素未找到或超时: {target}"
            logger.error(err_msg)
            filename = f"FAIL_{ctx.run_id}_{case.name}_{int(time.time()*1000)}.png"
            screenshot_path = str(ctx.screenshot_dir / filename)
            Path(screenshot_path).touch()
            return TestResultStatus.ERROR, err_msg, screenshot_path

        if step.action in (StepAction.WAIT,):
            pass

        dur = int((time.time() - start) * 1000)
        msg = f"OK ({dur}ms)"
        return TestResultStatus.PASSED, msg, screenshot_path

    def run_case(
        self,
        case: TestCaseConfig,
        ctx: ExecutionContext,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> TestCaseResult:
        start = time.time()
        account = ctx.get_account(case.account)
        log_file = ctx.log_dir / f"{case.name.replace('/', '_')}.log"
        logger = Logger(log_file)
        logger.info(f"===== 开始执行用例: {case.name} =====")
        logger.info(f"风险等级: {case.risk_level.value}, Tags: {case.tags}")
        if account:
            logger.info(f"使用账号: [{account.role}] {account.username}")

        final_result = TestCaseResult(
            case=case,
            status=TestResultStatus.SKIPPED,
            version=ctx.version,
            build=ctx.build,
        )

        for attempt in range(1, self.retry + 1):
            attempt_start = time.time()
            logger.info(f"--- 第 {attempt}/{self.retry} 次尝试 ---")
            step_results: list[StepResult] = []
            all_passed = True
            last_screenshot: Optional[str] = None
            error_msg = ""

            for i, step in enumerate(case.steps, 1):
                if progress_cb:
                    progress_cb(i, len(case.steps), step.description or step.action.value)
                status, msg, screenshot = self._simulate_step(step, ctx, case, account, logger)
                step_start = time.time()
                dur = int((time.time() - step_start) * 1000) + 100
                sr = StepResult(
                    step=step,
                    status=status,
                    message=msg,
                    duration_ms=dur,
                    screenshot=screenshot,
                )
                step_results.append(sr)
                if screenshot:
                    last_screenshot = screenshot
                if status in (TestResultStatus.FAILED, TestResultStatus.ERROR):
                    all_passed = False
                    error_msg = msg
                    break

            end = time.time()
            final_result = TestCaseResult(
                case=case,
                status=TestResultStatus.PASSED if all_passed else (TestResultStatus.FAILED if error_msg and "断言" in error_msg else TestResultStatus.ERROR),
                start_time=start,
                end_time=end,
                duration_ms=int((end - attempt_start) * 1000),
                retry_count=attempt - 1,
                step_results=step_results,
                error_message=error_msg,
                logs=logger.entries,
                failure_screenshot=None if all_passed else last_screenshot,
                version=ctx.version,
                build=ctx.build,
            )

            if all_passed:
                logger.info(f"用例通过 (耗时 {final_result.duration_ms}ms)")
                break
            else:
                logger.warn(f"用例失败: {error_msg}，第 {attempt} 次尝试")
                if attempt < self.retry:
                    logger.info("等待 0.1s 后重试...")
                    time.sleep(0.1)

        logger.info(f"===== 用例结束: {case.name} -> {final_result.status.value} =====")
        final_result.logs = logger.entries
        return final_result

    def run_all(
        self,
        case_names: Optional[list[str]] = None,
        progress_cb: Optional[Callable[[int, int, TestCaseConfig], None]] = None,
    ) -> TestRunReport:
        from .config import ReportManager

        rm = ReportManager(self.config_mgr)
        run_id = rm.generate_run_id()
        ctx = self._make_context(run_id)

        all_cases = self._collect_cases()
        if case_names:
            name_set = set(case_names)
            all_cases = [c for c in all_cases if c.name in name_set]
            for cn in case_names:
                bc = get_builtin_case(cn)
                if bc and bc.name not in {c.name for c in all_cases}:
                    all_cases.append(bc)
        all_cases = self.filter_cases(all_cases)

        if not all_cases:
            console.print("[yellow]⚠[/] 没有匹配的测试用例可执行")

        start_time = time.time()
        results: list[TestCaseResult] = []

        console.print(f"\n[bold cyan]▶[/] 开始冒烟测试 run_id=[green]{run_id}[/]  版本=[green]{ctx.version}[/] build=[green]{ctx.build}[/]")
        console.print(f"  设备: [{ctx.device.platform.value}] {ctx.device.device_name}")
        console.print(f"  用例数: {len(all_cases)}  重试次数: {self.retry}")
        if self.high_risk_only:
            console.print(f"  [yellow]仅执行 HIGH 风险用例[/]")
        if self.tags:
            console.print(f"  标签过滤: {','.join(self.tags)}")
        console.print()

        for i, case in enumerate(all_cases, 1):
            if progress_cb:
                progress_cb(i, len(all_cases), case)
            risk_color = {"high": "red", "medium": "yellow", "low": "green"}.get(case.risk_level.value, "white")
            console.print(f"[{i}/{len(all_cases)}] ▶ 执行 [bold]{case.name}[/]  [{risk_color}]{case.risk_level.value}[/]  ({len(case.steps)}步)")
            with console.status(f"  运行中..."):
                r = self.run_case(case, ctx)
            icon = {"passed": "[green]✓[/]", "failed": "[red]✗[/]", "error": "[magenta]![/]", "skipped": "[yellow]-[/]"}.get(r.status.value, "?")
            retry_str = f" [dim]重试{r.retry_count}次[/]" if r.retry_count > 0 else ""
            console.print(f"  {icon} {r.status.value.upper():<7} 耗时 {r.duration_seconds:.2f}s{retry_str}")
            if r.error_message:
                console.print(f"     [dim red]{r.error_message}[/]")
            results.append(r)

        end_time = time.time()
        total_duration = int((end_time - start_time) * 1000)

        passed = sum(1 for r in results if r.status == TestResultStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestResultStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestResultStatus.ERROR)
        skipped = sum(1 for r in results if r.status == TestResultStatus.SKIPPED)

        report = TestRunReport(
            run_id=run_id,
            version=ctx.version,
            build=ctx.build,
            start_time=start_time,
            end_time=end_time,
            device=ctx.device,
            total_duration_ms=total_duration,
            total_cases=len(results),
            passed_cases=passed,
            failed_cases=failed,
            skipped_cases=skipped,
            error_cases=errors,
            results=results,
            report_dir=str(self.report_dir),
        )

        self.report_dir.mkdir(parents=True, exist_ok=True)
        report_path = rm.save_report(report)
        console.print(f"\n[bold green]✓[/] 报告已保存: [cyan]{report_path}[/]")
        return report
