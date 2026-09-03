# Plan: Agent Lifecycle-Hooks (`pre`/`post`) für die Vibemind-Agentfarm

> Inspiriert von `ruvnet/agentic-flow` (`.claude/agents/*.md` mit `hooks.pre`/`hooks.post` Shell-Strings).
> Status: **PLAN — noch nicht umgesetzt.** Datum: 2026-06-09.

## Ziel (eine Zeile)

Ein Agent-Manifest soll deklarativ sagen können *"führe dieses Shell-Kommando
aus, bevor/nachdem ich laufe"* — statt Hook-Logik im Code zu verstreuen.
Beispiel: `coder`-Agent läuft → `post`-Hook ruft `lint`.

## Befund: Was schon da ist (verifiziert)

- **Rust hat das Hook-Konzept halb gebaut.** `openfang-types/src/agent.rs:97-109`
  definiert `enum HookEvent { BeforeToolCall, AfterToolCall, BeforePromptBuild,
  AgentLoopEnd }` — aber **NICHT mit `AgentManifest` verdrahtet** (kein
  `hooks`-Feld im Struct bei `agent.rs:426`).
- **Vier Agent-Formate existieren** (Brain-YAML, space_agent_registry.yml,
  OpenFang `agent.toml`, SKILL.md). Die OpenFang-TOML ist das reichhaltigste
  und der richtige Ort.
- **Kein einziges Format hat heute Lifecycle-Hooks.** (verifiziert)
- OpenFang ist **Rust** (14 crates). CLAUDE.md verlangt bei Rust-Änderungen
  `cargo build/test/clippy` + Live-Integration-Tests, und **"Don't touch openfang-cli"**.

## Entscheidung: Python-MCP-Schicht zuerst, nicht Rust

Zwei mögliche Orte:

| Ort | Aufwand | Trigger-Granularität |
|---|---|---|
| **Python MCP-Wrapper** (`openfang/mcp/openfang_agents_server.py`) | klein, kein Rebuild | nur **spawn-Zeitpunkt** (pre/post um den HTTP-POST) |
| **Rust-Kernel** (`agent.rs` + `kernel.rs` + Hook-Runner) | groß, Rebuild+Tests | echte Lifecycle-Events (vor/nach jedem Tool-Call, AgentLoopEnd) |

**Phase-1-Entscheidung: Python-MCP-Schicht.** Liefert 80% des Werts (pre/post
um Agent-Start) ohne Rust-Risiko. Rust-Wiring ist Phase 2, NUR wenn echte
per-tool-call-Hooks gebraucht werden.

> ⚠️ Einschränkung ehrlich benannt: Der Python-Hook feuert nur, wenn der Agent
> über `openfang_agent_spawn_from_*` (MCP) gestartet wird. Agents, die direkt
> über die OpenFang-HTTP-API oder beim Daemon-Boot geladen werden, lösen den
> Python-Hook NICHT aus. Für vollständige Abdeckung → Phase 2 (Rust).

---

## Phase 1 — Python-MCP-Hooks (umsetzbar, ~1 Sitzung)

### Manifest-Erweiterung (rein additiv, bricht nichts)

```toml
# agent.toml — NEUER optionaler Block
[hooks]
pre  = "echo 'spawning $AGENT_NAME'"      # läuft VOR dem Spawn-HTTP-POST
post = "python scripts/notify_telegram.py 'agent $AGENT_NAME up'"  # NACH erfolgreichem Spawn
```

Rust ignoriert unbekannte TOML-Keys nicht automatisch — ABER: `[hooks]` wird
nur vom Python-Wrapper aus dem rohen TOML-String gelesen, BEVOR er an Rust geht.
Prüfen: parst Rust `toml::from_str` mit `#[serde(default)]`-Struct streng oder
lenient? Wenn streng → Python muss den `[hooks]`-Block aus dem TOML-String
entfernen, bevor er weitergereicht wird. **TODO im Code verifizieren.**

### Code-Änderungen

**Datei:** `vibemind-os/openfang/mcp/openfang_agents_server.py`

1. Neue Helper:
   - `_extract_hooks(manifest_toml: str) -> dict` — parst `[hooks]` (tomllib),
     gibt `{"pre": str|None, "post": str|None}`.
   - `_strip_hooks(manifest_toml: str) -> str` — entfernt `[hooks]`-Block, falls
     Rust strikt parst (erst Verifikation, dann ggf. nutzen).
   - `_run_hook(cmd: str, env: dict) -> tuple[int, str]` — `subprocess.run` mit
     Timeout (z.B. 30s), `$AGENT_NAME` etc. via `env`. **Niemals shell=True mit
     ungefiltertem Input ohne bewusste Entscheidung** — Hooks kommen aus
     lokalen, vertrauenswürdigen agent.toml, aber dokumentieren.

2. In `openfang_agent_spawn_from_toml` (Zeile ~300) und
   `openfang_agent_spawn_from_template` (Zeile ~294):
   - `pre`-Hook ausführen → bei Exit≠0 **Spawn abbrechen** und Fehler
     zurückgeben (pre kann blocken, wie agentic-flow es vorsieht).
   - `_http("POST", "/api/agents", ...)`.
   - bei Erfolg `post`-Hook (best-effort, Exit-Code loggen, nicht blocken).
   - Hook-Output in die MCP-Antwort mit aufnehmen (Sichtbarkeit).
   - Für `spawn_from_template`: Template-TOML erst aus
     `~/.openfang/agents/{template}/agent.toml` lesen, um `[hooks]` zu finden.

### Verifikation Phase 1 (Pflicht vor "fertig")

1. Unit: `_extract_hooks` mit/ohne `[hooks]`, kaputtes TOML → kein Crash.
2. Live: Agent mit `pre = "echo HOOK_PRE > $TEMP/hooktest"` spawnen → Datei prüfen.
3. Live: `pre = "exit 1"` → Spawn wird abgebrochen, Agent erscheint NICHT in
   `/api/agents`.
4. Live: `post`-Hook feuert nach erfolgreichem Spawn (Telegram/echo verifizieren).

---

## Phase 2 — Rust-native Lifecycle-Hooks (optional, nur bei Bedarf)

Nur angehen, wenn per-tool-call- oder AgentLoopEnd-Hooks gebraucht werden
(Python kann das nicht — der Agent läuft im Rust-Kernel).

1. `AgentManifest` (agent.rs:426): Feld
   `#[serde(default)] pub hooks: HashMap<HookEvent, String>` ergänzen.
   → Default-Impl-Eintrag + serde nachziehen (CLAUDE.md-Gotcha).
2. Hook-Runner im Kernel/Runtime an den vorhandenen `HookEvent`-Punkten
   (`triggers.evaluate` bei `kernel.rs:1426` ist der Lifecycle-Hook-Einstieg).
3. `cargo build --workspace --lib && cargo test --workspace && cargo clippy
   --workspace --all-targets -- -D warnings`.
4. Live-Integration-Tests nach OpenFang-CLAUDE.md (Daemon neu bauen, spawnen,
   message senden, side-effects prüfen).
5. **openfang-cli NICHT anfassen.**

---

## Bewusst NICHT in diesem Plan

- Kein Import von agentic-flow als Dependency (Fragmentierung,
  `project_automation_ui_fragmentation`).
- Kein Übernehmen der 111 `.md`-Templates als Mechanik — höchstens einzelne
  Prompt-Texte als Steinbruch in bestehende `system_prompt`-Felder.
- Keine zweite Orchestrierungs-Engine.
