"""OVRIQ API: [N0D3-X]-endpoints løftet til Decimal + journal-persistens."""
from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from ..core.engine import AuthError, EngineError, Node, OvriqEngine, RESOURCE_TYPES
from ..core.money import MoneyError
from ..storage import FileJournal, journal_from_env

engine = OvriqEngine()
journal: FileJournal | None = None
_lock = asyncio.Lock()
_latencies: list[float] = []
BOOT_TS = time.time()


def boot(journal_path: str | None = None) -> None:
    """Indlæs journal og genopbyg state. Kaldes ved opstart og i tests."""
    global engine, journal
    kind, target = ("file", journal_path) if journal_path else journal_from_env()
    if kind != "file":  # Postgres-vejen initialiseres async i lifespan (prod)
        raise RuntimeError("PostgresJournal initialiseres via lifespan i prod-image")
    engine = OvriqEngine()
    journal = FileJournal(target)
    for ev in journal.replay_events():
        engine.apply(ev)


async def _boot_async() -> None:
    """Prod-opstart: backend vælges af OVRIQ_DATABASE_URL. Postgres er async."""
    global engine, journal
    kind, target = journal_from_env()
    if kind == "file":
        boot(target)
        return
    from ..storage import PostgresJournal
    engine = OvriqEngine()
    journal = await PostgresJournal.connect(target)
    for ev in await journal.replay_events():
        engine.apply(ev)


async def _append(ev: dict) -> None:
    """Write-ahead: virker for både sync FileJournal og async PostgresJournal."""
    r = journal.append(ev)
    if hasattr(r, "__await__"):
        await r


@asynccontextmanager
async def lifespan(app: FastAPI):
    if journal is None:
        await _boot_async()
    reaper = asyncio.create_task(_reaper())
    yield
    reaper.cancel()
    if journal:
        r = journal.close()
        if hasattr(r, "__await__"):
            await r


async def _reaper():
    while True:
        await asyncio.sleep(1.0)
        async with _lock:
            ev = engine.cmd_expire()
            if ev:
                await _append(ev)
                engine.apply(ev)


app = FastAPI(title="OVRIQ M2M Marketplace", version="1.0.0-fase1", lifespan=lifespan)

from .webui import attach  # noqa: E402
attach(app)

from .portal import attach_portal  # noqa: E402
attach_portal(app)


@app.middleware("http")
async def _latency_mw(request, call_next):
    t0 = time.perf_counter()
    resp = await call_next(request)
    _latencies.append((time.perf_counter() - t0) * 1000)
    if len(_latencies) > 2000:
        del _latencies[:1000]
    return resp


async def _execute(cmd_fn, *args, **kwargs) -> dict:
    """Kommando-pipeline: validér → journalfør (fsync) → apply → svar."""
    async with _lock:
        ev = cmd_fn(*args, **kwargs)
        await _append(ev)
        return engine.apply(ev)


def auth(x_node_id: str | None = Header(None), x_api_key: str | None = Header(None)) -> Node:
    try:
        return engine.authenticate(x_node_id, x_api_key)
    except AuthError as e:
        raise HTTPException(status_code=429 if "rate" in str(e) else 401, detail=str(e))


class RegisterReq(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    pow_nonce: int = Field(ge=0)


class OrderReq(BaseModel):
    side: str
    resource_type: str
    price: str | float = Field(description="OQ-beløb; send helst som streng")
    qty: int = Field(gt=0, le=10_000)
    meta: dict = Field(default_factory=dict)


class DeliverReq(BaseModel):
    payload_hash: str = Field(min_length=64, max_length=64)


@app.get("/health")
async def health():
    return {"status": "ok", "uptime_s": round(time.time() - BOOT_TS, 1),
            "journal_seq": journal.seq if journal else 0,
            "journal_head": journal.head[:16] if journal else None,
            "ledger_invariant_ok": engine.invariant_ok(),
            "chain_valid": engine.chain_ok()}


@app.post("/nodes/register")
async def register(req: RegisterReq):
    try:
        return await _execute(engine.cmd_register, req.name, req.pow_nonce)
    except (AuthError, EngineError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/market/orders")
async def submit_order(req: OrderReq, node: Node = Depends(auth)):
    try:
        return await _execute(engine.cmd_order, node.node_id, req.side,
                              req.resource_type, req.price, req.qty, req.meta)
    except (EngineError, MoneyError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.delete("/market/orders/{order_id}")
async def cancel_order(order_id: int, node: Node = Depends(auth)):
    try:
        return await _execute(engine.cmd_cancel, node.node_id, order_id)
    except EngineError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/contracts/{contract_id}/deliver")
async def deliver(contract_id: int, req: DeliverReq, node: Node = Depends(auth)):
    try:
        return await _execute(engine.cmd_deliver, node.node_id, contract_id,
                              req.payload_hash)
    except (EngineError, MoneyError) as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/contracts")
async def my_contracts(state: str | None = None, node: Node = Depends(auth)):
    return {"contracts": [c.as_dict() for c in engine.contracts.values()
                          if node.node_id in (c.buyer, c.seller)
                          and (state is None or c.state.value == state.upper())]}


@app.get("/market/listings")
async def listings():
    return {"listings": engine.open_asks()}


@app.get("/market/orderbook/{resource_type}")
async def orderbook(resource_type: str):
    if resource_type not in RESOURCE_TYPES:
        raise HTTPException(status_code=404, detail="unknown resource_type")
    return engine.snapshot_book(resource_type)


@app.get("/ledger/balance")
async def balance(node: Node = Depends(auth)):
    from ..core.money import ZERO, s
    return {"node_id": node.node_id,
            "balance_oq": s(engine.accounts.get(node.node_id, ZERO))}


@app.get("/ledger/blocks")
async def blocks(limit: int = 10):
    bs = engine.blocks[-min(limit, 100):]
    return {"height": len(engine.blocks), "chain_valid": engine.chain_ok(),
            "blocks": [{"height": b.height, "hash": b.block_hash,
                        "prev": b.prev_hash, "txs": b.n_txs} for b in bs]}


@app.get("/metrics")
async def metrics():
    m = engine.metrics()
    m["uptime_s"] = round(time.time() - BOOT_TS, 1)
    m["journal_seq"] = journal.seq if journal else 0
    if _latencies:
        recent = _latencies[-500:]
        m["latency_ms_avg"] = round(sum(recent) / len(recent), 2)
        m["latency_ms_max"] = round(max(recent), 2)
    return m


# ── betalinger (Gate 2): kobles paa til sidst, da den bruger _execute/auth ──
from ..payments.routes import attach_payments  # noqa: E402
import ovriq.api.server as _self  # noqa: E402
attach_payments(app, execute=_execute, auth_dep=Depends(auth),
                get_engine=lambda: _self.engine)
