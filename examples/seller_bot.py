"""En komplet OVRIQ-sælger på under 50 linjer.

Kør:  python examples/seller_bot.py  (kræver kørende OVRIQ-server)
Botten lister compute-tid, leverer ved salg og justerer prisen efter trækket.
"""
import asyncio
import hashlib
import random
import time

from ovriq.sdk import OvriqClient

URL = "http://127.0.0.1:8642"


async def main(runtime_s: float = 20.0):
    async with OvriqClient(URL, f"demo-seller-{random.randint(100, 999)}") as c:
        print(f"Registreret som {c.node_id} · saldo {await c.balance()} OQ")
        price, sold = 12.0, 0
        deadline = time.time() + runtime_s
        while time.time() < deadline:
            await c.sell("compute_tid", f"{price:.2f}", qty=2,
                         meta={"gpu": "sim-a100", "quality": 0.9})
            fills = 0
            for contract in await c.pending_deliveries():
                proof = hashlib.sha256(
                    f"work:{contract['contract_id']}".encode()).hexdigest()
                await c.deliver(contract["contract_id"], proof)
                fills += 1
                sold += 1
            price *= 1.05 if fills else 0.98      # simpel market making
            price = max(1.0, min(price, 100.0))
            await asyncio.sleep(0.5)
        print(f"Færdig: {sold} leverancer · saldo {await c.balance()} OQ")


if __name__ == "__main__":
    asyncio.run(main())
