# Coding-Engine Internals (req-gen / regen / Architect) + MiroFish→Bubble-Evaluate

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

The **VibeMind Coding-Engine internals** comprise a hybrid multi-agent architecture for intelligent code generation, combined with a **mirofish-to-bubble bridge** that uses knowledge graphs and expert scoring to evaluate idea readiness before code generation. The core pipeline splits into two parallel streams: (1) **req-gen / requirements enrichment** (architect → chunk-planner → generator agents), and (2) **mirofish knowledge-graph evaluation** that feeds bubble scoring for go/no-go gates.

## Components

### Core Architecture Files

**Architect Agent** (`coding-engine/src/agents/architect_agent.py:81-100`)
- Pre-analysis phase (Phase 1) that analyzes all requirements
- Identifies shared types and interfaces via HybridContractGenerator
- Generates InterfaceContracts (types, endpoints, components, services) for parallel workers
- Assigns file ownership to prevent conflicts
- Supports parallel chunk analysis (configurable `max_parallel_chunks`, default 4)

**Chunk Planner Agent** (`coding-engine/src/agents/chunk_planner_agent.py:79-100`)
- LLM-based intelligent requirement chunking (Phase 2)
- Groups requirements by 12 logical domains mapped to 8 microservices (DOMAIN_TO_SERVICE_MAP)
- Analyzes dependencies via DAG (Directed Acyclic Graph) 
- Scores complexity (simple/medium/complex) per requirement
- Creates balanced chunks for parallel execution via Wave scheduling
- Loads balancing with configurable threshold (default 20% imbalance tolerance)

**Generator Agent** (`coding-engine/src/agents/generator_agent.py:55-80`)
- Autonomous code generation triggered by CODE_FIX_NEEDED events
- Subscribes to recovery attempts and test failures
- Uses ClaudeCodeTool for actual code synthesis
- Publishes CODE_GENERATED, CODE_FIXED, FILE_CREATED/MODIFIED events
- Integrates with AutogenTeamMixin for swarm-based code orchestration

**DAG Parser** (`coding-engine/src/engine/dag_parser.py:78-100`)
- Parses requirements JSON into RequirementsData structure
- Builds networkx.DiGraph for dependency inference
- Groups requirements by tag/domain/type
- Computes topological order for execution scheduling

**Execution Plan** (`coding-engine/src/engine/execution_plan.py:84-99`)
- ServiceGroup: Clusters requirements by domain (auth, user, payment, dashboard, etc.)
- RequirementChunk: Work package for single worker with dependency tracking
- Wave: Parallel execution stage respecting inter-chunk dependencies
- Estimates task duration per complexity level (simple=3min, medium=5min, complex=10min)

### MiroFish-to-Bubble Bridge

**Bubble Evaluate Capability** (`brain/the_brain/data/capabilities.yaml:21-50`)
- Direct execution target: `supabase:bubble.evaluate` (replaces former `spaces.mirofish.tools.mirofish_tools:evaluate_bubble_readiness`)
- Triggered by voice patterns: "evaluate/assess/bewerte bubble X" or "ready for production"
- Argument extraction: regex captures bubble name between 'evaluate' and 'bubble'
- Validator: ensures result score in [0,100] range
- Status: ACTIVE (scored by Brain's own groq_subagent, writes metadata.ai_eval to Supabase)

**Capability Executor** (`brain/the_brain/core/capability_executor.py:56-150`)
- Resolves and invokes direct execution targets via DirectExecutor
- Lazy module import with caching (code changes require Brain restart)
- Always returns envelope: `{ok: bool, result/error: Any, elapsed_s: float, target: str}`
- Ensures system paths include `vibemind-os`, `vibemind-os/spaces`, `vibemind-os/voice/python`

**MiroFish Tools Registry** (`data/space_capabilities/mirofish.yml:1-259`)
- 34 total tools (32 documented), 0 explicit voice-triggers
- Docker management: start_docker, stop_docker, restart_docker, docker_status
- Graph operations: generate_ontology, build_graph, search_graph, get_graph_summary
- Simulation: configure_simulation, start_simulation, poll_simulation, interview_agent
- Reports: generate_report, get_report, chat_report
- Full pipeline: run_prediction (ontology → graph → simulation → report)
- **Bubble integration**: evaluate_bubble_readiness (line 252-258) — uses MiroFish KG + Minibook expert panel

## Dependencies

### Upstream (Needs)

**Requirements Generator → Architect/Chunk Planner**
- Consumes RequirementsData (DAG + nodes/edges) from DAGParser
- Depends on ContractGenerator / HybridContractGenerator for interface synthesis
- Uses DocumentRegistry to persist ImplementationPlan, PlannedFix, FileChange documents
- Memory tool integration (MemoryTool) for pattern recall from similar architectures

**Generator → Event Bus**
- Subscribes to: CODE_FIX_NEEDED, RECOVERY_ATTEMPTED
- Publishes: CODE_GENERATED, CODE_FIXED, FILE_CREATED, FILE_MODIFIED
- Integrates with SharedState for cross-agent communication

**Bubble Evaluate → MiroFish Backend**
- MiroFish Docker stack: Flask API + Neo4j + Ollama (port 5000 assumed)
- Knowledge graph endpoints: /api/graph/*, /api/simulation/*, /api/report/*
- Rowboat integration: predict_from_knowledge pulls bubble context via brain-db

**Brain Executor → Module Import**
- VibeMind path roots: `vibemind-os`, `vibemind-os/spaces`, `vibemind-os/voice/python`
- Target modules must be importable and contain callable matching func_name

### Downstream (Callers)

**Spaces/Coding → Coding Agent**
- Exposes generate_code, get_generation_status, start_preview tools (spaces/coding/tools/coding_tools.py)
- Registry agent: brain-coder
- Events routed: code.generate, code.modify, code.status, code.show, code.preview.*, code.list, code.cancel

**Spaces/Ideas → Bubble Tools**
- Calls score_bubble, evaluate_bubble_evolution (spaces/ideas/tools/bubble_tools.py)
- Registry agent: brain-bubbles
- Events routed: bubble.*, idea.*

**OpenFang Agent Dispatch** (brain-coder, brain-forecaster, brain-bubbles)
- Router broadcasts intents to primary + supporting agents per capabilities.yaml
- Expects tool results within timeout (typically 30-120s per stage)
- Handles agent unavailability via fallback list

**Voice/Python Publishing** (mirofish_publisher.py)
- Syncs mirofish simulation results back to rowboat/ideas space
- May trigger bubble enrichment loop

## Possible Usages

### Architecture Phase (Architect Agent)
```
User bubble "E-Ticketing Platform" contains:
- 50 requirements (auth, payment, validation, offline-sync, etc.)

→ Architect analyzes
→ Identifies 8 shared types (Ticket, Fare, Vehicle, Journey, etc.)
→ Generates API contracts (REST endpoints + request/response schemas)
→ Assigns file ownership (backend/auth.py, backend/payment.py, etc.)
→ Publishes 1 ImplementationPlan to DocumentRegistry
```

### Chunking Phase (Chunk Planner Agent)
```
RequirementsData(50 requirements) →
- Groups by DOMAIN_TO_SERVICE_MAP (auth→auth-service, payment→billing-service, etc.)
- Scores complexity: 10 simple, 20 medium, 20 complex
- Creates 5 chunks: [auth(3 reqs), payment(5), validation(8), sync(12), admin(7), etc.]
- Assigns waves: Wave1=[auth], Wave2=[payment, validation], Wave3=[sync], etc.
- Assigns 3 workers with load balancing
→ Publishes ExecutionPlan to shared state
```

### Generation Phase (Generator Agent)
```
ExecutionPlan + Chunk1 (auth requirements) →
- Generator receives CODE_FIX_NEEDED event
- Calls ClaudeCodeTool.generate() with ContractGenerator's interface spec
- Publishes FILE_CREATED (backend/auth.py, types/auth.ts)
- On error, publishes CODE_FIX_NEEDED again
→ Continues until all chunks complete or max retries exceeded
```

### Bubble Readiness Evaluation
```
User voice: "evaluate EU E-Ticketing bubble"

→ Brain router matches "evaluate...bubble" pattern
→ Executes bubble_evaluate capability
→ DirectExecutor calls supabase:bubble.evaluate(bubble_name="EU E-Ticketing")
→ Supabase function:
  1. Fetches bubble content from vibemind-db
  2. Calls groq_subagent to score across 5 dimensions
     (clarity, completeness, feasibility, innovation, risk)
  3. Writes score + missing_items to metadata.ai_eval
  4. Returns {score: 78, ready: true, missing_items: [...]}
→ Capability validator checks score in [0,100]
→ Response returned to user + bubble metadata updated
```

### Voice Triggers
- "Create a new project space for E-ticketing" → bubble_create
- "Add 5 requirements for fare validation" → idea_add (batch)
- "Evaluate if this is ready to build" → bubble_evaluate (via mirofish scoring)
- "Generate code for this bubble" → idea_to_project + coding.generate
- "Start simulation on the requirements" → mirofish.simulate (via rowboat)

## Integration Points

### Brain ← → Bubble (Ideas Space)
- Bubble enter/exit → agent context switch (brain-bubbles ↔ bubble's dedicated agent)
- Bubble evaluate → scores via groq_subagent (no mirofish KG-recall)
- Ideas promote → triggers idea_to_project event → coding space

### Bubble ← → MiroFish (Scoring Pipeline)
- **OLD path** (Phase 1U.H, disabled): `spaces.mirofish.tools:evaluate_bubble_readiness` 
  - Hallucination risk: KG-recall created phantom bubbles
  - Import cost: dragged swarm chain into Brain process
- **NEW path** (current): `supabase:bubble.evaluate`
  - Supabase function wraps groq_subagent scoring
  - Zero spaces imports, zero KG-recall
  - Metadata stored in vibemind-db

### Coding Space ← → Architect/Chunk Planner
- idea_to_project converts bubble → ProjectSpec (summary_tools.py:generate_project_structure)
- ProjectSpec → RequirementsData → DAGParser
- DAGParser → ExecutionPlan (chunk_planner_agent.py output)
- ExecutionPlan distributed to generator agents via event bus

### Generator ← → DocumentRegistry
- Architect writes ImplementationPlan (contracts, file ownership, phase timeline)
- Chunk Planner writes ExecutionPlan (chunks, waves, worker assignments)
- Generator writes QualityReport, DebugReport on code generation success/failure
- All persisted in DocumentRegistry for audit/replay

### MiroFish ← → Rowboat (Data Source)
- predict_from_knowledge (mirofish_tools.py:329) fetches context from rowboat
- Runs simulation against that context
- Generates report with agent interviews

## Isolated Startup

### Docker-Based Testing (Mirofish Simulation Alone)
```bash
cd vibemind-os/spaces/mirofish/mirofish
docker-compose up -d  # Starts Flask + Neo4j + Ollama
curl http://localhost:5000/health  # Verify online
```

### Native VibeMind Setup (Full Coding Pipeline)
```bash
# 1. Install dependencies
pip install -r vibemind-os/coding-engine/requirements.txt
pip install -r vibemind-os/brain/requirements.txt

# 2. Start Brain (if using Capability Router)
cd vibemind-os/brain
python -m the_brain.server  # Starts on :4200 (OpenFang API)

# 3. For Architect/Chunk Planner testing (no MCP needed)
python -c "from src.agents.architect_agent import ArchitectAgent; a = ArchitectAgent(use_memory=False); print(a)"

# 4. For Generator testing (requires event bus)
# Use MockEventBus if testing in isolation
```

### MCP Integration
- **vibemind-db**: Supabase PostgreSQL (required for bubble metadata)
- **filesystem**: Read/write generated code (required for generator)
- **git**: Commit generated code (optional, for version control)
- **github**: Create PR (optional, for peer review)
- **context7**: Fetch SDK docs during code gen (optional, improves contract generation)
- **qdrant**: Vector search for pattern recall (optional, improves architect memory)

### Gaps / Stubs
1. **Regen (code REGENERATION)**: No explicit "regen" agent found. Generator handles via CODE_FIX_NEEDED loop, but no dedicated phase for requirement changes → regen.
2. **Society-of-Mind agents**: Architecturally defined (architect, planner, generator), but no explicit "debate" or "verification" agent for consensus on design decisions (ArchitectureHealthAgent exists but is read-only).
3. **Mirofish scoring functions**: evaluate_bubble_readiness is NOW DEPRECATED (supabase:bubble.evaluate). Original mirofish scoring functions (if any in backend/app/services/) are NOT exposed via the tools API.
4. **Voice integration**: mirofish_publisher.py exists but no clear sync trigger (manual? event-driven?).

## Key Files — Load-Bearing References

| File | Line | Purpose |
|------|------|---------|
| `coding-engine/src/agents/architect_agent.py` | 81-100 | ArchitectAgent class definition + contract generation |
| `coding-engine/src/agents/chunk_planner_agent.py` | 79-100 | ChunkPlannerAgent: LLM-based requirement chunking |
| `coding-engine/src/agents/generator_agent.py` | 55-80 | GeneratorAgent: autonomous code generation |
| `coding-engine/src/engine/dag_parser.py` | 78-100 | DAGParser: requirements JSON → dependency graph |
| `coding-engine/src/engine/execution_plan.py` | 84-99 | ServiceGroup, RequirementChunk, Wave datastructures |
| `coding-engine/src/engine/contract_generator.py` | (check for exists) | InterfaceContracts, HybridContractGenerator |
| `brain/the_brain/data/capabilities.yaml` | 21-50 | bubble_evaluate capability routing + bubble_evaluate pattern matching |
| `brain/the_brain/core/capability_executor.py` | 56-150 | DirectExecutor: resolves & invokes direct:module:function targets |
| `spaces/ideas/tools/bubble_tools.py` | 35-1517 | Bubble create/update/score/evaluate (full impl) |
| `data/space_capabilities/mirofish.yml` | 252-258 | evaluate_bubble_readiness tool metadata (DEPRECATED) |
| `data/space_capabilities/bubbles.yml` | 1-1126 | Bubble tools registry (current active API) |
| `spaces/mirofish/tools/mirofish_tools.py` | 577+ | evaluate_bubble_readiness impl (DEPRECATED, now uses supabase:) |
| `voice/python/publishing/mirofish_publisher.py` | (all) | Sync mirofish results → rowboat/ideas |

## Gotchas

1. **Mirofish KG Hallucination (CRITICAL)**: Direct imports of `spaces.mirofish` were creating phantom bubbles via KG-recall during eval. That path is DISABLED. Always use `supabase:bubble.evaluate` instead.

2. **Agent Startup Order**: Architect must complete phase 1 (interface contracts) before ChunkPlanner phase 2 (chunking). Generator depends on both. Event bus publishing order matters.

3. **Path Resolution in DirectExecutor**: If adding new evaluation targets, ensure sys.path includes `vibemind-os/spaces`, `vibemind-os/voice/python`, etc. (see `capability_executor.py:29-53`). Module names must not conflict with Brain's own imports.

4. **Mirofish Backend Offline**: docker-compose may not auto-restart on reboot. Always check `docker ps` + `curl http://localhost:5000/health` before running predict_from_knowledge or simulate.

5. **Chunk Planner LLM Decisions**: DOMAIN_TO_SERVICE_MAP (8 services) is HARD-CODED. Adding a new domain (e.g., "video-processing") requires code change + restart.

6. **ContractGenerator AI Coupling**: Architect uses Claude to generate interface specs. Quality depends on prompt + model. No fallback if API fails; uses cached InterfaceContracts if available.

7. **DocumentRegistry Persistence**: Plans/reports stored in DocumentRegistry, which must be initialized + backed by vibemind-db. No in-memory fallback; missing DB = silent data loss.

8. **Requirements Enrichment Pipeline**: capabilities.yaml routes bubble_evaluate, but the submission_to_req_orchestrator tool (ideas/tools/summary_tools.py:1546) hints at a shuttle-based validation loop that is INCOMPLETELY DOCUMENTED. Check `spaces/shuttles/wizard_handler.py` for shuttle checkpoint logic.

9. **Voice-Triggered Regen**: No explicit voice trigger for "regenerate code from updated bubble". Only path is: bubble edit → manual promote_bubble → idea_to_project (overwrites prior ProjectSpec). Incremental diff-based regen is NOT IMPLEMENTED.

10. **Missing Observability**: No tracing across architect → chunk_planner → generator phases. Error in one phase doesn't propagate status to prior phases. Debugging multi-phase failures requires manual event log inspection.
