# 10 — Backend

---

## 10.1 Die Manager-Monolith-Frage

`coworker/server/manager.py` — **3.766 LOC, ~150 Methoden, eine Klasse.**

`SessionManager` besitzt und koordiniert:

```
Engines (dict[session_id → TurnEngine])   ProviderRouter        SecretStore
ConversationStore                          MemoryStore           InboxStore
InboxRouting                               UnattendedRegistry    AuditStore
TaskStore + Scheduler                      Gateway (Messaging)   MCPManager
PersonaRegistry                            SkillLoader           WorkspaceTrustStore
SubscriptionStore + ChannelBuffer          MentionSessionStore   WakeStore
ParkedStore                                UnroutedStore         SessionConnectionStore
PersonaConnectionStore                     Browser-Steuerung     Preferences
```

Verantwortungsbereiche in einer Klasse (aus den Methodennamen abgeleitet):

| Bereich | Methoden ca. |
|---|---|
| Session-/Engine-Lifecycle | 15 |
| Connector-Verwaltung (connect/disconnect/status/accounts/filters) | 35 |
| MCP-Verwaltung | 10 |
| Provider-/Modell-Einstellungen | 20 |
| Automations (CRUD, Run, Finalize, Notify) | 15 |
| Inbox/Approval/Standing Rules | 12 |
| Messaging-Gateway, Mentions, Routing | 15 |
| Workspace/Roots/Artefakte/Trust | 15 |
| Persona-Verwaltung | 8 |
| Sonstiges (Prefs, Ollama-Probing, Autotitle, Broadcast) | 10 |

**Das ist ein God-Object.** Die Datei ist der klare Kandidat für eine Zerlegung in
`SessionService`, `ConnectorService`, `AutomationService`, `MessagingService`,
`SettingsService` — jeweils mit eigenem Zustand und schmalem Vertrag.

**Warum es so gekommen ist** (nachvollziehbar): Der Manager ist die einzige Stelle, an
der *alle* Stores zusammenlaufen, und viele Operationen sind echt querschnittlich —
„Connector deaktivieren" muss laufende Engines invalidieren, „Persona ändern" muss
Session-Verbindungen neu berechnen, „Automation läuft" muss Inbox, Scheduler, Engine und
Broadcast koordinieren. Ohne Event-Bus landet diese Koordination zwangsläufig in einer
zentralen Klasse.

**Das ist die Lehre für VibeMind:** Ein Event-Bus ist keine Architektur-Zierde, er ist
das, was verhindert, dass Querschnittskoordination in ein God-Object kollabiert.

---

## 10.2 Modulschnitt

**Gut geschnitten** (klarer Zweck, schmale Schnittstelle, testbar):

| Modul | Warum gut |
|---|---|
| `engine.py` | Ein Zweck, injizierte Abhängigkeiten, kein Wissen über Server |
| `permissions.py` + `risk.py` | Reine Entscheidungslogik, keine Seiteneffekte |
| `tools/*` | Fabrikfunktionen `→ list[Callable]`, kein globaler Zustand |
| `providers/*` | ABC + Implementierungen + Router |
| `memory/*` | ABC + ein Adapter |
| `inbox.py` | Zustandsautomat mit expliziter Anti-Race-Vertragsdoku |
| `skills/`, `personas/`, `catalog.py` | Datengetrieben, klar |

**Schlecht geschnitten:**

| Modul | Problem |
|---|---|
| `server/manager.py` | God-Object (oben) |
| `connectors/integration_tools.py` | 4.892 LOC, 33 Dienste in einer Datei |
| `connectors/descriptors.py` | 1.470 LOC Datentabelle |
| `server/app.py` | 1.968 LOC, 120+ Routen ohne `APIRouter`-Gliederung |

FastAPI bietet `APIRouter` für genau diese Aufteilung; es wird nicht genutzt. Alle
Routen sind Closures innerhalb von `create_app(manager)` — was den Zugriff auf `manager`
bequem macht, aber die Datei unteilbar.

---

## 10.3 Dependency Injection

**Es gibt keinen DI-Container** — und das ist eine bewusste, gute Entscheidung. Statt
dessen: **Konstruktor-/Parameter-Injektion durchgereicht.**

`agent.py:109-136` — `build_engine()` nimmt **27 Keyword-Argumente**:

```python
agent, workspace, model, mode, approver, provider, allowed_commands,
max_iterations, model_settings, memory_store, messages, extra_tools, secrets,
task_store, wake_store, session_id, audit_sink, roots, directory_requester,
plan_approver, question_asker, subscription_store, channel_buffer,
routing_targets, connector_filter
```

**Vorteile:** Alles explizit, kein Magie-Container, im Test trivial ersetzbar —
`tests/` nutzt genau das durchgehend, und das ist der Grund, warum 881 Tests ohne
Mocking-Framework auskommen.

**Nachteile:** 27 Parameter sind das Signal, dass eine Ebene fehlt. Die vier
Callback-Parameter (`approver`, `directory_requester`, `plan_approver`,
`question_asker`) sind alle dasselbe Konzept — „so erreichst du den Menschen" — und
gehörten in ein `HumanInterface`-Protokoll. Ebenso: `task_store`, `wake_store`,
`subscription_store`, `channel_buffer`, `memory_store`, `secrets` gehörten in einen
`SessionContext`.

**Für VibeMind:** Das Muster (explizite Injektion, kein Container) übernehmen, aber
**Parameterobjekte** statt flacher Argumentlisten.

---

## 10.4 Testbarkeit

**881 Testfunktionen in 82 Dateien.** Das ist die zweitstärkste Eigenschaft des Repos.

**Was die Testbarkeit ermöglicht:**
- Keine Singletons in der Runtime (Ausnahme: `_BROWSER` — und genau das ist die
  am schlechtesten testbare Komponente).
- Stores nehmen einen Pfad; Tests nutzen `tmp_path` oder `:memory:`.
- `SQLiteMemoryStore(":memory:")` funktioniert direkt.
- `COWORKER_STATE_DIR` als Env-Override (`secrets.py:36-38`) — Tests isolieren den
  gesamten Zustandsbaum mit einer Variable.
- Der Provider ist ein ABC; ein Fake-Provider ist zehn Zeilen.
- **FakeSlack** (`coworker/testing/fake_slack/`) treibt den *echten* slack-bolt-Handler
  in-process. Kein Netz, keine HTTP-Mocks, echter Codepfad.

**Testthemen als Incident-Archäologie:** `test_durable_resume`, `test_engine_stop`,
`test_wake_resume`, `test_standing_approvals`, `test_slack_approval_owners`,
`test_risk_overrides`, `test_connectors_allowlist`, `test_multiroot`,
`test_message_timestamps`, `test_send_target_resolution`. Jeder dieser Namen ist ein
Bug, der Produktion erreicht hat und dann festgenagelt wurde.

**Lücken:**
- **Kein Coverage-Reporting** in CI.
- **Keine Property-based Tests** — für die Permission-Engine (Mode × Risk × Pfad ×
  Allowlist × Rule) wäre Hypothesis ideal; die Kombinatorik ist groß und die
  Fehlerkosten hoch.
- **Keine Last-/Nebenläufigkeitstests** — z. B. zwei Sessions, die gleichzeitig den
  Browser-Singleton nutzen.
- **Keine Contract-Tests** Frontend↔Backend (Typ-Drift, siehe [09](09-frontend.md#93-komponentenstruktur)).

---

## 10.5 Wartbarkeit

### Was die Wartbarkeit deutlich hebt

**Die Kommentarkultur.** Kommentare erklären hier durchgehend **warum**, nicht was:

> „An allowlist entry auto-runs a command WITHOUT approval, so prefix matching is
> unsafe: `git status` would auto-approve `git status && rm -rf ~`."
> — `permissions.py:217-219`

> „Windows has no such bits — `os.chmod` there only toggles the read-only flag, so a
> 0600 chmod is a silent no-op and the file inherits broad ACLs."
> — `secrets.py:61-66`

> „A directory grant MUST be inheritable … Without these flags, `/inheritance:r` leaves
> the directory with a non-inheritable ACE and any child file ends up with an empty DACL
> → sqlite3 'unable to open database file', crashing the server on launch."
> — `secrets.py:72-77`

> „Trailing model_switch notices don't break the guard — switching models and THEN
> retrying is the intended recovery path (**owner-hit 2026-07-23**)."
> — `engine.py:240-242`

Das ist überdurchschnittlich. Jeder dieser Kommentare spart einem künftigen Entwickler
Stunden — und einige dokumentieren Fehler, die Produktion erreicht haben, samt Datum.

**Für VibeMind direkt übernehmbar als Standard:** Kommentare, die den *Grund* und
gegebenenfalls den *Incident* festhalten. → [ADR-0016](adr/ADR-0016-kommentarkultur.md).

### Was die Wartbarkeit senkt

| Problem | Beleg |
|---|---|
| **Referenzen auf nicht existierende Dokumente** | §16/§25/§30/§33/§34/§36, `PERSONAS.md`, `FAKE-SLACK-SPEC.md`, `AUTOMATION-SCHEDULING.md`, `PERMISSIONS-AND-INBOX.md` — [02](02-repositorystruktur.md#docs) |
| **Lazy-Imports zur Zyklenvermeidung** | `agents/registry.py:20`, `permissions.py:72`, `agent.py:193`, `catalog.py` — Symptom zu enger Kopplung |
| **Attribut-Anheftung an Objekte** | `engine.executor = …`, `engine.todo = …`, `engine.roots = …`, `engine.skill_loader = …` mit `# type: ignore[attr-defined]` (`agent.py:329-338`) — der `TurnEngine`-Vertrag ist unvollständig, die Lücke wird per Monkey-Patch gefüllt |
| **Keine Typprüfung in CI** | Kein `mypy`; `# type: ignore` steht ungeprüft im Code |
| **Kein Linter in CI** | Kein `ruff`/`black`-Gate |
| **Kein Schema-Versioning** | JSONL-Konversationen und JSON-Stores ohne Versionsfeld oder Migrationspfad |
| **Import mitten in der Datei** | `permissions.py:27` importiert nach einer Funktionsdefinition — funktioniert, ist aber Stilbruch |

---

## 10.6 Async-Modell

**Ein Event-Loop, blockierendes I/O in Threads.**

| Was | Wie |
|---|---|
| Provider-Aufrufe | blockierend, in `loop.run_in_executor` (`engine.py:416`), Chunks über `asyncio.Queue` |
| Tool-Ausführung | `asyncio.to_thread(self._execute_sync, tc)` (`engine.py:490, 501`) |
| MCP | nativ async, Brücke aus Threads per `run_coroutine_threadsafe` (`mcp/tools.py:72`) |
| SQLite | `check_same_thread=False` + `threading.RLock` (`memory/sqlite_store.py:20-21`) |
| Scheduler | `asyncio.create_task` pro fälligem Task, **nicht awaited** (`automation/scheduler.py:76-79`) |
| Gateway (Slack/Telegram) | slack-bolt Socket Mode + `to_thread` für blockierende Sends |

**Bewertung:** Das ist die pragmatisch richtige Wahl für ein lokales Produkt — man
vermeidet die Vollkonvertierung aller SDKs auf async und behält Responsivität.

**Aber:** Der **Default-ThreadPoolExecutor** ist ungebunden konfiguriert
(`min(32, cpu+4)` Worker) und wird von *allem* geteilt: Tool-Ausführung,
Provider-Streams, Sends. Es gibt keine Priorisierung, keine Queue, keine
Rückstau-Signalisierung. Bei parallelem `explore`-Fan-out oder mehreren gleichzeitig
feuernden Automations ist das der erste Engpass ([11 B-03](11-performance.md#b-03)).

**Der Scheduler-Kommentar ist lehrreich** (`scheduler.py:76-79`): „Spawn, don't await:
a run can suspend on a parked approval and **one blocked automation must never stall the
scheduler loop**, other due tasks, or self-wake resumption." Richtig erkannt — aber es
gibt keine Obergrenze für gleichzeitig laufende Automations.

---

## 10.7 Bewertung

| Aspekt | Note | |
|---|---|---|
| Modulschnitt Runtime | **A-** | engine/permissions/risk/tools/providers sauber |
| Modulschnitt Server | **D** | manager.py + app.py + integration_tools.py |
| DI-Ansatz | B+ | Explizit und testbar, aber 27 Parameter |
| Testbarkeit | **A-** | 881 Tests, FakeSlack, Env-isolierbar |
| Kommentarkultur | **A** | Warum statt was, mit Incident-Bezug |
| Dokumentation | **E** | Referenzen ins Leere |
| Async-Design | B | Pragmatisch richtig, aber ungebundene Executoren |
| Typsicherheit | C | Type-Hints vorhanden, aber ungeprüft |
| Fehlerbehandlung | B- | Konsistent, aber viele stille `except Exception: pass` |

**Anmerkung zu „stille Excepts":** `grep`-Stichprobe zeigt das Muster
`except Exception: pass` an vielen Stellen (Audit-Sink, Interrupt-Hooks,
Telemetrie, ACL-Setzung, Provider-Capabilities). In den meisten Fällen ist es
begründet („best-effort: a dead executor must not block the stop") und kommentiert.
In Summe verbirgt es aber Fehlerklassen, für die es keine Metrik gibt.

---

## 10.8 Entscheidung

| Komponente | Entscheidung |
|---|---|
| Explizite Parameter-Injektion (kein DI-Container) | **Übernehmen**, mit Parameterobjekten |
| `COWORKER_STATE_DIR`-Muster (Env-isolierter Zustandsbaum) | **Direkt übernehmen** — macht Tests trivial |
| FakeSlack-Harness-Muster (echter Handler, kein Netz) | **Direkt übernehmen** |
| Kommentarkultur (Warum + Incident-Datum) | **Direkt übernehmen** |
| `SessionManager` | **Nicht übernehmen** — in Services zerlegen, Event-Bus dazwischen |
| `app.py`-Routenstruktur | **Nicht übernehmen** — `APIRouter` pro Domäne |
| Async-Modell (Loop + Threads) | **Übernehmen**, aber mit **begrenztem, priorisiertem Worker-Pool** |

---

**Weiter:** [11 — Performance](11-performance.md)
