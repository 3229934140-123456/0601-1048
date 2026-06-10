from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt

from ..config import ConfigManager
from ..models import RiskLevel, StepAction, TestAccount, TestCaseConfig, TestStep


app = typer.Typer(name="record", help="录制测试步骤、添加用例和测试账号")
console = Console()


ACTION_HELP = {
    StepAction.CLICK.value: "点击元素 (target=元素定位, value=可选)",
    StepAction.INPUT.value: "输入文本 (target=元素定位, value=文本内容)",
    StepAction.SWIPE.value: "滑动屏幕 (target=方向: up/down/left/right)",
    StepAction.ASSERT.value: "断言验证 (target=元素定位, value=预期值/属性)",
    StepAction.WAIT.value: "等待 (value=毫秒数)",
    StepAction.SCREENSHOT.value: "截图保存",
    StepAction.BACK.value: "返回上一页",
}


def _ask_step() -> Optional[TestStep]:
    action = Prompt.ask(
        "选择操作类型",
        choices=list(ACTION_HELP.keys()),
        default="click",
    )
    console.print(f"[dim]说明: {ACTION_HELP[action]}[/]")
    target = None
    value = None
    description = Prompt.ask("步骤描述（可选）", default="").strip() or None

    if action in ("click", "input", "assert"):
        target = Prompt.ask("元素定位 (如 id/username, xpath/...)", default="").strip() or None
    elif action == "swipe":
        target = Prompt.ask("滑动方向", choices=["up", "down", "left", "right"], default="up")

    if action in ("input", "wait", "assert"):
        default_value = "3000" if action == "wait" else ""
        value = Prompt.ask("值 (输入内容/等待毫秒/断言预期)", default=default_value).strip() or None

    timeout = IntPrompt.ask("步骤超时秒数", default=10)

    return TestStep(
        action=StepAction(action),
        target=target,
        value=value,
        description=description,
        timeout=timeout,
    )


@app.command("case")
def record_case(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="用例名称"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径"),
    risk: str = typer.Option("medium", "--risk", "-r", help="风险等级 high/medium/low", show_choices=True),
    tags: str = typer.Option("", "--tags", "-t", help="标签，逗号分隔"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="绑定的测试账号角色"),
    edit: Optional[str] = typer.Option(None, "--edit", "-e", help="编辑已存在的用例名称"),
) -> None:
    """交互式录制测试用例步骤"""
    mgr = ConfigManager(path or Path.cwd())
    if not mgr.is_initialized:
        console.print("[bold red]✗[/] 项目未初始化，请先执行 smoke init new")
        raise typer.Exit(code=1)

    # 编辑模式
    if edit:
        existing = mgr.get_case_by_name(edit)
        if not existing:
            console.print(f"[bold red]✗[/] 未找到用例: {edit}")
            raise typer.Exit(code=1)
        case = existing.model_copy(deep=True)
        console.print(f"[yellow]编辑用例:[/] {case.name} 当前 {len(case.steps)} 步")
        if Confirm.ask("是否清空现有步骤重新录制？", default=False):
            case.steps = []
    else:
        name = name or Prompt.ask("请输入用例名称")
        description = Prompt.ask("用例描述（可选）", default="")
        risk_level = RiskLevel(risk)
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        timeout = IntPrompt.ask("用例总超时秒数", default=120)
        case = TestCaseConfig(
            name=name,
            description=description,
            tags=tag_list,
            risk_level=risk_level,
            account=account,
            timeout=timeout,
        )

    console.print(Panel.fit(f"[bold]🎬 录制步骤: {case.name}[/]\n[dim]每录完一步询问是否继续[/]", border_style="cyan"))
    if case.steps:
        console.print(f"[dim]当前已有 {len(case.steps)} 步，将追加录制[/]")

    while True:
        step = _ask_step()
        if step:
            case.steps.append(step)
            idx = len(case.steps)
            desc = step.description or step.action.value
            console.print(f"[green]  ✓ 步骤{idx}[/] {step.action.value} | {step.target or '-'} | {step.value or '-'} [dim]{desc}[/]")
        if not Confirm.ask(f"\n继续添加步骤？当前共 {len(case.steps)} 步", default=True):
            break

    if not case.steps:
        console.print("[yellow]⚠[/] 用例没有任何步骤，将跳过保存")
        raise typer.Exit(code=0)

    # 展示完整用例
    console.print(Panel.fit(f"[bold]📋 用例预览: {case.name}[/] ({len(case.steps)} steps)", border_style="green"))
    for i, s in enumerate(case.steps, 1):
        desc = s.description or ""
        console.print(f"  {i:2d}. [bold]{s.action.value:<10}[/] target={s.target or '-':<20} value={s.value or '-':<15} [dim]{desc}[/]")

    if not Confirm.ask("确认保存？", default=True):
        console.print("[yellow]已取消保存[/]")
        raise typer.Exit(code=0)

    if edit:
        ok = mgr.update_case(edit, case)
    else:
        mgr.add_case(case)
        ok = True
    mgr.save()

    if ok:
        console.print(f"[bold green]✓[/] 用例已保存: [cyan]{case.name}[/] ({len(case.steps)} 步)")
    else:
        console.print("[bold red]✗[/] 保存失败")


@app.command("account")
def add_account(
    role: Optional[str] = typer.Option(None, "--role", "-r", help="账号角色，如 default/vip/admin"),
    username: Optional[str] = typer.Option(None, "--user", "-u", help="用户名"),
    password: Optional[str] = typer.Option(None, "--pwd", "-w", help="密码"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径"),
    extra: Optional[str] = typer.Option(None, "--extra", "-x", help="附加字段，格式 k1=v1;k2=v2"),
) -> None:
    """添加测试账号配置"""
    mgr = ConfigManager(path or Path.cwd())
    if not mgr.is_initialized:
        console.print("[bold red]✗[/] 项目未初始化，请先执行 smoke init new")
        raise typer.Exit(code=1)

    role = role or Prompt.ask("账号角色", default="default")
    username = username or Prompt.ask("用户名")
    password = password or Prompt.ask("密码", password=True)

    extra_dict: dict[str, str] = {}
    if extra:
        for pair in extra.split(";"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                extra_dict[k.strip()] = v.strip()
    if Confirm.ask("是否添加附加字段？", default=False):
        while True:
            k = Prompt.ask("字段名 (留空结束)", default="").strip()
            if not k:
                break
            v = Prompt.ask(f"[{k}] 的值")
            extra_dict[k] = v

    account = TestAccount(role=role, username=username, password=password, extra=extra_dict)
    mgr.add_account(account)
    mgr.save()

    console.print(f"[bold green]✓[/] 已添加测试账号: [{account.role}] {account.username}")
    if extra_dict:
        console.print(f"  附加字段: {extra_dict}")


@app.command("list")
def list_cases(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径"),
    tags: str = typer.Option("", "--tags", "-t", help="按标签过滤，逗号分隔"),
    risk: Optional[str] = typer.Option(None, "--risk", "-r", help="按风险等级过滤"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="关键词搜索用例名"),
) -> None:
    """列出所有测试用例，支持过滤"""
    mgr = ConfigManager(path or Path.cwd())
    if not mgr.is_initialized:
        console.print("[bold red]✗[/] 项目未初始化，请先执行 smoke init new")
        raise typer.Exit(code=1)

    cases = mgr.get_cases()
    tag_filter = {t.strip() for t in tags.split(",") if t.strip()}
    risk_filter = RiskLevel(risk) if risk else None

    filtered = []
    for c in cases:
        if tag_filter and not (set(c.tags) & tag_filter):
            continue
        if risk_filter and c.risk_level != risk_filter:
            continue
        if search and search.lower() not in c.name.lower():
            continue
        filtered.append(c)

    console.print(Panel.fit(f"[bold]📋 测试用例列表[/] ({len(filtered)}/{len(cases)})", border_style="blue"))
    if not filtered:
        console.print("[yellow]未找到匹配的用例[/]")
        return

    for c in filtered:
        risk_color = {RiskLevel.HIGH: "red", RiskLevel.MEDIUM: "yellow", RiskLevel.LOW: "green"}[c.risk_level]
        tag_str = ",".join(c.tags) if c.tags else "-"
        acc = f"[{c.account}]" if c.account else "-"
        status_icon = "✓" if c.enabled else "✗"
        console.print(
            f"  [{status_icon}] [bold]{c.name}[/] "
            f"[dim]{c.steps.__len__()}步[/] "
            f"[{risk_color}]{c.risk_level.value:<6}[/] "
            f"[cyan]tags:[/]{tag_str:<18} "
            f"[yellow]acc:[/]{acc}"
        )
        if c.description:
            console.print(f"       [dim]{c.description}[/]")
