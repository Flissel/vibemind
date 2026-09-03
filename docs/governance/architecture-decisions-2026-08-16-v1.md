# V1 Architekturentscheidungen — 2026-08-16 (Entscheidungsrunde 2, Block Research)

**Status:** entschieden, umsetzungspendent
**Referenz:** `claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-16T15:45:00Z`
**Anlass:** Das Cockpit `cockpit-research` hatte drei Gates eskaliert. Aus der Klärung mit dem User ist mehr geworden als die Beantwortung dieser drei Fragen: eine **verbindliche Definition dessen, was der Research-Space ist**. Dieses Dokument setzt die E-Nummerierung fort (2026-08-13: E1–E5; 2026-08-15: E6–E8) und hält den Research-Block als E9–E13 fest.

Dieses Dokument ändert selbst **keine** Registry, keinen Vertrag und keine Laufzeit. Umsetzung erfolgt ausschließlich in den abgeleiteten, separat geprüften Tasks.

## Ausgangslage (Orchestrator-Evidence, repo-first erhoben)

| Befund | Beleg |
|---|---|
| **Der Research-Space ist heute nicht ausführbar.** Das generierte Manifest deklariert `mcp_servers = ["vibemind-db", "fetch", "qdrant"]`, gibt dem Agenten aber nur `tools = ["memory_store", "memory_recall"]`. Alle sechs `research.*`-Events binden auf Werkzeuge, die der Agent nicht besitzt. | `vibemind-os/openfang/agents/brain-researcher/agent.toml:7`, `:52` |
| Ursache ist ein dokumentierter Fail-closed-Mechanismus: ohne `mcp_tools` leitet der Generator **keine** Tools ab; Research hat `mcp_tools: {}`. | `vibemind-os/config/space_agent_registry.yml:30-38` (Kommentar im Bubbles-Block), `sync_openfang_agents.py:86`, Authority-Contract `spaces.research.mcp_tools` |
| Das Modell des Agenten ist für Deep Research zu klein dimensioniert (`gpt-4o-mini`, `max_tokens = 4096`). | `vibemind-os/openfang/agents/brain-researcher/agent.toml` `[model]` |
| OpenFang bringt einen gebundelten **Researcher Hand** mit: autonome Tiefenrecherche mit Settings `research_depth` (quick/thorough/exhaustive) und `output_style` (brief/detailed/**academic** mit Zitaten/executive), Werkzeuge inklusive `web_search`, `web_fetch`, `knowledge_*`, `schedule_*`, `event_publish`. | `openfang/crates/openfang-hands/bundled/researcher/HAND.toml` |
| Der Hand bringt eine Fünf-Phasen-Methodik als Prompt-Skill mit; Phase 1 lautet ausdrücklich „identify what's known vs unknown". | `openfang/crates/openfang-hands/bundled/researcher/SKILL.md` |
| Das Hands-Modell ist ausdrücklich asynchron: „Unlike regular agents (you chat with them), Hands work for you (you check in on them)." | `openfang/crates/openfang-hands/src/lib.rs:3-5` |
| OpenFang kann OpenClaw-Skills laden. | `openfang/crates/openfang-skills/src/openclaw_compat.rs` |
| **Bubble-Daten fließen nach Rowboat — als einmaliger, fail-silenter Publish, nicht als Sync.** `_publish_to_rowboat()` schreibt angereicherte `.md`-Dateien je Bubble, feuert nur beim Wizard-Abschluss, steckt vollständig in `try/except` und lässt den Abschluss auch bei Fehlschlag als erfolgreich gelten. Kein Rückkanal, kein Nachfluss bei späteren Änderungen. | `vibemind-os/spaces/shuttles/wizard_handler.py:322-325`, `:549-576` |
| **Rowboat ist abfrageseitig ebenfalls nicht verdrahtet.** `rowboat.search`/`rowboat.query` binden auf `search_knowledge`/`query_knowledge`; das Manifest führt nur `memory_store`, `memory_recall`, die Status-Probe und `shell_exec`. Die Implementierung existiert, ist aber nicht über MCP freigegeben. | `openfang/agents/rowboat-chat/agent.toml:52`, `vibemind-os/spaces/rowboat/mcp_server.py`, `spaces/rowboat/tools/roarboot_client.py` |
| Bubbles sind Ideen-Cluster; der Bubbles-Agent besitzt eine eng gefasste Tool-Allowlist. | `vibemind-os/config/space_agent_registry.yml:21-39` |

## E9 — Research→Idea-Persistenz: über die spaces-ideas-Autorität

**Frage:** `research.summarize` und `research.to_idea` binden auf `db_ideas_update`/`db_ideas_create` des breiten `vibemind-db`-Servers und damit am Authority-Contract des Ideas-Golden-Path vorbei.

**Entscheidung (User):** Der Schreibpfad wird auf **`spaces-ideas`** umgestellt — eine Schreib-Autorität je Datendomäne.

**Präzisierung durch den Evidence-Befund:** Es handelt sich **nicht** um eine Migration eines laufenden Pfades. Da `brain-researcher` gar keine DB-Werkzeuge besitzt, ist der heutige Schreibpfad nicht ausführbar. E9 ist damit die **erstmalige korrekte Verdrahtung**, nicht ein Umbau — das senkt Risiko und Aufwand erheblich und macht die frühere Auflage „erst nach bewiesenem Durchstich" gegenstandslos: es gibt nichts, was währenddessen brechen könnte.

## E10 — Privilege-Scoping: Ownership bei `cockpit-research`

**Entscheidung (User):** Der Task, der die Tool-Allowlist des Research-Space definiert, gehört `cockpit-research`.

**Auflage:** Das Allowlist-**Vokabular** bleibt das des MCP-Authority-Contracts (`task-integration-0005a`, gemerged in #162). Research definiert seinen Scope, erfindet aber keine eigene Scoping-Mechanik.

## E11 — Definition des Research-Space: zwei Dienstgrade, ein Subjekt-Modell

**Der Research-Space ist das allgemeine Recherche-Feature von VibeMind.** Er wird in **zwei Dienstgraden** erbracht, weil zwei unvereinbare Ausführungsformen vorliegen — ein synchroner Tool-Aufruf gegenüber einem langlaufenden autonomen Job:

1. **Lookup (synchron).** `research.web`, `research.scrape` — ein Werkzeugaufruf, Sekunden, keine Persistenz. Die heutige Form; sie muss lediglich verdrahtet werden.
2. **Deep Research (asynchroner Job).** Getragen vom **OpenFang Researcher Hand**. Die Parameter `depth` und `output_style` sind **keine Neuerfindung**, sondern die bereits vorhandenen Hand-Settings; sie werden gebunden, nicht nachgebaut. Der Job liefert sofort eine Referenz, ist zwischenzeitlich abfragbar und meldet sich bei Fertigstellung.

**Subjekt-Modell.** Jede Anfrage nennt ein Subjekt: `topic` (Freitext), `idea` (eine Idee — deren Titel und Body werden zur Fragestellung, das Ergebnis reichert die Idee an) oder `bubble` (ein Ideen-Cluster). Dies ersetzt die heutigen Ad-hoc-Parameter (`query`, `title`, `idea_id`).

**Offen und ausdrücklich nicht entschieden:** (a) ob ein Bubble-Subjekt einen übergreifenden Report oder je Idee einen Report erzeugt; (b) wo ein Report physisch lebt (Idee mit langem Body gegenüber Kurzfassung plus verlinktem Artefakt). Beides legt der Definitions-Task als Entscheidungsvorlage vor.

**Evidence-Disziplin bleibt fail-closed.** `spaces/research/execution_target.py` verwirft heute schon Antworten ohne Quell-URL. Für Deep-Runs gilt verschärft: ein Report ohne Zitate ist ein fehlgeschlagener Lauf.

## E12 — Rowboat: Referenzquelle für Bubble-Daten, nicht Assoziations-Eigentümer

**Frage:** Der User hat vorgeschlagen, Rowboat als Datenquelle für Deep Research zu nutzen, da Bubble-Daten dort vorliegen.

**Entscheidung (User):** **Ja — Rowboat wird Referenzquelle für Bubble-Daten.** Recherchiert Deep Research ein Bubble- oder Idee-Subjekt, liest es zuerst die zu dieser Bubble publizierten Rowboat-Dokumente als Kontext („was wissen wir schon?") und geht erst für die Lücken nach außen. Das entspricht exakt Phase 1 der Hand-Methodik.

**Zwei Rollen, die getrennt bleiben.** Rowboat ist **Input** (Kontext), nicht **Output** (Assoziations-Speicher). Die Aussage „Report R gehört zu Idee 42 in Bubble 7" gehört zur Ideas-Datenhoheit, weil dort die Objekte wirklich leben; Rowboat führt nur best-effort befüllte Kopien. OpenFangs Memory-KG bleibt Arbeitsgedächtnis während eines Laufs, nicht Dauerspeicher.

**Verbindliche Auflage — fail-open auf Kontext, fail-closed auf Evidence.** Da der Rowboat-Publish einmalig und fail-silent ist, darf Deep Research **nicht** davon abhängen: Fehlt der Kontext oder ist Rowboat nicht erreichbar, läuft die Recherche web-only weiter und **vermerkt im Report, dass ohne internen Kontext gearbeitet wurde**. Ein stiller Verzicht ist unzulässig. Die Evidence-Regel aus E11 bleibt davon unberührt fail-closed.

## E13 — Reihenfolge: Web-first, Rowboat additiv (Variante B)

**Entscheidung (User):** Deep Research startet mit Web-Recherche und dem Subjekt-Modell; die Rowboat-Referenzquelle dockt an, sobald sie verdrahtet ist.

**Begründung:** Rowboat ist beidseitig unverdrahtet (Publish unzuverlässig, Query nicht freigegeben). Würde Deep Research darauf warten, stünde es bis zur vollständigen Rowboat-Reparatur still. Web-first liefert früh einen prüfbaren Report und beantwortet die Frage, ob der Hand überhaupt brauchbare Ergebnisse liefert, bevor weitere Abhängigkeiten entstehen. Die Rowboat-Arbeit ist ohnehin eigenständig wertvoll, da der Knowledge-Graph-Space auch für sich genommen unverdrahtet ist.

## E14 — Report-Ablageort: eigene Artefakt-Tabelle per DB-Migration (D1)

**Referenz:** `claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-17T07:02:00Z`

**Entscheidung (User):** Für die Ablage eines Deep-Research-Reports wird die **Artefakt-Variante** gewählt — eine eigene Tabelle über eine **DB-Migration**, nicht der lange Body in `ideas.description`.

**Lesart des Orchestrators, offengelegt:** Die Antwort des Users lautete auf die Vorlage D1 knapp „Db Migration". Der Orchestrator liest das als Option B aus `docs/spaces/research/deep-research-open-decisions-v1.md` — Kurzfassung in der Idee, Report als verlinktes Artefakt in eigener Tabelle. Trifft diese Lesart die Absicht nicht, ist E14 vor Umsetzungsbeginn zu korrigieren.

**Begründung, die für diese Variante spricht:** Der Sync-Trigger `emit_ideas_sync_event()` schreibt bei **jeder** Änderung an `public.ideas` die komplette Zeile in die Outbox (`20260610_ideas_sync_triggers.sql`). Ein Paper in `description` würde bei jedem späteren Feld-Update erneut vollständig durch die Outbox geschleust. Die Artefakt-Tabelle entkoppelt das.

**Verbindliche Stufung, weil `database-migration` eine Fail-closed-Klasse ist:**

1. **Stufe 1 (Repository):** Die Migration wird **geschrieben**, nicht angewendet — Migrationsdatei, Schema-/Contract-Nachführung, Tests, Rückfallweg. Dazu gehört ein belegter Vorschlag, ob und wie das Artefakt in die bestehende Ideas-Rowboat-Sync-Kette eingebunden wird oder bewusst außerhalb bleibt.
2. **Stufe 2 (Anwendung):** Das Einspielen gegen eine echte Datenbank ist eine Live-Aktion des Users und von dieser Entscheidung **nicht** gedeckt. Vor dem Einspielen ist zu klären, ob die Migration idempotent und rückrollbar ist.

**Weiterhin offen:** **D2** (Bubble-Fan-out — ein übergreifender Report gegenüber einem Report je Idee) ist mit dieser Antwort **nicht** entschieden und bleibt Entscheidungsvorlage.

## E15 — Rowboat-Verdrahtung: zurückgestellt

**Referenz:** dieselbe Nachricht.

**Entscheidung (User):** Die Rowboat-Verdrahtung (Query-Freigabe, Publish-Zuverlässigkeit) wird **zurückgestellt**. E12 bleibt als Zielbild gültig und ungeändert; die Reihenfolgeentscheidung E13 (web-first) trägt genau diesen Fall. Solange Rowboat unverdrahtet ist, greift die E12-Auflage **fail-open auf Kontext mit Vermerkpflicht im Report** — Deep Research läuft web-only und hält fest, dass ohne internen Kontext gearbeitet wurde.

## Weiterhin offen (nicht in diesem Block entschieden)

- **Die beiden `openclaw.*`-Events** (`openclaw.research`, `openclaw.compare`) hängen im Research-Space, obwohl dieser nur `research.` deklariert, und binden auf den simplen `fetch`-Pfad. OpenClaw hat perspektivisch **zwei getrennte Rollen**: als **Kanal** (Trigger von außen, gehört zur offenen Kanal-Klassifikation E5) und als **Skill-Quelle** für den strukturellen Paper-Aufbau (technisch möglich über `openclaw_compat.rs`). Beide bleiben offen; die Trennung ist hiermit festgehalten, damit sie nicht weiter vermischt werden.
- **Report-Ablageort** und **Bubble-Fan-out-Semantik** (siehe E11).

**Nicht weiterverfolgt:** Der Fork `Flissel/open-deep-research` (Next.js/Firecrawl-Klon, unverändert seit 2025-02) wird **nicht** integriert; OpenFang deckt den Recherche-Loop nativ und tiefer ab. Er bleibt Referenz für das Extract-Muster.

## Abgeleitete Tasks

| Task | Entscheidung | Parent-Cockpit | Risiko | Stufe |
|---|---|---|---|---|
| `task-research-0001-agent-tool-enablement-v1` | E9, E10 (Task Null: dem Agenten überhaupt Werkzeuge geben) | `cockpit-research` | `code` | 3 |
| `task-research-0002-space-definition-contract-v1` | E11, E12, E13 (Definition, Subjekt-Modell, Event-Schnitt, Entscheidungsvorlagen) | `cockpit-research` | `code` | 2 |
| Rowboat-Verdrahtung (Publish-Zuverlässigkeit, Query-Freigabe) | E12-Voraussetzung | `cockpit-rowboat` | `code`, pendent | offen |
| Deep-Research-Anbindung an den Hand | E11 Dienstgrad 2 | `cockpit-research` | nach 0001/0002 | offen |
