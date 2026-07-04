"""OVRIQ ⇄ PayPal: Orders API v2 + webhook-verifikation.

Miljø styres af PAYPAL_ENV (sandbox|live). Uden PAYPAL_CLIENT_ID/SECRET er
betalinger slået fra, og endpoints svarer 503. LIVE kræver desuden
OVRIQ_ALLOW_LIVE_PAYMENTS=yes — Automation Controllerens ekstra sikring mod
utilsigtet produktion (Gate 2 skal være PASS først).
"""
from __future__ import annotations

import base64
import os
import time

import httpx

BASE = {"sandbox": "https://api-m.sandbox.paypal.com",
        "live": "https://api-m.paypal.com"}
MIN_DKK = 25          # under dette æder gebyrer beløbet
MAX_DKK = 1000        # Controller-cap pr. køb i beta


class PayPalError(Exception):
    pass


class PayPalConfig:
    def __init__(self):
        def env(k, d=""):  # .strip() taaler Windows-linjeskift og mellemrum i .env
            return os.environ.get(k, d).strip()
        self.env = env("PAYPAL_ENV", "sandbox").lower()
        self.client_id = env("PAYPAL_CLIENT_ID")
        self.secret = env("PAYPAL_SECRET")
        self.webhook_id = env("PAYPAL_WEBHOOK_ID")
        if self.env not in BASE:
            raise PayPalError(f"PAYPAL_ENV must be sandbox|live, got {self.env}")
        if self.env == "live" and os.environ.get("OVRIQ_ALLOW_LIVE_PAYMENTS") != "yes":
            raise PayPalError(
                "LIVE payments blocked: Gate 2 not passed "
                "(set OVRIQ_ALLOW_LIVE_PAYMENTS=yes only after compliance PASS)")

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.secret)

    @property
    def base(self) -> str:
        return BASE[self.env]


class PayPalClient:
    """Tynd async klient. Al beløbslogik lever i OVRIQ — PayPal er kun kassen."""

    def __init__(self, config: PayPalConfig | None = None):
        self.cfg = config or PayPalConfig()
        self._token: str | None = None
        self._token_exp = 0.0
        self._http = httpx.AsyncClient(base_url=self.cfg.base, timeout=20.0)

    async def _auth_header(self) -> dict:
        if not self._token or time.time() > self._token_exp - 60:
            basic = base64.b64encode(
                f"{self.cfg.client_id}:{self.cfg.secret}".encode()).decode()
            r = await self._http.post("/v1/oauth2/token",
                                      headers={"Authorization": f"Basic {basic}"},
                                      data={"grant_type": "client_credentials"})
            if r.status_code != 200:
                raise PayPalError(f"oauth failed: {r.status_code}")
            d = r.json()
            self._token = d["access_token"]
            self._token_exp = time.time() + int(d.get("expires_in", 300))
        return {"Authorization": f"Bearer {self._token}"}

    async def create_order(self, node_id: str, amount_dkk: int,
                           return_url: str, cancel_url: str) -> dict:
        """Opret PayPal-ordre for X DKK → X OQ. custom_id bærer node_id."""
        if not (MIN_DKK <= amount_dkk <= MAX_DKK):
            raise PayPalError(f"amount must be {MIN_DKK}-{MAX_DKK} DKK")
        body = {"intent": "CAPTURE",
                "purchase_units": [{
                    "custom_id": node_id,
                    "description": f"OVRIQ credits: {amount_dkk} OQ",
                    "amount": {"currency_code": "DKK", "value": f"{amount_dkk}.00"}}],
                "payment_source": {"paypal": {"experience_context": {
                    "return_url": return_url, "cancel_url": cancel_url,
                    "user_action": "PAY_NOW", "brand_name": "OVRIQ"}}}}
        r = await self._http.post("/v2/checkout/orders", json=body,
                                  headers=await self._auth_header())
        if r.status_code not in (200, 201):
            raise PayPalError(f"create_order failed: {r.status_code} {r.text[:200]}")
        d = r.json()
        approve = next((l["href"] for l in d.get("links", [])
                        if l["rel"] in ("payer-action", "approve")), None)
        return {"order_id": d["id"], "status": d["status"], "approve_url": approve}

    async def capture_order(self, order_id: str) -> dict:
        """Indløs godkendt ordre. Returnerer verificerede fakta FRA PAYPAL —
        aldrig klientens påstande: capture_id, beløb, valuta, node_id."""
        r = await self._http.post(f"/v2/checkout/orders/{order_id}/capture",
                                  json={}, headers=await self._auth_header())
        if r.status_code not in (200, 201):
            raise PayPalError(f"capture failed: {r.status_code} {r.text[:200]}")
        d = r.json()
        if d.get("status") != "COMPLETED":
            raise PayPalError(f"capture not completed: {d.get('status')}")
        pu = d["purchase_units"][0]
        cap = pu["payments"]["captures"][0]
        if cap["amount"]["currency_code"] != "DKK":
            raise PayPalError("unexpected currency")
        return {"capture_id": cap["id"], "order_id": d["id"],
                "node_id": pu.get("custom_id") or cap.get("custom_id"),
                "amount_dkk": cap["amount"]["value"],
                "payer_country": d.get("payment_source", {}).get("paypal", {})
                                  .get("address", {}).get("country_code")}

    async def verify_webhook(self, headers: dict, body: dict) -> bool:
        """Server-til-server verifikation af webhook-signatur hos PayPal."""
        if not self.cfg.webhook_id:
            return False  # uden webhook_id kan intet verificeres → afvis
        payload = {"auth_algo": headers.get("paypal-auth-algo"),
                   "cert_url": headers.get("paypal-cert-url"),
                   "transmission_id": headers.get("paypal-transmission-id"),
                   "transmission_sig": headers.get("paypal-transmission-sig"),
                   "transmission_time": headers.get("paypal-transmission-time"),
                   "webhook_id": self.cfg.webhook_id, "webhook_event": body}
        r = await self._http.post("/v1/notifications/verify-webhook-signature",
                                  json=payload, headers=await self._auth_header())
        return r.status_code == 200 and r.json().get("verification_status") == "SUCCESS"

    async def close(self) -> None:
        await self._http.aclose()
