# Intent-Test-Liste — Ausführung (Phase A Routing + Execution)

## ✅ ROUTING-EVAL ABGESCHLOSSEN (2026-06-09, live, alle Fixes drin)

**Trefferquote: 11/11 korrekt** über alle 5 Klassen (live, brain-core mit Iter-1-
Schwelle + Multi-Worker). Die Über-Routing-Fehler vom 2026-06-08 sind behoben:

| Intent | erwartet | bekam | cos |
|---|---|---|---|
| wie viele Ideen gibt es | medium | medium | 0.83 |
| scan for hardcoded api keys | medium | medium | 0.96 |
| is example.com up | medium | medium | 0.73 |
| verschiebe Idee A in Bubble B | medium | medium | 0.85 |
| lösche die Bubble Marketing | medium | medium | 0.81 |
| erstelle Excel mit Spalten | hard | hard | 0.87 |
| plane meine Bewerbung | hard | hard | 0.96 |
| entwirf Strategie Launch | insane | insane | 0.79 |
| Newsletter-Flow aufbauen | insane | insane | 0.91 |
| danke dir | easy | easy | 0.78 |
| Summarize…/[Previous context] | meta | meta-reject | — |

**Fazit Routing:** funktioniert. Iter-1-Fix (Konfidenz-Schwelle DIFFICULTY_MIN_COS=0.55
+ breitere medium-Anker) hat das Über-Routing nach insane vollständig behoben (frühere
Fehlfälle „wie viele Ideen" 0.36→insane, „scan" 0.39→insane sind jetzt medium 0.83/0.96).

**Execution-Halbteil:** medium→Capability-Shortcut baut korrekte Pläne (idea_count-Plan
gegen Supabase, HTTP 200 verifiziert). hard→SoM + insane→som-team dispatchen async (200).
OFFEN (separates Issue, NICHT Routing): heavy-Requests (easy-chat, med→plan) haben hohe
Downstream-Latenz (>120s/Hang im Planner-LLM/SoM-Pfad) — eigene Eval-Iteration.

**Contention:** GELÖST (Major Change). brain-core läuft mit 2 uvicorn-Workern
(BRAIN_HTTP_WORKERS=2), Loops im separaten brain-loops-Prozess. meta antwortet immer
in ~20ms, auch parallel/während heavy-Requests (Event-Loop frei). start_period 360s
für 2-Worker-Coldstart.

---

## ⚠️ EVAL-ERGEBNIS (2026-06-08, live nach Contention-Fix)

Routing live getestet (brain-core responsiv, kein Timeout/Contention mehr). Befund:
**Die Difficulty-Klassifikation über-routet nach `insane`.** Korrekte Fälle:
- easy: „hi, wer bist du?" → easy/chat ✅
- meta: „Summarize…" → reject in 3ms ✅
- hard: „erstelle Excel" → som (cos 0.90) ✅
- insane: „entwirf Strategie"/„Newsletter-Flow" → autogen (cos 0.78-0.88) ✅

**FEHLklassifikationen (alle mit niedrigem cos → schwacher Match, raten):**
| Intent | erwartet | bekam | cos |
|---|---|---|---|
| „wie viele Ideen gibt es?" | medium (idea_count) | insane | 0.36 |
| „scan for hardcoded api keys" | medium (security_scan) | insane | 0.39 |
| „verschiebe die Idee X in Bubble Y" | medium (idea_move) | insane | 0.54 |
| „expand this idea into sub-ideas" | medium (idea_expand) | insane | 0.58 |
| „was ist der Capability-Router?" | knowledge/architecture | easy | 0.43 |

**Root-Cause:** (1) Der insane-Anker „wie baue ich am besten einen kompletten…" ist
zu lang/generisch → viele Intents matchen ihn schwach-positiv. (2) **Keine Konfidenz-
Schwelle:** bei cos 0.36-0.58 „rät" der Router den nächsten Anker statt auf einen
sicheren Default zu fallen. (3) medium-Anker sind zu wenige/zu eng.

**Fix (Folge-Arbeit, NICHT die Routing-Mechanik — die funktioniert):**
1. **Konfidenz-Schwelle** in difficulty_router: cos < ~0.55 → NICHT insane/hard,
   sondern medium (Capability-Shortcut probieren) ODER Heuristik-Fallback. Verhindert
   das „raten ins insane".
2. **Anker kuratieren:** insane-Anker spezifischer (vage/explorativ-only), medium-Anker
   breiter (CRUD/1-Aktion: count/list/move/scan/expand). Die DEFAULT_ANCHORS in
   difficulty_router.py:DEFAULT_ANCHORS überarbeiten.
3. Optional: medium ist heute der **schwächste** Eimer (wenig Anker) — bekommt die
   meisten Capability-Intents, braucht also die meisten/besten Anker.

**Was FUNKTIONIERT:** Mechanik (Qwen-Cosine + Dispatch), HTTP-Responsiveness (Fix),
Meta-Filter, die klaren Fälle (easy-Smalltalk, Excel→hard, Strategie→insane), beide
async-Dispatches (SoM 200, som-team 200/4.6s). Es ist ein **Anker-/Schwellwert-
Tuning-Problem**, kein struktureller Defekt.

---


> Erstellt 2026-06-08 aus `brain/the_brain/data/capabilities.yaml` (65 Capabilities)
> + OpenFang-Agenten + Skill-Library. Zweck: systematisch durchtesten, welche
> Intents korrekt **klassifiziert** (Difficulty-Router) UND **ausgeführt** werden.
>
> **Routing-Schema (Phase A, live):** `easy→chat`, `medium→shortcut/Groq`,
> `hard→SoM`, `insane→AutoGen`. Test via `POST :5000/api/multihop/execute {"intent":"..."}`.
> Routing-Log: `docker logs vibemind_brain-core | grep "\[multihop\] difficulty"`.
>
> **Spalten:** Intent (Testtext) · erwartetes Level · erwartete Capability/Handler
> · execution_target · ✅/❌/⚠️ (beim Durchtesten ausfüllen).
>
> **Execution-Verteilung:** 46× `supabase:` · 9× `openfang:` · 1× `mcp:` · Rest broadcast/chat.

---

## 0. Routing-Sanity (die 4 Schwierigkeitsgrade) — zuerst testen

| # | Intent | erwartet Level | erwartet Handler | Status |
|---|--------|----------------|------------------|--------|
| 0.1 | „danke dir" / „wie geht's?" | easy | chat (brain_chat) | ✅ live cos=0.65 |
| 0.2 | „öffne example.com im browser" | medium | capability-shortcut | ✅ live (shortcut) |
| 0.3 | „erstelle mir eine Excel auf dem Desktop mit Spalten Name und Betrag" | hard | SoM | ✅ live cos=0.96 |
| 0.4 | „wie baue ich am besten einen kompletten Newsletter-Flow auf?" | insane | AutoGen | ✅ live cos=0.94 |
| 0.5 | „was ist die Hauptstadt von Frankreich?" | easy | chat (off-domain, kein Planer) | ☐ |
| 0.6 | „mach erst A, dann B und dann C" | hard | SoM (mehrstufig) | ☐ |

---

## 1. EASY — Chat / Wissen / Smalltalk (kein Planer)

| # | Intent | Capability | Handler / Ziel | Status |
|---|--------|-----------|----------------|--------|
| 1.1 | „hi" / „hallo" / „moin" | chitchat | chat | ☐ |
| 1.2 | „wer bist du?" / „what are you?" | chitchat | chat | ☐ |
| 1.3 | „good morning, how have you been?" | chitchat | chat | ☐ |
| 1.4 | „was ist der Brain-Router?" | knowledge_query | rowboat-knowledge/supermemory | ☐ |
| 1.5 | „wie funktioniert der Capability-Router?" | architecture_question | fungus-search + brain-coder | ☐ |
| 1.6 | „walk me through the routing pipeline" | architecture_question | fungus-search | ☐ |
| 1.7 | „erklär mir kurz was eine Bubble ist" | knowledge_query / chat | chat | ☐ |

---

## 2. MEDIUM — 1 klare Aktion (Capability-Shortcut, schnell)

### 2a. Lesen / Suchen / Prüfen (read-only)

| # | Intent | Capability | execution_target | Status |
|---|--------|-----------|------------------|--------|
| 2.1 | „wo ist die `multihop_execute` Funktion?" | code_search | fungus-search | ☐ |
| 2.2 | „find the auth code" | code_search | fungus-search | ☐ |
| 2.3 | „is example.com up?" | site_check | poc-site-verifier | ☐ |
| 2.4 | „check if the api endpoint is reachable" | site_check | poc-site-verifier | ☐ |
| 2.5 | „wie viele Agents sind registriert?" | knowledge_query | rowboat-knowledge | ☐ |
| 2.6 | „list all bubbles" / „zeig mir alle Bubbles" | bubble_list | supabase:bubble.list | ☐ |
| 2.7 | „find the bubble called X" | bubble_find | supabase:bubble.find | ☐ |
| 2.8 | „wie viele Ideen sind in der Bubble?" | bubble_stats | supabase:bubble.stats | ☐ |
| 2.9 | „list all ideas" / „zeig mir die Ideen" | idea_list | supabase:idea.list | ☐ |
| 2.10 | „wie viele Ideen?" / „count the ideas" | idea_count | supabase:idea.count | ☐ |
| 2.11 | „such die Idee X" | idea_find | supabase:idea.find | ☐ |
| 2.12 | „was braucht Auth_Identity?" (E-Ticketing) | component_requirements | supabase:component.requirements | ☐ |
| 2.13 | „welches Format hat die Idee?" | idea_format_get | supabase:idea.format | ☐ |
| 2.14 | „welche Formate gibt es?" | idea_format_list | supabase:idea.format | ☐ |

### 2b. Schreiben / Ändern (single mutation)

| # | Intent | Capability | execution_target | Status |
|---|--------|-----------|------------------|--------|
| 2.15 | „create a bubble called Marketing" | bubble_create | supabase:bubble.create | ☐ |
| 2.16 | „benenne die Bubble X um in Y" | bubble_update | supabase:bubble.update | ☐ |
| 2.17 | „lösche die Bubble X" | bubble_delete | supabase:bubble.delete | ☐ ⚠️ destruktiv |
| 2.18 | „notiere: Cache-Strategie überdenken" | idea_add | supabase:idea.create | ☐ |
| 2.19 | „ändere die Idee X" | idea_update | supabase:idea.update | ☐ |
| 2.20 | „lösche die Idee X" | idea_delete | supabase:idea.delete | ☐ ⚠️ destruktiv |
| 2.21 | „verbinde Idee A mit Idee B" | idea_connect | supabase:idea.connect | ☐ |
| 2.22 | „trenne Idee A von B" | idea_disconnect | supabase:idea.disconnect | ☐ |
| 2.23 | „verschiebe die Idee X in Bubble Y" | idea_move | supabase:idea.move | ☐ |
| 2.24 | „betrete die Bubble X" | bubble_enter | supabase:bubble.enter (noop) | ☐ |

### 2c. Idee transformieren / formatieren (LLM single-shot)

| # | Intent | Capability | execution_target | Status |
|---|--------|-----------|------------------|--------|
| 2.25 | „expand this idea into sub-ideas" | idea_expand | supabase:idea.llm | ☐ |
| 2.26 | „classify each idea" | idea_classify | supabase:idea.llm | ☐ |
| 2.27 | „explain this idea in detail" | idea_explain | supabase:idea.llm | ☐ |
| 2.28 | „format the idea as a table" | idea_format_table | supabase:idea.format | ☐ |
| 2.29 | „als SWOT-Analyse" | idea_format_swot | supabase:idea.format | ☐ |
| 2.30 | „als Mindmap" | idea_format_mindmap | supabase:idea.format | ☐ |
| 2.31 | „als Flowchart" | idea_format_flowchart | supabase:idea.format | ☐ |
| 2.32 | „pros and cons" | idea_format_pros_cons | supabase:idea.format | ☐ |
| 2.33 | „als Kanban-Board" | idea_format_kanban | supabase:idea.format | ☐ |
| 2.34 | „als technische Spezifikation" | idea_format_specs | supabase:idea.format | ☐ |
| 2.35 | „als User Stories" | idea_format_user_story | supabase:idea.format | ☐ |
| 2.36 | „als Gliederung/Outline" | idea_format_hierarchy | supabase:idea.format | ☐ |
| 2.37 | „als Aufgabenliste/Todos" | idea_format_action_list | supabase:idea.format | ☐ |
| 2.38 | „mach das Format rückgängig" | idea_format_revert | supabase:idea.format | ☐ |

---

## 3. HARD — mehrstufig / Artefakt (SoM-Planner)

| # | Intent | Capability/Pfad | execution_target | Status |
|---|--------|-----------------|------------------|--------|
| 3.1 | „erstelle eine Excel mit Spalten Name und Betrag auf dem Desktop" | desktop_skill / som_plan | openfang:desktop-skill | ☐ |
| 3.2 | „plane meine Bewerbung und bereite die Unterlagen vor" | som_plan | openfang:som-planner | ☐ |
| 3.3 | „erstelle einen Plan für X" / „orchestriere Y" | som_plan | openfang:som-planner | ☐ |
| 3.4 | „expandiere jede Idee in der Bubble + klassifiziere sie" | (multi-cap SoM) | SoM | ☐ |
| 3.5 | „schreibe die Spec für Auth in die E-Ticketing-Bubble" | component_note_write | supabase:idea.create (validator:block) | ☐ |
| 3.6 | „write a python script that does X and run it" | coding_task | openfang:openclaude-coder | ☐ |
| 3.7 | „fix the bug in `som_core.py` line 200" | coding_task | openfang:openclaude-coder | ☐ |
| 3.8 | „leg 5 Ideen mit den Titeln A,B,C,D,E an" | idea_create_batch | supabase:idea.* | ☐ |
| 3.9 | „onboarding-workflow für neuen Mitarbeiter" (HR) | desktop_skill | openfang:desktop-skill | ☐ ⚠️ Telegram-Approval |
| 3.10 | „evaluate the X bubble for project-readiness" | bubble_evaluate | supabase:bubble.evaluate + feedback_loop | ☐ |
| 3.11 | „auto-link alle Ideen in der Bubble" | idea_auto_link | supabase:idea.auto_link | ☐ |
| 3.12 | „regeneriere die Embeddings der Bubble" | bubble_generate_embeddings | supabase:* | ☐ |

### 3b. Bürgergeld-Suite (sensibel — bleiben lokal, kein Auto-Versand)

| # | Intent | Capability | Status |
|---|--------|-----------|--------|
| 3.13 | „lies das neue Jobcenter-Schreiben in eingang/" | buergergeld_parse_eingang | ☐ ⚠️ lokal/sensibel |
| 3.14 | „was fehlt noch für meinen Bürgergeld-Antrag?" | buergergeld_status_abgleich | ☐ ⚠️ lokal/sensibel |

---

## 4. INSANE — vage / explorativ / mehrteilig (AutoGen)

| # | Intent | erwartet | Status |
|---|--------|----------|--------|
| 4.1 | „wie baue ich am besten einen Newsletter-Flow auf?" | insane → AutoGen | ☐ |
| 4.2 | „entwirf eine Strategie für meinen Produkt-Launch" | insane → AutoGen | ☐ |
| 4.3 | „überlege dir, wie wir das Marketing automatisieren könnten" | insane → AutoGen | ☐ |
| 4.4 | „design an end-to-end architecture for the whole system" | insane → AutoGen | ☐ |
| 4.5 | „finde heraus, was wir verbessern könnten und schlag was vor" | insane → AutoGen | ☐ |
| 4.6 | „plane und orchestriere ein mehrteiliges Projekt von Grund auf" | insane → AutoGen | ☐ |

> ⚠️ AutoGen ist **Phase B** — bis dahin fällt insane auf SoM zurück. Test prüft
> hier nur die Klassifikation (`handler=autogen` im Log), nicht die echte AutoGen-Ausführung.

---

## 5. SECURITY / OPS (broadcast → poc-* Agenten)

| # | Intent | Capability | Agenten | Status |
|---|--------|-----------|---------|--------|
| 5.1 | „scan for hardcoded api keys" | security_scan | poc-security-scanner | ☐ |
| 5.2 | „audit secrets in this codebase" | security_scan | poc-secret-vault | ☐ |
| 5.3 | „the api is throwing 500 errors" | incident_response | poc-alerter, poc-forensics | ☐ |
| 5.4 | „analysiere die Datei error.log" | log_analysis | poc-log-analyzer | ☐ |
| 5.5 | „review my code in X for bugs" | code_review | brain-coder + poc-security-scanner | ☐ |
| 5.6 | „compose a follow-up email to the team" | email_action | poc-email-* | ☐ |

---

## 6. RESUME / EXECUTE (Plan-Lebenszyklus — Phase 5/6)

| # | Intent | Capability | Status |
|---|--------|-----------|--------|
| 6.1 | (nach SoM-Rückfrage) „AI-Vollzeit Konzern" | som_resume → re-plan | ☐ |
| 6.2 | (nach SoM-Rückfrage) „x" | som_resume → abbrechen | ☐ |
| 6.3 | „führe den Plan aus" / „los, mach das" | som_execute | ☐ ⚠️ Approval-Gates |
| 6.4 | „starte die Ausführung" | som_execute | ☐ |

---

## 7. META / AGENT-MANAGEMENT

| # | Intent | Capability | execution_target | Status |
|---|--------|-----------|------------------|--------|
| 7.1 | „create a new OpenFang agent for task X" | openfang_agent_create | mcp:openfang-agents | ☐ |
| 7.2 | „promote die Bubble X zum Projekt" | bubble_promote | supabase:bubble.noop | ☐ |
| 7.3 | „score the bubble X" / „wie reif ist die Bubble?" | bubble_score | supabase:bubble.score | ☐ |

---

## Test-Mechanik

```bash
# Einzeltest (UTF-8 via Datei, sonst Umlaut-Mojibake):
printf '{"intent":"erstelle eine Excel mit Spalten Name und Betrag"}' > /tmp/t.json
curl -s -X POST http://localhost:5000/api/multihop/execute \
  -H "Content-Type: application/json" --data-binary @/tmp/t.json

# Routing-Entscheidung im Log nachsehen:
C=$(docker ps --filter "name=vibemind_brain-core" --format "{{.Names}}")
docker logs --since 2m "$C" 2>&1 | grep "\[multihop\] difficulty"
```

## Vorbedingungen für echte Ausführung (NICHT nur Routing)
- **OpenFang :4200 erreichbar** vom Brain-Container (aktuell ⚠️ `host.docker.internal` unreachable
  → hard/insane/openfang:-Targets routen korrekt, versanden aber bei der Ausführung).
- **Supabase erreichbar** für die 46 `supabase:`-Targets (bubble/idea CRUD).
- **Telegram-Bot aktiv** für desktop_skill / som_execute Approval-Gates.
- **Sensible Bürgergeld-Intents** bleiben lokal — kein Auto-Versand ans Jobcenter.

## Bekannte Routing-Feinheiten
- **medium mit direktem Cap-Match** (z.B. „öffne example.com") nimmt den Shortcut
  *vor* der Difficulty-Klassifikation → loggt KEINE difficulty-Zeile (by design, schnell).
- **off-domain Wissensfragen** („Hauptstadt von Frankreich") → easy/chat, NICHT knowledge_query
  (das ist Vibemind-Domain-beschränkt).
- **destruktive Intents** (delete_all, bubble_delete, idea_delete) ⚠️ in Testumgebung vorsichtig.
