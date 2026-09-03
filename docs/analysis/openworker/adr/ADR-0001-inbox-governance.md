# ADR-0001 — Inbox als kanonische Human-in-the-Loop-Schicht

**Status:** Vorgeschlagen · **Kategorie:** A (direkt übernehmen) · **Phase:** 2
**Betrifft:** Governance, Sicherheit, UX, Automations

---

## Goal

> Jede Aktion eines VibeMind-Agenten, die menschliche Zustimmung braucht, wird über
> **einen** persistenten, kanalübergreifenden Mechanismus abgewickelt — beantwortbar
> aus Web-UI, Slack, Telegram oder per Sprache, und neustartfest.

**Messbar erreicht, wenn:** Ein in der Web-UI erzeugtes Approval per Slack-Button
beantwortet werden kann; ein Backend-Neustart während eines wartenden Approvals
verliert keinen Turn.

---

## Kontext

VibeMind orchestriert 446 Intents über 19 Kategorien, darunter sensible Bereiche
(HR mit 12 Skills, Bürgergeld mit 7, Security/Ops, Marketing-Send). Der heutige Stand
der Zustimmungslogik ist `mcp/docker/approval.py`: eine env-gesteuerte
Default-Deny-Allowlist (`MCP_DOCKER_ALLOW_VERBS`, `group:verb`-Tokens). Handwerklich
gut — `container:rm` erlaubt nicht `stack:rm`, Flag-Werte werden korrekt übersprungen —
aber **statisch**: keine Laufzeit-Nachfrage, kein Prompt-Kanal (der Docstring nennt es
selbst: „stdio MCP has no interactive prompt channel"), keine Persistenz, keine
Wiederaufnahme.

OpenWorker hat für dasselbe Problem eine ausgereifte Lösung gebaut
(`coworker/inbox.py`, `server/app.py:1459-1620`, `engine.py:250-292`):

- **Vier Prompt-Typen** (Approval, Question, Directory, Plan), jeder mit eigener
  Darstellung und eigener Entscheidungsmenge.
- **Zustandsautomat** `pending → resolved`, **einmalig auflösbar**, idempotent,
  first-responder-wins (`inbox.py:8-11`).
- **Sichtbarkeit** getrennt von Existenz: `inline` (attended — nur in dieser Session)
  vs. `inbox` (unattended — Cross-Session-Warteschlange + Slack-Spiegelung).
- **Persistenz vor dem Warten**: `persist_session()` schreibt die Historie **mit dem
  unbeantworteten `tool_call`** auf Platte, *bevor* die Engine wartet
  (`app.py:1508-1512`).
- **Durable Resume**: `_unanswered_trailing_tool_calls()` rekonstruiert den Zustand
  aus der persistierten Historie; bereits beantwortete Calls werden übersprungen,
  also führt nichts doppelt aus.

---

## Entscheidung

VibeMind übernimmt die Inbox-Architektur **strukturell**, mit vier Anpassungen:

1. **Store auf Supabase** statt lokaler JSON-Datei (VibeMind ist verteilt).
2. **Zusätzliche Routing-Dimensionen**: `space`, `agent_id`, `plan_step_id` — damit
   ein Approval einem Schritt eines Plans zugeordnet werden kann.
3. **Kanäle erweitern**: Web-UI, Slack, Telegram, **Voice** (Sprachbestätigung mit
   Rückfrage-Bestätigung bei konsequenziellen Aktionen).
4. **Provenienz-Feld** (siehe [ADR-0015](ADR-0015-taint-tracking.md)): Die Karte zeigt,
   *welcher Input* die Aktion ausgelöst hat und ob Fremdinhalt im Kontext war.

Der Zustandsautomat (`pending → resolved`, idempotent, first-responder-wins) wird
**unverändert** übernommen — er ist der Kern der Race-Freiheit.

---

## Begründung

- **Es löst vier Probleme mit einem Mechanismus:** Verbindungsabbruch,
  Prozess-Neustart, Multi-Surface-Antwort, unbeaufsichtigter Betrieb.
- **Es ist aus Produktionsfehlern gewachsen.** Die Testdatei-Namen
  (`test_durable_resume`, `test_standing_approvals`, `test_slack_approval_owners`)
  belegen, dass jeder Mechanismus einen realen Vorfall hinter sich hat. Diese Erfahrung
  ist nicht selbst herstellbar — sie ist der eigentliche Wert der Übernahme.
- **Kein Konkurrenzsystem hat das** in dieser Form ([15.4](../15-architekturvergleich.md#154-sicherheit)).
  LangGraph hat Interrupts + Checkpointer als Primitive, aber keine produkthafte
  Cross-Surface-Auflösung.
- **Ohne diese Schicht ist Multi-Agent nicht verantwortbar.** Bei n parallelen Agenten
  ist „der Nutzer sitzt davor und klickt" keine gültige Annahme mehr.

---

## Konsequenzen

**Positiv**
- Einheitliche Genehmigung über alle Spaces und Agenten.
- Unbeaufsichtigter Betrieb wird betreibbar, ohne Autonomie zu erhöhen.
- Audit und Genehmigung teilen sich eine Datenquelle.
- Voraussetzung für [ADR-0005](ADR-0005-standing-rules.md) und
  [ADR-0012](ADR-0012-multi-agent-runtime.md).

**Negativ / Kosten**
- Jeder Agent-Pfad muss durch die Inbox — kein Bypass. Das ist Integrationsarbeit an
  **jeder** Stelle, die heute direkt ausführt.
- Latenz: Ein Approval kostet mindestens einen Roundtrip zum Store.
- Durable Resume ist im **verteilten** Fall komplexer als bei OpenWorker (ein Prozess).
  Deshalb: zunächst nur pro Agent-Session, agentenübergreifend erst in Phase 4.
- Der Zustandsautomat muss unter Nebenläufigkeit korrekt bleiben — Supabase-seitig
  über eine bedingte Aktualisierung (`UPDATE … WHERE state='pending'`), nicht über
  Anwendungslogik.

**Risiko**
- **Approval-Müdigkeit.** Zu viele Prompts führen dazu, dass Nutzer blind zustimmen —
  was die Schicht wertlos macht. Gegenmaßnahme: Standing Grants
  ([ADR-0005](ADR-0005-standing-rules.md)) und Risikoklassifikation
  ([ADR-0002](ADR-0002-risk-klassifikation.md)) müssen zusammen eingeführt werden.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Env-Allowlist beibehalten** (Status quo) | Verworfen: statisch, kein Laufzeitkanal, keine Persistenz, keine Wiederaufnahme |
| **LangGraph Interrupts + Checkpointer** | Teilweise besser (Checkpoint an *jeder* Stelle, nicht nur an Prompts), aber ohne Cross-Surface-UX. **Empfehlung: Checkpoint-Idee später ergänzen, Inbox-UX jetzt übernehmen** |
| **Nur synchrone UI-Dialoge** | Verworfen: unbeaufsichtigter Betrieb unmöglich, kein Neustart-Überleben |
| **n8n-Approval-Nodes** | Verworfen als Primärlösung: an Workflow-Läufe gebunden, deckt Ad-hoc-Agentenaktionen nicht ab. Kann als *Kanal* angebunden werden |
| **Eigenentwicklung von Grund auf** | Verworfen: ~2 PW gespart, aber ohne die Race- und Resume-Erfahrung, die im Original steckt |
