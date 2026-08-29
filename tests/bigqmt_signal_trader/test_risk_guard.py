import datetime as _dt
import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from bigqmt_signal_trader.models import PositionSnapshot, SignalAction, TradeSignal
from bigqmt_signal_trader.risk_guard import build_trade_volume, validate_signal


def _sell_signal(**kwargs):
    payload = {
        "signal_id": "sig-test",
        "account_id": "acct",
        "created_at": "2026-08-29 09:00:00",
        "expire_at": "2099-01-01 00:00:00",
        "schema_version": 1,
        "action": "SELL",
        "stock_code": "000001.SZ",
        "strategy_name": "test",
    }
    payload.update(kwargs)
    return TradeSignal.from_dict(payload)


def _positions(available=1000):
    return {
        "000001.SZ": PositionSnapshot(
            stock_code="000001.SZ", volume=1000, available=available, cost=9.5
        )
    }


class RiskGuardPercentageTest(unittest.TestCase):
    def test_percentage_none_sells_everything(self):
        # from_dict rejects amount=None + percentage=None for SELL, so this
        # branch is only reachable via direct construction (or CLEAR).
        signal = TradeSignal(
            signal_id="sig-direct",
            account_id="acct",
            action=SignalAction.SELL,
            stock_code="000001.SZ",
            created_at=_dt.datetime(2026, 8, 29, 9, 0, 0),
            expire_at=_dt.datetime(2099, 1, 1),
            schema_version=1,
        )
        decision = build_trade_volume(signal, _positions())
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.volume, 1000)

    def test_percentage_zero_is_rejected_not_full_sell(self):
        # ``0 or 100`` used to turn an explicit no-op into a full-position sell.
        decision = build_trade_volume(_sell_signal(percentage=0), _positions())
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "invalid_percentage")

    def test_negative_percentage_is_rejected(self):
        decision = build_trade_volume(_sell_signal(percentage=-10), _positions())
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "invalid_percentage")

    def test_percentage_above_100_clamps_to_available(self):
        decision = build_trade_volume(_sell_signal(percentage=150), _positions())
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.volume, 1000)

    def test_partial_percentage_sells_that_share(self):
        decision = build_trade_volume(_sell_signal(percentage=20), _positions())
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.volume, 200)

    def test_validate_signal_passes_invalid_percentage_through(self):
        signal = _sell_signal(percentage=0)
        decision = validate_signal(signal, _dt.datetime(2026, 8, 29, 10, 0, 0), _positions())
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "invalid_percentage")


if __name__ == "__main__":
    unittest.main()
