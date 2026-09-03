# ADR-0011 — Planner als eigene Komponente mit Plan-Artefakt

**Status:** Vorgeschlagen · **Kategorie:** C (neu entwickeln) · **Phase:** 4
**Betrifft:** Orchestrierung, Multi-Agent, Budget, Genehmigung

---

## Goal

> Ein komplexer Auftrag wird in einen **prüfbaren, ausführbaren, budgetierten Plan**
> zerlegt, den ein Mensch genehmigen und dessen Fortschritt er verfolgen kann.

**Messbar erreicht, wenn:** Ein Plan mit ≥ 5 Schritten wird von ≥ 3 Agenten
abgearbeitet; ein fehlgeschlagener Schritt löst gezieltes Replanning nur seines
Teilbaums aus.

---

## Kontext

In der VibeMind-Zielarchitektur steht der Planner an zentraler Stelle:
`Voice → Intent → Planner → Workflow → Agenten → Tool Calls → Memory → Ergebnis`.

**OpenWorker hat keinen Planner.** Was so heißt, sind drei getrennte Dinge:

1. **Plan-Mode** — ein Permission-Mode, der Schreiben und Shell **hart** blockiert
   (`permissions.py:131-134`, kein „ask", schlicht `deny`).
2. **`propose_plan`** — ein engine-interzeptiertes Tool, das einen Markdown-Text zur
   Genehmigung vorlegt (`engine.py:704-769`).
3. **`todo_write`** — eine Fortschrittsliste, die laut Cowork-Prompt ausdrücklich
   **für die UI** existiert („no todo list means the user sees nothing happening",
   `agents/cowork.py:24-28`).

Die Zerlegung macht das LLM implizit. Es gibt keine Abhängigkeiten, keine
Ressourcenzuweisung, kein Replanning, keine Verifikation, kein Budget.

**Eine Sache ist aber genau richtig gelöst und wird übernommen:** Bei Genehmigung
schaltet die **laufende Session** in den Ausführungsmodus (`engine.py:740-751`) — kein
Neustart, kein Kontextverlust. Der Explorationskontext, der zum Plan geführt hat, bleibt
für die Umsetzung erhalten.

---

## Entscheidung

Ein Planner, der ein **strukturiertes Artefakt** erzeugt:

```yaml
plan:
  id: plan-4f2a
  goal: "Release 2.4 vorbereiten"
  created_from: {intent: release_prepare, space: coding}
  budget: {tokens: 500000, wall_clock_s: 3600, spend_eur: 12}
  steps:
    - id: s1
      intent: analyze_changes
      agent_role: explorer
      inputs: {since_tag: "v2.3"}
      output_schema: {type: object, properties: {changes: {...}}}
      depends_on: []
      budget: {tokens: 50000}
      risk: read
    - id: s2
      intent: write_changelog
      agent_role: implementer
      depends_on: [s1]
      risk: write_local
    - id: s3
      intent: create_release_pr
      agent_role: implementer
      depends_on: [s2]
      risk: external          # → Genehmigung
  verification:
    - {check: tests_green, blocking: true}
    - {check: no_new_lint_errors, blocking: false}
  on_failure: replan_subtree
```

**Fünf Eigenschaften, die das Artefakt haben muss:**

| Eigenschaft | Warum |
|---|---|
| **Genehmigbar** | Ein Mensch sieht *vorher*, was passieren wird — inklusive der `EXTERNAL`-Schritte |
| **Ausführbar** | `depends_on` bildet einen DAG; der Supervisor plant daraus die Reihenfolge und Parallelität |
| **Prüfbar** | `verification` macht „fertig" objektiv statt zur Modellbehauptung |
| **Replanbar** | Bei Fehlschlag wird nur der betroffene Teilbaum neu geplant, nicht der ganze Plan |
| **Budgetiert** | Pro Schritt und pro Plan — verhindert unbegrenzte Multi-Agent-Läufe |

**Hierarchie:** Ziel → Epics → Tasks → Schritte. Ein Schritt kann sich zur Laufzeit
selbst in einen Unterplan zerlegen (begrenzte Tiefe, Budget wird vererbt).

**Übernommen aus OpenWorker:** Plan-Genehmigung schaltet die Autonomie der laufenden
Session um; der Genehmigende wählt den Folgemodus („weiter jeden Schreibvorgang fragen"
vs. „genehmigten Plan durchziehen").

**Abgrenzung zu n8n** (wichtig, sonst entsteht doppelte Wahrheit):

| n8n | Planner |
|---|---|
| **Deterministische** Integrationen, vom Menschen entworfen | **Adaptive** Abläufe, vom LLM erzeugt |
| Stabile, wiederkehrende Datenflüsse | Einmalige, kontextabhängige Aufträge |
| Kein LLM im Kontrollfluss nötig | LLM erzeugt und revidiert den Ablauf |

Ein Plan-Schritt **darf** einen n8n-Workflow aufrufen. Ein n8n-Workflow **darf** einen
Plan anstoßen. Aber sie beschreiben nicht dasselbe.

---

## Begründung

- **Ohne Plan-Artefakt gibt es keine Genehmigung im Voraus** — nur Genehmigung pro
  Einzelaktion, was bei 30-Schritt-Aufträgen zu Genehmigungsmüdigkeit führt.
- **Ohne DAG gibt es keine Parallelität** — der Worker Pool
  ([ADR-0014](ADR-0014-worker-pool.md)) hat sonst nichts zu verteilen.
- **Ohne Verifikation ist „fertig" eine Modellbehauptung.** Bei einer „digitalen
  Entwicklungsabteilung" ist das nicht ausreichend.
- **Ohne Budget ist ein Multi-Agent-Lauf finanziell unbegrenzt.**
- **Hierarchie ist der Kern der Aufgabenstellung.** „Digitale Entwicklungsabteilung"
  ist per Definition hierarchisch.

---

## Konsequenzen

**Positiv**
- Genehmigung im Voraus statt Einzelfreigaben.
- Nachvollziehbarer, sichtbarer Fortschritt (auch per Sprache abfragbar).
- Parallelisierbarkeit ohne Rätselraten.
- Kostenkontrolle.
- Replanning ohne Totalverlust.

**Negativ / Kosten**
- **Planqualität ist der Flaschenhals.** Ein schlechter Plan ist schlimmer als kein
  Plan, weil er Genehmigung suggeriert. Gegenmaßnahmen: Planning mit dem stärksten
  verfügbaren Modell (`model_policy`, [ADR-0009](ADR-0009-skill-persona-format.md)),
  Plan-Kritiker als zweite Instanz, Eval-Harness für Plangüte.
- **Overhead bei einfachen Aufgaben.** Nicht jeder Auftrag braucht einen Plan.
  Gegenmaßnahme: Schwelle — unter n Schritten läuft der Direktpfad ohne Planner.
  Der Intent-Router (Brain) entscheidet das bereits heute über `execution_target`.
- **Replanning kann oszillieren** (Plan A scheitert → Plan B scheitert → Plan A).
  Gegenmaßnahme: Replan-Zähler pro Teilbaum, danach Eskalation an den Menschen.
- Zusätzliche Modellrunden für Planung und Verifikation.

**Risiko**
- **Doppelte Wahrheit mit n8n.** Wahrscheinlichkeit mittel. Gegenmaßnahme: die
  Abgrenzung oben wird verbindlich dokumentiert und im Review geprüft.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Status quo (implizite LLM-Planung)** | Verworfen: nicht genehmigbar, nicht parallelisierbar, nicht budgetierbar |
| **`propose_plan` als Markdown übernehmen** | Verworfen als Ziel: nicht maschinenlesbar. **Als UI-Darstellung des Artefakts sinnvoll** |
| **n8n als Planner** | Verworfen: n8n-Workflows sind statisch entworfen; adaptive Zerlegung ist nicht sein Modell |
| **LangGraph als Plan-Engine** | Ernsthafte Alternative — Graph + Checkpointer + Tracing. Aber: Der Graph wird zur Entwurfszeit definiert, nicht vom LLM zur Laufzeit erzeugt. **Empfehlung: LangGraph-Muster (Checkpointing) übernehmen, Plangenerierung eigen** |
| **CrewAI-artige Task-Listen** | Zu schwach: keine echten Abhängigkeiten, keine Verifikation, kein Replanning |
| **Kein Planner, nur Multi-Agent-Konversation** (reines AutoGen) | Verworfen: Konversation ist nicht genehmigbar und nicht budgetierbar; Fortschritt ist nicht messbar |
