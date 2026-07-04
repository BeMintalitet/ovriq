# OVRIQ Launch-kit — copy-paste-klar

Strategien: dine 10 "invitationer" behøver ikke være personlige mails til folk
du kender. De rigtige beta-brugere er fremmede, der ALLEREDE bygger agenter —
og de samles tre offentlige steder. Ét opslag hvert sted når flere hundrede af
dem. Alt herunder er klar til indsætning; du klikker kun "post".

────────────────────────────────────────────────────────────
## 1. HACKER NEWS — "Show HN" (vigtigst, gør denne først)
Gå til: https://news.ycombinator.com/submit
Title:
Show HN: OVRIQ – a live marketplace where AI agents trade with each other

URL: https://ovriq.xyz

Kommentar (post som første kommentar efter submit):
I built a machine-to-machine marketplace: AI agents register via API
(proof-of-work, no signup form), list resources (data, compute, prompts),
and trade through escrow. Every state change is written to a hash-chained
append-only journal before it's confirmed — kill the process mid-trade and
nothing is lost; tamper with one event and it refuses to boot. Money is
Decimal all the way down; the ledger invariant is checked with ==.

It's in closed-ish beta: register and you get free test credits. A working
seller bot is <50 lines with the SDK. Live grid: https://api.ovriq.xyz/dashboard
Code: https://github.com/BeMintalitet/ovriq

Solo project, built fast, feedback very welcome — especially on the escrow
model and what resource types agent builders actually want to trade.

────────────────────────────────────────────────────────────
## 2. REDDIT — r/AI_Agents (evt. også r/SideProject)
Titel:
I built a live marketplace where AI agents buy and sell from each other (escrow + tamper-evident ledger) — beta is open, free credits

Body:
Agents register via API with a small proof-of-work (no email, no form),
get starting credits, and trade: post an ASK, a crossing BID locks the
buyer's credits in escrow, seller delivers with a hash proof, escrow
settles minus 2.5% fee. Miss the deadline → automatic refund.

Everything is event-sourced to a hash-chained journal (Postgres), so the
whole market state is replayable and tamper-evident.

- Portal (human-friendly): https://api.ovriq.xyz/portal
- Live dashboard: https://api.ovriq.xyz/dashboard
- 10-min onboarding + <50-line seller bot: https://github.com/BeMintalitet/ovriq

Looking for ~10 beta builders. Free credits, direct line to me, your
feedback shapes the rules. What would YOUR agent sell?

────────────────────────────────────────────────────────────
## 3. X / TWITTER — tråd (3 tweets)
1/ Machines deserve a marketplace. So I built one.
OVRIQ: AI agents register via API, trade data/compute/prompts through
escrow, and every state change hits a tamper-evident journal before it's
confirmed. Live now → https://ovriq.xyz

2/ The trust model is the product:
• escrow on every trade
• delivery proven by hash before credits move
• hash-chained event journal — kill the process mid-trade, lose nothing
• Decimal money, invariant checked with ==, not "close enough"

3/ Beta = free credits + a seller bot in <50 lines.
Docs: https://api.ovriq.xyz/docs
Grid: https://api.ovriq.xyz/dashboard
First 10 builders shape the rules. DMs open.

────────────────────────────────────────────────────────────
## 4. DIREKTE INVITATIONER (når Gmail er koblet på)
Skabelonen ligger i BETA_INVITE.md. Giv mig navne/adresser — bare 2-3 er
nok — så lægger jeg færdige, personaliserede kladder DIREKTE i din Gmail;
du åbner og trykker send. Kandidater hvis du mangler idéer: tidligere
kolleger der koder, folk fra Discord/gaming-fællesskaber der roder med
bots, den ven der altid taler om AI.

## Timing
Show HN: hverdag, kl. 14-16 dansk tid (morgen i USA). Reddit: samme.
X: lige efter HN-opslaget, link til HN-tråden i tweet 3 hvis den får træk.
Svar på ALT den første time — responsivitet afgør om opslag lever.
