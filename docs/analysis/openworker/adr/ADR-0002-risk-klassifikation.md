# ADR-0002 — Risikoklassifikation als deklarative Tool-Eigenschaft

**Status:** Vorgeschlagen · **Kategorie:** A (direkt übernehmen, mit einer Korrektur) · **Phase:** 1
**Betrifft:** Permission-Engine, Tool-System, unbeaufsichtigter Betrieb

---

## Goal

> Jedes Tool in VibeMind trägt eine **deklarierte Risikoklasse**. Die Frage
> „braucht dieser Aufruf Aufsicht?" wird durch **eine** Funktion beantwortet,
> nicht durch verstreute Sonderfälle.

**Messbar erreicht, wenn:** Kein Genehmigungspfad im Code enthält eine Tool-Namensliste;
ein neues Tool ohne Metadaten wird **fail-closed** behandelt.

---

## Kontext

OpenWorkers `coworker/risk.py` (58 Zeilen) ersetzt hartkodierte Namensmengen
(`WRITE_TOOLS`, `SHELL_TOOL`), die zuvor in der Permission-Engine standen, durch eine
deklarierte Eigenschaft:

```python
class RiskClass(str, Enum):
    READ         # keine Seiteneffekte
    WRITE_LOCAL  # verändert den Workspace — pfad-gescoped + mode-gated
    EXEC         # führt Kommandos aus — mode-gated
    EXTERNAL     # Seiteneffekte außerhalb der Maschine — Inbox-Hook im unbeaufsichtigten Betrieb
```

Auflösung: **User-Override → Namenstabelle → Metadaten (`requires_approval` → EXTERNAL)
→ sonst READ** (`risk.py:39-53`).

Der entscheidende Schnitt ist `WRITE_LOCAL` vs. `EXTERNAL`: lokale Schreibvorgänge sind
reversibel und im eigenen Verantwortungsbereich; externe Aktionen (Nachricht senden,
Ticket schließen, Zahlung auslösen) sind es nicht. Nur letztere brauchen im
unbeaufsichtigten Betrieb zwingend den Inbox-Pfad.

**Der Defekt im Original:** Der Fallback ist `READ`. Ein Tool ohne Metadaten gilt als
harmlos und läuft **ohne jede Prüfung** ([08 R-06](../08-security-risikoanalyse.md#r-06)).

---

## Entscheidung

VibeMind übernimmt `RiskClass` + `classify()` + Override-Resolver **mit zwei Änderungen**:

1. **Fail-closed:** unbekanntes/undeklariertes Tool → `EXTERNAL`, nicht `READ`.
   Ein Tool muss `READ` **verdienen**, nicht geschenkt bekommen.
2. **Zwei zusätzliche Klassen** für VibeMinds Realität:

```python
DESTRUCTIVE  # irreversibel und weitreichend (stack:rm, DB-Drop, Massen-Delete)
             # → nie durch Standing Grants abdeckbar, immer explizite Zustimmung
SPEND        # verursacht direkte Kosten (Zahlungen, teure API-Aufrufe, Cloud-Ressourcen)
             # → gegen ein Budget geprüft, nicht nur genehmigt
```

`DESTRUCTIVE` bildet ab, was `mcp/docker/approval.py` bereits richtig unterscheidet
(`container:rm` ≠ `stack:rm`) — aber als Klasse statt als Verb-Liste.

---

## Begründung

- **Ein Ort für die Entscheidung.** Ohne Klassifikation landen Tool-Namen in
  if-Kaskaden über die ganze Codebasis — genau der Zustand, aus dem OpenWorker
  herausrefactored hat.
- **Die vier Klassen sind empirisch richtig geschnitten.** Sie decken die
  Unterscheidungen ab, die im Betrieb tatsächlich gebraucht werden: reversibel/nicht,
  lokal/extern, ausführend/nicht.
- **`EXTERNAL` ist die Bedingung für Standing Grants.** Nur eine externe Aktion mit
  deklariertem Ziel kann sicher an ein Ziel gebunden werden
  ([ADR-0005](ADR-0005-standing-rules.md)).
- **`DESTRUCTIVE` und `SPEND` fehlen bei OpenWorker**, weil es weder Infrastruktur
  verwaltet noch Budgets kennt. VibeMind tut beides.

---

## Konsequenzen

**Positiv**
- Genehmigungslogik ist eine Funktion, keine Sammlung von Sonderfällen.
- Neue Tools sind automatisch abgesichert (fail-closed).
- `SPEND` ermöglicht Budgetsteuerung ohne separate Buchführung.
- Voraussetzung für [ADR-0001](ADR-0001-inbox-governance.md),
  [ADR-0005](ADR-0005-standing-rules.md), [ADR-0015](ADR-0015-taint-tracking.md).

**Negativ / Kosten**
- **Jedes bestehende Tool muss klassifiziert werden.** Bei VibeMinds Toolbestand
  (446 Intents, mehrere MCP-Server, Automation_ui mit 19 Perception-Tools) ist das
  echte Fleißarbeit — geschätzt 1–2 PW.
- Fail-closed erzeugt anfangs **mehr** Prompts, bis alles klassifiziert ist. Das ist
  gewollt, aber es braucht eine Migrationsphase mit Reporting („diese 40 Tools sind
  noch unklassifiziert").
- MCP-Tools haben pro Server nur ein Level; pro-Tool-Klassifikation braucht Heuristik
  (Namensmuster wie `get_*`/`list_*` → READ) plus manuelle Overrides.

**Risiko**
- Fehlklassifikation in Richtung `READ` ist ein stiller Sicherheitsfehler.
  Gegenmaßnahme: Klassifikation ist Teil des Code-Reviews; Änderungen an
  Risikoklassen erzeugen einen Audit-Eintrag.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Nur `requires_approval: bool`** | Verworfen: zu grob. Kann „reversibel lokal" nicht von „irreversibel extern" unterscheiden — genau der Schnitt, den unbeaufsichtigter Betrieb braucht |
| **Capability-basiert** (Tool deklariert `fs:write`, `net:send`, …) | Mächtiger und feiner, aber deutlich aufwendiger. **Empfehlung: später ergänzen** — die Risikoklasse bleibt dann die aggregierte Sicht auf die Capabilities |
| **Policy-Sprache (OPA/Rego, Cedar)** | Sehr mächtig, aber Overkill für 6 Klassen; zusätzliche Laufzeitabhängigkeit und Debugging-Aufwand. Sinnvoll erst, wenn Policies pro Kunde/Mandant konfigurierbar werden müssen |
| **LLM entscheidet über das Risiko** | Verworfen: Sicherheitsentscheidungen dürfen nicht vom zu kontrollierenden System getroffen werden |
| **Status quo (Verb-Allowlist)** | Verworfen: skaliert nicht über Docker hinaus |
