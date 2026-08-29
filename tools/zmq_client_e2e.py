# -*- coding: utf-8 -*-
"""ZMQ 部署端到端只读验证：ping / 行情 / 持仓查询（不下单）。

用法（在仓库根目录运行，自动读根目录的 bigqmt_signal_trader_client_config.py）：
    python tools/zmq_client_e2e.py
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "deploy"))  # 客户端私有配置
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from bigqmt_signal_trader.xtquant_compat import configure  # noqa: E402


def main():
    trader, xtdata = configure()

    def step(name, fn):
        t0 = time.time()
        try:
            result = fn()
            print("[OK]   %-38s %6.0fms  %s" % (name, (time.time() - t0) * 1000, _brief(result)))
            return result
        except Exception as exc:
            print("[FAIL] %-38s %6.0fms  %s: %s" % (name, (time.time() - t0) * 1000,
                                                    exc.__class__.__name__, exc))
            return None

    print("== ZMQ E2E (read-only) ==")
    step("ping", lambda: trader.client.call("ping"))

    # 行情类（内联方法）
    dates = step("get_trading_dates(SH, 3)", lambda: xtdata.get_trading_dates("SH", "", "", 3))
    step("get_market_data_ex 600000.SH 1d x5",
         lambda: xtdata.get_market_data_ex(["close"], ["600000.SH"], period="1d", count=5))
    step("get_full_tick 600000.SH", lambda: xtdata.get_full_tick(["600000.SH"]))
    step("get_instrument_detail_list",
         lambda: xtdata.get_instrument_detail_list(["600000.SH", "000001.SZ"]))
    step("get_stock_list_in_sector(沪深A股)",
         lambda: len(xtdata.get_stock_list_in_sector("沪深A股") or []))

    # 交易查询类（deferred：经 adjust 线程，含批次E修复的路径）
    acc = trader.client.account_id
    from bigqmt_signal_trader.xtquant_compat import StockAccount
    account = StockAccount(acc)
    step("query_stock_asset", lambda: trader.query_stock_asset(account))
    positions = step("query_stock_positions", lambda: trader.query_stock_positions(account))
    step("query_stock_orders", lambda: trader.query_stock_orders(account))
    print("== done ==")


def _brief(result):
    if result is None:
        return "None"
    if isinstance(result, dict):
        keys = list(result.keys())
        return "dict(%d keys: %s%s)" % (len(keys), ",".join(map(str, keys[:4])), "..." if len(keys) > 4 else "")
    if isinstance(result, (list, tuple)):
        return "%s(len=%d)" % (type(result).__name__, len(result))
    text = repr(result)
    return text if len(text) <= 80 else text[:77] + "..."


if __name__ == "__main__":
    main()
