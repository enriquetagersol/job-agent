# Development instructions

Work within this repository. These instructions govern code development; the employment assistant's runtime behavior is defined separately in `agent_instructions.md`, `jobs/agent.py` and `chat/conversational_agent.py`.

## Project organization

- `app.py`: Streamlit entry point and composition of feature interfaces.
- `main.py`: existing command-line profile/recommendation entry point.
- `profiles/`: profile migration, career entries, editors, confirmed skills and progressive enrichment.
- `jobs/`: search/extraction, agent orchestration, structured evaluations, ranking and recommendation explanations.
- `chat/`: floating chat interface and conversational LLM/tool loop.
- `memory/`: company interests, conversational preferences, saved/discarded offers and adaptive-priority history.
- `resumes/`: current base CV generation, PDF preview and download.
- `shared/`: shared paths, private JSON persistence, validation, wire-format compatibility and sanitized diagnostics.
- `tests/`: offline unit and simulated Streamlit integration tests.

Create new files directly in the appropriate feature package. Reuse shared code rather than duplicating it; add folders only when there is a concrete responsibility. Keep cross-feature orchestration in the entry point or an explicit coordinating module. Update imports, test patch targets, documentation and paths when moving modules.

Each own Python file must begin with an English triple-quoted module docstring describing its actual responsibility and integration. Update that description when responsibility changes. New filenames, identifiers, comments and documentation use English; preserve Spanish interface text. Preserve existing stored JSON aliases unless a backward-compatible migration is explicitly needed.

## Execution and verification

From the repository root, using the existing environment:

```bash
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
.venv/bin/python main.py
.venv/bin/python run_tests.py
```

The test runner blocks network access and isolates diagnostics in a temporary directory. Mock OpenAI/Tavily for tests; never consume real APIs as routine verification. Unit/AppTest success is not browser or real-model end-to-end validation. Validate relevant interactions and report pending checks honestly. Do not change interface design or behavior during structural refactors.

## Runtime instructions, data and secrets

Use `shared.paths.PROJECT_ROOT` for project-relative data, `.env` and instruction paths; never derive their locations from a feature package directory. Keep existing `user_profile.json`, `.local_data/` and legacy migration destinations at the repository root. Moving code must not relocate, reset, silently overwrite or lose private data.

Preserve `agent_instructions.md` and its loading into the model's `instructions` parameter for search, evaluation and CLI guidance. Chat runtime instructions remain separate in `chat/conversational_agent.py`; skill proposal instructions remain in `profiles/skills.py`. Do not substitute this `AGENTS.md` for employment-assistant instructions or automatically send it to the runtime model.

Never commit secrets, `.env`, private profiles, results, feedback/memory records or personal PDFs. Preserve `.gitignore` protections for legacy and current private paths, the environment and generated PDFs. Do not display key contents or private payloads in logs; diagnostics use allowlisted technical metadata. Test with fictional temporary data, and check saved-data access without overwriting actual user files. Do not modify dependencies, virtual environments or generated files as part of documentation/refactor work.

## Multiple chats in one checkout

Before editing, inspect working-tree changes and delimit the files owned by the current task. Communicate the intended scope and coordinate changes to shared modules, entry points, imports and documentation. Do not overwrite another chat's edits, reset unrelated changes or assume an existing diff belongs to you. Re-read shared files before editing and reconcile compatible changes. Pause for coordination when concurrent edits conflict. Do not commit or push unless explicitly authorized for the current task.
