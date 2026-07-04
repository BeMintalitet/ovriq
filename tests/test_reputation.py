"""[QA+Sikkerhed] Omdømme: kun køber, kun én gang, kun SETTLED, replay-identisk."""
import hashlib
import time

import pytest

from ovriq.core.engine import EngineError, OvriqEngine, State, solve_pow

H = hashlib.sha256(b"x").hexdigest()


def _mk(e, name):
    return e.apply(e.cmd_register(name, solve_pow(name)))["node_id"]


def _settled_contract(e, seller, buyer, price="10", qty=2):
    e.apply(e.cmd_order(seller, "ASK", "datapakke", price, qty))
    res = e.apply(e.cmd_order(buyer, "BID", "datapakke", price, qty))
    cid = res["contracts"][0]["contract_id"]
    e.apply(e.cmd_deliver(seller, cid, H))
    return cid


def test_review_rules_enforced():
    e = OvriqEngine()
    seller, buyer, evil = _mk(e, "s"), _mk(e, "b"), _mk(e, "evil")
    cid = _settled_contract(e, seller, buyer)
    with pytest.raises(EngineError, match="only the buyer"):
        e.cmd_review(evil, cid, 5)
    with pytest.raises(EngineError, match="only the buyer"):
        e.cmd_review(seller, cid, 5)  # sælger kan ikke rate sig selv
    for bad in (0, 6, "fem"):
        with pytest.raises(EngineError):
            e.cmd_review(buyer, cid, bad)
    e.apply(e.cmd_review(buyer, cid, 5))
    with pytest.raises(EngineError, match="already reviewed"):
        e.cmd_review(buyer, cid, 1)  # ingen ændring af historien


def test_unsettled_contracts_cannot_be_reviewed():
    e = OvriqEngine()
    seller, buyer = _mk(e, "s"), _mk(e, "b")
    e.apply(e.cmd_order(seller, "ASK", "compute_tid", "10", 2))
    res = e.apply(e.cmd_order(buyer, "BID", "compute_tid", "10", 2))
    cid = res["contracts"][0]["contract_id"]  # FUNDED, ikke leveret
    with pytest.raises(EngineError, match="settled"):
        e.cmd_review(buyer, cid, 5)


def test_score_rewards_delivery_and_punishes_refunds():
    e = OvriqEngine()
    good, bad, buyer = _mk(e, "good"), _mk(e, "bad"), _mk(e, "buyer")
    for _ in range(3):
        cid = _settled_contract(e, good, buyer)
        e.apply(e.cmd_review(buyer, cid, 5))
    # bad får sin kontrakt refunderet (leverer aldrig)
    e.apply(e.cmd_order(bad, "ASK", "premium_prompt", "10", 1))
    res = e.apply(e.cmd_order(buyer, "BID", "premium_prompt", "10", 1))
    c = e.contracts[res["contracts"][0]["contract_id"]]
    c.deadline = time.time() - 1  # tving udløb
    e.apply(e.cmd_expire())
    assert c.state is State.REFUNDED
    r_good, r_bad = e.reputation(good), e.reputation(bad)
    assert r_good["score"] > r_bad["score"]
    assert r_good["avg_rating"] == 5.0 and r_good["settled"] == 3
    assert r_bad["refunded"] == 1 and r_bad["settled"] == 0
    # ny node uden historik lander neutralt imellem
    fresh = _mk(e, "fresh")
    assert r_bad["score"] < e.reputation(fresh)["score"] < r_good["score"]


def test_reputation_survives_replay():
    e1 = OvriqEngine()
    events = []

    def do(ev):
        events.append(ev)
        return e1.apply(ev)

    s_id = do(e1.cmd_register("s", solve_pow("s")))["node_id"]
    b_id = do(e1.cmd_register("b", solve_pow("b")))["node_id"]
    do(e1.cmd_order(s_id, "ASK", "datapakke", "10", 2))
    res = do(e1.cmd_order(b_id, "BID", "datapakke", "10", 2))
    cid = res["contracts"][0]["contract_id"]
    do(e1.cmd_deliver(s_id, cid, H))
    do(e1.cmd_review(b_id, cid, 4))
    e2 = OvriqEngine()
    for ev in events:
        e2.apply(ev)
    assert e2.reputation(s_id) == e1.reputation(s_id)
    assert e2.invariant_ok()
