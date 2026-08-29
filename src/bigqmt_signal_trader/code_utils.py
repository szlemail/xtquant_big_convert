"""证券代码标准化和委托数量处理。"""

import re


_DIGIT_CODE_RE = re.compile(r"^\d{6}$")


def normalize_stock_code(code):
    text = str(code or "").strip().upper()
    if not text:
        return ""
    # QMT ContextInfo uses market-specific suffixes for all instrument types.
    # If the code already has a recognized suffix, pass it through unchanged —
    # these are native ContextInfo codes that need no normalization.
    _QMT_SUFFIXES = (
        ".SH", ".SZ", ".BJ", ".HK",           # Stock markets
        ".HGT", ".SGT",                        # 港股通（沪/深）
        ".SHO", ".SZO",                        # Options markets (8-digit codes)
        ".SF", ".DF", ".IF", ".ZF", ".INE", ".GF",    # Futures markets
    )
    for suffix in _QMT_SUFFIXES:
        if text.endswith(suffix):
            prefix = text[:-len(suffix)]
            if prefix and (prefix.isdigit() or prefix[0].isalpha()):
                return text
    # Original logic for 6-digit stock codes
    if text.startswith("SH") and _DIGIT_CODE_RE.match(text[2:]):
        return f"{text[2:]}.SH"
    if text.startswith("SZ") and _DIGIT_CODE_RE.match(text[2:]):
        return f"{text[2:]}.SZ"
    if text.endswith(".SH") or text.endswith(".SZ"):
        prefix = text[:6]
        if _DIGIT_CODE_RE.match(prefix):
            return text
    if _DIGIT_CODE_RE.match(text):
        # 北交所：43/83/87/88（原新三板精选层转板段）与 92（920 新号段）。
        # 误判成 .SZ 会把委托报到错误市场、持仓也永远查不到（POSITION 行
        # 带的是 .BJ 后缀）。
        if text.startswith(("43", "83", "87", "88", "92")):
            return f"{text}.BJ"
        # 沪市可转债 110/111/113/118；12 开头的深市转债走下面的 SZ。
        if text.startswith("11"):
            return f"{text}.SH"
        market = "SH" if text.startswith(("5", "6")) else "SZ"
        return f"{text}.{market}"
    raise ValueError(f"invalid stock code: {code}")


def min_lot(stock_code):
    normalized = normalize_stock_code(stock_code)
    pure = normalized.split(".")[0]
    return 200 if pure.startswith("688") else 100


def round_buy_volume(stock_code, amount):
    lot = min_lot(stock_code)
    value = int(amount or 0)
    if value <= 0:
        return 0
    return (value // lot) * lot


def round_sell_volume(stock_code, amount, sell_all=False):
    value = int(amount or 0)
    if value <= 0:
        return 0
    if sell_all:
        return value
    lot = min_lot(stock_code)
    return (value // lot) * lot
