# 15 — Architekturvergleich

> **Methodische Einschränkung — wichtig:**
> Nur **OpenWorker** wurde für diese Analyse im Quellcode gelesen (Commit `3766805`).
> Die Aussagen zu OpenHands, OpenInterpreter, Claude Computer Use, OpenAI Codex, Goose,
> Continue, Cline, AutoGen, LangGraph und CrewAI beruhen auf allgemeinem Wissen über
> deren Architektur und **nicht** auf einer Code-Prüfung im Rahmen dieser Arbeit.
> Sie sind als **Orientierungsrahmen** zu lesen, nicht als belegte Befunde. Vor einer
> Technologieentscheidung für VibeMind sollte der jeweilige Kandidat separat geprüft werden.
> OpenWorker-Spalten sind durchgängig belegt.

---

## 15.1 Kategorisierung

Die zehn Systeme gehören zu **vier** verschiedenen Gattungen. Ein direkter Vergleich
ist nur innerhalb einer Gattung sinnvoll:

| Gattung | Systeme | Was sie sind |
|---|---|---|
| **Produkte / Endanwender-Agenten** | **OpenWorker**, OpenHands, OpenInterpreter, Goose | Lauffähige Agenten mit UI, Tools, Genehmigungen |
| **Coding-Assistenten (IDE-nah)** | Continue, Cline, OpenAI Codex | Entwicklerwerkzeuge im Editor/CLI-Kontext |
| **Orchestrierungs-Frameworks** | AutoGen, LangGraph, CrewAI | Bibliotheken zum Bau von Agenten-Systemen |
| **Modell-Fähigkeit** | Claude Computer Use | Eine Modellfähigkeit + Referenz-Harness, kein Produkt |

**OpenWorker konkurriert mit Gattung 1.** Für VibeMind, das ein *Orchestrierungssystem*
baut, sind Gattung 3 und die Governance-Ideen aus Gattung 1 relevant.

---

## 15.2 Agentenmodell

| System | Agentenmodell | Multi-Agent | Planung |
|---|---|---|---|
| **OpenWorker** | 1 Agent/Session, Persona = Prompt + Toolset + Traits. Ein read-only `explore`-Subagent (belegt: `tools/subagent.py`) | ❌ | ❌ Prompt + Permission-Mode |
| OpenHands | Agent mit Event-Stream-Historie, austauschbare Agent-Klassen (CodeAct u. a.) | eingeschränkt (Delegation) | implizit im Agenten |
| OpenInterpreter | Einzelner Code-ausführender Agent (REPL-Schleife) | ❌ | ❌ |
| Goose | Einzelagent mit Extensions (MCP-zentriert), Rezepte/Subrecipes | eingeschränkt | Rezepte als vordefinierte Abläufe |
| Continue | Assistenzmodi (Chat/Edit/Autocomplete/Agent) im Editor | ❌ | ❌ |
| Cline | Plan-/Act-Modus-Paar, Einzelagent | ❌ | expliziter Plan-Modus |
| OpenAI Codex | Cloud-/CLI-Agent mit Sandbox pro Aufgabe | parallele Tasks | implizit |
| AutoGen | **Konversierende Agenten** als Kernabstraktion, GroupChat, Handoffs | ✅ **nativ** | über Agentenrollen |
| LangGraph | **Zustandsgraph**; Knoten = Agenten/Funktionen, Kanten = Kontrollfluss | ✅ als Graph | **explizit im Graphen** |
| CrewAI | **Rollen + Tasks + Crew**, sequenziell oder hierarchisch | ✅ | Task-Beschreibungen |

**Einordnung für VibeMind:** Die Zielarchitektur nennt AutoGen für „Gesprächslogik und
Agentenkoordination". Das ist konsistent — AutoGen ist die einzige Gattung-3-Bibliothek,
deren Kernabstraktion *Konversation zwischen Agenten* ist.

**Aber:** AutoGen (wie LangGraph und CrewAI) bringt **keine Governance** mit. Kein
Approval-Modell, kein Risikomodell, kein Audit, keine durable Wiederaufnahme über
Prozessgrenzen. Genau diese Lücke füllt OpenWorkers Schicht — das ist der Grund, warum
die Kombination „AutoGen für Koordination + OpenWorker-Governance darunter" sinnvoll ist
und keine Redundanz erzeugt.

---

## 15.3 Tool-System

| System | Tool-Modell | MCP | Erweiterbarkeit |
|---|---|---|---|
| **OpenWorker** | Flache Registry, alle Schemas immer, 4 Ebenen (lokal/Connector/MCP/Browser) — belegt: `engine.py:393` | ✅ Client (stdio+http, nur Tools) | nach außen offen, nach innen geschlossen |
| OpenHands | Aktions-/Beobachtungs-Modell über Events; Runtime kapselt Ausführung | ✅ | Plugins/Microagents |
| OpenInterpreter | Im Wesentlichen ein Tool: Code ausführen | teilweise | über Python |
| Goose | **Extensions = MCP-Server**, MCP ist der Hauptkanal | ✅ **zentral** | sehr offen |
| Continue | Kontext-Provider + Slash-Commands + Tools | ✅ | Config-getrieben, offen |
| Cline | Fest definiertes Toolset + MCP-Marktplatz | ✅ | über MCP |
| Codex | Shell + Datei-Tools in der Sandbox | teilweise | begrenzt |
| AutoGen | Funktions-Registrierung pro Agent | ✅ | offen (Python) |
| LangGraph | LangChain-Tools als Knoten | ✅ | offen |
| CrewAI | Tool-Klassen, LangChain-kompatibel | ✅ | offen |

**Erkenntnis:** **Alle** modernen Systeme setzen auf MCP als Erweiterungsvertrag.
Für VibeMind bestätigt das die vorhandene Richtung (`mcp/docker/`, `tools/mcp_sync/`).

**Goose ist hier das interessanteste Gegenmodell zu OpenWorker:** Es hat *keinen*
eingebauten Connector-Katalog, sondern behandelt **alles** als MCP-Extension. Das ist
die Architektur, die VibeMind anstreben sollte — nur mit der Governance-Schicht,
die Goose (wie alle anderen) so nicht hat.

**Was OpenWorker hier einzigartig macht:** Die **Risiko-Deklaration pro Tool** mit
`target_arg` für Standing Rules. Kein anderes System der Liste hat ein vergleichbar
differenziertes Modell dafür, *welches Tool welche Art von Aufsicht braucht*.

---

## 15.4 Sicherheit

| System | Isolation | Genehmigung | Secrets | Prompt Injection |
|---|---|---|---|---|
| **OpenWorker** | ❌ **keine** (nur leere `Executor`-ABC — belegt) | ✅ **sehr differenziert** (4 Prompt-Typen, 5 Modi, Standing Rules, Inbox, durable) | ⚠️ Klartext-JSON 0600 (belegt: `secrets.py:184-193`) | ⚠️ nur Prompt-Instruktion |
| OpenHands | ✅ **Docker-Runtime standardmäßig** | ⚠️ konfigurierbar | ⚠️ env/config | ⚠️ |
| OpenInterpreter | ❌ standardmäßig keine | ⚠️ y/n pro Codeblock | ⚠️ | ❌ |
| Goose | ⚠️ optional (Container-Rezepte) | ⚠️ Modi (smart/approve/chat) | ⚠️ Keyring | ⚠️ |
| Continue | ✅ läuft im Editor-Kontext | ✅ Diff-Bestätigung | ✅ IDE-Secrets | ⚠️ |
| Cline | ⚠️ | ✅ pro Aktion + Auto-Approve-Listen | ⚠️ | ⚠️ |
| Codex | ✅ **Sandbox by design** | ✅ Modi | ✅ | ⚠️ |
| AutoGen | ⚠️ optional Docker für Code-Executor | ⚠️ Human-in-the-loop-Modi | — | ❌ |
| LangGraph | ❌ Bibliothek | ✅ **Interrupts + Checkpointer** | — | ❌ |
| CrewAI | ❌ Bibliothek | ⚠️ `human_input` | — | ❌ |

**Zwei zentrale Erkenntnisse:**

1. **OpenWorker hat die beste Genehmigungsschicht und die schlechteste Isolation.**
   Genau umgekehrt zu OpenHands und Codex. Für VibeMind heißt das: **beides
   kombinieren** — OpenWorkers Approval-Modell auf einer Container-Isolation wie bei
   OpenHands.

2. **LangGraphs Checkpointer + Interrupts sind das direkte Gegenstück zu OpenWorkers
   Durable Resume** — aber als Bibliotheksprimitive statt als produkthafte Inbox.
   LangGraph kann an beliebiger Stelle unterbrechen und aus einem Checkpoint fortsetzen;
   OpenWorker nur an Prompt-Punkten, dafür mit vollständiger UX drumherum
   (Inbox, Slack-Buttons, Cross-Surface-Auflösung).

   **Für VibeMind ist die Kombination interessant:** LangGraph-artige Checkpoints
   (durable an *jeder* Stelle) + OpenWorker-artige Inbox (Auflösung von *jeder* Oberfläche).

**Prompt Injection ist bei allen ungelöst.** Kein System der Liste hat Taint-Tracking
oder strukturelle Kanaltrennung. Das ist eine echte Differenzierungschance für VibeMind
([ADR-0015](adr/ADR-0015-taint-tracking.md)).

---

## 15.5 Erweiterbarkeit

| System | Erweiterungsvertrag | Marktplatz |
|---|---|---|
| **OpenWorker** | MCP + Skills + Personas; Connectoren geschlossen (belegt: `catalog.py:11-13`) | Persona-Galerie (`/v1/cloud/gallery`) |
| OpenHands | Microagents, Runtime-Plugins, MCP | Community-Repos |
| OpenInterpreter | Python-Profile | ❌ |
| Goose | MCP-Extensions, Rezepte | Extension-Verzeichnis |
| Continue | Config-Blöcke, Kontext-Provider | Hub |
| Cline | MCP | MCP-Marktplatz |
| AutoGen | Python (offen) | ❌ |
| LangGraph | Python (offen) | LangGraph Platform |
| CrewAI | Python (offen) | Tool-Bibliothek |

**Für VibeMind:** Das Persona-Manifest-Format (Markdown + YAML, strikt validiert,
mit `recommends`) ist das ausgereifteste Erweiterungsformat der Liste — konkreter als
OpenHands' Microagents, strukturierter als Goose-Rezepte.

---

## 15.6 Entwicklererfahrung

| System | Setup | Debugbarkeit | Tests | Doku |
|---|---|---|---|---|
| **OpenWorker** | ⚠️ Bootstrap-Skript + 3 Terminals | ✅ **sehr gut** (kein Framework, lesbarer Loop) | ✅ **881 + 55 E2E** (belegt) | ❌ **Design-Docs fehlen** (belegt) |
| OpenHands | ✅ Docker-Compose | ⚠️ mehrere Schichten | ✅ | ✅ |
| OpenInterpreter | ✅ `pip install` | ✅ | ⚠️ | ⚠️ |
| Goose | ✅ ein Binary | ✅ | ✅ | ✅ |
| Continue | ✅ Extension | ⚠️ | ✅ | ✅ |
| Cline | ✅ Extension | ⚠️ | ⚠️ | ✅ |
| AutoGen | ✅ `pip install` | ⚠️ Konversationen schwer zu debuggen | ✅ | ✅ |
| LangGraph | ✅ | ✅ **LangSmith-Tracing** | ✅ | ✅ |
| CrewAI | ✅ | ⚠️ | ✅ | ✅ |

**OpenWorkers auffälligste Anomalie:** exzellente Testabdeckung bei fehlender
Architekturdokumentation. Für einen Fork bedeutet das: Man kann dem Code vertrauen
(Tests decken das Verhalten ab), aber man muss das *Warum* aus Kommentaren rekonstruieren.

**LangSmith-Tracing** ist der Punkt, an dem LangGraph allen anderen voraus ist.
OpenWorker hat nur `audit.py` (Tool-Entscheidungen), kein Tracing über Turns/Agenten.
**Für VibeMind mit Multi-Agent-Fan-out ist verteiltes Tracing (OpenTelemetry) nicht
optional** — ohne es ist ein Fehler in einem 12-Agenten-Lauf nicht diagnostizierbar.

---

## 15.7 Skalierbarkeit

| System | Ausführungsmodell | Horizontal | Zustand |
|---|---|---|---|
| **OpenWorker** | 1 Prozess, lokal (belegt) | ❌ | SQLite + JSONL, lokal (belegt) |
| OpenHands | Container pro Session | ✅ | Event-Store |
| OpenInterpreter | lokaler Prozess | ❌ | — |
| Goose | lokaler Prozess | ❌ | lokale Sessions |
| Codex | Cloud-Sandboxes | ✅ | verwaltet |
| AutoGen | in-Process (Bibliothek) | über eigene Infrastruktur | in-Memory |
| LangGraph | Bibliothek + Platform | ✅ (Platform) | **Checkpointer** (Postgres/Redis) |
| CrewAI | in-Process | über eigene Infrastruktur | in-Memory |

**Für VibeMind (Swarm, ~36 Services):** OpenWorkers Skalierungsmodell ist
**nicht übernehmbar**. Die richtige Referenz sind LangGraphs **Checkpointer**
(Zustand in Postgres/Redis statt im Prozess) und OpenHands' **Container pro Session**.

**Konkret heißt das für die Übernahme:** Die Governance-Schicht muss beim Portieren von
lokalen Dateien (JSON/SQLite) auf **Supabase + Redis** umgestellt werden — sonst wird
sie zum Skalierungsengpass. Der Aufwand ist überschaubar, weil die Stores hinter
schmalen Interfaces liegen.

---

## 15.8 Gesamteinordnung

**Wo OpenWorker führt:**

| # | Fähigkeit | Warum es führt |
|---|---|---|
| 1 | **Human-in-the-Loop-Genehmigung** | 4 differenzierte Prompt-Typen, 5 Modi, Standing Rules mit Zielbindung, Auflösung von jeder Oberfläche, überlebt Neustart |
| 2 | **Durable Resume ohne Workflow-Engine** | ~40 Zeilen, keine Zusatzinfrastruktur |
| 3 | **Risiko-Deklaration pro Tool** | `target_arg` macht Auto-Genehmigung sicher bindbar |
| 4 | **Unattended-Modus als eigenes Konzept** | Trennt „wo wird der Mensch erreicht" von „wie autonom ist der Agent" |
| 5 | **Cancellation-Vollständigkeit** | Aus jedem Zustand, mit Historien-Invariante |

**Wo OpenWorker zurückliegt:**

| # | Fähigkeit | Wer es besser macht |
|---|---|---|
| 1 | **Isolation/Sandbox** | OpenHands, Codex |
| 2 | **Multi-Agent** | AutoGen, LangGraph, CrewAI |
| 3 | **Zustandspersistenz für Skalierung** | LangGraph (Checkpointer) |
| 4 | **Observability/Tracing** | LangGraph/LangSmith |
| 5 | **Interne Erweiterbarkeit** | Goose (alles ist MCP) |
| 6 | **Dokumentation** | praktisch alle |

**Die Synthese für VibeMind:**

```
AutoGen           → Agentenkoordination (Gattung 3)
LangGraph-Muster  → Checkpointing, Zustand außerhalb des Prozesses, Tracing
OpenHands-Muster  → Container-Isolation pro Session/Agent
Goose-Muster      → MCP als einziger Erweiterungsvertrag
OpenWorker        → Governance: Inbox, Risk, Permission, Durable Approval, Audit
VibeMind eigen    → Voice, Intent-Routing, Planner, Memory Graph, Desktop, n8n
```

Kein einzelnes System deckt VibeMinds Bedarf. OpenWorker liefert **einen** Baustein —
aber den, der am schwersten selbst richtig zu bauen ist, weil er aus echten
Produktionsfehlern gewachsen ist.

---

**Weiter:** [16 — OpenWorker V2](16-openworker-v2.md)
