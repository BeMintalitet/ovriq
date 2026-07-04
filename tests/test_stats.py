"""[QA] Markedsstatistik + leaderboard: korrekthed, sortering, endpoints."""
import hashlib
import httpx
import pytest

from ovriq.core.engine import OvriqEngine, solve_pow

H = hashlib.sha256(b"x").hexdigest()


def _mk(e, n): return e.apply(e.cmd_register(n, solve_pow(n)))["node_id"]


def _settle(e, seller, buyer, rt="datapakke", price="5", qty=2, rating=None):
    e.apply(e.cmd_order(seller, "ASK", rt, price, qty))
    res = e.apply(e.cmd_order(buyer, "BID", rt, price, qty))
    cid = res["contracts"][0]["contract_id"]
    e.apply(e.cmd_deliver(seller, cid, H))
    if rating:
        e.apply(e.cmd_review(buyer, cid, rating))
    return cid


def test_market_stats_aggregates_per_resource():
    e = OvriqEngine()
    s, b = _mk(e, "s"), _mk(e, "b")
    _settle(e, s, b, "datapakke", "5", 2)     # volumen 10
    _settle(e, s, b, "compute_tid", "10", 1)  # volumen 10
    st = e.market_stats()
    assert st["total_trades"] == 2
    assert st["total_volume_oq"] == "20.0000"
    dp = next(m for m in st["markets"] if m["resource_type"] == "datapakke")
    assert dp["last_price"] == "5.0000" and dp["volume_oq"] == "10.0000"
    prem = next(m for m in st["markets"] if m["resource_type"] == "premium_prompt")
    assert prem["trades"] == 0 and prem["last_price"] is None


def test_low_ask_reflects_open_orders():
    e = OvriqEngine()
    s = _mk(e, "s")
    e.apply(e.cmd_order(s, "ASK", "datapakke", "9", 1))
    e.apply(e.cmd_order(s, "ASK", "datapakke", "4", 1))
    dp = next(m for m in e.market_stats()["markets"] if m["resource_type"] == "datapakke")
    assert dp["low_ask"] == "4.0000" and dp["open_asks"] == 2


def test_leaderboard_sorted_by_score():
    e = OvriqEngine()
    good, ok, buyer = _mk(e, "good"), _mk(e, "ok"), _mk(e, "buyer")
    for _ in range(3):
        _settle(e, good, buyer, rating=5)
    _settle(e, ok, buyer, rating=3)
    lb = e.leaderboard()
    assert lb[0]["name"] == "good" and lb[0]["score"] >= lb[1]["score"]
    names = [r["name"] for r in lb]
    assert "buyer" not in names  # køber uden salg er ikke på listen


@pytest.mark.asyncio
async def test_stats_endpoints(tmp_path):
    import importlib
    import ovriq.api.server as srv
    importlib.reload(srv)
    srv.boot(str(tmp_path / "j.jsonl"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=srv.app),
                                 base_url="http://t") as http:
        for path in ("/market/stats", "/leaderboard", "/dashboard"):
            r = await http.get(path)
            assert r.status_code == 200, path
        assert "markets" in (await http.get("/market/stats")).json()
        assert "OVRIQ" in (await http.get("/dashboard")).text
