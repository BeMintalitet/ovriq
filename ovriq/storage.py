"""OVRIQ journal-persistens: append-only, hash-kædet, write-ahead.

FileJournal (JSONL + fsync) til dev og små deployments.
PostgresJournal (asyncpg) til produktion — samme interface, samme replay.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

GENESIS = "0" * 64


class JournalError(Exception):
    pass


def _hash_event(seq: int, prev_hash: str, payload: str) -> str:
    return hashlib.sha256(f"{seq}|{prev_hash}|{payload}".encode()).hexdigest()


class FileJournal:
    """JSONL-fil; hvert event fsync'es før kommandoen bekræftes (write-ahead)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.seq = 0
        self.head = GENESIS
        self._fh = None
        self._replay_cache: list[dict] = []
        if self.path.exists():
            self._replay_cache = self._load()
        self._fh = open(self.path, "a", encoding="utf-8")

    def _load(self) -> list[dict]:
        events = []
        prev = GENESIS
        with open(self.path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                payload = json.dumps(rec["event"], sort_keys=True, separators=(",", ":"))
                expect = _hash_event(rec["seq"], prev, payload)
                if rec["hash"] != expect:
                    raise JournalError(
                        f"journal tampered or corrupt at line {lineno} (seq {rec['seq']})")
                prev = rec["hash"]
                events.append(rec["event"])
        self.seq = len(events)
        self.head = prev
        return events

    def replay_events(self) -> list[dict]:
        return list(self._replay_cache)

    def append(self, event: dict) -> None:
        payload = json.dumps(event, sort_keys=True, separators=(",", ":"))
        self.seq += 1
        h = _hash_event(self.seq, self.head, payload)
        rec = json.dumps({"seq": self.seq, "hash": h, "event": event},
                         sort_keys=True, separators=(",", ":"))
        self._fh.write(rec + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self.head = h

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    seq        BIGINT PRIMARY KEY,
    hash       CHAR(64) NOT NULL,
    prev_hash  CHAR(64) NOT NULL,
    event      JSONB    NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS events_kind_idx ON events ((event->>'kind'));
"""


class PostgresJournal:
    """Samme kontrakt som FileJournal, mod PostgreSQL. Kræver asyncpg.

    Brug: j = await PostgresJournal.connect(dsn); events = await j.replay_events()
    Append sker i én transaktion med advisory lock => single-writer på tværs
    af processer. Hash-kæden verificeres ved load præcis som FileJournal.
    """

    def __init__(self, pool):
        self.pool = pool
        self.seq = 0
        self.head = GENESIS

    @classmethod
    async def connect(cls, dsn: str):
        import asyncpg  # kun i prod-miljø
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
        async with pool.acquire() as con:
            await con.execute(SCHEMA_SQL)
        return cls(pool)

    async def replay_events(self) -> list[dict]:
        events = []
        prev = GENESIS
        async with self.pool.acquire() as con:
            rows = await con.fetch("SELECT seq, hash, prev_hash, event FROM events ORDER BY seq")
        for r in rows:
            payload = json.dumps(json.loads(r["event"]), sort_keys=True, separators=(",", ":"))
            if r["prev_hash"] != prev or r["hash"] != _hash_event(r["seq"], prev, payload):
                raise JournalError(f"journal tampered or corrupt at seq {r['seq']}")
            prev = r["hash"]
            events.append(json.loads(r["event"]))
        self.seq = len(events)
        self.head = prev
        return events

    async def append(self, event: dict) -> None:
        payload = json.dumps(event, sort_keys=True, separators=(",", ":"))
        async with self.pool.acquire() as con:
            async with con.transaction():
                await con.execute("SELECT pg_advisory_xact_lock(4207)")
                self.seq += 1
                h = _hash_event(self.seq, self.head, payload)
                await con.execute(
                    "INSERT INTO events (seq, hash, prev_hash, event) VALUES ($1,$2,$3,$4)",
                    self.seq, h, self.head, payload)
                self.head = h

    async def close(self) -> None:
        await self.pool.close()


def journal_from_env():
    """OVRIQ_DATABASE_URL=postgres://... => PostgresJournal (async setup i app),
    ellers FileJournal på OVRIQ_JOURNAL_PATH (default ./data/journal.jsonl)."""
    dsn = os.environ.get("OVRIQ_DATABASE_URL", "")
    if dsn.startswith("postgres"):
        return ("postgres", dsn)
    return ("file", os.environ.get("OVRIQ_JOURNAL_PATH", "./data/journal.jsonl"))
