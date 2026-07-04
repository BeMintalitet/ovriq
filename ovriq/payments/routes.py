"""OVRIQ betalings-endpoints. Kobles på app'en via attach_payments()."""
from __future__ import annotations

import os

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from .paypal import MAX_DKK, MIN_DKK, PayPalClient, PayPalConfig, PayPalError

client: PayPalClient | None = None  # kan erstattes af tests


def _get_client() -> PayPalClient:
    global client
    if client is None:
        cfg = PayPalConfig()
        if not cfg.configured:
            raise HTTPException(status_code=503,
                                detail="payments not configured (PAYPAL_CLIENT_ID/SECRET)")
        client = PayPalClient(cfg)
    return client


class CheckoutReq(BaseModel):
    amount_dkk: int = Field(ge=MIN_DKK, le=MAX_DKK,
                            description="1 DKK = 1 OQ (gavekort-model, ingen udbetaling)")


def attach_payments(app, *, execute, auth_dep, get_engine) -> None:
    public = os.environ.get("OVRIQ_PUBLIC_URL", "http://127.0.0.1:8642").rstrip("/")

    @app.get("/credits/status")
    async def credits_status():
        try:
            cfg = PayPalConfig()
            return {"payments": "configured" if cfg.configured else "disabled",
                    "env": cfg.env, "min_dkk": MIN_DKK, "max_dkk": MAX_DKK,
                    "model": "prepaid gavekort: OQ kan bruges, ikke udbetales"}
        except PayPalError as e:
            return {"payments": "blocked", "reason": str(e)}

    @app.post("/credits/checkout")
    async def checkout(req: CheckoutReq, node=auth_dep):
        pp = _get_client()
        try:
            order = await pp.create_order(node.node_id, req.amount_dkk,
                                          f"{public}/credits/return",
                                          f"{public}/credits/cancel")
        except PayPalError as e:
            raise HTTPException(status_code=502, detail=str(e))
        return {**order, "next": "godkend paa approve_url, kald derefter "
                                 f"POST /credits/capture/{order['order_id']}"}

    @app.post("/credits/capture/{order_id}")
    async def capture(order_id: str, node=auth_dep):
        pp = _get_client()
        try:
            facts = await pp.capture_order(order_id)  # verificerede fakta fra PayPal
        except PayPalError as e:
            raise HTTPException(status_code=502, detail=str(e))
        eng = get_engine()
        try:
            return await execute(eng.cmd_credit_purchase, facts["node_id"],
                                 facts["amount_dkk"], facts["order_id"],
                                 facts["capture_id"])
        except Exception as e:
            raise HTTPException(status_code=409, detail=str(e))

    @app.post("/webhooks/paypal")
    async def paypal_webhook(request: Request):
        pp = _get_client()
        body = await request.json()
        if not await pp.verify_webhook(dict(request.headers), body):
            raise HTTPException(status_code=401, detail="webhook signature invalid")
        if body.get("event_type") != "PAYMENT.CAPTURE.COMPLETED":
            return {"ignored": body.get("event_type")}
        res = body.get("resource", {})
        amt = res.get("amount", {})
        if amt.get("currency_code") != "DKK":
            raise HTTPException(status_code=422, detail="unexpected currency")
        eng = get_engine()
        try:
            return await execute(eng.cmd_credit_purchase, res.get("custom_id"),
                                 amt.get("value"),
                                 res.get("supplementary_data", {})
                                    .get("related_ids", {}).get("order_id", "?"),
                                 res.get("id"))
        except Exception:
            return {"already_credited_or_invalid": res.get("id")}  # webhook-retry-venlig
