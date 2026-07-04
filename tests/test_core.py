"""[QA] OVRIQ core: Decimal-penge, matching, escrow, determinisme."""
import hashlib
from decimal import Decimal

import pytest

from ovriq.core.engine import (FAUCET, AuthError, EngineError, OvriqEngine,
                                solve_pow)
from ovriq.core.money import MoneyError, s, oq

H = hashlib.sha256(b"x").hexdigest()


def _reg(e: OvriqEngine, name: str) -> str:
    ev = e.cmd_register(name, solve_pow(name))
    return e.apply(ev)["node_id"]


def _order(e, node, side, rt, price, qty):
    return e.apply(e.cmd_order(node, side, rt, price, qty))


def test_money_is_exact_decimal():
    assert oq("0.1") + oq("0.2") == oq("0.3")  # umuligt med float
    assert oq(0.1) == Decimal("0.1000")        # float renses via repr
    assert s(oq("5")) == "5.0000"
    with pytest.raises(MoneyError):
        oq("NaN")
    with pytest.raises(MoneyError):
        oq("abekat")


def test_full_lifecycle_exact_amounts():
    e = OvriqEngine()
    seller = _reg(e, "s")
    buyer = _reg(e, "b")
    _order(e, seller, "ASK", "datapakke", "5", 10)
    res = _order(e, buyer, "BID", "datapakke", "5", 10)
    cid = res["contracts"][0]["contract_id"]
    e.apply(e.cmd_deliver(seller, cid, H))
    assert e.accounts[buyer] == oq("950")
    assert e.accounts[seller] == oq("1048.75")   # 1000 + 50 - 0.5%
    assert e.accounts["$TREASURY"] == oq("1.25")
    assert e.invariant_ok() and e.chain_ok()


def test_price_time_priority_and_self_trade_guard():
    e = OvriqEngine()
    s1, s2, b = _reg(e, "s1"), _reg(e, "s2"), _reg(e, "b")
    _order(e, s1, "ASK", "datapakke", "5", 10)
    _order(e, s2, "ASK", "datapakke", "4", 10)
    res = _order(e, b, "BID", "datapakke", "5", 15)
    assert [t["seller"] for t in res["trades"]] == [s2, s1]
    assert res["trades"][0]["price"] == "4.0000"
    # self-trade
    res2 = _order(e, s1, "BID", "datapakke", "9", 1)
    assert res2["trades"] == []


def test_exposure_check_blocks_overcommit():
    e = OvriqEngine()
    b = _reg(e, "whale")
    e.apply(e.cmd_order(b, "BID", "compute_tid", "100", 8))
    with pytest.raises(EngineError, match="insufficient"):
        e.cmd_order(b, "BID", "compute_tid", "100", 8)


def test_escrow_state_machine_and_ownership():
    e = OvriqEngine()
    seller, buyer, evil = _reg(e, "s"), _reg(e, "b"), _reg(e, "evil")
    _order(e, seller, "ASK", "compute_tid", "10", 2)
    res = _order(e, buyer, "BID", "compute_tid", "10", 2)
    cid = res["contracts"][0]["contract_id"]
    with pytest.raises(EngineError, match="only the seller"):
        e.cmd_deliver(evil, cid, H)
    e.apply(e.cmd_deliver(seller, cid, H))
    with pytest.raises(EngineError, match="not FUNDED"):
        e.cmd_deliver(seller, cid, H)  # replay-forsøg
    assert e.invariant_ok()


def test_auth_pow_and_bad_input():
    e = OvriqEngine()
    with pytest.raises(AuthError):
        e.cmd_register("bot", 1)
    node_id = _reg(e, "bot")
    with pytest.raises(AuthError):
        e.authenticate(node_id, "wrong")
    with pytest.raises(AuthError):
        e.cmd_register("bot", solve_pow("bot"))  # navne-sybil
    for bad in [("SIDE", "datapakke", "5", 1), ("BID", "nuclear", "5", 1),
                ("BID", "datapakke", "-1", 1), ("BID", "datapakke", "5", 0)]:
        with pytest.raises((EngineError, MoneyError)):
            e.cmd_order(node_id, *bad)


def test_determinism_same_events_same_state():
    e1 = OvriqEngine()
    events = []
    for cmd in [lambda e: e.cmd_register("s", solve_pow("s")),
                lambda e: e.cmd_register("b", solve_pow("b"))]:
        ev = cmd(e1)
        events.append(ev)
        e1.apply(ev)
    sid = events[0]["node_id"]
    bid = events[1]["node_id"]
    for cmd in [lambda e: e.cmd_order(sid, "ASK", "datapakke", "3.33", 7),
                lambda e: e.cmd_order(bid, "BID", "datapakke", "3.50", 5)]:
        ev = cmd(e1)
        events.append(ev)
        e1.apply(ev)
    e2 = OvriqEngine()
    for ev in events:
        e2.apply(ev)
    assert e2.accounts == e1.accounts
    assert e2.metrics()["volume_oq"] == e1.metrics()["volume_oq"]
    assert [b.block_hash for b in e2.blocks] == [b.block_hash for b in e1.blocks]
