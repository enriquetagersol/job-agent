"""Render the floating conversational panel and queue each user message before model processing. Connect conversation tools to local preferences and the existing search flow, preserving history and undo controls."""

import streamlit as st
from shared.local_storage import save_json, search_context
from memory.directed_chat import add_company, remove_company, directed_context


def process_message(message, profile, profile_path, can_search, append_user=True):
    """One native submission creates one conversational turn, never a visibility call."""
    from chat.conversational_agent import converse
    from profiles.user_profile import profile_for_model
    from memory.offer_feedback import load_feedback, effective_priorities, available_batch, effective_profile
    from jobs.evaluation import rank_evaluations, normalize_weights
    from jobs.presentation import explain_listing
    messages = st.session_state.setdefault('chat_messages', [])
    if append_user:
        messages.append({'role': 'user', 'content': message})
    state = load_feedback(profile_path.parent / '.local_data' / 'offer_feedback.json', profile)
    saved = st.session_state.get('saved_results') or {}
    ranked = rank_evaluations(saved.get('evaluaciones', []), normalize_weights(effective_profile(state, profile)))
    available = available_batch(ranked, state, st.session_state.get('hidden_offers', []))
    cards = [{'url': item['oferta'].url, 'role': item['oferta'].role,
              'company': item['oferta'].company, 'location': item['oferta'].location,
              'responsibility': item['oferta'].documented_responsibility,
              'requirement': item['oferta'].documented_requirement,
              'evaluation': item['oferta'].model_dump(),
              'explanations': {k: v for k, v in explain_listing(item['oferta'], separate_user=True, profile=profile).items()
                               if k != 'pendientes'}} for item in available]

    def execute(name, arguments):
        if name == 'get_recommendations':
            return {'ok': True, 'recommendations': cards, 'search_date': saved.get('fecha')}
        current = st.session_state.profile
        if name in ('remember_search_preference', 'forget_search_preference'):
            from memory.conversational_memory import change_preference
            updated, changed = change_preference(current, arguments['preference'], name == 'remember_search_preference')
            save_json(profile_path, updated)
            st.session_state.profile = updated
            if changed:
                st.session_state.chat_memory_undo = {'preference': arguments['preference'], 'action': name, 'message_index': len(messages)}
            return {'ok': True, 'changed': changed, 'preferences': updated['conversation_preferences']}
        if name in ('add_company_interest', 'remove_company_interest'):
            company = arguments['company']
            before = list(current.get('companies_of_interest', []))
            if name == 'add_company_interest':
                updated, changed = add_company(current, company)
            else:
                updated = remove_company(current, company)
                changed = before != updated['companies_of_interest']
            save_json(profile_path, updated)
            st.session_state.profile = updated
            if changed:
                st.session_state.chat_memory_undo = {'company': company, 'action': name, 'message_index': len(messages)}
            return {'ok': True, 'changed': changed, 'companies': updated['companies_of_interest']}
        if name == 'search_jobs':
            if st.session_state.get('search_pending') or st.session_state.get('searching'):
                return {'ok': False, 'error': 'Ya hay una búsqueda en curso.'}
            context = directed_context(search_context(current), arguments['company'].strip())
            location = arguments['location'].strip()
            if location:
                context.setdefault('directed_search', {})['location'] = location
                context['perfil']['preferencias']['search_location'] = location
            from shared.validation import has_search_information
            if not has_search_information(context['perfil']):
                return {'ok': False, 'error': 'Falta información para orientar la búsqueda.'}
            st.session_state.pending_search_context = context
            st.session_state.search_pending = True
            return {'ok': True, 'status': 'queued', 'company': arguments['company'], 'location': location,
                    'results_location': 'main_cards'}
        raise ValueError('Acción no disponible.')

    try:
        response = converse(messages, {'profile': profile_for_model(profile),
            'effective_priorities': effective_priorities(state), 'available_recommendations': cards}, execute)
    except Exception as error:
        from shared.diagnostics import record_chat_event
        record_chat_event('other', 'conversation_error', type(error).__name__)
        # Keep profile changes and user text, without exposing keys or API payloads.
        response = 'No he podido completar la respuesta. Las acciones guardadas se conservan; puedes revisarlas en tu perfil.'
    messages.append({'role': 'assistant', 'content': response})


CHAT_STYLE = """
<style>
.st-key-floating_chat_launcher {
 position: fixed; right: max(20px, env(safe-area-inset-right));
 bottom: max(20px, env(safe-area-inset-bottom)); z-index: 999990; width: 58px;
}
.st-key-floating_chat_launcher button {
 border-radius: 50%; width: 58px; height: 58px; font-size: 25px;
 box-shadow: 0 4px 18px rgba(0,0,0,.25);
}
.st-key-floating_chat_panel {
 position: fixed; right: max(20px, env(safe-area-inset-right));
 bottom: max(20px, env(safe-area-inset-bottom)); z-index: 999991;
 width: min(420px, calc(100vw - 40px)); max-height: calc(100dvh - 90px);
 padding: 16px; border-radius: 18px; border: 1px solid rgba(128,128,128,.35);
 background: var(--background-color, #fff); box-shadow: 0 8px 32px rgba(0,0,0,.25);
 overflow-y: auto; overscroll-behavior: contain;
}
.st-key-floating_chat_history {
 max-height: min(320px, calc(100dvh - 270px)); overflow-y: auto;
}
.st-key-floating_chat_history [data-testid="stChatMessage"] { padding: 10px; }
.st-key-floating_chat_history [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
 background: rgba(80,130,230,.13); margin-left: 18px;
}
.st-key-floating_chat_history [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
 background: rgba(128,128,128,.08); margin-right: 18px;
}
.st-key-floating_chat_header [data-testid="stHorizontalBlock"],
.st-key-floating_chat_memory_actions [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; }
.st-key-floating_chat_header [data-testid="stColumn"],
.st-key-floating_chat_memory_actions [data-testid="stColumn"] { min-width: 0 !important; width: auto !important; }
.st-key-floating_chat_header [data-testid="stColumn"]:last-child { flex: 0 0 40px !important; }
.st-key-floating_chat_header button { width: 36px; height: 36px; padding: 0; }
.st-key-floating_chat_memory_actions button { min-height: 24px; padding: 0 4px; font-size: 12px; }
.st-key-floating_chat_panel [data-testid="stChatInput"] { min-width: 0; }
@media (max-width: 600px) {
 .st-key-floating_chat_panel {
  right: max(8px, env(safe-area-inset-right)); bottom: max(8px, env(safe-area-inset-bottom));
  width: calc(100vw - 16px); max-height: calc(100dvh - 64px); padding: 12px;
 }
 .st-key-floating_chat_history { max-height: calc(100dvh - 250px); }
}
</style>
"""


def set_chat_open(value):
    st.session_state.chat_open = value


def queue_chat_message():
    message = st.session_state.get('employment_chat_input')
    if message and not st.session_state.get('pending_chat_message'):
        st.session_state.setdefault('chat_messages', []).append({'role': 'user', 'content': message})
        st.session_state.pending_chat_message = message


def render_chat(profile, profile_path, can_search, busy=False):
    st.markdown(CHAT_STYLE, unsafe_allow_html=True)
    if not st.session_state.get('chat_open', False):
        with st.container(key='floating_chat_launcher'):
            st.button('🤖', key='open_employment_chat', help='Abrir tu asistente de empleo',
                      on_click=set_chat_open, args=(True,))
    else:
        with st.container(key='floating_chat_panel'):
            with st.container(key='floating_chat_header'):
                title, close = st.columns([5, 1])
                title.markdown('**Tu asistente de empleo**')
                close.button('✕', key='close_employment_chat', help='Cerrar chat',
                             on_click=set_chat_open, args=(False,))
            undo = st.session_state.get('chat_memory_undo')
            messages = st.session_state.get('chat_messages', [])
            pending = st.session_state.get('pending_chat_message')
            with st.container(height=320, key='floating_chat_history'):
                for index, entry in enumerate(messages):
                    with st.chat_message(entry['role']):
                        st.write(entry['content'])
                        if undo and entry['role'] == 'assistant' and index == undo.get('message_index', len(messages) - 1):
                            with st.container(key='floating_chat_memory_actions'):
                                left, right = st.columns([4, 1])
                                if left.button('Deshacer', key='undo_chat_memory', type='tertiary'):
                                    current = st.session_state.profile
                                    if 'preference' in undo:
                                        from memory.conversational_memory import change_preference
                                        updated, _ = change_preference(current, undo['preference'], undo['action'] == 'forget_search_preference')
                                    elif undo['action'] == 'add_company_interest':
                                        updated = remove_company(current, undo['company'])
                                    else:
                                        updated, _ = add_company(current, undo['company'])
                                    save_json(profile_path, updated)
                                    st.session_state.profile = updated
                                    st.session_state.chat_memory_undo = None
                                    messages.append({'role': 'assistant', 'content': 'He deshecho el cambio en tus preferencias.' if 'preference' in undo else 'He deshecho el cambio en tus empresas de interés.'})
                                    st.rerun()
                                if right.button('×', key='dismiss_chat_memory', type='tertiary', help='Ocultar opción de deshacer'):
                                    st.session_state.chat_memory_undo = None
                                    st.rerun()
                if busy or pending:
                    st.caption('Escribiendo…')
            st.chat_input('Escribe tu petición…', key='employment_chat_input', disabled=busy or bool(pending),
                          on_submit=queue_chat_message)
            if pending and not busy:
                # Consume before the model call: rerenders cannot resubmit a turn.
                st.session_state.pending_chat_message = None
                process_message(pending, profile, profile_path, can_search, append_user=False)
                st.rerun()
