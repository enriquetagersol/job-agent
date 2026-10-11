# Offline verification and manual checks

## Automated checks

Run the suite from the repository directory:

```bash
.venv/bin/python run_tests.py
```

The runner blocks socket connections, DNS resolution and HTTPX transports. Any unexpected real network request fails the suite. OpenAI/Tavily responses used by service tests are simulated; no API requests or credits are consumed. Tests use fictional profiles and temporary storage, not the user's saved files.

The current checks establish these specific properties:

| Area | Automated evidence | Still requires browser verification |
| --- | --- | --- |
| Profile and confirmed answers | JSON persistence, new AppTest sessions restoring saved values, confirmation before writes, answer editing/deletion and suppression of answered questions | Real tab refresh/reopening, readable summaries and confirmation controls |
| Offer actions | Independent saved/interested/discarded flags, reasons/dates, undo and persistence across new AppTest sessions | Lists and card controls behaving consistently in the actual browser |
| Adaptive priorities | Three explicit global signals from distinct vacancies, duplicate publications not counted twice, excluded reasons/scopes, persisted adjustments, undo without immediate repetition and manual overrides | Notice clarity, effective/declared priorities shown correctly and controls understandable |
| Replacement batches | Up to five unique offers, smaller subsequent batches, exhaustion and return to previous results, with no search/reevaluation/suggestion calls | No stale or duplicated cards while navigating in the browser |
| Base CV | A generated PDF, literal confirmed data, required-field checks and byte-for-byte unchanged profile storage | PDF rendering, preview visibility and download contents in the browser |

AppTest executes Streamlit scripts and widget interactions without a browser. These tests cover local integration paths as well as unit rules, but **do not validate the complete user-facing flow end to end**. Mocked service tests also do not validate real search quality, live page extraction or real-model explanations. The progressive profile-improvement flow remains pending real-browser end-to-end validation.

## Review findings

The additional replacement-batch test exposed stale earlier cards in Streamlit's element tree when switching from five offers to a smaller batch. Batch navigation now updates session state in button callbacks before cards render. The regression test checks the actual displayed headings without a compensating extra rerun.

Feedback UI tests reuse setup helpers without inheriting unrelated test methods, avoiding six duplicate test executions. Existing CV coverage already checks that generating the PDF does not alter profile bytes; no duplicate CV test was added.

## Short manual checklist

Use existing saved results to avoid API calls. Do not click “Buscar ofertas”, “Buscar más ofertas”, “Actualizar recomendaciones” or “Proponer skills” during this offline manual check. Some checks require enough stored vacancies/questions and a complete CV profile; if unavailable, mark that check pending rather than claiming success.

1. **Profile:** edit a field, save and reopen/refresh. Confirm the value persists. Propose an answer in “Mejorar mi perfil”; confirm it is not saved before approval. Confirm, reopen, edit and delete it; check that persisted answers are not asked again.
2. **Offer actions:** save a vacancy, mark interest and discard it with an optional reason. Reopen the app and inspect the three lists. Undo each action independently and reopen again. Confirm no action means an application was submitted.
3. **Priorities:** with declared importance Baja or Media, discard three distinct vacancies for the same eligible reason using “Este criterio pesa más para mí”. Inspect the notice and effective priority. Undo an adjustment or a contributing discard; check it does not immediately repeat. Manually save the affected preference and verify that the manual value prevails.
4. **Other offers:** navigate to remaining batches, checking no repeated/stale cards or discarded vacancies. At exhaustion, confirm that an explicit search button is offered but no search starts automatically. Return to previous results.
5. **CV:** generate a base CV, inspect its preview and download the PDF. Check names, dates and content; verify the profile is unchanged after generation and reopening. Browser preview/download are not established by the automated PDF-header assertion alone.

Record each manual check separately as passed, failed or pending. Passing a unit or AppTest check alone is not a manual pass.

## Directed chat: additional manual checks (pending)

The offline suite simulates directed searches, persists company preferences, tests undo/removal and checks that results are cards rather than chat content. These are not real-browser or live-company-search validation.

- Send “Hola” and “Me interesa trabajar en [company]”: no search should start. Verify the notification, undo, list removal and persistence after reopening.
- Send an ambiguous “Quiero trabajar en esta empresa; busca puestos”: without a prior explicit company, the chat should request a name rather than search.
- An explicit “Busca ofertas en [company]” uses external APIs in the live app; check this later, separately from offline verification. Confirm it does not add lasting interest and that results remain in cards.
- After a directed search, use the ordinary search button: the target company must no longer constrain it. Check the existing feedback and adaptive-priority controls still work.
- Review explanations against the actual profile and retrieved descriptions: task-based interest, separate qualifications, confirmed gaps only, general user questions outside cards and vacancy questions retained privately. Inspect “Ver detalles” for evidence.

## Floating chat presentation

Offline interface tests cover opening/closing without search calls, preserved history across rerenders and exactly one search per submission. Check the overlay visually on desktop and mobile, including the on-screen keyboard, long-history scrolling, Enter and the send button. These visual checks are separate from automated logic validation.

## Simplified preference memory

Offline interface checks cover the shared manual/chat company list, normalized duplicate prevention, persistence and removal without API calls. They also cover current priorities in normal fields, notice dismissal without reverting learned weights, and manual editing after an adjustment. Browser checks remain pending for tab placement and notice usability. The learning history is retained internally.

## LLM conversation (offline contracts; live quality pending)

Simulated Responses API messages cover natural-language interest, typo correction, company add/remove, contextual affirmation with a temporary Madrid restriction, read-only comparisons and ambiguity, strict arguments, unsupported actions, tool failures, duplicate suppression, undo and no model calls on opening. These tests supply the model decision: they validate Python integration, not real LLM comprehension or factual reliability.

Manual checks with real services remain pending: express company interest using varied phrasing, accept the offered search with a temporary location, verify the global profile is unchanged, compare retrieved cards, request removal or use undo, and test ambiguous references. Failed tools must not be reported as successful. Ordinary conversation may use OpenAI but must not start Tavily without a requested search. Verify search completion in main cards, and confirm no API calls from opening/closing alone.
