# 📱 smoke-cli — 移动 App 冒烟测试命令行工具

移动 App 发版前自动化冒烟检查 CLI，面向测试人员，覆盖 **初始化 → 录制用例 → 批量执行 → 报告分析 → 版本对比** 全流程。

## ✨ 特性

| 能力 | 说明 |
|---|---|
| **init** | 交互式初始化项目、设备、测试账号，内置标准登录/下单/支付/消息/设置用例 |
| **record** | 交互式录制点击/输入/滑动/断言/截图/等待等步骤，支持编辑已有用例 |
| **run** | 批量执行用例，支持重试次数、标签过滤、高风险过滤、自定义报告目录、dry-run |
| **report** | 控制台查看通过率、失败用例+截图、耗时排行、关键日志；导出可视化 HTML/JSON |
| **compare** | 双报告对比，识别回归/修复/新增/移除用例，展示通过率和耗时变化 |

内置 6 个标准冒烟用例：登录成功、密码错误、商品下单、模拟支付、消息中心、设置页检查。

## 📦 安装

```bash
# 方式 1：使用 pip
pip install -r requirements.txt

# 方式 2：使用 poetry（可选）
poetry install
```

Python 版本要求：`>=3.9`

## 🚀 快速开始

```bash
# 1. 查看帮助
python run_smoke.py --help

# 2. 初始化项目（交互式）
python run_smoke.py init new

# 3. 查看当前配置与用例
python run_smoke.py init show

# 4. 列出所有用例
python run_smoke.py record list

# 5. 执行全部冒烟用例（3 次重试，只跑高风险）
python run_smoke.py run all --retry 3 --high-risk

# 6. 执行内置标准用例
python run_smoke.py run builtin login order payment_mock

# 7. 查看最新报告（含耗时排行 + 关键日志）
python run_smoke.py report show --logs

# 8. 导出 HTML 可视化报告
python run_smoke.py report export --html ./reports/latest.html --open

# 9. 对比最新两次报告的版本差异
python run_smoke.py compare latest --html ./reports/diff.html
```

## 📖 命令详解

### 1. init — 项目初始化

```bash
# 交互式创建（推荐）
smoke init new -i -e

# 非交互 + 指定目录 + 强制覆盖
smoke init new --path ./my_project --no-interactive --force

# 查看当前配置
smoke init show
```

### 2. record — 录制用例与账号

```bash
# 交互式录制新用例（高风险 + 标签）
smoke record case -n "支付超时" --risk high --tags "pay,timeout" -a default

# 编辑已有用例
smoke record case --edit "登录成功"

# 添加测试账号
smoke record account --role vip --user vip001 --pwd xxx --extra "phone=13800138000;level=3"

# 列出用例（按标签/风险/关键词过滤）
smoke record list --tags "core,trade" --risk high --search "支付"
```

### 3. run — 执行用例

```bash
# 批量执行：标签过滤 + 2 次重试 + 自定义报告目录
smoke run all --tags "login,trade" --retry 2 --report-dir ./build/reports

# 只跑高风险
smoke run all --high-risk

# 指定版本号覆盖
smoke run all -V 2.3.0 -b 2024061100

# 按名称执行若干用例
smoke run case "登录成功" "商品下单流程_内置"

# 仅运行内置标准用例集合
smoke run builtin login order payment_mock message settings
```

参数速览：

| 参数 | 短 | 说明 |
|---|---|---|
| `--retry N` | `-r` | 失败重试次数，默认配置 |
| `--high-risk` | `--high` | 只跑 HIGH 风险用例 |
| `--tags a,b` | `-t` | 按标签逗号分隔过滤 |
| `--report-dir` | `-o` | 报告输出目录 |
| `--dry-run` | | 模拟执行不连设备 |
| `--verbose` | `-v` | 详细日志 |
| `--version` | `-V` | 覆盖配置中的版本号 |
| `--build` | `-b` | 覆盖 build 号 |

### 4. report — 报告查看与导出

```bash
# 查看最新报告 + 失败详情 + 关键日志
smoke report show --logs

# 查看指定 run_id，只展示失败用例
smoke report show run_20240611_100000_abc123 -f

# 耗时排行 top 5
smoke report show --top 5

# 导出 HTML 并自动浏览器打开
smoke report export -o ./last.html --open

# 导出 JSON 全量数据
smoke report export --format json -o ./last.json

# 列出历史报告最近 10 条
smoke report list -n 10
```

### 5. compare — 版本差异对比

```bash
# 对比两个指定 run_id
smoke compare reports run_20240610_abc run_20240611_def -o ./diff.html

# 只看有差异的用例
smoke compare reports OLD NEW --only-diff

# 快速对比最新两条
smoke compare latest --html ./latest-diff.html
```

对比输出：
- 📊 通过率 / 总耗时 delta
- ✅ 已修复用例、❌ 回归用例
- ➕ 新增用例、➖ 移除用例
- ⏱️ 每个用例耗时变化明细

## 🧪 风险级别与标签

| 等级 | 说明 | 典型场景 |
|---|---|---|
| `high` | 阻断/资损风险，发版必过 | 登录、下单、支付 |
| `medium` | 核心路径但有旁路 | 消息、设置、收藏 |
| `low` | 体验类，非阻断 | 换肤、引导、分享 |

标签可自定义，建议：`core` / `smoke` / `login` / `trade` / `pay` / `message` / `setting` / `regression`。

## 📁 项目结构

```
smoke_cli/
├── main.py                 # CLI 入口
├── models.py               # 数据模型 (Pydantic)
├── config.py               # 配置 & 报告管理器
├── engine.py               # 执行引擎：调度/重试/模拟/采集
├── cases/
│   └── builtin.py          # 6 个内置标准冒烟用例
└── commands/
    ├── init.py             # init 命令组
    ├── record.py           # record 命令组
    ├── run.py              # run 命令组
    ├── report.py           # report 命令组
    └── compare.py          # compare 命令组
```

## 🔁 典型发版前检查流程

```bash
# 1. 初始化/更新配置
smoke init show
smoke record list --risk high

# 2. 高风险 + 核心标签，失败重试 2 次
smoke run all --high-risk --tags "core" --retry 2 \
    -V 2.3.0 -b 2024061100 \
    -o ./release_reports/2.3.0

# 3. 查看报告与失败详情
smoke report show --logs

# 4. 和上一版本 2.2.0 对比
smoke compare reports RUN_2.2.0 RUN_2.3.0 -o ./diff_2.2.0_vs_2.3.0.html

# 5. 导出正式报告归档
smoke report export -o ./release_reports/2.3.0/smoke-report.html --open
```

通过率 ≥ 90% 且无回归 → 可进入发版流程。

## 🛠️ 自定义扩展

- **接入 Appium/UIAutomator**：替换 `engine.py` 中 `_simulate_step` 方法，通过 WebDriver 执行真实操作。
- **新增内置用例**：在 `cases/builtin.py` 中添加工厂函数并注册到 `BUILTIN_CASES`。
- **企业 IM 通知**：在 `run.py` 的执行完成后接飞书/钉钉 WebHook，推送通过率与失败截图。

## 📝 License

MIT
