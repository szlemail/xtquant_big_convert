import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from bigqmt_signal_trader.full_tick_cache import (
    full_tick_demand_key,
    full_tick_request_id,
    read_full_tick_cache,
    refresh_full_tick_cache,
    request_full_tick_cache,
    write_full_tick_cache,
)


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.kv = {}
        self.deleted = []
        self.expired = []

    def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = value
        return 1

    def hgetall(self, key):
        return self.hashes.get(key, {})

    def hdel(self, key, field):
        self.deleted.append((key, field))
        self.hashes.setdefault(key, {}).pop(field, None)
        return 1

    def expire(self, key, seconds):
        self.expired.append((key, seconds))
        return True

    def setex(self, key, seconds, value):
        self.kv[key] = value
        self.expired.append((key, seconds))
        return True

    def get(self, key):
        return self.kv.get(key)


class FakeContext:
    def __init__(self):
        self.calls = []

    def get_full_tick(self, codes):
        self.calls.append(list(codes))
        return {codes[0]: {"lastPrice": 10.0, "bidPrice": [9.9], "askPrice": [10.1]}}


class FullTickCacheTest(unittest.TestCase):
    def test_request_then_refresh_writes_fresh_snapshot(self):
        redis_client = FakeRedis()
        context = FakeContext()

        demand = request_full_tick_cache(redis_client, "acct", ["600000"], demand_ttl_seconds=10)
        refreshed = refresh_full_tick_cache(redis_client, context, "acct", cache_ttl_seconds=10)
        ticks = read_full_tick_cache(redis_client, "acct", ["600000.SH"], max_age_seconds=10)

        self.assertEqual(demand["codes"], ["600000.SH"])
        self.assertEqual(refreshed, 1)
        self.assertEqual(context.calls, [["600000.SH"]])
        self.assertEqual(ticks["600000.SH"]["lastPrice"], 10.0)

    def test_expired_demand_is_removed_without_refreshing(self):
        redis_client = FakeRedis()
        context = FakeContext()
        key = full_tick_demand_key("acct")
        request_id = full_tick_request_id(["600000.SH"])
        redis_client.hset(
            key,
            request_id,
            '{"request_id":"%s","codes":["600000.SH"],"requested_at_ts":1,"expires_at_ts":1}' % request_id,
        )

        refreshed = refresh_full_tick_cache(redis_client, context, "acct", cache_ttl_seconds=10)

        self.assertEqual(refreshed, 0)
        self.assertEqual(context.calls, [])
        self.assertIn((key, request_id), redis_client.deleted)

    def test_refresh_kind_symbol_skips_market_demands(self):
        redis_client = FakeRedis()
        context = FakeContext()
        request_full_tick_cache(redis_client, "acct", ["600000"], demand_ttl_seconds=10)
        request_full_tick_cache(redis_client, "acct", ["SH", "SZ"], demand_ttl_seconds=10)

        refreshed = refresh_full_tick_cache(redis_client, context, "acct", cache_ttl_seconds=10, kind="symbol")

        self.assertEqual(refreshed, 1)
        self.assertEqual(context.calls, [["600000.SH"]])

    def test_refresh_kind_market_skips_symbol_demands(self):
        redis_client = FakeRedis()
        context = FakeContext()
        request_full_tick_cache(redis_client, "acct", ["600000"], demand_ttl_seconds=10)
        request_full_tick_cache(redis_client, "acct", ["SH", "SZ"], demand_ttl_seconds=10)

        refreshed = refresh_full_tick_cache(redis_client, context, "acct", cache_ttl_seconds=10, kind="market")

        self.assertEqual(refreshed, 1)
        self.assertEqual(context.calls, [["SH", "SZ"]])

    def test_empty_snapshot_is_not_written(self):
        # QMT returning {} for the codes must not become a "fresh" cache entry
        # that blocks the live-RPC fallback for a whole TTL window.
        r = FakeRedis()
        written = write_full_tick_cache(r, "acct", ["600000.SH"], {}, cache_ttl_seconds=10)
        self.assertIsNone(written)
        key = "bigqmt:fulltick:acct:%s" % full_tick_request_id(["600000.SH"])
        self.assertNotIn(key, r.kv)

    def test_empty_snapshot_read_is_a_miss(self):
        # Backward guard: an older server may still publish {} snapshots; the
        # reader must treat them as a miss so callers fall back / keep waiting.
        r = FakeRedis()
        import time as _time

        r.kv["bigqmt:fulltick:acct:%s" % full_tick_request_id(["600000.SH"])] = (
            __import__("bigqmt_signal_trader.full_tick_cache", fromlist=["_dump_snapshot"])
            ._dump_snapshot(
                {
                    "request_id": full_tick_request_id(["600000.SH"]),
                    "codes": ["600000.SH"],
                    "updated_at_ts": _time.time(),
                    "updated_at": "now",
                    "data": {},
                }
            )
        )
        self.assertIsNone(read_full_tick_cache(r, "acct", ["600000.SH"]))

    def test_non_empty_snapshot_read_still_hits(self):
        r = FakeRedis()
        write_full_tick_cache(r, "acct", ["600000.SH"], {"600000.SH": {"lastPrice": 1.0}})
        data = read_full_tick_cache(r, "acct", ["600000.SH"])
        self.assertEqual(data, {"600000.SH": {"lastPrice": 1.0}})


if __name__ == "__main__":
    unittest.main()
