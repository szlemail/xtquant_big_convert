# -*- coding: utf-8 -*-
"""生产环境探测脚本：验证「待环境确认」的几个修复前提。

用法：把本文件放进大 QMT 的策略目录（或粘贴进 QMT 内置 Python 执行），
在 QMT 内运行。每项探测独立 try/except，一项失败不影响其余。

输出逐行带 [PROBE-n] 前缀，收集后对照说明：
  PROBE-1 get_market_data_ex_ori 是否存在（raw 桥是否生效，决定批次 B 是否命中）
  PROBE-2 get_trading_dates 首元素类型（毫秒 int 还是 'YYYYMMDD'，决定节假日修复路径）
  PROBE-3 ContextInfo.get_market_data 返回形状（DataFrame/dict，决定迁移建议）
  PROBE-4 download_history_data2 全局第 5 参数签名（callback 还是 incrementally）
  PROBE-5 get_full_tick 对未知代码返回什么（空 dict 还是缺键——full_tick 修复验证）
"""

import inspect


def _section(title):
    print("=" * 60)
    print(title)
    print("=" * 60)


def probe(context_info=None):
    # ---- PROBE-1: raw 桥 ----
    try:
        ori = getattr(context_info, "get_market_data_ex_ori", None)
        print("[PROBE-1] get_market_data_ex_ori: %s"
              % ("EXISTS -> raw bridge ACTIVE (batch B fixes apply)" if callable(ori)
                 else "absent -> raw bridge inactive (batch B fixes dormant)"))
    except Exception as exc:
        print("[PROBE-1] probe failed: %s" % exc)

    # ---- PROBE-2: trading dates 格式 ----
    try:
        if context_info is not None:
            dates = context_info.get_trading_dates("SH", "", "", 3) or []
        else:
            from xtquant import xtdata
            dates = xtdata.get_trading_dates("SH", "", "", 3) or []
        if dates:
            first = dates[0]
            kind = type(first).__name__
            print("[PROBE-2] get_trading_dates[0] = %r (%s)" % (first, kind))
            if isinstance(first, (int, float)):
                print("       -> millisecond timestamps: holiday normalization fix ACTIVE")
            else:
                print("       -> date strings: holiday fix dormant (harmless)")
        else:
            print("[PROBE-2] get_trading_dates returned empty")
    except Exception as exc:
        print("[PROBE-2] probe failed: %s" % exc)

    # ---- PROBE-3: get_market_data 形状 ----
    try:
        data = context_info.get_market_data(
            ["close"], ["600000.SH"], period="1d", count=3
        )
        print("[PROBE-3] ContextInfo.get_market_data -> %s" % type(data).__name__)
        if hasattr(data, "columns"):
            print("       columns=%s index_dtype=%s" % (list(data.columns)[:6], data.index.dtype))
        elif isinstance(data, dict):
            keys = list(data.keys())[:3]
            print("       first keys: %s" % keys)
            v = data.get(keys[0]) if keys else None
            print("       value type: %s" % type(v).__name__)
    except Exception as exc:
        print("[PROBE-3] probe failed: %s" % exc)

    # ---- PROBE-4: download_history_data2 签名 ----
    try:
        import xtquant.xtdata as _xd
        fn = getattr(_xd, "download_history_data2", None)
        if fn is None:
            print("[PROBE-4] xtdata module has no download_history_data2")
        else:
            sig = None
            try:
                sig = str(inspect.signature(fn))
            except (TypeError, ValueError):
                pass
            print("[PROBE-4] download_history_data2 signature: %s" % (sig or "<builtin>"))
            print("       (keyword callback= is safe under either parameter order)")
    except Exception as exc:
        print("[PROBE-4] probe failed: %s" % exc)

    # ---- PROBE-5: get_full_tick 未知代码 ----
    try:
        ticks = context_info.get_full_tick(["999999.SH"]) or {}
        print("[PROBE-5] get_full_tick(unknown code) -> %r" % (ticks,))
    except Exception as exc:
        print("[PROBE-5] probe failed: %s" % exc)


if __name__ == "__main__":
    probe(None)
else:
    # 在 QMT 策略上下文里：init(C) 时调用 probe(C)
    pass
