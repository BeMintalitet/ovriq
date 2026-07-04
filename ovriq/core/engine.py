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
from .money import s as s_money

RESOURCE_TYPES = ("datapakke", "premium_prompt", "compute_tid")
ESCROW, TREASURY, MINT = "$ESCROW", "$TREASURY", "$MINT"
FEE_RATE = Decimal("0.025")  # 2,5% markedsplads-gebyr (matcher vilkaar)
FAUCET = oq(1000)
CONTRACT_TTL = 30.0
TASK_TTL = 300.0        # opgaver tager laengere end spot-handler (5 min default)
TASK_CATEGORIES = ("kodning", "data", "analyse", "oversaettelse", "andet")
BLOCK_SIZE = 8
POW_PREFIX = "000"
RATE_CAPACITY, RATE_REFILL = 60.0, 30.0
MAX_QTY = 10_000
WASH_MIN_RECIPROCAL = 2      # trades hver vej før par flagges
CONCENTRATION_MIN_TRADES = 3 # min. afregnede handler før koncentration måles
CONCENTRATION_THRESHOLD = 0.9 # andel af volumen fra én modpart


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
    rating: int | None = None

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["amount"] = s(self.amount)
        d["state"] = self.state.value
        return d


class TaskState(str, Enum):
    OPEN = "OPEN"          # slaaet op, dusoer i escrow, ingen worker endnu
    CLAIMED = "CLAIMED"    # en worker har taget opgaven
    SETTLED = "SETTLED"    # leveret + accepteret, dusoer udbetalt
    REFUNDED = "REFUNDED"  # udloebet uden accept, dusoer retur til poster


@dataclass
class Task:
    task_id: int
    poster: str
    category: str
    title: str
    bounty: Decimal
    deadline: float
    state: TaskState = TaskState.OPEN
    worker: str | None = None
    expected_hash: str | None = None   # sat => auto-accept ved match
    payload_hash: str | None = None
    settled_ts: float | None = None

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["bounty"] = s_money(self.bounty)
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
    tasks: dict[int, Task] = field(default_factory=dict)
    task_seq: int = 0

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

    def _settle_task(self, t: Task, ts: float) -> None:
        fee = oq(t.bounty * FEE_RATE)
        if fee > ZERO:
            self._post(ESCROW, TREASURY, fee, f"task_fee:{t.task_id}")
        self._post(ESCROW, t.worker, t.bounty - fee, f"task_settle:{t.task_id}")
        t.state = TaskState.SETTLED
        t.settled_ts = ts

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

    def cmd_review(self, node_id: str, contract_id: int, rating: int) -> dict:
        """Køberen bedømmer en AFREGNET kontrakt, 1-5, præcis én gang."""
        c = self.contracts.get(contract_id)
        if c is None:
            raise EngineError("contract not found")
        if c.buyer != node_id:
            raise EngineError("only the buyer can review")
        if c.state is not State.SETTLED:
            raise EngineError("only settled contracts can be reviewed")
        if c.rating is not None:
            raise EngineError("contract already reviewed")
        if not isinstance(rating, int) or not 1 <= rating <= 5:
            raise EngineError("rating must be an integer 1-5")
        return {"kind": "REVIEW", "ts": time.time(), "node_id": node_id,
                "contract_id": contract_id, "rating": rating}

    def cmd_task_post(self, node_id: str, category: str, title: str,
                      bounty, ttl: float | None = None,
                      expected_hash: str | None = None) -> dict:
        """Slaa en opgave op. Dusoeren escrow'es straks fra posterens saldo."""
        if node_id not in self.nodes:
            raise EngineError("unknown node")
        if category not in TASK_CATEGORIES:
            raise EngineError(f"unknown category: {category}")
        title = (title or "").strip()[:160]
        if not title:
            raise EngineError("title required")
        b = require_positive(oq(bounty), "bounty")
        available = self.accounts.get(node_id, ZERO) - self._bid_exposure(node_id)
        if available < b:
            raise EngineError(f"insufficient available balance: {s_money(available)} < {s_money(b)}")
        if expected_hash is not None and len(expected_hash) != 64:
            raise EngineError("expected_hash must be a sha256 hex digest")
        return {"kind": "TASK_POST", "ts": time.time(), "node_id": node_id,
                "category": category, "title": title, "bounty": s_money(b),
                "ttl": float(ttl) if ttl else TASK_TTL, "expected_hash": expected_hash}

    def cmd_task_claim(self, node_id: str, task_id: int) -> dict:
        t = self.tasks.get(task_id)
        if t is None:
            raise EngineError("task not found")
        if t.state is not TaskState.OPEN:
            raise EngineError(f"task is {t.state.value}, not OPEN")
        if t.poster == node_id:
            raise EngineError("cannot claim your own task")
        if time.time() > t.deadline:
            raise EngineError("task deadline passed")
        return {"kind": "TASK_CLAIM", "ts": time.time(), "node_id": node_id,
                "task_id": task_id}

    def cmd_task_deliver(self, node_id: str, task_id: int, payload_hash: str) -> dict:
        t = self.tasks.get(task_id)
        if t is None:
            raise EngineError("task not found")
        if t.worker != node_id:
            raise EngineError("only the assigned worker can deliver")
        if t.state is not TaskState.CLAIMED:
            raise EngineError(f"task is {t.state.value}, not CLAIMED")
        if time.time() > t.deadline:
            raise EngineError("task deadline passed; awaiting refund")
        if not payload_hash or len(payload_hash) != 64:
            raise EngineError("payload_hash must be a sha256 hex digest")
        return {"kind": "TASK_DELIVER", "ts": time.time(), "node_id": node_id,
                "task_id": task_id, "payload_hash": payload_hash}

    def cmd_task_accept(self, node_id: str, task_id: int) -> dict:
        """Poster accepterer et subjektivt leveret resultat => udbetaling."""
        t = self.tasks.get(task_id)
        if t is None:
            raise EngineError("task not found")
        if t.poster != node_id:
            raise EngineError("only the poster can accept")
        if t.state is not TaskState.CLAIMED or t.payload_hash is None:
            raise EngineError("task has no delivered work to accept")
        return {"kind": "TASK_ACCEPT", "ts": time.time(), "node_id": node_id,
                "task_id": task_id}

    def cmd_expire(self) -> dict | None:
        now = time.time()
        ids = [c.contract_id for c in self.contracts.values()
               if c.state is State.FUNDED and now > c.deadline]
        task_ids = [t.task_id for t in self.tasks.values()
                    if t.state in (TaskState.OPEN, TaskState.CLAIMED) and now > t.deadline]
        if not ids and not task_ids:
            return None
        return {"kind": "EXPIRE", "ts": now, "contract_ids": ids, "task_ids": task_ids}

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

        if kind == "REVIEW":
            c = self.contracts[ev["contract_id"]]
            c.rating = ev["rating"]
            return {"contract_id": c.contract_id, "rating": c.rating,
                    "seller": c.seller}

        if kind == "TASK_POST":
            self.task_seq += 1
            t = Task(self.task_seq, ev["node_id"], ev["category"], ev["title"],
                     oq(ev["bounty"]), ev["ts"] + ev["ttl"],
                     expected_hash=ev.get("expected_hash"))
            self._post(ev["node_id"], ESCROW, t.bounty, f"task_escrow:{t.task_id}")
            self.tasks[t.task_id] = t
            return t.as_dict()

        if kind == "TASK_CLAIM":
            t = self.tasks[ev["task_id"]]
            t.worker = ev["node_id"]
            t.state = TaskState.CLAIMED
            return t.as_dict()

        if kind == "TASK_DELIVER":
            t = self.tasks[ev["task_id"]]
            t.payload_hash = ev["payload_hash"]
            # auto-accept hvis opgaven havde et forventet hash der matcher
            if t.expected_hash is not None and ev["payload_hash"] == t.expected_hash:
                self._settle_task(t, ev["ts"])
                return {**t.as_dict(), "auto_accepted": True}
            return t.as_dict()

        if kind == "TASK_ACCEPT":
            t = self.tasks[ev["task_id"]]
            self._settle_task(t, ev["ts"])
            return t.as_dict()

        if kind == "EXPIRE":
            out = []
            for cid in ev["contract_ids"]:
                c = self.contracts[cid]
                if c.state is State.FUNDED:
                    self._post(ESCROW, c.buyer, c.amount, f"refund:c{cid}")
                    c.state = State.REFUNDED
                    c.settled_ts = ev["ts"]
                    out.append(c.as_dict())
            tasks_refunded = []
            for tid in ev.get("task_ids", []):
                t = self.tasks[tid]
                if t.state in (TaskState.OPEN, TaskState.CLAIMED):
                    self._post(ESCROW, t.poster, t.bounty, f"task_refund:{tid}")
                    t.state = TaskState.REFUNDED
                    t.settled_ts = ev["ts"]
                    tasks_refunded.append(t.as_dict())
            return {"refunded": out, "tasks_refunded": tasks_refunded}

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

    def reputation(self, node_id: str) -> dict:
        """Afledt omdømme for en node som SÆLGER. Beregnes fra kontrakterne —
        ingen separat tællestand, der kan drive fra sandheden.
        Score 0-100: 50% leveringsevne, 30% ratings, 20% volumen (mæt v. 1000 OQ).
        Nye noder starter neutralt (komponenter uden data tæller 0.5)."""
        if node_id not in self.nodes:
            raise EngineError(f"unknown node: {node_id}")
        settled = refunded = reviews = 0
        rating_sum = 0
        volume = ZERO
        for c in self.contracts.values():
            if c.seller != node_id:
                continue
            if c.state is State.SETTLED:
                settled += 1
                volume += c.amount
                if c.rating is not None:
                    reviews += 1
                    rating_sum += c.rating
            elif c.state is State.REFUNDED:
                refunded += 1
        done = settled + refunded
        settle_comp = (settled / done) if done else 0.5
        rating_comp = ((rating_sum / reviews) - 1) / 4 if reviews else 0.5
        vol_comp = min(1.0, float(volume) / 1000.0)
        score = round(100 * (0.5 * settle_comp + 0.3 * rating_comp + 0.2 * vol_comp))
        return {"node_id": node_id, "name": self.nodes[node_id].name,
                "score": score, "settled": settled, "refunded": refunded,
                "avg_rating": round(rating_sum / reviews, 2) if reviews else None,
                "reviews": reviews, "volume_oq": s_money(volume),
                "member_since": self.nodes[node_id].registered_ts}

    def export_state(self) -> dict:
        """Fuld, JSON-sikker serialisering af hele state til et snapshot.
        Heaps (bids/asks) gemmes IKKE — de rekonstrueres fra ordrer ved load."""
        return {
            "accounts": {k: s_money(v) for k, v in self.accounts.items()},
            "total_minted": s_money(self.total_minted),
            "tx_count": self.tx_count,
            "tx_digests": list(self._tx_digests),
            "blocks": [{"height": b.height, "prev_hash": b.prev_hash,
                        "tx_root": b.tx_root, "n_txs": b.n_txs, "sealed_ts": b.sealed_ts}
                       for b in self.blocks],
            "nodes": {nid: {"node_id": n.node_id, "name": n.name, "api_key": n.api_key,
                            "registered_ts": n.registered_ts, "bucket_tokens": n.bucket_tokens,
                            "bucket_ts": n.bucket_ts} for nid, n in self.nodes.items()},
            "names": list(self.names),
            "orders": {str(oid): {"order_id": o.order_id, "node_id": o.node_id, "side": o.side,
                                  "resource_type": o.resource_type, "price": s_money(o.price),
                                  "qty": o.qty, "open_qty": o.open_qty, "meta": o.meta, "ts": o.ts}
                       for oid, o in self.orders.items()},
            "trades": [{"trade_id": t.trade_id, "resource_type": t.resource_type,
                        "price": s_money(t.price), "qty": t.qty, "buyer": t.buyer,
                        "seller": t.seller, "bid_id": t.bid_id, "ask_id": t.ask_id,
                        "contract_id": t.contract_id, "ts": t.ts} for t in self.trades],
            "contracts": {str(cid): {"contract_id": c.contract_id, "trade_id": c.trade_id,
                                     "buyer": c.buyer, "seller": c.seller, "amount": s_money(c.amount),
                                     "resource_type": c.resource_type, "deadline": c.deadline,
                                     "state": c.state.value, "payload_hash": c.payload_hash,
                                     "settled_ts": c.settled_ts, "rating": c.rating}
                          for cid, c in self.contracts.items()},
            "tasks": {str(tid): {"task_id": t.task_id, "poster": t.poster, "category": t.category,
                                 "title": t.title, "bounty": s_money(t.bounty), "deadline": t.deadline,
                                 "state": t.state.value, "worker": t.worker,
                                 "expected_hash": t.expected_hash, "payload_hash": t.payload_hash,
                                 "settled_ts": t.settled_ts} for tid, t in self.tasks.items()},
            "order_seq": self.order_seq, "trade_seq": self.trade_seq,
            "contract_seq": self.contract_seq, "task_seq": self.task_seq,
            "purchased_total": s_money(self.purchased_total),
            "capture_ids": list(self.capture_ids),
        }

    def load_state(self, d: dict) -> None:
        """Genopbyg fuld state fra et snapshot. Modstykke til export_state."""
        self.accounts = {k: oq(v) for k, v in d["accounts"].items()}
        self.total_minted = oq(d["total_minted"])
        self.tx_count = d["tx_count"]
        self._tx_digests = list(d["tx_digests"])
        self.blocks = [Block(b["height"], b["prev_hash"], b["tx_root"], b["n_txs"], b["sealed_ts"])
                       for b in d["blocks"]]
        self.nodes = {nid: Node(**n) for nid, n in d["nodes"].items()}
        self.names = set(d["names"])
        self.orders = {}
        self.bids = {r: [] for r in RESOURCE_TYPES}
        self.asks = {r: [] for r in RESOURCE_TYPES}
        for o in d["orders"].values():
            order = Order(o["order_id"], o["node_id"], o["side"], o["resource_type"],
                          oq(o["price"]), o["qty"], o["open_qty"], o["meta"], o["ts"])
            self.orders[order.order_id] = order
            if order.open_qty > 0:
                book = self.bids if order.side == "BID" else self.asks
                key = -order.price if order.side == "BID" else order.price
                heapq.heappush(book[order.resource_type], (key, order.ts, order.order_id))
        self.trades = [Trade(t["trade_id"], t["resource_type"], oq(t["price"]), t["qty"],
                             t["buyer"], t["seller"], t["bid_id"], t["ask_id"],
                             t["contract_id"], t["ts"]) for t in d["trades"]]
        self.contracts = {}
        for c in d["contracts"].values():
            con = Contract(c["contract_id"], c["trade_id"], c["buyer"], c["seller"],
                           oq(c["amount"]), c["resource_type"], c["deadline"],
                           State(c["state"]), c["payload_hash"], c["settled_ts"], c["rating"])
            self.contracts[con.contract_id] = con
        self.tasks = {}
        for t in d["tasks"].values():
            tk = Task(t["task_id"], t["poster"], t["category"], t["title"], oq(t["bounty"]),
                      t["deadline"], TaskState(t["state"]), t["worker"], t["expected_hash"],
                      t["payload_hash"], t["settled_ts"])
            self.tasks[tk.task_id] = tk
        self.order_seq = d["order_seq"]; self.trade_seq = d["trade_seq"]
        self.contract_seq = d["contract_seq"]; self.task_seq = d["task_seq"]
        self.purchased_total = oq(d["purchased_total"])
        self.capture_ids = set(d["capture_ids"])

    def market_stats(self) -> dict:
        """Offentligt markedsoverblik pr. ressourcetype: volumen, sidste pris,
        antal handler, åbne udbud. Til dashboard og pris-indeks."""
        state = {c.trade_id: c.state for c in self.contracts.values()}
        per: dict[str, dict] = {rt: {"resource_type": rt, "trades": 0,
                                     "volume_oq": ZERO, "last_price": None,
                                     "open_asks": 0, "low_ask": None}
                                for rt in RESOURCE_TYPES}
        for t in self.trades:
            d = per[t.resource_type]
            d["trades"] += 1
            d["volume_oq"] += t.price * t.qty
            d["last_price"] = t.price
        for o in self.orders.values():
            if o.side == "ASK" and o.open_qty > 0:
                d = per[o.resource_type]
                d["open_asks"] += 1
                if d["low_ask"] is None or o.price < d["low_ask"]:
                    d["low_ask"] = o.price
        markets = []
        for rt in RESOURCE_TYPES:
            d = per[rt]
            markets.append({"resource_type": rt, "trades": d["trades"],
                            "volume_oq": s_money(d["volume_oq"]),
                            "last_price": s_money(d["last_price"]) if d["last_price"] is not None else None,
                            "open_asks": d["open_asks"],
                            "low_ask": s_money(d["low_ask"]) if d["low_ask"] is not None else None})
        settled = sum(1 for st in state.values() if st is State.SETTLED)
        open_tasks = sum(1 for t in self.tasks.values() if t.state is TaskState.OPEN)
        task_bounty = sum((t.bounty for t in self.tasks.values()
                           if t.state is TaskState.OPEN), ZERO)
        return {"markets": markets, "settled_contracts": settled,
                "total_trades": len(self.trades),
                "total_volume_oq": s_money(sum((t.price * t.qty for t in self.trades), ZERO)),
                "active_nodes": len(self.nodes),
                "open_tasks": open_tasks, "open_task_bounty_oq": s_money(task_bounty)}

    def leaderboard(self, limit: int = 10) -> list[dict]:
        """Top-sælgere efter omdømme. Kun noder med mindst én afregnet handel."""
        sellers = {c.seller for c in self.contracts.values()
                   if c.state is State.SETTLED}
        rows = [self.reputation(nid) for nid in sellers]
        rows.sort(key=lambda r: (r["score"], r["settled"]), reverse=True)
        return rows[:limit]

    def risk_report(self) -> list[dict]:
        """Advisory svindeldetektion — READ-ONLY. Fryser aldrig selv; leverer
        flag til Automation Controlleren, som eskalerer til ejeren.
        To mønstre der spiller omdømme-/volumensystemet:
          1) reciprocal_wash: to noder handler frem og tilbage (A→B og B→A),
             klassisk kunstig volumen mellem egne noder.
          2) counterparty_concentration: en sælgers volumen kommer næsten
             udelukkende fra én køber (typisk køberen der pumper sælgerens
             omdømme). Interne bootstrap-noder er undtaget.
        """
        state = {c.trade_id: c.state for c in self.contracts.values()}
        # kun afregnede handler tæller — escrow-refunderede er ikke reel volumen
        settled = [t for t in self.trades if state.get(t.trade_id) is State.SETTLED]

        flags: list[dict] = []

        # 1) reciprocal wash
        pair_dir: dict[tuple[str, str], int] = {}
        for t in settled:
            pair_dir[(t.seller, t.buyer)] = pair_dir.get((t.seller, t.buyer), 0) + 1
        seen: set[frozenset] = set()
        for (a, b), n_ab in pair_dir.items():
            key = frozenset((a, b))
            if key in seen:
                continue
            n_ba = pair_dir.get((b, a), 0)
            if n_ab >= WASH_MIN_RECIPROCAL and n_ba >= WASH_MIN_RECIPROCAL:
                seen.add(key)
                flags.append({"type": "reciprocal_wash", "severity": "high",
                              "nodes": sorted((a, b)),
                              "detail": f"{n_ab}+{n_ba} handler frem og tilbage mellem to noder"})

        # 2) counterparty concentration (omdømme-pumpning)
        by_seller: dict[str, dict[str, Decimal]] = {}
        cnt_seller: dict[str, int] = {}
        for t in settled:
            by_seller.setdefault(t.seller, {})
            by_seller[t.seller][t.buyer] = by_seller[t.seller].get(t.buyer, ZERO) + t.price * t.qty
            cnt_seller[t.seller] = cnt_seller.get(t.seller, 0) + 1
        for seller, buyers in by_seller.items():
            if cnt_seller[seller] < CONCENTRATION_MIN_TRADES:
                continue
            total = sum(buyers.values(), ZERO)
            top_buyer, top_vol = max(buyers.items(), key=lambda kv: kv[1])
            share = float(top_vol / total) if total > ZERO else 0.0
            if share >= CONCENTRATION_THRESHOLD:
                flags.append({"type": "counterparty_concentration", "severity": "medium",
                              "nodes": [seller, top_buyer],
                              "detail": f"{round(share*100)}% af sælgers volumen fra én køber over {cnt_seller[seller]} handler"})
        return flags

    @staticmethod
    def core_oq(v):
        return oq(v)

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
                "last_trades": [t.as_dict() for t in self.trades[-8:]],
                "risk_flags": len(self.risk_report()),
                "tasks": {s: sum(1 for t in self.tasks.values() if t.state.value == s)
                          for s in ("OPEN", "CLAIMED", "SETTLED", "REFUNDED")}}
