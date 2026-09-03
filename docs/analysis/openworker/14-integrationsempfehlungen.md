# 14 — Integrationsempfehlungen

Jede Komponente wird genau **einer** Kategorie zugeordnet:

| Kategorie | Bedeutung |
|---|---|
| **A — Direkt übernehmen** | Code oder Mechanismus 1:1 portieren (MIT-Lizenz erlaubt es) |
| **B — Übernehmen und erweitern** | Konzept ist richtig, VibeMind braucht mehr |
| **C — Neu entwickeln** | OpenWorker reicht nicht; eigenes Design nötig |
| **D — Nicht übernehmen** | Bewusst verwerfen |

Lizenzlage: **MIT** — Portierung von Code ist zulässig, Copyright-Hinweis erforderlich.

---

## A — Direkt übernehmen

### A-1 · Inbox + Durable Approval

**Was:** `coworker/inbox.py`, der Approver-Pfad in `server/app.py:1489-1620`,
`engine.resume()` (`engine.py:250-292`).

**Warum:** Es löst vier Probleme gleichzeitig, die VibeMind sonst einzeln lösen müsste:
Genehmigung überlebt Verbindungsabbruch, überlebt Prozess-Neustart, ist von **jeder**
Oberfläche beantwortbar (GUI, REST, Slack-Button, nach Wiederaufnahme), und der
Zustandsautomat ist explizit anti-race (`pending → resolved`, idempotent,
first-responder-wins — `inbox.py:8-11`).

VibeMinds heutiger Stand (`mcp/docker/approval.py`) ist eine statische Env-Allowlist
ohne Laufzeitkanal. Für sensible Kategorien (HR, Bürgergeld, Security/Ops,
Marketing-Send) ist das zu wenig.

**Anpassungen für VibeMind:** Store auf Supabase statt JSON; `space`/`agent_id` als
zusätzliche Routing-Dimensionen; Kanäle um Telegram/Web-Push erweitern.

→ [ADR-0001](adr/ADR-0001-inbox-governance.md)

### A-2 · Risikoklassifikation (`risk.py`)

**Was:** Vier Klassen (`READ`/`WRITE_LOCAL`/`EXEC`/`EXTERNAL`), ein `classify()`,
Override-Resolver. 58 Zeilen.

**Warum:** Die Trennung `WRITE_LOCAL` (reversibel, lokal) vs. `EXTERNAL` (irreversibel,
außerhalb) ist genau der Schnitt, der entscheidet, was im unbeaufsichtigten Betrieb
gefragt werden muss.

**Eine Änderung ist Pflicht:** Default auf **fail-closed** drehen —
`UNKNOWN → EXTERNAL` statt `→ READ` ([08 R-06](08-security-risikoanalyse.md#r-06)).

→ [ADR-0002](adr/ADR-0002-risk-klassifikation.md)

### A-3 · Cancellation-Invarianten

**Was:** `request_interrupt()` + `_interruptible()` + `_interrupted_tool()` +
Interrupt-Hooks (`engine.py:120-148, 504-515`).

**Warum:** Barge-in *ist* Cancellation. Ohne die Invariante „jeder ausstehende
`tool_call` bekommt eine Antwort" bricht sowohl die Provider-Kompatibilität (Templates
lehnen verwaiste Calls ab) als auch die Wiederaufnahme.

→ [ADR-0003](adr/ADR-0003-cancellation-invarianten.md)

### A-4 · Shell-Allowlist-Härtung

**Was:** `_has_shell_operators()` + `shlex`-Token-Präfix-Matching
(`permissions.py:21-25, 216-238`).

**Warum:** Die naive Präfix-Prüfung (`git status` erlaubt `git status && rm -rf ~`)
ist ein Fehler, den man einmal macht. Hier ist er bereits behoben und getestet.

### A-5 · Persistente Shell mit Marker-Protokoll

**Was:** `LocalExecutor` (`tools/shell.py`) — Marker-Trailer für Exit-Code + CWD,
Timeout mit Interrupt-und-Resync, Self-Healing-Respawn, Tail-Trunkierung,
detachte Hintergrundtasks.

**Warum:** Zustandsbehaftete Shell ist für Entwicklungsarbeit essenziell (`cd`, venv,
`export`). Die Windows-Variante ist mitgeliefert und dokumentiert.

**Anpassung:** Die `Executor`-ABC füllen — `ContainerExecutor` als **Default**.

→ [ADR-0006](adr/ADR-0006-shell-executor.md)

### A-6 · `_display`-Sidecar (Informationsfluss-Trennung)

**Was:** `engine.py:642-670` — Tool-Result-Metadaten, die die UI sieht und das Modell
nicht.

**Warum:** Für VibeMind mit HR-/Bürgergeld-Kategorien ist „Filterinformationen dürfen
den Agenten nicht erreichen" eine echte Anforderung, keine Feinheit.

### A-7 · Sidecar-Muster für Nachrichten

**Was:** `source`, `ts`, `reasoning`, provider-private `extras` reisen auf der
Nachricht mit und werden in `_outbound_messages()` abgestreift; `notice`-Rollen sind
rein anzeigeseitig (`engine.py:878-901`).

**Warum:** Erlaubt eine reiche UI-Historie ohne Verschmutzung des Modellkontexts —
und macht Modellwechsel mitten in der Session verlustfrei.

### A-8 · `_SNAPSHOT_JS` (Browser-Wahrnehmung)

**Was:** `browser_automation.py:270-311` — Text + sichtbare Controls + `selectorHint`.

**Warum:** Kompakteste bekannte Seitenrepräsentation für ein LLM, <40 Zeilen.
Nach OpenClaw portierbar.

### A-9 · `COWORKER_STATE_DIR`-Muster

**Was:** Ein Env-Override isoliert den gesamten Zustandsbaum (`secrets.py:36-38`).

**Warum:** Macht Integrationstests trivial. Genau der Grund, warum OpenWorker 881 Tests
ohne Mocking-Framework hat.

### A-10 · Artefakt-Links im Antworttext

**Was:** Der Cowork-Prompt fordert am Antwortende das Literal
`[Titel](artifact:<relativer-pfad>)` (`agents/cowork.py:29-31`); die Oberfläche rendert
daraus einen Ein-Klick-Öffner (`/v1/sessions/{id}/artifacts/read` + `…/reveal`).

**Warum:** Löst „Deliverable statt Chat" mit minimalem Aufwand — ein Prompt-Satz plus
ein Renderer. Für VibeMind, dessen Aufträge Artefakte erzeugen sollen, direkt relevant;
per Sprache wird daraus „Der Bericht liegt bereit — soll ich ihn öffnen?".

### A-11 · Kommentarkultur

**Was:** Kommentare erklären das *Warum* und nennen den Incident samt Datum
(z. B. `engine.py:240-242`: „owner-hit 2026-07-23").

→ [ADR-0016](adr/ADR-0016-kommentarkultur.md)

---

## B — Übernehmen und erweitern

### B-1 · Permission-Engine → **Policy Engine**

| OpenWorker | VibeMind-Erweiterung |
|---|---|
| 5 Modi × 4 Risikoklassen | + **Space-Dimension** (jeder VibeMind-Space hat eigene Obergrenzen) |
| Pfad-Scoping für Writes | + **Egress-Scoping** (welche Domains/Kanäle je Space) |
| Session-Allowlists | + **Rollen-Scoping** (Planner darf anderes als Worker) |
| — | + **Taint-Level**: nach Konsum von Fremdinhalt sinkt die effektive Autonomie |
| — | + **Kosten-/Rate-Budget** pro Space und Automation |

**Warum erweitern statt übernehmen:** OpenWorkers Engine kennt eine Session mit einem
Agenten. VibeMind hat Spaces × Agenten × Rollen × Quellen.

### B-2 · Standing Rules → **Scoped Grants mit TTL**

Übernehmen: Bindung an *exaktes Ziel*, nur `EXTERNAL`, Regel lebt auf dem Task-Record,
fail-closed-Validierung, Audit zitiert die Regel.

Ergänzen: **TTL** (90 Tage), **Rate-Limit** (n/Tag), **Inhaltsklasse** statt nur Ziel,
**Widerruf-UI** über alle Automations hinweg.

→ [ADR-0005](adr/ADR-0005-standing-rules.md)

### B-3 · Persona-/Skill-Format → **VibeMind Agent Manifest**

Übernehmen: Markdown + YAML-Frontmatter, `persona ⊇ skill`, strikte Validierung,
Progressive Disclosure, Capability-IDs statt Tool-Listen, `recommends` für Connectoren.

Ergänzen: `space`, `role` (planner/worker/reviewer), `model_policy` (welches Modell für
welche Phase), `budget`, `escalation` (an wen bei Blockade), **`allowed_tools` mit
echter Durchsetzung**, Signatur/Provenienz für Drittinstallation.

→ [ADR-0009](adr/ADR-0009-skill-persona-format.md)

### B-4 · Memory-Governance → **Semantic Memory**

Übernehmen: `_MEMORY_GUIDANCE` (fünf Regeln), ID-sichtbares Format `[#7]`,
`context_provider()`-Hook als Injektionspunkt.

Ersetzen: den Store (siehe C-3).

→ [ADR-0008](adr/ADR-0008-memory-architektur.md)

### B-5 · Automation-Modell → **Workflow-Trigger**

Übernehmen: `ScheduledTask` mit eigenem Thread, eigenem Arbeitsordner, Run-Historie,
„run-once-catch-up", „skip-on-overlap".

Ergänzen: Event-Trigger (nicht nur Cron), Bedingungen, n8n-Kopplung, verteilte
Ausführung mit Leader-Election (Swarm), Retry-Policy pro Task.

### B-6 · MCP-Client → **MCP-Federation + Server-Modus**

Übernehmen: Async-Lifecycle-Lösung (eine Task besitzt enter+exit), Nicht-Hijack-OAuth,
`include_tools`/`exclude_tools`.

Ergänzen: Resources + Prompts + Sampling; **Risk-Level pro Tool** statt pro Server;
Namespace-Hierarchie statt 64-Zeichen-Abschnitt; Health-Check + Reconnect;
**VibeMind als MCP-Server** (Fähigkeiten nach außen anbieten).

→ [ADR-0013](adr/ADR-0013-mcp-federation.md)

### B-7 · Audit → **Governance-Log mit Provenienz**

Übernehmen: Stage-basiertes Schema, Invariante „jeder auto-erlaubte Call zitiert seine
Regel", Filter-Ereignisse ohne Inhalt.

Ergänzen: **Provenienz** (welcher Input hat den Call ausgelöst, war Fremdinhalt im
Kontext), Kosten pro Call, Korrelations-IDs über Agenten hinweg, Export nach
Supabase mit Retention-Policy.

### B-8 · Event-Taxonomie → **Event Bus**

Übernehmen: die 15 Event-Typen als Vokabular — sie sind gut geschnitten.

Ergänzen: `TOOL_OUTPUT_DELTA`, `PLAN_*`, `AGENT_SPAWNED/FINISHED`, `HANDOFF`,
`BUDGET_WARNING`, `TAINT_RAISED`; echter Publish/Subscribe über Redis statt
UI-Broadcast; Events als **Zustandsquelle**, nicht nur Benachrichtigung.

→ [ADR-0004](adr/ADR-0004-event-taxonomie.md)

---

## C — Neu entwickeln

### C-1 · Voice Pipeline

**Warum OpenWorker nicht reicht:** Push-to-Talk, Batch-Transkription, Englisch,
kein TTS, kein Wake-Word, kein Barge-in, an Tauri gebunden. Die *Architektur* ist auf
Batch ausgelegt — Streaming wäre keine Ergänzung, sondern eine Neuimplementierung.

→ [ADR-0010](adr/ADR-0010-voice-pipeline-neuentwicklung.md)

### C-2 · Planner

**Warum OpenWorker nicht reicht:** Es gibt keinen. `propose_plan` ist ein
Genehmigungs-Tool ohne Zerlegung, ohne Abhängigkeiten, ohne Replanning.

→ [ADR-0011](adr/ADR-0011-planner-neuentwicklung.md)

### C-3 · Semantic Memory + Memory Graph

**Warum OpenWorker nicht reicht:** SQLite-Tabelle ohne Index, alle Einträge im
Systemprompt, keine Embeddings, keine Relationen, kein Verfall, keine Provenienz.
Ab ~100 Einträgen unbrauchbar.

→ [ADR-0008](adr/ADR-0008-memory-architektur.md)

### C-4 · Multi-Agent-Runtime

**Warum OpenWorker nicht reicht:** Ein read-only `explore`-Subagent ist
Context-Offloading, kein Multi-Agent-System. Kein A2A-Protokoll, keine Rollen, keine
Koordination, keine schreibenden Subagenten.

**Was mitgenommen wird:** Das Isolationsmodell des Subagenten (Rechte strukturell,
nicht per Prompt begrenzt).

→ [ADR-0012](adr/ADR-0012-multi-agent-runtime.md)

### C-5 · Worker Pool

**Warum OpenWorker nicht reicht:** `asyncio.to_thread` auf dem Default-Executor,
ungebunden, ohne Queue, ohne Priorität, ohne Backpressure.

→ [ADR-0014](adr/ADR-0014-worker-pool.md)

### C-6 · Sandboxing / Execution Isolation

**Warum OpenWorker nicht reicht:** Existiert nicht — nur die leere `Executor`-ABC.

→ [ADR-0006](adr/ADR-0006-shell-executor.md)

### C-7 · Prompt-Injection-Abwehr (Taint-Tracking)

**Warum OpenWorker nicht reicht:** Ein Satz im Systemprompt ist keine Abwehr.

→ [ADR-0015](adr/ADR-0015-taint-tracking.md)

### C-8 · Tool-Retrieval + Namespaces

**Warum OpenWorker nicht reicht:** Flache Registry, alle Schemas immer, stilles
Überschreiben bei Namenskollision.

→ [ADR-0007](adr/ADR-0007-tool-registry-namespaces.md)

### C-9 · Kontext-Management

**Warum OpenWorker nicht reicht:** Keine Kompaktierung, unbegrenztes Wachstum,
Tool-Results inline bis 20 k Zeichen.

**Nötig:** Sliding Window + hierarchische Summaries + Artefakt-Handles + Token-Budget
pro Turn + bewusstes Prompt-Caching.

→ [ADR-0017](adr/ADR-0017-kontext-management.md)

---

## D — Nicht übernehmen

| Komponente | Begründung |
|---|---|
| **`SessionManager`** | 3.766-LOC-God-Object. Entstanden aus fehlendem Event-Bus. VibeMind hat einen — die Koordination gehört dorthin, nicht in eine Klasse. |
| **Connector-Monolith** (33 Connectoren, 4.892 LOC) | Geschlossener Katalog, nur upstream erweiterbar. VibeMind nutzt n8n + MCP als Integrationsschicht. Der Wartungsaufwand für 33 SaaS-APIs ist nicht rechtfertigbar. |
| **`SecretStore` (Klartext-JSON)** | Keine Verschlüsselung at rest. VibeMind braucht OS-Keystore bzw. Vault. Das *Interface* ist brauchbar, die Implementierung nicht. |
| **`SQLiteMemoryStore`** | Trivial, ohne Index, ohne Suche. Nachbau günstiger als Portierung. |
| **React/Tauri-GUI** | VibeMind hat Electron + Next.js. Nur UX-*Muster* übernehmen. |
| **`ocw-stt`** | Batch, Englisch, Push-to-Talk. Falsche Architektur. |
| **Browser-Singleton** | Architekturfehler (keine Session-Isolation). OpenClaw existiert bereits. |
| **`aisuite`-Abhängigkeit** | Git-Commit-Pin, kein PyPI-Release. Schema-Ableitung ist ~50 Zeilen selbst geschrieben. Keine Abhängigkeit auf ein unveröffentlichtes Paket eingehen. |
| **`/v1/chat/completions`-Proxy** | Nette Idee, aber für VibeMind irrelevant — und sie umgeht die eigene Governance-Schicht. |
| **Flache Tool-Registry** | Siehe C-8. |
| **Cron-only-Scheduler** | n8n und der VibeMind-Scheduler decken das ab. |
| **Textual-TUI, CLI** | Kein Bedarf. |

---

## Übersicht

| Kategorie | Anzahl | Anteil des Codes | Geschätzter Portierungsaufwand |
|---|---|---|---|
| **A — Direkt** | 11 | ~2.500 LOC | 2–3 Wochen |
| **B — Erweitern** | 8 | ~2.000 LOC Basis | 6–10 Wochen |
| **C — Neu** | 9 | — | 6+ Monate |
| **D — Verwerfen** | 11 | ~18.000 LOC | — |

**Das Verhältnis ist die Kernaussage:** Von ~25.000 LOC Backend sind **~4.500 LOC
(18 %) übernehmenswert** — und diese 18 % sind fast vollständig die
**Governance-Schicht**, nicht die Agenten-Intelligenz.

---

**Weiter:** [15 — Architekturvergleich](15-architekturvergleich.md)
