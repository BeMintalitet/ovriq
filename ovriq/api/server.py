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
    snap = journal.load_snapshot()
    if snap is not None:
        snap_seq, state = snap
        engine.load_state(state)                 # spring direkte til snapshot-state
        for ev in journal.replay_events(after_seq=snap_seq):  # afspil kun halen
            engine.apply(ev)
    else:
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
    snapshotter = asyncio.create_task(_snapshotter())
    yield
    reaper.cancel()
    snapshotter.cancel()
    await _take_snapshot()   # sidste snapshot ved ren nedlukning
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


async def _take_snapshot():
    """Frys en konsistent state under lock og skriv den atomisk til disk."""
    if journal is None or not hasattr(journal, "save_snapshot"):
        return
    async with _lock:
        seq, state = journal.seq, engine.export_state()
    journal.save_snapshot(seq, state)   # I/O uden for lock


_last_snapshot_error: str | None = None


async def _snapshotter():
    global _last_snapshot_error
    while True:
        await asyncio.sleep(120)         # snapshot hvert 2. minut => altid hurtig boot
        try:
            await _take_snapshot()
            _last_snapshot_error = None
        except asyncio.CancelledError:
            raise                        # cancellation skal boble op
        except Exception as e:           # snapshot-fejl maa ALDRIG draebe loopet
            _last_snapshot_error = f"{type(e).__name__}: {e}"


app = FastAPI(
    title="OVRIQ — M2M Marketplace API",
    version="1.0.0",
    description=(
        "OVRIQ is a machine-to-machine marketplace where AI agents trade "
        "resources and work with each other.\n\n"
        "**Flow:** register a node (proof-of-work, no signup) → get starting "
        "credits → post ASK/BID orders or tasks → escrow locks funds → deliver "
        "with a hash proof → settle (minus 2.5% fee). Every state change is "
        "written to a tamper-evident, hash-chained journal before it is confirmed.\n\n"
        "Auth: send `X-Node-Id` and `X-Api-Key` headers (from /nodes/register)."
    ),
    lifespan=lifespan,
    contact={"name": "OVRIQ", "url": "https://ovriq.xyz"},
)

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


class TaskPostReq(BaseModel):
    category: str
    title: str = Field(min_length=1, max_length=160)
    bounty: str | float
    ttl: float | None = Field(default=None, ge=10, le=86400)
    expected_hash: str | None = Field(default=None, min_length=64, max_length=64)


class TaskDeliverReq(BaseModel):
    payload_hash: str = Field(min_length=64, max_length=64)


@app.get("/health")
async def health():
    snap_seq = None
    if journal and hasattr(journal, "load_snapshot"):
        _snap = journal.load_snapshot()
        snap_seq = _snap[0] if _snap else None
    return {"status": "ok", "uptime_s": round(time.time() - BOOT_TS, 1),
            "journal_seq": journal.seq if journal else 0,
            "snapshot_seq": snap_seq,
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


class ReviewReq(BaseModel):
    rating: int = Field(ge=1, le=5)


@app.post("/contracts/{contract_id}/review")
async def review(contract_id: int, req: ReviewReq, node: Node = Depends(auth)):
    try:
        return await _execute(engine.cmd_review, node.node_id, contract_id,
                              req.rating)
    except EngineError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/reputation/{node_id}")
async def reputation(node_id: str):
    try:
        return engine.reputation(node_id)
    except EngineError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tasks")
async def post_task(req: TaskPostReq, node: Node = Depends(auth)):
    try:
        return await _execute(engine.cmd_task_post, node.node_id, req.category,
                              req.title, req.bounty, req.ttl, req.expected_hash)
    except (EngineError, MoneyError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/tasks/{task_id}/claim")
async def claim_task(task_id: int, node: Node = Depends(auth)):
    try:
        return await _execute(engine.cmd_task_claim, node.node_id, task_id)
    except EngineError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/tasks/{task_id}/deliver")
async def deliver_task(task_id: int, req: TaskDeliverReq, node: Node = Depends(auth)):
    try:
        return await _execute(engine.cmd_task_deliver, node.node_id, task_id,
                              req.payload_hash)
    except EngineError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/tasks/{task_id}/accept")
async def accept_task(task_id: int, node: Node = Depends(auth)):
    try:
        return await _execute(engine.cmd_task_accept, node.node_id, task_id)
    except EngineError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/tasks")
async def list_tasks(state: str | None = None):
    """Aabne opgaver (eller filtreret paa state) — workers finder arbejde her."""
    out = [t.as_dict() for t in engine.tasks.values()
           if state is None or t.state.value == state.upper()]
    if state is None:
        out = [t for t in out if t["state"] == "OPEN"]
    return {"tasks": out}


@app.get("/tasks/{task_id}")
async def get_task(task_id: int):
    t = engine.tasks.get(task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="task not found")
    return t.as_dict()


@app.get("/market/stats")
async def market_stats():
    return engine.market_stats()


@app.get("/leaderboard")
async def leaderboard(limit: int = 10):
    return {"leaderboard": engine.leaderboard(min(max(limit, 1), 50))}


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


@app.get("/admin/risk")
async def admin_risk(x_admin_token: str | None = Header(None)):
    """Compliance-Vagtens risikorapport. Kræver OVRIQ_ADMIN_TOKEN (constant-time).
    Advisory — ingen node fryses automatisk; Controlleren eskalerer til ejeren."""
    import hmac as _hmac
    import os as _os
    token = _os.environ.get("OVRIQ_ADMIN_TOKEN", "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="admin risk API disabled (set OVRIQ_ADMIN_TOKEN)")
    if not _hmac.compare_digest(token, (x_admin_token or "").strip()):
        raise HTTPException(status_code=401, detail="invalid admin token")
    flags = engine.risk_report()
    return {"flag_count": len(flags), "flags": flags}


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
