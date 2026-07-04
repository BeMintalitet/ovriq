"""[QA] Journal-snapshots: round-trip == replay, hurtig boot bevarer alt, dashboard-tasks."""
import hashlib
import httpx
import pytest

from ovriq.core.engine import OvriqEngine, solve_pow
from ovriq.storage import FileJournal

H = hashlib.sha256(b"x").hexdigest()


def _busy_market(e):
    def reg(n): return e.apply(e.cmd_register(n, solve_pow(n)))["node_id"]
    s, b, w = reg("s"), reg("b"), reg("w")
    e.apply(e.cmd_order(s, "ASK", "datapakke", "5", 10))
    r = e.apply(e.cmd_order(b, "BID", "datapakke", "5", 6))
    cid = r["contracts"][0]["contract_id"]
    e.apply(e.cmd_deliver(s, cid, H))
    e.apply(e.cmd_review(b, cid, 5))
    t = e.apply(e.cmd_task_post(b, "kodning", "Byg X", "40"))
    e.apply(e.cmd_task_claim(w, t["task_id"]))
    e.apply(e.cmd_task_deliver(w, t["task_id"], H))
    e.apply(e.cmd_task_accept(b, t["task_id"]))
    e.apply(e.cmd_order(s, "ASK", "compute_tid", "9", 2))  # åben ordre (heap-test)
    return s, b, w


def test_snapshot_roundtrip_matches_full_state():
    import json
    e = OvriqEngine()
    s, b, w = _busy_market(e)
    snap = json.loads(json.dumps(e.export_state()))  # gennem JSON = fuld realisme
    e2 = OvriqEngine()
    e2.load_state(snap)
    assert e2.accounts == e.accounts
    assert e2.metrics() == e.metrics()
    assert e2.reputation(s) == e.reputation(s)
    assert e2.market_stats() == e.market_stats()
    assert e2.risk_report() == e.risk_report()
    assert [x.block_hash for x in e2.blocks] == [x.block_hash for x in e.blocks]
    # handel kan fortsætte efter load (heaps intakte)
    r = e2.apply(e2.cmd_order(w, "BID", "compute_tid", "9", 1))
    assert r["trades"] and e2.invariant_ok() and e2.chain_ok()


def test_boot_from_snapshot_equals_full_replay(tmp_path):
    jp = tmp_path / "j.jsonl"
    j = FileJournal(jp)
    e = OvriqEngine()

    def do(ev):
        j.append(ev)
        return e.apply(ev)

    def reg(n): return do(e.cmd_register(n, solve_pow(n)))["node_id"]
    s, b = reg("s"), reg("b")
    do(e.cmd_order(s, "ASK", "datapakke", "5", 4))
    r = do(e.cmd_order(b, "BID", "datapakke", "5", 4))
    do(e.cmd_deliver(s, r["contracts"][0]["contract_id"], H))
    # skriv snapshot ved nuværende seq, tilføj SÅ flere events efter
    j.save_snapshot(j.seq, e.export_state())
    do(e.cmd_order(s, "ASK", "compute_tid", "7", 2))
    r2 = do(e.cmd_order(b, "BID", "compute_tid", "7", 2))
    do(e.cmd_deliver(s, r2["contracts"][0]["contract_id"], H))
    j.close()

    # A) fuld replay uden snapshot
    e_full = OvriqEngine()
    jA = FileJournal(jp)
    for ev in jA.replay_events():
        e_full.apply(ev)

    # B) boot fra snapshot + kun hale
    e_snap = OvriqEngine()
    jB = FileJournal(jp)
    snap_seq, state = jB.load_snapshot()
    e_snap.load_state(state)
    tail = jB.replay_events(after_seq=snap_seq)
    assert len(tail) == 3   # kun de 3 events efter snapshot
    for ev in tail:
        e_snap.apply(ev)

    assert e_snap.accounts == e_full.accounts
    assert e_snap.metrics()["volume_oq"] == e_full.metrics()["volume_oq"]
    assert e_snap.invariant_ok() and e_snap.chain_ok()


def test_snapshot_atomic_write(tmp_path):
    j = FileJournal(tmp_path / "j.jsonl")
    e = OvriqEngine()
    j.append(e.cmd_register("x", solve_pow("x")))
    j.save_snapshot(j.seq, e.export_state())
    assert j.snapshot_path.exists()
    # ingen efterladt .tmp-fil
    assert not j.snapshot_path.with_suffix(j.snapshot_path.suffix + ".tmp").exists()
    seq, state = j.load_snapshot()
    assert seq == j.seq and "accounts" in state


@pytest.mark.asyncio
async def test_api_boot_uses_snapshot(tmp_path):
    import importlib
    import ovriq.api.server as srv
    importlib.reload(srv)
    srv.boot(str(tmp_path / "j.jsonl"))

    async def hdr(http, name):
        r = await http.post("/nodes/register",
                            json={"name": name, "pow_nonce": solve_pow(name)})
        d = r.json()
        return {"X-Node-Id": d["node_id"], "X-Api-Key": d["api_key"]}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=srv.app),
                                 base_url="http://t") as http:
        p = await hdr(http, "poster")
        await http.post("/tasks", headers=p,
                        json={"category": "data", "title": "Skrab X", "bounty": "75"})
        # tvungent snapshot
        await srv._take_snapshot()
        h = (await http.get("/health")).json()
        assert h["snapshot_seq"] is not None and h["snapshot_seq"] >= 1
        # opgaven er på dashboard + i stats
        assert "AABNE OPGAVER" in (await http.get("/dashboard")).text
        stt = (await http.get("/market/stats")).json()
        assert stt["open_tasks"] == 1 and stt["open_task_bounty_oq"] == "75.0000"

    # "genstart": frisk reload booter fra snapshot
    importlib.reload(srv)
    srv.boot(str(tmp_path / "j.jsonl"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=srv.app),
                                 base_url="http://t") as http:
        assert (await http.get("/market/stats")).json()["open_tasks"] == 1
        assert (await http.get("/health")).json()["ledger_invariant_ok"]
    srv.journal.close()
