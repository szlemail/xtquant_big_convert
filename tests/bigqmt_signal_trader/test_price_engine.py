import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from bigqmt_signal_trader.price_engine import build_order_price


class FakeMarketDataProvider:
    def get_ticks(self, codes):
        return {
            "000001.SZ": {
                "lastPrice": 10.0,
                "askPrice": [10.01, 10.02],
                "bidPrice": [9.99, 9.98],
            }
        }

    def get_instrument(self, code):
        return {
            "InstrumentStatus": 0,
            "UpStopPrice": 11.0,
            "DownStopPrice": 9.0,
        }


class PriceEngineTest(unittest.TestCase):
    def test_auto_buy_price_uses_ask2_when_better_than_markup(self):
        price = build_order_price(FakeMarketDataProvider(), "000001.SZ", "BUY")
        self.assertEqual(price, 10.02)

    def test_auto_sell_price_uses_bid2_when_better_than_discount(self):
        price = build_order_price(FakeMarketDataProvider(), "000001.SZ", "SELL")
        self.assertEqual(price, 9.98)


class PricePrecisionTest(unittest.TestCase):
    def test_three_decimal_instruments(self):
        from bigqmt_signal_trader.price_engine import _price_precision

        # ETF: 15/16 (深), 51/52/56/58 (沪)；可转债: 11 (沪) / 12 (深)。
        for code in ("159915.SZ", "162411.SZ", "510300.SH", "588000.SH",
                     "560010.SH", "582000.SH", "113050.SH", "123088.SZ"):
            self.assertEqual(_price_precision(code), 3, code)

    def test_two_decimal_stocks(self):
        from bigqmt_signal_trader.price_engine import _price_precision

        for code in ("600000.SH", "000001.SZ", "300750.SZ", "688981.SH"):
            self.assertEqual(_price_precision(code), 2, code)


if __name__ == "__main__":
    unittest.main()
