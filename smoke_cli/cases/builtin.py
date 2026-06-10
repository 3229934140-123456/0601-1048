from __future__ import annotations

from typing import Optional

from ..models import RiskLevel, StepAction, TestCaseConfig, TestStep


def _make_login_case() -> TestCaseConfig:
    return TestCaseConfig(
        name="登录成功_内置",
        description="使用正确的账号密码完成登录并进入首页",
        tags=["login", "core", "builtin"],
        risk_level=RiskLevel.HIGH,
        account="default",
        timeout=120,
        steps=[
            TestStep(action=StepAction.CLICK, target="id/profile_tab", description="点击我的 Tab"),
            TestStep(action=StepAction.INPUT, target="id/et_username", value="{{username}}", description="输入用户名", timeout=15),
            TestStep(action=StepAction.INPUT, target="id/et_password", value="{{password}}", description="输入密码"),
            TestStep(action=StepAction.SCREENSHOT, description="登录前截图"),
            TestStep(action=StepAction.CLICK, target="id/btn_login", description="点击登录按钮"),
            TestStep(action=StepAction.WAIT, value="3000", description="等待首页加载"),
            TestStep(action=StepAction.ASSERT, target="id/home_tab", value="exists", description="断言首页 Tab 存在"),
            TestStep(action=StepAction.SCREENSHOT, description="登录成功后截图"),
        ],
    )


def _make_login_fail_case() -> TestCaseConfig:
    return TestCaseConfig(
        name="密码错误_内置",
        description="验证错误密码无法登录并展示错误提示",
        tags=["login", "builtin"],
        risk_level=RiskLevel.MEDIUM,
        timeout=90,
        steps=[
            TestStep(action=StepAction.CLICK, target="id/profile_tab", description="点击我的 Tab"),
            TestStep(action=StepAction.INPUT, target="id/et_username", value="test_user", description="输入用户名"),
            TestStep(action=StepAction.INPUT, target="id/et_password", value="wrong_password", description="输入错误密码"),
            TestStep(action=StepAction.CLICK, target="id/btn_login", description="点击登录按钮"),
            TestStep(action=StepAction.WAIT, value="2000", description="等待响应"),
            TestStep(action=StepAction.ASSERT, target="id/tv_error", value="exists", description="断言错误提示出现"),
        ],
    )


def _make_order_case() -> TestCaseConfig:
    return TestCaseConfig(
        name="商品下单流程_内置",
        description="浏览商品->加入购物车->提交订单",
        tags=["order", "trade", "core", "builtin"],
        risk_level=RiskLevel.HIGH,
        timeout=180,
        steps=[
            TestStep(action=StepAction.CLICK, target="id/home_tab", description="进入首页"),
            TestStep(action=StepAction.SWIPE, target="up", description="向上滑动加载商品"),
            TestStep(action=StepAction.CLICK, target="id/product_card_0", description="点击第一个商品卡片"),
            TestStep(action=StepAction.WAIT, value="2000", description="等待商品详情"),
            TestStep(action=StepAction.ASSERT, target="id/tv_product_name", value="exists", description="断言商品名称存在"),
            TestStep(action=StepAction.SCREENSHOT, description="商品详情截图"),
            TestStep(action=StepAction.CLICK, target="id/btn_add_cart", description="加入购物车"),
            TestStep(action=StepAction.WAIT, value="1000", description="等待加入动画"),
            TestStep(action=StepAction.CLICK, target="id/cart_tab", description="切换到购物车"),
            TestStep(action=StepAction.CLICK, target="id/cb_select_all", description="全选购物车商品"),
            TestStep(action=StepAction.CLICK, target="id/btn_checkout", description="点击结算"),
            TestStep(action=StepAction.WAIT, value="2000", description="等待确认订单页"),
            TestStep(action=StepAction.ASSERT, target="id/btn_submit_order", value="exists", description="断言提交订单按钮存在"),
        ],
    )


def _make_payment_mock_case() -> TestCaseConfig:
    return TestCaseConfig(
        name="模拟支付_内置",
        description="在确认订单页使用模拟支付渠道完成支付",
        tags=["pay", "trade", "core", "builtin"],
        risk_level=RiskLevel.HIGH,
        account="default",
        timeout=180,
        steps=[
            TestStep(action=StepAction.CLICK, target="id/btn_submit_order", description="提交订单"),
            TestStep(action=StepAction.WAIT, value="3000", description="等待收银台"),
            TestStep(action=StepAction.ASSERT, target="id/pay_channel_list", value="exists", description="断言支付渠道列表"),
            TestStep(action=StepAction.SCREENSHOT, description="收银台截图"),
            TestStep(action=StepAction.CLICK, target="id/channel_mock_pay", description="选择模拟支付"),
            TestStep(action=StepAction.CLICK, target="id/btn_confirm_pay", description="确认支付"),
            TestStep(action=StepAction.WAIT, value="5000", description="等待支付回调"),
            TestStep(action=StepAction.ASSERT, target="id/pay_success_icon", value="exists", description="断言支付成功图标"),
            TestStep(action=StepAction.SCREENSHOT, description="支付成功截图"),
            TestStep(action=StepAction.CLICK, target="id/btn_view_order", description="查看订单详情"),
            TestStep(action=StepAction.ASSERT, target="id/order_status_paid", value="exists", description="断言订单已支付状态"),
        ],
    )


def _make_message_case() -> TestCaseConfig:
    return TestCaseConfig(
        name="消息中心_内置",
        description="验证消息中心列表和各分类 Tab 展示正常",
        tags=["message", "smoke", "builtin"],
        risk_level=RiskLevel.MEDIUM,
        timeout=120,
        steps=[
            TestStep(action=StepAction.CLICK, target="id/home_tab", description="进入首页"),
            TestStep(action=StepAction.CLICK, target="id/iv_msg_bell", description="点击消息铃铛"),
            TestStep(action=StepAction.WAIT, value="2000", description="等待消息列表"),
            TestStep(action=StepAction.ASSERT, target="id/msg_recycler", value="exists", description="断言消息列表存在"),
            TestStep(action=StepAction.SCREENSHOT, description="消息中心截图"),
            TestStep(action=StepAction.CLICK, target="id/tab_system", description="切换系统消息"),
            TestStep(action=StepAction.CLICK, target="id/tab_activity", description="切换活动消息"),
            TestStep(action=StepAction.CLICK, target="id/tab_order", description="切换订单消息"),
            TestStep(action=StepAction.SWIPE, target="up", description="上滑加载更多"),
            TestStep(action=StepAction.BACK, description="返回首页"),
        ],
    )


def _make_settings_case() -> TestCaseConfig:
    return TestCaseConfig(
        name="设置页检查_内置",
        description="检查设置页各入口、版本号、退出登录",
        tags=["setting", "smoke", "builtin"],
        risk_level=RiskLevel.MEDIUM,
        timeout=120,
        steps=[
            TestStep(action=StepAction.CLICK, target="id/profile_tab", description="进入我的页"),
            TestStep(action=StepAction.CLICK, target="id/iv_settings", description="进入设置"),
            TestStep(action=StepAction.WAIT, value="1500", description="等待设置页"),
            TestStep(action=StepAction.ASSERT, target="id/item_account", value="exists", description="断言账号与安全入口"),
            TestStep(action=StepAction.ASSERT, target="id/item_privacy", value="exists", description="断言隐私设置入口"),
            TestStep(action=StepAction.ASSERT, target="id/item_notification", value="exists", description="断言通知设置入口"),
            TestStep(action=StepAction.ASSERT, target="id/item_about", value="exists", description="断言关于我们入口"),
            TestStep(action=StepAction.ASSERT, target="id/tv_version", value="{{version}}", description="断言版本号正确"),
            TestStep(action=StepAction.SCREENSHOT, description="设置页截图"),
            TestStep(action=StepAction.CLICK, target="id/item_about", description="进入关于页"),
            TestStep(action=StepAction.BACK, description="返回设置"),
            TestStep(action=StepAction.CLICK, target="id/btn_logout", description="点击退出登录"),
            TestStep(action=StepAction.ASSERT, target="id/btn_confirm_logout", value="exists", description="断言二次确认弹窗"),
            TestStep(action=StepAction.CLICK, target="id/btn_confirm_logout", description="确认退出"),
            TestStep(action=StepAction.WAIT, value="1500", description="等待退出完成"),
        ],
    )


BUILTIN_CASES = {
    "login": _make_login_case(),
    "login_fail": _make_login_fail_case(),
    "order": _make_order_case(),
    "payment_mock": _make_payment_mock_case(),
    "message": _make_message_case(),
    "settings": _make_settings_case(),
}


def list_builtin_cases() -> list[TestCaseConfig]:
    return list(BUILTIN_CASES.values())


def get_builtin_case(key: str) -> Optional[TestCaseConfig]:
    return BUILTIN_CASES.get(key)
