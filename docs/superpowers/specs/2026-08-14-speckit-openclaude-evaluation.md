# Evaluation: github/spec-kit für OpenClaude und den VibeMind-Coding-Space

**Datum:** 2026-08-14
**Session:** `task-coding-0003-speckit-openclaude-evaluation-v1` (Parent-Cockpit: `cockpit-coding`)
**Authority:** direkte User-Anweisung, Referenz `claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-14T11:08:00Z`
**Status:** Evaluationsergebnis mit Empfehlung; ändert keinen Vertrag, keinen Code, keine Pins.

## 0. Quellenlage und Ehrlichkeitsregel

Alle Aussagen dieses Dokuments sind wie folgt klassifiziert:

- **statisch quellcode-verifiziert** — aus einem realen, pin-exakten Checkout gelesen:
  - Superproject `Flissel/Vibemind_V1` @ `061feea` (`origin/master`),
  - Submodul `vibemind-os` @ `a92ccd3114a25f5bfd7b1a878ba68cff3e225895` (Gitlink-Pin, per `git submodule update --init` nach `docs/runbooks/submodule-checkout-workflow.md`),
  - Nested-Submodul `openclaude` @ `20d570b33ed627d5ccb8ae75ac380006bcd78616` — exakt der Manifest-Pin (`repo-manifest.yaml:62-74`),
  - Nested-Submodul `coding-engine` @ `be1994b47fe8b28acbd122b5ea2d3ab8ba1788f7` — exakt der Manifest-Pin (`repo-manifest.yaml:36-48`),
  - `github/spec-kit` @ `83883a2` (frischer Clone von `https://github.com/github/spec-kit`, außerhalb der VibeMind-Repos, keine Installation).
- **statisch dokumentbasiert** — aus committeten Docs/Registry-Katalogen (`docs/SPACES.md`, `docs/contracts/openfang-mcp-authority-v1.md`), nicht gegen weitere Submodule (z. B. `voice`, `openfang`) nachgeprüft; diese blieben uninitialisiert.
- **vermutet / nicht verifiziert** — explizit so markiert. Es gibt in diesem Dokument **keine** Runtime- oder Live-Claims; nichts wurde gestartet, installiert oder registriert.

**Governance-Lücke (dokumentiert, nicht blockierend):** Der im Auftrag benannte Session-Request `docs/governance/session-requests/task-coding-0003-speckit-openclaude-evaluation-v1.json` existiert weder auf `origin/master` noch auf irgendeinem Remote-Branch; auch Queue (`session-request-queue-v1.md`), Next-Task-Register und `WORKBOARD.md` kennen `task-coding-0003` nicht. Diese Session arbeitet daher allein auf der direkten User-Anweisung (Referenz oben). Ein `session validate`/`pr check`-Gate gegen den Request war nicht möglich; der Orchestrator sollte den Request nachreichen oder die Admission im Ledger nachdokumentieren.

## 1. Istbild OpenClaude (quellcode-verifiziert @ `20d570b`)

### 1.1 Was OpenClaude ist

OpenClaude ist ein **vollständiger Fork des geleakten Claude-Code-Quellcodes** mit einem OpenAI-kompatiblen Provider-Shim: „OpenClaude is a fork of the Claude Code source leak … We added an OpenAI-compatible provider shim" (`openclaude/README.md:5`). Paket `@gitlawb/openclaude` v0.1.6, MIT-ähnlich lizenziert laut `package.json` (`"license": "MIT"`). Es ist damit **kein Orchestrierungs-Framework, sondern ein interaktiver Coding-Agent (CLI)** mit allen Claude-Code-Mechaniken: Tools (bash, read/write/edit, grep, glob), Agents/Tasks, MCP (`README.md:7`), Slash-Commands (`src/commands/` mit ~100 eingebauten Commands), Skills (`src/skills/loadSkillsDir.ts`) und Custom-Command-/Skill-Discovery über `.claude/`-Verzeichnisse (`src/utils/markdownConfigLoader.ts:30,33` — Subdirs `commands` und `skills`; Discovery von cwd bis Git-Root, `markdownConfigLoader.ts:224-330`).

Provider-Seite: `smart_router.py` ist ein reiner **Provider-Router** (Latenz/Kosten/Health-Scoring über OpenAI-kompatible Endpoints, `smart_router.py:1-25`) — keine Task- oder Planungsschicht.

### 1.2 Die Service-Oberfläche (`serve.ts`) — der eigentliche Integrationspunkt heute

`serve.ts` exponiert OpenClaude als HTTP-Dienst auf Port 8091 mit genau drei Endpoints: `POST /v1/chat/completions`, `GET /health`, `GET /config` (`serve.ts:1-15`). Der Completions-Endpoint:

- baut aus den Messages einen **einzigen Prompt-String** (`serve.ts:77-89`),
- spawnt **pro Request einen frischen CLI-Prozess** im One-Shot-Print-Modus: `dist/cli.mjs --dangerously-skip-permissions --output-format text -p <prompt>` (`serve.ts:92-98`),
- gibt stdout als eine OpenAI-Completion zurück (`serve.ts:146-167`).

Konsequenzen (statisch belegt):

1. **Kein Sessionzustand, kein Multi-Turn:** jede Anfrage ist ein neuer Prozess; es gibt keine Konversations- oder Artefakt-Kontinuität auf Service-Ebene.
2. **`agent_role` wird angenommen, aber ignoriert:** das Feld existiert im Request-Interface (`serve.ts:29`), wird im gesamten File aber nie gelesen. Die Rollen-Bindung (E1) findet hier heute schlicht nicht statt.
3. **Keine Approval-/Cost-/Evidence-Mechanik:** `--dangerously-skip-permissions` schaltet die Claude-Code-eigene Permission-Schicht ab; Kosten werden als grobe Schätzung zurückgegeben (`serve.ts:160-164`: `prompt.length / 4`, `wordCount * 2` — keine echten Token-Zahlen).
4. Container-seitig läuft der Dienst als Nicht-Root-User `bun` mit Arbeitsvolume `/workspace` (`openclaude/Dockerfile:36-47`), Secrets via Docker-Secrets (`docker-entrypoint.sh`).

### 1.3 Wie OpenClaude heute im Coding-Space hängt (quellcode-verifiziert @ coding-engine `be1994b`)

Die coding-engine deklariert den Dienst als `openclaude-service` im Compose (`coding-engine/docker-compose.yml:309-337`): Build-Context `../openclaude`, Port 8091, Provider OpenRouter (`OPENAI_BASE_URL=https://openrouter.ai/api/v1`, Default-Modell `qwen/qwen3.6-plus-preview:free`), Egress nur über `egress-proxy`, Volume `./Data/generated:/workspace`. Die API bekommt `OPENCLAUDE_URL=http://openclaude-service:8091` (`docker-compose.yml:71`).

Der einzige Aufrufer im Engine-Code ist `ClaudeCodeTool` (`src/tools/claude_code_tool.py`):

- **Backend-Kette** (Phase 11.W): OpenClaude-HTTP-Router zuerst, dann Kilo → OpenRouter → Claude Agent SDK → Claude CLI als Fallbacks (`claude_code_tool.py:1232-1268`); `_detect_router_mode()` probt `OPENCLAUDE_URL/health` und macht OpenClaude bei Erfolg zum Primär-Backend (`claude_code_tool.py:1411-1443`).
- **Aufrufform:** genau ein System-Prompt „You are a code generation assistant … output ```filepath: <path>```" plus User-Prompt, single-shot, 300 s Timeout (`claude_code_tool.py:1489-1530`). Die Engine **parst die Dateien selbst aus dem Antworttext und schreibt sie selbst auf Platte** (`claude_code_tool.py:1575-1593`) — sie nutzt OpenClaudes Datei-Tools über diesen Pfad gar nicht.
- **`agent_role` wird mitgesendet** (`claude_code_tool.py:1519`), mit dem dokumentierten Wissen, dass der OpenClaude-Wrapper es ignoriert (Kommentar `claude_code_tool.py:1496-1498`).
- Quota-Fehler (402/429) werden als `LLMQuotaExhausted` eskaliert, Task-Rollback auf PENDING, **kein Auto-Fallback auf ein anderes LLM** (`claude_code_tool.py:199-213, 1542-1552`).

### 1.4 Die Planungsschicht liegt in der coding-engine, nicht in OpenClaude

Die coding-engine besitzt bereits eine eigene, mehrstufige Spec→Plan→Tasks-Kette:

- **Spec-Eingang:** `POST /api/jobs` (`src/api/routes/jobs.py:66`) nimmt Job-Spezifikationen an; `spec_adapter.py` normalisiert vier Formate (`SpecFormat`: `DOCUMENTATION`-Verzeichnis mit `MASTER_DOCUMENT.md`, `RICH_BILLING`, `LEGACY_TECHSTACK`, `SIMPLE`; `src/engine/spec_adapter.py:23-28`), `spec_parser.py` parst Spezifikations-Artefakte in Dataclasses (`src/engine/spec_parser.py:1-9`).
- **Planung:** `planning_engine.py` erzeugt aus Task-Slices Execution-Batches mit Parallelitäts-Markierung (`src/engine/planning_engine.py:1-40`), flankiert von `slicer.py`, `execution_plan.py`, `dag_parser.py`, `master_orchestrator.py`.
- **Ausführung:** Worker rufen `ClaudeCodeTool.execute()` mit Agent-Typ-Profilen und angereichertem Kontext (CLAUDE.md, DocumentRegistry-Reports, Supermemory, Fungus/Qdrant, Redis-Streams; `claude_code_tool.py:80-88, 892-1024`).

**Fazit Istbild:** OpenClaude ist heute ein **stateless Text-Completion-Backend** am Ende der Kette. Planung, Task-Zerlegung, Datei-Schreiben und Verifikation liegen vollständig in der coding-engine. Eine „OpenClaude-Planungsschicht" existiert nicht — die Claude-Code-Fähigkeiten (Tools, Commands, Skills) sind im Fork vorhanden, werden über den Service-Pfad aber nicht genutzt.

Die E2-Entscheidung (`docs/governance/architecture-decisions-2026-08-13-v1.md`, Abschnitt E2) will Arch-Gap-Capabilities künftig „über OpenClaude" ausführen; der hier belegte Ist-Zustand zeigt, dass dafür heute nur der One-Shot-Text-Pfad existiert — die dort verlangte Prüfung „ob OpenClaude die genannten Capabilities tatsächlich abdeckt" bleibt offen und wird durch diese Evaluation nicht ersetzt.

## 2. spec-kit-Mechanik (quellcode-verifiziert @ `83883a2`)

### 2.1 Was spec-kit tatsächlich ist

spec-kit (MIT) besteht aus zwei Teilen:

1. **`specify`-CLI** (Python, `uv tool install specify-cli`, `README.md:55-69`): ein **Scaffolding-Werkzeug**. `specify init` legt im Projekt `.specify/` an (Templates, Skripte, `memory/constitution.md`) und registriert die Slash-Commands beim gewählten Coding-Agent. Die Integrations-Registry umfasst ~38 Agents (`src/specify_cli/integrations/` — u. a. `claude`, `codex`, `copilot`, `cursor_agent`, `gemini`; README nennt konservativ „30+"). Für Claude Code werden die Commands als **Skills** nach `.claude/skills/speckit-*/SKILL.md` geschrieben (`integrations/claude/__init__.py:41-55`: `registrar_config = {"dir": ".claude/skills", "format": "markdown", "extension": "/SKILL.md"}`).
2. **Prompt-Templates + Hilfsskripte**: Die Commands (`templates/commands/{constitution,specify,clarify,plan,tasks,analyze,checklist,implement,converge,taskstoissues}.md`) sind **reine Prompt-Dateien, die der Coding-Agent selbst ausführt**. Deterministisch sind nur kleine Skripte (`scripts/bash/…`): `create-new-feature.sh` erzeugt Feature-Verzeichnis `specs/NNN-slug/` **und einen Git-Branch** (`create-new-feature.sh:147-157`), `setup-plan.sh`/`check-prerequisites.sh` prüfen Artefakt-Vorbedingungen.

### 2.2 Der Workflow und seine Artefakte

`/speckit.constitution` → `.specify/memory/constitution.md` (Projektprinzipien; `templates/commands/constitution.md:77-125`) → `/speckit.specify` → `specs/NNN/spec.md` (User-Stories, Requirements; mit „handoffs"-Frontmatter auf die Folge-Commands, `templates/commands/specify.md:1-10`) → `/speckit.clarify` (gezielte Rückfragen) → `/speckit.plan` → `plan.md` + Design-Artefakte (`research.md`, `data-model.md`, `contracts/`) → `/speckit.tasks` → `tasks.md` mit Format `[ID] [P?] [Story] Beschreibung + exakter Dateipfad`, gruppiert nach User-Story, `[P]` = parallelisierbar (`templates/tasks-template.md:16-20`) → `/speckit.implement` (Agent arbeitet tasks.md ab) → `/speckit.analyze` (Konsistenzprüfung Spec↔Plan↔Tasks) → `/speckit.converge` (Ist-Code gegen Spec diffen, Rest-Tasks anhängen, `templates/commands/converge.md:1-7`). Dazu Extensions/Presets/Bundles (`extensions/`, `presets/`, `bundles/`) als Paketierung zusätzlicher Commands und Hooks (`hooks.before_specify` etc. in `.specify/extensions.yml`).

**Wesenskern:** spec-kit ist **Methodik als Prompts + Markdown-Artefakt-Konventionen**. Es hat keine eigene Runtime, keine Ausführungs-Engine, keine API — die „Execution" ist immer der Host-Agent selbst.

### 2.3 Kompatibilität mit OpenClaude (statisch belegt vs. vermutet)

- **Statisch belegt:** OpenClaude besitzt exakt die Loader, die spec-kits Claude-Integration bedient — `.claude/commands` und `.claude/skills` werden von cwd bis Git-Root discovered (`openclaude/src/utils/markdownConfigLoader.ts:30,33,224-330`; `src/skills/loadSkillsDir.ts`). Ein per `specify init --integration claude` gescaffoldetes Projekt würde seine `speckit-*`-Skills in einer **interaktiven** OpenClaude-Session strukturell auffindbar machen.
- **Vermutet, nicht verifiziert:** ob der One-Shot-Pfad (`-p`-Modus über `serve.ts`) Skills/Slash-Commands tatsächlich auflöst und ob die spec-kit-Prompts mit den in der Compose konfigurierten Free-Tier-Modellen (`qwen/…:free`) brauchbare Artefakte erzeugen. Beides wurde nicht ausgeführt (keine Installation, kein Runtime-Test — außerhalb des Session-Scopes).

## 3. Fit/Gap-Analyse

### 3.1 (a) Andockpunkte

| Andockpunkt | Befund | Bewertung |
|---|---|---|
| OpenClaude `serve.ts` (One-Shot-HTTP) | stateless, kein `agent_role`-Dispatch, keine Artefakt-Persistenz (`serve.ts:29,92-98`) | **ungeeignet** für den mehrstufigen spec-kit-Workflow; ein Workflow aus 5+ Slash-Commands braucht Session-/Artefakt-Kontinuität |
| OpenClaude interaktiv (CLI im Workspace) | Loader-kompatibel mit spec-kit-Skills (statisch belegt, 2.3) | technisch plausibel, aber heute **kein produktiver Pfad** im Coding-Space; wäre ein neuer Runtime-Modus (siehe Stufe 3) |
| coding-engine `spec_adapter`/`spec_parser` | Engine konsumiert bereits Spec-**Verzeichnisse** (`SpecFormat.DOCUMENTATION` mit `MASTER_DOCUMENT.md`, `user_stories/`, `tech_stack/`; `spec_adapter.py:23-28`) | **bester Andockpunkt**: spec-kits `specs/NNN/{spec,plan,tasks}.md` ist strukturell ein weiteres Eingabeformat derselben Kette |
| Brain/OpenFang (`code.*`-Events, `brain-coder`) | `code.*` ruft `POST /api/start` der Engine (statisch dokumentbasiert, `docs/SPACES.md:65-83`; MCP-Scope `docs/contracts/openfang-mcp-authority-v1.md:90`) | unverändert lassen; spec-kit darf hier **nichts** hinzufügen (3.3) |

### 3.2 (b) Verhältnis zur V1-Governance — Doppelstruktur vermeiden

Die spec-kit-Kette (constitution → spec → plan → tasks) und die V1-Governance-Kette (Charter → Session-Request → Task-Brief → Handoff) sind **konzeptionell isomorph, aber auf verschiedenen Ebenen**:

- Die V1-Kette regelt die **Programm-Ebene**: wer welche Session mit welcher Authority auf welchem Branch fahren darf (`docs/governance/multi-session-program-charter-v1.md` §4-5, `docs/runbooks/v1-session-lifecycle.md`).
- spec-kit adressiert die **Produkt-Ebene**: wie ein einzelner Coding-Job (Feature im generierten Projekt) spezifiziert, geplant und in Tasks zerlegt wird — genau die Ebene, die heute `spec_adapter`/`planning_engine` in der Engine besetzen.

**Empfohlene Abgrenzung:** spec-kit **nicht** für die Governance-Ebene adaptieren (Session-Requests/Task-Briefs sind etabliert, validator-gestützt und strenger — insbesondere fail-closed Approval-Referenzen, die spec-kit nicht kennt). Adaption ausschließlich auf der Produkt-Ebene als **Artefakt-Format für Coding-Jobs**. Damit entsteht keine Doppelstruktur: eine Ebene, ein Format.

### 3.3 (c) Konflikte mit der V1-Architektur

1. **OpenFang als einzige Execution Engine** (Charter §2; `docs/SPACES.md:233`): `/speckit.implement` macht den Coding-Agent selbst zum Executor eines Task-Plans. Direkt auf OpenClaude verdrahtet wäre das eine **parallele Execution-Schiene** an Brain/OpenFang vorbei — exakt das verbotene Muster. Mitigation: spec-kit-Artefakte fließen als *Daten* in die bestehende Kette `Brain → OpenFang → brain-coder → coding-engine`; `implement` bleibt die Engine-Pipeline, nicht der Agent.
2. **E1-Rollensemantik** (Brain benennt Rolle, OpenFang bindet Instanz; `architecture-decisions-2026-08-13-v1.md` E1): spec-kit kennt keine Rollen — es adressiert „den Agent" des Projekts. Der heutige OpenClaude-Pfad ignoriert `agent_role` ohnehin (1.2). spec-kit-Adaption darf die Rollen-Bindung weder vorwegnehmen noch umgehen; sie bleibt Scope von `task-brain-0018`.
3. **Approval-/Cost-/Evidence-Pflichten** (`openfang-mcp-authority-v1.md` N4: MCP-Events brauchen `approval_ref`/`cost_ref`; SPACES.md Coding-Safety): spec-kits Workflow hat keine Provenance-Begriffe, `serve.ts` läuft mit `--dangerously-skip-permissions` und liefert Schätz-Token statt Kosten-Evidence. Jede Live-Verdrahtung erbt diese Lücken und braucht deshalb die Runtime-Authority-Gates (nicht Teil dieser Evaluation).
4. **Branch-Governance:** `create-new-feature.sh` erzeugt eigene Git-Branches (`NNN-slug`). Im Superproject/Submodul-Kontext kollidiert das mit dem Branch-Schema `codex/<space>/<task-id>` und der Regel, dass nur der Orchestrator merged. In generierten *Produkt*-Projekten (Gitea-Namespace der Engine, `Data/generated`-Volume) ist es unkritisch — die Grenze muss aber explizit gezogen werden.
5. **Installations-Fußabdruck:** `specify init` schreibt `.specify/` + Agent-Verzeichnisse ins Zielrepo. In VibeMind-Repos ist das ohne eigenen Task verboten (Scaffolding = Code-/Konfig-Änderung); in generierten Projekten der Engine wäre es zulässig.

### 3.4 (d) Was sich lohnt — und was nicht

**Lohnend (Adaption, nicht Installation):**

- **`tasks.md`-Format** (`[ID] [P?] [Story] + Dateipfad`, Story-Gruppierung): kartiert fast 1:1 auf `TaskSlice`/`ExecutionBatch` der Engine (`planning_engine.py:20-36` kennt `parallel`-Batches). Ein Parser dafür ist klein und testbar.
- **`spec.md`/`plan.md`-Templates** als diszipliniertes Eingabeformat für `/api/jobs` — strukturell ein fünftes `SpecFormat`, das die vorhandene `DOCUMENTATION`-Mechanik ergänzt.
- **Constitution-Idee** als projektweite, versionierte Prinzipien-Datei im *generierten* Projekt: kartiert auf die bereits vorhandene CLAUDE.md-Injektion der Engine (`claude_code_tool.py:438-551` lädt Engine- und Projekt-CLAUDE.md) — Adaption heißt hier: das Projekt-CLAUDE.md nach Constitution-Vorbild strukturieren, kein neuer Mechanismus.
- **`analyze`/`converge`-Prompts** als Vorlage für einen späteren Verifikations-Schritt der Engine (Spec↔Code-Drift) — konzeptionell wertvoll, aber erst nach dem ersten Schritt.

**Nicht lohnend / ausgeschlossen:**

- `specify`-CLI-Installation in VibeMind-Repos oder in die Engine-Images (Scaffolding-Nutzen ≈ 0, Governance-Kosten hoch).
- spec-kit-Branch-Automatik im Superproject/Submodul-Kontext.
- `/speckit.implement` als Ausführungspfad (parallele Execution-Schiene, 3.3.1).
- `taskstoissues` (GitHub-Issue-Erzeugung — externe Mutation, eigener Authority-Pfad, kein Bedarf).
- Extensions-/Presets-/Bundles-Marketplace (Reifegrad und Angriffsfläche stehen in keinem Verhältnis zum Nutzen; Hooks führen fremde Commands aus).

## 4. Integrationsvorschlag in Stufen

| Stufe | Inhalt | Klassifikation | Authority |
|---|---|---|---|
| 0 (dieses Dokument) | Evaluation, Abgrenzung Governance- vs. Produkt-Ebene | `docs`-Routine | Standing Autonomy innerhalb freigegebener Session |
| 1 | Format-Spezifikation „VibeMind Coding-Job-Spec v1" (spec-kit-abgeleitet: `spec.md`/`plan.md`/`tasks.md`-Schema, Mapping auf `SpecFormat`/`TaskSlice`), als Spec-Dokument in `docs/superpowers/specs/` | `docs`-Routine | Maintenance-Delegation (Charter §4a.2) |
| 2 | `SpecFormat.SPEC_KIT` in `spec_adapter.py` + Parser + fokussierte Tests (coding-engine-Submodul; Service-Commit und Superproject-Pin getrennt) | `code`-Routine, kein Vertrag, keine Runtime | Maintenance-Delegation; **empfohlener erster Task, siehe §6** |
| 3 | Interaktiver/mehrstufiger OpenClaude-Modus (Session-Persistenz, echte Tool-Nutzung statt Text-Parsing, `agent_role`-Dispatch), ggf. spec-kit-Skills im Engine-Workspace generierter Projekte | Runtime-/Deployment-nah, berührt E1/E2 | request-spezifische Runtime-Authority; abhängig von `task-brain-0018` und `task-integration-0007` — **nicht jetzt** |

Fokus-Direktive beachtet: Stufen 1-2 sind vorbereitend und klein; der Ideas-Golden-Path bleibt unberührt und prioritär. Nichts in diesem Vorschlag erfordert oder rechtfertigt einen Sofort-Umbau.

## 5. Explizite Nicht-Ziele

1. Keine Installation von spec-kit (CLI, Templates, `.specify/`, Agent-Verzeichnisse) in `Vibemind_V1`, `vibemind-os` oder ein Submodul.
2. Keine parallele Execution-Schiene: `/speckit.implement` und spec-kit-Branch-Automatik werden nicht in die Produkt-Kette übernommen; OpenFang bleibt einzige Execution Engine.
3. Keine Änderung an `serve.ts`, OpenClaude-Pins, OpenFang-Config, Registry oder Verträgen durch diese Evaluation.
4. Keine Adaption von spec-kit für die Governance-Ebene (Session-Requests/Task-Briefs bleiben das einzige Programm-Format).
5. Keine Runtime-, Live- oder Deployment-Claims; keine Aussage über Modellqualität der konfigurierten Free-Tier-Provider.

## 6. Empfohlener erster Implementierungstask (genau einer)

**`task-coding-0004-speckit-jobspec-format-v1`** — Parent-Cockpit `cockpit-coding`, Risikoklasse `code`-Routine.

**Scope:**

- In `docs/superpowers/specs/`: Format-Spezifikation „Coding-Job-Spec v1" (Stufe 1) — `spec.md`/`plan.md`/`tasks.md`-Schema nach spec-kit-Vorbild, inkl. Mapping-Tabelle auf `SpecFormat`-Interna und `TaskSlice`-Felder.
- In `vibemind-os/coding-engine` (isolierter Worktree, eigener Branch): `SpecFormat.SPEC_KIT` in `src/engine/spec_adapter.py` mit Parser für ein Feature-Verzeichnis `{spec.md, plan.md, tasks.md}` (tasks.md-Zeilenformat `[ID] [P?] [Story]` → `TaskSlice` mit Parallel-Flag), plus Fixture-Verzeichnis und fokussierte Tests. Keine API-Änderung nötig (bestehender `/api/jobs`-Eingang, `jobs.py:66`), keine OpenClaude-/OpenFang-Berührung.
- Service-Commit und Superproject-Pin-Update strikt getrennt; Pin-Update nur durch den Orchestrator nach Merge-Reihenfolge.

**Explizit außerhalb:** jede Runtime-Verdrahtung, `agent_role`-Dispatch, `serve.ts`-Änderungen, Registry-/Vertrags-Änderungen, spec-kit-Installation.

**Definition of Done:**

1. Ein committetes Fixture-Featureverzeichnis wird deterministisch in das interne Format geparst (Requirements aus spec.md-Stories, Tasks mit IDs, `[P]`-Flags und Dateipfaden aus tasks.md).
2. Fokussierte Unit-Tests grün (Parser, Format-Erkennung, Fehlerfälle: fehlende plan.md → fail-closed mit klarem Fehler); bestehende `spec_adapter`-Tests unverändert grün.
3. Format-Spec-Dokument gemergt; Mapping-Tabelle vollständig (jedes tasks.md-Feld hat ein Ziel oder ein dokumentiertes „ignoriert").
4. Handoff mit exakten Testkommandos und Commit-SHAs; kein Pin geändert, keine Runtime-Evidence behauptet.

## 7. Empfehlung in einem Satz

spec-kit **nicht als Werkzeug installieren, sondern als Artefakt-Format adaptieren**: die `spec.md`/`plan.md`/`tasks.md`-Konventionen als fünftes Eingabeformat der bestehenden coding-engine-Kette (`spec_adapter` → `planning_engine`) übernehmen, die Execution unverändert bei Brain → OpenFang → coding-engine belassen — und den heutigen OpenClaude-One-Shot-Pfad erst in einem separat autorisierten Stufe-3-Task zu einem echten mehrstufigen Agent-Backend ausbauen.
