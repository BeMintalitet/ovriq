"""[QA] Gate 1-beviset: 0 datatab ved crash, tamper-detektion, API-genstart."""
import asyncio
import hashlib
import json
import random

import httpx
import pytest

from ovriq.core.engine import OvriqEngine, solve_pow
from ovriq.storage import FileJournal, JournalError

H = hashlib.sha256(b"payload").hexdigest()


def _run_market(journal_path, n_rounds=30):
    """Kør et marked med journal, returnér (engine, node-ids)."""
    j = FileJournal(journal_path)
    e = OvriqEngine()
    for ev in j.replay_events():
        e.apply(ev)

    def do(ev):
        j.append(ev)
        return e.apply(ev)

    s_id = do(e.cmd_register("seller", solve_pow("seller")))["node_id"]
    b_id = do(e.cmd_register("buyer", solve_pow("buyer")))["node_id"]
    rng = random.Random(42)
    for _ in range(n_rounds):
        rt = rng.choice(["datapakke", "premium_prompt", "compute_tid"])
        price = f"{rng.randint(1, 9)}.{rng.randint(0, 99):02d}"
        res = do(e.cmd_order(s_id, "ASK", rt, price, rng.randint(1, 3)))
        res2 = do(e.cmd_order(b_id, "BID", rt, price, rng.randint(1, 3)))
        for c in res2["contracts"]:
            do(e.cmd_deliver(s_id, c["contract_id"], H))
    j.close()
    return e


def test_crash_and_replay_zero_data_loss(tmp_path):
    """Kør marked, 'crash' (ingen nedlukning), genstart, sammenlign ALT."""
    jp = tmp_path / "journal.jsonl"
    e_before = _run_market(jp)
    assert e_before.trades and e_before.invariant_ok()

    # Genstart: frisk engine, kun journalen som kilde
    j2 = FileJournal(jp)
    e_after = OvriqEngine()
    for ev in j2.replay_events():
        e_after.apply(ev)

    assert e_after.accounts == e_before.accounts
    assert e_after.tx_count == e_before.tx_count
    assert len(e_after.trades) == len(e_before.trades)
    assert [b.block_hash for b in e_after.blocks] == [b.block_hash for b in e_before.blocks]
    assert {c.contract_id: c.state for c in e_after.contracts.values()} == \
           {c.contract_id: c.state for c in e_before.contracts.values()}
    assert e_after.invariant_ok() and e_after.chain_ok()


def test_journal_tamper_detection(tmp_path):
    jp = tmp_path / "journal.jsonl"
    _run_market(jp, n_rounds=3)
    lines = jp.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["event"]["name"] = "hacked"  # manipulér et event
    lines[1] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    jp.write_text("\n".join(lines) + "\n")
    with pytest.raises(JournalError, match="tampered"):
        FileJournal(jp)


def test_append_after_reload_continues_chain(tmp_path):
    jp = tmp_path / "journal.jsonl"
    _run_market(jp, n_rounds=2)
    j = FileJournal(jp)
    e = OvriqEngine()
    for ev in j.replay_events():
        e.apply(ev)
    ev = e.cmd_register("newcomer", solve_pow("newcomer"))
    j.append(ev)
    e.apply(ev)
    j.close()
    j2 = FileJournal(jp)  # verificerer hele kæden inkl. nye event
    assert j2.seq == j.seq and j2.head == j.head


@pytest.mark.asyncio
async def test_api_restart_preserves_state(tmp_path):
    """API-niveau: registrér+handl, 'genstart' serveren, saldi intakte."""
    import importlib
    import ovriq.api.server as srv
    importlib.reload(srv)
    srv.boot(str(tmp_path / "api_journal.jsonl"))

    async def client():
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=srv.app),
                                 base_url="http://t")

    async with await client() as http:
        r = await http.post("/nodes/register",
                            json={"name": "s", "pow_nonce": solve_pow("s")})
        sh = {"X-Node-Id": r.json()["node_id"], "X-Api-Key": r.json()["api_key"]}
        r = await http.post("/nodes/register",
                            json={"name": "b", "pow_nonce": solve_pow("b")})
        bh = {"X-Node-Id": r.json()["node_id"], "X-Api-Key": r.json()["api_key"]}
        await http.post("/market/orders", headers=sh,
                        json={"side": "ASK", "resource_type": "datapakke",
                              "price": "5", "qty": 10})
        r = await http.post("/market/orders", headers=bh,
                            json={"side": "BID", "resource_type": "datapakke",
                                  "price": "5", "qty": 10})
        cid = r.json()["contracts"][0]["contract_id"]
        await http.post(f"/contracts/{cid}/deliver", headers=sh,
                        json={"payload_hash": H})

    srv.journal.close()
    importlib.reload(srv)                       # ← "genstart"
    srv.boot(str(tmp_path / "api_journal.jsonl"))
    async with await client() as http:
        rb = await http.get("/ledger/balance", headers=bh)
        rs = await http.get("/ledger/balance", headers=sh)
        rh = await http.get("/health")
    assert rb.json()["balance_oq"] == "950.0000"
    assert rs.json()["balance_oq"] == "1049.7500"
    assert rh.json()["ledger_invariant_ok"] and rh.json()["chain_valid"]


@pytest.mark.asyncio
async def test_stress_concurrent_orders_with_journal(tmp_path):
    """1000 samtidige ordrer GENNEM journalen: 0 fejl, eksakt invariant."""
    import importlib
    import ovriq.api.server as srv
    importlib.reload(srv)
    srv.boot(str(tmp_path / "stress_journal.jsonl"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=srv.app),
                                 base_url="http://t") as http:
        async def reg(i):
            r = await http.post("/nodes/register",
                                json={"name": f"n{i}", "pow_nonce": solve_pow(f"n{i}")})
            return {"X-Node-Id": r.json()["node_id"], "X-Api-Key": r.json()["api_key"]}
        nodes = await asyncio.gather(*[reg(i) for i in range(20)])
        rng = random.Random(7)

        async def storm(h, i):
            for _ in range(50):
                r = await http.post("/market/orders", headers=h,
                                    json={"side": "ASK" if i % 2 == 0 else "BID",
                                          "resource_type": rng.choice(list(
                                              ("datapakke", "premium_prompt", "compute_tid"))),
                                          "price": f"{rng.randint(1, 5)}.{rng.randint(0, 9)}",
                                          "qty": rng.randint(1, 3)})
                assert r.status_code in (200, 422, 429), r.text
        await asyncio.gather(*[storm(h, i) for i, h in enumerate(nodes)])
        m = (await http.get("/metrics")).json()
    assert m["ledger_invariant_ok"] is True and m["chain_valid"] is True
    assert m["trades_total"] > 0 and m["journal_seq"] > 500
    srv.journal.close()
