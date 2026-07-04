"""[QA] Discovery-manifest + liquidity-maker."""
import httpx
import pytest


@pytest.fixture()
def app(tmp_path):
    import importlib
    import ovriq.api.server as srv
    importlib.reload(srv)
    srv.boot(str(tmp_path / "j.jsonl"))
    return srv.app


@pytest.mark.asyncio
async def test_manifest_is_complete_and_valid(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://t") as http:
        for path in ("/.well-known/agent.json", "/manifest"):
            r = await http.get(path)
            assert r.status_code == 200
            m = r.json()
            assert m["name"] == "OVRIQ"
            assert m["base_url"] == "https://api.ovriq.xyz"
            assert "datapakke" in m["resource_types"]
            assert "register" in m["endpoints"] and "post_task" in m["endpoints"]
            assert m["currency"]["code"] == "OQ"
            assert "escrow" in m["capabilities"]


@pytest.mark.asyncio
async def test_maker_keeps_liquidity_and_delivers(app, tmp_path, monkeypatch):
    """Makeren holder staaende udbud, opretter opgaver og leverer paa aegte fills —
    men koeber ALDRIG (ingen wash)."""
    import ovriq.nodes.maker as mk
    monkeypatch.setattr(mk, "CREDS_PATH", tmp_path / "maker.json")

    transport = httpx.ASGITransport(app=app)
    maker = mk.LiquidityMaker()
    maker._http = httpx.AsyncClient(transport=transport, base_url="http://t")
    await maker._ensure_identity()
    assert maker.node_id

    # ét maker-tick: udbud + opgaver
    await maker._top_up_asks()
    await maker._keep_tasks()
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as http:
        listings = (await http.get("/market/listings")).json()["listings"]
        assert len([o for o in listings if o["node_id"] == maker.node_id]) >= 3
        tasks = (await http.get("/tasks")).json()["tasks"]
        assert any(t["poster"] == maker.node_id for t in tasks)

        # en ægte køber fylder et af makerens udbud
        from ovriq.core.engine import solve_pow
        rb = await http.post("/nodes/register",
                             json={"name": "real-buyer", "pow_nonce": solve_pow("real-buyer")})
        bd = rb.json()
        bh = {"X-Node-Id": bd["node_id"], "X-Api-Key": bd["api_key"]}
        ask = next(o for o in listings if o["node_id"] == maker.node_id)
        await http.post("/market/orders", headers=bh,
                        json={"side": "BID", "resource_type": ask["resource_type"],
                              "price": ask["price"], "qty": 1})
        # makeren leverer på den FUNDED kontrakt
        await maker._deliver_fills()
        m = (await http.get("/metrics")).json()
        assert m["contracts"].get("SETTLED", 0) >= 1
        # og makeren har ingen risiko-flag (ingen wash — den køber aldrig)
        assert m["risk_flags"] == 0
    await maker._http.aclose()
