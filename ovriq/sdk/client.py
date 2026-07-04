"""OVRIQ SDK: alt en agent behøver for at handle på markedspladsen."""
from __future__ import annotations

import httpx

from ..core.engine import solve_pow


class OvriqClient:
    """Async klient. Brug: async with OvriqClient(url, "mit-navn") as c: ..."""

    def __init__(self, base_url: str, name: str,
                 node_id: str | None = None, api_key: str | None = None):
        self.name = name
        self.node_id, self.api_key = node_id, api_key
        self._http = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=15.0)

    async def __aenter__(self):
        if not self.node_id:
            await self.register()
        return self

    async def __aexit__(self, *exc):
        await self._http.aclose()

    async def register(self) -> dict:
        r = await self._http.post("/nodes/register",
                                  json={"name": self.name,
                                        "pow_nonce": solve_pow(self.name)})
        r.raise_for_status()
        d = r.json()
        self.node_id, self.api_key = d["node_id"], d["api_key"]
        return d

    @property
    def _h(self) -> dict:
        return {"X-Node-Id": self.node_id or "", "X-Api-Key": self.api_key or ""}

    async def sell(self, resource_type: str, price: str, qty: int,
                   meta: dict | None = None) -> dict:
        return await self._order("ASK", resource_type, price, qty, meta)

    async def buy(self, resource_type: str, price: str, qty: int) -> dict:
        return await self._order("BID", resource_type, price, qty, None)

    async def _order(self, side, rt, price, qty, meta) -> dict:
        r = await self._http.post("/market/orders", headers=self._h,
                                  json={"side": side, "resource_type": rt,
                                        "price": str(price), "qty": qty,
                                        "meta": meta or {}})
        r.raise_for_status()
        return r.json()

    async def cancel(self, order_id: int) -> None:
        (await self._http.delete(f"/market/orders/{order_id}",
                                 headers=self._h)).raise_for_status()

    async def pending_deliveries(self) -> list[dict]:
        r = await self._http.get("/contracts", headers=self._h,
                                 params={"state": "FUNDED"})
        r.raise_for_status()
        return [c for c in r.json()["contracts"] if c["seller"] == self.node_id]

    async def deliver(self, contract_id: int, payload_hash: str) -> dict:
        r = await self._http.post(f"/contracts/{contract_id}/deliver",
                                  headers=self._h,
                                  json={"payload_hash": payload_hash})
        r.raise_for_status()
        return r.json()

    async def orderbook(self, resource_type: str) -> dict:
        r = await self._http.get(f"/market/orderbook/{resource_type}")
        r.raise_for_status()
        return r.json()

    async def balance(self) -> str:
        r = await self._http.get("/ledger/balance", headers=self._h)
        r.raise_for_status()
        return r.json()["balance_oq"]
