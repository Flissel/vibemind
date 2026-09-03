# 02 — Repositorystruktur

Bewertung pro Verzeichnis: **Zweck · Verantwortlichkeit · Abhängigkeiten · Erweiterbarkeit · technische Qualität**.
Qualitätsnote: A (vorbildlich) … E (Schuld).

## Übersicht

```
openworker/
├── coworker/          Python-Backend — die gesamte Runtime          (~25.000 LOC)
│   ├── agents/        Personas als Runtime-Objekte
│   ├── automation/    Cron-Scheduler + ScheduledTask
│   ├── connectors/    33 Connectoren, Gateway, OAuth, Relay        (~12.000 LOC)
│   ├── mcp/           MCP-Client (stdio + http) + OAuth
│   ├── memory/        SQLite-Memory + Tools
│   ├── personas/      Manifest-Parser + Registry (Markdown+YAML)
│   ├── providers/     7 Provider + Router + Capability-Matrix
│   ├── server/        FastAPI-App + SessionManager
│   ├── skills/        SKILL.md-Loader (Anthropic-Format)
│   ├── testing/       FakeSlack-Harness
│   ├── tools/         Lokale Tools (files, shell, git, search, todo, plan, ask, subagent)
│   ├── tui/           Textual-TUI
│   └── web/           Websuche + Fetch
├── surfaces/gui/      React 18 + Vite + Tailwind + Tauri 2          (~12.000 LOC)
│   ├── src/           49 Komponenten, api.ts (1.864 LOC), App.tsx (1.732 LOC)
│   ├── src-tauri/     Rust-Shell: Server-Supervisor + Dictation-Commands
│   ├── e2e/           55 hermetische Playwright-Specs
│   └── e2e-live/      7 Specs gegen echten Server
├── stt/               Rust-Crate `ocw-stt` — Whisper-Diktat          (666 LOC)
├── packaging/         DMG/MSI-Build, PyInstaller-Spec, Update-Manifest
├── tests/             82 Dateien, 881 Testfunktionen
├── ui-mocks/          4 statische HTML-Mockups
└── docs/              config.example.toml + 1 PNG   ← siehe unten
```

---

## `coworker/` — Backend-Wurzel

**Zweck:** Alles außer Darstellung. **Verantwortlichkeit:** Runtime, Persistenz,
Integrationen, Server.

**Bemerkenswert:** Es gibt **keinen** DI-Container, **kein** Framework über FastAPI
hinaus, **keine** Plugin-Loader-Magie. Abhängigkeiten werden als Konstruktorparameter
durchgereicht — `build_engine()` in `agent.py:109-136` nimmt 27 (!) Keyword-Argumente.
Das ist ehrlich und testbar, aber ein Signal, dass die Komposition an ihre Grenze kommt.

**Zyklen-Vermeidung per Lazy-Import:** `agents/registry.py:20`, `permissions.py:72`,
`agent.py:193`. Funktioniert, ist aber ein Symptom zu enger Kopplung — siehe [10](10-backend.md).

**Note: B.**

### `coworker/tools/` — die lokalen Tools

| Datei | LOC | Zweck | Bewertung |
|---|---|---|---|
| `shell.py` | 589 | Persistente Shell (bash/PowerShell), Hintergrund-Tasks, Interrupt | **A** — siehe unten |
| `files.py` | ~200 | `read_file` mit Zeilennummern + Fenstern | **A** |
| `search.py` | ~150 | `grep` (ripgrep-artig) | B |
| `git.py` | ~120 | `git_log` etc. | B |
| `subagent.py` | 139 | `explore` — read-only Subagent | **A-** |
| `todo.py` | ~150 | Todo-Liste (rendert das Progress-Panel) | B |
| `plan.py` | ~80 | `propose_plan` | C — reines Prompt-Konstrukt |
| `ask.py` | ~60 | `ask_user` | B |
| `registry.py` | 72 | ToolRegistry | B+ — minimal, aber flach ([04](04-tool-system.md#45-die-flat-registry-falle)) |

**`shell.py` ist die technisch beste Datei des Repos.** Sie löst ein Problem, das die
meisten Agent-Frameworks falsch lösen:

- **Persistente Shell statt `subprocess.run` pro Call** — `cd`, `export`, aktivierte
  venvs überleben zwischen Tool-Calls (`shell.py:1-21`).
- **Marker-Protokoll** für Exit-Code + CWD: nach jedem Kommando wird ein
  `printf "\n%s %s %s\n" "$MARKER" "$?" "$PWD"` angehängt (`shell.py:354-366`).
  Auf Windows die PowerShell-Entsprechung mit `$?`/`$LASTEXITCODE`.
- **Self-Healing:** Timeout → SIGINT an den Vordergrund-Child, 3 s Gnadenfrist auf den
  Marker zur Resynchronisation, sonst harter Kill + Respawn im letzten CWD
  (`shell.py:243-298`). Auf Windows: kein Resync-Versuch, weil PowerShell keine
  verlässliche „interrupt one command"-Primitive hat — bewusst dokumentiert.
- **Output-Trunkierung behält den *Tail***, weil Build-/Test-Verdikte am Ende stehen
  (`shell.py:287-290`). Kleines Detail, große Wirkung auf Agent-Qualität.
- **Hintergrund-Tasks** laufen als *eigener* detachter Prozess, nicht in der
  persistenten Shell — damit ein Dev-Server weiterläuft, während die Session arbeitet.

**Für VibeMind direkt übernehmbar** — siehe [ADR-0006](adr/ADR-0006-shell-executor.md).

**Note: A.**

### `coworker/connectors/` — der Problembereich

| Datei | LOC | |
|---|---|---|
| `integration_tools.py` | **4.892** | Alle 159 Connector-Tools in *einer* Datei |
| `descriptors.py` | 1.470 | Setup-Wizard-Daten pro Connector |
| `tool_defs.py` | 1.203 | Tool-Katalog + Enablement-Policy |
| `email_tools.py` | 843 | |
| `browser_automation.py` | 577 | Playwright |
| `relay_client.py` | 531 | Managed-Slack-Relay (WebSocket) |
| … 21 weitere | | |

**Was gut ist:** Das *Datenmodell* ist richtig gedacht. `ConnectorDescriptor`
(`descriptors.py:44-60`) macht „einen Connector hinzufügen" zu **Daten statt UI-Code**:
Auth-Methode, Felder zum Einfügen, Schritt-für-Schritt-Anleitung, `validate`-Callable,
das den Token per echtem API-Call prüft und die Bot-Identität zurückgibt. Der
`ConnectorToolDef` (`tool_defs.py:11-25`) deklariert pro Tool `kind` (read/write) und
`target_arg` — das Argument, das das externe Objekt benennt. Genau dieses `target_arg`
macht Standing Rules sicher (siehe [08](08-security-risikoanalyse.md#84-standing-rules)).

**Was schlecht ist:** Die *Implementierung* ist ein Monolith. 4.892 Zeilen in einer
Datei, 33 Dienste ohne Modulgrenze. Kein Connector-Plugin-Interface, keine dynamische
Registrierung, kein Third-Party-Pfad — bewusst so gewollt: `catalog.py:11-13` sagt
explizit „**The catalog is platform-owned and closed**: third parties get breadth from
us adding vetted capabilities here and from MCP, never by adding entries."

Das ist eine **legitime Produktentscheidung** (Kuratierung als Sicherheitsmodell),
aber sie ist für VibeMind das Gegenteil dessen, was gebraucht wird.

**Note: C** (Datenmodell A, Implementierung D).

### `coworker/mcp/` — MCP-Client

4 Dateien, ~600 LOC. Eigener async Layer über dem offiziellen `mcp`-SDK.

**Die kluge Entscheidung** (`mcp/client.py:1-11`): Jeder Server läuft in einer
**dedizierten asyncio-Task**, die Transport und `ClientSession` öffnet, offen hält und
**in derselben Task** wieder schließt. Grund: die anyio-Cancel-Scopes des SDK müssen
auf *einer* Task betreten und verlassen werden. Kein `nest_asyncio`, kein zweiter
Event-Loop. Das ist eine Falle, in die viele MCP-Integrationen tappen — hier korrekt gelöst.

Tool-Aufrufe brücken vom Sync-Registry-Kontext per `run_coroutine_threadsafe` zurück
(`mcp/tools.py:71-73`), Timeout 120 s.

**Schwächen:**
- MCP-Tools bekommen pauschal `risk_level="medium"` und `requires_approval` aus der
  Server-Config (`mcp/tools.py:82-88`) — **keine** Unterscheidung read/write pro Tool.
  Der Kommentar in `risk.py:35` gibt zu, dass User-Overrides „mainly to relax MCP's
  conservative default" existieren. Das ist ein Workaround, keine Lösung.
- Nur Tools. **Keine** MCP-Resources, **keine** Prompts, **keine** Sampling-Unterstützung.
- Namensraum-Kollision möglich: `tool_name()` schneidet bei 64 Zeichen hart ab
  (`mcp/tools.py:26-31`) — zwei lange Servernamen können auf denselben Tool-Namen kollidieren
  und sich in der flachen Registry gegenseitig überschreiben (`registry.py:45-46`
  überschreibt kommentarlos). **Realer Bug bei vielen MCP-Servern.**

**Note: B+.**

### `coworker/providers/` — Modellzugriff

7 Provider (OpenAI, Anthropic, Gemini, Bedrock, Vertex, + OpenAI-kompatible Resells),
`router.py` (119 LOC) dispatcht über den `provider:`-Präfix des Modell-Strings.

**Elegant:** Der Router *ist* selbst ein `ProviderClient` — der Manager reicht genau
einen Provider an alle Engines, und jeder `complete()/stream()`-Aufruf routet sich
selbst, weil der Modellstring pro Call mitkommt (`router.py:1-11`). Modellwechsel
mitten in der Session braucht keinen Rebuild.

**Sauber gelöste Kanten:**
- `_bare()` strippt nur *bekannte* Präfixe, damit `qwen2.5-coder:32b` (Versions-Tag,
  kein Präfix) nicht zerlegt wird (`router.py:70-80`).
- Capability-Degradation: Modelle ohne Vision bekommen Text-Platzhalter statt
  abgelehnter Payloads; Modelle ohne native PDF-Unterstützung bekommen lokal
  extrahierten Text oder Seitenbilder — **pro Call neu entschieden**, nie in der
  Historie persistiert (`engine.py:904-961`). Dadurch ist der Modellwechsel wirklich
  verlustfrei reversibel.

**Schwäche:** Kein Retry/Backoff gegen Rate-Limits, kein Circuit Breaker, kein
Failover. `_param_fix_retry` behebt nur Parameterfehler (`openai_provider.py:206-214`).

**Note: A-.**

### `coworker/server/` — Control Plane

| Datei | LOC | Note |
|---|---|---|
| `app.py` | 1.968 | B — 120+ Routen, aber flach und lesbar |
| `manager.py` | **3.766** | **D** — God-Object, ~150 Methoden |
| `run.py` | ~120 | B |

`manager.py` besitzt: Engines, Provider, Secrets, Conversations, Memory, Inbox,
Inbox-Routing, Unattended-Registry, Audit, Automation-Store, Scheduler, Gateway,
MCP-Manager, Personas, Skills, Workspace-Trust, Subscriptions, Channel-Buffer,
Mentions, Wake-Store, Parked-Store, Unrouted-Store, Connections.
**Alles.** Das ist der klassische Punkt, an dem ein Projekt Services extrahieren muss.

Details: [10 — Backend](10-backend.md).

### `coworker/personas/` + `skills/` + `catalog.py` — die Erweiterungsschicht

Das ist die konzeptionell interessanteste Ecke:

- **Skill** = Anthropic-`SKILL.md`-Format (YAML-Frontmatter + Markdown), **Progressive
  Disclosure**: beim Sessionstart wandert nur der *Katalog* (Name + Beschreibung) in den
  Kontext, der Rumpf wird per `load_skill(name)` on demand geladen (`skills/base.py:1-8`).
- **Persona** = `persona ⊇ skill` (`personas/manifest.py:3-5`) — dasselbe
  Frontmatter-Markdown-Format, aber mit strukturierten Feldern: `family`, `tools`
  (Capability-IDs), `messaging`, `connectors`, `default_permission_mode`,
  `recommended_models`, `skills`, `mcp`, `recommends`.
- **Capability-Katalog** (`catalog.py`) = die stabile `id → Tool-Bundle`-Schicht, auf
  die Personas verweisen. Mit `requires` (Kontext-Voraussetzungen) und `risk`
  (für den Install-Consent-Screen).

**Das ist ein sehr gutes Design** und für VibeMind direkt adaptierbar
([ADR-0009](adr/ADR-0009-skill-persona-format.md)).

**Ein Fehler darin:** `Skill.allowed_tools` wird geparst (`skills/base.py:73-80`),
aber **nirgends durchgesetzt**. Volltextsuche über `allowed_tools` in `.py` liefert nur
Vorkommen in `automation/models.py` (dort geht es um Standing Rules, ein anderes
Konzept) — kein Enforcement-Pfad im Skill-Kontext. Ein Skill kann also jedes Tool
aufrufen, unabhängig von seiner Deklaration. **Falsches Sicherheitsgefühl.**

**Note: A-** (mit dem genannten Defekt).

---

## `surfaces/gui/`

React 18, Vite 5, Tailwind 3, TypeScript 5.5, Tauri 2. Bewusst **ohne** Redux/Zustand/
Jotai/React-Query — reines `useState`/`useEffect` (78 Hook-Aufrufe in `App.tsx` allein).

- `api.ts` (1.864 LOC) — dünner REST/WS-Client, kein Codegen, keine Typ-Ableitung aus
  dem Backend (Typen in `types.ts` von Hand gepflegt → Driftrisiko).
- `App.tsx` (1.732 LOC) — der zentrale Zustandsknoten.
- 49 Komponenten, davon 14 Connector-spezifisch.
- **55 hermetische E2E-Specs** mit gemocktem `/v1` + WS — laufen ohne Modell und ohne
  Netz in CI. Das ist überdurchschnittlich diszipliniert.

Details: [09 — Frontend](09-frontend.md). **Note: B.**

---

## `stt/`

Eigenständige Rust-Crate `ocw-stt`, bewusst **ohne** Tauri-/UI-/Clipboard-Abhängigkeit
(`stt/src/lib.rs:1-5`). `cpal` für Mikrofon, `whisper-rs` 0.16, `ureq` für den
Modell-Download, `sha2` für Verifikation.

Handwerklich gut: atomarer Download nach `.part` mit SHA-256-Prüfung vor dem Rename
(`lib.rs:212-228`), Per-Read-Timeout statt Gesamt-Timeout (damit Cancel responsiv bleibt),
CPAL-Stream auf einem dedizierten Owner-Thread, weil er `!Send` ist (`lib.rs:88-90`).

Funktional aber: **Push-to-Talk-Diktat, Whisper `base.en`, Englisch, Batch.**
Details: [05](05-voice-pipeline.md). **Note: B+ handwerklich / E für den Zweck „Voice-first OS".**

---

## `tests/`

881 Testfunktionen in 82 Dateien. `pytest-asyncio` im `auto`-Modus.
Abdeckungsschwerpunkte lesen sich wie eine Liste realer Produktions-Incidents:
`test_durable_resume.py`, `test_engine_stop.py`, `test_slack_approval_owners.py`,
`test_standing_approvals.py`, `test_risk_overrides.py`, `test_wake_resume.py`,
`test_permissions_risk.py`, `test_connectors_allowlist.py`.

Dazu ein **FakeSlack-Harness** (`coworker/testing/fake_slack/`), der den echten
slack-bolt-Handler in-process treibt — kein Netz, kein Mock-Framework-Zauber.

**Note: A-.** Das ist die zweitstärkste Eigenschaft des Repos nach der Engine.

**Lücke in CI** (`.github/workflows/ci.yml`): nur `pytest`, `vitest`, `playwright`.
**Kein** Linter (`ruff`), **kein** Typcheck (`mypy`), **kein** `tsc --noEmit`
(`npm test` ist nur vitest, `npm run build` läuft nicht in CI), **keine** Rust-Tests,
**kein** Dependency-/Secret-Scan.

---

## `docs/` — der Elefant

`docs/` enthält genau **zwei** Dateien: `config.example.toml` und `assets/how-it-works.png`.

Der Code referenziert jedoch:

| Referenz | Fundstelle |
|---|---|
| `docs/AUTOMATION-SCHEDULING.md` | `automation/models.py:2` |
| `platform/docs/PERSONAS.md` | `personas/__init__.py:6` |
| `platform/docs/FAKE-SLACK-SPEC.md` | `connectors/adapters.py:197`, `senders.py:26`, `testing/fake_slack/*`, `tests/conftest.py:6` |
| `PERMISSIONS-AND-INBOX.md` | `catalog.py:13` |
| `UX-DECISIONS §16/§25/§30/§33/§34/§36` | quer durch `engine.py`, `permissions.py`, `tool_defs.py`, `browser_automation.py`, `streamGate.ts` |

**Keine davon existiert im Repository.** Der Präfix `platform/` verrät, dass dies ein
Teil-Export eines internen Monorepos ist. Die README-Zeile
„`docs/` | Design specs and decision logs" ist damit **faktisch falsch**.

**Konsequenz für VibeMind:** Die *Begründungen* hinter den interessantesten
Entscheidungen (§25 Standing Rules, §33 Stream-Gating, §36 Tool-Kind-Vorrang) sind
**nicht** verfügbar. Ich habe sie aus dem Code rekonstruiert und markiere jede solche
Stelle in dieser Analyse als *rekonstruiert*, nicht als *belegt*.

**Note: E.**

---

## `packaging/`, `ui-mocks/`

`packaging/` — DMG-Build (macOS, signiert+notarisiert), Windows-PS1 (nicht signiert,
laut README „signing is in progress"), PyInstaller-Spec, Auto-Update-Manifest.
Solide, unspektakulär. **Note: B.**

`ui-mocks/` — 4 statische HTML-Dateien (919 + 636 + 2 kleinere LOC), u. a.
`voice-input-composer-states.html`. Design-Artefakte im Repo. Harmlos, aber
sie gehören nicht in ein `main`. **Note: C.**

---

## Zusammenfassende Bewertungstabelle

| Verzeichnis | Zweck erfüllt | Erweiterbar | Qualität | Für VibeMind |
|---|---|---|---|---|
| `coworker/tools/shell.py` | ✅ | ✅ Executor-ABC | **A** | **Direkt übernehmen** |
| `coworker/engine.py` | ✅ | ⚠️ monolithisch | **A** | **Semantik übernehmen** |
| `coworker/permissions.py` + `risk.py` | ✅ | ✅ Overrides | **A** | **Direkt übernehmen** |
| `coworker/inbox.py` + Durable Resume | ✅ | ✅ | **A** | **Direkt übernehmen** |
| `coworker/personas/` + `skills/` + `catalog.py` | ✅ | ✅ | **A-** | **Übernehmen + erweitern** |
| `coworker/providers/` | ✅ | ✅ Descriptor | **A-** | Konzept übernehmen |
| `coworker/mcp/` | ✅ | ⚠️ nur Tools | **B+** | Übernehmen + erweitern |
| `tests/` | ✅ | — | **A-** | Methodik übernehmen |
| `surfaces/gui/` | ✅ | ⚠️ kein State-Mgmt | **B** | Nicht übernehmen |
| `stt/` | ⚠️ nur Diktat | ❌ | **B+/E** | **Nicht übernehmen** |
| `coworker/memory/` | ⚠️ trivial | ✅ ABC | **C** | **Neu bauen** |
| `coworker/connectors/` | ✅ | ❌ geschlossen | **C** | **Nicht übernehmen** |
| `coworker/server/manager.py` | ✅ | ❌ | **D** | **Nicht übernehmen** |
| `docs/` | ❌ | — | **E** | — |

---

**Weiter:** [03 — Agent Runtime](03-agent-runtime.md)
