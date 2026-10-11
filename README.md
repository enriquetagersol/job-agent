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
- OpenAI and Tavily search, description retrieval, deduplication and batches of up to five explained recommendations, with inspectable evidence.
- Independent saved/discarded offer actions, reversible discard reasons, local replacement batches, and explicit adaptive priority rules with persistent history and user controls.
- LLM conversational chat with explicit search requests, persistent company interests, undo/removal and results outside the conversation.
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

Only explicit search buttons (“Buscar ofertas” or “Buscar más ofertas”) or an explicit chat search request trigger a new search. At least one meaningful saved item in career history or search preferences is sufficient; a target role is not mandatory. Contact details, defaults, empty entries and selectors without an explicit choice are insufficient. Partial profiles can search without inventing missing criteria.

The agent loads `agent_instructions.md`, uses tool calling and limits each search to **ten search/extraction tool calls**. It prioritizes original company publications or their recruitment systems; job boards help discover vacancies. Evaluation requires a retrieved description with responsibilities and requirements, rather than only titles or search snippets. Pages without sufficient evidence are discarded, duplicates removed, and results never invented to reach five.

The interface does not show a 1–10 fit score or a global suitability label. Python retains preference-based ordering using dimensions evaluated by the model with evidence: role relevance, skills, experience, languages, location, work arrangement and salary.

Each vacancy shows company, role, location, URL and explanations of:

- Reasons for interest, separate from qualifications.
- Requirements met and partial matches.
- Confirmed gaps.
- Vacancy information still needing confirmation.

Evidence is available under “Ver detalles”. Declaring a skill does not confirm proficiency or professional experience. “¿Qué buscas?” guides interest without becoming confirmed capability. Missing information is not a failure: it appears as “No documentado” or an internal vacancy question; user questions appear in “Mejorar mi perfil”. If vacancy activity cannot be confirmed, that uncertainty is stated.

Preferences prioritize opportunities rather than automatically excluding them. Mandatory conditions and additional filters are no longer part of the interface or evaluation flow. Salaries in different currencies are not compared without reliable conversion, and annual pay is not inferred when necessary information is missing.

## Directed-search chat and company interests

The chat opens from a circular chatbot button fixed at the bottom right. Its overlay panel includes a scrollable conversation, a close button and an inline input supporting Enter or the send button. Opening and closing preserve messages within the Streamlit session and never trigger API calls. Submissions use Streamlit’s native chat input; rerenders do not resend them. The panel adapts to narrow screens, and “Escribiendo…” indicates processing. Job cards remain on the main page.

The Spanish chat now uses the configured OpenAI model through the Responses API for natural-language understanding and replies. The old regular-expression command parser has been removed. Every submitted message can consume API calls; opening, closing or rerendering the panel does not. The model sees the session conversation, confirmed career profile (without the contact-data section), effective priorities and current available cards with saved evaluations. It can discuss goals, explain recommendations, compare available opportunities and ask clarifying questions without initiating a web search.

Six tool-calling functions are available: `get_recommendations`, `search_jobs`, `add_company_interest`, `remove_company_interest`, `remember_search_preference` and `forget_search_preference`. Python validates strict typed arguments and a nonempty user turn; the LLM resolves intent and ambiguity from the conversation, executes only known actions, returns success/failure to the model, and suppresses repeated identical actions within a turn. Search is queued through the existing search/evaluation pipeline, retaining its ten-call Tavily limit; a queued search is not reported as completed. Tool schemas no longer require a literal quotation: accents, paraphrases and contextual affirmations do not fail a text-equality check. Local `chat_diagnostics.json` retains only allowlisted tool names, result codes and exception categories, never messages, profiles, arguments or keys. The conversational loop is bounded to six model responses. No application, contact, CV adaptation or arbitrary profile-editing tools are exposed. Implementation follows the [official function-calling guide](https://developers.openai.com/api/docs/guides/function-calling).

An explicit lasting interest such as “Me interesaría trabajar en Salesforce” can be saved by the corresponding tool. The assistant can then offer a search; “Sí, pero solo en Madrid” is interpreted using the previous conversation. Company and location restrictions apply only to that request. Python excludes results whose documented employer/location do not match those temporary constraints; unknown locations are not assumed compatible. Ordinary searches remain unrestricted by remembered company interests. A one-off search does not itself authorize a lasting company preference, and ambiguous intent must prompt clarification.

The profile’s “Empresas de interés” controls and chat tools share the same persistent, case/whitespace-deduplicated list. A compact undo action is attached to the relevant assistant message; it adds no separate notice panel and leaves the composer in place. Undo also adds a conversation update so subsequent replies know the preference was reverted. After recording interest, the assistant is instructed to offer a relevant next conversational step without starting a search automatically. Conversation history stays in the Streamlit session, separately from persistent profile facts and confirmed answers. Undo affects only the changed company and preserves unrelated profile data. No conversation statement automatically establishes professional experience or skills.

Evaluation prompts now ask for concise, task-based connections with aspirations, career history and preferences, separately from demonstrated qualifications. Python preserves a responsibility-grounded reason when a title matches, instead of overwriting it with a generic title comparison. Interest may use documented career activities, but a title or aspiration never establishes professional proficiency. Explicit company-interest explanations remain separate from qualification claims. Legacy technical comparison blocks and verbatim evidence-only reasons are kept out of the main explanation; evidence remains available under “Ver detalles”. Missing user information is routed to “Mejorar mi perfil”, while vacancy uncertainties stay private in the saved evaluations.

Retrieved descriptions and company names are passed as data, not instructions. Evaluation prompts explicitly reject embedded instructions or requests to take actions. This boundary is covered by simulated payload tests; resistance of a real model to all prompt-injection attempts is not established by these tests.

### Validation status

**Implemented and checked offline:** simulated natural-language tool decisions and contextual follow-ups, one-off versus durable preferences, duplicate prevention, persistence/undo/removal, directed search through simulated tool responses, employer filtering, ordinary-search scope reset, cards outside chat, and preservation of grounded explanations. All tests run with network access blocked; no real API calls were made for this feature.

**Pending real-browser and real-service validation:** real-model understanding of equivalent expressions, typos and ambiguity, complete conversational usability, company-name aliases, original posting retrieval for specific employers, explanation quality and robustness against malicious page content. Existing saved explanations are not regenerated automatically; new searches or explicit “Actualizar recomendaciones” use the revised evaluation instructions. Neither unit tests nor AppTest simulations establish these complete flows as validated end to end.

## Offer feedback and adaptive priorities

Each recommendation has independent “Guardar” and “Descartar” actions. Saving never means the user applied. Both actions are reversible; saved and discarded titles can be consulted in their dedicated tabs, including after reopening the app or replacing search results. Legacy interest data remains stored internally.

Discarding optionally records location, work arrangement, salary, responsibilities, company, seniority or another reason, a free-text comment, and the date with the evaluated vacancy. “Descartar sin indicar motivo” requires no explanation. A discarded publication is excluded from future recommendation batches until its discard is undone. This never excludes its entire company or role category. Vacancy identity reuses the evaluator’s exact normalized company/role/location grouping when all three are documented, including publications with different URLs. Otherwise it uses a canonical URL with tracking parameters and fragments removed, retaining vacancy identifiers in query parameters. This exact grouping is not a company/category exclusion. Identity remains a limitation: distinct openings with identical company, title and location may be grouped, while aliases with different undocumented details cannot always be recognized.

Declared priorities remain in the profile. Effective priorities and feedback history are stored separately in the private `.local_data/offer_feedback.json` file. No profile facts, accepted destinations, work arrangements or minimum salary are changed by the rule.

The provisional deterministic rule is:

- **Three distinct discarded vacancies** with the same explicit location, work-arrangement or salary reason can raise that criterion one level: Baja → Media → Alta.
- Only the explicit option “Este criterio pesa más para mí” counts. “Esta opción no me interesa”, missing reasons, other reasons and free-text comments do not create global-priority evidence.
- Each signal is used once. Already used signals and repeated undo/discard cycles do not produce fresh evidence. No automatic decreases occur. An unspecified declared importance uses the existing Media default.
- A new adjustment or a manual edit starts a fresh evidence period for that criterion. Individual preference saves override learned adjustments even if the declared importance is unchanged; full-profile saves reset only preference groups that changed. Unrelated profile edits preserve learned priorities.
- The default threshold is `SIGNAL_THRESHOLD = 3` in `offer_feedback.py`; it initializes the persisted `threshold` setting. Changing the setting in an existing private feedback file affects later actions only. It must be a positive integer. This is a provisional rule, not statistical inference or model training.

After an adjustment, a brief dismissible notice offers “Deshacer”. Current priorities appear in the normal preference summaries and editors; manual edits override previous adjustments. Dismissing a notice persists without undoing the adjustment. Memory, separate declared/effective priorities and audit history remain internal; no permanent learning panel or technical labels are shown. Unrelated full-profile edits preserve adjusted priorities.

Undoing a discard deactivates its signal and withdraws an active adjustment that depended on it. Undoing an adjustment does not reactivate consumed signals. Saved and interested actions do not affect weights in this implementation.

“Mostrar otras ofertas” uses remaining locally evaluated candidates, excludes discarded vacancies and avoids repeated publications within the current batch sequence. When none remain, “Buscar más ofertas” offers an explicit external search; discarding never initiates one. Fewer than five valid candidates are shown as-is. Users can return to previous non-discarded batches. Older stored results may contain fewer candidates, so replacing offers cannot provide unevaluated vacancies without an explicit new search.

Offline automated tests cover persistence, deduplication, batch replacement, explicit signal scope, threshold changes, ranking, manual overrides, correction and undo. Streamlit interaction tests use simulated search responses to verify feedback does not call APIs. Real-service end-to-end validation of this new flow remains pending.

To run the offline checks:

```bash
.venv/bin/python run_tests.py
```

The offline runner explicitly blocks network access. See [TESTING.md](TESTING.md) for the coverage boundaries, the replacement-batch regression fix, and the manual browser checklist. Automated unit/AppTest success is not an end-to-end validation claim.

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

Save data before starting an action. Editing and saving do not call external services. Profiles are stored in `user_profile.json`; evaluations, available sources and diagnostics in `.local_data/`, including `.local_data/evaluations.json` and `.local_data/offer_feedback.json`. Previous results do not automatically update after profile changes: reevaluate them or start a new search.

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

## Private vacancy follow-up topics

Recommendation cards show interest, accredited requirements, partial matches and confirmed gaps. Vacancy questions and unknown-information notices are not shown in cards or replaced with another visible alert. User questions remain exclusively in “Mejorar mi perfil”; vacancy uncertainties never become user profile facts.

Unknown criteria and their evidence remain in the saved evaluation; missing information is neither fulfillment nor a confirmed mismatch. Evaluation saves also rebuild a private `vacancy_follow_up` map by listing URL, containing unknown vacancy criteria and questions for future recruiter conversations. Existing evaluations remain compatible and retain their original unknowns; this extra map is built when evaluations are next saved. New verified evidence can update evaluations through the existing evaluation flow, refreshing these topics without retaining stale unknowns. No automatic monitoring, application records, recruiter messages or tracker flow is implemented by this preparation.

Offline checks verify hidden vacancy questions, preserved unknown assessments and separation from user questions. Live retrieval and the future application/tracker workflow remain unvalidated.

## Conversational preference memory and immediate messages

Native chat submission queues and displays the user message before any model call. The pending turn is consumed once; the input is disabled and “Escribiendo…” appears while processing. Opening, closing and rerendering never resubmit a completed turn.

The model can remember or forget clearly expressed lasting search preferences through validated tools. These notes persist in the private profile's `conversation_preferences` list, feed later search/evaluation contexts and are separate from confirmed professional facts and session conversation history. A temporary request does not become lasting memory; ambiguous intent requires clarification. Notes are preferences, not proof of skills or experience, and do not enter the CV. Manual profile fields take precedence and notes do not automatically become hard filters or alter numerical ranking weights. Users can undo changes in the chat or review and remove notes under search preferences; full-profile editing can add/remove them. This is stored preference memory, not model training.

Offline tests cover message-before-call ordering, exactly-once submission, persisted notes, undo, session reopening and future search context without changes to confirmed career data. Real-model inference of permanence, conflicts and recommendation quality remains pending live validation.

## Saved and discarded offer lists

A “Guardadas y descartadas” tab contains separate “Guardadas” and “Descartadas” lists. Each entry shows only its clickable job title. Clicking opens a native Streamlit dialog with the same recommendation summary, evidence and save/discard controls as the search cards. The dialog has a top-right close cross and opening/closing uses local evaluations without API calls. Saved offers are bookmarks, not submitted applications.

The “Me interesa” action and its list have been removed from the interface. Existing interest flags/history remain in private feedback storage for compatibility; no old data is deleted. Saving, discarding, reasons, undo and adaptive priorities continue to work. No application submission or tracker functionality is added.
