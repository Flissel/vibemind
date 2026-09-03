# ADR-0007 — Tool-Registry mit Namespaces und Retrieval

**Status:** Vorgeschlagen · **Kategorie:** C (neu entwickeln) · **Phase:** 3
**Betrifft:** Tool-System, Token-Kosten, Auswahlqualität, Multi-Agent

---

## Goal

> Ein Agent sieht pro Turn **die Tools, die er braucht** — nicht alle. Tool-Schemas
> kosten weniger als 8.000 Token pro Request, bei gleichbleibender oder besserer
> Intent-Genauigkeit.

**Messbar erreicht, wenn:** Schema-Token pro Request < 8.000; `intent_validation`
zeigt keine Verschlechterung gegenüber der Vollliste; eine Namenskollision erzeugt
einen Fehler statt eines stillen Überschreibens.

---

## Kontext

OpenWorkers Registry ist eine flache `dict[str, ToolSpec]`, und **alle** Schemas gehen
in **jeden** Request (`engine.py:393`).

**Rechnung** ([11 B-02](../11-performance.md#b-02)):

| Quelle | Tools | Token |
|---|---|---|
| Basis | ~15 | 3.000 |
| Connectoren (33 Dienste) | bis 159 | bis 31.800 |
| MCP (3 Server) | ~45 | 9.000 |
| Memory/Skills/Scheduling/Web | ~10 | 2.000 |
| **pro Request** | **~230** | **~46.000** |

Dazu zwei Folgeprobleme:
1. **Auswahlqualität.** Modelle wählen bei >50 Tools messbar schlechter. VibeMind hat
   das selbst dokumentiert: `intent_validation/00_MASTER.md` beschreibt Fehlwahl #7
   („such die Idee X" → `bubble_evaluate` statt `idea_find`, 3/3 reproduzierbar) mit
   Root-Cause „`bubble_evaluate`-desc enthält 'idea' prominent" — **bei einer weit
   kleineren Toolmenge**.
2. **Kollisionen.** `registry.register()` überschreibt kommentarlos
   (`registry.py:45-46`); MCP-Namen werden bei 64 Zeichen hart abgeschnitten
   (`mcp/tools.py:29-31`). Zwei lange Servernamen können denselben Tool-Namen erzeugen.

**Ironie:** OpenWorker hat Progressive Disclosure bereits implementiert — für *Skills*
(`skills/base.py:6-8`: nur Katalog im Kontext, Rumpf per `load_skill`). Das Muster liegt
im selben Repo und wurde nicht auf Tools angewandt.

---

## Entscheidung

**Dreistufige Sichtbarkeit + Namespaces + Rollen-Scoping.**

### Namespaces

```
local:read_file
mcp:github/create_issue
connector:slack/send_message
space:coding/run_tests
```

- **Kollision = Fehler beim Registrieren**, nicht Überschreiben.
- Namen werden bei Bedarf gehasht statt abgeschnitten (Kollisionsfreiheit vor Lesbarkeit).

### Dreistufige Sichtbarkeit pro Turn

| Stufe | Inhalt | Token |
|---|---|---|
| **1 — immer sichtbar** | Kern-Tools: Dateien lesen/schreiben, Shell, `ask_user`, `recall`, `load_toolset` | ~2.000 |
| **2 — Katalog** | Ein Eintrag pro Namespace: „`mcp:github` — 18 Tools für Issues, PRs, Reviews. `load_toolset('mcp:github')`" | ~500 |
| **3 — Retrieval** | Top-k Tools per Embedding-Ähnlichkeit zur aktuellen Aufgabe (k ≈ 15) | ~3.000 |

Stufe 2 ist exakt OpenWorkers Skill-Muster, auf Tools angewandt.

### Rollen-Scoping

Jede Agentenrolle deklariert ihre Namespaces:

```yaml
role: planner    → [local:read, local:search, mcp:*/read, plan:*]
role: implementer→ [local:*, space:coding/*, mcp:github/*]
role: reviewer   → [local:read, local:search, space:coding/test]
```

Least Privilege pro Rolle, nicht nur pro Session.

### Fallback

Pro Space konfigurierbar: **Vollliste statt Retrieval**. Nötig als Sicherheitsnetz und
als Referenz für die Intent-Regression.

---

## Begründung

- **Kostenersparnis ist der offensichtliche Gewinn** (~46.000 → ~5.500 Token/Request),
  aber **Auswahlqualität ist der wichtigere.** VibeMinds eigene Fehlwahl-Analyse
  belegt, dass Beschreibungsähnlichkeit bereits bei kleinen Mengen zu Fehlrouting führt.
- **Bei Multi-Agent multipliziert sich das:** n Agenten × 230 Tools ist wirtschaftlich
  und qualitativ nicht tragbar.
- **Rollen-Scoping ist gleichzeitig eine Sicherheitsmaßnahme:** Ein Reviewer-Agent, der
  `send_message` gar nicht *sieht*, kann es nicht aufrufen — unabhängig von der
  Permission-Engine. Defense in Depth.
- **Namespaces sind Pflicht, nicht Kür.** VibeMind hat mehrere MCP-Server, mehrere
  Spaces und eigene Tools. Ohne Namensraum sind Kollisionen unvermeidlich, und stilles
  Überschreiben ist die schlechteste Fehlerart.

---

## Konsequenzen

**Positiv**
- Deutlich geringere Token-Kosten und bessere Auswahlqualität.
- Least Privilege pro Rolle.
- Neue Tools/Server verschlechtern bestehende Turns nicht mehr.
- Skaliert auf beliebig viele MCP-Server.

**Negativ / Kosten**
- **Retrieval kann danebengreifen.** Wenn das relevante Tool nicht in den Top-k landet,
  scheitert die Aufgabe — schlimmer noch: das Modell improvisiert.
  **Gegenmaßnahmen:** (a) `load_toolset()` als expliziter Ausweg, (b) Stufe 2 nennt
  *alle* Namespaces, sodass das Modell weiß, was existiert, (c) Rollen-Scoping
  reduziert den Suchraum vor dem Retrieval.
- **Zusätzliche Latenz** durch Embedding der Aufgabe (~50–150 ms). Cachebar.
- **Ein weiterer beweglicher Teil**: Embedding-Modell, Index, Aktualisierung bei
  Tool-Änderungen.
- Migration: alle bestehenden Tool-Referenzen (Personas, Skills, Automations) brauchen
  Namespaces.

**Risiko**
- **Qualitätsverlust bleibt unsichtbar**, wenn nicht gemessen wird.
  **Harte Bedingung:** 3.2 darf nur mit laufender `intent_validation`-Regression
  ausgerollt werden (446 Intents, 4 Assertions je Intent). Das ist der Grund, warum
  VibeMind diese Harness bereits hat — sie wird hier zum Ausrollkriterium.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Status quo (alle Schemas)** | Verworfen: Kosten und Qualität skalieren nicht |
| **Nur manuelles Scoping pro Persona** (OpenWorkers `tools:`-Liste) | Teilweise gut, aber statisch — deckt nicht ab, dass eine Persona je nach Aufgabe andere Tools braucht. **Bleibt als Stufe-0-Filter erhalten** |
| **Nur Progressive Disclosure ohne Retrieval** | Einfacher und deterministisch, aber kostet eine zusätzliche Modellrunde (`load_toolset` → erneuter Aufruf). **Empfehlung: als Stufe 2 behalten, Retrieval ergänzt sie** |
| **Nur Retrieval ohne Katalog** | Verworfen: Das Modell weiß dann nicht, was es *nicht* sieht — und kann nicht gezielt nachladen |
| **Hierarchisches Routing über einen Meta-Agenten** | Mächtig, aber eine zusätzliche Modellrunde pro Turn und ein weiterer Fehlerpunkt. VibeMinds Brain Cap-Router deckt die Intent-Ebene bereits ab; hier geht es um die Tool-Ebene darunter |
| **Ein Tool pro Namespace mit `action`-Parameter** | Reduziert Schemas drastisch, verlagert aber die Auswahl in einen unstrukturierten String — schlechtere Validierung, schlechtere Modellführung |
