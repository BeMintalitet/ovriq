"""[QA] Opgave-marked: fuld livscyklus, escrow, auto-accept, misbrug, udloeb, replay."""
import hashlib
import time

import httpx
import pytest

from ovriq.core.engine import OvriqEngine, TaskState, solve_pow

H = hashlib.sha256(b"work").hexdigest()


def _mk(e, n): return e.apply(e.cmd_register(n, solve_pow(n)))["node_id"]


def test_subjective_task_full_lifecycle():
    e = OvriqEngine()
    poster, worker = _mk(e, "poster"), _mk(e, "worker")
    t = e.apply(e.cmd_task_post(poster, "kodning", "Byg en parser", "100"))
    tid = t["task_id"]
    assert e.accounts[poster] == e.core_oq("900")  # 1000 - 100 escrow
    e.apply(e.cmd_task_claim(worker, tid))
    e.apply(e.cmd_task_deliver(worker, tid, H))
    e.apply(e.cmd_task_accept(poster, tid))
    assert e.tasks[tid].state is TaskState.SETTLED
    assert e.accounts[worker] == e.core_oq("1097.50")   # 1000 + 100 - 2.5%
    assert e.accounts["$TREASURY"] == e.core_oq("2.50")
    assert e.invariant_ok() and e.chain_ok()


def test_auto_accept_on_hash_match():
    e = OvriqEngine()
    poster, worker = _mk(e, "p"), _mk(e, "w")
    answer = hashlib.sha256(b"42").hexdigest()
    t = e.apply(e.cmd_task_post(poster, "data", "Find svaret", "50", expected_hash=answer))
    tid = t["task_id"]
    e.apply(e.cmd_task_claim(worker, tid))
    res = e.apply(e.cmd_task_deliver(worker, tid, answer))
    assert res.get("auto_accepted") is True
    assert e.tasks[tid].state is TaskState.SETTLED
    # forkert hash auto-accepterer IKKE
    t2 = e.apply(e.cmd_task_post(poster, "data", "Igen", "50", expected_hash=answer))
    e.apply(e.cmd_task_claim(worker, t2["task_id"]))
    res2 = e.apply(e.cmd_task_deliver(worker, t2["task_id"], H))
    assert not res2.get("auto_accepted")
    assert e.tasks[t2["task_id"]].state is TaskState.CLAIMED


def test_task_abuse_rules():
    e = OvriqEngine()
    poster, worker, evil = _mk(e, "p"), _mk(e, "w"), _mk(e, "evil")
    t = e.apply(e.cmd_task_post(poster, "andet", "Opgave", "100"))
    tid = t["task_id"]
    with pytest.raises(Exception, match="cannot claim your own"):
        e.cmd_task_claim(poster, tid)
    e.apply(e.cmd_task_claim(worker, tid))
    with pytest.raises(Exception, match="not OPEN"):
        e.cmd_task_claim(evil, tid)  # allerede taget
    with pytest.raises(Exception, match="assigned worker"):
        e.cmd_task_deliver(evil, tid, H)  # ikke-worker kan ikke levere
    e.apply(e.cmd_task_deliver(worker, tid, H))
    with pytest.raises(Exception, match="only the poster"):
        e.cmd_task_accept(evil, tid)  # kun poster accepterer
    # overkommitering: dusoer over disponibel saldo
    with pytest.raises(Exception, match="insufficient"):
        e.cmd_task_post(poster, "andet", "For dyr", "100000")


def test_task_expiry_refunds_poster():
    e = OvriqEngine()
    poster, worker = _mk(e, "p"), _mk(e, "w")
    t = e.apply(e.cmd_task_post(poster, "analyse", "Haster", "80", ttl=10))
    tid = t["task_id"]
    e.apply(e.cmd_task_claim(worker, tid))
    e.tasks[tid].deadline = time.time() - 1   # tving udloeb
    ev = e.cmd_expire()
    e.apply(ev)
    assert e.tasks[tid].state is TaskState.REFUNDED
    assert e.accounts[poster] == e.core_oq("1000")  # dusoer retur
    assert e.accounts[worker] == e.core_oq("1000")  # worker fik intet
    assert e.invariant_ok()


def test_tasks_survive_replay():
    e1 = OvriqEngine()
    events = []

    def do(ev):
        events.append(ev)
        return e1.apply(ev)

    p = do(e1.cmd_register("p", solve_pow("p")))["node_id"]
    w = do(e1.cmd_register("w", solve_pow("w")))["node_id"]
    t = do(e1.cmd_task_post(p, "kodning", "X", "60"))
    do(e1.cmd_task_claim(w, t["task_id"]))
    do(e1.cmd_task_deliver(w, t["task_id"], H))
    do(e1.cmd_task_accept(p, t["task_id"]))
    e2 = OvriqEngine()
    for ev in events:
        e2.apply(ev)
    assert e2.accounts == e1.accounts
    assert {k: v.state for k, v in e2.tasks.items()} == {k: v.state for k, v in e1.tasks.items()}
    assert e2.invariant_ok()


@pytest.mark.asyncio
async def test_task_api_flow(tmp_path):
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
        w = await hdr(http, "worker")
        r = await http.post("/tasks", headers=p,
                            json={"category": "kodning", "title": "Byg X", "bounty": "100"})
        assert r.status_code == 200
        tid = r.json()["task_id"]
        # opgaven er synlig i det aabne marked
        r = await http.get("/tasks")
        assert any(t["task_id"] == tid for t in r.json()["tasks"])
        assert (await http.post(f"/tasks/{tid}/claim", headers=w)).status_code == 200
        assert (await http.post(f"/tasks/{tid}/deliver", headers=w,
                                json={"payload_hash": H})).status_code == 200
        assert (await http.post(f"/tasks/{tid}/accept", headers=p)).status_code == 200
        rb = await http.get("/ledger/balance", headers=w)
        assert rb.json()["balance_oq"] == "1097.5000"
        m = (await http.get("/metrics")).json()
        assert m["tasks"]["SETTLED"] == 1 and m["ledger_invariant_ok"]
