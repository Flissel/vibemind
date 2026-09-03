# VibeMind V1 Codex-Session-Portfolio — Design

**Datum:** 2026-07-30
**Status:** Architektur im Dialog freigegeben
**Ziel:** VibeMind V1 wird durch einen Haupt-Orchestrator und mindestens ein dauerhaftes, interaktives Codex-Cockpit pro fachlichem Space und zentralem Plattformbereich entwickelt.

> **Charter-Präzedenz (2026-08-13):** Für die Erstellung von Sessions gilt `docs/governance/multi-session-program-charter-v1.md`: jede Session — Cockpit wie Implementierung — wird nur nach individueller User-Freigabe erstellt. Aussagen in diesem Dokument, nach denen Sessions unter `standing-autonomy:v1` ohne per-session User-Interaktion erstellt oder aktiviert werden, sind insoweit ersetzt. Alle übrigen Abschnitte bleiben verbindlich.

## 1. Verbindliche Entscheidung

Die V1-Umsetzung verwendet zwei strikt getrennte Session-Ebenen:

1. **Cockpit-Session:** dauerhaft, interaktiv und zunächst read-only. Sie auditiert den vorhandenen Stand, strukturiert das betreffende Gebiet gemeinsam mit dem User und schlägt konkrete Tasks vor.
2. **Implementierungs-Session:** zeitlich und fachlich begrenzt. Routine-`docs`-/`code`-Tasks werden unter `standing-autonomy:v1` ohne per-session User-Interaktion aktiviert und erhalten genau einen Task, einen isolierten Worktree, einen Feature-Branch, erlaubte Pfade, Tests und Definition of Done.

Der aktuelle Codex-Task ist der **V1 Haupt-Orchestrator**. Er verwaltet das Session-Portfolio autonom, erstellt begrenzte Sessions, führt Handoffs zusammen, pflegt und merged grüne PRs und kontrolliert Merge-Reihenfolge sowie Verifikation. Ein sekundärer Prozess überwacht diese Arbeit und informiert den User bei Fehlverhalten; er ist keine Lifecycle-Autorität.

Mit „Session“ ist eine für den User sichtbare, eigenständige Codex-Session gemeint. Cockpits und Implementierungs-Sessions dürfen nicht selbstständig weitere Sessions oder unsichtbare Wegwerf-Subagenten erzeugen.

## 2. Brain und OpenFang

OpenFang-Ausführung ist Bestandteil dieser MVP-Welle. Die verbindliche Product-Runtime-Kette lautet:

```text
Brain -> OpenFang -> Space-Agent -> MCP/Service
```

Brain bleibt Control Plane und besitzt Intent-Verständnis, Planung, Routing, Task-DAG und Ergebnisvalidierung. OpenFang ist die Execution Engine und besitzt Agentenausführung, Tool- und MCP-Zugriff, LLM-Provider, Kosten sowie Runtime-Approvals. Applications dürfen nicht direkt vom Brain mutiert werden und es gibt keinen parallelen Execution-Fallback außerhalb OpenFang.

Die Aufnahme in den MVP ist noch kein Live-Nachweis. Jeder ausführbare Space benötigt einen geprüften OpenFang-Agenten, einen fail-closed Adapter, Approval-/Cost-/Evidence-Korrelation und einen sicheren Brain-to-OpenFang Golden Path. Ein OpenFang-Neubau, eine zweite Execution Engine und ein separates LLM-Provider-Repository bleiben Nicht-Ziele.

### 2.1 Historischer Repository-Fork-Kontext (superseded)

Der am 2026-08-01 dokumentierte Stand beschrieb historisch einen Fork im Superproject und in `vibemind-os`. Die damals genannten Pins, operativen Linien und Space-Wiring-Branches sind superseded und kein aktueller Repository-, Reachability- oder Integrationsnachweis.

Dieser Abschnitt begründet daher kein aktuelles Fork-Gate und keine Live-Aussage. Ein künftiger Git-Integrationstask muss Gitlink, Branches, Reachability, Tests und einen Kandidaten-Commit aus frischer Repository-Evidence bestimmen; der historische Bericht im lokalen Branch `codex/vibemind-ops-baseline` bleibt read-only Evidence.

## 3. Session-Hierarchie

```text
V1 Haupt-Orchestrator
└── Cockpit-Session
    ├── Repo-first Audit
    ├── Space Brief
    ├── MVP-Gap-Map
    ├── priorisierter Backlog
    └── Task-Vorschlag
        └── Standing-Autonomy-Admission
            └── Implementierungs-Session
                ├── isolierter Worktree
                ├── Feature-Branch
                ├── Tests und Evidence
                └── Handoff + PR
                    └── Haupt-Orchestrator
                        ├── Review und PR-Pflege
                        ├── Merge
                        ├── Post-Merge-Verifikation
                        └── Rückmeldung ans Cockpit
```

Ein Cockpit besitzt keinen schreibenden Arbeitsauftrag. Falls aus einem Audit eine Korrektur entsteht, formuliert es zuerst einen Task-Antrag. Es darf die Korrektur nicht selbst ausführen.

## 4. Vollständiges Cockpit-Portfolio

### 4.1 Plattform- und Querschnitts-Cockpits

| Session-ID | Bereich | Auftrag | Erstes Ergebnis |
|---|---|---|---|
| `cockpit-brain` | Brain | Intent-Eingang, Routing, Planung, Task-DAG, Space-Auswahl und Erfolgsbedingungen untersuchen | Brain-Istbild, Routing-Lücken und priorisierter Control-Plane-Backlog |
| `cockpit-openfang` | OpenFang | Execution Engine, Space-Agenten, MCP-Hub, Provider, Kosten, Approvals, Permissions und Runtime-Evidence untersuchen | OpenFang Execution-/Cost-/Approval-Vertrag und priorisierter Runtime-Backlog |
| `cockpit-shared` | Shared | Contracts, IDs, Task Briefs, Approvals, Todos, Handoffs, Memory und Datengrenzen ordnen | kanonisches Shared-Contract-Inventar und Konfliktliste |
| `cockpit-git` | Git & Repositories | Repo-Topologie, Worktrees, Branches, Submodule, SmartGit, PRs und Merge-Reihenfolge kontrollieren | Git-Baseline und freigegebene Governance-Tasks |
| `cockpit-deployment` | Deployment | lokale Runtime, Docker, Proxmox, Backups, Restore, Cutover und Releaseablauf inventarisieren | Deployment-Matrix mit verifiziertem Ist-Zustand und sicheren nächsten Gates |
| `cockpit-integration` | Integration & Golden Paths | Brain-, OpenFang-, Shared-, Space- und Application-Verträge sowie Evidence-Grenzen planen | Golden-Path-Matrix für Brain -> OpenFang -> Space-Agent -> MCP/Service |
| `cockpit-observability` | Observability & Evidence | Logs, Traces, Korrelation, Kosten, Healthchecks, Fehlerbilder und Nachweise vereinheitlichen | Observability-Gap-Map und Evidence-Contract-Vorschlag |
| `cockpit-channels` | Channels | Voice, Desktop-Chat, OpenClaw und Space-Chats als Brain-Eingänge inventarisieren | Channel-Matrix mit Auth-, Intent-, Routing- und Fehlerschnittstellen |

Brain bleibt die Control Plane. OpenFang ist die Execution Engine. Shared ist die Vertrags- und Datenebene, aber keine zusätzliche Lifecycle- oder Execution-Autorität.

Damit existieren 8 Plattform-/Querschnitts-Cockpits und 14 fachliche Space-Cockpits, insgesamt 22 Cockpit-Sessions zusätzlich zum Haupt-Orchestrator.

### 4.2 Fachliche Space-Cockpits

| Session-ID | Space | Auftrag des Cockpits |
|---|---|---|
| `cockpit-ideas` | Ideas | vorhandene Ideen-, Dokument- und Verknüpfungsflüsse sowie direkte Datenbankpfade prüfen |
| `cockpit-bubbles` | Bubbles / Shuttles | Canvas-Bereiche, Navigation, Bewertung, Begriffe und Datenflüsse ordnen |
| `cockpit-coding` | Coding | langlebige Code-Jobs, Projektbezug, Start/Status/Cancel/Resume/Result und Evidence prüfen |
| `cockpit-desktop` | Desktop | Apps, Browser, Screenshots, Eingaben, sichere Aktionen, Abbruch und Nachweis strukturieren |
| `cockpit-research` | Research | Recherche, Scraping, Quellen, Zitate, Zusammenfassung und fail-closed Verhalten inventarisieren |
| `cockpit-n8n` | n8n | geschützten Audit durchführen und eine separate Update-Spezifikation erstellen; bestehende Volumes und Workflows nicht übernehmen oder löschen |
| `cockpit-agentfarm` | AgentFarm / AutoGen | Multi-Agent-Konfiguration auditieren und eine separate Update-Spezifikation erstellen |
| `cockpit-schedule` | Schedule | Termine, Erinnerungen, Trigger, Zeitzonen, Zustellung und fehlende Anwendungsschnittstellen prüfen |
| `cockpit-rowboat` | Rowboat | Wissenssuche, Briefings, Entwürfe und RAG-Flows prüfen; `roarboot` kontrolliert als Alt-Alias abbauen |
| `cockpit-minibook` | Minibook intern | interne Projektion für Tasks, Reihenfolge, Logs, Kosten und Handoffs definieren, ohne Lifecycle-Autorität zu übernehmen |
| `cockpit-video` | Video | Engine, Video-, Vision-, Lipsync-, TTS-Jobs, Artefakte und Ressourcen auditieren und eine Update-Spezifikation erstellen |
| `cockpit-flowzen` | Flowzen | App-Stand, Check-ins, Tagesfluss, Datenmodell und sinnvollen MVP-Kern bestimmen |
| `cockpit-mirofish` | MiroFish | Simulationen, Prognosen, Inputs, reproduzierbare Runs, Resultate und Graphbezug prüfen |
| `cockpit-marketing` | Marketing | bestehende Marketing-/n8n-/Mail-Funktionen schützen, Zuständigkeiten trennen und MVP-Lücken priorisieren |

## 5. Cockpit-Vertrag

Jedes Cockpit beginnt nach autonomer Aktivierung mit demselben read-only Ablauf:

1. relevante Repositories, Worktrees, Branches, Dirty State, Submodule und Remotes prüfen;
2. bestehende Applications, APIs, Worker, Tools, Tests, Deployments und Dokumentation inventarisieren;
3. widersprüchliche Namen, Registries, Zuständigkeiten und Datenpfade markieren;
4. keine statische Registrierung als funktionierende Live-Orchestrierung darstellen;
5. gemeinsam mit dem User MVP-Ziel, Nicht-Ziele und Akzeptanzkriterien festlegen;
6. Brain-, OpenFang-, Shared- und Space-Abhängigkeiten identifizieren und die konkrete Agent-, MCP-, Approval-, Cost- und Evidence-Grenze benennen;
7. priorisierten Backlog und genau einen empfohlenen ersten Task formulieren;
8. für diesen Task eine separate, begrenzte Implementierungs-Session unter der passenden Authority-Referenz anlegen;
9. nach Merge verifizierte Ergebnisse und Restlücken übernehmen.

Die strukturierte Cockpit-Ausgabe besitzt folgende Felder:

```yaml
schema_version: 1
cockpit_session_id: cockpit-coding
domain: coding
audit:
  repositories: []
  entrypoints: []
  existing_capabilities: []
  tests: []
  deployments: []
mvp:
  objective: ""
  non_goals: []
  acceptance_criteria: []
gaps: []
dependencies: []
risks: []
backlog: []
recommended_first_task: null
open_questions: []
```

Leere Felder sind nur während der laufenden Analyse erlaubt. Vor einem Task-Vorschlag müssen Ziel, Akzeptanzkriterien, Lücken, Abhängigkeiten, Risiken und erster Task bewusst ausgefüllt oder mit einer begründeten leeren Liste abgeschlossen sein.

## 6. Autonomievertrag

`standing-autonomy:v1` erlaubt dem Haupt-Orchestrator, bestehende Routine-Cockpits zu koordinieren und begrenzte `docs`-/`code`-Tasks ohne wiederholte User-Interaktion zu erstellen. Ein neuer User-Owned-Codex-Cockpit-Thread benötigt davon unabhängig eine individuelle User-Freigabe im geschlossenen `docs/governance/cockpit-approval-ledger-v1.json`. Vor der Aktivierung hält der Orchestrator intern fest:

- exakte Session-ID und sichtbaren Titel;
- Zweck und Read-only-Scope;
- betroffene Repositories;
- bekannte Abhängigkeiten;
- erwartetes erstes Ergebnis;
- ausdrücklichen Hinweis, ob geschrieben oder nur auditiert wird.

Die Standing Authority ersetzt keine Task-Grenzen. Jeder Prozess erhält einen dauerhaften Request-Verweis, exakten Scope, Risikoklasse, Tests, Evidence und Merge-Position. Für Routine-`docs`/`code` wird `approval_reference: standing-autonomy:v1` verwendet; eine synthetische per-task User-Freigabe wird nicht erzeugt.

Vor jeder Implementierungs-Session erzeugt der Haupt-Orchestrator zusätzlich einen vollständigen Task-Brief mit:

- Task-Session-ID, Parent-Cockpit und dauerhafte Request-Referenz;
- Ziel und Nicht-Zielen;
- Repositories und erlaubten Pfaden;
- Base-Ref, Branch und Worktree;
- deklarierte Abhängigkeiten und Merge-Position;
- Risikoklasse und erforderlicher Authority-Art;
- konkreten Testbefehlen;
- Definition of Done.

Materielle Änderungen an Ziel, Repository, Pfadscope, Risiko oder Definition of Done benötigen eine neue Task-Version und erneute Klassifikation. Routine-`docs`/`code` bleibt autonom; höhere Risikoklassen benötigen request-spezifische Authority. Technische Detailentscheidungen innerhalb des Scopes trifft und dokumentiert die Session selbst.

## 7. Implementierungs-Session-Vertrag

Eine freigegebene Implementierungs-Session:

- besitzt genau ein Parent-Cockpit;
- bindet Handoff und PR-Gate an den genehmigten Request, dessen Approval-Referenz, Parent-Cockpit, Abhängigkeiten und Merge-Position;
- arbeitet in genau einem isolierten Worktree pro Repository;
- verwendet `codex/<domain>/<task-id>-<slug>`;
- beginnt mit Repo-first Audit und bestätigt den Task-Plan interaktiv;
- schreibt nur in den freigegebenen Pfaden;
- verwendet TDD und kleine Conventional Commits;
- trennt Service-Commit und Superproject-Submodule-Pin;
- liefert exakte Tests, Evidence, Commit-SHAs, Dependencies und Restblocker;
- erstellt keinen eigenen Merge und keine neue Session;
- führt keine Deployments oder destruktiven Änderungen unter `standing-autonomy:v1` aus.

## 8. Orchestrator-Verantwortung

Nur der Haupt-Orchestrator:

- hält die kanonische Session-Liste und deren Status;
- verhindert doppelte oder überlappende Scopes;
- prüft Merge-Basen und Abhängigkeiten;
- entscheidet autonom, welche sichere Session als Nächstes aktiviert wird;
- erstellt und koordiniert begrenzte Codex-Sessions unter der passenden Authority;
- liest Handoffs und fordert fehlende Evidence nach;
- pflegt PR-Titel, Beschreibung, Labels, Abhängigkeiten, CI, Reviews und Konflikte;
- merged normale, bereits freigegebene und grüne Code-PRs;
- blockiert Deployment, destruktive Aktionen, Breaking Contracts, DB-Migrationen, Secrets, Proxmox und große Repo-Verschiebungen ohne request-spezifische Authority;
- führt Post-Merge- und Integrationsprüfungen aus;
- meldet Ergebnisse an Parent-Cockpit und User zurück;
- löscht keine Branches oder Worktrees unter Standing Autonomy.

## 9. Wellen und Abhängigkeiten

Cockpits werden kontrolliert nach Kapazität und Abhängigkeiten autonom aktiviert. Die Wellen sind eine Priorisierung, keine Verpflichtung zu serieller User-Interaktion.

| Welle | Cockpits | Zweck |
|---|---|---|
| 1 | `cockpit-git`, `cockpit-shared`, `cockpit-brain`, `cockpit-openfang`, `cockpit-deployment` | sichere Arbeits-, Vertrags-, Routing-, Execution- und Betriebsgrundlage |
| 2 | `cockpit-integration`, `cockpit-observability`, `cockpit-channels` | gemeinsame Evidence, Golden Paths und Eingänge |
| 3 | `cockpit-ideas`, `cockpit-bubbles`, `cockpit-minibook` | einfacher Daten-/UI-Referenzpfad und interne Projektion |
| 4 | `cockpit-coding`, `cockpit-desktop`, `cockpit-research`, `cockpit-rowboat` | langlebige Jobs, Aktionen, Quellen und Wissen |
| 5 | `cockpit-schedule`, `cockpit-flowzen`, `cockpit-mirofish`, `cockpit-marketing` | weitere fachliche MVPs auf der gemeinsamen Grundlage |
| 6 | `cockpit-n8n`, `cockpit-agentfarm`, `cockpit-video` | geschützte Audits und jeweils eigene Update-Spezifikation |

Welle 1 beginnt mit `cockpit-git`. Erst dieses Cockpit prüft die bestehende Repo- und Worktree-Landschaft sowie den geschriebenen Git-Governance-Plan gegen den Live-Zustand. Danach werden Shared und Brain einzeln vorbereitet; Deployment folgt auf den bestätigten Runtime- und Repo-Grenzen.

## 10. PR- und Merge-Modell

Cockpits erzeugen keine PRs. Implementierungs-Sessions liefern Handoffs an den Haupt-Orchestrator. Dieser integriert in folgender Grundreihenfolge:

```text
Git-/Session-Grundlage
-> Shared Contracts
-> Brain-Planvertrag
-> Brain/OpenFang Gateway
-> Application- oder Service-Änderung
-> OpenFang Space-Agent und Adapter
-> Superproject-Pin
-> Integration und Golden Path
-> Deployment-Konfiguration
-> freigegebenes Deployment
-> Release-Nachweis
```

Ein späterer Task darf nur auf gemergten oder ausdrücklich als gestapelt genehmigten Abhängigkeiten basieren. Stacked PRs müssen Basis sowie Rebase-/Merge-Reihenfolge explizit nennen.

## 11. Fehler- und Konfliktverhalten

- Fehlt ein Repository, Contract, Identifier oder Live-Zugang, meldet das Cockpit die Lücke und erfindet keinen Ersatz.
- Ist ein Worktree dirty oder ein Scope fremd belegt, bleibt die Analyse read-only und eskaliert an den Haupt-Orchestrator.
- Scheitert Remote-Authentifizierung, wird Remote-Parität als unbestätigt ausgewiesen.
- Ein Healthcheck, Mock, Skip oder statischer Registry-Eintrag ist kein Live-Golden-Path.
- OpenFang-Ausführung ist der erforderliche Product-Runtime-Pfad, gilt aber erst nach einem echten Agent-/Tool-Aufruf mit korreliertem Readback als live nachgewiesen.
- Session-Ergebnisse ohne Tests, Evidence oder vollständigen Handoff sind nicht merge-ready.
- Widersprechen sich Cockpits, entscheidet nicht eines der Cockpits; der Haupt-Orchestrator legt dem User die konkrete Architekturentscheidung vor.

## 12. Erfolgsbedingungen

Das Session-Portfolio ist betriebsbereit, wenn:

- alle 22 Cockpits eindeutig registriert sind;
- jedes Cockpit eine gültige Standing- oder request-spezifische Authority besitzt;
- jedes gestartete Cockpit seinen Repo-first Audit und Space Brief geliefert hat;
- kein Cockpit ungefragt Code oder Git-Zustand verändert hat;
- jeder Implementierungstask auf ein Parent-Cockpit, einen dauerhaften Request und eine gültige Authority verweist;
- Worktrees, Branches, Handoffs und PRs eindeutig zugeordnet sind;
- der Haupt-Orchestrator Abhängigkeiten und Merge-Reihenfolge nachweisbar pflegt;
- OpenFangs Execution-, Provider-, Cost-, Approval- und Evidence-Grenzen eindeutig dokumentiert und taskweise verifiziert sind;
- mindestens ein vollständiger Cockpit→Task→PR→Merge→Verifikation-Zyklus abgeschlossen ist.

## 13. Erster nächster Schritt

Nach Aufnahme dieses Designs koordiniert der Haupt-Orchestrator vorhandene sichere Cockpits und aktiviert Routine-Tasks autonom gemäß Abhängigkeiten, Kapazität und `standing-autonomy:v1`. Neue User-Owned-Cockpit-Threads bleiben bis zu einer individuellen, dauerhaft referenzierten User-Freigabe fail-closed. High-Risk-Arbeit bleibt bis zu request-spezifischer Authority fail-closed.
