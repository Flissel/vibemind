# VibeMind V1 Space-Orchestrierung — Design

**Datum:** 2026-07-30
**Status:** Normatives MVP-Zieldesign; Routine-Umsetzung läuft autonom, Live-Nachweise bleiben taskweise verpflichtend.
**Ziel:** VibeMind V1 wird zum zentralen Entwicklungs-, Integrations- und Betriebsprojekt. Brain plant und routet; OpenFang führt sämtliche Application-Aktionen aus, verwaltet LLM-Provider, Kosten und Approvals; jeder fachliche Space besitzt einen eigenen Chat-Agenten.

> **Aktuelle MVP-Klarstellung vom 2026-08-01:** OpenFang bleibt die verpflichtende Execution Engine des MVP. Jeder ausführbare Intent läuft über Brain zu OpenFang und von dort zum zuständigen Space-Agenten und der bestehenden Application. Aus dem MVP herausgehalten werden nur ein OpenFang-Neubau, eine parallele Execution Engine und ein separates LLM-Provider-Repository.
>
> Das aktuelle Portfolio in `docs/superpowers/specs/2026-07-30-v1-codex-session-portfolio-design.md` und der Lifecycle in `docs/runbooks/v1-session-lifecycle.md` bleiben für Session-Scope, Task-Authority und Nachweisgrenzen maßgeblich.

## 1. Ausgangslage

VibeMind besteht aus einem V1-Oberprojekt, dem eingebetteten `vibemind-os`, mehreren verschachtelten Repositories, bestehenden Applications, Space-Adaptern, Infrastruktur und vielen parallelen Git-Worktrees. Teile des Systems sind bereits nutzbar, andere besitzen nur Routing-, Tool- oder Deployment-Gerüste.

Die bestehenden Applications sollen nicht durch neue Parallelentwicklungen ersetzt werden. VibeMind soll sie über stabile Verträge verbinden, damit jede Anwendung über Brain und einen zuständigen OpenFang-Agenten per Chat orchestrierbar wird.

Die vor diesem Design gestarteten 14 Space-Implementierungssessions gelten als verworfen. Ihre nicht integrierten Ergebnisse sind keine Architektur- oder Implementierungsgrundlage. Branches und Worktrees werden unter Standing Autonomy nicht entfernt.

## 2. Verbindliche Architekturentscheidungen

1. `Vibemind_V1` ist das zentrale Superproject und der Einstiegspunkt für Codex-Sessions.
2. SmartGit ist ausschließlich eine optionale visuelle Git-Oberfläche. Git, Worktrees, Branch-Regeln, CI und V1-Skripte bleiben die technische Wahrheit.
3. Brain ist kein normaler Space. Brain ist das globale Routing-, Planungs- und Validierungs-Control-Plane.
4. Brain entscheidet, welche Tasks entstehen, welche Spaces beteiligt sind, welche und wie viele Agenten benötigt werden und welche Abhängigkeiten gelten.
5. OpenFang ist die einzige Ausführungs-, LLM-Provider-, Kosten- und Approval-Schicht für Product-Runtime-Aktionen.
6. Jeder fachliche Space erhält einen eigenen OpenFang Chat-Agenten.
7. Routine-Codex-Prozesse werden unter `standing-autonomy:v1` ohne per-session Nutzerinteraktion erstellt und orchestriert.
8. Jede Implementierungs-Session benötigt einen begrenzten Task-Brief, Implementierungsplan, Authority-Verweis und Evidence-Plan.
9. Bestehende Repositories, APIs, Tools, Worker, Tests und Deployments werden vor jeder Änderung geprüft und bevorzugt weiterverwendet.
10. Minibook ist ein internes VibeMind-Cockpit und keine Lifecycle-Autorität.
11. Ein separates LLM-Provider-Repository ist nicht Bestandteil des MVP. OpenFangs vorhandene Provider-Schicht wird verwendet.
12. `rowboat` ist der kanonische Name. `roarboot` darf nur zeitlich begrenzt als Eingangs-Alias existieren.
13. Merge und Deployment sind getrennte Aktionen. Der Haupt-Orchestrator pflegt und merged grüne Routine-PRs autonom; Produktionsdeployments benötigen request-spezifische Authority.

## 3. Zielstruktur des Superprojects

Große, eigenständig versionierte Applications werden langfristig direkte Submodule erster Ebene. Verschachtelte Submodule werden schrittweise aufgelöst; es gibt keine Big-Bang-Migration.

```text
Vibemind_V1/
├── README.md
├── AGENTS.md
├── CONTRIBUTING.md
├── CODEOWNERS
├── SECURITY.md
├── LICENSE
├── .gitignore
├── .gitattributes
├── .gitmodules
├── repo-manifest.yaml
├── vibemind.config.yaml
├── Taskfile.yml
│
├── .github/
│   ├── CODEOWNERS
│   ├── pull_request_template.md
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
│       ├── architecture.yml
│       ├── contracts.yml
│       ├── spaces.yml
│       ├── integration.yml
│       └── release.yml
│
├── .agents/
│   ├── skills/
│   ├── templates/
│   └── policies/
│
├── control-plane/
│   ├── brain/
│   ├── task-ledger/
│   ├── approval-gateway/
│   ├── agent-gateway/
│   ├── event-bus/
│   └── memory-gateway/
│
├── shared/
│   ├── contracts/
│   ├── sdk/
│   │   ├── python/
│   │   ├── typescript/
│   │   └── rust/
│   ├── observability/
│   ├── testing/
│   └── security/
│
├── apps/
│   ├── voice/
│   ├── internal/
│   │   ├── minibook/
│   │   └── control-center/
│   └── desktop/
│
├── spaces/
│   ├── ideas/
│   ├── bubbles/
│   ├── coding/
│   ├── desktop/
│   ├── research/
│   ├── n8n/
│   ├── agentfarm/
│   ├── schedule/
│   ├── rowboat/
│   ├── video/
│   ├── flowzen/
│   ├── mirofish/
│   └── marketing/
│
├── services/
│   ├── openfang/
│   ├── openclaw/
│   ├── coding-engine/
│   ├── desktop-automation/
│   ├── rowboat/
│   ├── mirofish/
│   ├── video-engine/
│   └── agentfarm/
│
├── integrations/
│   ├── openfang/
│   ├── openclaw/
│   ├── n8n/
│   ├── supabase/
│   ├── neo4j/
│   ├── qdrant/
│   ├── redis/
│   └── notifications/
│
├── data/
│   ├── supabase/
│   ├── neo4j/
│   ├── qdrant/
│   └── fixtures/
│
├── workflows/
│   ├── n8n/
│   ├── agentfarm/
│   └── approvals/
│
├── infra/
│   ├── local/
│   ├── proxmox/
│   ├── swarm/
│   ├── observability/
│   └── secrets/
│
├── scripts/
│   ├── git/
│   ├── spaces/
│   ├── deploy/
│   ├── backup/
│   ├── restore/
│   └── evidence/
│
├── tests/
│   ├── architecture/
│   ├── contracts/
│   ├── integration/
│   ├── e2e/
│   ├── live/
│   └── deployment/
│
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── superpowers/
│   ├── spaces/
│   ├── runbooks/
│   ├── operations/
│   └── releases/
│
├── tools/
│   ├── manifest-validator/
│   ├── contract-generator/
│   ├── agent-config-generator/
│   └── dependency-graph/
│
└── .worktrees/                 # gitignored; alternative externe Codex-Worktrees
```

### 3.1 Ownership der Schichten

- `control-plane/`: globale Planung, Taskzustand und Integrationssteuerung.
- `spaces/`: dünne fachliche Verträge und Adapter, keine Kopien bestehender Applications.
- `services/`: eigenständige, versionierte Application-Repositories.
- `apps/`: Nutzer- und interne Oberflächen.
- `shared/`: versionsstabile Schemas, SDKs und Querschnittsfunktionen.
- `integrations/`: technische Adapter zu externen oder gemeinsam genutzten Systemen.
- `infra/`: reproduzierbarer Betrieb ohne Secrets.
- `data/`: Schemas und Migrationen, keine produktiven Daten.

## 4. Standardstruktur eines Spaces

```text
spaces/<space>/
├── README.md
├── AGENTS.md
├── space.yaml
├── contracts/
│   ├── intents.yaml
│   ├── commands.yaml
│   ├── events.yaml
│   └── results.yaml
├── agent/
│   ├── openfang-agent.toml
│   ├── prompt.md
│   ├── tools.yaml
│   └── permissions.yaml
├── adapter/
│   ├── client.*
│   ├── mapper.*
│   ├── validator.*
│   └── health.*
├── api/
├── workers/
├── workflows/
├── migrations/
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   └── golden_path/
└── docs/
    ├── architecture.md
    ├── mvp.md
    ├── operations.md
    └── backlog.md
```

Nicht benötigte Unterbereiche werden nicht als leere Platzhalter angelegt. `space.yaml` ist der maschinenlesbare Vertrag für Space-ID, Chat-Agent, Intents, Zielservice, Ausführungsmodus, Healthcheck, Approvals und Kostenklasse.

## 5. Brain und OpenFang

### 5.1 Brain-Verantwortung

Brain steht logisch vor OpenFang und:

- erkennt Intent und expliziten Space-Kontext;
- lädt den freigegebenen Task- und Memory-Kontext;
- erstellt einzelne Tasks oder eine versionsgebundene Task-DAG;
- bestimmt beteiligte Spaces;
- bestimmt Agentenrollen, Agentenanzahl und Parallelität;
- formuliert Erfolgskriterien;
- validiert Teilergebnisse und das Gesamtergebnis;
- erzeugt bei Bedarf einen neuen, erneut kostenpflichtig zu prüfenden Folgeplan.

Brain darf keine Application direkt mutieren, kein OpenFang-Approval umgehen, keine Provider-Schlüssel besitzen und keinen Task ohne Evidence als erfolgreich markieren.

### 5.2 OpenFang-Verantwortung

OpenFang:

- löst die vom Brain geplanten Agentenrollen auf;
- validiert Agenten, Tools und Berechtigungen;
- verwendet im MVP seine vorhandene LLM-Provider-Schicht;
- schätzt, reserviert und misst Kosten;
- verwaltet die autoritativen Approvals;
- startet und überwacht Agenten;
- führt sämtliche Product-Runtime-Aktionen aus;
- liefert Status, Kosten, Logs, Ergebnisse und Evidence zurück.

Wenn Brain selbst für komplexe Planung ein kostenpflichtiges LLM benötigt, verwendet es OpenFangs Provider-/Cost-API. Die initiale Space-Erkennung soll möglichst deterministisch und ohne kostenpflichtigen Provider funktionieren.

### 5.3 Planübergabe

```yaml
plan_id: plan_coding_1042
intent: "Baue Projekt X"
tasks:
  - id: requirements
    capability: requirements.analyze
    depends_on: []
  - id: architecture
    capability: architecture.design
    depends_on: [requirements]
  - id: implementation
    capability: coding.generate
    depends_on: [architecture]
agents:
  - template: requirements-agent
    count: 1
    tasks: [requirements]
  - template: architecture-agent
    count: 2
    tasks: [architecture]
  - template: coding-agent
    count: 3
    tasks: [implementation]
execution:
  max_parallel_agents: 3
  quality_tier: high
  timeout_seconds: 14400
success:
  - requirements_validated
  - architecture_approved
  - tests_green
```

Brain beschreibt Fähigkeiten, Qualität, Rollen, Anzahl und Abhängigkeiten. OpenFang wählt Provider und Modelle gemäß freigegebener Policy und Budget.

## 6. Kosten und Approvals

Alle kostenpflichtigen Vorgänge laufen über OpenFang, einschließlich Brain-LLM-Aufrufen, Agenteninferenz, Research-APIs, Embeddings sowie Video- und Medienprovider.

Vor Ausführung erstellt OpenFang ein Kostenangebot:

```yaml
quote_id: quote_839
plan_id: plan_coding_1042
estimated_cost:
  minimum: 1.80
  expected: 4.20
  maximum: 8.00
currency: EUR
agents: 6
provider_calls: 40
approval_required: true
```

OpenFang speichert pro Plan, Task und Agent Provider, Modell, Tokenverbrauch, Toolkosten, Laufzeit, Retry-Kosten, freigegebenes Budget und tatsächliche Kosten.

Approval-Regeln:

- Approval ist an Aktion, Parameter und Request-Hash gebunden.
- Geänderte Parameter benötigen ein neues Approval.
- Timeout und Nichterreichbarkeit bedeuten Ablehnung.
- Read-only-Aktionen können per Policy automatisch freigegeben werden.
- Writes, externe Kommunikation, Desktop-Aktionen, kostenpflichtige Provider, Deployments und Löschvorgänge benötigen die passende Approval-Klasse.
- Zusätzliche Agenten und Budgetüberschreitungen pausieren die Ausführung bis zur erneuten Prüfung.
- OpenFang-Ausfall führt niemals zu einem direkten Fallback auf die Application.

## 7. Chat-Agenten pro Space

Jeder fachliche Space besitzt einen eigenen OpenFang Chat-Agenten. Der globale Chat läuft über Brain; ein direkter Space-Chat übergibt dem Brain eine bereits festgelegte Space-ID. Auch der direkte Space-Chat umgeht Brain nicht.

```text
Globaler Chat → Brain wählt Space(s) → OpenFang Space Chat-Agent
Space-Chat    → Brain registriert Space → OpenFang Space Chat-Agent
```

Ein Space Chat-Agent:

- stellt Rückfragen;
- erklärt den Space und zeigt Tasks oder Projekte;
- erzeugt Task- und Planvorschläge;
- koordiniert Space-interne Spezialagenten;
- verwendet bestehende Applications und APIs;
- startet und überwacht langlebige Jobs;
- fordert Kosten- und Aktionsapprovals an;
- meldet Status, Logs, Evidence und Ergebnisse;
- kann zusätzliche Ressourcen anfragen, aber nicht selbst genehmigen;
- erzeugt strukturierte Handoffs.

Kanonische Agenten:

- `space-ideas-chat`
- `space-bubbles-chat`
- `space-coding-chat`
- `space-desktop-chat`
- `space-research-chat`
- `space-n8n-chat`
- `space-agentfarm-chat`
- `space-schedule-chat`
- `space-rowboat-chat`
- `space-video-chat`
- `space-flowzen-chat`
- `space-mirofish-chat`
- `space-marketing-chat`

Minibook erhält einen internen `minibook-assistant`. Brain ist kein normaler Space-Agent.

Space-Agenten koordinieren sich nicht unkontrolliert direkt. Space-übergreifende Arbeit läuft über Brain und den gemeinsamen Task-Ledger.

## 8. Application- und Job-Vertrag

Bestehende Applications werden über dünne Adapter angebunden. Wenn die native API vom gemeinsamen Vertrag abweicht, übersetzt der Adapter; die Application wird nicht allein für Namensgleichheit umgebaut.

Standard für langlebige Jobs:

```text
POST   /jobs
GET    /jobs/{id}
POST   /jobs/{id}/cancel
POST   /jobs/{id}/resume
GET    /jobs/{id}/result
GET    /jobs/{id}/logs
```

Kanonische Zustände:

- `accepted`
- `queued`
- `running`
- `waiting_for_approval`
- `waiting_for_dependency`
- `paused`
- `succeeded`
- `failed`
- `cancelled`

Ein Ergebnis enthält mindestens Task-, Execution-, Service-Job- und Trace-ID, Status, Artefakte, Evidence sowie geschätzte und tatsächliche Kosten. `ok: true` ist nur erlaubt, wenn Application-Evidence den Erfolg bestätigt.

Fehler werden explizit als `unavailable`, `waiting_for_approval`, `paused_budget`, `not_found`, `provider_failed` oder `unresolved` dargestellt. Ein unklarer Zustand ist niemals Erfolg.

## 9. Task-Ledger, Memory und Minibook

### 9.1 Autoritäten

| Bereich | Autorität |
|---|---|
| Task-DAG, Reihenfolge und Taskstatus | Brain Task-Ledger |
| Agentenausführung | OpenFang |
| Approvals | OpenFang |
| Provider- und Agentenkosten | OpenFang |
| Strukturierte Taskdaten | Supabase |
| Semantisches Wissen | Qdrant |
| Beziehungen und Entscheidungen | Neo4j |
| Große Logs und Artefakte | Object Storage |
| Menschliche Darstellung | Minibook |
| Kurzlebiger Eventtransport | Redis |

Redis ist keine dauerhafte Task- oder Memory-Datenbank.

### 9.2 Gemeinsame Identitäten

Alle Komponenten verwenden gemeinsame IDs für Projekt, Task, Plan, Trace, Execution, Agentenlauf, Approval, Service-Job, Artefakt, Git-Branch, Commit und PR.

### 9.3 Task-Lifecycle

```text
draft
→ awaiting_session_approval
→ discovery
→ awaiting_plan_approval
→ ready
→ quoting
→ awaiting_cost_approval
→ queued
→ running
→ validating
→ ready_for_pr
→ pr_open
→ merge_ready
→ merged
→ verifying
→ succeeded
```

Zusätzliche Zustände sind `waiting_for_user`, `waiting_for_dependency`, `waiting_for_external_service`, `paused_budget`, `failed` und `cancelled`. Zustandswechsel werden als unveränderliche Events protokolliert.

### 9.4 Session-Kontext

Eine Session erhält ein kuratiertes Context-Paket statt vollständiger alter Chats:

- Task-Brief und Akzeptanzkriterien;
- freigegebene Spezifikation und Plan;
- relevante Entscheidungen;
- offene Todos und Abhängigkeiten;
- bestehende APIs und Repo-Fundstellen;
- Testevidence und Handoffs;
- Git-/PR-Status;
- erlaubter Scope.

### 9.5 Minibook

Minibook ist ein internes VibeMind-Cockpit für Projekte, Task-Reihenfolge, Briefs, Todos, Sessions, Agenten, Approvals, Kosten, Logs, PRs, Ergebnisse und Handoffs.

Minibook verändert keine Application und keine Approval- oder Taskwahrheit direkt. Aktionen werden an Brain beziehungsweise OpenFang weitergereicht.

Im MVP ist Minibook ausschließlich lokal oder im privaten VibeMind-Netz erreichbar:

```text
Desktop-App → interne Minibook API/UI
OpenClaw → Brain → OpenFang Minibook-Agent → interne Minibook API
```

Es gibt im MVP keinen VPN-Aufbau, keine öffentliche Portfreigabe und keinen direkten Datenbankzugriff aus Desktop oder OpenClaw. VPN bleibt späteres Hardening.

## 10. Repo-first- und Session-Regeln

Jede Space- oder Task-Session beginnt read-only mit:

1. Branch-, Remote-, Worktree- und Dirty-State-Audit.
2. Lokalisierung der bestehenden Application und Submodule.
3. Prüfung vorhandener APIs, Agenten, Tools und Worker.
4. Prüfung vorhandener Tests und Deployment-Manifeste.
5. Prüfung bestehender OpenFang-Agenten und Approval-Funktionen.
6. Bestimmung der autoritativen Daten- und Memory-Pfade.
7. Dokumentation, welche bestehende Software weiterverwendet wird.

Neue Komponenten werden nur vorgeschlagen, wenn die bestehende Application den benötigten Vertrag nicht sinnvoll bereitstellen oder adaptieren kann.

### 10.1 Autonome Session-Ebenen

**Space-Cockpit:** Eine dauerhafte Planungssession pro Space. Sie auditiert repo-first und definiert MVP, Backlog und Spezifikationen aus User-Ziel und Evidence. Sie bleibt read-only.

**Task-Session:** Eine isolierte Implementierungssession für genau einen begrenzten Task, Branch, Worktree und Dateiscope.

### 10.2 Session-Authority

Vor jeder neuen Session erzeugt der Haupt-Orchestrator einen Antrag mit Sessiontyp, Ziel, Repositories, Scope, erwarteten Ergebnissen, Risiken und Schreibrechten. Routine-`docs`/`code` wird mit `standing-autonomy:v1` ohne Pause aktiviert.

Eine Scope-Erweiterung innerhalb einer Session benötigt eine neue Request-Version und Risikoklassifikation. Follow-ups innerhalb des Scopes benötigen keine neue Session. High-Risk-Arbeit benötigt request-spezifische Authority.

## 11. Git-, PR- und Merge-Modell

### 11.1 Branches und Worktrees

- `main` ist geschützt, reproduzierbar und deploybar.
- Task-Branches heißen `codex/<space>/<task-id>-<slug>`.
- Ein Task besitzt genau einen primären V1-Worktree.
- Keine Session arbeitet im dirty Hauptcheckout.
- Große Service-Änderungen werden zuerst im Service-Repository committed.
- Ein separater V1-Commit aktualisiert Adapter und Submodul-Pin.
- Es gibt höchstens eine Submodulebene unter `services/`.
- Branches, Worktrees und Submodule werden nicht unter Standing Autonomy gelöscht.

### 11.2 PR-Verantwortung des Haupt-Orchestrators

Sobald ein PR existiert, übernimmt der Haupt-Orchestrator:

- Titel, Beschreibung, Task-ID, Labels und Abhängigkeiten;
- CI-, Review- und Evidence-Status;
- Rückfragen an die zuständige Session;
- Synchronisierung mit `main`;
- Konfliktanalyse und koordinierte Behebung;
- richtige Merge-Reihenfolge;
- Merge nach erfüllten Gates;
- nachgelagerte V1-Pin-PRs;
- Post-Merge-Verifikation;
- Task- und Minibook-Abschluss.

### 11.3 Merge-Gates

Ein PR wird gemerged, wenn:

- Spezifikation, Task-Scope und Authority valide sind;
- alle Abhängigkeiten gemerged sind;
- der Branch auf einem geprüften `main` basiert;
- keine fremden Dateien enthalten sind;
- Contract-, Unit-, Integrations- und Architekturtests grün sind;
- relevante Fehlerfälle fail-closed getestet sind;
- Task-Ledger und Evidence vollständig sind;
- Reviews abgeschlossen sind;
- keine offenen Approval- oder Blocker-Zustände bestehen.

Merge-Reihenfolge:

1. Shared Contracts und Schemas
2. Brain-/OpenFang-Gateway
3. Service-Repository
4. Space-Adapter
5. V1-Submodul-Pin
6. V1-Integrationstests
7. Deployment-Konfiguration
8. Golden Path
9. Release-Tag

Normale, durch `standing-autonomy:v1` gedeckte und vollständig grüne `docs`-/`code`-PRs merged der Haupt-Orchestrator selbstständig. Breaking Contracts, Datenmigrationen, Secrets, Produktionsdeployments, Proxmox-Änderungen, große Repo-Verschiebungen und destruktive Cleanups benötigen request-spezifische Authority.

## 12. Space-Katalog und MVP-Grenze

| Space | Chat-Agent | Bestehende Application | MVP-Fokus |
|---|---|---|---|
| Ideas | `space-ideas-chat` | Supabase Canvas | Ideen erfassen, formatieren und verbinden |
| Bubbles | `space-bubbles-chat` | Supabase Canvas | Bereiche, Navigation und Bewertung |
| Coding | `space-coding-chat` | Coding Engine | langlebige Projektgenerierung |
| Desktop | `space-desktop-chat` | Desktop Automation/OpenClaw | sichtbare Computersteuerung |
| Research | `space-research-chat` | Research-/Fetch-Tools | Recherche mit Quellen und Evidence |
| n8n | `space-n8n-chat` | bestehendes n8n | Workflows verwalten und ausführen |
| AgentFarm | `space-agentfarm-chat` | AutoGen/AgentFarm | Agententeams ausführen |
| Schedule | `space-schedule-chat` | Schedule Worker | persistente Termine und Tasks |
| Rowboat | `space-rowboat-chat` | Rowboat | Wissen, Briefings und Dokumente |
| Video | `space-video-chat` | Video Engine | Video-, Audio- und Vision-Jobs |
| Flowzen | `space-flowzen-chat` | Flowzen | Check-ins und Tagesfluss |
| MiroFish | `space-mirofish-chat` | MiroFish | Simulation, Prognose und Graphen |
| Marketing | `space-marketing-chat` | Marketing/n8n/Mail | Kampagnen und Publishing |
| Minibook intern | `minibook-assistant` | Minibook | Tasks, Logs, Kosten und Handoffs |

Ein Space ist MVP, wenn Chat, Brain-Registrierung, OpenFang-Agent, Application-Adapter, Healthcheck, Kosten-/Approval-Policy, Task-/Ergebnisvertrag, fail-closed Fehlerpfad, Golden Path und Betriebsdokumentation vorhanden und verifiziert sind.

n8n, AgentFarm und Video erhalten vor funktionalen Updates jeweils eine eigene, vom Nutzer freigegebene Space-Spezifikation. Bis dahin werden vorhandene Funktionen nur inventarisiert und geschützt.

## 13. Test-, Release- und Rollback-Modell

### 13.1 Pflichtprüfungen

- Formatierung und statische Prüfung
- Secret-Scan
- Unit Tests
- Space-Contract-Tests
- OpenFang-Agentenmanifest-Validierung
- Approval-Policy-Tests
- Cost-Accounting-Tests
- Fail-Closed-Tests
- Architekturtests gegen direkte Application- oder Provider-Bypässe
- Abhängigkeits- und Submodulprüfung
- `git diff --check`

Architekturtests verhindern direkte LLM-Aufrufe außerhalb OpenFang, direkte Application-Mutationen aus Brain oder Voice, mutierende Tools ohne Approval, fehlende Kostenerfassung, unbekannte Space-IDs, `roarboot` als kanonische ID, direkte Minibook-Datenbankmutationen, Redis als Taskdatenbank, verschachtelte Submodule, ungepinnte Services und Erfolg ohne Evidence.

### 13.2 Golden Path

Jeder Space benötigt mindestens einen echten, korrelierten Pfad:

```text
Space-Chat
→ Brain-Plan
→ OpenFang-Kostenangebot
→ Approval
→ Space-Agent
→ echte Application
→ Ergebnis und Truth-Evidence
→ Task-Ledger
→ Minibook
```

Alle Schritte verwenden dieselbe `trace_id`.

### 13.3 Merge und Deployment

```text
PR grün
→ Haupt-Orchestrator merged
→ Post-Merge-Tests
→ Release Candidate
→ Nutzer genehmigt Deployment
→ Proxmox-Deployment
→ Live-Golden-Path
→ Release-Tag
```

Jeder Release-Stand pinnt V1-Commit, Contract-Versionen, Service-Commits, Agentenmanifest-Versionen und Image-Digests.

Vor produktiven Migrationen werden vorheriger V1-Tag, Service-Pins, Image-Digests, Datenbank-Backup, Migrationsstand, aktive Tasks und OpenFang-Agentenversionen erfasst. Fehlender Rollback-Nachweis blockiert produktive Datenmigrationen.

## 14. Definition of Done

Ein Task ist abgeschlossen, wenn:

- Code gemerged ist;
- erforderliche Tests grün sind;
- Task-Ledger und gemeinsame IDs vollständig sind;
- PR und Commits verknüpft sind;
- Evidence gespeichert ist;
- Minibook den Zustand korrekt zeigt;
- keine offenen Follow-ups versteckt sind;
- Deployment entweder live verifiziert oder ausdrücklich als offen markiert ist.

## 15. MVP-Reihenfolge

1. Git-/Worktree-/Session-Grundlage und Repo-Manifeste
2. Shared Contracts, Task-Ledger und gemeinsame IDs
3. Brain-Planvertrag und OpenFang Execution-/Cost-/Approval-Gateway
4. Minibook-Projektion und interne Zugänge
5. Ideas und Bubbles als einfacher Referenzpfad
6. Coding als Referenz für langlebige Jobs
7. Desktop als Referenz für Aktionsapprovals
8. Research als Referenz für Quellen und Evidence
9. Schedule als Referenz für persistente Jobs
10. Rowboat inklusive kontrollierter `roarboot`-Alias-Migration
11. MiroFish und Flowzen
12. n8n, AgentFarm und Video nach separater Update-Spezifikation
13. Marketing

Für jeden Space wird vor Erstellung seiner Space-Cockpit-Session ein eigener Session-Antrag erzeugt und unter der passenden Authority autonom aktiviert.

## 16. Nicht Bestandteil des MVP

- separates LLM-Provider-Repository;
- öffentlich erreichbares Minibook;
- VPN-Aufbau;
- Big-Bang-Auflösung aller Submodule;
- ungeprüfte Übernahme der verworfenen Space-Sessions;
- automatisches Produktionsdeployment;
- ungebundene Session-Erstellung ohne Task-Scope, Authority und Evidence-Plan;
- direkte Provider- oder Application-Fallbacks außerhalb OpenFang.
