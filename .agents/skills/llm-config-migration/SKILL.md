---
name: llm-config-migration
description: Migrate hardcoded LLM client instantiations across vibemind-os to use the unified vibemind_shared.get_client(role) factory. Use when the user wants to centralize LLM configuration, switch providers without code changes, or prepare the repo for open-source release. Supports auditing direct LLM usage, sanitizing .env files, and migrating files one service at a time.
---

# LLM Config Migration Skill

You are migrating the **vibemind-os** monorepo to a unified, role-based LLM configuration system. The goal is **one config file** (`llm_config.yml`) that controls every LLM call in the codebase, so users can switch providers/models without touching code — required for open-source release.

## The architecture

```
   llm_config.yml          ← single source of truth
        |
        v
   vibemind_shared         ← pip-installable factory package
   .get_client(role)       ← returns AsyncOpenAI or AsyncAnthropic
        |
        v
   <every service>         ← imports get_client, no hardcoded providers
```

## Supported providers (exactly 5 — do not add more)

| Provider | Driver type | Use for |
|----------|------------|---------|
| `openai` | openai | gpt-4o, gpt-4o-mini, gpt-4o-realtime-preview (voice) |
| `anthropic` | anthropic | Codex-sonnet-4-5, Codex-opus-4 (best for code) |
| `openrouter` | openai | gateway to 100+ models, free tier for security/red-team |
| `google` | openai | gemini-2.0-flash (cheap fast classification) |
| `ollama` | openai | local homelab default — no key, runs on 127.0.0.1:11434 |

**Do NOT add Bedrock, Azure, Vertex, Groq, DeepSeek, Mistral, etc.** Users who need those can add a custom provider via the `overrides:` mechanism in their own `llm_config.yml`. Keeping the supported set small means simpler code, fewer dependencies, and a single auth model (`api_key` + `base_url`).

**Key files:**
- `vibemind-os/shared/src/vibemind_shared/llm_client.py` — the factory
- `vibemind-os/llm_config.yml.example` — canonical config template (all roles)
- `vibemind-os/shared/scripts/audit_llm_usage.py` — find direct LLM usage
- `vibemind-os/shared/scripts/sanitize_env.py` — redact secrets from .env
- `vibemind-os/LLM_AUDIT_REPORT.md` — current migration backlog (398 files)

## Workflow

### 1. Always start with the audit report

Read `vibemind-os/LLM_AUDIT_REPORT.md` to see which files still have direct LLM instantiations. The report is grouped by service. Pick **one service** at a time — never try to migrate the whole repo in one pass.

If the report is stale (older than the last code change), regenerate it:
```bash
cd vibemind-os && python shared/scripts/audit_llm_usage.py --root . --out LLM_AUDIT_REPORT.md
```

### 2. For each file, follow this exact pattern

**Before (direct instantiation):**
```python
from openai import AsyncOpenAI
import os

client = AsyncOpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url="https://api.openai.com/v1",
)
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
)
```

**After (vibemind_shared):**
```python
from vibemind_shared import get_client, get_model

client = get_client("coding_executor")   # role from llm_config.yml
response = await client.chat.completions.create(
    model=get_model("coding_executor"),
    messages=[...],
)
```

**Rules:**
- The `role` argument MUST already exist in `llm_config.yml`. If you need a new role, add it to `llm_config.yml.example` first AND mention it in the user-facing summary.
- Never invent role names — pick the closest existing one or ask the user.
- Keep model names OUT of the calling code. Always go through `get_model(role)`.
- For Anthropic-style calls (`messages.create` instead of `chat.completions.create`), `get_client` returns `AsyncAnthropic` automatically when the provider type is `anthropic`.

### 3. Map common patterns to roles

| Direct usage hint                            | Role to use                  |
|----------------------------------------------|------------------------------|
| `gpt-4o` general purpose                     | `coding_test_writer` / `agent_minibook` |
| `Codex-sonnet` for planning                 | `coding_planner`             |
| `Codex-sonnet` for code execution           | `coding_executor`            |
| Anthropic SDK for review                     | `coding_reviewer`            |
| Voice realtime (`gpt-4o-realtime`)           | `voice_realtime`             |
| Brain reasoning (Tahlamus)                   | `brain_*` family             |
| Red/blue team security                       | `security_red_team` / `security_blue_team` |
| Email personalization (was Groq llama)       | `email_personalizer` (now via openrouter) |
| Cheap fast classifier                        | `rag_classifier` (google gemini-2.0-flash) |
| Local Ollama (anything offline)              | `local_default` / `local_chat` / `local_fast` |
| Anything from Groq/DeepSeek/Mistral/etc.     | Use `openrouter` provider — same models, single key |

If none fit, **add a new role** to `llm_config.yml.example` with a sensible default and explain why in the user-facing summary.

### 4. Verification after each file edit

After editing a file:
1. **Run the audit script on just that service** to confirm the file moves to "Already migrated":
   ```bash
   python shared/scripts/audit_llm_usage.py --root <service-name> --out _check.md
   ```
2. **Look for indirect breakage**: grep the file for any remaining `import openai`, `import anthropic`, hardcoded `model=` strings, or `os.environ.get("*_API_KEY")` calls that should also go through the factory.
3. **Don't run the actual service** — it usually requires Docker/network and isn't worth the friction for a config refactor. Trust the audit script.

### 5. Sanitize secrets before commit

Before suggesting any commit, run:
```bash
python shared/scripts/sanitize_env.py --root . --check-only
```

This exits non-zero if any `.env` file still contains real keys. The user must `--in-place` rewrite or manually clean before pushing to a public repo.

## What NOT to do

- **Never** edit `llm_config.yml` directly (it's gitignored). Always edit `llm_config.yml.example` and tell the user to copy it.
- **Never** delete the old service-local `llm_config.yml` files (`brain/the_brain/llm_config.yml`, etc.) until ALL files in that service are migrated. They're used by the legacy code path during transition.
- **Never** migrate test files in `_archive/`, `old_tests/`, or `test_data/` — they're excluded from the audit for a reason.
- **Never** touch the `vibemind_shared` package itself (it's the allowlisted exception). If you think the factory needs a new feature, propose it in the user-facing summary instead of editing inline.
- **Never** rewrite minified JS files (`dashboard-app/out/renderer/assets/*.js`) — those are build artifacts. Rebuild from source instead.
- **Never** commit `.env` files — only `.env.example` and `.env.example.generated`.
- **Never** add new providers without updating `vibemind_shared/llm_client.py` to handle the provider `type`. Currently supported types are `openai` and `anthropic`.

## Open-source release checklist

When the user says "make this opensource ready", run through these in order:

1. `python shared/scripts/sanitize_env.py --root . --check-only` — must exit 0
2. `python shared/scripts/audit_llm_usage.py --root . --out LLM_AUDIT_REPORT.md` — should show <50 migration targets
3. Verify `llm_config.yml.example` has a role for every service in the audit report
4. Check that `vibemind-os/.gitignore` excludes: `.env`, `llm_config.yml`, `*.sanitized`, `LLM_AUDIT_REPORT.md`, `SECRETS_REPORT.md`, `.fungus_cache/`
5. Verify `vibemind-shared` is published or installable from the monorepo (`pip install -e shared/`)
6. Each top-level service should have a README explaining how to set up `llm_config.yml`
7. Run `git grep -i "sk-or-v1\|sk-proj-\|sk-ant-\|gsk_\|sm_e[A-Z]"` — must return zero lines

Refer the user to `vibemind-os/OPENSOURCE_RELEASE_CHECKLIST.md` for the full step-by-step.

## When to delegate vs. do directly

- **Single file migration**: do it directly with Read + Edit
- **Whole service migration (>10 files)**: spawn a sub-agent per file in parallel using the Agent tool — give each agent the exact file path, the role to use, and a copy of the "Before/After" pattern above
- **New role design**: ask the user first, never guess
- **Bulk sanitization**: use `sanitize_env.py --in-place` only after the user explicitly confirms (it overwrites real `.env` files)