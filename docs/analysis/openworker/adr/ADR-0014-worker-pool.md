# ADR-0014 — Worker Pool mit Priorität und Backpressure

**Status:** Vorgeschlagen · **Kategorie:** C (neu entwickeln) · **Phase:** 4
**Betrifft:** Nebenläufigkeit, Latenz, Kosten, Betriebsstabilität

---

## Goal

> Agentenarbeit wird über einen **begrenzten, priorisierten** Pool ausgeführt.
> Eine interaktive Sprachsitzung wird nie durch Hintergrund-Automationen ausgebremst,
> und Überlast ist sichtbar statt unbemerkt.

**Messbar erreicht, wenn:** Bei 20 gleichzeitig fälligen Automations bleibt die
Antwortlatenz einer interaktiven Session unverändert; Warteschlangentiefe ist in der UI
sichtbar.

---

## Kontext

OpenWorker hat **keinen** Pool. Drei Stellen laufen unbegrenzt
([11 B-03](../11-performance.md#b-03)):

| Stelle | Code | Risiko |
|---|---|---|
| Paralleles Tool-Fan-out | `asyncio.gather(*[to_thread(...) …])` (`engine.py:489-491`) | n `explore`-Calls = n Threads **und** n LLM-Sessions |
| Automation-Läufe | `asyncio.create_task` pro fälligem Task, nicht awaited (`scheduler.py:76-79`) | 20 fällige Cron-Tasks starten 20 Engines |
| Default-ThreadPool | `min(32, cpu+4)`, geteilt von allem | Sättigung blockiert auch Provider-Streams |

Der Scheduler-Kommentar ist dabei **richtig gedacht**: „Spawn, don't await: a run can
suspend on a parked approval and one blocked automation must never stall the scheduler
loop." Nur ist die Konsequenz nicht zu Ende geführt — es gibt keine Obergrenze.

VibeMind hat Redis im Stack (`redis_voice:6379`, `coding_redis:6382`) und plant
Multi-Agent. Bei n Agenten × m Tools ist unbegrenzte Nebenläufigkeit keine Option.

---

## Entscheidung

```python
class WorkPool:
    queues:     {interactive: HIGH, voice: HIGHEST, automation: NORMAL, background: LOW}
    semaphores: {llm_calls: N, shell: M, browser: K, mcp_per_server: 1, container: C}
    def submit(task, *, priority, budget, deadline) -> Handle
    def state() -> PoolState        # → Backpressure ans UI
    def drain(space) -> None        # Kill-Switch pro Space
```

**Vier Eigenschaften:**

1. **Priorisierung.** Sprache > interaktiv > Automation > Hintergrund. Eine
   Sprachsitzung darf nie hinter einem Batch-Lauf warten — das Latenzbudget aus
   [ADR-0010](ADR-0010-voice-pipeline-neuentwicklung.md) (1,2 s) ist sonst nicht haltbar.
2. **Ressourcen-Semaphoren.** Getrennt pro Ressourcenart: LLM-Aufrufe (Rate-Limits der
   Anbieter), Shell/Container (CPU/RAM), Browser (Sessions), MCP (ein Aufruf pro Server
   gleichzeitig — die meisten MCP-Server sind nicht nebenläufigkeitsfest).
3. **Sichtbarer Rückstau.** `PoolState` geht als Event an die UI („3 Aufgaben in
   Warteschlange, geschätzt 40 s"). Bei Voice wird das ausgesprochen — Warten ohne
   Rückmeldung ist bei Sprache besonders schlecht.
4. **Deadline-Propagierung.** Eine Aufgabe mit abgelaufener Deadline wird gar nicht erst
   gestartet, statt Ressourcen für ein wertloses Ergebnis zu verbrauchen.

**Umsetzung:** Redis Streams als Queue (bereits im Stack, konsistent mit
[ADR-0004](ADR-0004-event-taxonomie.md)). Worker sind Prozesse, keine Threads —
das passt zu `ContainerExecutor` ([ADR-0006](ADR-0006-shell-executor.md)) und
erlaubt echte Isolation.

**Kill-Switch pro Space** — `drain(space)` bricht alle laufenden Aufgaben eines Space ab
(nutzt [ADR-0003](ADR-0003-cancellation-invarianten.md)). Betriebsnotwendig.

---

## Begründung

- **Ohne Pool ist Multi-Agent nicht betreibbar.** n Agenten × m Tools ohne Obergrenze
  sättigt CPU, Speicher **und** Anbieter-Rate-Limits.
- **Priorisierung ist eine Voice-Anforderung, keine Optimierung.** Ohne sie ist das
  Latenzbudget bei paralleler Hintergrundlast strukturell unerreichbar.
- **Backpressure ist eine UX-Anforderung.** Ein System, das unbemerkt langsamer wird,
  wirkt kaputt. Ein System, das sagt „ich habe gerade viel zu tun", wirkt kompetent.
- **MCP-Server sind selten nebenläufigkeitsfest** — die Semaphore von 1 pro Server ist
  Erfahrungswissen, das OpenWorker nicht abbildet.

---

## Konsequenzen

**Positiv**
- Vorhersagbare Latenz für interaktive und Sprachsitzungen.
- Schutz vor Rate-Limits und Ressourcenerschöpfung.
- Sichtbare Systemlast.
- Kill-Switch für den Notfall.
- Deadline-Prüfung spart Kosten für wertlose Läufe.

**Negativ / Kosten**
- **Zusätzliche Latenz** durch Queue-Roundtrip (~5–20 ms bei Redis). Für Voice
  relevant, aber im Budget. Gegenmaßnahme: `voice`-Priorität kann den Fast-Path direkt
  nehmen, wenn ein Slot frei ist.
- **Verhungern niedriger Prioritäten.** Bei Dauerlast laufen Hintergrundaufgaben nie.
  Gegenmaßnahme: Alterung (Priorität steigt mit Wartezeit) und garantierte Mindestslots.
- **Verteilter Zustand.** Wer besitzt eine Aufgabe, wenn ein Worker stirbt?
  Braucht Lease/Heartbeat und Wiederzustellung — mit Idempotenzschlüsseln, sonst führen
  Wiederholungen externe Aktionen doppelt aus (Phase 5.3).
- Debugging wird indirekter (Aufgabe ≠ Aufrufstack).

**Risiko**
- **Falsch dimensionierte Semaphoren.** Zu eng = künstliche Langsamkeit, zu weit =
  keine Wirkung. Gegenmaßnahme: konfigurierbar pro Space, Metriken (Wartezeit,
  Sättigung) von Anfang an, Nachjustierung im Betrieb.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Status quo (`asyncio.to_thread`, unbegrenzt)** | Verworfen: sättigt unter Multi-Agent-Last |
| **Nur `asyncio.Semaphore` im Prozess** | Einfach und ausreichend für **einen** Prozess. Verworfen, weil VibeMind verteilt ist — eine prozesslokale Semaphore koordiniert nichts über Container hinweg |
| **Celery / RQ / Dramatiq** | Ausgereift, aber schwergewichtig und auf Task-Queues zugeschnitten, nicht auf priorisierte, abbrechbare, budgetierte Agentenarbeit. Redis Streams direkt ist näher am Bedarf und konsistent mit [ADR-0004](ADR-0004-event-taxonomie.md) |
| **Kubernetes Jobs pro Aufgabe** | Zu hohe Startlatenz (Sekunden) für interaktive Arbeit |
| **Keine Priorisierung, nur Begrenzung** | Verworfen: verhindert Sättigung, aber nicht, dass eine Sprachsitzung hinter einem Batch-Lauf wartet |
