# ADR-Sammlung — VibeMind × OpenWorker

Architecture Decision Records zu jeder Entscheidung, die aus der OpenWorker-Analyse
folgt. Jede ADR enthält: **Goal · Kontext · Entscheidung · Begründung · Konsequenzen ·
Alternativen · Status**.

**Status-Legende:** `Vorgeschlagen` = zur Freigabe · `Angenommen` = beschlossen ·
`Abgelehnt` = geprüft und verworfen.

---

## Übersicht

| ADR | Titel | Kategorie | Phase | Status |
|---|---|---|---|---|
| [0001](ADR-0001-inbox-governance.md) | Inbox als kanonische Human-in-the-Loop-Schicht | A — Direkt übernehmen | 2 | Vorgeschlagen |
| [0002](ADR-0002-risk-klassifikation.md) | Risikoklassifikation als deklarative Tool-Eigenschaft | A | 1 | Vorgeschlagen |
| [0003](ADR-0003-cancellation-invarianten.md) | Cancellation-Invarianten als Barge-in-Fundament | A | 2 | Vorgeschlagen |
| [0004](ADR-0004-event-taxonomie.md) | Event-Taxonomie übernehmen, Event-Bus neu bauen | B — Erweitern | 2 | Vorgeschlagen |
| [0005](ADR-0005-standing-rules.md) | Standing Grants mit Zielbindung, TTL und Rate-Limit | B | 2 | Vorgeschlagen |
| [0006](ADR-0006-shell-executor.md) | ContainerExecutor als Default-Ausführungsumgebung | C — Neu | 3 | Vorgeschlagen |
| [0007](ADR-0007-tool-registry-namespaces.md) | Tool-Registry mit Namespaces und Retrieval | C | 3 | Vorgeschlagen |
| [0008](ADR-0008-memory-architektur.md) | Fünfschichtiger Memory Graph statt Notizliste | C | 4 | Vorgeschlagen |
| [0009](ADR-0009-skill-persona-format.md) | Markdown+YAML-Manifest als Agenten-Erweiterungsformat | B | 3 | Vorgeschlagen |
| [0010](ADR-0010-voice-pipeline-neuentwicklung.md) | Voice-Pipeline vollständig neu entwickeln | C | 4 | Vorgeschlagen |
| [0011](ADR-0011-planner-neuentwicklung.md) | Planner als eigene Komponente mit Plan-Artefakt | C | 4 | Vorgeschlagen |
| [0012](ADR-0012-multi-agent-runtime.md) | Multi-Agent auf AutoGen mit Governance-Gate | C | 4 | Vorgeschlagen |
| [0013](ADR-0013-mcp-federation.md) | MCP als einziger externer Erweiterungsvertrag | B | 3 | Vorgeschlagen |
| [0014](ADR-0014-worker-pool.md) | Worker Pool mit Priorität und Backpressure | C | 4 | Vorgeschlagen |
| [0015](ADR-0015-taint-tracking.md) | Taint-Tracking gegen Prompt Injection | C | 5 | Vorgeschlagen |
| [0016](ADR-0016-kommentarkultur.md) | Kommentarkultur: Warum + Incident-Bezug | A | 1 | Vorgeschlagen |
| [0017](ADR-0017-kontext-management.md) | Kontext als verwaltete Ressource | C | 3 | Vorgeschlagen |
| [0018](ADR-0018-nicht-uebernahmen.md) | Sammel-ADR: bewusste Nicht-Übernahmen | D — Verwerfen | — | Vorgeschlagen |

---

## Leitentscheidung

> **Aus OpenWorker wird die Governance-Schicht übernommen, nicht die Agenten-Intelligenz.**
>
> Von ~25.000 LOC Backend sind ~4.500 LOC (18 %) übernehmenswert — und diese 18 %
> sind fast vollständig Genehmigung, Risiko, Audit und Wiederaufnahme.
> Planner, Multi-Agent, Voice, Memory und Isolation entstehen neu.

Belege: [14 — Integrationsempfehlungen](../14-integrationsempfehlungen.md) ·
Umsetzung: [17 — Migrationsplan](../17-migrationsplan-vibemind.md)

---

## Lizenzhinweis

OpenWorker steht unter **MIT** (`LICENSE`, Commit `3766805`). Portierung von Code ist
zulässig; der Copyright-Hinweis muss erhalten bleiben. Jede portierte Datei erhält im
Kopf einen Hinweis der Form:

```
# Portiert aus openworker (MIT), Commit 3766805 — <Pfad in openworker>
# Copyright (c) OpenWorker contributors
```
