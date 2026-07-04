# PayPal-opsætning · Gate 2 · SANDBOX FØRST

**Status: koden kører i sandbox-mode. Live er teknisk BLOKERET** indtil Gate 2
er PASS — miljøvariablen `OVRIQ_ALLOW_LIVE_PAYMENTS=yes` nægtes af koden selv.

## Din 10-minutters opgave (kræver computer, ikke kun mobil)

1. Gå til **developer.paypal.com** → log ind med din PayPal Business-konto.
2. Apps & Credentials → sørg for at **Sandbox** er valgt (toggle øverst) →
   Create App → navn: `ovriq-sandbox` → Create.
3. Kopiér **Client ID** og **Secret**.
4. I `ovriq/`-mappen: kopiér `.env.example` til `.env` og udfyld:
   ```
   PAYPAL_ENV=sandbox
   PAYPAL_CLIENT_ID=<dit sandbox client id>
   PAYPAL_SECRET=<din sandbox secret>
   ```
   `.env` er gitignoret — den forlader aldrig din maskine, og du indsætter
   den ALDRIG i en chat.
5. Testkonti: developer.paypal.com → Testing Tools → Sandbox Accounts.
   Der ligger en færdig "personal" testkøber (falske penge). Notér login.

## Testflowet (når serveren kører lokalt)

```
POST /credits/checkout {"amount_dkk": 100}   (med node-auth-headers)
→ åbn approve_url i browser → log ind med SANDBOX-testkøberen → godkend
POST /credits/capture/{order_id}
→ 100.0000 OQ crediteret · tjek /ledger/balance
```

Webhooks (til prod): developer.paypal.com → din app → Add Webhook →
URL `https://<server>/webhooks/paypal`, event `Payment capture completed`,
og sæt `PAYPAL_WEBHOOK_ID` i `.env`. Kræver offentlig server (fase 1-deploy).

## Grænser (håndhævet i kode)

Køb: min 25 / max 1.000 DKK pr. transaktion. 1 DKK = 1 OQ, fastlåst.
Gavekort-model: OQ kan bruges på markedspladsen, aldrig udbetales (fase 3-emne).
