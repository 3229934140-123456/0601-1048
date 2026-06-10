from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from ..config import ConfigManager
from ..models import DeviceConfig, DevicePlatform, RiskLevel, TestAccount, TestCaseConfig, TestStep, StepAction


app = typer.Typer(name="init", help="初始化冒烟测试项目，生成配置文件和示例用例")
console = Console()


def _prompt_device() -> DeviceConfig:
    console.print(Panel.fit("📱 配置测试设备", border_style="blue"))
    platform = Prompt.ask("请选择平台", choices=["android", "ios"], default="android")
    platform_version = Prompt.ask("系统版本", default="13.0" if platform == "android" else "16.0")
    device_name = Prompt.ask("设备名称", default="emulator-5554" if platform == "android" else "iPhone Simulator")
    app_package = Prompt.ask("App 包名", default="com.example.app")
    app_activity = Prompt.ask("启动 Activity (仅 Android)", default=".MainActivity") if platform == "android" else ""
    return DeviceConfig(
        platform=DevicePlatform(platform),
        platform_version=platform_version,
        device_name=device_name,
        app_package=app_package,
        app_activity=app_activity,
    )


def _prompt_accounts() -> list[TestAccount]:
    accounts: list[TestAccount] = []
    console.print(Panel.fit("👤 配置测试账号", border_style="green"))
    if not Confirm.ask("是否添加测试账号？", default=True):
        return accounts
    while True:
        role = Prompt.ask("账号角色", default="default")
        username = Prompt.ask(f"[{role}] 用户名")
        password = Prompt.ask(f"[{role}] 密码", password=True)
        accounts.append(TestAccount(username=username, password=password, role=role))
        if not Confirm.ask("继续添加账号？", default=False):
            break
    return accounts


def _default_cases() -> list[TestCaseConfig]:
    return [
        TestCaseConfig(
            name="登录成功",
            description="验证正确的账号密码可成功登录并进入首页",
            tags=["login", "core"],
            risk_level=RiskLevel.HIGH,
            account="default",
            steps=[
                TestStep(action=StepAction.INPUT, target="id/username", value="{{username}}", description="输入用户名", timeout=15),
                TestStep(action=StepAction.INPUT, target="id/password", value="{{password}}", description="输入密码"),
                TestStep(action=StepAction.CLICK, target="id/login_btn", description="点击登录按钮"),
                TestStep(action=StepAction.WAIT, value="3000", description="等待首页加载"),
                TestStep(action=StepAction.ASSERT, target="id/home_tab", value="exists", description="断言首页 Tab 存在"),
            ],
            timeout=120,
        ),
        TestCaseConfig(
            name="商品下单",
            description="进入商品详情页，添加到购物车并提交订单",
            tags=["order", "trade", "core"],
            risk_level=RiskLevel.HIGH,
            steps=[
                TestStep(action=StepAction.CLICK, target="id/home_tab", description="进入首页"),
                TestStep(action=StepAction.CLICK, target="id/product_card_1", description="点击第一个商品"),
                TestStep(action=StepAction.WAIT, value="2000", description="等待详情页"),
                TestStep(action=StepAction.CLICK, target="id/add_to_cart", description="加入购物车"),
                TestStep(action=StepAction.CLICK, target="id/cart_tab", description="进入购物车"),
                TestStep(action=StepAction.CLICK, target="id/select_all", description="全选商品"),
                TestStep(action=StepAction.CLICK, target="id/checkout_btn", description="提交结算"),
                TestStep(action=StepAction.ASSERT, target="id/confirm_order", value="exists", description="断言确认订单页"),
            ],
            timeout=180,
        ),
        TestCaseConfig(
            name="模拟支付",
            description="使用测试支付渠道完成支付流程",
            tags=["pay", "trade", "core"],
            risk_level=RiskLevel.HIGH,
            steps=[
                TestStep(action=StepAction.CLICK, target="id/confirm_order", description="确认订单"),
                TestStep(action=StepAction.WAIT, value="2000", description="等待收银台"),
                TestStep(action=StepAction.CLICK, target="id/pay_mock", description="选择模拟支付"),
                TestStep(action=StepAction.CLICK, target="id/pay_confirm", description="确认支付"),
                TestStep(action=StepAction.WAIT, value="5000", description="等待支付回调"),
                TestStep(action=StepAction.ASSERT, target="id/pay_success", value="exists", description="断言支付成功页"),
            ],
            timeout=180,
        ),
        TestCaseConfig(
            name="查看消息",
            description="验证消息中心可正常加载并显示消息列表",
            tags=["message", "smoke"],
            risk_level=RiskLevel.MEDIUM,
            steps=[
                TestStep(action=StepAction.CLICK, target="id/message_icon", description="点击消息图标"),
                TestStep(action=StepAction.WAIT, value="2000", description="等待消息列表"),
                TestStep(action=StepAction.ASSERT, target="id/message_list", value="exists", description="断言消息列表存在"),
                TestStep(action=StepAction.SWIPE, target="up", description="滑动查看更多消息"),
            ],
            timeout=120,
        ),
        TestCaseConfig(
            name="设置页检查",
            description="检查设置页各入口展示正常，版本号显示正确",
            tags=["setting", "smoke"],
            risk_level=RiskLevel.MEDIUM,
            steps=[
                TestStep(action=StepAction.CLICK, target="id/mine_tab", description="进入我的页"),
                TestStep(action=StepAction.CLICK, target="id/settings", description="点击设置"),
                TestStep(action=StepAction.ASSERT, target="id/account_setting", value="exists", description="断言账号设置入口"),
                TestStep(action=StepAction.ASSERT, target="id/privacy_setting", value="exists", description="断言隐私设置入口"),
                TestStep(action=StepAction.ASSERT, target="id/version_info", value="{{version}}", description="断言版本号正确"),
                TestStep(action=StepAction.CLICK, target="id/logout", description="退出登录"),
            ],
            timeout=120,
        ),
    ]


@app.command()
def new(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径，默认当前目录"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", "-i/-I", help="是否以交互方式配置"),
    with_examples: bool = typer.Option(True, "--examples/--no-examples", "-e/-E", help="是否生成示例用例"),
    force: bool = typer.Option(False, "--force", "-f", help="覆盖已存在的配置"),
) -> None:
    """创建新的冒烟测试项目"""
    project_root = Path(path or Path.cwd())
    project_root.mkdir(parents=True, exist_ok=True)
    mgr = ConfigManager(project_root)

    if mgr.is_initialized and not force:
        console.print(f"[bold red]✗[/] 项目已初始化: {mgr.config_file}")
        console.print("如需覆盖，请加 --force 选项")
        raise typer.Exit(code=1)

    console.print(Panel.fit("[bold]🚀 初始化冒烟测试项目[/]", border_style="magenta"))

    if interactive:
        project_name = Prompt.ask("项目名称", default="mobile_smoke_test")
        version = Prompt.ask("App 版本号", default="1.0.0")
        build = Prompt.ask("Build 号", default="0001")
        mgr.set("project_name", project_name)
        mgr.set("version", version)
        mgr.set("build", build)

        device = _prompt_device()
        mgr.add_device(device)

        accounts = _prompt_accounts()
        for acc in accounts:
            mgr.add_account(acc)
    else:
        mgr.add_device(DeviceConfig())

    if with_examples:
        for case in _default_cases():
            mgr.add_case(case)

    mgr.save()
    mgr.ensure_dirs("latest")

    console.print(f"\n[bold green]✓[/] 项目初始化成功!")
    console.print(f"  配置文件: [cyan]{mgr.config_file}[/]")
    console.print(f"  报告目录: [cyan]{mgr.get_report_dir()}[/]")
    if with_examples:
        console.print(f"  示例用例: [green]{len(_default_cases())}[/] 个已添加")
    console.print("\n[dim]提示: 可执行 [cyan]smoke list[/] 查看所有用例[/dim]")


@app.command("show")
def show_config(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="项目路径"),
) -> None:
    """显示当前项目配置"""
    mgr = ConfigManager(path or Path.cwd())
    if not mgr.is_initialized:
        console.print("[bold red]✗[/] 当前目录未初始化，请先执行 smoke init new")
        raise typer.Exit(code=1)

    cfg = mgr.config
    console.print(Panel.fit(f"[bold]⚙  项目配置: {cfg.get('project_name')}[/]", border_style="cyan"))
    console.print(f"  版本: [green]{cfg.get('version')}[/]  Build: [green]{cfg.get('build')}[/]")
    console.print(f"  报告目录: {cfg.get('report_dir')}")
    console.print(f"  默认重试次数: {cfg.get('default_retry')}")

    devices = mgr.get_devices()
    if devices:
        console.print(f"\n[bold]📱 设备配置 ({len(devices)})[/]:")
        for d in devices:
            console.print(f"  • [{d.platform.value}] {d.device_name} v{d.platform_version}  {d.app_package}")

    accounts = mgr.get_accounts()
    if accounts:
        console.print(f"\n[bold]👤 测试账号 ({len(accounts)})[/]:")
        for a in accounts:
            console.print(f"  • [{a.role}] {a.username}")

    cases = mgr.get_cases()
    console.print(f"\n[bold]📋 测试用例 ({len(cases)})[/]:")
    for c in cases:
        risk_color = {"high": "red", "medium": "yellow", "low": "green"}.get(c.risk_level.value, "white")
        tags = ",".join(c.tags) if c.tags else "-"
        console.print(f"  • [bold]{c.name}[/] [dim]({c.steps.__len__()}步)[/]  [{risk_color}]{c.risk_level.value}[/]  tags:[cyan]{tags}[/]")
