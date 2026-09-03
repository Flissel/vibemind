# TODO: Dynamischer LLM-Router (inspiriert von ruvnet/agentic-flow)

> Status: **Idee / Recherche** — noch nicht implementiert.
> Quelle: ruvnet/agentic-flow LLM-Router + ruflo `ruflo-ruvllm` Plugin (Multi-Provider-Failover).
> Datum aufgenommen: 2026-06-09

## Problem (warum überhaupt)

Aktuell ist die Provider-/Modell-Kette **hardgecodet** in `PLANNER_MODEL`
(siehe Memory `project_openclaw_brain_dispatcher`): die Kette
Groq-429 → OpenRouter-402 → `gpt-4o-mini` wurde manuell erarbeitet und
festgenagelt. Kein dynamisches Failover, keine complexity-basierte Modellwahl,
Kostenoptimierung nur statisch.

## Was agentic-flow konzeptionell macht

- **Complexity-based routing**: simple Tasks → günstiges/kleines Modell (Haiku),
  harte Tasks → starkes Modell (Sonnet/Opus). Quality-aware mit Confidence-Score.
- **Provider-Failover**: "5 providers with failover" — bei 429/402/timeout
  automatisch zum nächsten Provider.
- Anbindung über Hooks: `hooks route "<task>"` → empfohlener Agent + Confidence.

## Ziel für Vibemind

Ein **dünner Python-Router-Layer** VOR `multihop_execute` (Brain), der:
1. Task-Complexity grob klassifiziert (heuristik oder Brain-classify nutzen).
2. Provider-Kette dynamisch fährt: Groq → OpenRouter → OpenAI, mit echtem
   Failover auf 429/402/5xx statt hardcoded Reihenfolge.
3. Kosten/Confidence pro Routing-Entscheidung loggt (füttert evtl. die
   Routing-Matrix-Autotrain, siehe `project_routing_matrix_autotrain`).

## Offene Punkte / TODO

- [ ] agentic-flow Router-Modul im **echten Code** lesen (nicht README) —
      welche Signale fließen in die Modellwahl ein?
- [ ] Prüfen ob `vibemind_shared.get_client(role)` (siehe llm-config-migration
      Skill) schon der richtige Einhängepunkt ist — Router könnte dort sitzen.
- [ ] Failover-Logik gegen bestehende `vibemind-shared`-Clientfabrik mappen.
- [ ] Entscheiden: eigener Router vs. agentic-flow als Dependency
      (Achtung Fragmentierung — `project_automation_ui_fragmentation`).
- [ ] KEINE Adoption des ganzen TS-Frameworks — nur Routing-Logik portieren.

## Bewusst NICHT übernehmen

- AgentDB/HNSW Vector-DB → wir haben Qdrant.
- Swarm/Hive-Mind (queen+Raft) → wir haben Brain→OpenFang als Orchestrator.
- Attention/GNN → Marketing-Glanz, kein konkreter Nutzen.
