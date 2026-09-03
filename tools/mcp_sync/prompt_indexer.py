"""Sync Supabase public.agent_prompts to the Qdrant collection
`vibemind_agent_prompts`. Direct mirror of skills/_indexer.py.

Usage:
    python prompt_indexer.py --rebuild
    python prompt_indexer.py --tool docker
    python prompt_indexer.py --search "deploy a container"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6340")
COLLECTION = os.environ.get("VIBEMIND_PROMPTS_COLLECTION", "vibemind_agent_prompts")
EMBED_MODEL = os.environ.get("VIBEMIND_EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = 1536
OPENAI_BASE = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def embedding_text(row: dict) -> str:
    return f"{row['description']}\n{row.get('trigger','')}\n{row['tool']}"


def point_id_for(row: dict) -> int:
    digest = hashlib.sha1(row["tool"].encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=False) >> 1


def payload_for(row: dict) -> dict:
    return {
        "supabase_id": row["id"],
        "tool": row["tool"],
        "agent_name": row["agent_name"],
        "description": row["description"],
        "trigger": row.get("trigger", ""),
        "visibility": row.get("visibility", ["*"]),
        "confidence": row.get("confidence", 0.5),
    }


def _http_json(method, url, body=None, headers=None) -> dict[str, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {url}: {e.read().decode('utf-8','ignore')[:300]}") from e


def ensure_collection() -> None:
    url = f"{QDRANT_URL}/collections/{COLLECTION}"
    try:
        _http_json("GET", url); return
    except RuntimeError as exc:
        if "404" not in str(exc):
            raise
    _http_json("PUT", url, {"vectors": {"size": EMBED_DIM, "distance": "Cosine"}})
    print(f"[prompt_indexer] created collection {COLLECTION}")


def embed(text: str) -> list[float]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    resp = _http_json("POST", f"{OPENAI_BASE}/embeddings",
                      {"model": EMBED_MODEL, "input": text},
                      {"Authorization": f"Bearer {key}"})
    return resp["data"][0]["embedding"]


def fetch_rows(tool: str | None = None) -> list[dict]:
    q = f"{SUPABASE_URL}/rest/v1/agent_prompts?select=*"
    if tool:
        q += f"&tool=eq.{tool}"
    return _http_json("GET", q, headers={"apikey": SUPABASE_KEY,
                                         "Authorization": f"Bearer {SUPABASE_KEY}"})


def upsert(row: dict) -> None:
    body = {"points": [{"id": point_id_for(row),
                        "vector": embed(embedding_text(row)),
                        "payload": payload_for(row)}]}
    _http_json("PUT", f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true", body)
    print(f"[prompt_indexer] upserted {row['tool']}")


def search(query: str, limit: int = 5) -> list[dict]:
    body = {"vector": embed(query), "limit": limit, "with_payload": True}
    return _http_json("POST", f"{QDRANT_URL}/collections/{COLLECTION}/points/search", body).get("result", [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--tool")
    ap.add_argument("--search")
    args = ap.parse_args()
    ensure_collection()
    if args.search:
        for r in search(args.search):
            p = r["payload"]
            print(f"  [{p['tool']}] {r['score']:.3f}  {p['description']}")
        return 0
    rows = fetch_rows(args.tool)
    for row in rows:
        upsert(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
