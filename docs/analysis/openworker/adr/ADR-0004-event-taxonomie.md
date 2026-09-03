# ADR-0004 — Event-Taxonomie übernehmen, Event-Bus neu bauen

**Status:** Vorgeschlagen · **Kategorie:** B (übernehmen und erweitern) · **Phase:** 2
**Betrifft:** Runtime, UI, Observability, Modulkopplung

---

## Goal

> VibeMind hat **ein** Event-Vokabular für Agentenverhalten, über alle Module hinweg,
> und die Ereignisse laufen über einen echten Bus — nicht über direkte Aufrufe zwischen
> Diensten.

**Messbar erreicht, wenn:** Ein neues Modul kann Agentenverhalten beobachten, ohne dass
ein bestehendes Modul geändert wird; die Ereignisfolge eines Turns ist vollständig aus
dem Bus rekonstruierbar.

---

## Kontext

OpenWorkers `coworker/events.py` definiert **15 Event-Typen** — bewusst schmal und
gut geschnitten:

```
TURN_START · ASSISTANT_DELTA · REASONING_DELTA · ASSISTANT_MESSAGE
TOOL_PROPOSED · PERMISSION_REQUIRED · DIRECTORY_REQUESTED · QUESTION_REQUESTED
PLAN_PROPOSED · TOOL_STARTED · TOOL_FINISHED · ITERATION_END · TURN_END
ERROR · INTERRUPTED
```

**Aber es ist kein Event-Bus.** Es gibt kein Publish/Subscribe zwischen Komponenten,
kein Event-Log, keine Wiederherstellbarkeit aus Events. Events sind reine
**UI-Benachrichtigungen**; der Zustand liegt in der Nachrichtenliste.

Genau daraus folgt OpenWorkers größtes Strukturproblem: Weil es keinen Bus gibt, muss
alle Querschnittskoordination irgendwo zusammenlaufen — und das ist
`SessionManager` mit 3.766 LOC ([10.1](../10-backend.md#101-die-manager-monolith-frage)).

**Das ist die Lehre:** Ein Event-Bus ist keine Zierde. Er ist das, was verhindert, dass
Koordination in ein God-Object kollabiert.

VibeMind hat Redis im Stack und ~36 Dienste — die Voraussetzungen sind da.

---

## Entscheidung

**Die Taxonomie wird übernommen** (sie ist gut), **der Transport wird neu gebaut.**

### Übernommenes Vokabular + Erweiterungen

| Kategorie | Events |
|---|---|
| **Turn** (aus OpenWorker) | `turn.started` · `turn.ended` · `turn.interrupted` · `turn.error` · `iteration.ended` |
| **Assistant** (aus OpenWorker) | `assistant.delta` · `assistant.reasoning_delta` · `assistant.message` |
| **Tool** (aus OpenWorker + neu) | `tool.proposed` · `tool.started` · **`tool.output_delta`** ⭐ · `tool.finished` |
| **Human-in-the-Loop** (aus OpenWorker) | `permission.required` · `question.required` · `directory.required` · `plan.proposed` |
| **Plan** (neu) | `plan.created` · `plan.step_started` · `plan.step_finished` · `plan.replanned` |
| **Agent** (neu) | `agent.spawned` · `agent.finished` · `agent.handoff` · `agent.escalated` |
| **Voice** (neu) | `voice.wake_detected` · `voice.transcript_partial` · `voice.transcript_final` · `voice.tts_started` · `voice.barge_in` |
| **Governance** (neu) | `taint.raised` · `budget.warning` · `budget.exceeded` · `grant.minted` · `grant.revoked` |

⭐ `tool.output_delta` ist die wichtigste Ergänzung — ohne sie zeigt ein fünfminütiger
Build fünf Minuten nichts, was bei Voice unbenutzbar ist
([11 B-04](../11-performance.md#b-04-kein-streaming-von-tool-output--mittel)).

### Transport

- **Redis Streams** als Bus (bereits im Stack; Consumer Groups, Persistenz, Replay).
- **Append-Only-Journal** pro Session: die Ereignisfolge ist rekonstruierbar.
- **Projektionen** statt Parallelsystemen: `conversation_view`, `audit_view`,
  `cost_view`, `timeline_view` werden aus dem Journal abgeleitet.
- **Kein volles CQRS** — siehe [16.2](../16-openworker-v2.md#162-bewertung-der-genannten-konzepte).
  Journal + Projektionen liefern 80 % des Nutzens bei 30 % der Kosten.

### Pflichtfelder jedes Events

```
event_id · trace_id · span_id · session_id · space · agent_id
plan_step_id? · timestamp · type · payload · provenance?
```

`trace_id`/`span_id` machen den Bus direkt OpenTelemetry-kompatibel
(Phase 5, siehe [17](../17-migrationsplan-vibemind.md#phase-5--produktionsreife)).

---

## Begründung

- **Die 15 Typen sind empirisch validiert.** Sie sind genau die Granularität, die eine
  UI braucht — nicht feiner (Rauschen), nicht gröber (kein Live-Feedback).
- **Vier Prompt-Typen als eigene Events** (statt einem generischen „needs input")
  ist die richtige Entscheidung: Jeder Typ hat eine andere Entscheidungsmenge und
  eine andere Darstellung.
- **Ein Bus entkoppelt.** Ohne ihn braucht jedes neue Modul (Voice-Feedback,
  Kostenzähler, Trace-Exporter) eine Änderung im Kern.
- **Journal + Projektionen lösen mehrere Probleme gleichzeitig:** Audit, Kosten,
  Zeitreise-Debugging, Wiederaufnahme — ohne vier Parallelsysteme.

---

## Konsequenzen

**Positiv**
- Neue Beobachter ohne Kernänderung.
- Audit wird eine Projektion, kein zweites System.
- Kostenrechnung fällt nebenbei ab.
- Direkte OTel-Kompatibilität.
- Verhindert strukturell ein zweites `SessionManager`-God-Object.

**Negativ / Kosten**
- **Event-Volumen.** `assistant.delta` und `tool.output_delta` sind hochfrequent.
  Gegenmaßnahme: Deltas werden **nicht** journalisiert, nur live gestreamt; nur
  aggregierte Ereignisse gehen ins Journal. Diese Trennung muss von Anfang an klar sein.
- **Schema-Evolution.** Events sind ein Vertrag; jede Änderung braucht Versionierung.
  OpenWorker hat kein Schema-Versioning — das ist ein Fehler, den VibeMind nicht
  wiederholen darf.
- **Eventual Consistency** zwischen Journal und Projektionen. Für die UI unkritisch,
  für Genehmigungsentscheidungen **nicht akzeptabel** — die Inbox bleibt deshalb
  transaktional in Supabase ([ADR-0001](ADR-0001-inbox-governance.md)), sie ist keine
  Projektion.
- Debugging wird indirekter: „wer hat dieses Event verarbeitet" ist schwerer zu
  beantworten als ein Stacktrace.

**Risiko**
- **Bus-Ausfall = Systemausfall.** Redis wird kritischer Pfad. Gegenmaßnahme:
  Persistenz aktiviert, definierter Degradationsmodus (lokale Pufferung).

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Status quo (direkte Aufrufe)** | Verworfen: führt bei ~36 Diensten zwangsläufig zum God-Object, siehe OpenWorker |
| **Vollständiges Event Sourcing + CQRS** | Verworfen als Gesamtansatz: hohe Komplexitätskosten, VibeMind hat kein Lese-/Schreib-Skalierungsproblem. Journal + Projektionen genügen |
| **Kafka statt Redis Streams** | Verworfen für v1: Betriebsaufwand nicht gerechtfertigt. Redis ist bereits da. Bei > 10⁵ Events/s neu bewerten |
| **Nur WebSocket-Broadcast wie OpenWorker** | Verworfen: löst UI, nicht Modulkopplung |
| **Ein generisches `needs_input`-Event** statt vier Prompt-Typen | Verworfen: Die vier Typen tragen unterschiedliche Semantik und UI; Zusammenlegen verlagert die Fallunterscheidung nur in den Payload |
