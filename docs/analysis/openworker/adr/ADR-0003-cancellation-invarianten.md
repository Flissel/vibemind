# ADR-0003 — Cancellation-Invarianten als Barge-in-Fundament

**Status:** Vorgeschlagen · **Kategorie:** A (direkt übernehmen) · **Phase:** 2
**Betrifft:** Agent-Runtime, Voice, Multi-Agent

---

## Goal

> Ein laufender Agenten-Turn ist aus **jedem** Zustand innerhalb einer Sekunde
> abbrechbar, und die Konversationshistorie bleibt dabei **immer** konsistent
> fortsetzbar.

**Messbar erreicht, wenn:** Ein Abbruch während eines laufenden Shell-Kommandos tötet
den Prozess in ≤1 s; nach jedem Abbruch ist die Session ohne Fehler fortsetzbar; kein
`tool_call` bleibt jemals ohne Antwort in der Historie.

---

## Kontext

**Barge-in ist Cancellation.** Wenn VibeMind spricht und der Nutzer dazwischenredet,
muss der laufende Turn sofort enden — mitten im TTS, mitten im Modell-Stream, mitten
in einem Tool-Aufruf, oder während auf eine Genehmigung gewartet wird.

OpenWorker hat das gelöst (`engine.py:120-148, 504-515`), mit fünf Abbruchpfaden:

| Zustand | Mechanismus |
|---|---|
| Mitten im Modell-Stream | Producer-Thread prüft das Cancel-Event zwischen Chunks; der Konsument rennt bei jedem `queue.get()` gegen das Event (`engine.py:420-428`) |
| Mitten im Tool | `interrupt_hooks` → `LocalExecutor.interrupt_now()` → Abort-Flag; das Vordergrundkommando stirbt binnen ≤0,5 s (`shell.py:300-304`) |
| Warten auf Genehmigung/Frage/Plan | `_interruptible()` rennt die Coroutine gegen Cancel **und cancelt die Task**, damit ein später beantwortetes Inbox-Item ins Leere läuft |
| Zwischen Tool-Calls | Restliche Calls erhalten `_interrupted_tool()` |
| Zwischen Iterationen | Loop-Checkpoint |

**Die tragende Invariante** (`engine.py:124-127`): *Jeder* ausstehende `tool_call`
bekommt eine Tool-Result-Message — auch der abgebrochene. Begründung im Original:
„hosted templates reject them, and durable-resume would re-prompt them."

Zusätzlich: Der bereits gestreamte Teiltext wird persistiert
(„the partial the user watched arrive survives"), aber **ohne** halbfertige Tool-Calls —
die würden entweder verwaisen oder gegen den Abbruch ausgeführt (`engine.py:309-315`).

---

## Entscheidung

VibeMind übernimmt die Invarianten **wörtlich**:

1. **Vollständigkeitsinvariante:** Jeder ausstehende `tool_call` erhält ein Ergebnis
   (echtes Ergebnis, Fehler oder `interrupted`). Nie ein verwaister Call.
2. **Partial-Preservation:** Was der Nutzer gesehen (oder gehört) hat, bleibt in der
   Historie — Text und Thinking, **nie** halbfertige Tool-Calls.
3. **Abbruch aus jedem Zustand**, mit Interrupt-Hooks für laufende Ressourcen
   (Shell, Browser, Container, TTS-Wiedergabe).
4. **Abgebrochene Wartevorgänge werden aktiv gecancelt**, damit eine späte Antwort
   keinen Zombie-Turn wiederbelebt.

**VibeMind-Erweiterungen:**

| Erweiterung | Grund |
|---|---|
| **Kaskadierender Abbruch** über den Agentenbaum (Supervisor → alle Worker) | Bei Multi-Agent muss ein Abbruch alle Kinder erreichen |
| **TTS als Interrupt-Hook** | Barge-in muss die Wiedergabe stoppen, nicht nur den Turn |
| **Was wurde tatsächlich ausgesprochen?** | Bei Voice ist „was der Nutzer gesehen hat" = „was hörbar wurde". Die Historie muss den *ausgesprochenen* Teil festhalten, nicht den generierten |
| **Container-Kill als Hook** | Bei `ContainerExecutor` ([ADR-0006](ADR-0006-shell-executor.md)) |

Punkt 3 ist die nicht-triviale Ergänzung: Bei Text ist „gesehen" ≈ „gestreamt".
Bei Sprache liegt zwischen generiert und ausgesprochen eine Pufferzeit. Wird der
generierte Text persistiert, „erinnert" sich der Agent an Aussagen, die der Nutzer nie
gehört hat — und die Konversation entgleist.

---

## Begründung

- **Ohne diese Invarianten ist Voice-first nicht möglich.** Ein Sprachsystem, das man
  nicht unterbrechen kann, ist unbenutzbar.
- **Die Historien-Invariante ist keine Feinheit, sondern eine harte Anforderung.**
  Verwaiste `tool_call`s werden von Chat-Templates abgelehnt und brechen die
  Wiederaufnahme ([ADR-0001](ADR-0001-inbox-governance.md)).
- **Es ist schwer, das nachträglich richtig zu machen.** Der Abbruchpfad berührt jede
  Schicht; wenn er nicht von Anfang an durchgezogen ist, entstehen Zustände, die man
  einzeln jagen muss.
- **Bei Multi-Agent multipliziert sich das Problem.** Ein Abbruch, der nur den
  Supervisor trifft, hinterlässt laufende Worker mit Seiteneffekten.

---

## Konsequenzen

**Positiv**
- Barge-in wird umsetzbar.
- Sessions bleiben nach jedem Abbruch fortsetzbar.
- Kill-Switch pro Space wird trivial (kaskadierender Abbruch).
- Kein Ressourcenleck (Shells, Container, Browser-Kontexte) nach Abbruch.

**Negativ / Kosten**
- **Jeder Ausführungspfad braucht einen Interrupt-Hook.** Jede neue Ressourcenart
  (Container, MCP-Aufruf, n8n-Workflow, TTS) muss ihren Hook registrieren — das ist
  Disziplin, keine Einmalarbeit.
- **Externe Seiteneffekte sind nicht abbrechbar.** Eine bereits gesendete Slack-Nachricht
  bleibt gesendet. Der Abbruch verhindert nur *weitere* Aktionen. Das muss dokumentiert
  und in der UI sichtbar sein.
- Test-Aufwand: Abbruchpfade brauchen eigene Tests je Zustand (OpenWorker hat dafür
  `test_engine_stop.py`).

**Risiko**
- **Teilweise ausgeführte Multi-Step-Operationen.** Ein Abbruch mitten in „drei Dateien
  schreiben" hinterlässt einen inkonsistenten Zustand. Gegenmaßnahme: Kompensation
  gehört zum Planner ([ADR-0011](ADR-0011-planner-neuentwicklung.md)), nicht zum
  Abbruchmechanismus — aber der Plan muss wissen, wo er stand.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Nur zwischen Iterationen abbrechen** | Verworfen: Latenz bis zu einem vollen Modellaufruf + Tool-Lauf (bis 10 Minuten). Für Voice untragbar |
| **Prozess-Kill statt kooperativem Abbruch** | Verworfen: verliert Zustand, keine konsistente Historie, keine Wiederaufnahme |
| **`asyncio.CancelledError` durchreichen** | Verworfen als alleinige Lösung: erreicht keine blockierenden Thread-Aufrufe (Provider-SDKs, Shell-Reads) — genau der Grund, warum OpenWorker ein explizites Event + Hooks nutzt |
| **Nur TTS stoppen, Turn weiterlaufen lassen** | Verworfen: der Agent würde weiter handeln, während der Nutzer bereits etwas anderes will — die häufigste Barge-in-Fehlerquelle |
