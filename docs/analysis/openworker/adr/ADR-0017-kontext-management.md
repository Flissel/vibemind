# ADR-0017 — Kontext als verwaltete Ressource

**Status:** Vorgeschlagen · **Kategorie:** C (neu entwickeln) · **Phase:** 3
**Betrifft:** Kosten, Sessiondauer, Zuverlässigkeit

---

## Goal

> Eine VibeMind-Session läuft über **hunderte** Turns, ohne in das Kontextlimit zu
> laufen und ohne dass die Kosten pro Turn linear mit der Sessiondauer steigen.

**Messbar erreicht, wenn:** Sessions mit > 100 Turns laufen fehlerfrei; die
Prompt-Cache-Trefferquote auf dem statischen Anteil liegt über 50 %; Kosten pro Turn
bleiben über die Sessiondauer annähernd konstant.

---

## Kontext

**OpenWorker hat keinerlei Kontextverwaltung.** `_outbound_messages()`
(`engine.py:878-982`) strippt Anzeige-Sidecars und passt PDFs/Bilder an die
Modellfähigkeiten an — aber es **kürzt nie**. Volltextsuche nach `compact`,
`summariz`, `token_budget`, `context_window`, `truncate_history` im Engine-Pfad:
keine Treffer ([11 B-01](../11-performance.md#b-01)).

| Turn | Historie | Verhalten |
|---|---|---|
| 1–10 | < 20 k Token | normal |
| 30–50 | 60–120 k Token | Kosten steigen linear, Latenz spürbar |
| 80+ | > 200 k Token | **Provider-Fehler → Session tot** |

Ein einzelnes Tool-Result kann 20.000 Zeichen sein (`shell.py:145`). Zehn Shell-Calls =
~50 k Token, **permanent** in der Historie.

**Erschwerend:** Die Historie ist die *einzige* Zustandsquelle — was gleichzeitig die
Stärke des Durable-Resume-Designs ist ([ADR-0001](ADR-0001-inbox-governance.md)).
Kompaktierung kollidiert damit direkt.

**Und eine vermeidbare Kostenquelle:** Alle Erinnerungen wandern in den *Systemprompt*
(`agent.py:255-260`). Da sie sich ändern, ist der Prompt-Prefix nie stabil — und
Prompt-Caching ist damit wertlos.

---

## Entscheidung

Ein `ContextManager` zwischen Agent und Provider mit vier Mechanismen.

### 1. Token-Budget pro Turn

Harte Obergrenze, **bevor** der Provider sie durchsetzt. Bei Überschreitung greift
Mechanismus 2 — statt eines Fehlers.

### 2. Sliding Window + hierarchische Zusammenfassung

```
[System] [Zusammenfassung der Turns 1–40] [Zusammenfassung 41–70] [Turns 71–80 vollständig] [aktueller Turn]
```

Ältere Turns werden verdichtet; Zusammenfassungen wiederum zu Meta-Zusammenfassungen.
Die letzten n Turns bleiben immer vollständig.

**Harte Invariante:** **Unbeantwortete `tool_call`s werden nie zusammengefasst.**
Sonst bricht Durable Resume ([ADR-0003](ADR-0003-cancellation-invarianten.md)) —
`_unanswered_trailing_tool_calls()` muss sie unverändert vorfinden. Das ist ein
expliziter Testfall, kein Implementierungsdetail.

### 3. Artefakt-Handles ⭐

Tool-Results über einem Schwellwert wandern in den Artefaktspeicher. Das Modell erhält:

```json
{"handle": "art:4f2a", "summary": "pytest: 143 passed, 2 failed",
 "schema": {...}, "size_bytes": 84213,
 "hint": "read_artifact('art:4f2a', range=...) für Details"}
```

**Das ist der wirkungsvollste Mechanismus.** Ein 20-k-Zeichen-Testlauf wird zu ~50 Token
plus optionalem Nachladen. Er passt exakt zu OpenWorkers Tail-Trunkierungs-Erkenntnis
(„Verdikte stehen am Ende") — nur ohne den Rest wegzuwerfen.

### 4. Stabiler Cache-Prefix

| Systemprompt (statisch, cachebar) | Ephemerer Block (pro Turn) |
|---|---|
| Persona-Prompt | Erinnerungen (Recall, [ADR-0008](ADR-0008-memory-architektur.md)) |
| Narration-Regeln | Root-Verzeichnisse |
| Umgebungs-Grundlagen | Modus-Hinweise |
| Skill-Katalog | Datum/Uhrzeit |

Der Injektionspunkt existiert bereits konzeptionell: OpenWorkers `context_provider()`
hängt ephemeren Kontext an die letzte Nutzernachricht und persistiert ihn **nie**
(`engine.py:963-981`). Es muss nur das Richtige dort hinein — und aus dem Systemprompt
heraus.

**Das ist Phase-1-Maßnahme 1.3** und die günstigste Verbesserung der gesamten Roadmap:
eine Verschiebung, kein Neubau, mit 50–90 % Ersparnis auf dem statischen Anteil.

---

## Begründung

- **Ohne Kompaktierung sterben lange Sessions.** Für eine „digitale
  Entwicklungsabteilung", die stundenlang an einem Auftrag arbeitet, ist das ein
  Ausschlusskriterium.
- **Artefakt-Handles lösen das Problem an der Wurzel.** Große Tool-Results sind der
  Haupttreiber des Kontextwachstums — sie gehören nicht in eine Konversation.
- **Der Cache-Prefix ist geschenktes Geld.** Es kostet eine Verschiebung und spart
  dauerhaft.
- **`explore` zeigt, dass das Prinzip funktioniert.** OpenWorkers Subagent ist bereits
  Kontext-Ökonomie: dutzende Dateireads im Kind-Kontext, nur der Report kehrt zurück.
  Der `ContextManager` verallgemeinert dieses Prinzip.

---

## Konsequenzen

**Positiv**
- Sessions beliebiger Länge.
- Kosten pro Turn annähernd konstant statt linear steigend.
- Prompt-Caching wird nutzbar.
- Große Tool-Ausgaben bleiben vollständig verfügbar (im Artefaktspeicher), statt
  abgeschnitten zu werden.

**Negativ / Kosten**
- **Zusammenfassung verliert Information.** Das Modell „vergisst" Details.
  Gegenmaßnahmen: Zusammenfassungen sind strukturiert (Entscheidungen, offene Punkte,
  Artefakte), die Rohhistorie bleibt persistiert und über `recall` erreichbar.
- **Zusammenfassung kostet Modellrunden.** Gegenmaßnahmen: günstigeres Modell dafür,
  inkrementell im Hintergrund statt blockierend.
- **Handles erfordern eine Modellrunde zum Nachladen.** In der Praxis selten nötig,
  wenn die Zusammenfassung gut ist.
- **Kollision mit Durable Resume** (siehe Invariante oben) — braucht einen expliziten
  Test.

**Risiko**
- **Zu aggressive Kompaktierung macht den Agenten dümmer**, und zwar unauffällig.
  Wahrscheinlichkeit mittel, Wirkung hoch. Gegenmaßnahmen: großzügiges Fenster als
  Default, Messung über die Eval-Harness (Phase 5.5) **vor** dem Nachjustieren,
  Kompaktierungsereignisse im Governance-Log sichtbar.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Status quo (unbegrenzt)** | Verworfen: Sessions sterben |
| **Hartes Abschneiden** (älteste Nachrichten verwerfen) | Verworfen: verliert Entscheidungen und Kontext ersatzlos; bricht Tool-Call/Result-Paare |
| **Nur Artefakt-Handles, keine Zusammenfassung** | Deckt den Haupttreiber ab und ist deutlich einfacher. **Empfehlung: als erste Stufe umsetzen** (3.4 vor 3.3), Zusammenfassung danach |
| **Session bei n Turns beenden und neu starten** | Verworfen: verliert den Zusammenhang, den lange Aufträge gerade brauchen |
| **Externes Kontextfenster-Management-Framework** | Verworfen: das Zusammenspiel mit Durable Resume und der Genehmigungsschicht ist VibeMind-spezifisch |
| **Auf größere Kontextfenster warten** | Verworfen: Kosten skalieren mit dem Kontext, auch wenn er hineinpasst. Größere Fenster verschieben das Problem, sie lösen es nicht |
