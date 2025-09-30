from datetime import datetime, timezone
from typing import Any, Dict, Literal
from bson import ObjectId
from models.db import db

Role = Literal["system","user","assistant"]
Kind = Literal["status","query","fetch","reflect","draft","section","complete","error","info"]

def _oid(x): return ObjectId(x) if isinstance(x, str) else x

async def emit_msg(run_id: str|ObjectId, *, role: Role, kind: Kind, text: str, meta: Dict[str,Any]|None=None):
    doc = {
        "runId": _oid(run_id),
        "t": datetime.now(timezone.utc),
        "role": role,
        "kind": kind,
        "text": text,
        "meta": meta or {},
    }
    await db().researchMessages.insert_one(doc)
    return doc
