"""SoM Planner — claude-code Agent-Wrapper mit erzwungenem JSON-Output.

Eine Rolle pro Aufruf (env SOM_ROLE ∈ planner|executor|validator). Liest den
Prompt von stdin, ruft Claude CLI mit --json-schema (structured output) auf,
gibt reines JSON auf stdout.

Nutzt `claude -p --output-format json --json-schema <schema>` — die CLI
erzwingt + validiert die Struktur, kein fragiles Text-Parsen.

Env:
  SOM_ROLE          planner | executor | validator  (required)
  SOM_CLAUDE_BIN    Pfad zu claude.exe (default C:/Users/User/bin/claude.exe)
  SOM_MODEL         model alias (default: sonnet)
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Windows-stdout auf UTF-8 zwingen (sonst cp1252-Crash bei Umlauten/Pfeilen)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

_REPO = Path(__file__).resolve().parents[1]   # Vibemind_V1/
_PLANNER = _REPO / "vibemind-os" / "spaces" / "autogen" / "planner"

CLAUDE_BIN = os.environ.get("SOM_CLAUDE_BIN", r"C:/Users/User/bin/claude.exe")
MODEL = os.environ.get("SOM_MODEL", "sonnet")


def _load_schema(role: str) -> dict:
    """Pydantic-Schema → JSON-Schema für claude --json-schema."""
    sys.path.insert(0, str(_PLANNER / "_lib"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("som_schemas", _PLANNER / "_lib" / "schemas.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    model_cls = mod.ROLE_SCHEMA[role]
    return model_cls.model_json_schema()


def _load_prompt(role: str) -> str:
    return (_PLANNER / "prompts" / f"{role}.md").read_text(encoding="utf-8")


def _strip_fence(text: str) -> str:
    """Entfernt ```json ... ``` Markdown-Fences die Claude manchmal um JSON legt."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        # erste Zeile ist ```json o.ä., letzte ist ```
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _schema_hint(role: str) -> str:
    """Kompakte Schema-Beschreibung für den System-Prompt (claude --json-schema
    erzwingt das Format NICHT hart genug — wir packen das Schema in den Prompt
    und isolieren die Session, damit Claude nur denkt + JSON liefert)."""
    schema = _load_schema(role)
    props = schema.get("properties", {})
    return json.dumps({k: v.get("type", "object") for k, v in props.items()})


def _som_mcp_config() -> str:
    """MCP-Config die NUR den som-planner Server exponiert (strict-mcp-config
    ignoriert geerbte Server, damit der Agent nicht 'losarbeitet')."""
    server_py = str(_PLANNER / "mcp_server.py")
    # globaler Python hat mcp + yaml (venv312 nicht) — siehe Memory
    py = os.environ.get("SOM_MCP_PYTHON", "python")
    return json.dumps({
        "mcpServers": {
            "som": {
                "type": "stdio",
                "command": py,
                "args": [server_py],
            }
        }
    })


def run(role: str, user_input: str) -> dict:
    system_prompt = _load_prompt(role)
    hint = _schema_hint(role)
    run_id = os.environ.get("SOM_RUN_ID", "")
    max_turns = os.environ.get("SOM_MAX_TURNS", "12")

    # AKTIVE Society-of-Mind Agents (2026-06-01): der Agent beschafft DATEN SELBST
    # via MCP-Tools (think/data_read/data_list/capability_list/skill_search/
    # plan_read/plan_write), denkt, und schreibt den Plan. Mehrere Turns.
    # --strict-mcp-config + nur som-Server: der Agent kann NUR unsere Tools, nicht
    # Docker/etc. (sonst "arbeitet" er los). Tools der CLI selbst bleiben aus.
    # Ausgabe-Regel + Rollen im USER-INPUT (verifiziert: System-Prompt verliert).
    mcp_cfg = _som_mcp_config()
    composed_input = (
        "Du hast Tools (MCP-Server 'som'): think, data_read, data_list, "
        "capability_list, skill_search, plan_read, plan_write. NUTZE sie aktiv: "
        "beschaffe dir SELBST die Daten die du brauchst (data_read/data_list für "
        "vorliegende Akten, capability_list für Fähigkeiten, skill_search für "
        "benötigte Daten), denke mit think, und schreibe dein Ergebnis am Ende mit "
        f"plan_write(run_id='{run_id}', kind='<plan|exec|verdict>', data=<dein JSON>).\n\n"
        "Nimm NICHT an dass Daten fehlen — prüfe erst mit data_read/data_list ob sie "
        "vorliegen.\n\n"
        "Wenn du fertig bist, gib als finale Textantwort dein Ergebnis-JSON aus "
        "(erstes Zeichen `{`, letztes `}`, keine Prosa). "
        f"Erwartete Top-Level-Felder: {hint}\n\n"
        "ROLLE + REGELN:\n" + system_prompt + "\n\n"
        "INPUT:\n" + user_input
    )
    cmd = [
        CLAUDE_BIN,
        "-p",
        "--output-format", "json",
        "--model", MODEL,
        "--tools", "",                       # keine BUILT-IN Tools (nur MCP-som)
        "--strict-mcp-config",               # nur unsere MCP-Config, keine geerbten
        "--mcp-config", mcp_cfg,             # som-planner Tools
        "--permission-mode", "bypassPermissions",  # Tools ohne Nachfrage (headless)
        "--max-turns", str(max_turns),       # mehrere Turns für Tool-Beschaffung
    ]
    # Loop-Guard: CLAUDECODE/CLAUDE_CODE_* aus Env entfernen (verschachtelte Session)
    child_env = {k: v for k, v in os.environ.items()
                 if not k.startswith("CLAUDECODE") and not k.startswith("CLAUDE_CODE")}
    # Neutrales CWD: kein .claude-Projektkontext (sonst werden Skills/MCP geerbt)
    import tempfile
    cwd = tempfile.mkdtemp(prefix="som_")

    try:
        proc = subprocess.run(
            cmd,
            input=composed_input,
            capture_output=True,
            text=True,
            encoding="utf-8",
            # INNERER claude-CLI-Timeout: eigene Var SOM_CLAUDE_TIMEOUT_S, default
            # 180s. MUSS < SOM_TIMEOUT_S (äußerer subprocess-Timeout in som_core,
            # default 240s) sein, sonst feuert der äußere zuerst und maskiert den
            # claude-Timeout als "non-JSON" statt sauberer Fehlermeldung.
            timeout=int(os.environ.get("SOM_CLAUDE_TIMEOUT_S", "180")),
            env=child_env,
            cwd=cwd,
        )
    finally:
        try:
            shutil.rmtree(cwd, ignore_errors=True)
        except Exception:  # noqa: BLE001
            pass

    if proc.returncode != 0:
        return {"error": f"claude exit {proc.returncode}", "stderr": (proc.stderr or "")[:500]}

    raw = (proc.stdout or "").strip()
    try:
        envelope = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {"error": "claude returned non-JSON envelope", "raw": raw[:500]}

    if envelope.get("subtype") == "error_max_turns":
        return {"error": "max_turns hit (claude tried to use tools)", "raw": raw[:300]}

    result = envelope.get("result", envelope)
    if isinstance(result, str):
        result = _strip_fence(result)
        try:
            result = json.loads(result)
        except (json.JSONDecodeError, ValueError):
            return {"error": "result field not JSON", "raw": result[:500]}
    return result


def main() -> int:
    role = os.environ.get("SOM_ROLE", "").strip().lower()
    if role not in ("planner", "executor", "validator"):
        sys.stdout.write(json.dumps({"error": f"invalid SOM_ROLE={role!r}"}) + "\n")
        return 2

    user_input = sys.stdin.read().strip()
    if not user_input:
        sys.stdout.write(json.dumps({"error": "empty stdin"}) + "\n")
        return 2

    try:
        result = run(role, user_input)
    except subprocess.TimeoutExpired:
        result = {"error": "claude timeout"}
    except Exception as e:  # noqa: BLE001
        result = {"error": f"{type(e).__name__}: {e}"}

    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())
