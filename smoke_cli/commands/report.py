from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from jinja2 import Template
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..config import ConfigManager, ReportManager
from ..models import TestResultStatus


app = typer.Typer(name="report", help="查看与导出测试报告：通过率、失败截图、耗时排行、关键日志")
console = Console()


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>冒烟测试报告 - {{ report.version }} ({{ report.run_id }})</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, "Segoe UI", Arial, sans-serif; background: #f5f7fa; color: #2c3e50; padding: 20px; }
.container { max-width: 1200px; margin: 0 auto; }
.header { background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }
.header h1 { font-size: 24px; margin-bottom: 10px; }
.header .meta { opacity: 0.9; font-size: 14px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 16px; margin-bottom: 24px; }
.card { background: white; border-radius: 10px; padding: 18px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.card .label { font-size: 13px; color: #95a5a6; margin-bottom: 6px; }
.card .value { font-size: 28px; font-weight: 700; }
.card.pass .value { color: #27ae60; }
.card.fail .value { color: #e74c3c; }
.card.err .value { color: #9b59b6; }
.card.rate .value { color: {{ '#27ae60' if report.pass_rate >= 90 else '#f39c12' if report.pass_rate >= 70 else '#e74c3c' }}; }
.section { background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.section h2 { font-size: 18px; margin-bottom: 16px; color: #34495e; border-left: 4px solid #667eea; padding-left: 10px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #ecf0f1; font-size: 14px; }
th { background: #f8f9fa; color: #7f8c8d; font-weight: 600; }
tr:hover { background: #f8f9fa; }
.badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge.pass { background: #d5f5e3; color: #1e8449; }
.badge.fail { background: #fadbd8; color: #c0392b; }
.badge.err { background: #e8daef; color: #8e44ad; }
.badge.skip { background: #fcf3cf; color: #b7950b; }
.badge.high { background: #fadbd8; color: #c0392b; }
.badge.medium { background: #fef9e7; color: #b7950b; }
.badge.low { background: #d5f5e3; color: #1e8449; }
.log-box { background: #2c3e50; color: #ecf0f1; padding: 14px; border-radius: 8px; font-family: Consolas, monospace; font-size: 13px; max-height: 240px; overflow: auto; white-space: pre-wrap; margin-bottom: 12px; }
.screenshot { max-width: 100%; border: 1px solid #ddd; border-radius: 6px; margin-top: 8px; }
.failure-item { border-left: 3px solid #e74c3c; padding: 10px 14px; margin-bottom: 14px; background: #fdf5f4; border-radius: 4px; }
.bar-chart { display: flex; flex-direction: column; gap: 10px; }
.bar-row { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.bar-row .name { width: 220px; flex-shrink: 0; }
.bar-row .track { flex: 1; background: #ecf0f1; height: 22px; border-radius: 11px; overflow: hidden; }
.bar-row .fill { height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); display: flex; align-items: center; justify-content: flex-end; padding-right: 8px; color: white; font-size: 12px; font-weight: 600; }
.footer { text-align: center; color: #95a5a6; font-size: 13px; margin-top: 30px; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📱 移动 App 冒烟测试报告</h1>
    <div class="meta">
      Run ID: <strong>{{ report.run_id }}</strong> &nbsp;|&nbsp;
      版本: <strong>{{ report.version }}</strong> (build {{ report.build }}) &nbsp;|&nbsp;
      设备: <strong>{{ report.device.platform.value }} {{ report.device.platform_version }}</strong> / {{ report.device.device_name }} &nbsp;|&nbsp;
      时间: <strong>{{ start_time_str }}</strong>
    </div>
  </div>

  <div class="cards">
    <div class="card"><div class="label">总用例</div><div class="value">{{ report.total_cases }}</div></div>
    <div class="card pass"><div class="label">通过</div><div class="value">{{ report.passed_cases }}</div></div>
    <div class="card fail"><div class="label">失败</div><div class="value">{{ report.failed_cases }}</div></div>
    <div class="card err"><div class="label">错误</div><div class="value">{{ report.error_cases }}</div></div>
    <div class="card"><div class="label">跳过</div><div class="value" style="color:#f39c12">{{ report.skipped_cases }}</div></div>
    <div class="card rate"><div class="label">通过率</div><div class="value">{{ '%.2f'|format(report.pass_rate) }}%</div></div>
    <div class="card"><div class="label">总耗时</div><div class="value" style="font-size:22px">{{ '%.2f'|format(report.total_duration_seconds) }}s</div></div>
  </div>

  {% if failures %}
  <div class="section">
    <h2>❌ 失败用例与截图</h2>
    {% for r in failures %}
      <div class="failure-item">
        <strong>{{ r.case.name }}</strong>
        <span class="badge {{ 'fail' if r.status == 'failed' else 'err' }}">{{ r.status.value.upper() }}</span>
        <span class="badge {{ r.case.risk_level.value }}">{{ r.case.risk_level.value.upper() }}</span>
        <div style="margin:6px 0;color:#c0392b;">原因: {{ r.error_message or '(无)' }}</div>
        {% if r.failure_screenshot %}
          <div>截图: {{ r.failure_screenshot }}</div>
        {% endif %}
        {% if r.logs %}
          <details style="margin-top:8px">
            <summary style="cursor:pointer;color:#3498db;">展开关键日志 ({{ r.logs|length }} 条)</summary>
            <div class="log-box">{{ r.logs[-20:]|join('\n') }}</div>
          </details>
        {% endif %}
      </div>
    {% endfor %}
  </div>
  {% endif %}

  <div class="section">
    <h2>⏱️ 耗时排行 Top 10 (秒)</h2>
    <div class="bar-chart">
      {% for r in top_slow %}
        <div class="bar-row">
          <div class="name">{{ r.case.name }}</div>
          <div class="track">
            <div class="fill" style="width:{{ (r.duration_seconds / top_slow[0].duration_seconds * 100)|round if top_slow else 0 }}%">
              {{ '%.2f'|format(r.duration_seconds) }}s
            </div>
          </div>
        </div>
      {% endfor %}
    </div>
  </div>

  <div class="section">
    <h2>📋 全部用例明细</h2>
    <table>
      <thead>
        <tr><th>#</th><th>用例名称</th><th>风险</th><th>标签</th><th>状态</th><th>耗时</th><th>重试</th><th>步骤</th></tr>
      </thead>
      <tbody>
        {% for r in report.results %}
          <tr>
            <td>{{ loop.index }}</td>
            <td>{{ r.case.name }}</td>
            <td><span class="badge {{ r.case.risk_level.value }}">{{ r.case.risk_level.value.upper() }}</span></td>
            <td>{{ ', '.join(r.case.tags) or '-' }}</td>
            <td><span class="badge {{ r.status.value }}">{{ r.status.value.upper() }}</span></td>
            <td>{{ '%.2f'|format(r.duration_seconds) }}s</td>
            <td>{{ r.retry_count }}</td>
            <td>{{ r.step_results|length }}/{{ r.case.steps|length }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  {% if critical_logs %}
  <div class="section">
    <h2>🔎 关键日志 (ERROR/WARN)</h2>
    {% for case_name, logs in critical_logs.items() %}
      <div style="margin-bottom:10px">
        <strong>{{ case_name }}</strong>
        <div class="log-box">{{ logs|join('\n') }}</div>
      </div>
    {% endfor %}
  </div>
  {% endif %}

  <div class="footer">
    由 smoke-cli 自动生成 · {{ generated_at }}
  </div>
</div>
</body>
</html>
"""


def _format_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _build_report_assets(report):
    failures = [r for r in report.results if r.status in (TestResultStatus.FAILED, TestResultStatus.ERROR)]
    top_slow = sorted(report.results, key=lambda r: r.duration_seconds, reverse=True)[:10]
    critical_logs: dict[str, list[str]] = {}
    for r in report.results:
        bad = [l for l in r.logs if any(k in l for k in ("ERROR", "WARN", "FAIL", "断言失败", "未找到"))]
        if bad:
            critical_logs[r.case.name] = bad[-30:]
    return failures, top_slow, critical_logs


@app.command("show")
def show_report(
    run_id: Optional[str] = typer.Argument(None, help="报告 ID 或路径，留空查看最新"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径"),
    failures_only: bool = typer.Option(False, "--failures-only", "-f", help="仅展示失败用例"),
    show_logs: bool = typer.Option(False, "--logs", "-l", help="展示关键日志"),
    top: int = typer.Option(10, "--top", "-t", help="耗时排行显示数量"),
) -> None:
    """在控制台展示测试报告（通过率、失败截图、耗时排行、关键日志）"""
    mgr = ConfigManager(path or Path.cwd())
    if not mgr.is_initialized:
        console.print("[bold red]✗[/] 项目未初始化")
        raise typer.Exit(code=1)

    rm = ReportManager(mgr)
    report = None
    if run_id:
        report = rm.load_report(run_id)
    else:
        report = rm.get_latest_report()
    if not report:
        console.print("[bold red]✗[/] 未找到报告，请先执行 smoke run")
        raise typer.Exit(code=1)

    failures, top_slow, critical_logs = _build_report_assets(report)

    pr = report.pass_rate
    rate_color = "green" if pr >= 90 else ("yellow" if pr >= 70 else "red")
    console.print(Panel.fit(
        f"[bold]📱 冒烟测试报告[/]\n"
        f"Run ID: [cyan]{report.run_id}[/]  版本: [green]{report.version}[/] build:{report.build}\n"
        f"设备: {report.device.platform.value} {report.device.device_name}  "
        f"时间: {_format_time(report.start_time)}",
        border_style="cyan",
    ))

    # 通过率卡片
    cards = Table(show_header=False, box=None, padding=(0, 3))
    cards.add_row(
        Text("总用例\n", style="dim") + Text(str(report.total_cases), style="bold", overflow="fold"),
        Text("通过\n", style="dim") + Text(str(report.passed_cases), style="bold green"),
        Text("失败\n", style="dim") + Text(str(report.failed_cases), style="bold red"),
        Text("错误\n", style="dim") + Text(str(report.error_cases), style="bold magenta"),
        Text("通过率\n", style="dim") + Text(f"{pr:.2f}%", style=f"bold {rate_color}"),
        Text("总耗时\n", style="dim") + Text(f"{report.total_duration_seconds:.2f}s", style="bold"),
    )
    console.print(cards)
    console.print()

    # 失败列表
    if failures:
        console.print(Panel.fit(
            "\n".join(
                f"  [red]●[/] [bold]{r.case.name}[/] [dim]({r.case.risk_level.value})[/]\n"
                f"     原因: {r.error_message}\n"
                f"     截图: [cyan]{r.failure_screenshot or '(无)'}[/]"
                for r in failures
            ),
            title=f"❌ 失败用例 ({len(failures)})", border_style="red",
        ))
    else:
        console.print(Panel.fit("[green]🎉 全部通过！[/]", title="✅ 失败用例", border_style="green"))

    # 耗时排行
    if not failures_only and top_slow:
        slow_table = Table(title=f"⏱️  耗时排行 Top {min(top, len(top_slow))}", header_style="bold")
        slow_table.add_column("排名", justify="right", style="dim")
        slow_table.add_column("用例")
        slow_table.add_column("耗时", justify="right")
        slow_table.add_column("占比", justify="right")
        max_dur = top_slow[0].duration_seconds or 1.0
        for i, r in enumerate(top_slow[:top], 1):
            bar_len = int(r.duration_seconds / max_dur * 30)
            bar = "█" * bar_len
            slow_table.add_row(str(i), r.case.name, f"{r.duration_seconds:.2f}s", f"[magenta]{bar}[/]")
        console.print(slow_table)

    # 明细表
    if not failures_only:
        detail = Table(title="📋 用例明细", show_lines=False, header_style="bold")
        detail.add_column("#", justify="right", style="dim")
        detail.add_column("用例")
        detail.add_column("风险", justify="center")
        detail.add_column("状态", justify="center")
        detail.add_column("耗时", justify="right")
        detail.add_column("步骤", justify="right")
        detail.add_column("重试", justify="right")
        for i, r in enumerate(report.results, 1):
            if failures_only and r.status == TestResultStatus.PASSED:
                continue
            risk_color = {"high": "red", "medium": "yellow", "low": "green"}.get(r.case.risk_level.value, "white")
            status_badge = {
                TestResultStatus.PASSED: "[green]✓ PASS[/]",
                TestResultStatus.FAILED: "[red]✗ FAIL[/]",
                TestResultStatus.ERROR: "[magenta]! ERR[/]",
                TestResultStatus.SKIPPED: "[yellow]- SKIP[/]",
            }.get(r.status, r.status.value)
            detail.add_row(
                str(i),
                r.case.name,
                f"[{risk_color}]{r.case.risk_level.value.upper()}[/]",
                status_badge,
                f"{r.duration_seconds:.2f}s",
                f"{len(r.step_results)}/{len(r.case.steps)}",
                str(r.retry_count),
            )
        console.print(detail)

    # 关键日志
    if show_logs and critical_logs:
        console.print(Panel.fit("🔎 关键日志", border_style="magenta"))
        for case_name, logs in critical_logs.items():
            console.print(f"  [bold]{case_name}[/] ({len(logs)} 条):")
            for line in logs[-10:]:
                if "ERROR" in line or "FAIL" in line:
                    console.print(f"    [red]{line}[/]")
                elif "WARN" in line:
                    console.print(f"    [yellow]{line}[/]")
                else:
                    console.print(f"    [dim]{line}[/]")


@app.command("export")
def export_report(
    run_id: Optional[str] = typer.Argument(None, help="报告 ID，留空为最新"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出 HTML 文件路径"),
    open_file: bool = typer.Option(False, "--open", help="导出后自动打开"),
    format: str = typer.Option("html", "--format", "-f", help="导出格式 html/json", show_choices=True),
) -> None:
    """导出 HTML 或 JSON 格式报告"""
    mgr = ConfigManager(path or Path.cwd())
    if not mgr.is_initialized:
        console.print("[bold red]✗[/] 项目未初始化")
        raise typer.Exit(code=1)
    rm = ReportManager(mgr)
    report = rm.load_report(run_id) if run_id else rm.get_latest_report()
    if not report:
        console.print("[bold red]✗[/] 未找到报告")
        raise typer.Exit(code=1)

    report_dir = mgr.get_report_dir()
    report_dir.mkdir(parents=True, exist_ok=True)

    if format.lower() == "json":
        out = output or (report_dir / f"{report.run_id}_full.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    else:
        out = output or (report_dir / f"{report.run_id}.html")
        failures, top_slow, critical_logs = _build_report_assets(report)
        tpl = Template(HTML_TEMPLATE)
        html = tpl.render(
            report=report,
            failures=failures,
            top_slow=top_slow,
            critical_logs=critical_logs,
            start_time_str=_format_time(report.start_time),
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)

    console.print(f"[bold green]✓[/] 报告已导出: [cyan]{out}[/]")
    if open_file:
        import webbrowser
        webbrowser.open(out.resolve().as_uri())


@app.command("list")
def list_reports(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径"),
    limit: int = typer.Option(20, "--limit", "-n", help="显示数量"),
) -> None:
    """列出历史测试报告"""
    mgr = ConfigManager(path or Path.cwd())
    if not mgr.is_initialized:
        console.print("[bold red]✗[/] 项目未初始化")
        raise typer.Exit(code=1)
    rm = ReportManager(mgr)
    reports = rm.list_reports()[:limit]
    if not reports:
        console.print("[yellow]暂无历史报告[/]")
        return
    table = Table(title="📚 历史报告", header_style="bold cyan")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Run ID")
    table.add_column("版本")
    table.add_column("总用例")
    table.add_column("通过")
    table.add_column("失败")
    table.add_column("通过率")
    table.add_column("耗时")
    table.add_column("创建时间")
    for i, p in enumerate(reports, 1):
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        pr = (d.get("passed_cases", 0) / max(1, d.get("total_cases", 0))) * 100
        rate_color = "green" if pr >= 90 else ("yellow" if pr >= 70 else "red")
        dur = d.get("total_duration_ms", 0) / 1000
        ts = datetime.fromtimestamp(p.stat().st_mtime).strftime("%m-%d %H:%M:%S")
        table.add_row(
            str(i), d.get("run_id", p.stem),
            f"{d.get('version','')}({d.get('build','')})",
            str(d.get("total_cases", 0)),
            f"[green]{d.get('passed_cases',0)}[/]",
            f"[red]{d.get('failed_cases',0)+d.get('error_cases',0)}[/]",
            f"[{rate_color}]{pr:.1f}%[/]",
            f"{dur:.1f}s", ts,
        )
    console.print(table)
