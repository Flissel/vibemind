# Plan: Provider-Failover + Circuit-Breaker für Brain-LLM-Calls

> Inspiriert von `ruvnet/agentic-flow` `src/core/provider-manager.ts` (~250 Z.
> echte, vollständige Logik — im Gegensatz zu `router.ts`, das voller
> `TODO: implement` ist).
> Status: **PLAN — noch nicht umgesetzt.** Datum: 2026-06-09.
> Verwandt: [tasks/todo-llm-router.md](todo-llm-router.md), Memory
> `project_openclaw_brain_dispatcher` (die hardcodierte Groq→OpenRouter→gpt-4o-mini-Kette),
> `project_routing_matrix_autotrain` (Per-Provider-Limits Hintergrund).

## Problem (verifiziert im echten Code)

`vibemind-os/brain/the_brain/core/multi_llm_router.py` hat:
- ✅ Per-Provider-**Semaphore** gegen 429-Kaskaden (`_PROVIDER_LIMITS`, Z.44-51) —
  das ist *Concurrency-Begrenzung*, KEIN Retry/Failover.
- ⚠️ **Genau einen** Fallback (Z.605-611): wenn ein Nicht-Planning-LLM failt →
  einmal zum Planning-LLM. Sonst `raise`.
- ❌ **Kein** Retry mit Backoff, **kein** Circuit-Breaker, **keine** geordnete
  Provider-Kette mit Recovery.

Die "echte" Provider-Kette (Groq→OpenRouter→OpenAI) lebt damit als Folklore in
`PLANNER_MODEL`-ENV + manuellem Wissen, nicht als Runtime-Logik.

OpenFang-seitig: `agent.toml` deklariert `[[fallback_models]]`
(`agent.rs:405-414`), aber das Feld wird bei der Agent-Ausführung **nie benutzt**
(verifiziert — nur deklariert).

## Was von `provider-manager.ts` portierbar ist (echte Logik, kein TODO)

| Mechanik | TS-Quelle | Portierbar? |
|---|---|---|
| **Circuit-Breaker** (nach `maxFailures` consecutive → Provider `recoveryTime` aus) | `recordFailure` Z.498, `getAvailableProviders` Z.231 | ✅ direkt |
| **`isRetryableError`** (`/429/`, `/rate limit/`, `/503/`, `/502/`, `/timeout/`) | Z.454-466 | ✅ exakt unsere Fehler |
| **Exponential Backoff** (1→2→4→8s, cap 30s) | `calculateBackoffDelay` Z.441 | ✅ direkt |
| **`executeWithFallback`** (selektierter Provider, dann alle gesunden der Reihe nach) | Z.329-396 | ✅ Kernstück |
| **Health/Metrics pro Provider** (successRate, avgLatency, cost) | Z.471-531 | ✅ optional, gut fürs Routing-Matrix-Autotrain |
| Cost-/Performance-Selektion | `selectByCost/Performance` | ⚠️ später (braucht Cost-Tabelle) |

## Einhängepunkt (verifiziert)

**Datei:** `vibemind-os/brain/the_brain/core/multi_llm_router.py`
**Funktion:** `_acall_openrouter()` (Z.633-676) ist der eine Punkt, durch den die
async LLM-Calls laufen. Ein Wrapper `_acall_with_failover()` davor ist der
sauberste Sitz — die bestehenden Per-Provider-Semaphore bleiben **drinnen**
(erst Semaphore, dann Call), der Failover liegt **außen drum**.

NICHT in `vibemind_shared.get_client()` (llm_client.py:142) einbauen — das gibt
nur einen rohen SDK-Client zurück, kennt keine Provider-Kette. Failover gehört
auf die Aufruf-Ebene (Router), nicht auf die Client-Fabrik.

---

## Phase 1 — Failover-Wrapper (Kern, ~1 Sitzung)

### Neue Komponente: `ProviderFailover` (eigene Datei, klein, testbar isoliert)

`vibemind-os/brain/the_brain/core/provider_failover.py`:

- `is_retryable(exc) -> bool` — Port von `isRetryableError` (httpx/requests
  HTTPError-Status + Message-Regex 429/502/503/timeout/connection).
- `backoff_delay(retry, mode="exponential") -> float` — Port von
  `calculateBackoffDelay` (asyncio.sleep-Werte, cap 30s).
- `class CircuitBreaker` — pro Provider: `consecutive_failures`, `open_until`
  (statt `Date.now()` — Brain läuft normal, kein Workflow-Sandbox; `time.monotonic()`
  ok). `maxFailures=3`, `recoveryTime=60s` als Defaults (ENV-überschreibbar,
  Muster wie `_PROVIDER_LIMITS`).
- `async def call_with_failover(models: list[str], fn) -> result` — probiert
  `models` der Reihe nach; pro Modell `maxRetries` mit Backoff bei retryable;
  Circuit-Breaker überspringt offene Provider; alle failen → letzten Fehler raisen.

### Verdrahtung in `multi_llm_router.py`

1. `_acall_openrouter()` bleibt unverändert (der "innere" Call).
2. Neuer `_acall_with_failover(model, prompt, ...)`:
   - Modell-Kette bauen: `[primary] + fallback_models`. Quelle der Kette:
     - **kurzfristig:** ENV (die heutige Groq→OpenRouter→OpenAI-Reihenfolge
       explizit als Liste, ersetzt das implizite `PLANNER_MODEL`-Wissen).
     - **mittelfristig:** aus `agent.toml [[fallback_models]]` durchreichen
       (schließt die OpenFang-Lücke, dass das Feld ungenutzt ist).
   - `await failover.call_with_failover(chain, lambda m: self._acall_openrouter(m, ...))`.
   - Provider-Key via vorhandenem `_provider_key(model, api_url)`.
3. Aufrufer in `aroute()` (Z.~591) auf `_acall_with_failover` umstellen. Der
   bestehende Single-Fallback (Z.605-611) wird damit redundant → entfernen oder
   als letztes Kettenglied modellieren.

### Konfiguration

- `BRAIN_LLM_FALLBACK_CHAIN` (ENV, kommagetrennt) — explizite Kette, z.B.
  `groq::llama-3.3-70b,openrouter/...,gpt-4o-mini`.
- `BRAIN_CB_MAX_FAILURES` (default 3), `BRAIN_CB_RECOVERY_S` (default 60).
- Defaults so wählen, dass Verhalten ohne ENV ~= heute (kein Regress).

---

## Phase 2 — Metriken ans Routing-Matrix-Autotrain (optional)

`ProviderFailover` sammelt successRate/avgLatency/cost pro Provider (Port von
`recordSuccess/recordFailure`). Diese Signale in die bestehende
Routing-Matrix-Pipeline (`project_routing_matrix_autotrain`, :5001
ProductionPlanner) einspeisen → organisches Lernen, welcher Provider für welche
Task-Klasse robust/günstig ist. NICHT in Phase 1 — erst wenn Failover stabil.

---

## Verifikation (Pflicht vor "fertig")

1. **Unit** (isoliert, kein echter LLM):
   - `is_retryable`: 429/503/timeout → True; 400/auth → False.
   - `backoff_delay`: monotone Werte, cap 30s.
   - `CircuitBreaker`: nach 3 Fails offen; nach `recovery_s` wieder zu.
   - `call_with_failover`: 1. Modell wirft 429 → fällt auf 2. Modell; alle
     werfen → letzter Fehler propagiert; offener Breaker wird übersprungen.
2. **Integration** (gemockter `_acall_openrouter` mit injizierten Fehlern):
   - Kette Groq(429)→OpenRouter(ok) liefert OpenRouter-Antwort, 1 Fallback-Hop.
3. **Live** (echter Brain, ein bewusst kaputtgemachter Primär-Key):
   - `multihop_execute` läuft durch, Logs zeigen Failover-Hop, Antwort kommt.
   - Kein Regress: mit korrekten Keys identisches Verhalten wie heute.
4. Keine Secrets in Logs (Keys nie loggen — nur Provider-Namen).

---

## Bewusst NICHT in diesem Plan

- `router.ts` portieren (großteils `TODO: implement`, kein Mehrwert).
- agentic-flow als Dependency.
- Cost-optimized Routing in Phase 1 (braucht gepflegte Cost-Tabelle → später).
- get_client()/llm_client.py anfassen (falscher Layer).
