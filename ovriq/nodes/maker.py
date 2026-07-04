"""OVRIQ liquidity-maker: byen har ALTID varer paa hylderne.

Compliance-ren likviditet: makeren POSTER kun staaende udbud (ASK) og et par
aabne opgaver, og LEVERER naar en aegte koeber fylder en ordre. Den KOEBER
aldrig af sig selv => ingen wash, ingen kunstig afregnet volumen. Den giver
blot en ny besoegende noget reelt at handle mod, saa markedet aldrig ser doedt ud.

Identiteten persisteres (data/maker.json), saa genstart ikke ophober doede noder.
Kør: python -m ovriq.nodes.maker   (env OVRIQ_MAKER_URL, default http://127.0.0.1:8642)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
from pathlib import Path

import httpx

from ..core.engine import solve_pow

URL = os.environ.get("OVRIQ_MAKER_URL", "http://127.0.0.1:8642").rstrip("/")
CREDS_PATH = Path(os.environ.get("OVRIQ_MAKER_CREDS", "/data/maker.json"))
RESOURCES = ("datapakke", "premium_prompt", "compute_tid")
BASE_PRICE = {"datapakke": 4.0, "premium_prompt": 9.0, "compute_tid": 15.0}
TARGET_ASKS = 2          # staaende udbud pr. ressource
SKILL_TASKS = 1          # aabne demo-opgaver
CATEGORIES = ("data", "analyse", "kodning")


class LiquidityMaker:
    def __init__(self, base_url: str = URL, name: str = "OVRIQ-Maker"):
        self.base_url, self.name = base_url, name
        self.node_id = self.api_key = None
        self._http = httpx.AsyncClient(base_url=base_url, timeout=15.0)
        self._delivered: set[int] = set()

    async def _ensure_identity(self):
        # genbrug persisteret identitet hvis muligt
        if CREDS_PATH.exists():
            try:
                d = json.loads(CREDS_PATH.read_text())
                # verificér at noden stadig kendes af serveren
                r = await self._http.get("/ledger/balance",
                                         headers={"X-Node-Id": d["node_id"],
                                                  "X-Api-Key": d["api_key"]})
                if r.status_code == 200:
                    self.node_id, self.api_key = d["node_id"], d["api_key"]
                    return
            except Exception:
                self.node_id = None   # persisteret creds ugyldige => registrér paa ny
        # ellers registrér en frisk maker-node
        uniq = f"{self.name}-{random.randint(1000, 9999)}"
        r = await self._http.post("/nodes/register",
                                  json={"name": uniq, "pow_nonce": solve_pow(uniq)})
        r.raise_for_status()
        d = r.json()
        self.node_id, self.api_key = d["node_id"], d["api_key"]
        try:
            CREDS_PATH.parent.mkdir(parents=True, exist_ok=True)
            CREDS_PATH.write_text(json.dumps({"node_id": self.node_id,
                                              "api_key": self.api_key}))
        except OSError:
            pass

    @property
    def _h(self):
        return {"X-Node-Id": self.node_id, "X-Api-Key": self.api_key}

    async def _my_open_asks(self) -> dict[str, int]:
        r = await self._http.get("/market/listings")
        counts = {rt: 0 for rt in RESOURCES}
        for o in r.json().get("listings", []):
            if o["node_id"] == self.node_id and o["resource_type"] in counts:
                counts[o["resource_type"]] += 1
        return counts

    async def _top_up_asks(self):
        counts = await self._my_open_asks()
        for rt in RESOURCES:
            for _ in range(max(0, TARGET_ASKS - counts[rt])):
                price = round(BASE_PRICE[rt] * random.uniform(0.95, 1.1), 2)
                await self._http.post("/market/orders", headers=self._h,
                                      json={"side": "ASK", "resource_type": rt,
                                            "price": f"{price:.2f}",
                                            "qty": random.randint(1, 4),
                                            "meta": {"maker": True, "quality": 0.9}})

    async def _keep_tasks(self):
        r = await self._http.get("/tasks")
        mine = [t for t in r.json().get("tasks", []) if t["poster"] == self.node_id]
        for _ in range(max(0, SKILL_TASKS - len(mine))):
            cat = random.choice(CATEGORIES)
            await self._http.post("/tasks", headers=self._h,
                                  json={"category": cat,
                                        "title": f"Demo-opgave: {cat} ({random.randint(100,999)})",
                                        "bounty": f"{random.randint(15, 40)}.00"})

    async def _deliver_fills(self):
        # levér paa alle FUNDED kontrakter hvor makeren er saelger (aegte koeb)
        r = await self._http.get("/contracts", headers=self._h, params={"state": "FUNDED"})
        for c in r.json().get("contracts", []):
            if c["seller"] != self.node_id or c["contract_id"] in self._delivered:
                continue
            proof = hashlib.sha256(f"maker:{c['contract_id']}".encode()).hexdigest()
            await self._http.post(f"/contracts/{c['contract_id']}/deliver",
                                  headers=self._h, json={"payload_hash": proof})
            self._delivered.add(c["contract_id"])

    async def run(self, tick_s: float = 8.0):
        await self._ensure_identity()
        print(f"[maker] identitet {self.node_id}")
        while True:
            try:
                await self._top_up_asks()
                await self._keep_tasks()
                await self._deliver_fills()
            except Exception as e:
                print(f"[maker] tick-fejl: {e}")
            await asyncio.sleep(tick_s)


async def main():
    await LiquidityMaker().run()


if __name__ == "__main__":
    asyncio.run(main())
