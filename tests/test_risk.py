"""[QA] Svindeldetektion: fanger wash-mønstre, frikender ærlig handel, deterministisk."""
import hashlib

import httpx
import pytest

from ovriq.core.engine import OvriqEngine, solve_pow

H = hashlib.sha256(b"x").hexdigest()


def _mk(e, name):
    return e.apply(e.cmd_register(name, solve_pow(name)))["node_id"]


def _trade(e, seller, buyer, rt="datapakke", price="5", qty=1):
    e.apply(e.cmd_order(seller, "ASK", rt, price, qty))
    res = e.apply(e.cmd_order(buyer, "BID", rt, price, qty))
    cid = res["contracts"][0]["contract_id"]
    e.apply(e.cmd_deliver(seller, cid, H))
    return cid


def test_reciprocal_wash_is_flagged():
    e = OvriqEngine()
    a, b = _mk(e, "washA"), _mk(e, "washB")
    # A→B og B→A gentagne gange = kunstig volumen
    for _ in range(3):
        _trade(e, a, b)
        _trade(e, b, a)
    flags = e.risk_report()
    wash = [f for f in flags if f["type"] == "reciprocal_wash"]
    assert wash and sorted(wash[0]["nodes"]) == sorted([a, b])
    assert e.metrics()["risk_flags"] >= 1


def test_honest_market_is_clean():
    e = OvriqEngine()
    s = _mk(e, "seller")
    buyers = [_mk(e, f"buyer{i}") for i in range(5)]
    for b in buyers:  # mange forskellige købere, ingen gensidighed
        _trade(e, s, b)
    assert e.risk_report() == []


def test_counterparty_concentration_flagged():
    e = OvriqEngine()
    s, pump, other = _mk(e, "seller"), _mk(e, "pumper"), _mk(e, "real")
    for _ in range(4):
        _trade(e, s, pump, price="20")   # næsten al volumen fra én køber
    _trade(e, s, other, price="1")       # en enkelt ægte handel
    conc = [f for f in e.risk_report() if f["type"] == "counterparty_concentration"]
    assert conc and s in conc[0]["nodes"]
    # men den ene ægte handel alene (uden koncentration) ville ikke flagge:
    e2 = OvriqEngine()
    s2 = _mk(e2, "s2")
    _trade(e2, s2, _mk(e2, "b2"))
    assert e2.risk_report() == []


def test_risk_report_deterministic_across_replay():
    e1 = OvriqEngine()
    events = []

    def do(ev):
        events.append(ev)
        return e1.apply(ev)

    a = do(e1.cmd_register("a", solve_pow("a")))["node_id"]
    b = do(e1.cmd_register("b", solve_pow("b")))["node_id"]
    for _ in range(2):
        do(e1.cmd_order(a, "ASK", "datapakke", "5", 1))
        r = do(e1.cmd_order(b, "BID", "datapakke", "5", 1))
        do(e1.cmd_deliver(a, r["contracts"][0]["contract_id"], H))
        do(e1.cmd_order(b, "ASK", "datapakke", "5", 1))
        r = do(e1.cmd_order(a, "BID", "datapakke", "5", 1))
        do(e1.cmd_deliver(b, r["contracts"][0]["contract_id"], H))
    e2 = OvriqEngine()
    for ev in events:
        e2.apply(ev)
    assert e2.risk_report() == e1.risk_report()


@pytest.fixture()
def api(tmp_path, monkeypatch):
    import importlib
    import ovriq.api.server as srv
    importlib.reload(srv)
    srv.boot(str(tmp_path / "j.jsonl"))
    return srv


@pytest.mark.asyncio
async def test_admin_endpoint_requires_token(api, monkeypatch):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app),
                                 base_url="http://t") as http:
        # uden token-env → 503
        monkeypatch.delenv("OVRIQ_ADMIN_TOKEN", raising=False)
        r = await http.get("/admin/risk")
        assert r.status_code == 503
        # med env men forkert header → 401
        monkeypatch.setenv("OVRIQ_ADMIN_TOKEN", "s3cret")
        r = await http.get("/admin/risk", headers={"X-Admin-Token": "wrong"})
        assert r.status_code == 401
        # korrekt token → 200
        r = await http.get("/admin/risk", headers={"X-Admin-Token": "s3cret"})
        assert r.status_code == 200 and "flags" in r.json()
