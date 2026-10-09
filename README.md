# job-agent

A job-search application that compares vacancies with the user's career history and preferences, explains why they may be interesting, and supports application tracking.

Currently a **local Python and Streamlit prototype for one user**, with JSON file persistence. It has no database or multi-user accounts. The interface remains in Spanish.

## First-version scope

1. **User profile:** personal details, career history and preferences, with optional CV input.
2. **Real vacancy search:** find publications and retrieve their descriptions for analysis.
3. **Explained, prioritized recommendations:** distinguish interest, matches, confirmed gaps and missing information.
4. **A personalized CV for each vacancy:** generate a reviewable, downloadable PDF using confirmed information only.
5. **“He aplicado” registration:** record an application made by the user and the exact CV used, when applicable.
6. **Application tracker:** view and update statuses, notes and next steps.

These six items describe the target scope, not a claim that everything has been implemented or validated. The complementary base CV **does not replace a CV personalized for a vacancy**.

## Current status

### Implemented

- Profile tabs: “Datos personales”, “Trayectoria profesional” and “Preferencias de búsqueda”, with individual and full-profile editing, saving and cancellation.
- Editable and removable work experience, education and projects; confirmed skills and declared language levels.
- Required-field and date validation. Incomplete legacy entries remain available for correction.
- One confirmed skill list shared by search, evaluation and CV generation; explicit acceptance of AI suggestions, duplicate checks, deletion and confirmed merges.
- OpenAI and Tavily search, description retrieval, deduplication and up to five explained recommendations, with inspectable evidence.
- “Mejorar mi perfil”: general questions, answer confirmation and persistence, editing and deletion. “Actualizar recomendaciones” reevaluates existing listings.
- Locally generated base CV PDF, with preview and download. There is currently no draft text editor in the interface.
- Private persistence of profiles, evaluations, available sources and skill decisions; local diagnostics without keys or personal data.

### Pending validation

**The progressive profile-improvement flow has not yet been tested end to end.** Real-use validation must cover questions, confirmed answers, reopening the application and reevaluation with the enriched profile without another web search.

Explanation quality, skill-suggestion relevance, retrieval from different employment sites, and CV preview/download across the browsers used also require ongoing validation.

Automated tests cover rules, persistence and interactions. Mocked services do not establish that the full flow works with real services. Occasional real searches and visual PDF checks with fictional data have been performed. **Implemented does not mean validated end to end.**

### Pending implementation

- Optional CV input for the profile.
- Per-vacancy personalized CV, “He aplicado” registration and tracker, in the order below.
- Later-stage features: database, multi-user accounts, daily searches, application submission and visual CV templates.

## Profile and career history

The profile includes:

- **Personal details:** first name, surname, phone, email and LinkedIn. Contact details alone do not enable search.
- **Work experience:** company, role, dates, responsibilities and optional achievements/tools. Multiple jobs are supported, including past employment.
- **Education:** institution, studies, courses or certifications, dates and optional learning content/projects.
- **Projects:** name, description, personal contribution, tools and an optional URL.
- **Skills and languages:** a single confirmed skill list and declared language levels.
- **Search preferences:** target roles, locations, work arrangements, minimum gross annual salary, preferences, importance and “¿Qué buscas?”. The current employer can optionally be excluded; users with multiple current jobs can choose which employer to exclude.

Each field or block has its own “Guardar” and “Cancelar” editor. Work experience, education and projects have individual entry editors. Saving one block preserves other data; cancelling retains the previous value. Editing and saving do not initiate search or model calls.

Work experience requires a company, role, start date and responsibilities. Education requires an institution, study title and start date. Both require an end date unless ongoing, and reject inconsistent dates. Legacy experience-year ranges are never converted into invented jobs.

Manually added skills are confirmed. AI suggestions become confirmed only when accepted, and their names can be edited before acceptance. Case and whitespace duplicates are prevented; possible equivalents merge only after confirmation. The limit is **10 confirmed skills**, excluding pending suggestions. Any confirmed skill can be removed while its sources remain internally recorded. Discarded or removed skills must not be suggested again from the same evidence.

“Proponer skills” appears in the skill summary and requires saved descriptions of tasks, knowledge or tools. Clicking it explicitly starts the model call. Study titles alone do not establish specific skills. Learning in education, application in projects and professional work are distinguished: completing a course does not establish advanced proficiency or work experience.

## Progressive profile improvement

“Mejorar mi perfil” groups up to three relevant, deduplicated general questions outside vacancy cards. The user may answer or skip them. Before saving an answer, the proposed information is displayed for confirmation.

Confirmed answers enrich the profile, persist between sessions and can be reviewed, edited or removed. Already answered or documented information should not be requested again. This persistence is **stored user information, not model training**.

Questions about the user are separated from vacancy-specific uncertainties, such as undocumented salary, requirements or whether the vacancy remains active. Vacancy questions stay in the corresponding card.

“Actualizar recomendaciones” calls the model to reevaluate existing vacancies using the updated profile and locally stored descriptions, **without another web search or Tavily extraction**. Some legacy results retain only verified excerpts: reevaluation is limited to that evidence and does not fill gaps with assumptions. The complete flow remains pending end-to-end validation.

## Search and recommendations

“Buscar ofertas” is the only trigger for a new search. At least one meaningful saved item in career history or search preferences is sufficient; a target role is not mandatory. Contact details, defaults, empty entries and selectors without an explicit choice are insufficient. Partial profiles can search without inventing missing criteria.

The agent loads `agent_instructions.md`, uses tool calling and limits each search to **ten search/extraction tool calls**. It prioritizes original company publications or their recruitment systems; job boards help discover vacancies. Evaluation requires a retrieved description with responsibilities and requirements, rather than only titles or search snippets. Pages without sufficient evidence are discarded, duplicates removed, and results never invented to reach five.

The interface does not show a 1–10 fit score or a global suitability label. Python retains preference-based ordering using dimensions evaluated by the model with evidence: role relevance, skills, experience, languages, location, work arrangement and salary.

Each vacancy shows company, role, location, URL and explanations of:

- Reasons for interest, separate from qualifications.
- Requirements met and partial matches.
- Confirmed gaps.
- Vacancy information still needing confirmation.

Evidence is available under “Ver detalles”. Declaring a skill does not confirm proficiency or professional experience. “¿Qué buscas?” guides interest without becoming confirmed capability. Missing information is not a failure: it appears as “No documentado” or a specific question. If vacancy activity cannot be confirmed, that uncertainty is stated.

Preferences prioritize opportunities rather than automatically excluding them. Mandatory conditions and additional filters are no longer part of the interface or evaluation flow. Salaries in different currencies are not compared without reliable conversion, and annual pay is not inferred when necessary information is missing.

## Complementary base CV

“Generar CV base” prepares a PDF draft from personal details and confirmed career history for preview and download. There is currently no editable text draft in the interface: corrections require editing the profile and regenerating the PDF.

It excludes salary, locations, work arrangements and search conditions, and never invents achievements, dates, titles or proficiency levels. The initial description may include professional-interest excerpts from “¿Qué buscas?”, identified as aspirations rather than acquired experience. This is the only use of that field in the base CV.

Generation requires first name and surname, a valid email and at least one complete experience, education or project entry. A complete project requires a name, description and personal contribution. Phone and links are optional. Incomplete entries remain in the profile but are omitted from the CV. A blocked CV does not prevent vacancy search.

The PDF is generated locally in memory. It is not yet adapted to a vacancy and does not replace future personalized CV development. Visual templates are deferred.

## Next features to implement

In this order:

1. **Personalized CV:** a “Generar CV” button per vacancy. Generate an adapted PDF solely from confirmed information, without inventing experience, skills, dates or achievements; support review and download.
2. **He aplicado:** record the vacancy, URL, date and application status after the user applies. Associate the exact CV version sent; when multiple versions exist, the user chooses. Allow an external CV or registration without a CV. **This does not submit applications.**
3. **Tracker:** view and update statuses, notes and next steps. Preserve the associated historical CV when the profile changes.

## Later stages

- A database and multi-user accounts with appropriate personal-data storage and access.
- Daily searches for new vacancies.
- Visual CV templates.
- Application submission from the app. Every submission, including automated submissions, requires explicit user approval for that application after reviewing the vacancy and outgoing content. The current prototype neither submits applications nor contacts companies.

## Run the local interface

With `requirements.txt` dependencies installed in `.venv`, run from the repository directory:

```bash
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open the local URL printed by the terminal, usually `http://127.0.0.1:8501`.

Set `OPENAI_API_KEY` and `TAVILY_API_KEY` manually in `.env`. `OPENAI_MODEL` overrides the default `gpt-6-luna`. Searches and skill suggestions use external services; reevaluation uses OpenAI with stored evidence. Base CV generation is local.

Save data before starting an action. Editing and saving do not call external services. Profiles are stored in `user_profile.json`; evaluations, available sources and diagnostics in `.local_data/`, including `.local_data/evaluations.json`. Previous results do not automatically update after profile changes: reevaluate them or start a new search.

### Naming and saved-data compatibility

Python modules, functions and variables use English names; interface text remains Spanish. Examples include `user_profile.py`, `profile_ui.py`, `career_history.py`, `agent.py`, `job_search.py` and `evaluation.py`.

On loading, legacy `perfil.json` and `.datos/` files are moved to their English paths without rewriting their contents. Existing destination files are never overwritten. Legacy JSON field names remain supported through explicit model aliases and the existing profile migration logic, preserving saved information.

## Privacy and secrets

- Never commit API keys, passwords, tokens or `.env`.
- Never commit profiles, real search results, personal descriptions/answers, applications, private notes or CVs, including generated PDFs and external documents.
- Keep `user_profile.json`, `.local_data/`, `.env`, the virtual environment and PDFs excluded through `.gitignore`. Legacy private paths remain excluded too. Review new files before committing them.
- Use fictional data only in repository examples and tests.
- Current persistence is local JSON storage, not an account, synchronization or model training. Searches and reevaluation share the information necessary for the action with configured services.

The prototype is intended for personal local use. A database, multi-user access and application submission belong to later stages.
