# ADR-0012 — Multi-Agent auf AutoGen mit Governance-Gate

**Status:** Vorgeschlagen · **Kategorie:** C (neu entwickeln) · **Phase:** 4
**Betrifft:** Orchestrierung, Sicherheit, Kosten, Debugbarkeit

---

## Goal

> Mehrere spezialisierte Agenten arbeiten an einem Plan — mit **strukturell**
> begrenzten Rechten, typisierten Ergebnissen und **ohne** Möglichkeit, die
> Governance-Schicht zu umgehen.

**Messbar erreicht, wenn:** Ein Test beweist, dass **kein** Agent-Tool-Aufruf an der
Policy-Engine vorbeiführt; ein Worker mit `role: reviewer` kann nachweislich nicht
schreiben.

---

## Kontext

OpenWorker hat **kein** Multi-Agent-System. Es gibt genau eine Delegationsform:
`explore` (`tools/subagent.py`) — und die ist bewusst minimal:

| Eigenschaft | Umsetzung |
|---|---|
| Rechte **strukturell** begrenzt | Kind-`PermissionEngine` in `Mode.PLAN` — „hard-blocks writes/shell **no matter what the child decides**" |
| Kein Approval-Roundtrip | kein Approver → das Kind kann gar nicht fragen |
| Keine Rekursion | die Kind-Registry enthält kein `explore` |
| Eigener Kontext | nur der finale Report kehrt zurück |
| Parallelisierbar | weil `risk_level="low"` — was nur möglich ist, weil es nichts tun kann |

**Diese Kausalkette ist das Wertvolle daran** und im Docstring explizit gemacht
(`subagent.py:7-11`): Weil die Rechte strukturell begrenzt sind, ist der Subagent
risikoarm; weil er risikoarm ist, darf er parallel laufen.

**Was fehlt:** schreibende Subagenten, Agent-zu-Agent-Kommunikation, Rollen,
Hierarchie, Handoffs, typisierte Ergebnisse.

VibeMinds Zielarchitektur nennt AutoGen für „Gesprächslogik und Agentenkoordination".
Das `agentfarm`-Modul ist in `vibemind.config.json` derzeit **deaktiviert**
(„Docker build references … which doesn't exist; needs source restore").

---

## Entscheidung

**AutoGen als Koordinationsschicht, VibeMind-Governance als Gate darunter.**

### Agentenmodell

```
Supervisor ──delegate──▶ Worker(role, scope, budget, allowed_tools)
           ◀──report──── typisiertes Ergebnis (Schema, nicht Freitext)
Worker     ──escalate─▶ Supervisor    (blockiert / Budget erschöpft)
Worker     ──handoff──▶ Worker        (Übergabe mit explizitem Kontextpaket)
Supervisor ──ask──────▶ Inbox         (Mensch, ADR-0001)
```

### Vier Eigenschaften, aus `explore` verallgemeinert

1. **Rechte strukturell begrenzt.** Jeder Worker bekommt eine eigene
   Policy-Engine-Instanz mit seinem Scope. Ein `reviewer` **kann** nicht schreiben —
   nicht weil sein Prompt es sagt, sondern weil die Engine es ablehnt und die Registry
   das Tool gar nicht enthält ([ADR-0007](ADR-0007-tool-registry-namespaces.md),
   [ADR-0009](ADR-0009-skill-persona-format.md)).
2. **Eigener Kontext.** Nur das Ergebnis kehrt zurück — die Kontext-Ökonomie, die
   `explore` bereits richtig macht, wird zum allgemeinen Prinzip.
3. **Begrenzte Rekursion.** Tiefenlimit + vererbtes Budget. Kein Agent kann unbegrenzt
   Kinder erzeugen.
4. **Typisierte Ergebnisse.** ⭐ Die wichtigste Ergänzung: `explore` gibt Markdown
   zurück. Ein Worker im Pool muss ein **validiertes Schema** liefern — sonst ist
   Komposition nicht automatisierbar und der Supervisor muss Freitext interpretieren.

### Das Governance-Gate — der kritische Punkt

AutoGen bringt eine **eigene Ausführungsschleife** mit. Damit die Governance greift,
muss **jeder** Tool-Aufruf durch die Policy-Engine.

**Gewählte Umsetzung: Proxy-Tools.** Jedes Tool, das einem AutoGen-Agenten registriert
wird, ist ein Wrapper, der intern die Policy-Engine aufruft und bei `needs_user` in die
Inbox geht. AutoGen sieht nur eine normale Funktion.

**Warum nicht AutoGens Executor ersetzen:** mächtiger, aber es bindet VibeMind an
AutoGen-Interna und bricht bei jedem Upstream-Update.

**Pflicht-Testfall:** Ein Test, der beweist, dass es **keinen** Pfad gibt, auf dem ein
Agent ein Tool ohne Policy-Prüfung erreicht. Ohne diesen Test gilt die Anforderung als
nicht erfüllt.

---

## Begründung

- **Multi-Agent ohne Governance ist ein Rückschritt.** n Agenten mit vollen Rechten sind
  n unabhängige Fehlerquellen. Deshalb steht [ADR-0001](ADR-0001-inbox-governance.md)
  in Phase 2 und dieser Punkt in Phase 4 — nicht umgekehrt.
- **AutoGen ist die richtige Basis für die Koordinationsschicht** — es ist die einzige
  Bibliothek des Vergleichsfelds, deren Kernabstraktion Konversation zwischen Agenten
  ist ([15.2](../15-architekturvergleich.md#152-agentenmodell)).
- **AutoGen bringt keine Governance mit** — wie LangGraph und CrewAI auch nicht.
  Deshalb ist die Kombination komplementär, nicht redundant.
- **Typisierte Ergebnisse sind die Voraussetzung für Automatisierung.**
  Freitext-Reports komponieren nicht; der Supervisor müsste sie parsen und würde raten.

---

## Konsequenzen

**Positiv**
- Echte Parallelisierung entlang des Plan-DAG.
- Kontext-Ökonomie durch isolierte Sub-Kontexte.
- Least Privilege pro Rolle, strukturell durchgesetzt.
- Spezialisierung (Reviewer, Implementer, Explorer) statt Alleskönner-Prompt.

**Negativ / Kosten**
- **Debugbarkeit sinkt drastisch.** Ein Fehler in einem 12-Agenten-Lauf ist ohne
  verteiltes Tracing nicht auffindbar. **Harte Kopplung:** OTel (Phase 5.4) ist keine
  Kür, sondern Betriebsvoraussetzung.
- **Kosten skalieren mit der Agentenzahl.** Jeder Agent hat eigenen Kontext und eigene
  Modellrunden. Ohne Budget ([ADR-0011](ADR-0011-planner-neuentwicklung.md)) ist der
  Lauf unbegrenzt.
- **Konversationelle Endlosschleifen** (zwei Agenten reichen einander die Aufgabe zu).
  Gegenmaßnahmen: Handoff-Zähler, Budget, Tiefenlimit, Timeout pro Schritt.
- **Upstream-Abhängigkeit von AutoGen** — API-Änderungen betreffen die
  Koordinationsschicht. Gegenmaßnahme: dünne Adapterschicht, damit ein Wechsel
  (LangGraph, eigene Schleife) möglich bleibt.
- `agentfarm` muss zuerst wieder lauffähig gemacht werden (aktuell deaktiviert).

**Risiko**
- **AutoGen umgeht die Policy-Engine.** Wahrscheinlichkeit mittel, Wirkung **sehr hoch**.
  Gegenmaßnahme: Proxy-Tools + Beweis-Test (siehe oben). Dieser Test ist
  Ausrollkriterium.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Nur `explore`-artige read-only Subagenten** (OpenWorker-Status) | Verworfen als Ziel: löst nur Kontext-Ökonomie, keine Arbeitsteilung. **Bleibt als Spezialfall (Rolle `explorer`) erhalten** |
| **LangGraph statt AutoGen** | Ernsthafte Alternative: expliziter Kontrollfluss, Checkpointer, LangSmith-Tracing — deutlich besser debugbar. Nachteil: Graph zur Entwurfszeit statt Konversation zur Laufzeit. **Empfehlung: Checkpointing- und Tracing-Muster übernehmen, Koordination bei AutoGen belassen** |
| **CrewAI** | Einfacher, aber schwächere Kontrolle über Kontext und Rechte |
| **Eigene Multi-Agent-Schleife** | Volle Kontrolle, aber ~8 PW zusätzlich für ein gelöstes Problem |
| **Kein Multi-Agent** (ein Agent, sequenziell) | Verworfen: „digitale Entwicklungsabteilung" ist die Anforderung; ein Agent kann nicht parallelisieren und nicht spezialisieren |
