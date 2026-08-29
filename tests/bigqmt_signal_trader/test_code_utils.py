import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from bigqmt_signal_trader.code_utils import (
    normalize_stock_code,
    round_buy_volume,
    round_sell_volume,
)


class CodeUtilsTest(unittest.TestCase):
    def test_normalize_stock_code_accepts_common_formats(self):
        self.assertEqual(normalize_stock_code("600000"), "600000.SH")
        self.assertEqual(normalize_stock_code("000001"), "000001.SZ")
        self.assertEqual(normalize_stock_code("SZ000001"), "000001.SZ")
        self.assertEqual(normalize_stock_code("sh600000"), "600000.SH")
        self.assertEqual(normalize_stock_code("600000.SH"), "600000.SH")

    def test_normalize_stock_code_keeps_etf_tradable(self):
        self.assertEqual(normalize_stock_code("510300"), "510300.SH")
        self.assertEqual(normalize_stock_code("159915"), "159915.SZ")

    def test_round_buy_volume_by_lot(self):
        self.assertEqual(round_buy_volume("000001.SZ", 1234), 1200)
        self.assertEqual(round_buy_volume("688001.SH", 234), 200)

    def test_round_sell_volume_keeps_all_when_sell_all(self):
        self.assertEqual(round_sell_volume("000001.SZ", 1234, sell_all=False), 1200)
        self.assertEqual(round_sell_volume("000001.SZ", 1234, sell_all=True), 1234)


if __name__ == "__main__":
    unittest.main()


class BareCodeMarketInferenceTest(unittest.TestCase):
    def test_bj_codes_get_bj_suffix(self):
        from bigqmt_signal_trader.code_utils import normalize_stock_code

        for code in ("430047", "830799", "871981", "889000", "920001"):
            self.assertEqual(normalize_stock_code(code), f"{code}.BJ", code)

    def test_sh_convertible_bonds_get_sh_suffix(self):
        from bigqmt_signal_trader.code_utils import normalize_stock_code

        for code in ("110059", "111000", "113050", "118000"):
            self.assertEqual(normalize_stock_code(code), f"{code}.SH", code)

    def test_sz_convertible_bonds_stay_sz(self):
        from bigqmt_signal_trader.code_utils import normalize_stock_code

        for code in ("123088", "127000", "128100"):
            self.assertEqual(normalize_stock_code(code), f"{code}.SZ", code)

    def test_ambiguous_prefixes_unchanged(self):
        from bigqmt_signal_trader.code_utils import normalize_stock_code

        # 显式后缀永远优先，不受前缀推断影响
        self.assertEqual(normalize_stock_code("430047.BJ"), "430047.BJ")
        self.assertEqual(normalize_stock_code("600000.SH"), "600000.SH")
