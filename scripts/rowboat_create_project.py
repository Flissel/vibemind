"""
Create a minimal Rowboat Project record in Mongo so the /api/v1/{projectId}/chat
endpoint can resolve the project. One-shot bootstrap; safe to re-run (idempotent
on the configured ROWBOAT_PROJECT_ID).

Reads:
- ROWBOAT_PROJECT_ID from env  (must match what rowboat clients send)
- ROWBOAT_API_KEY    from env  (becomes the project's secret + an api_key record)
- ROWBOAT_MONGODB_URI from env (default mongodb://localhost:27017)
- ROWBOAT_MONGODB_DB  from env (default 'rowboat')

The minimal workflow has one user-facing agent named 'memory_responder' that
just answers the user's last message. No tools, no prompts. Good enough to make
/chat return 200 instead of 500 and to verify the agents service wiring.
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timezone

from pymongo import MongoClient


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require(var: str) -> str:
    val = os.environ.get(var)
    if not val:
        print(f"FATAL: env var {var} is required", file=sys.stderr)
        sys.exit(2)
    return val


def main() -> int:
    project_id = _require("ROWBOAT_PROJECT_ID")
    api_key = _require("ROWBOAT_API_KEY")
    mongo_uri = os.environ.get("ROWBOAT_MONGODB_URI", "mongodb://localhost:27017")
    mongo_db = os.environ.get("ROWBOAT_MONGODB_DB", "rowboat")

    client = MongoClient(mongo_uri)
    db = client[mongo_db]

    # Minimal workflow: one start agent, no tools, no prompts.
    start_agent_name = "memory_responder"
    workflow = {
        "agents": [
            {
                "name": start_agent_name,
                "type": "conversation",
                "description": "Bootstrap agent for VibeMind memory queries.",
                "instructions": (
                    "You are the user's persistent memory responder. Answer "
                    "based on the user's last message and any memory context "
                    "the system provided. Be terse. If you don't know, say so."
                ),
                "model": os.environ.get("PROVIDER_DEFAULT_MODEL", "gpt-4o-mini"),
                "outputVisibility": "user_facing",
                "controlType": "retain",
                "ragReturnType": "chunks",
                "ragK": 3,
            }
        ],
        "prompts": [],
        "tools": [],
        "pipelines": [],
        "startAgent": start_agent_name,
        "lastUpdatedAt": _now_iso(),
    }

    project_doc = {
        "_id": project_id,
        "name": "VibeMind Memory Bootstrap",
        "createdAt": _now_iso(),
        "lastUpdatedAt": _now_iso(),
        "createdByUserId": "system-bootstrap",
        "secret": hashlib.sha256(f"vibemind-{project_id}".encode()).hexdigest(),
        "draftWorkflow": workflow,
        "liveWorkflow": workflow,
    }

    # Upsert project (idempotent on _id)
    result = db.projects.replace_one(
        {"_id": project_id},
        project_doc,
        upsert=True,
    )
    print(
        f"projects: matched={result.matched_count} modified={result.modified_count} "
        f"upserted_id={result.upserted_id}"
    )

    # Upsert API key record (rowboat uses this for Bearer auth validation)
    api_key_id = f"vibemind-{project_id}"
    api_key_doc = {
        "_id": api_key_id,
        "projectId": project_id,
        "key": api_key,
        "createdAt": _now_iso(),
        "lastUsedAt": None,
    }
    result = db.api_keys.replace_one(
        {"_id": api_key_id},
        api_key_doc,
        upsert=True,
    )
    print(
        f"api_keys: matched={result.matched_count} modified={result.modified_count} "
        f"upserted_id={result.upserted_id}"
    )

    # Upsert project membership for the no-auth guest user. Rowboat's UI pages
    # (workflow, sources/knowledge-graph) authorize via project_members, NOT the
    # API key. With USE_AUTH=false, authCheck() returns GUEST_DB_USER (id
    # "guest_user"). Without this record the UI throws "User is not a member of
    # the project" -> client-side exception (blank page).
    guest_user_id = "guest_user"
    member_id = f"member-{guest_user_id}-{project_id}"
    member_doc = {
        "_id": member_id,
        "userId": guest_user_id,
        "projectId": project_id,
        "createdAt": _now_iso(),
        "lastUpdatedAt": _now_iso(),
    }
    result = db.project_members.replace_one(
        {"_id": member_id},
        member_doc,
        upsert=True,
    )
    print(
        f"project_members: matched={result.matched_count} modified={result.modified_count} "
        f"upserted_id={result.upserted_id}"
    )

    # Ensure the guest user itself exists (some pages load the user record).
    user_doc = {
        "_id": guest_user_id,
        "auth0Id": guest_user_id,
        "name": "Guest",
        "email": "guest@rowboatlabs.com",
        "createdAt": _now_iso(),
    }
    result = db.users.replace_one({"_id": guest_user_id}, user_doc, upsert=True)
    print(
        f"users: matched={result.matched_count} modified={result.modified_count} "
        f"upserted_id={result.upserted_id}"
    )

    print(f"OK: project {project_id!r} ready, agent={start_agent_name!r}, guest member added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
