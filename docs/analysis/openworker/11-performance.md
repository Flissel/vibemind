# 11 — Performance

Bewertet werden zwei Dimensionen: **Latenz/Durchsatz** (wie schnell reagiert das
System) und **Token-Ökonomie** (was kostet eine Aufgabe) — letztere dominiert bei
Agenten-Systemen die realen Kosten.

---

## Bottleneck-Register

### B-01 — Unbegrenzt wachsender Kontext · **Kritisch**

**Befund:** Es gibt **keine** Kontext-Kompaktierung. `_outbound_messages()`
(`engine.py:878-982`) strippt Anzeige-Sidecars und passt PDFs/Bilder an die
Modellfähigkeiten an — aber es **kürzt nie**. Volltextsuche über `coworker/` nach
`compact`, `summariz`, `token_budget`, `context_window`, `truncate_history`:
keine Treffer im Engine-Pfad (nur Autotitle-Generierung im Manager).

**Wirkung:**

| Turn | Historie (grob) | Verhalten |
|---|---|---|
| 1–10 | < 20 k Token | normal |
| 30–50 | 60–120 k Token | Kosten pro Turn steigen linear, Latenz spürbar |
| 80+ | > 200 k Token | Provider-Fehler (Kontextlimit) → `ERROR`-Notice → Session ist **tot** |

Ein Tool-Result kann allein 20.000 Zeichen sein (`shell.py:145` — `max_output_chars`).
Zehn Shell-Calls = 200.000 Zeichen ≈ 50 k Token, permanent in der Historie.

**Erschwerend:** Die Historie ist die *einzige* Zustandsquelle (das ist gleichzeitig
die Stärke des Durable-Resume-Designs). Kompaktierung ist deshalb nicht trivial
nachrüstbar — sie kollidiert mit `_unanswered_trailing_tool_calls()`.

**Für VibeMind:** Blockierend. Ein „digitale Entwicklungsabteilung"-Auftrag läuft über
Stunden und Hunderte Turns. Nötig: Sliding-Window + hierarchische Zusammenfassung +
Auslagerung großer Tool-Results in einen Artefaktspeicher, referenziert per Handle statt
inline.

### B-02 — Alle Tool-Schemas in jedem Request · **Kritisch (Kosten)**

**Befund:** `engine.py:393` — `tools = self.registry.schemas() or None`.

**Rechnung** (Cowork-Persona mit aktivierten Connectoren):

| Quelle | Tools | Token (à ~200) |
|---|---|---|
| Basis (files, search, shell, todo, git) | ~15 | 3.000 |
| Connectoren (bei allen aktiviert) | bis 159 | bis 31.800 |
| MCP-Server (3 Server à 15 Tools) | 45 | 9.000 |
| Memory + Skills + Scheduling + Web | ~10 | 2.000 |
| **Summe pro Request** | **~230** | **~46.000** |
| **Pro Turn** (`max_iterations=12`) | | **bis 550.000** |

Realistisch sind es weniger (User aktiviert selten alles), aber die
Größenordnung stimmt: **Tool-Schemas sind bei aktiven Connectoren der größte einzelne
Kostenblock** — größer als Systemprompt und oft größer als die Konversation.

**Verschärfend:** Es gibt keine sichtbare Nutzung von Prompt-Caching
(weder Anthropic-`cache_control` noch bewusste Prefix-Stabilität). Der Systemprompt
enthält *alle* Memories, die sich ändern können — was einen stabilen Cache-Prefix
ohnehin bricht.

**Und ein Qualitätsproblem:** Modelle wählen bei >50 Tools messbar schlechter.
Bei 230 ist Fehlrouting erwartbar. VibeMinds eigene Erfahrung bestätigt das:
`intent_validation/00_MASTER.md` dokumentiert Fehlwahl #7 („such die Idee X" →
`bubble_evaluate` statt `idea_find`) mit Root-Cause „`bubble_evaluate`-desc enthält
'idea' prominent → Planner greift falsch" — bei einer **weit kleineren** Toolmenge.

### B-03 — Ungebundene Nebenläufigkeit · **Hoch**

Drei Stellen ohne Obergrenze:

| Stelle | Code | Risiko |
|---|---|---|
| Paralleles Tool-Fan-out | `asyncio.gather(*[to_thread(...) for tc in concurrent])` (`engine.py:489-491`) | n parallele `explore`-Calls = n Threads **und** n LLM-Sessions |
| Automation-Läufe | `asyncio.create_task` pro fälligem Task, nicht awaited (`scheduler.py:76-79`) | 20 gleichzeitig fällige Cron-Tasks starten 20 Engines |
| Default-ThreadPool | `min(32, cpu+4)`, von allem geteilt | Sättigung blockiert auch Provider-Streams |

Es gibt **keine** Semaphore, **keine** Queue, **kein** Backpressure-Signal,
**keine** Priorisierung (interaktive Session vs. Hintergrund-Automation).

**Für VibeMind mit Worker Pool in der Zielarchitektur:** genau hier muss die eigene
Lösung ansetzen — begrenzter, priorisierter Pool mit Queue und Rückstau.

### B-04 — Kein Streaming von Tool-Output · **Mittel**

`TOOL_FINISHED` liefert `result_preview` — **300 Zeichen** (`engine.py:1030-1033`).
Bis dahin: nichts. Ein fünfminütiger Build zeigt fünf Minuten lang keinen Fortschritt.

Der Workaround existiert (`run_in_background` + `shell_task_output`-Polling), aber er
kostet Modell-Runden und verlangt, dass das Modell daran denkt.

**Für Voice-first besonders relevant:** Ein Sprachinterface ohne Zwischenfeedback über
Minuten ist unbenutzbar. VibeMind braucht Tool-Output-Streaming als Event-Typ.

### B-05 — Browser-Serialisierung · **Mittel**

`ThreadPoolExecutor(max_workers=1)` + Modul-Singleton
(`browser_automation.py:70-72, 223`). Alle Browser-Operationen **aller Sessions**
laufen durch einen Worker. Zwei parallel browsende Sessions blockieren sich, teilen
Cookies und Seite.

### B-06 — SQLite unter einem globalen Lock · **Niedrig-Mittel**

`memory/sqlite_store.py:20-21` — eine Verbindung mit `check_same_thread=False`,
serialisiert über `threading.RLock`. Für Memory-Volumina unkritisch; bei parallelen
Sessions mit häufigen Reads wird es zum Punkt-Engpass. WAL-Modus ist nicht aktiviert.

### B-07 — JSONL-Vollreload beim Session-Öffnen · **Niedrig**

`conversations/<id>.jsonl` wird beim Laden vollständig geparst. Schreiben ist
append-only (gut), Lesen ist O(n). Bei sehr langen Sessions merklich; das Limit ist
faktisch B-01, das früher greift.

### B-08 — Frontend-Rerender & Streaming-Puffer · **Niedrig-Mittel**

Zentraler State in `App.tsx` → breite Rerenders pro Delta; String-Konkatenation im
State → O(n²) bei langen Antworten; keine Virtualisierung im Transcript.
Details in [09](09-frontend.md#95-performance).

---

## 11.2 Was gut gelöst ist

| Mechanismus | Wirkung |
|---|---|
| **Blockierendes I/O in Threads** (`to_thread`, `run_in_executor`) | Der Loop bleibt responsiv; UI-Events fließen während Tool-Läufen |
| **Cancel-Race bei jedem `queue.get()`** (`engine.py:420-428`) | Ein hängender Stream kann den Turn nicht festhalten |
| **Tool-Output behält den Tail** (`shell.py:287-290`) | Build-/Test-Verdikte gehen nie verloren |
| **Paralleles Fan-out nur für risikoarme Reads** | Deterministisch für alles mit Seiteneffekt |
| **Append-only-Persistenz** | Kein Rewrite der Historie pro Turn |
| **Lazy Provider-Clients mit Cache + `invalidate()`** (`router.py:58-88`) | Kein Rebuild bei Konfigänderung |
| **Progressive Disclosure für Skills** | Nur Katalog im Kontext — das *richtige* Muster, nur nicht auf Tools angewandt |
| **PDF/Bild-Adaption pro Call, nicht persistiert** | Modellwechsel bleibt verlustfrei |
| **`explore`-Subagent mit eigenem Kontext** | Die einzige implementierte Kontext-Ökonomie-Maßnahme, und sie ist richtig |

**`explore` verdient eine Hervorhebung:** Es ist die einzige Stelle, an der OpenWorker
Token-Ökonomie ernst nimmt — dutzende Dateireads passieren im Kind-Kontext, nur der
Report kehrt zurück (`tools/subagent.py:1-11`). Genau dieses Muster muss VibeMind
verallgemeinern: **jede** breite Recherche gehört in einen Sub-Kontext.

---

## 11.3 Speicherverbrauch

| Quelle | Verhalten |
|---|---|
| `TurnEngine.messages` | Wächst unbegrenzt; Tool-Results bis 20 k Zeichen je Call |
| Engine-Cache im Manager | Engines pro Session gehalten, mit Eviction (Durable Resume ist der Hinweis darauf); Grenze nicht dokumentiert |
| Persistente Shell | Ein Prozess pro Session mit Workspace, plus **nicht getötete** Hintergrundtasks |
| Browser | Ein Chromium (sichtbar) prozessweit |
| MCP | Ein Kindprozess (stdio) pro Server, dauerhaft |
| Whisper-Modell | 142 MB, im Speicher während der Transkription |
| Audio-Puffer | Rohe f32-Samples der gesamten Äußerung im RAM |

**Realistische Baseline** mit 3 Sessions, 2 MCP-Servern, offenem Browser: Python-Server
+ Chromium + 2 MCP-Kindprozesse + 3 Shells. Auf einem 8-GB-Rechner nicht komfortabel.

---

## 11.4 Was VibeMind daraus baut

| Problem | VibeMind-Lösung |
|---|---|
| B-01 Kontext | Sliding Window + hierarchische Summaries + **Artefakt-Handles** statt inline (großes Tool-Result → Datei/Qdrant, Modell bekommt Referenz + Kurzfassung) |
| B-02 Tool-Schemas | Namespaces + **semantisches Tool-Retrieval** (Top-k pro Turn) + rollenbasiertes Scoping + Progressive Disclosure auf Kategorieebene |
| B-03 Nebenläufigkeit | **Redis-basierter Worker Pool** mit Queue, Priorität (interaktiv > Automation), Semaphore pro Ressource, Backpressure ans UI |
| B-04 Tool-Streaming | Neuer Event-Typ `TOOL_OUTPUT_DELTA`; für Voice zwingend |
| B-05 Browser | Session-scoped Contexts (OpenClaw hat das bereits) |
| B-06 SQLite | Postgres/Supabase (bereits im Stack) statt SQLite-Lock |
| B-08 Frontend | Store + Virtualisierung + Rope/Chunk-Puffer für Streams |
| — | **Prompt-Caching bewusst nutzen:** stabiler Prefix (Systemprompt ohne dynamische Memories), Memories erst im ephemeren `<system-context>`-Block |

**Der letzte Punkt ist die günstigste Einzelmaßnahme überhaupt.** OpenWorker packt
Memories in den *Systemprompt* (`agent.py:255-260`) und zerstört damit den stabilen
Cache-Prefix. Verschiebt man sie in den ephemeren Kontextblock, der bereits existiert
(`context_provider()`), wird der Prefix cachebar — bei Anthropic/OpenAI-Caching sind das
50–90 % Kostenersparnis auf den statischen Anteil, ohne Funktionsverlust.

---

## 11.5 Bewertung

| Aspekt | Note |
|---|---|
| Responsivität des Loops | **A** |
| Cancellation-Latenz (≤0,5 s bis Shell-Tod) | **A** |
| Kontext-Ökonomie | **E** — keine Kompaktierung, alle Schemas immer |
| Nebenläufigkeitssteuerung | **D** — ungebunden, keine Priorität |
| Streaming | B — Text ja, Tool-Output nein |
| Speicherdisziplin | C |
| Persistenz-I/O | B+ — append-only, aber O(n)-Reload |
| Caching (Prompt/Tool/HTTP) | **E** — existiert nicht |

---

**Weiter:** [12 — Erweiterbarkeit](12-erweiterbarkeit.md)
