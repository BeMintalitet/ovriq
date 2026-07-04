"""[QA+Sikkerhed] Gate 2-kritiske betalingstests — alt mod FAKE PayPal, ingen netvaerk."""
import asyncio

import httpx
import pytest

from ovriq.core.engine import OvriqEngine, solve_pow
from ovriq.core.money import oq


# ── Engine-niveau ───────────────────────────────────────────────────────────
def _engine_with_node():
    e = OvriqEngine()
    ev = e.cmd_register("buyer", solve_pow("buyer"))
    node_id = e.apply(ev)["node_id"]
    return e, node_id


def test_purchase_mints_exactly_and_tracks_reserve():
    e, nid = _engine_with_node()
    ev = e.cmd_credit_purchase(nid, "100.00", "ORD-1", "CAP-1")
    res = e.apply(ev)
    assert res["credited_oq"] == "100.0000"
    assert e.accounts[nid] == oq("1100")          # 1000 faucet + 100 koebt
    assert e.purchased_total == oq("100")
    assert e.invariant_ok()


def test_purchase_idempotency_no_double_mint():
    e, nid = _engine_with_node()
    ev = e.cmd_credit_purchase(nid, "100.00", "ORD-1", "CAP-1")
    e.apply(ev)
    # samme capture_id igen: kommandoen afvises...
    with pytest.raises(Exception, match="idempotency"):
        e.cmd_credit_purchase(nid, "100.00", "ORD-1", "CAP-1")
    # ...og selv hvis samme EVENT afspilles (webhook-retry/replay): ingen dobbelt-mint
    res = e.apply(ev)
    assert res == {"already_credited": "CAP-1"}
    assert e.accounts[nid] == oq("1100")


def test_purchase_rejects_unknown_node_and_bad_amounts():
    e, _ = _engine_with_node()
    with pytest.raises(Exception, match="unknown node"):
        e.cmd_credit_purchase("nd_fake", "100.00", "O", "C")
    nid = next(iter(e.nodes))
    for bad in ("-100", "0", "NaN", "abekat"):
        with pytest.raises(Exception):
            e.cmd_credit_purchase(nid, bad, "O", f"C-{bad}")


# ── API-niveau med fake PayPal ──────────────────────────────────────────────
class FakePayPal:
    """Simulerer PayPal: create → approve → capture. Optaeller kald."""
    def __init__(self):
        self.captured: set[str] = set()
        self.orders: dict[str, tuple[str, int]] = {}
        self.webhook_valid = True

    async def create_order(self, node_id, amount_dkk, return_url, cancel_url):
        oid = f"ORD-{len(self.orders) + 1}"
        self.orders[oid] = (node_id, amount_dkk)
        return {"order_id": oid, "status": "PAYER_ACTION_REQUIRED",
                "approve_url": f"https://fake.paypal/approve/{oid}"}

    async def capture_order(self, order_id):
        node_id, amount = self.orders[order_id]
        self.captured.add(order_id)
        return {"capture_id": f"CAP-{order_id}", "order_id": order_id,
                "node_id": node_id, "amount_dkk": f"{amount}.00",
                "payer_country": "DK"}

    async def verify_webhook(self, headers, body):
        return self.webhook_valid


@pytest.fixture()
def api(tmp_path, monkeypatch):
    import importlib
    import ovriq.payments.routes as routes
    import ovriq.api.server as srv
    importlib.reload(srv)
    srv.boot(str(tmp_path / "j.jsonl"))
    fake = FakePayPal()
    monkeypatch.setattr(routes, "client", fake)
    return srv, fake


async def _register(http, name):
    r = await http.post("/nodes/register", json={"name": name,
                                                 "pow_nonce": solve_pow(name)})
    d = r.json()
    return {"X-Node-Id": d["node_id"], "X-Api-Key": d["api_key"]}, d["node_id"]


@pytest.mark.asyncio
async def test_checkout_capture_flow_credits_correct_node(api):
    srv, fake = api
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=srv.app),
                                 base_url="http://t") as http:
        h, nid = await _register(http, "buyer")
        r = await http.post("/credits/checkout", headers=h, json={"amount_dkk": 100})
        assert r.status_code == 200 and r.json()["approve_url"]
        oid = r.json()["order_id"]
        r = await http.post(f"/credits/capture/{oid}", headers=h)
        assert r.status_code == 200 and r.json()["credited_oq"] == "100.0000"
        r = await http.get("/ledger/balance", headers=h)
        assert r.json()["balance_oq"] == "1100.0000"
        # dobbelt-capture: PayPal-fakta er de samme → idempotens-afvisning, ingen mint
        r = await http.post(f"/credits/capture/{oid}", headers=h)
        assert r.status_code == 409
        r = await http.get("/ledger/balance", headers=h)
        assert r.json()["balance_oq"] == "1100.0000"


@pytest.mark.asyncio
async def test_client_cannot_fake_amount_or_skip_auth(api):
    srv, fake = api
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=srv.app),
                                 base_url="http://t") as http:
        h, nid = await _register(http, "cheater")
        # beloeb uden for caps afvises af Pydantic
        for amt in (0, 5, 1001, 999999):
            r = await http.post("/credits/checkout", headers=h,
                                json={"amount_dkk": amt})
            assert r.status_code == 422
        # ingen auth → 401
        r = await http.post("/credits/checkout", json={"amount_dkk": 100})
        assert r.status_code == 401
        # crediteringen bruger PAYPALS beloeb, ikke klientens: fake en ordre
        # skabt med 100 og forsoeg at "capture" den — beloebet kommer fra fake
        r = await http.post("/credits/checkout", headers=h, json={"amount_dkk": 100})
        oid = r.json()["order_id"]
        fake.orders[oid] = (nid, 100)  # PayPal-sandheden
        r = await http.post(f"/credits/capture/{oid}", headers=h)
        assert r.json()["credited_oq"] == "100.0000"


@pytest.mark.asyncio
async def test_webhook_signature_and_retry_safety(api):
    srv, fake = api
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=srv.app),
                                 base_url="http://t") as http:
        h, nid = await _register(http, "hookbuyer")
        event = {"event_type": "PAYMENT.CAPTURE.COMPLETED",
                 "resource": {"id": "CAP-WH-1", "custom_id": nid,
                              "amount": {"currency_code": "DKK", "value": "50.00"},
                              "supplementary_data": {"related_ids": {"order_id": "ORD-WH"}}}}
        # ugyldig signatur → 401, ingen kredit
        fake.webhook_valid = False
        r = await http.post("/webhooks/paypal", json=event)
        assert r.status_code == 401
        # gyldig → kredit
        fake.webhook_valid = True
        r = await http.post("/webhooks/paypal", json=event)
        assert r.status_code == 200 and r.json()["credited_oq"] == "50.0000"
        # PayPal gensender webhooks → retry maa ALDRIG dobbelt-minte
        r = await http.post("/webhooks/paypal", json=event)
        assert r.status_code == 200 and "credited_oq" not in r.json()
        rb = await http.get("/ledger/balance", headers=h)
        assert rb.json()["balance_oq"] == "1050.0000"
        # forkert valuta afvises
        event["resource"]["id"] = "CAP-WH-2"
        event["resource"]["amount"]["currency_code"] = "USD"
        r = await http.post("/webhooks/paypal", json=event)
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_purchases_survive_restart(api, tmp_path):
    srv, fake = api
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=srv.app),
                                 base_url="http://t") as http:
        h, nid = await _register(http, "persistent")
        r = await http.post("/credits/checkout", headers=h, json={"amount_dkk": 200})
        await http.post(f"/credits/capture/{r.json()['order_id']}", headers=h)
    jp = srv.journal.path
    srv.journal.close()
    import importlib
    import ovriq.api.server as srv2
    importlib.reload(srv2)
    srv2.boot(str(jp))
    assert srv2.engine.accounts[nid] == oq("1200")
    assert srv2.engine.purchased_total == oq("200")
    assert "CAP-ORD-1" in srv2.engine.capture_ids   # idempotens overlever genstart
    srv2.journal.close()
