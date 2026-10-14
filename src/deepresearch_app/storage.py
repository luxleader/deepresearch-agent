import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .models import ResearchPacket, ResearchState, now


class SQLiteStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                    calls INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS steps(run_id TEXT, step_key TEXT, status TEXT,
                    attempts INTEGER NOT NULL, packet TEXT, PRIMARY KEY(run_id,step_key));
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT, stage TEXT, detail TEXT, created_at TEXT);
                CREATE TABLE IF NOT EXISTS sources(run_id TEXT, id TEXT, payload TEXT,
                    PRIMARY KEY(run_id,id));
                CREATE TABLE IF NOT EXISTS evidence(run_id TEXT, id TEXT, payload TEXT,
                    PRIMARY KEY(run_id,id));
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, request, mode="replay"):
        state = ResearchState(run_id=uuid.uuid4().hex, request=request, mode=mode)
        with self.connection() as db:
            db.execute("INSERT INTO runs(id,payload) VALUES (?,?)", (state.run_id, state.model_dump_json()))
        self.append_event(state.run_id, "created", {"mode": mode})
        return state

    def get(self, run_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            state = ResearchState.model_validate_json(row["payload"])
            state.calls = row["calls"]
            state.completed_steps = {r["step_key"]: ResearchPacket.model_validate_json(r["packet"])
                                     for r in db.execute("SELECT * FROM steps WHERE run_id=? AND status='completed'", (run_id,))}
        return state

    def save(self, state):
        state.updated_at = now()
        payload = state.model_dump(exclude={"calls", "completed_steps"}, mode="json")
        with self.connection() as db:
            cursor = db.execute("UPDATE runs SET payload=? WHERE id=?", (json.dumps(payload, ensure_ascii=False), state.run_id))
            if not cursor.rowcount:
                raise KeyError(state.run_id)
            for table, entries in [("sources", state.sources), ("evidence", state.evidence)]:
                for item in entries:
                    db.execute(f"INSERT OR REPLACE INTO {table} VALUES (?,?,?)",
                               (state.run_id, item.id, item.model_dump_json()))

    def reserve_call(self, run_id, step_key):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            step = db.execute("SELECT * FROM steps WHERE run_id=? AND step_key=?", (run_id, step_key)).fetchone()
            limit = ResearchState.model_validate_json(row["payload"]).request.max_calls
            if row["calls"] >= limit or (step and step["status"] in {"completed", "running"}):
                return False
            db.execute("UPDATE runs SET calls=calls+1 WHERE id=?", (run_id,))
            db.execute("INSERT INTO steps VALUES (?,?,'running',1,NULL) ON CONFLICT(run_id,step_key) DO UPDATE SET status='running',attempts=attempts+1",
                       (run_id, step_key))
        return True

    def commit_packet(self, run_id, step_key, packet):
        with self.connection() as db:
            cursor = db.execute("UPDATE steps SET status='completed',packet=? WHERE run_id=? AND step_key=? AND status='running'",
                                (packet.model_dump_json(), run_id, step_key))
            if not cursor.rowcount:
                raise ValueError("步骤没有有效调用预留")

    def fail_step(self, run_id, step_key):
        with self.connection() as db:
            db.execute("UPDATE steps SET status='failed' WHERE run_id=? AND step_key=? AND status='running'", (run_id, step_key))

    def claim_run(self, run_id):
        with self.connection() as db:
            cursor = db.execute("UPDATE runs SET active=1 WHERE id=? AND active=0", (run_id,))
            return bool(cursor.rowcount)

    def release_run(self, run_id):
        with self.connection() as db:
            db.execute("UPDATE runs SET active=0 WHERE id=?", (run_id,))

    def recover_interrupted(self):
        with self.connection() as db:
            rows = list(db.execute("SELECT * FROM runs WHERE active=1"))
            for row in rows:
                state = ResearchState.model_validate_json(row["payload"])
                state.status = "interrupted"
                state.error = "进程中断，请显式恢复任务"
                db.execute("UPDATE runs SET active=0,payload=? WHERE id=?", (state.model_dump_json(), row["id"]))
            db.execute("UPDATE steps SET status='failed' WHERE status='running'")

    def append_event(self, run_id, stage, detail):
        with self.connection() as db:
            cursor = db.execute("INSERT INTO events(run_id,stage,detail,created_at) VALUES (?,?,?,?)",
                                (run_id, stage, json.dumps(detail, ensure_ascii=False), now().isoformat()))
            return cursor.lastrowid

    def events(self, run_id, after_seq=0):
        self.get(run_id)
        with self.connection() as db:
            return [{**dict(row), "detail": json.loads(row["detail"])} for row in db.execute(
                "SELECT * FROM events WHERE run_id=? AND seq>? ORDER BY seq LIMIT 500", (run_id, after_seq))]
