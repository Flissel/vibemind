# ADR-0008 — Fünfschichtiger Memory Graph statt Notizliste

**Status:** Vorgeschlagen · **Kategorie:** C (neu) + B (Governance übernehmen) · **Phase:** 4
**Betrifft:** Memory, Kontext, Kosten, Personalisierung

---

## Goal

> VibeMind ruft bei > 1.000 gespeicherten Erinnerungen die **relevanten** ab —
> nicht alle — und weiß bei jeder, **woher sie stammt** und **ob sie noch gilt**.

**Messbar erreicht, wenn:** Recall liefert bei > 1.000 Einträgen die relevanten Treffer
in < 200 ms; der Systemprompt wächst nicht mit der Anzahl der Erinnerungen; jede
Erinnerung trägt Herkunft und Verfallsdatum.

---

## Kontext

OpenWorkers Memory ist eine SQLite-Tabelle **ohne jeden Index**
(`memory/sqlite_store.py:23-33`) und der Abruf ist kein Abruf: **alle** globalen plus
**alle** Workspace-Erinnerungen wandern ungefiltert in den Systemprompt
(`agent.py:255-260`).

| Anzahl | Prompt-Overhead |
|---|---|
| 20 | ~600 Token |
| 100 | ~3.000 Token |
| 500 | ~15.000 Token |
| 2.000 | **unbenutzbar** |

Kein Index, keine Volltextsuche, keine Embeddings, kein Verfall, keine Relationen,
keine Provenienz.

**Was dagegen sehr gut ist: das Regelwerk.** `_MEMORY_GUIDANCE` (`agent.py:62-73`)
enthält fünf echte Erkenntnisse:
1. Präferenzen **mit Begründung** speichern,
2. **nicht** speichern, was aus dem Code/Repo ableitbar ist,
3. absolute Daten statt „gestern",
4. **revidieren statt duplizieren** (`memory_update` vor `remember`),
5. **Erinnerungen sind Momentaufnahmen** — vor Verwendung prüfen, ob Datei/Flag/URL
   noch existiert.

Dazu das ID-sichtbare Format `- [#7] …`, das gezielte Revision überhaupt erst möglich macht.

VibeMind hat bereits: Qdrant und Supabase geplant, Neo4j live (MiroFish),
La-Fungus als Such-Layer, Redis im Stack.

---

## Entscheidung

**Regelwerk übernehmen, Speicher neu bauen — als fünf Schichten mit klaren Rollen.**

| Schicht | Technologie | Inhalt | Abruf |
|---|---|---|---|
| **Episodisch** | Supabase/Postgres | Was ist passiert: Turns, Tool-Calls, Ergebnisse | zeitlich, gefiltert |
| **Semantisch** | **Qdrant** | Was bedeutet es: Erinnerungen, Dokumente, Code | Hybrid (dense + BM25) + Re-Ranking + MMR |
| **Relational** | Neo4j (vorhanden) | Wie hängt es zusammen: Entitäten, Projekte, Personen, Artefakte | Graph-Traversal |
| **Prozedural** | Dateisystem (Skills) | Wie macht man etwas | Progressive Disclosure (aus OpenWorker) |
| **Arbeitsspeicher** | Redis | Was gerade zählt: Session-State, Worker-Koordination | Key/TTL |

### Abrufmodell — die entscheidende Änderung

| Heute (OpenWorker) | VibeMind |
|---|---|
| Alle Erinnerungen → Systemprompt, statisch beim Build | **Keine** Erinnerung im Systemprompt |
| — | `recall(query, top_k)` als **Tool** — das Modell ruft ab, wenn es etwas braucht |
| — | **plus** automatischer Pre-Turn-Recall: Top-k zur aktuellen Nachricht, injiziert über den **ephemeren Kontextblock** |

Der Injektionspunkt existiert bereits konzeptionell: OpenWorkers `context_provider()`
hängt ephemeren Kontext an die letzte Nutzernachricht und persistiert ihn **nie**
(`engine.py:963-981`). Das ist genau richtig für RAG-Recall — pro Turn neu, ohne die
Historie zu verschmutzen, **und ohne den cachebaren Prompt-Prefix zu zerstören**
([ADR-0017](ADR-0017-kontext-management.md)).

### Payload-Pflichtfelder

| Feld | Zweck |
|---|---|
| `scope`, `space`, `agent_id`, `workspace` | Mandantentrennung entlang der VibeMind-Spaces |
| `created_at`, `updated_at`, `last_accessed`, `access_count` | Verfall und Nutzungsgewichtung |
| **`source`** ∈ {`user_stated`, `agent_inferred`, `tool_derived`, `external_content`} | **Sicherheitskritisch:** eine aus einem fremden Ticket abgeleitete „Erinnerung" darf nie dasselbe Vertrauen haben wie eine Nutzeraussage |
| `confidence`, `supersedes` | Revision statt Duplikat — maschinell prüfbar, nicht nur als Prompt-Bitte |
| `ttl` / `expires_at` | Zeitgebundene Fakten laufen ab, statt zu vergiften |

Das Feld `source` ist die Verbindung zu [ADR-0015](ADR-0015-taint-tracking.md):
**Prompt Injection über Memory ist ein persistenter Angriff** — eine einmal
eingeschleuste „Erinnerung" wirkt in jeder künftigen Session.

---

## Begründung

- **Der Prompt-Ansatz skaliert nachweislich nicht.** Ab ~100 Einträgen dominiert Memory
  den Prompt; ab ~500 ist das System unbrauchbar.
- **Die fünf Schichten haben unterschiedliche Zugriffsmuster.** Sie in einen Speicher
  zu zwingen, macht jeden davon schlecht. VibeMind hat für vier davon bereits die
  richtige Technologie im Stack.
- **Das Regelwerk ist unabhängig vom Speicher wertvoll** und sofort einsetzbar
  (Phase 1, Maßnahme 1.4).
- **Provenienz ist keine Zusatzfunktion.** Ohne sie ist Memory ein persistenter
  Injection-Vektor.

---

## Konsequenzen

**Positiv**
- Systemprompt wächst nicht mehr mit dem Wissensbestand.
- Prompt-Caching wird nutzbar (statischer Prefix).
- Relevanz statt Vollständigkeit.
- Memory Graph der Zielarchitektur wird real.
- Verfall verhindert Vergiftung durch veraltete Fakten.

**Negativ / Kosten**
- **Fünf Speicher = fünf Betriebsaufgaben** (Backup, Migration, Konsistenz).
  Gegenmaßnahme: Supabase ist Source of Truth, Qdrant und Neo4j sind **ableitbare
  Indizes** — bei Verlust neu aufbaubar. Das begrenzt den Konsistenzaufwand erheblich.
- **Embedding-Kosten und -Latenz** bei jedem Schreib- und Lesevorgang. Lokales Modell
  (mehrsprachig, DE/EN) statt API — auch aus Datenschutzgründen.
- **Recall kann danebengreifen.** Das Modell „vergisst" scheinbar, weil der Treffer
  nicht in den Top-k war. Gegenmaßnahme: `recall()` als explizites Tool, damit das
  Modell gezielt nachfragen kann.
- Migration bestehender Erinnerungen inklusive Nachtragen von Provenienz (für Altdaten
  konservativ: `source = agent_inferred`).

**Risiko**
- **Qualität der Einbettung entscheidet über die Qualität des Systems.** Ein schlechtes
  mehrsprachiges Embedding macht Recall wertlos. Gegenmaßnahme: Evaluation auf echten
  VibeMind-Anfragen vor der Festlegung.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **Status quo (alles in den Prompt)** | Verworfen: skaliert nicht |
| **Nur Qdrant, kein Graph** | Guter erster Schritt und **empfohlene Reihenfolge** (4C.2 vor 4C.6). Aber: Beziehungsfragen („welche Tickets hängen an diesem Projekt") beantwortet Vektorsuche schlecht |
| **Nur Graph, keine Vektoren** | Verworfen: unstrukturierte Ähnlichkeitssuche fehlt |
| **Supermemory / gehostete Memory-API** | Ein Key ist bereits konfiguriert. Verworfen als Primärspeicher: Datenhoheit, Latenz, Kopplung an einen Anbieter. Als Vergleichs-Baseline nutzbar |
| **Volltextsuche (FTS5/Postgres FTS) statt Embeddings** | Deutlich billiger, deckt exakte Begriffe gut ab. **Empfehlung: als Sparse-Teil der Hybrid-Suche behalten**, nicht als Ersatz |
| **Kein Auto-Recall, nur `recall()`-Tool** | Einfacher und deterministisch, aber das Modell ruft erfahrungsgemäß zu selten ab. **Empfehlung: beides** |
