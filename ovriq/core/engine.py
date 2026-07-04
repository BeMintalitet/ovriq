"""OVRIQ deterministisk markeds-engine.

Alle statsændringer sker gennem events: kommando-metoder validerer, bygger
eventet (inkl. genererede id'er og tidsstempler), journalfører det og kalder
apply(). Replay kalder apply() med de gemte events → identisk state.
Apply-vejen er ren: ingen ur, ingen RNG, ingen I/O.
"""
from __future__ import annotations

import hashlib
import heapq
import hmac
import secrets
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from .money import ZERO, MoneyError, require_positive, s, oq

RESOURCE_TYPES = ("datapakke", "premium_prompt", "compute_tid")
ESCROW, TREASURY, MINT = "$ESCROW", "$TREASURY", "$MINT"
FEE_RATE = Decimal("0.005")
FAUCET = oq(1000)
CONTRACT_TTL = 30.0
BLOCK_SIZE = 8
POW_PREFIX = "000"
RATE_CAPACITY, RATE_REFILL = 60.0, 30.0
MAX_QTY = 10_000


class EngineError(Exception):
    pass


class AuthError(EngineError):
    pass


class State(str, Enum):
    FUNDED = "FUNDED"
    SETTLED = "SETTLED"
    REFUNDED = "REFUNDED"


def solve_pow(name: str) -> int:
    nonce = 0
    while not hashlib.sha256(f"{name}:{nonce}".encode()).hexdigest().startswith(POW_PREFIX):
        nonce += 1
    return nonce


@dataclass
class Node:
    node_id: str
    name: str
    api_key: str
    registered_ts: float
    bucket_tokens: float = RATE_CAPACITY
    bucket_ts: float = 0.0


@dataclass
class Order:
    order_id: int
    node_id: str
    side: str
    resource_type: str
    price: Decimal
    qty: int
    open_qty: int
    meta: dict
    ts: float

    def as_dict(self) -> dict:
        return {"order_id": self.order_id, "node_id": self.node_id, "side": self.side,
                "resource_type": self.resource_type, "price": s(self.price),
                "qty": self.qty, "open_qty": self.open_qty, "meta": self.meta, "ts": self.ts}


@dataclass
class Trade:
    trade_id: int
    resource_type: str
    price: Decimal
    qty: int
    buyer: str
    seller: str
    bid_id: int
    ask_id: int
    contract_id: int
    ts: float

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["price"] = s(self.price)
        return d


@dataclass
class Contract:
    contract_id: int
    trade_id: int
    buyer: str
    seller: str
    amount: Decimal
    resource_type: str
    deadline: float
    state: State = State.FUNDED
    payload_hash: str | None = None
    settled_ts: float | None = None

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["amount"] = s(self.amount)
        d["state"] = self.state.value
        return d


@dataclass
class Block:
    height: int
    prev_hash: str
    tx_root: str
    n_txs: int
    sealed_ts: float

    @property
    def block_hash(self) -> str:
        return hashlib.sha256(
            f"{self.height}|{self.prev_hash}|{self.tx_root}|{self.n_txs}".encode()).hexdigest()


@dataclass
class OvriqEngine:
    """Ren state machine. Wrap i api.server for lås + journal."""
    accounts: dict[str, Decimal] = field(default_factory=dict)
    total_minted: Decimal = ZERO
    tx_count: int = 0
    _tx_digests: list[str] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)
    nodes: dict[str, Node] = field(default_factory=dict)
    names: set[str] = field(default_factory=set)
    orders: dict[int, Order] = field(default_factory=dict)
    bids: dict[str, list] = field(default_factory=lambda: {r: [] for r in RESOURCE_TYPES})
    asks: dict[str, list] = field(default_factory=lambda: {r: [] for r in RESOURCE_TYPES})
    trades: list[Trade] = field(default_factory=list)
    contracts: dict[int, Contract] = field(default_factory=dict)
    order_seq: int = 0
    trade_seq: int = 0
    contract_seq: int = 0
    purchased_total: Decimal = ZERO
    capture_ids: set[str] = field(default_factory=set)

    # ══ intern bogføring (kaldes kun fra apply) ═══════════════════════════
    def _post(self, src: str, dst: str, amount: Decimal, memo: str) -> None:
        amount = require_positive(oq(amount))
        if src == MINT:
            self.total_minted += amount
        else:
            if self.accounts.get(src, ZERO) < amount:
                raise MoneyError(f"insufficient funds: {src}")
            self.accounts[src] -= amount
        self.accounts[dst] = self.accounts.get(dst, ZERO) + amount
        digest = hashlib.sha256(f"{self.tx_count}|{src}|{dst}|{s(amount)}|{memo}".encode()).hexdigest()
        self.tx_count += 1
        self._tx_digests.append(digest)
        if len(self._tx_digests) >= BLOCK_SIZE:
            prev = self.blocks[-1].block_hash if self.blocks else "0" * 64
            root = hashlib.sha256("".join(self._tx_digests).encode()).hexdigest()
            self.blocks.append(Block(len(self.blocks), prev, root,
                                     len(self._tx_digests), 0.0))
            self._tx_digests = []

    def invariant_ok(self) -> bool:
        return sum(self.accounts.values(), ZERO) == self.total_minted

    def chain_ok(self) -> bool:
        prev = "0" * 64
        for b in self.blocks:
            if b.prev_hash != prev:
                return False
            prev = b.block_hash
        return True

    def _bid_exposure(self, node_id: str) -> Decimal:
        return sum((o.price * o.open_qty for o in self.orders.values()
                    if o.node_id == node_id and o.side == "BID" and o.open_qty > 0), ZERO)

    # ══ kommandoer: validér → byg event ═══════════════════════════════════
    def cmd_register(self, name: str, pow_nonce: int) -> dict:
        name = (name or "").strip()[:64]
        if not name:
            raise AuthError("name required")
        if name in self.names:
            raise AuthError("name already registered")
        digest = hashlib.sha256(f"{name}:{pow_nonce}".encode()).hexdigest()
        if not digest.startswith(POW_PREFIX):
            raise AuthError("invalid proof-of-work nonce")
        return {"kind": "REGISTER", "ts": time.time(), "name": name,
                "node_id": f"oq_{secrets.token_hex(8)}", "api_key": secrets.token_hex(24)}

    def cmd_order(self, node_id: str, side: str, resource_type: str,
                  price, qty: int, meta: dict | None = None) -> dict:
        side = (side or "").upper()
        if side not in ("BID", "ASK"):
            raise EngineError("side must be BID or ASK")
        if resource_type not in RESOURCE_TYPES:
            raise EngineError(f"unknown resource_type: {resource_type}")
        p = require_positive(oq(price), "price")
        if not isinstance(qty, int) or qty <= 0 or qty > MAX_QTY:
            raise EngineError(f"qty must be 1..{MAX_QTY}")
        if side == "BID":
            available = self.accounts.get(node_id, ZERO) - self._bid_exposure(node_id)
            if available < p * qty:
                raise EngineError(f"insufficient available balance: {s(available)} < {s(p * qty)}")
        return {"kind": "ORDER", "ts": time.time(), "node_id": node_id, "side": side,
                "resource_type": resource_type, "price": s(p), "qty": qty,
                "meta": meta or {}}

    def cmd_cancel(self, node_id: str, order_id: int) -> dict:
        o = self.orders.get(order_id)
        if o is None or o.open_qty == 0:
            raise EngineError("order not found or already filled")
        if o.node_id != node_id:
            raise EngineError("not your order")
        return {"kind": "CANCEL", "ts": time.time(), "node_id": node_id, "order_id": order_id}

    def cmd_deliver(self, node_id: str, contract_id: int, payload_hash: str) -> dict:
        c = self.contracts.get(contract_id)
        if c is None:
            raise EngineError("contract not found")
        if c.seller != node_id:
            raise EngineError("only the seller can deliver")
        if c.state is not State.FUNDED:
            raise EngineError(f"contract is {c.state.value}, not FUNDED")
        if time.time() > c.deadline:
            raise EngineError("deadline passed; awaiting refund")
        if not payload_hash or len(payload_hash) != 64:
            raise EngineError("payload_hash must be a sha256 hex digest")
        return {"kind": "DELIVER", "ts": time.time(), "node_id": node_id,
                "contract_id": contract_id, "payload_hash": payload_hash}

    def cmd_credit_purchase(self, node_id: str, amount_dkk: str,
                            order_id: str, capture_id: str) -> dict:
        """Byg CREDIT_PURCHASE-event fra VERIFICEREDE PayPal-fakta (aldrig
        klient-input). 1 DKK = 1 OQ. Idempotent paa capture_id."""
        if node_id not in self.nodes:
            raise EngineError(f"unknown node: {node_id}")
        if not capture_id or capture_id in self.capture_ids:
            raise EngineError("capture already credited (idempotency)")
        amount = require_positive(oq(amount_dkk), "purchase amount")
        return {"kind": "CREDIT_PURCHASE", "ts": time.time(), "node_id": node_id,
                "amount": s(amount), "order_id": order_id, "capture_id": capture_id}

    def cmd_expire(self) -> dict | None:
        now = time.time()
        ids = [c.contract_id for c in self.contracts.values()
               if c.state is State.FUNDED and now > c.deadline]
        if not ids:
            return None
        return {"kind": "EXPIRE", "ts": now, "contract_ids": ids}

    # ══ apply: ren, deterministisk, ur-fri ════════════════════════════════
    def apply(self, ev: dict) -> dict:
        kind = ev["kind"]
        if kind == "REGISTER":
            node = Node(ev["node_id"], ev["name"], ev["api_key"], ev["ts"],
                        bucket_ts=ev["ts"])
            self.nodes[node.node_id] = node
            self.names.add(node.name)
            self._post(MINT, node.node_id, FAUCET, "faucet:registration")
            return {"node_id": node.node_id, "api_key": node.api_key,
                    "faucet_oq": s(FAUCET)}

        if kind == "ORDER":
            self.order_seq += 1
            order = Order(self.order_seq, ev["node_id"], ev["side"], ev["resource_type"],
                          oq(ev["price"]), ev["qty"], ev["qty"], ev["meta"], ev["ts"])
            self.orders[order.order_id] = order
            trades, contracts = self._match(order, ev["ts"])
            if order.open_qty > 0:
                book = self.bids if order.side == "BID" else self.asks
                key = -order.price if order.side == "BID" else order.price
                heapq.heappush(book[order.resource_type], (key, order.ts, order.order_id))
            return {"order": order.as_dict(),
                    "trades": [t.as_dict() for t in trades],
                    "contracts": [c.as_dict() for c in contracts]}

        if kind == "CANCEL":
            self.orders[ev["order_id"]].open_qty = 0
            return {"cancelled": ev["order_id"]}

        if kind == "DELIVER":
            c = self.contracts[ev["contract_id"]]
            fee = oq(c.amount * FEE_RATE)
            if fee > ZERO:
                self._post(ESCROW, TREASURY, fee, f"fee:c{c.contract_id}")
            self._post(ESCROW, c.seller, c.amount - fee, f"settle:c{c.contract_id}")
            c.state = State.SETTLED
            c.payload_hash = ev["payload_hash"]
            c.settled_ts = ev["ts"]
            return c.as_dict()

        if kind == "CREDIT_PURCHASE":
            if ev["capture_id"] in self.capture_ids:  # replay-sikkerhed
                return {"already_credited": ev["capture_id"]}
            amount = oq(ev["amount"])
            self._post(MINT, ev["node_id"], amount,
                       f"purchase:paypal:{ev['capture_id']}")
            self.purchased_total += amount
            self.capture_ids.add(ev["capture_id"])
            return {"node_id": ev["node_id"], "credited_oq": s(amount),
                    "capture_id": ev["capture_id"]}

        if kind == "EXPIRE":
            out = []
            for cid in ev["contract_ids"]:
                c = self.contracts[cid]
                if c.state is State.FUNDED:
                    self._post(ESCROW, c.buyer, c.amount, f"refund:c{cid}")
                    c.state = State.REFUNDED
                    c.settled_ts = ev["ts"]
                    out.append(c.as_dict())
            return {"refunded": out}

        raise EngineError(f"unknown event kind: {kind}")

    def _match(self, incoming: Order, ts: float) -> tuple[list[Trade], list[Contract]]:
        trades: list[Trade] = []
        contracts: list[Contract] = []
        rt = incoming.resource_type
        opposite = self.asks[rt] if incoming.side == "BID" else self.bids[rt]
        while incoming.open_qty > 0 and opposite:
            _, _, oid = opposite[0]
            resting = self.orders.get(oid)
            if resting is None or resting.open_qty == 0:
                heapq.heappop(opposite)
                continue
            crosses = (incoming.price >= resting.price if incoming.side == "BID"
                       else incoming.price <= resting.price)
            if not crosses or resting.node_id == incoming.node_id:
                break
            fill = min(incoming.open_qty, resting.open_qty)
            price = resting.price
            buyer, seller = ((incoming.node_id, resting.node_id) if incoming.side == "BID"
                             else (resting.node_id, incoming.node_id))
            bid_id, ask_id = ((incoming.order_id, resting.order_id) if incoming.side == "BID"
                              else (resting.order_id, incoming.order_id))
            incoming.open_qty -= fill
            resting.open_qty -= fill
            if resting.open_qty == 0:
                heapq.heappop(opposite)
            amount = oq(price * fill)
            self.contract_seq += 1
            self.trade_seq += 1
            self._post(buyer, ESCROW, amount, f"escrow:t{self.trade_seq}")
            c = Contract(self.contract_seq, self.trade_seq, buyer, seller,
                         amount, rt, ts + CONTRACT_TTL)
            self.contracts[c.contract_id] = c
            t = Trade(self.trade_seq, rt, price, fill, buyer, seller,
                      bid_id, ask_id, c.contract_id, ts)
            self.trades.append(t)
            trades.append(t)
            contracts.append(c)
        return trades, contracts

    # ══ auth (uden for event-strømmen: rate limit er flygtig) ═════════════
    def authenticate(self, node_id: str | None, api_key: str | None) -> Node:
        node = self.nodes.get(node_id or "")
        if node is None or not hmac.compare_digest(node.api_key, api_key or ""):
            raise AuthError("invalid credentials")
        now = time.time()
        node.bucket_tokens = min(RATE_CAPACITY,
                                 node.bucket_tokens + (now - node.bucket_ts) * RATE_REFILL)
        node.bucket_ts = now
        if node.bucket_tokens < 1:
            raise AuthError("rate limit exceeded")
        node.bucket_tokens -= 1
        return node

    # ══ læse-snapshots ════════════════════════════════════════════════════
    def snapshot_book(self, resource_type: str, depth: int = 10) -> dict:
        def top(heap):
            return [self.orders[oid].as_dict() for _, _, oid in sorted(heap)
                    if self.orders[oid].open_qty > 0][:depth]
        return {"resource_type": resource_type,
                "bids": top(self.bids[resource_type]),
                "asks": top(self.asks[resource_type])}

    def open_asks(self) -> list[dict]:
        return [o.as_dict() for o in self.orders.values()
                if o.side == "ASK" and o.open_qty > 0]

    def metrics(self) -> dict:
        states: dict[str, int] = {}
        for c in self.contracts.values():
            states[c.state.value] = states.get(c.state.value, 0) + 1
        return {"nodes": len(self.nodes), "orders_total": len(self.orders),
                "trades_total": len(self.trades),
                "volume_oq": s(sum((t.price * t.qty for t in self.trades), ZERO)),
                "contracts": states, "blocks": len(self.blocks),
                "txs": self.tx_count, "chain_valid": self.chain_ok(),
                "ledger_invariant_ok": self.invariant_ok(),
                "treasury_oq": s(self.accounts.get(TREASURY, ZERO)),
                "purchased_oq": s(self.purchased_total),
                "last_trades": [t.as_dict() for t in self.trades[-8:]]}
