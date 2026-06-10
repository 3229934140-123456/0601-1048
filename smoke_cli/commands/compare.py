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
from ..models import TestResultStatus, TestRunReport, VersionDiff


app = typer.Typer(name="compare", help="对比两次测试报告的差异：通过率、失败变化、耗时变化等")
console = Console()


COMPARE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<title>版本对比 - {{ diff.version_a }} vs {{ diff.version_b }}</title>
<style>
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Arial, sans-serif; background: #f5f7fa; color: #2c3e50; padding: 20px; }
.container { max-width: 1200px; margin: 0 auto; }
.header { background: linear-gradient(135deg, #11998e, #38ef7d); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }
.header h1 { font-size: 22px; margin-bottom: 10px; }
.vs { display: grid; grid-template-columns: 1fr auto 1fr; gap: 16px; align-items: center; margin: 20px 0; }
.vs .side { background: rgba(255,255,255,0.15); padding: 14px; border-radius: 8px; }
.vs .center { font-size: 28px; font-weight: 800; }
.section { background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.section h2 { font-size: 17px; margin-bottom: 14px; border-left: 4px solid #11998e; padding-left: 10px; color: #34495e; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 18px; }
.metric { background: #f8f9fa; border-radius: 8px; padding: 14px; }
.metric .label { font-size: 13px; color: #7f8c8d; }
.metric .v { font-size: 12px; color: #95a5a6; text-decoration: line-through; margin-top: 4px; }
.metric .val { font-size: 22px; font-weight: 700; margin-top: 4px; }
.metric .delta { font-size: 13px; margin-top: 4px; font-weight: 600; }
.up { color: #27ae60; }
.down { color: #e74c3c; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 9px 12px; border-bottom: 1px solid #ecf0f1; text-align: left; }
th { background: #f8f9fa; color: #7f8c8d; }
tr:hover { background: #f8f9fa; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 600; }
.tag.regression { background: #fadbd8; color: #c0392b; }
.tag.fixed { background: #d5f5e3; color: #1e8449; }
.tag.new { background: #d4e6f1; color: #2874a6; }
.tag.removed { background: #fcf3cf; color: #b7950b; }
.footer { text-align: center; color: #95a5a6; font-size: 13px; margin-top: 30px; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🔍 版本冒烟测试对比报告</h1>
    <div class="vs">
      <div class="side"><strong>版本 A (基准)</strong><br/>{{ diff.version_a }} · run_id={{ run_a_id }}</div>
      <div class="center">VS</div>
      <div class="side"><strong>版本 B (目标)</strong><br/>{{ diff.version_b }} · run_id={{ run_b_id }}</div>
    </div>
  </div>

  <div class="section">
    <h2>📊 关键指标变化</h2>
    <div class="metrics">
      <div class="metric">
        <div class="label">通过率</div>
        <div class="v">{{ '%.2f'|format(diff.pass_rate_a) }}% →</div>
        <div class="val">{{ '%.2f'|format(diff.pass_rate_b) }}%</div>
        <div class="delta {{ 'up' if diff.pass_rate_b >= diff.pass_rate_a else 'down' }}">
          {{ '+' if diff.pass_rate_b - diff.pass_rate_a >= 0 else '' }}{{ '%.2f'|format(diff.pass_rate_b - diff.pass_rate_a) }}pp
        </div>
      </div>
      <div class="metric">
        <div class="label">总耗时</div>
        <div class="val">{{ '%.2f'|format(duration_b_s) }}s</div>
        <div class="delta {{ 'down' if diff.duration_diff_ms <= 0 else 'up' }}">
          {{ '+' if diff.duration_diff_ms > 0 else '' }}{{ '%.2f'|format(diff.duration_diff_ms/1000) }}s
        </div>
      </div>
      <div class="metric">
        <div class="label">✅ 修复用例</div>
        <div class="val up">{{ diff.fixed_cases|length }}</div>
      </div>
      <div class="metric">
        <div class="label">❌ 回归用例</div>
        <div class="val down">{{ diff.regression_cases|length }}</div>
      </div>
      <div class="metric">
        <div class="label">➕ 新增用例</div>
        <div class="val" style="color:#2874a6">{{ diff.new_cases|length }}</div>
      </div>
      <div class="metric">
        <div class="label">➖ 移除用例</div>
        <div class="val" style="color:#b7950b">{{ diff.removed_cases|length }}</div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>📋 用例状态对比明细</h2>
    <table>
      <thead>
        <tr><th>用例</th><th>版本A</th><th>版本B</th><th>耗时A</th><th>耗时B</th><th>变化</th></tr>
      </thead>
      <tbody>
        {% for row in rows %}
          <tr>
            <td>{{ row.name }}{% if row.tag %} <span class="tag {{ row.tag }}">{{ row.tag_label }}</span>{% endif %}</td>
            <td>{{ row.a_status or '-' }}</td>
            <td>{{ row.b_status or '-' }}</td>
            <td>{{ row.a_dur }}</td>
            <td>{{ row.b_dur }}</td>
            <td class="{{ 'up' if row.delta_dur < 0 else 'down' if row.delta_dur > 0 else '' }}">{{ row.delta_str }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="footer">由 smoke-cli compare 自动生成 · {{ generated_at }}</div>
</div>
</body>
</html>
"""


def _build_diff(report_a: TestRunReport, report_b: TestRunReport) -> tuple[VersionDiff, list[dict]]:
    a_map = {r.case.name: r for r in report_a.results}
    b_map = {r.case.name: r for r in report_b.results}
    all_names = sorted(set(a_map.keys()) | set(b_map.keys()))

    regression: list[str] = []
    fixed: list[str] = []
    new: list[str] = []
    removed: list[str] = []
    rows: list[dict] = []

    def status_str(s):
        return {
            TestResultStatus.PASSED: "✅ PASS",
            TestResultStatus.FAILED: "❌ FAIL",
            TestResultStatus.ERROR: "⚠️ ERR",
            TestResultStatus.SKIPPED: "⏭️ SKIP",
        }.get(s, s.value if s else "-")

    for name in all_names:
        ar = a_map.get(name)
        br = b_map.get(name)
        a_status = status_str(ar.status) if ar else None
        b_status = status_str(br.status) if br else None
        a_dur = f"{ar.duration_seconds:.2f}s" if ar else "-"
        b_dur = f"{br.duration_seconds:.2f}s" if br else "-"
        delta_ms = (br.duration_ms if br else 0) - (ar.duration_ms if ar else 0)
        delta_str = f"{'+' if delta_ms > 0 else ''}{delta_ms/1000:.2f}s" if (ar and br) else "-"

        tag = ""
        tag_label = ""
        if ar and not br:
            removed.append(name)
            tag = "removed"
            tag_label = "已移除"
        elif br and not ar:
            new.append(name)
            tag = "new"
            tag_label = "新增"
        else:
            a_pass = ar.status == TestResultStatus.PASSED
            b_pass = br.status == TestResultStatus.PASSED
            if not a_pass and b_pass:
                fixed.append(name)
                tag = "fixed"
                tag_label = "已修复"
            elif a_pass and not b_pass:
                regression.append(name)
                tag = "regression"
                tag_label = "回归"

        rows.append({
            "name": name,
            "a_status": a_status,
            "b_status": b_status,
            "a_dur": a_dur,
            "b_dur": b_dur,
            "delta_dur": delta_ms,
            "delta_str": delta_str,
            "tag": tag,
            "tag_label": tag_label,
        })

    diff = VersionDiff(
        version_a=report_a.version,
        version_b=report_b.version,
        regression_cases=regression,
        fixed_cases=fixed,
        new_cases=new,
        removed_cases=removed,
        pass_rate_a=report_a.pass_rate,
        pass_rate_b=report_b.pass_rate,
        duration_diff_ms=report_b.total_duration_ms - report_a.total_duration_ms,
    )
    return diff, rows


@app.command("reports")
def compare_reports(
    report_a: str = typer.Argument(..., help="基准报告 ID 或路径（老版本）"),
    report_b: str = typer.Argument(..., help="目标报告 ID 或路径（新版本）"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径"),
    html: Optional[Path] = typer.Option(None, "--html", "-o", help="同时导出 HTML 对比报告到指定路径"),
    only_diff: bool = typer.Option(False, "--only-diff", "-d", help="仅展示有差异的用例"),
) -> None:
    """对比两次测试报告的版本差异"""
    mgr = ConfigManager(path or Path.cwd())
    rm = ReportManager(mgr)

    ra = rm.load_report(report_a)
    if not ra:
        console.print(f"[bold red]✗[/] 报告 A 未找到: {report_a}")
        raise typer.Exit(code=1)
    rb = rm.load_report(report_b)
    if not rb:
        console.print(f"[bold red]✗[/] 报告 B 未找到: {report_b}")
        raise typer.Exit(code=1)

    diff, rows = _build_diff(ra, rb)

    console.print(Panel.fit(
        f"[bold]🔍 版本差异对比[/]\n"
        f"[cyan]A[/] {diff.version_a} ({ra.run_id})  ↔  [green]B[/] {diff.version_b} ({rb.run_id})",
        border_style="cyan",
    ))

    # 汇总指标
    dpr = diff.pass_rate_b - diff.pass_rate_a
    pr_color = "green" if dpr >= 0 else "red"
    summary = Table(show_header=False, box=None, padding=(0, 3))
    summary.add_row(
        Text("通过率 A→B\n", style="dim") + Text(f"{diff.pass_rate_a:.2f}% → {diff.pass_rate_b:.2f}%", style="bold") + Text(f"  [{pr_color}]{'+' if dpr >= 0 else ''}{dpr:.2f}pp[/]", overflow="fold"),
        Text("总耗时变化\n", style="dim") + Text(f"{ra.total_duration_seconds:.2f}s → {rb.total_duration_seconds:.2f}s", style="bold") + Text(f"  [{'green' if diff.duration_diff_ms <= 0 else 'red'}]{'+' if diff.duration_diff_ms > 0 else ''}{diff.duration_diff_ms/1000:.2f}s[/]", overflow="fold"),
    )
    console.print(summary)

    counts = Table(title="📊 变化类型统计", header_style="bold")
    counts.add_column("类型", style="dim")
    counts.add_column("数量", justify="right")
    counts.add_column("用例", overflow="fold")
    counts.add_row("[green]✅ 修复通过[/]", f"[green]{len(diff.fixed_cases)}[/]", ", ".join(diff.fixed_cases) or "-")
    counts.add_row("[red]❌ 回归失败[/]", f"[red]{len(diff.regression_cases)}[/]", ", ".join(diff.regression_cases) or "-")
    counts.add_row("[blue]➕ 新增用例[/]", f"[blue]{len(diff.new_cases)}[/]", ", ".join(diff.new_cases) or "-")
    counts.add_row("[yellow]➖ 移除用例[/]", f"[yellow]{len(diff.removed_cases)}[/]", ", ".join(diff.removed_cases) or "-")
    console.print(counts)

    # 明细表
    display_rows = rows
    if only_diff:
        display_rows = [r for r in rows if r["tag"]]
    if display_rows:
        detail = Table(title=f"📋 用例对比 ({len(display_rows)}/{len(rows)})", header_style="bold")
        detail.add_column("用例")
        detail.add_column("A状态", justify="center")
        detail.add_column("B状态", justify="center")
        detail.add_column("A耗时", justify="right")
        detail.add_column("B耗时", justify="right")
        detail.add_column("Δ耗时", justify="right")
        for r in display_rows:
            badge = ""
            if r["tag"]:
                badge_color = {"regression": "red", "fixed": "green", "new": "blue", "removed": "yellow"}[r["tag"]]
                badge = f" [{badge_color}][{r['tag_label']}][/]"
            delta_color = "green" if r["delta_dur"] < 0 else ("red" if r["delta_dur"] > 0 else "white")
            detail.add_row(
                r["name"] + badge,
                r["a_status"] or "-",
                r["b_status"] or "-",
                r["a_dur"],
                r["b_dur"],
                f"[{delta_color}]{r['delta_str']}[/]" if r["delta_str"] != "-" else "-",
            )
        console.print(detail)

    # 导出 HTML
    if html:
        out = Path(html)
        out.parent.mkdir(parents=True, exist_ok=True)
        tpl = Template(COMPARE_HTML_TEMPLATE)
        text = tpl.render(
            diff=diff,
            run_a_id=ra.run_id,
            run_b_id=rb.run_id,
            duration_b_s=rb.total_duration_seconds,
            rows=rows,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        out.write_text(text, encoding="utf-8")
        console.print(f"\n[bold green]✓[/] HTML 对比报告已导出: [cyan]{out}[/]")

    if diff.regression_cases:
        console.print(Panel.fit(
            f"[bold red]⚠ 发现 {len(diff.regression_cases)} 个回归用例，请重点关注！[/]\n" +
            "\n".join(f"  • {c}" for c in diff.regression_cases),
            title="回归风险提示", border_style="red",
        ))


@app.command("latest")
def compare_with_previous(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径"),
    html: Optional[Path] = typer.Option(None, "--html", "-o", help="导出 HTML"),
) -> None:
    """快速对比最新两次报告"""
    mgr = ConfigManager(path or Path.cwd())
    rm = ReportManager(mgr)
    reports = rm.list_reports()
    if len(reports) < 2:
        console.print(f"[bold red]✗[/] 报告不足 2 份，当前 {len(reports)} 份")
        raise typer.Exit(code=1)
    b_file, a_file = reports[0], reports[1]
    with open(a_file, "r", encoding="utf-8") as f:
        ra_dict = json.load(f)
    with open(b_file, "r", encoding="utf-8") as f:
        rb_dict = json.load(f)
    ra = TestRunReport(**ra_dict)
    rb = TestRunReport(**rb_dict)

    console.print(f"[dim]基准报告: {a_file.name}[/]")
    console.print(f"[dim]目标报告: {b_file.name}[/]")
    compare_reports(ra.run_id, rb.run_id, path=path, html=html, only_diff=False)
