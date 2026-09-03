# OpenFang Tool-Agent-Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `servers.json` the single source of truth for VibeMind's generic MCP tools, generate OpenFang's TOML + Claude's `.mcp.json` from it, and delete the ~22 redundant `security/poc_*` tool-mirrors — without touching the coding-engine runtime or the security defensive PoCs.

**Architecture:** A pure-text generator (`mcp_sync.py`) reads `servers.json` and writes a marker-delimited block into the OpenFang TOML and `.mcp.json`. A `--check` mode is a CI gate against hand-drift. A second store (Supabase `agent_prompts` + Qdrant `vibemind_agent_prompts`, modeled 1:1 on `skills/_indexer.py`) holds the per-tool prompt templates for the later runtime phases.

**Tech Stack:** Python 3.11 (stdlib only for the generator, mirroring `skills/_indexer.py`), JSON/TOML, Qdrant HTTP API, Supabase (Postgres), OpenAI `text-embedding-3-small`.

**Spec:** `docs/superpowers/specs/2026-06-25-openfang-tool-agent-hub-design.md`

---

## File Structure

| File | Responsibility | Phase |
|---|---|---|
| `vibemind-os/coding-engine/mcp_plugins/servers/servers.json` | **Source of truth** — add `scope` per server | 1 |
| `tools/mcp_sync/mcp_sync.py` | Generator: servers.json → TOML block + `.mcp.json` | 1 |
| `tools/mcp_sync/test_mcp_sync.py` | Unit tests for the generator | 1 |
| `vibemind-os/openfang/openfang.vibemind.toml.template` | Add marker region for the generated tool block | 1 |
| `.mcp.json` (repo root) | Generated Claude-session MCP list (marker region) | 1 |
| `vibemind-os/security/poc_<tool>/` (~22 dirs) | **Deleted** — redundant tool-mirrors | 1 |
| `supabase/migrations/<ts>_agent_prompts.sql` | Supabase `agent_prompts` table | 2 |
| `tools/mcp_sync/prompt_indexer.py` | Supabase rows → Qdrant `vibemind_agent_prompts` (mirror of `_indexer.py`) | 2 |
| `tools/mcp_sync/test_prompt_indexer.py` | Unit tests for the indexer | 2 |

---

## Phase 1 — Source of Truth + Generator + De-Dup

### Task 1: Add `scope` field to `servers.json`

**Files:**
- Modify: `vibemind-os/coding-engine/mcp_plugins/servers/servers.json`

- [ ] **Step 1: Read the current server keys**

Run: `python -c "import json; d=json.load(open('vibemind-os/coding-engine/mcp_plugins/servers/servers.json')); print([s['name'] for s in d['servers']])"`
Expected: a list of 22 names (playwright, github, docker, …).

- [ ] **Step 2: Add `"scope"` to every server entry**

For each entry in `servers`, add a `"scope"` key. Coding-only tools get `"coding-only"`; everything else gets `"global"`.

Coding-only set (NOT generated into the hub): `npm`, `prisma`, `claude-code`, `dev`, `tests`, `fungus_mcp`.

Example (docker stays global, npm becomes coding-only):

```json
{
  "name": "docker",
  "active": true,
  "scope": "global",
  "type": "stdio",
  ...
},
{
  "name": "npm",
  "active": true,
  "scope": "coding-only",
  "type": "stdio",
  ...
}
```

- [ ] **Step 3: Verify JSON still parses + scope coverage**

Run: `python -c "import json; d=json.load(open('vibemind-os/coding-engine/mcp_plugins/servers/servers.json')); assert all('scope' in s for s in d['servers']), 'missing scope'; print('global:', sum(s['scope']=='global' for s in d['servers']), 'coding-only:', sum(s['scope']=='coding-only' for s in d['servers']))"`
Expected: PASS, prints counts (global ≈ 16, coding-only ≈ 6).

- [ ] **Step 4: Commit**

```bash
git add vibemind-os/coding-engine/mcp_plugins/servers/servers.json
git commit -m "feat(mcp): add scope field to servers.json (global vs coding-only)"
```

---

### Task 2: The `mcp_sync` generator (pure transform, TDD)

**Files:**
- Create: `tools/mcp_sync/mcp_sync.py`
- Test: `tools/mcp_sync/test_mcp_sync.py`

- [ ] **Step 1: Write the failing test**

```python
# tools/mcp_sync/test_mcp_sync.py
import json
import textwrap
from pathlib import Path

import mcp_sync


SAMPLE = {
    "servers": [
        {"name": "docker", "active": True, "scope": "global",
         "command": "python", "args": ["-m", "docker_mcp"],
         "read_timeout_seconds": 120, "description": "Docker"},
        {"name": "github", "active": True, "scope": "global",
         "command": "npx", "args": ["-y", "server-github"],
         "env_vars": {"GITHUB_PERSONAL_ACCESS_TOKEN": "env:GITHUB_TOKEN"},
         "read_timeout_seconds": 120, "description": "GitHub"},
        {"name": "npm", "active": True, "scope": "coding-only",
         "command": "npx", "args": ["-y", "server-npm"],
         "read_timeout_seconds": 60, "description": "npm"},
        {"name": "old", "active": False, "scope": "global",
         "command": "x", "args": [], "read_timeout_seconds": 30,
         "description": "inactive"},
    ]
}


def test_selected_servers_only_global_and_active():
    names = [s["name"] for s in mcp_sync.selected(SAMPLE)]
    assert names == ["docker", "github"]  # npm=coding-only, old=inactive excluded


def test_render_toml_block_is_deterministic():
    block = mcp_sync.render_toml(SAMPLE)
    assert mcp_sync.TOML_BEGIN in block and mcp_sync.TOML_END in block
    assert '[[mcp_servers]]\nname = "docker"' in block
    assert 'timeout_secs = 120' in block
    assert 'command = "python"' in block
    assert 'args = ["-m", "docker_mcp"]' in block
    # env-bearing server emits an env table
    assert '[mcp_servers.transport.env]' in block
    assert 'GITHUB_PERSONAL_ACCESS_TOKEN = "env:GITHUB_TOKEN"' in block
    # rendering twice is identical
    assert block == mcp_sync.render_toml(SAMPLE)


def test_render_mcp_json_shape():
    obj = json.loads(mcp_sync.render_mcp_json(SAMPLE))
    assert set(obj["mcpServers"].keys()) == {"docker", "github"}
    assert obj["mcpServers"]["docker"]["command"] == "python"
    assert obj["mcpServers"]["github"]["env"] == {"GITHUB_PERSONAL_ACCESS_TOKEN": "env:GITHUB_TOKEN"}


def test_splice_replaces_only_between_markers():
    original = f"head\n{mcp_sync.TOML_BEGIN}\nOLD\n{mcp_sync.TOML_END}\ntail\n"
    spliced = mcp_sync.splice(original, mcp_sync.TOML_BEGIN, mcp_sync.TOML_END, "NEW")
    assert spliced == f"head\n{mcp_sync.TOML_BEGIN}\nNEW\n{mcp_sync.TOML_END}\ntail\n"
    assert "head" in spliced and "tail" in spliced and "OLD" not in spliced
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/mcp_sync && python -m pytest test_mcp_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_sync'`.

- [ ] **Step 3: Write the generator**

```python
# tools/mcp_sync/mcp_sync.py
"""Generate OpenFang's tool [[mcp_servers]] block and Claude's .mcp.json
from servers.json (the single source of truth for generic MCP tools).

Pure stdlib, mirroring skills/_indexer.py's no-dependency style.

Usage:
    python mcp_sync.py --write     # write the generated blocks in place
    python mcp_sync.py --check     # exit 1 if files differ from the generation
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOML_BEGIN = "# >>> generated:tools (mcp_sync.py — do not edit by hand)"
TOML_END = "# <<< generated:tools"
JSON_BEGIN = "// >>> generated:tools"
JSON_END = "// <<< generated:tools"

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVERS_JSON = REPO_ROOT / "vibemind-os/coding-engine/mcp_plugins/servers/servers.json"
OPENFANG_TOML = REPO_ROOT / "vibemind-os/openfang/openfang.vibemind.toml.template"
MCP_JSON = REPO_ROOT / ".mcp.json"


def selected(registry: dict) -> list[dict]:
    """Active, global-scope servers in source order."""
    return [
        s for s in registry.get("servers", [])
        if s.get("active", False) and s.get("scope", "global") == "global"
    ]


def _toml_str_list(items: list[str]) -> str:
    return "[" + ", ".join(json.dumps(i) for i in items) + "]"


def render_toml(registry: dict) -> str:
    lines = [TOML_BEGIN]
    for s in selected(registry):
        lines.append("[[mcp_servers]]")
        lines.append(f'name = {json.dumps(s["name"])}')
        lines.append(f'timeout_secs = {int(s.get("read_timeout_seconds", 30))}')
        lines.append("[mcp_servers.transport]")
        lines.append('type = "stdio"')
        lines.append(f'command = {json.dumps(s["command"])}')
        lines.append(f'args = {_toml_str_list(s.get("args", []))}')
        env = s.get("env_vars") or {}
        if env:
            lines.append("[mcp_servers.transport.env]")
            for k, v in env.items():
                lines.append(f"{k} = {json.dumps(v)}")
        lines.append("")
    lines.append(TOML_END)
    return "\n".join(lines)


def render_mcp_json(registry: dict) -> str:
    servers = {}
    for s in selected(registry):
        entry = {"command": s["command"], "args": s.get("args", [])}
        if s.get("env_vars"):
            entry["env"] = s["env_vars"]
        servers[s["name"]] = entry
    return json.dumps({"mcpServers": servers}, indent=2)


def splice(text: str, begin: str, end: str, payload: str) -> str:
    if begin not in text or end not in text:
        raise ValueError(f"markers {begin!r}/{end!r} not found in target")
    head, _, rest = text.partition(begin)
    _, _, tail = rest.partition(end)
    return f"{head}{begin}\n{payload}\n{end}{tail}"


def _load() -> dict:
    return json.loads(SERVERS_JSON.read_text(encoding="utf-8"))


def write() -> None:
    reg = _load()
    toml = OPENFANG_TOML.read_text(encoding="utf-8")
    OPENFANG_TOML.write_text(
        splice(toml, TOML_BEGIN, TOML_END, render_toml(reg).split("\n", 1)[1].rsplit("\n", 1)[0]),
        encoding="utf-8")
    # .mcp.json: wrap the JSON object literal inside its own file (regenerated whole)
    MCP_JSON.write_text(render_mcp_json(reg) + "\n", encoding="utf-8")
    print("[mcp_sync] wrote OpenFang TOML block + .mcp.json")


def check() -> int:
    reg = _load()
    ok = True
    toml = OPENFANG_TOML.read_text(encoding="utf-8")
    expected = splice(toml, TOML_BEGIN, TOML_END,
                      render_toml(reg).split("\n", 1)[1].rsplit("\n", 1)[0])
    if toml != expected:
        print("[mcp_sync] DRIFT: openfang TOML out of sync"); ok = False
    if MCP_JSON.exists() and MCP_JSON.read_text(encoding="utf-8") != render_mcp_json(reg) + "\n":
        print("[mcp_sync] DRIFT: .mcp.json out of sync"); ok = False
    if ok:
        print("[mcp_sync] in sync")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        return check()
    if args.write:
        write(); return 0
    ap.print_help(); return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tools/mcp_sync && python -m pytest test_mcp_sync.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/mcp_sync/mcp_sync.py tools/mcp_sync/test_mcp_sync.py
git commit -m "feat(mcp): mcp_sync generator (servers.json -> OpenFang TOML + .mcp.json)"
```

---

### Task 3: Insert markers + generate + verify against live OpenFang

**Files:**
- Modify: `vibemind-os/openfang/openfang.vibemind.toml.template`
- Create/Modify: `.mcp.json`

- [ ] **Step 1: Add the marker region to the OpenFang TOML template**

Find the existing tool block (`name = "tavily"` … `name = "taskmanager"`, around lines 197–340). Replace those hand-maintained tool entries with the two marker lines (the generator fills between them). Leave the VibeMind-specific servers (`brain`, `vibemind-db`, `spaces-ideas`, `space-navigator`, `brain-bridge`) and the security/system blocks untouched, OUTSIDE the markers:

```toml
# >>> generated:tools (mcp_sync.py — do not edit by hand)
# <<< generated:tools
```

- [ ] **Step 2: Generate**

Run: `python tools/mcp_sync/mcp_sync.py --write`
Expected: `[mcp_sync] wrote OpenFang TOML block + .mcp.json`.

- [ ] **Step 3: Verify the generated TOML parses**

Run: `python -c "import tomllib; tomllib.load(open('vibemind-os/openfang/openfang.vibemind.toml.template','rb')); print('toml ok')"`
Expected: `toml ok`.

- [ ] **Step 4: Verify `--check` is green, then prove it catches drift**

Run: `python tools/mcp_sync/mcp_sync.py --check`
Expected: `[mcp_sync] in sync` (exit 0).
Then edit one server's `description` in `servers.json`, re-run `--check`, expect DRIFT + exit 1, then `--write` to restore green. Revert the description edit.

- [ ] **Step 5: LIVE verification (empirical — required, no assumptions)**

Copy the generated template to the live config and confirm OpenFang actually loads the tools (Ground-Truth, not "didn't throw"):

```bash
cp vibemind-os/openfang/openfang.vibemind.toml.template ~/.openfang/config.toml   # or the real live target
# restart OpenFang per its CLAUDE.md (taskkill openfang, start, sleep 6)
curl -s http://127.0.0.1:4200/api/health
curl -s http://127.0.0.1:4200/api/mcp/servers | python -c "import sys,json; d=json.load(sys.stdin); print(sorted(s['name'] for s in d))"
```
Expected: the generated tool names (docker, qdrant, redis, …) appear in the live MCP server list. If the env-table format is rejected by OpenFang's TOML parser, adjust `render_toml`'s env emit to match an existing env-using server and re-run from Step 2.

- [ ] **Step 6: Commit**

```bash
git add vibemind-os/openfang/openfang.vibemind.toml.template .mcp.json
git commit -m "feat(mcp): generate OpenFang tool block + .mcp.json from servers.json"
```

---

### Task 4: De-dup — delete the redundant `security/poc_*` tool-mirrors

**Files:**
- Delete: ~22 directories under `vibemind-os/security/`

- [ ] **Step 1: Confirm each target is a tool-mirror, not a defensive PoC**

The delete set (tool-mirrors that now live in `servers.json`):
`poc_filesystem, poc_github, poc_postgres, poc_qdrant, poc_supabase, poc_redis, poc_n8n, poc_playwright, poc_tavily, poc_context7, poc_brave_search, poc_fetch, poc_time, poc_memory, poc_supermemory, poc_taskmanager, poc_windows_core, poc_desktop, poc_grpc_host, poc_git, poc_fungus_mcp`.

The KEEP set (genuine security — never delete here):
`poc_network_monitor, poc_firewall, poc_event_log, poc_botnet_detector, poc_endpoint_hardening, poc_site_verifier, poc_vuln_scanner, poc_forensics, poc_canary, poc_red_blue, poc_os_shield, poc_alerter, poc_injection_chain, poc_captcha_eval, poc_nemoclaw, poc_claude_code, poc_chat_orchestrator, poc_automation_ui_bridge, poc_pc_monitor, poc_log_analyzer, poc_keycloak`.

Run (verify no in-repo code imports the delete set, excluding the dirs themselves):
`grep -rIl "security.poc_filesystem\|security/poc_filesystem" vibemind-os --include=*.py --include=*.toml --include=*.json | grep -v "security/poc_" || echo "no external refs"`
Expected: `no external refs` (repeat-spot-check 2–3 more from the delete set).

- [ ] **Step 2: Delete the tool-mirror dirs**

```bash
cd vibemind-os
git rm -r security/poc_filesystem security/poc_github security/poc_postgres \
  security/poc_qdrant security/poc_supabase security/poc_redis security/poc_n8n \
  security/poc_playwright security/poc_tavily security/poc_context7 \
  security/poc_brave_search security/poc_fetch security/poc_time security/poc_memory \
  security/poc_supermemory security/poc_taskmanager security/poc_windows_core \
  security/poc_desktop security/poc_grpc_host security/poc_git security/poc_fungus_mcp
```
Note: `security/` is a nested git repo — if `git rm` errors on the dir lock (Windows), use `git rm -r --cached <dirs>` then remove the working trees, mirroring the clawcode-removal pattern.

- [ ] **Step 3: Verify the security defensive PoCs + openfang wiring still intact**

Run: `ls vibemind-os/security | grep -c poc_` (expect the KEEP-set count, ~21) and
`grep -c "security/poc_" vibemind-os/openfang/openfang.vibemind.toml.template` (expect the 6 wired defensive ones unchanged).

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(security): remove 22 poc tool-mirrors (now sourced from servers.json)"
```

---

## Phase 2 — Prompt-Store (Supabase `agent_prompts` + Qdrant)

### Task 5: Supabase `agent_prompts` migration

**Files:**
- Create: `supabase/migrations/<timestamp>_agent_prompts.sql` (place per the repo's existing `supabase/migrations` convention — check a recent migration for the timestamp format)

- [ ] **Step 1: Write the migration SQL**

```sql
create table if not exists public.agent_prompts (
    id              uuid primary key default gen_random_uuid(),
    tool            text not null,              -- = servers.json key
    agent_name      text not null,              -- tool-<name>
    description     text not null,              -- for embedding
    trigger         text not null default '',   -- for embedding
    prompt_template text not null,              -- generic template with {slots}
    slots           jsonb not null default '{}'::jsonb,  -- {name:{type,source,required}}
    output_schema   jsonb not null default '{}'::jsonb,
    visibility      text[] not null default array['*'],
    confidence      real not null default 0.5,
    attempts        int  not null default 0,
    successes       int  not null default 0,
    last_adjusted   timestamptz,
    updated_at      timestamptz not null default now(),
    unique (tool)
);
create index if not exists agent_prompts_tool_idx on public.agent_prompts (tool);
```

- [ ] **Step 2: Apply + verify the table exists**

Apply via the repo's migration runner, then:
Run: `psql "$SUPABASE_DB_URL" -c "\d public.agent_prompts"`
Expected: the table with all columns listed.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/*_agent_prompts.sql
git commit -m "feat(prompts): supabase agent_prompts table"
```

---

### Task 6: `prompt_indexer.py` — Supabase rows → Qdrant (mirror of `_indexer.py`, TDD)

**Files:**
- Create: `tools/mcp_sync/prompt_indexer.py`
- Test: `tools/mcp_sync/test_prompt_indexer.py`

- [ ] **Step 1: Write the failing test (pure functions, no network)**

```python
# tools/mcp_sync/test_prompt_indexer.py
import prompt_indexer


ROW = {
    "id": "11111111-1111-1111-1111-111111111111",
    "tool": "docker", "agent_name": "tool-docker",
    "description": "Run and manage docker containers",
    "trigger": "deploy|container|image",
    "prompt_template": "Start a container from {image} named {name}",
    "slots": {"image": {"source": "kg", "required": True}},
}


def test_embedding_text_combines_desc_trigger_tool():
    txt = prompt_indexer.embedding_text(ROW)
    assert "Run and manage docker containers" in txt
    assert "deploy|container|image" in txt
    assert "docker" in txt


def test_point_id_is_stable_per_tool():
    a = prompt_indexer.point_id_for(ROW)
    b = prompt_indexer.point_id_for({**ROW, "description": "changed"})
    assert a == b  # stable on tool, not on description
    assert a != prompt_indexer.point_id_for({**ROW, "tool": "redis"})


def test_payload_carries_supabase_id_and_visibility():
    p = prompt_indexer.payload_for({**ROW, "visibility": ["brain", "*"]})
    assert p["supabase_id"] == ROW["id"]
    assert p["tool"] == "docker"
    assert p["visibility"] == ["brain", "*"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/mcp_sync && python -m pytest test_prompt_indexer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_indexer'`.

- [ ] **Step 3: Write the indexer (mirrors skills/_indexer.py exactly)**

```python
# tools/mcp_sync/prompt_indexer.py
"""Sync Supabase public.agent_prompts to the Qdrant collection
`vibemind_agent_prompts`. Direct mirror of skills/_indexer.py (same embed /
ensure_collection / upsert / search structure), source = Supabase instead of
SKILL.md.

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tools/mcp_sync && python -m pytest test_prompt_indexer.py -v`
Expected: 3 passed.

- [ ] **Step 5: Seed one row + live round-trip (empirical)**

Insert a `tool-docker` row into Supabase (the template above), then:
Run: `python tools/mcp_sync/prompt_indexer.py --rebuild && python tools/mcp_sync/prompt_indexer.py --search "deploy a container"`
Expected: the `docker` row comes back as the top hit (Ground-Truth: real Qdrant query, not "didn't error").

- [ ] **Step 6: Commit**

```bash
git add tools/mcp_sync/prompt_indexer.py tools/mcp_sync/test_prompt_indexer.py
git commit -m "feat(prompts): prompt_indexer (supabase agent_prompts -> qdrant)"
```

---

## Phases 3 & 4 — Follow-up plans (own brainstorming/plan pass)

Deliberately NOT expanded here: writing full TDD code for them requires verifying real OpenFang-agent-API and Brain `multihop_execute` internals first (per the project rule: verify empirically, don't fabricate). Each becomes its own spec→plan:

- **Phase 3 — Tool-Agents in the OpenFang hub.** Generate one `tool-<name>` agent per global server (system prompt = the `agent_prompts.prompt_template`), scoped to exactly its 1 MCP tool. Verify first: the live OpenFang agent-register API (POST agent → PUT tool-scope → restart; the PATCH-drops-system_prompt gotcha). Deliverable: a generator that turns each `agent_prompts` row + its `servers.json` entry into a registered, single-tool OpenFang agent.
- **Phase 4 — Brain Meta-Orchestrator.** A flag-gated resolver step in `multihop_execute`: semantic-search `vibemind_agent_prompts` → load template → resolve slots (`prompt → hop → config → kg`, with `ask` fallback, never guess) → render → dispatch to `tool-<name>` → Ground-Truth verify → write back confidence/attempts/successes. Verify first: the real `multihop_execute` + `kg_search` signatures and the executor-hook seam.

---

## Self-Review

- **Spec coverage:** §3 architecture EBENE-1 → Tasks 1–4; EBENE-2 → Tasks 5–6; §6 de-dup → Task 4; §7 security-separation → Task 4 KEEP-set + Task 1 scope; runtime (§3 LAUFZEIT, components C3/C6) → Phases 3–4 (explicitly deferred with verification gates). No silent gaps.
- **Placeholder scan:** every code step carries full code; no TBD/TODO inside active tasks. Phases 3–4 are scoped follow-up plans, not in-task placeholders.
- **Type consistency:** generator uses `selected()/render_toml()/render_mcp_json()/splice()` consistently across test and impl; indexer uses `embedding_text()/point_id_for()/payload_for()` consistently; `TOML_BEGIN/TOML_END` markers identical in code and Task 3.
