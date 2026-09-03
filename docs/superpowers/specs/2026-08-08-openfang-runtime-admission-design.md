# Design-Spec: OpenFang Runtime Admission für externe MCP-Tool-Aufrufe

**Datum:** 2026-08-08
**Status:** Design freigegeben, schriftliches Spec-Review offen
**Erste Lieferwelle:** ausschließlich externe deterministische `POST /mcp`-Aufrufe mit MCP-Methode `tools/call`

---

## 1. Ziel

OpenFang wird für ausführende VibeMind-Aufrufe zur verbindlichen Laufzeit-Autorität. Ein vom Brain gerouteter Tool-Aufruf darf erst ausgeführt werden, wenn OpenFang serverseitig alle folgenden Bedingungen erfolgreich gebunden hat:

1. eine gültige planweite Freigabe (`approval_ref`),
2. eine einmalige Kostenreservierung (`cost_ref`) für genau diese Invocation,
3. den registrierten Agenten und dessen wirksamen Tool-Scope,
4. Toolname und kanonischen Hash der Argumente,
5. eine stabile `invocation_id`,
6. ein dauerhaftes Pre-Execution-Receipt.

Das System priorisiert Sicherheit vor Verfügbarkeit: Bei unbekanntem Ausführungsstand wird niemals automatisch erneut ausgeführt.

## 2. Nicht-Ziele der ersten Lieferwelle

- Agent-Turns und Streaming-Ausführung auf das neue Admission-Modell umstellen.
- LLM-Tokenkosten vollständig reservieren oder abrechnen.
- Bestehende Space-MCPs, Brain-Routing oder Tool-Implementierungen neu bauen.
- Eine globale Exactly-once-Garantie für externe Side Effects behaupten.
- Tool-Ergebnisse ungefiltert als Audit- oder Replay-Datenbank speichern.
- Brain zu einer zweiten Approval-, Cost- oder Receipt-Source-of-Truth machen.

## 3. Verifizierter Ausgangspunkt

- `authority_admission.rs` und `cost_authority.rs` definieren Transporttypen, sind aber noch nicht in den Runtime-Pfad eingebunden.
- `ApprovalManager` hält Freigaben gegenwärtig im Speicher und liefert eine blockierende, boolähnliche Entscheidung ohne Plan-, Argument- oder Cost-Bindung.
- `tool_runner::execute_tool` prüft Capability und optional die bestehende Approval Policy, ruft danach aber ohne Cost-Reservierung, Authority-Ref, Receipt oder Replay-Schutz das Tool auf.
- `POST /mcp` löst den Caller über `X-OpenFang-Agent-Id` auf. Die Route liest die bereits vom Brain gesendeten Header `X-OpenFang-Approval-Ref` und `X-OpenFang-Cost-Ref` noch nicht.
- Die HTTP-Route liegt hinter der bestehenden OpenFang-API-Authentifizierung. Der Agent-ID-Header bleibt trotzdem nur eine beanspruchte Ausführungsidentität und kein eigener Authentifizierungsnachweis.
- Metering erfasst LLM-Verbrauch nachträglich; es ist keine atomare Runtime-Kostenreservierung.

Diese Spec erweitert den vorhandenen Pfad. Sie ersetzt weder den Tool-Scope noch die unabhängigen Brain-Truth-Validatoren.

## 4. Festgelegte Produktentscheidungen

### 4.1 Approval und Cost

- `approval_ref` ist planweit wiederverwendbar, aber an `plan_id`, `plan_revision`, `space_id` und `agent_id` gebunden.
- Jeder konkrete Tool-Aufruf erhält daraus eine serverseitige One-shot-Invocation-Zulassung.
- `cost_ref` ist immer single-use und an genau eine `invocation_id` gebunden.
- Auch deterministische Tools mit Kosten von `0` Micro-USD benötigen einen expliziten `cost_ref`. Damit bleibt der Authority-Pfad vollständig und prüfbar.
- Geldbeträge werden ausschließlich als Integer-Micro-USD gespeichert. Gleitkommazahlen sind in Admission und Settlement unzulässig.

### 4.2 Pending Approval

- Eine offene Freigabe blockiert keinen HTTP-Worker.
- Die Authority API antwortet strukturiert mit `pending_approval` und der vorhandenen `approval_ref`; Brain ruft `/mcp` in diesem Zustand noch nicht auf.
- Brain pausiert den Task und setzt später dieselbe `invocation_id` fort.
- Vor der positiven Entscheidung finden weder Cost-Reservation noch Cost-Consumption, Receipt-Preparation oder Tool-Dispatch statt.
- Falls `/mcp` defensiv dennoch eine inzwischen nicht freigegebene Approval sieht, antwortet es ebenfalls `pending_approval`, konsumiert keinen Cost-Ref und dispatcht nicht.

### 4.3 Replay und unklarer Ausgang

- Eine abgeschlossene Invocation wird nicht erneut ausgeführt.
- Eine gleichzeitig laufende Invocation antwortet `in_progress`.
- Ein nach möglichem Side Effect nicht mehr eindeutig bestimmbarer Ausgang wird `outcome_unknown`.
- `outcome_unknown` darf weder automatisch noch durch einen identischen Replay erneut dispatchen. Eine neue Ausführung benötigt eine bewusst neue `invocation_id`, neue Cost-Reservation und gegebenenfalls eine erneute Freigabeentscheidung.
- Damit garantiert das Design höchstens einen Dispatch pro Invocation. Es behauptet keine mathematische Exactly-once-Ausführung eines externen Systems.

### 4.4 Datensparsame Receipts

- Das Receipt speichert immer den SHA-256-Hash des vollständigen Ergebnisses.
- Zusätzlich darf es ein redigiertes Ergebnis-Envelope bis zu einer konfigurierbaren Obergrenze speichern; Default: 64 KiB UTF-8.
- Sensible oder größere Ergebnisse werden als `digest_only` gespeichert.
- Ein Replay von `digest_only` bestätigt die frühere Ausführung und liefert Status, Metadaten und Ergebnis-Hash, aber keine Rohdaten.
- Redaction findet vor dem dauerhaften Schreiben statt. Nicht redigierbare Ergebnisse führen nicht zu einer Speicherung des Rohinhalts.

## 5. Zielarchitektur

```text
Brain
  |  Plan + Approval bei OpenFang anfordern
  |  pending: Task pausieren, hier stoppen
  |  approved: Cost-Reservation bei OpenFang anfordern
  v
OpenFang Authority API
  |  approval_ref (planweit)
  |  cost_ref (single-use, invocation-gebunden)
  v
POST /mcp, method=tools/call
  Headers: Agent-Id + Approval-Ref + Cost-Ref
  JSON-RPC id: invocation_id
  params: Tool + Arguments
  v
RuntimeAdmissionService (Kernel, Source of Truth)
  1. Request/Caller/Tool-Scope prüfen
  2. Approval und Cost serverseitig auflösen und binden
  3. Receipt prepared + Cost-Consumption atomar persistieren
  4. Receipt dispatching persistieren
  5. genau einen ToolInvoker-Dispatch zulassen
  6. Ergebnis redigieren/hashen, Receipt finalisieren, Cost settlen
  v
MCP JSON-RPC Result oder strukturierter Authority-Fehler
```

Der `RuntimeAdmissionService` ist ein zentraler Kernel-Service. API und Runtime verwenden ihn über schmale Ports; sie führen keine Authority-Entscheidung lokal nach.

### 5.1 Erwogene Alternativen

1. **Gate ausschließlich in `tool_runner`:** verworfen, weil Transportvalidierung, Persistenz und Ausführung zu eng gekoppelt würden und weitere Origins dieselbe Logik duplizieren müssten.
2. **Gate ausschließlich in der `/mcp`-Route:** verworfen, weil ein späterer Agent-Loop-Pfad die Autorität leicht umgehen könnte und Concurrency/Recovery nicht in die API-Schicht gehören.
3. **Zentraler persistenter Kernel-Service:** gewählt. Er hält die Zustandsmaschine und Stores; API und Tool-Runner bleiben Adapter. Das ist die kleinste Architektur, die später ohne zweite Source-of-Truth auf Agent-Turns erweitert werden kann.

## 6. Transportvertrag

Für `POST /mcp` mit `method = "tools/call"` sind verpflichtend:

| Wert | Quelle | Regel |
|---|---|---|
| Caller | `X-OpenFang-Agent-Id` | nicht leer, gültige UUID, registrierter Agent |
| Approval | `X-OpenFang-Approval-Ref` | nicht leer, nur serverseitig auflösbar |
| Cost | `X-OpenFang-Cost-Ref` | nicht leer, nur serverseitig auflösbar |
| Invocation | JSON-RPC `id` | nicht leerer String, stabil über Resume/Replay |
| Tool | `params.name` | im effektiven Tool-Scope des Callers |
| Argumente | `params.arguments` | JSON-Objekt; wird kanonisiert und gehasht |

Authority-Refs in `params`, `arguments` oder Tool-spezifischen Feldern werden ignoriert und können fehlende Header niemals ersetzen. Die API gibt rohe Ref-Werte nicht an das Tool weiter.

Andere MCP-Methoden behalten zunächst ihr bestehendes Verhalten. `tools/list` benötigt weiterhin einen registrierten Caller, aber keine Invocation-Refs.

Die kanonische Argumentdarstellung verwendet UTF-8-JSON mit rekursiv lexikographisch sortierten Objektschlüsseln, unveränderter Array-Reihenfolge und stabiler JSON-Zahl-/String-Kodierung. Der Bindungswert ist `SHA-256(canonical_json)`.

## 7. Persistenzmodell

Die Tabellen liegen im bestehenden persistenten OpenFang-Backend und dürfen nur durch Kernel-Stores des `RuntimeAdmissionService` verändert werden.

### 7.1 `runtime_approvals`

Pflichtfelder:

- `approval_ref` als Primary Key,
- `plan_id`, `plan_revision`, `space_id`, `agent_id`,
- `status`: `pending | approved | denied | expired`,
- `decided_at`, `expires_at`, `created_at`,
- optionale Entscheidungsevidenz ohne Geheimnisse.

Eine Approval ist nur nutzbar, wenn alle Bindungen exakt stimmen und der Status zum Prüfzeitpunkt `approved` ist.

### 7.2 `cost_reservations`

Pflichtfelder:

- `cost_ref` als Primary Key,
- `approval_ref` und `invocation_id`,
- `agent_id`, `plan_id`, `plan_revision`,
- `reserved_micro_usd`, `settled_micro_usd`,
- `status`: `reserved | consumed | released | settled | held_unknown`,
- `expires_at`, `created_at`, `consumed_at`, `settled_at`.

Constraints erzwingen genau eine Invocation pro Cost-Ref und höchstens eine Consumption. Eine Reservierung von `0` ist gültig; negative Werte sind unzulässig.

### 7.3 `execution_receipts`

Pflichtfelder:

- `invocation_id` als Primary Key,
- Caller-, Plan-, Revision-, Space- und Agent-Bindung,
- `tool_name`, `arguments_sha256`,
- `approval_ref`, `cost_ref`,
- `status`: `prepared | dispatching | succeeded | failed | outcome_unknown`,
- `dispatch_started_at`, `finished_at`,
- `result_sha256`, `result_storage_mode`, redigiertes `result_envelope`,
- Fehlerklasse und Settlement-Metadaten.

Die Datenbank-Transaktion für die Zulassung validiert Approval und Cost, legt das eindeutige `prepared`-Receipt an und bindet/consumiert den Cost-Ref atomar. Ein Unique-Konflikt ist ein Replay und niemals die Erlaubnis für einen zweiten Dispatch.

## 8. Zustandsmaschine und Crash-Semantik

```text
keine Zulassung
  | approved + cost valid + bindings valid
  v
prepared
  | durable transition immediately before invoker call
  v
dispatching ---- tool returns clearly ----> succeeded | failed
  |
  +---- process/persistence ambiguity -----> outcome_unknown
```

- Fehler vor `dispatching`: kein Tool-Side-Effect möglich; Cost vollständig freigeben und Receipt als `failed` finalisieren.
- Fehler nach dauerhaftem `dispatching`: Falls das Ergebnis nicht zuverlässig finalisiert werden kann, `outcome_unknown`; Cost bleibt `held_unknown`.
- Beim Start werden stale `dispatching`-Receipts nicht erneut ausgeführt, sondern zu `outcome_unknown` reconciled.
- Der Service verwendet zusätzlich ein In-Process-Singleflight pro `invocation_id`; die dauerhafte Eindeutigkeit bleibt die Autorität über Prozessgrenzen hinweg.

## 9. Settlement-Regeln

- Erfolgreicher Dispatch: tatsächliche Kosten settlen, ungenutzte Reservierung freigeben.
- Sicherer Fehler vor Dispatch: gesamte Reservierung freigeben.
- Eindeutiger Tool-Fehler nach Dispatch: definierte tatsächliche Kosten settlen; Receipt `failed`.
- Unklarer Ausgang: Reservierung `held_unknown`; kein automatisches Release und kein Retry.
- Deterministischer MCP-Tool-Aufruf in Lieferwelle 1: `reserved_micro_usd = 0`, `settled_micro_usd = 0`.
- Settlement muss idempotent sein und darf eine Reservierung nie zweimal verändern.

## 10. Runtime-Seams

### 10.1 API Parser

Ein reiner Parser in der API erzeugt einen typisierten `RuntimeAdmissionContext` aus authentifiziertem Request, drei Authority-Headern, JSON-RPC-ID, Tool und Argument-Hash. Leere, ungültige oder zu lange Werte werden vor Kernel-Aufrufen abgelehnt.

### 10.2 Kernel-Port

`KernelHandle` erhält schmale Methoden für:

- `admit_runtime_tool(context)`,
- `finalize_runtime_tool(invocation_id, outcome)`,
- `read_runtime_receipt(invocation_id)`.

Die reale Implementierung delegiert ausschließlich an `RuntimeAdmissionService`. Tests können deterministische Fake-Stores und einen Fake-Clock einsetzen.

### 10.3 ToolInvoker

Der Dispatch liegt hinter einem kleinen `ToolInvoker`-Port. `tool_runner` erhält eine explizite `ExecutionOrigin`:

- `ExternalMcp(RuntimeAdmissionContext)` verlangt den neuen Authority-Pfad,
- bestehende Agent-Loop-Ursprünge bleiben in Lieferwelle 1 explizit unverändert.

Ein `exec_policy` darf bei `ExternalMcp` weder Approval, Cost noch Receipt umgehen.

## 11. Antworten und Fehlerklassen

Die API liefert stabile maschinenlesbare Authority-Daten im JSON-RPC-Fehlerfeld `error.data`:

| Status | Bedeutung | Dispatch |
|---|---|---|
| `pending_approval` | Freigabe noch offen | nein |
| `denied` | Approval, Caller, Tool oder Binding ungültig | nein |
| `cost_unavailable` | Cost fehlt, ist abgelaufen, verbraucht oder falsch gebunden | nein |
| `in_progress` | dieselbe Invocation wird bereits verarbeitet | nein |
| `outcome_unknown` | möglicher Side Effect, Ausgang unklar | niemals automatisch |

Ein erfolgreich abgeschlossenes Replay verwendet die normale JSON-RPC-`result`-Form, ergänzt um `replayed: true`, und liefert je nach `result_storage_mode` das redigierte Envelope oder nur den Ergebnis-Hash. Frühere finale Fehler bleiben Fehlerantworten mit `replayed: true` in `error.data`.

Interne Store-Details, Ref-Inhalte und Secrets werden nicht in Fehlermeldungen ausgegeben. Temporäre Infrastrukturfehler vor Dispatch dürfen nur nach dem bestehenden bounded-retry-Muster wiederholt werden. Nach `dispatching` ist automatischer Retry verboten.

## 12. Sicherheitsinvarianten

- Die bestehende HTTP-Authentifizierung bleibt Pflicht. `X-OpenFang-Agent-Id` allein authentifiziert keinen Client.
- Approval- und Cost-Refs sind opake Server-Capabilities; Clientwerte werden ausschließlich gegen persistente Serverrecords geprüft.
- Ein Ref kann nicht über Agent, Plan, Revision, Space, Tool, Argument-Hash oder Invocation hinweg umgebunden werden.
- Tool-Scope-Prüfung und Runtime Admission sind kumulativ. Keine der beiden Prüfungen ersetzt die andere.
- Brain darf Refs transportieren und Authority anfordern, aber keine Approval-, Cost- oder Receipt-Records direkt schreiben.
- Die unabhängigen `truth:`-Validatoren im Brain bleiben nach der Ausführung bestehen und entscheiden weiterhin über sichtbaren Erfolg.
- Logs enthalten höchstens gekürzte Ref-Fingerprints, niemals vollständige Refs oder rohe sensible Tool-Ergebnisse.

## 13. TDD- und Verifikationsstrategie

Tests arbeiten verhaltensbasiert mit `AtomicUsize`-Zählern, Raise-on-call-Guards, Barrieren, Fake-Clock und fehlschlagenden Stores. Quelltext-Stringprüfungen sind kein Ersatz.

### API

- Header sind verpflichtend, nicht leer und können nicht aus Arguments ersetzt werden.
- JSON-RPC-ID ist die stabile Invocation-ID.
- Der Parser reicht Ref-Werte niemals als Tool-Argumente weiter.

### Kernel Admission

- Denied Approval stoppt vor Cost und Dispatch.
- Pending Approval liefert nur den Pending-Status und verursacht keine Cost- oder Receipt-Mutation.
- Abgelaufene, verbrauchte oder falsch gebundene Cost-Refs stoppen vor Dispatch.
- Ein zugelassener Aufruf dispatcht einmal und persistiert das vollständig gebundene Receipt.
- Serieller und paralleler Replay verursachen weder zweiten Dispatch noch zweite Abrechnung.
- Refs können nicht zwischen Agent, Tool oder Argument-Hash wiederverwendet werden.
- Cost kann unter Parallelität nicht überbucht und nur einmal konsumiert/gesettlet werden.
- Fehler vor Dispatch releasen; eindeutige Fehler danach settlen einmal.
- Receipt-Fehler nach möglichem Dispatch ergeben `outcome_unknown` und niemals Redispatch.
- Stale `dispatching` wird nach Neustart zu `outcome_unknown` reconciled.

### Tool Runner

- `denied`, `pending_approval`, `cost_unavailable`, `in_progress` und bestehendes finales Receipt lassen den `ToolInvoker` unberührt.
- `ExternalMcp` kann durch `exec_policy = full` oder ähnliche bestehende Bypass-Pfade nicht an Admission vorbeilaufen.
- Der erfolgreiche Pfad behält das bestehende MCP-Result-Format bei.

### Testdoubles

- `PanicToolInvoker` für alle Pre-Dispatch-Abbrüche,
- `PanicCostAuthority` für Approval-Deny/Pending,
- `BarrierToolInvoker` für konkurrierende Duplikate,
- `FakeClock` für TTL und Recovery,
- `FailingReceiptStore` für `outcome_unknown`,
- getrennte Counter für Approval-Lookup, Cost-Consumption, Dispatch, Receipt-Write und Settlement.

## 14. Rollout

### Phase 1 — persistenter deterministischer `/mcp tools/call`-Korridor

- Stores, Migrationen, RuntimeAdmissionService und Ports,
- Authority-Header-Parser,
- externer Tool-Runner-Origin,
- fail-closed Feature Flag für den neuen Korridor,
- Brain-Client nutzt vorhandene getrennte Approval-/Cost-Header und stabile Invocation-ID,
- statische, Unit-, Concurrency- und Recovery-Tests.

Der Flag darf nur aktiviert werden, wenn persistente Stores und die Ref-Issuance erreichbar sind. Bei fehlender Migration oder Authority-Komponente bleibt Ausführung gesperrt.

### Phase 2 — Live-Golden-Path

Ein harmloser deterministischer Space-Call läuft:

`Brain intent -> OpenFang Approval/Cost -> /mcp tools/call -> Space-MCP -> Receipt -> unabhängige truth:-Rücklese`

Akzeptanz verlangt Logs, ein gebundenes Receipt, Cost `0`, Replay ohne Redispatch und keinen lokalen Executor-/DB-Fallback.

### Phase 3 — Agent-Turns und kognitive Kosten

Erst nach Phase 2 werden normale und streamende Agent-Loops sowie LLM-Kostenreservierung auf dasselbe Modell migriert. Diese Phase benötigt eigene Designs für Token-Schätzung, Teilstream-Abbruch und Provider-Settlement.

## 15. Abnahmekriterien der ersten Lieferwelle

1. Kein externer `tools/call` erreicht ein Tool ohne gültige Approval-, Cost-, Caller-, Scope-, Tool-, Argument- und Invocation-Bindung.
2. Pending ist nicht blockierend und mutiert weder Cost noch Dispatch.
3. Jede Invocation besitzt vor Dispatch ein dauerhaftes Receipt.
4. Serielle und parallele Duplikate verursachen höchstens einen Dispatch und ein Settlement.
5. Nach einem möglicherweise ausgeführten Side Effect führt derselbe Aufruf niemals zu einem automatischen Redispatch.
6. Replays geben nur redigierte, begrenzte Daten oder `digest_only` zurück.
7. Deterministische Tools durchlaufen denselben Cost-Pfad mit exakt `0` Micro-USD.
8. Bestehende Brain-Truth-Validatoren bestätigen das sichtbare Ergebnis unabhängig von OpenFangs Eigenbericht.
9. Die erste Lieferung behauptet keine Runtime-Abdeckung für Agent-Turns, Streaming, vollständige LLM-Kosten oder eine Live-Proxmox-Ausführung.

## 16. Bewusste Folgearbeiten

- Persistente UI-/Chat-Auflösung planweiter Approvals statt des heutigen rein blockierenden Waiter-Modells.
- Kognitive Agent-Turns und Streaming an `RuntimeAdmissionService` anschließen.
- LLM-Kosten vorab schätzen, reservieren und nach Provider-Usage settlen.
- Operator-Workflow für manuelle Klärung von `outcome_unknown` und `held_unknown`.
- Retention-, Verschlüsselungs- und Löschregeln für Receipts konkretisieren, bevor sensible Tool-Klassen live gehen.
