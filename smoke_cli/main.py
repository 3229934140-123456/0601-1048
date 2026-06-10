from __future__ import annotations

import os
import sys
from typing import Optional

import typer
from rich.console import Console

from .commands import compare_app, init_app, record_app, report_app, run_app


if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


app = typer.Typer(
    name="smoke",
    help="移动 App 冒烟测试 CLI 工具 - 发版前自动化质量检查",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        from . import __version__
        console.print(f"smoke-cli version [bold green]{__version__}[/]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version", "-V",
        help="显示版本号",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """
    📱 [bold]smoke-cli[/] 移动 App 发版前冒烟测试命令行工具

    五大核心命令:

    • [bold cyan]init[/]    初始化项目配置、设备、测试账号、示例用例
    • [bold cyan]record[/]  录制测试步骤、添加账号、列出用例
    • [bold cyan]run[/]     批量执行用例，支持重试/标签/高风险过滤
    • [bold cyan]report[/]  查看通过率、失败截图、耗时排行、日志，导出 HTML
    • [bold cyan]compare[/] 对比两次报告：回归、修复、耗时差异
    """
    return


app.add_typer(init_app, name="init")
app.add_typer(record_app, name="record")
app.add_typer(run_app, name="run")
app.add_typer(report_app, name="report")
app.add_typer(compare_app, name="compare")


def entry_point() -> None:
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断执行[/]")
        raise typer.Exit(code=130)


if __name__ == "__main__":
    entry_point()
