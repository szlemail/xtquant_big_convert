# 新项目接入速成（实测验证版）

> 依据 2026-09 gjqmt_test（国金模拟、ZMQ、无 Redis）端到端实测整理。
> 架构：服务端跑在大 QMT 内（每个 QMT 安装部署一次），客户端按项目接入。

## 一图看懂

```
┌─────────────────┐   ZMQ RPC 15579 (请求/响应)   ┌──────────────────────┐
│  你的项目(客户端) │ ◄──────────────────────────► │  大 QMT 终端(服务端)   │
│                 │   ZMQ PUB 15580 (行情/事件推送) │  策略: BIGQMT_REDIS_  │
└─────────────────┘ ◄─────────────────────────── │       DRYRUN          │
                                                   └──────────────────────┘
```

端口由资金账号派生：**RPC = 15560 + 账号数字 % 100，推送 = RPC + 1**。
例：62004819 → 15579/15580。换账号 = 换端口，多账号互不冲突。

## A. 服务端（每个 QMT 安装做一次）

1. 拷 5 样东西到 `<QMT安装目录>\python\`：
   `bigqmt_signal_trader\`（整包）、`bigqmt_signal_trader_strategy.py`、
   `bigqmt_signal_trader_redis_rpc_runtime.py`、`BIGQMT_REDIS_DRYRUN.py`、
   `bigqmt_signal_trader_local_config.py`（见下）
2. `bigqmt_signal_trader_local_config.py` 模板（ZMQ 版）：

   ```python
   BIGQMT_ACCOUNT_ID = "资金账号"
   BIGQMT_ACCOUNT_TYPE = "STOCK"          # 两融账户必须 CREDIT，否则资产全 0
   BIGQMT_REDIS_CONFIG = {
       "transport": "zmq",                # 无需安装任何东西，QMT 自带 pyzmq
       "rpc_allow_order_methods": False,  # 要远程下单时才改 True
       "rpc_process_in_listener": True,
       "rpc_listener_methods": ("*",),
       "rpc_background_threads": False,
       "schedule_adjust": True,
       "schedule_adjust_interval": "100nMilliSecond",
       "exec_events_enabled": True,
   }
   ```

3. **在 QMT 编辑器里新建策略**，粘贴 `BIGQMT_REDIS_DRYRUN.py` 的全部内容，
   保存（⚠️ 实测教训：直接把 .py 丢进 python 目录**不会**出现在策略树——
   树只认经编辑器保存过的加密策略）。
4. 策略属性：周期 1 分钟、标的任意（如 000300.SH）、
   **不勾「运行本地 Python」**（勾了会跑到外部 Python，找不到包和交易上下文）。
5. 运行后看到 `[bigqmt_signal_trader] init ok` + 端口监听即成功。

## B. 客户端（每个项目做一次）

### 方式一：从本地源码安装（当前必选项）

> ⚠️ **不要 `pip install xtquant-big-convert`**：PyPI 官方已发到 0.3.x，
> 那是上游另一条演进线——既不含本仓库的实盘修复（结算语义、raw 桥
> 毫秒归一化、推送自愈等），代码基线也和本地不一致。本地 main 基于
> 0.2.14 + 12 个修复提交；QMT 服务端部署的也是这份本地代码。

```bash
# 开发推荐（可编辑安装，仓库改代码即生效）：
pip install -e D:\developing\bigqmt_convert\xtquant_big_convert

# 或固定安装（拷贝当前快照）：
pip install D:\developing\bigqmt_convert\xtquant_big_convert
```

> 官方 pip 安装要等修复推送上游、合并发版之后才可用（届时同步评估
> 0.3.x 基线与本地的合并）。

在项目能 import 到的位置放 `bigqmt_signal_trader_client_config.py`：

```python
BIGQMT_ACCOUNT_ID = "62004819"           # 必须与服务端一致（信封校验+端口派生）
BIGQMT_RPC_TIMEOUT_SECONDS = 8.0
BIGQMT_REDIS_CONFIG = {"transport": "zmq", "zmq": {}}   # 空块=端口按账号派生
```

用法（MiniQMT 风格 API）：

```python
from bigqmt_signal_trader.xtquant_compat import configure
trader, xtdata = configure()

xtdata.get_market_data_ex(["close"], ["600000.SH"], period="1d", count=5)
xtdata.get_full_tick(["600000.SH"])
acc = trader.client.account_id
from bigqmt_signal_trader.xtquant_compat import StockAccount
trader.query_stock_positions(StockAccount(acc))
```

### 方式二：源码引用（本仓库开发中/不想装包）

```python
import sys
sys.path.insert(0, r"D:\developing\bigqmt_convert\xtquant_big_convert\src")
# 配置文件放到 sys.path 任一位置（仓库约定放 tools/deploy/，已 gitignore）
```

### 方式三：替换原生 xtquant（项目已写死 `from xtquant import xtdata` 时）

把本仓库 `src` 目录放到 `sys.path` **最前**——`src/xtquant` shim 会把调用
转发到桥。注意 import 顺序：先 import 真 SDK 再加 src 路径 = 不生效。

## 健康检查

```bash
python tools/zmq_client_e2e.py     # ping/行情/持仓/推送 全链路只读验证
```

预期量级：ping ~60ms、K线/快照 50–550ms、持仓资产 ~1.3s（deferred 路径）。

## 注意事项（都是实测踩过的）

| 事项 | 说明 |
|---|---|
| `get_market_data` 形状 | 桥透传大 QMT 形状（文档声明），与 MiniQMT 的 `{field: DataFrame}` 面板不同；**跨项目迁移请用 `get_market_data_ex`**（已归一化 `{code: df}`） |
| 下单默认关 | `rpc_allow_order_methods=False` 只放行查询；要下单改配置+重跑策略 |
| 两融账户 | `BIGQMT_ACCOUNT_TYPE="CREDIT"`，按 STOCK 查资产静默全 0 |
| 账号一致性 | 两端配置的账号必须相同（信封校验 + 端口派生都依赖它） |
| 回滚 | 服务端跑 `python <QMT>\python\uninstall_bigqmt.py`（部署清单同目录） |
| 换机器/多套 QMT | 重复 A 节即可；Redis 传输则需在机器上跑 Redis（Windows 用 Memurai/WSL），ZMQ 零依赖 |

## 给 transformer 项目的特别提示

- 数据面：用 `get_market_data_ex`（形状已对齐），别用 `get_market_data`
- `get_instrument_detail_list`（*ST 过滤用）桥已支持
- 5m 订阅路径：用 `subscribe_whole_quote`，不要用单股 `subscribe_quote`
  （后者只回调一次快照，属文档化限制）
- 下单：`order_stock` 结算语义已修复（活单不会返回 -1），但首日仍建议
  人工核对委托回报再放量
