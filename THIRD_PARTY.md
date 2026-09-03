# Third-party code and attributions

The root repository and most first-party components are MIT-licensed (see
[LICENSE](LICENSE)). Several vendored directories and submodules carry their
own licenses that take precedence for their subtree. **The monorepo is
therefore "MIT with exceptions" — always check the closest LICENSE file.**

Status column: ✅ = license present and compatible · ⚠️ = restriction, read
the note · ⏳ = being resolved before the v1.0.0 release.

## Vendored code (inside `vibemind-os`)

| Path | Upstream | License | Status |
| --- | --- | --- | --- |
| `vibemind-os/spaces/rowboat/rowboat` | [rowboatlabs/rowboat](https://github.com/rowboatlabs/rowboat) | Apache-2.0 | ✅ |
| `vibemind-os/spaces/mirofish/mirofish` | [666ghj/MiroFish](https://github.com/666ghj/MiroFish) via nikmcfly/MiroFish-Offline; engine [camel-ai/oasis](https://github.com/camel-ai/oasis) | **AGPL-3.0** | ⚠️ copyleft — this subtree is AGPL, not MIT; network use triggers source obligations |
| `vibemind-os/brain/the_brain` | contains code © 2025 ATM-R Project | MIT (ATM-R) | ✅ attribution via its LICENSE |
| `vibemind-os/skills/science/` (136 files) | Anthropic science skill collection | none shipped | ⚠️ excluded from the release — see below |
| `vibemind-os/skills/openclaw-official/` | openclaw upstream | MIT (upstream) | ⚠️ excluded — belongs to the openclaw project |
| `vibemind-os/skills/{excel,office,word,aws,composio,devops,dev,research,security,tapestry,utility}/` | third-party skill collections | none shipped | ⚠️ excluded from the release |
| `.agents/skills/` (56 skills) | Anthropic skills + [obra/superpowers](https://github.com/obra/superpowers) | none shipped | ⚠️ excluded — development-environment tooling, not product |
| `vibemind-os/spaces/marketing/curator/vendor/` | Alpine.js, Tailwind CSS | MIT | ⏳ verify headers survived minification |

## Submodules (separate repositories)

| Submodule | Upstream / origin | License | Status |
| --- | --- | --- | --- |
| `vibemind-os/openfang` | fork of [RightNow-AI/openfang](https://github.com/RightNow-AI/openfang) | Apache-2.0 / MIT dual | ✅ |
| `vibemind-os/openclaw` | fork of [openclaw/openclaw](https://github.com/openclaw/openclaw) (© Peter Steinberger) | MIT | ✅ |
| `vibemind-os/coding-engine` | DaveFelix Coding Engine | Apache-2.0 | ✅ (authorization confirmation pending) |
| `vibemind-os/openclaude` | fork of leaked proprietary source | **none** | ⚠️ being retired — not part of the v1 release (replaced by the engine's OpenRouter/Agent-SDK/official-CLI backends) |
| `vibemind-os/brain/the_brain/tribe` | fork of facebookresearch/tribev2 | **CC BY-NC 4.0** | ⚠️ non-commercial — optional add-on, excluded from commercial use |
| `vibemind-os/spaces/shuttles/swe_desgine` | based on SakanaAI AI-Scientist | AI Scientist Source Code License v1.0 | ⚠️ non-OSI, commercial restrictions |
| `vibemind-os/spaces/video/vibevideo` | first-party | MIT | ✅ |
| `vibemind-os/spaces/video/laura` | first-party (Lauras_star) | MIT | ✅ public since 2026-08-30 |
| `vibemind-os/spaces/video/vibevideo_deepfake` | first-party | VibeMind Synthetic Media Source Code License (based on [RAIL](http://licenses.ai/) v1.1) | ✅ public since 2026-08-30 — use-restricted: consent, labelling of synthetic output, no impersonation/NCII/surveillance |
| `vibemind-os/spaces/captain_cook` | first-party (+ nested [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) fork, MIT; minibook component Apache-2.0) | ⏳ root license to be selected | ⏳ |
| `vibemind-os/spaces/sales` | first-party (aisalesorgcore) | ⏳ | ⏳ LICENSE to be added |
| `vibemind-os/voice` | first-party (VibeMind-VoiceDialog) | MIT (badge) | ⏳ LICENSE file to be added |
| `vibemind-os/voice/external/zeroclaw` | zeroclaw-labs/zeroclaw | Apache-2.0 | ✅ |
| `vibemind-os/voice/external/minibook` | c4pt0r/minibook | Apache-2.0 | ✅ |
| `vibemind-os/voice/electron-app/clawport-ui` | JohnRiceML/clawport-ui | MIT | ✅ |
| `vibemind-os/la-fungus-search` | first-party | MIT | ⚠️ vendored EmbeddingGemma weights (Google **Gemma Terms**, gated) are being removed — weights load from Hugging Face at runtime instead |

## Model weights

No model weights are intended to ship in this repository. Embeddings and LLM
calls run against external APIs or are downloaded at runtime under their own
terms (e.g. Google Gemma Terms for EmbeddingGemma).

## Skill collections — audit result (2026-08-30)

The repository accumulated ~450 skill files from external sources. None of
them shipped a license, so none can be redistributed under this project's
MIT license. They are also **not part of the product**: VibeMind runs without
them; they are tooling for the development environment.

**Therefore all third-party skill collections are excluded from the public
release.** Identified sources:

- **Anthropic skills** — `science/` (136 files: adaptyv, benchling, biopython,
  cellxgene, deepchem, …), plus `docx`/`pdf`/`pptx`/`canvas-design`/
  `brand-guidelines`/`slack-gif-creator` and others under `.agents/skills/`.
  `brand-guidelines` additionally contains Anthropic's trademark guidance.
- **obra/superpowers** — 10 skills under `.agents/skills/`
  (`brainstorming`, `systematic-debugging`, `writing-plans`,
  `executing-plans`, `using-git-worktrees`, `writing-skills`, …), plus copies
  under `vibemind-os/skills/dev/`.
- **openclaw upstream** — `openclaw-official/` (22 files).
- **Unattributed third-party** — `excel`, `office`, `word`, `aws`, `composio`,
  `devops` (a copy of an Anthropic diagram skill), `research` (genealogy),
  `security` (ffuf fuzzing), `tapestry`, `utility`.

**First-party skills that stay in the release:** `roarboot`, `rowboat`,
`relay-skill`, `orchestrator`, `chrome`, `vscode`, `file-explorer`,
`claude-desktop`, `tests` — plus the VibeMind-specific ones under
`.agents/skills/` (`v1-*`, `source-command-vibemind-notify`,
`llm-config-migration`).

Anyone who wants the excluded collections can install them from their own
upstreams; the release documents where they came from.
