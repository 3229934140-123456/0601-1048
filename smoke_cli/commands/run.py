from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..config import ConfigManager
from ..engine import ExecutionEngine
from ..models import TestResultStatus


app = typer.Typer(name="run", help="批量执行冒烟测试用例")
console = Console()


def _print_summary(report, engine=None):
    table = Table(title="🧪 冒烟测试执行摘要", show_header=True, header_style="bold cyan")
    table.add_column("指标", style="dim")
    table.add_column("值")

    total = report.total_cases
    pr = report.pass_rate
    rate_color = "green" if pr >= 90 else ("yellow" if pr >= 70 else "red")
    table.add_row("Run ID", f"[cyan]{report.run_id}[/]")
    table.add_row("版本 / Build", f"[green]{report.version}[/] (build {report.build})")
    table.add_row("设备", f"[{report.device.platform.value}] {report.device.device_name}")
    table.add_row("总用例数", str(total))
    table.add_row("通过", f"[green]{report.passed_cases}[/]")
    table.add_row("失败", f"[red]{report.failed_cases}[/]")
    table.add_row("错误", f"[magenta]{report.error_cases}[/]")
    table.add_row("跳过", f"[yellow]{report.skipped_cases}[/]")
    table.add_row("通过率", f"[{rate_color}]{pr:.2f}%[/]")
    table.add_row("总耗时", f"{report.total_duration_seconds:.2f}s ({report.total_duration_ms}ms)")
    console.print(table)

    if report.results:
        detail = Table(title="📋 用例明细", show_header=True, header_style="bold")
        detail.add_column("#", justify="right", style="dim")
        detail.add_column("用例")
        detail.add_column("风险", justify="center")
        detail.add_column("状态", justify="center")
        detail.add_column("耗时", justify="right")
        detail.add_column("重试", justify="right")
        detail.add_column("失败原因")

        for i, r in enumerate(report.results, 1):
            risk_color = {"high": "red", "medium": "yellow", "low": "green"}.get(r.case.risk_level.value, "white")
            status_icon = {
                TestResultStatus.PASSED: "[green]✓ PASS[/]",
                TestResultStatus.FAILED: "[red]✗ FAIL[/]",
                TestResultStatus.ERROR: "[magenta]! ERR[/]",
                TestResultStatus.SKIPPED: "[yellow]- SKIP[/]",
                TestResultStatus.RETRYING: "[cyan]↻ RETRY[/]",
            }.get(r.status, r.status.value)
            reason = r.error_message if r.error_message else "-"
            if len(reason) > 40:
                reason = reason[:37] + "..."
            detail.add_row(
                str(i),
                r.case.name,
                f"[{risk_color}]{r.case.risk_level.value.upper()}[/]",
                status_icon,
                f"{r.duration_seconds:.2f}s",
                str(r.retry_count),
                reason,
            )
        console.print(detail)

    fail_list = [r for r in report.results if r.status in (TestResultStatus.FAILED, TestResultStatus.ERROR)]
    if fail_list:
        console.print(Panel.fit("\n".join(
            f"  [red]●[/] [bold]{r.case.name}[/]\n"
            f"     原因: {r.error_message}\n"
            f"     截图: {r.failure_screenshot or '(无)'}"
            for r in fail_list
        ), title="❌ 失败列表", border_style="red"))


@app.command("all")
def run_all(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径"),
    tags: str = typer.Option("", "--tags", "-t", help="按标签过滤，逗号分隔，如 login,trade"),
    high_risk_only: bool = typer.Option(False, "--high-risk", "--high", help="只执行高风险(HIGH)用例"),
    retry: int = typer.Option(0, "--retry", "-r", min=0, max=5, help="失败重试次数，0 表示使用默认配置"),
    report_dir: Optional[Path] = typer.Option(None, "--report-dir", "-o", help="报告输出目录"),
    no_builtin: bool = typer.Option(False, "--no-builtin", help="不使用内置标准用例"),
    dry_run: bool = typer.Option(False, "--dry-run", help="模拟执行不连接真机"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出详细执行日志"),
    version: Optional[str] = typer.Option(None, "--version", "-V", help="覆盖配置中的版本号"),
    build: Optional[str] = typer.Option(None, "--build", "-b", help="覆盖配置中的 build 号"),
) -> None:
    """批量执行所有匹配的冒烟测试用例"""
    mgr = ConfigManager(path or Path.cwd())
    if not mgr.is_initialized:
        console.print("[bold red]✗[/] 项目未初始化，请先执行 smoke init new")
        raise typer.Exit(code=1)

    if version:
        mgr.set("version", version)
    if build:
        mgr.set("build", build)

    retry_count = retry or mgr.get("default_retry", 1)
    tag_set = {t.strip() for t in tags.split(",") if t.strip()}

    engine = ExecutionEngine(
        config_mgr=mgr,
        retry=retry_count,
        high_risk_only=high_risk_only,
        tags=tag_set,
        report_dir=report_dir,
        dry_run=dry_run,
        use_builtin=not no_builtin,
        verbose=verbose,
    )

    report = engine.run_all()
    _print_summary(report)

    pr = report.pass_rate
    console.print()
    if pr >= 90:
        console.print(Panel.fit("[bold green]🎉 冒烟检查通过！[/]\n通过率达到 90% 以上，可进入发版流程", border_style="green"))
    elif pr >= 70:
        console.print(Panel.fit("[bold yellow]⚠ 冒烟检查存在风险[/]\n通过率低于 90%，建议修复失败用例后重试", border_style="yellow"))
    else:
        console.print(Panel.fit("[bold red]❌ 冒烟检查不通过[/]\n存在大量失败用例，不建议进入发版流程", border_style="red"))
        raise typer.Exit(code=2)


@app.command("case")
def run_case(
    names: list[str] = typer.Argument(..., help="要执行的用例名称，可多个"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径"),
    retry: int = typer.Option(0, "--retry", "-r", help="失败重试次数"),
    report_dir: Optional[Path] = typer.Option(None, "--report-dir", "-o", help="报告输出目录"),
    dry_run: bool = typer.Option(False, "--dry-run", help="模拟执行"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细日志"),
) -> None:
    """按名称执行指定一个或多个测试用例"""
    mgr = ConfigManager(path or Path.cwd())
    if not mgr.is_initialized:
        console.print("[bold red]✗[/] 项目未初始化，请先执行 smoke init new")
        raise typer.Exit(code=1)

    retry_count = retry or mgr.get("default_retry", 1)
    engine = ExecutionEngine(
        config_mgr=mgr,
        retry=retry_count,
        report_dir=report_dir,
        dry_run=dry_run,
        use_builtin=True,
        verbose=verbose,
    )
    report = engine.run_all(case_names=list(names))
    _print_summary(report)


@app.command("builtin")
def run_builtin(
    keys: Optional[list[str]] = typer.Argument(None, help="内置用例 key: login/order/payment_mock/message/settings/login_fail，留空表示全部"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径"),
    retry: int = typer.Option(0, "--retry", "-r", help="失败重试次数"),
    report_dir: Optional[Path] = typer.Option(None, "--report-dir", "-o", help="报告输出目录"),
    high_risk_only: bool = typer.Option(False, "--high-risk", "--high", help="只执行高风险"),
    dry_run: bool = typer.Option(False, "--dry-run", help="模拟执行"),
) -> None:
    """仅执行内置标准冒烟用例集合"""
    from ..cases import get_builtin_case, list_builtin_cases

    mgr = ConfigManager(path or Path.cwd())
    if not mgr.is_initialized:
        console.print("[bold red]✗[/] 项目未初始化，请先执行 smoke init new")
        raise typer.Exit(code=1)

    if keys:
        builtin_names = []
        for k in keys:
            bc = get_builtin_case(k)
            if bc:
                builtin_names.append(bc.name)
            else:
                console.print(f"[yellow]⚠[/] 未知内置用例 key: {k}，可用: login,login_fail,order,payment_mock,message,settings")
    else:
        builtin_names = [c.name for c in list_builtin_cases()]

    retry_count = retry or mgr.get("default_retry", 1)
    engine = ExecutionEngine(
        config_mgr=mgr,
        retry=retry_count,
        high_risk_only=high_risk_only,
        report_dir=report_dir,
        dry_run=dry_run,
        use_builtin=True,
    )
    report = engine.run_all(case_names=builtin_names)
    _print_summary(report)
