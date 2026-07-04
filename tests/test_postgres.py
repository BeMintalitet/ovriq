"""[QA] PostgresJournal-integrationstest. Kører kun når OVRIQ_TEST_PG_DSN er sat
(lokalt via docker-compose, i CI via service-containeren)."""
import hashlib
import os

import pytest

from ovriq.core.engine import OvriqEngine, solve_pow

DSN = os.environ.get("OVRIQ_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="OVRIQ_TEST_PG_DSN not set")

H = hashlib.sha256(b"payload").hexdigest()


@pytest.mark.asyncio
async def test_postgres_journal_roundtrip_and_tamper():
    import asyncpg
    from ovriq.storage import JournalError, PostgresJournal

    con = await asyncpg.connect(DSN)
    await con.execute("DROP TABLE IF EXISTS events")
    await con.close()

    j = await PostgresJournal.connect(DSN)
    e = OvriqEngine()

    async def do(ev):
        await j.append(ev)
        return e.apply(ev)

    s_id = (await do(e.cmd_register("s", solve_pow("s"))))["node_id"]
    b_id = (await do(e.cmd_register("b", solve_pow("b"))))["node_id"]
    await do(e.cmd_order(s_id, "ASK", "datapakke", "5", 10))
    res = await do(e.cmd_order(b_id, "BID", "datapakke", "5", 10))
    await do(e.cmd_deliver(s_id, res["contracts"][0]["contract_id"], H))

    # Genstart fra Postgres
    j2 = await PostgresJournal.connect(DSN)
    e2 = OvriqEngine()
    for ev in await j2.replay_events():
        e2.apply(ev)
    assert e2.accounts == e.accounts
    assert e2.invariant_ok() and e2.chain_ok()

    # Tamper-detektion
    con = await asyncpg.connect(DSN)
    await con.execute(
        "UPDATE events SET event = jsonb_set(event, '{name}', '\"hacked\"') WHERE seq = 1")
    await con.close()
    j3 = await PostgresJournal.connect(DSN)
    with pytest.raises(JournalError):
        await j3.replay_events()
    await j.close(); await j2.close(); await j3.close()
