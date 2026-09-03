# ADR-0018 — Sammel-ADR: bewusste Nicht-Übernahmen

**Status:** Vorgeschlagen · **Kategorie:** D (nicht übernehmen) · **Phase:** —
**Betrifft:** Scope-Kontrolle des Migrationsplans

---

## Goal

> Festhalten, **was aus OpenWorker bewusst nicht übernommen wird** — damit die
> Entscheidung dokumentiert ist und nicht in jedem künftigen Review neu diskutiert
> werden muss.

Eine Nicht-Entscheidung ist die teuerste Entscheidung: Sie wird immer wieder
aufgeworfen und blockiert jedes Mal aufs Neue.

---

## Kontext

Von ~25.000 LOC Backend sind ~4.500 LOC (18 %) übernehmenswert
([14](../14-integrationsempfehlungen.md)). Die übrigen 82 % werden **nicht** übernommen —
teils, weil VibeMind Besseres hat, teils, weil die Komponente für VibeMinds Topologie
falsch ist, teils, weil der Wartungsaufwand den Nutzen übersteigt.

---

## Entscheidungen

### 1. `SessionManager` (3.766 LOC)

**Nicht übernehmen.** Ein God-Object mit ~150 Methoden, das Engines, Provider, Secrets,
Konversationen, Memory, Inbox, Routing, Audit, Automations, Gateway, MCP, Personas,
Skills, Workspace-Trust, Subscriptions, Mentions, Wakes und Verbindungen besitzt.

**Warum es so gekommen ist:** Ohne Event-Bus muss Querschnittskoordination irgendwo
zusammenlaufen. **Die Lehre:** VibeMind bekommt einen Event-Bus
([ADR-0004](ADR-0004-event-taxonomie.md)) und schneidet Services entlang von Domänen.

### 2. Connector-Monolith (33 Connectoren, 159 Tools, 4.892 LOC in einer Datei)

**Nicht übernehmen.** Der Katalog ist explizit geschlossen (`catalog.py:11-13`) und nur
upstream erweiterbar. Der Wartungsaufwand für 33 SaaS-APIs ist für VibeMind nicht
rechtfertigbar, wenn n8n und MCP dieselbe Funktion offen abdecken
([ADR-0013](ADR-0013-mcp-federation.md)).

**Was doch mitgenommen wird:** das *Datenmodell* — `ConnectorDescriptor` (Setup als
Daten statt UI-Code) und `ConnectorToolDef.target_arg` (macht Standing Grants sicher
bindbar, [ADR-0005](ADR-0005-standing-rules.md)).

### 3. `SecretStore` (Klartext-JSON)

**Implementierung nicht übernehmen.** `secrets.json`, `json.dumps(indent=2)`, geschützt
nur durch Dateirechte (`secrets.py:184-193`). Darin: alle Modell-Keys, alle
Connector-Tokens für 33 Dienste, Cloud- und MCP-OAuth-Tokens. Jeder Prozess unter
demselben Benutzerkonto liest sie ([08 R-04](../08-security-risikoanalyse.md#r-04)).

**Was mitgenommen wird:** das *Interface* (Profile, `${ENV_VAR}`-Referenzen,
`status()` gibt nie Werte zurück) und der Windows-ACL-Code samt Begründung — beides
korrekt gelöst. Die Speicherung wandert auf OS-Keystore bzw. Vault.

### 4. `SQLiteMemoryStore`

**Nicht übernehmen.** Tabelle ohne Index, ohne Suche, ohne Verfall
([ADR-0008](ADR-0008-memory-architektur.md)). Nachbau ist günstiger als Portierung.
Das *Regelwerk* (`_MEMORY_GUIDANCE`) wird übernommen.

### 5. React/Tauri-GUI (~12.000 LOC)

**Nicht übernehmen.** VibeMind hat Electron + Next.js. Übernommen werden *Muster*:
Stream-Gating-Regel, Prompt-Karten-Taxonomie, strikte Trennung Fach-API (HTTP) /
OS-API (IPC), hermetische E2E-Strategie mit gemocktem Backend.

### 6. `ocw-stt`

**Nicht übernehmen.** Batch-Transkription, `base.en` (Englisch only), Push-to-Talk,
Tauri-gebunden ([ADR-0010](ADR-0010-voice-pipeline-neuentwicklung.md)). Übernommen wird
das *Modell-Provisioning-Muster* (Download → SHA-256 → `.verified` → Test → `.ready`).

### 7. Browser-Singleton

**Nicht übernehmen.** `_BROWSER = _BrowserController()` auf Modulebene
(`browser_automation.py:223`) — **eine** Instanz für alle Sessions, geteilte Cookies,
serialisiert über einen einzigen Worker. Architekturfehler. VibeMind hat OpenClaw mit
Docker-/Native-Varianten. Übernommen wird `_SNAPSHOT_JS` (die Seitenrepräsentation).

### 8. `aisuite` als Abhängigkeit

**Nicht übernehmen.** `pyproject.toml:20` pinnt einen **Git-Commit**, kein PyPI-Release.
Kein signiertes Artefakt, keine Hash-Verifikation. Genutzt wird davon im Wesentlichen die
Schema-Ableitung aus Docstring + Type-Hints — ~50 Zeilen, die man selbst schreibt.
Eine Abhängigkeit auf ein unveröffentlichtes Paket ist für ein Produkt mit Auto-Update
und Shell-Zugriff nicht vertretbar.

### 9. `/v1/chat/completions`-Proxy

**Nicht übernehmen.** Nette Idee (jeder OpenAI-Client kann die Runtime als Backend
nutzen), aber für VibeMind irrelevant — **und** sie umgeht die eigene
Genehmigungsschicht, weil sie einen Ein-Schuss-Completion-Pfad neben dem Agent-Loop
öffnet. Genau das darf VibeMind nicht haben.

### 10. Flache Tool-Registry

**Nicht übernehmen** ([ADR-0007](ADR-0007-tool-registry-namespaces.md)). Stilles
Überschreiben bei Namenskollision, alle Schemas in jedem Request.

### 11. Cron-only-Scheduler

**Nicht übernehmen** als Ganzes. n8n und der bestehende VibeMind-Scheduler decken das ab.
Übernommen wird das *Datenmodell* `ScheduledTask` (eigener Thread, eigener
Arbeitsordner, Run-Historie, „run-once-catch-up", „skip-on-overlap") — die Semantik ist
gut und in n8n so nicht vorhanden.

### 12. Textual-TUI und CLI

**Nicht übernehmen.** Kein Bedarf; VibeMind hat andere Oberflächen.

### 13. Fest verdrahtete Store-Auswahl

**Nicht übernehmen.** OpenWorker instanziiert `SQLiteMemoryStore` direkt im Manager,
obwohl ein ABC existiert. VibeMind nutzt Qdrant, Supabase und Redis parallel — die
Auswahl gehört in die Konfiguration.

---

## Begründung des Gesamtschnitts

**Das Muster hinter allen dreizehn Punkten:** OpenWorker ist für **einen lokalen Prozess
mit einem Nutzer** optimiert. Alles, was aus dieser Annahme folgt — SQLite, lokale
JSON-Dateien, Modul-Singletons, God-Object-Koordination, geschlossener Katalog — ist für
VibeMinds verteilte Multi-Agenten-Topologie strukturell falsch.

Alles, was **unabhängig** von dieser Annahme ist — Risikoklassifikation, Inbox-Semantik,
Cancellation-Invarianten, Approval-UX, Executor-Muster, Persona-Format — ist übernehmbar.

**Der Schnitt verläuft nicht entlang der Qualität, sondern entlang der Topologie-Annahme.**

---

## Konsequenzen

**Positiv**
- Der Migrationsplan bleibt auf ~108 PW begrenzt.
- Kein Wartungsaufwand für 33 SaaS-Integrationen.
- Keine Abhängigkeit auf ein unveröffentlichtes Paket.
- Keine Architektur-Altlasten (God-Object, Singletons) importiert.

**Negativ / Kosten**
- **Kein Connector-Bestand ab Tag 1.** VibeMind muss Integrationen über MCP und n8n
  aufbauen. Das kostet anfangs Breite.
- **Kein fertiges Frontend.** Die UX-Muster müssen neu implementiert werden.
- **Kein fertiger Voice-Einstieg.** Auch nicht die Push-to-Talk-Variante.

**Risiko**
- **Diese Entscheidungen werden in künftigen Reviews erneut aufgeworfen** („warum bauen
  wir den Slack-Connector selbst, OpenWorker hat einen?"). Genau dafür existiert diese
  ADR — sie ist die Antwort, nicht der Gesprächsanfang.

---

## Alternativen

| Alternative | Bewertung |
|---|---|
| **OpenWorker als Ganzes forken und anpassen** | Verworfen: 82 % des Codes trägt Annahmen, die für VibeMind falsch sind. Ein Fork erbt sie alle — inklusive `SessionManager` und Connector-Monolith |
| **OpenWorker als Sidecar neben VibeMind betreiben** | Verworfen: zwei Genehmigungsschichten, zwei Memory-Systeme, zwei Tool-Registries. Die Integrationskosten übersteigen den Nutzen |
| **Nur die Connectoren übernehmen** | Verworfen: sie sind nicht aus dem Monolithen herauslösbar, ohne `SessionManager`, `SecretStore` und Descriptor-Kette mitzunehmen |
| **Nichts übernehmen, alles selbst bauen** | Verworfen: die Governance-Schicht ist aus echten Produktionsfehlern gewachsen. Diese Erfahrung ist nicht selbst herstellbar — sie ist der eigentliche Wert der Übernahme |
