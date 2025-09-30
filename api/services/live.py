from datetime import datetime, timezone
from typing import Any, Dict
from bson import ObjectId
from models.db import db

def _rid(run_id):
    return ObjectId(run_id) if isinstance(run_id, str) else run_id

async def set_live(run_id: str | ObjectId, kind: str, msg: str, meta: Dict[str, Any] | None=None):
    """Upsert a single live status row per run. Overwrites previous message."""
    rid = _rid(run_id)
    doc = {
        "runId": rid,
        "ts": datetime.now(timezone.utc),   # TTL-compatible
        "kind": kind,
        "msg": msg,
        "meta": meta or {},
    }
    await db().liveStatus.update_one({"runId": rid}, {"$set": doc}, upsert=True)
