"""Test conversational agent contracts with local fixtures and simulated services. Exercise regression behavior without live APIs; unit and Streamlit simulations do not establish complete browser-flow validation."""

import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from chat.conversational_agent import converse


def response(*calls, text=''):
    return SimpleNamespace(output=list(calls), output_text=text)


def call(name, arguments, identifier='1'):
    return SimpleNamespace(type='function_call', name=name, arguments=json.dumps(arguments), call_id=identifier)


class ConversationTests(unittest.TestCase):
    def test_natural_interest_then_contextual_affirmation(self):
        history = [{'role': 'user', 'content': 'Me interesaría trabajar en Salesfrce'}]
        client = Mock()
        execute = Mock(return_value={'ok': True, 'companies': ['Salesforce']})
        client.responses.create.side_effect = [response(call('add_company_interest',
            {'company': 'Salesforce', 'user_evidence': history[-1]['content']})),
            response(text='Lo tendré en cuenta. ¿Quieres que busque puestos en Salesforce que encajen con tu perfil?')]
        reply = converse(history, {'profile': {}}, execute, client)
        self.assertEqual(execute.call_args.args[1]['company'], 'Salesforce')
        history.extend([{'role': 'assistant', 'content': reply}, {'role': 'user', 'content': 'Sí, pero solo en Madrid'}])
        client.responses.create.side_effect = [response(call('search_jobs', {'company': 'Salesforce',
            'location': 'Madrid', 'user_evidence': 'Sí, pero solo en Madrid'})), response(text='Buscaré solo en Madrid.')]
        converse(history, {'profile': {}}, execute, client)
        self.assertEqual(execute.call_args.args[1]['location'], 'Madrid')
        self.assertIn(reply, str(client.responses.create.call_args.kwargs['input']))

    def test_ambiguity_and_comparison_are_read_only(self):
        client = Mock()
        execute = Mock(return_value={'ok': True, 'recommendations': [{'role': 'Analista'}]})
        client.responses.create.side_effect = [response(text='¿Qué empresa tienes en mente?')]
        converse([{'role': 'user', 'content': 'Esa me interesa'}], {}, execute, client)
        execute.assert_not_called()
        client.responses.create.side_effect = [response(call('get_recommendations', {})), response(text='Comparando las funciones documentadas…')]
        context = {'profile': {'skills': ['Python']}}
        before = copy.deepcopy(context)
        converse([{'role': 'user', 'content': '¿Cuál de estas ofertas se acerca más a lo que quiero hacer?'}], context, execute, client)
        execute.assert_called_once_with('get_recommendations', {})
        self.assertEqual(context, before)

    def test_invalid_actions_and_tool_failure_are_not_success(self):
        client = Mock()
        execute = Mock(side_effect=OSError('private error'))
        client.responses.create.side_effect = [response(call('send_application', {}),
            call('add_company_interest', {'company': '   ', 'user_evidence': 'unrelated text'}, '2'),
            call('remove_company_interest', {'company': 'Acme', 'user_evidence': 'Quita Acme'}, '3')),
            response(text='No se pudo guardar el cambio.')]
        reply = converse([{'role': 'user', 'content': 'Quita Acme'}], {}, execute, client)
        execute.assert_called_once()
        outputs = [item for item in client.responses.create.call_args.kwargs['input'] if isinstance(item, dict) and item.get('type') == 'function_call_output']
        self.assertTrue(all(not json.loads(item['output'])['ok'] for item in outputs))
        self.assertNotIn('private error', str(outputs))
        self.assertIn('No se pudo', reply)

    def test_repeated_calls_execute_once_and_context_is_private_data(self):
        client = Mock()
        execute = Mock(return_value={'ok': True, 'status': 'queued'})
        args = {'company': 'Acme', 'location': '', 'user_evidence': 'Busca en Acme'}
        client.responses.create.side_effect = [response(call('search_jobs', args)),
            response(call('search_jobs', args, '2')), response(text='La búsqueda está en curso.')]
        converse([{'role': 'user', 'content': 'Busca en Acme'}], {}, execute, client)
        execute.assert_called_once()
        self.assertFalse(client.responses.create.call_args.kwargs['store'])

    def test_temporary_location_is_enforced_and_unknowns_are_excluded(self):
        from jobs.agent import filter_directed_listings
        from tests.test_interface import sample_listing
        first = sample_listing(url='https://example.test/1')
        first.company = 'Salesforce'
        other = sample_listing(url='https://example.test/2')
        other.company = 'Salesforce'
        other.location = 'Barcelona'
        unknown = sample_listing(url='https://example.test/3')
        unknown.company = 'Salesforce'
        unknown.location = 'No documentado'
        wrong_company = sample_listing(url='https://example.test/4')
        self.assertEqual(filter_directed_listings([first, other, unknown, wrong_company],
            {'company': 'Salesforce', 'location': 'Madrid'}), [first])
        self.assertEqual(len(filter_directed_listings([first, other, unknown, wrong_company], {})), 4)

    def test_memory_actions_do_not_require_literal_quotes_or_command_templates(self):
        from chat.conversational_agent import validate_action, TOOLS
        for message in ('me interesa salesforce', 'me interesaria trabajar en salesforce',
                        'Me interesaría incorporarme a esa empresa', 'sí, añádela'):
            self.assertEqual(validate_action('add_company_interest',
                json.dumps({'company': 'Salesforce'}), message)['company'], 'Salesforce')
        self.assertEqual(validate_action('add_company_interest', json.dumps({
            'company': 'Salesforce', 'user_evidence': 'Me interesaría trabajar en Salesforce'}),
            'me interesaria trabajar en salesforce')['company'], 'Salesforce')
        self.assertTrue(all('user_evidence' not in tool['parameters']['properties'] for tool in TOOLS))

    def test_chat_diagnostics_never_store_private_exception_text(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from shared.diagnostics import record_chat_event
        with tempfile.TemporaryDirectory() as directory:
            with patch('shared.diagnostics.BASE_DIR', Path(directory)):
                record_chat_event('add_company_interest', 'persistence_error', 'PermissionError')
                record_chat_event('secret company', 'private profile', 'password')
                text = (Path(directory) / '.local_data' / 'chat_diagnostics.json').read_text()
        self.assertIn('persistence_error', text)
        self.assertNotIn('secret company', text)
        self.assertNotIn('private profile', text)
        self.assertNotIn('password', text)
