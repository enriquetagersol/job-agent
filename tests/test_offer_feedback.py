"""Test offer feedback contracts with local fixtures and simulated services. Exercise regression behavior without live APIs; unit and Streamlit simulations do not establish complete browser-flow validation."""

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from shared import local_storage
from shared.local_storage import save_json
from memory.offer_feedback import (load_feedback, set_offer_action, effective_priorities, effective_profile,
    undo_adjustment, sync_manual_priorities, correct_priority, reset_criterion, available_batch, vacancy_id)
from jobs.evaluation import normalize_weights, rank_evaluations
from profiles.user_profile import migrate_profile
from tests.test_interface import sample_listing
import tests.test_interface as fixtures
class FeedbackRuleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'offer_feedback.json'
        self.profile = migrate_profile({})
        self.profile['importancia_ubicacion'] = 'Baja'
        self.state = load_feedback(self.path, self.profile)

    def tearDown(self):
        self.directory.cleanup()

    def listing(self, number):
        return sample_listing(role='Role ' + str(number), url='https://example.test/jobs/' + str(number)).model_dump()

    def discard(self, number, **kwargs):
        set_offer_action(self.state, self.listing(number), 'discarded', **kwargs)

    def test_actions_independent_and_persistent(self):
        listing = self.listing(1)
        set_offer_action(self.state, listing, 'saved')
        set_offer_action(self.state, listing, 'interested')
        self.discard(1, reason='company', text='A specific employer')
        save_json(self.path, self.state)
        restored = load_feedback(self.path, self.profile)
        record = restored['offers'][vacancy_id(listing)]
        self.assertTrue(record['saved'] and record['interested'] and record['discarded'])
        self.assertEqual(record['text'], 'A specific employer')
        self.assertTrue(record['discarded_date'])
        set_offer_action(restored, listing, 'saved', False)
        self.assertTrue(restored['offers'][vacancy_id(listing)]['interested'])
        self.assertNotIn('applied', record)

    def test_only_three_distinct_explicit_global_signals_count(self):
        for i in range(1, 4):
            self.discard(i, reason='location', scope='global')
        self.assertEqual(effective_priorities(self.state)['location'], 'Media')
        self.assertEqual(self.profile['importancia_ubicacion'], 'Baja')
        self.assertEqual(len(self.state['adjustments']), 1)
        self.assertTrue(all(s['consumed'] for s in self.state['signals']))
        self.discard(3, reason='location', scope='global')
        for i in range(4, 7):
            self.discard(i, reason='location', scope='global')
        self.assertEqual(effective_priorities(self.state)['location'], 'Alta')
        for i in range(7, 10):
            self.discard(i, reason='location', scope='global')
        self.assertEqual(len(self.state['adjustments']), 2)

    def test_specific_none_and_text_do_not_adjust(self):
        for i in range(1, 4):
            self.discard(i, reason='location', scope='specific')
        for i in range(4, 7):
            self.discard(i, text='Salary matters more')
        for i in range(7, 10):
            self.discard(i, reason='company', scope='global')
        self.assertEqual(self.state['adjustments'], [])

    def test_undo_discard_withdraws_learning_and_undo_adjustment_cannot_repeat(self):
        for i in range(1, 4):
            self.discard(i, reason='location', scope='global')
        set_offer_action(self.state, self.listing(3), 'discarded', False)
        self.assertEqual(effective_priorities(self.state)['location'], 'Baja')
        self.discard(3, reason='location', scope='global')
        self.assertEqual(effective_priorities(self.state)['location'], 'Baja')
        for i in range(4, 7):
            self.discard(i, reason='location', scope='global')
        undo_adjustment(self.state, self.state['adjustments'][-1]['id'])
        self.discard(7, reason='location', scope='global')
        self.assertEqual(effective_priorities(self.state)['location'], 'Baja')

    def test_manual_override_and_correction_preserve_profile(self):
        original = copy.deepcopy(self.profile)
        for i in range(1, 4):
            self.discard(i, reason='location', scope='global')
        sync_manual_priorities(self.state, self.profile, edited=('location',))
        self.assertEqual(effective_priorities(self.state)['location'], 'Baja')
        correct_priority(self.state, 'salary', 'Alta')
        self.assertEqual(effective_priorities(self.state)['salary'], 'Alta')
        reset_criterion(self.state, 'salary')
        self.assertEqual(effective_priorities(self.state)['salary'], 'Media')
        self.assertEqual(original, self.profile)
        save_json(self.path, self.state)
        self.profile['importancia_ubicacion'] = 'Alta'
        self.assertEqual(effective_priorities(load_feedback(self.path, self.profile))['location'], 'Alta')

    def test_manual_save_resets_even_when_declared_value_unchanged(self):
        root = Path(self.directory.name)
        path = root / '.local_data' / 'offer_feedback.json'
        for i in range(1, 4):
            self.discard(i, reason='location', scope='global')
        save_json(path, self.state)
        with patch.object(local_storage, 'PROFILE_FILE', root / 'user_profile.json'):
            save_json(local_storage.PROFILE_FILE, self.profile, manual_priorities=('location',))
        self.assertEqual(effective_priorities(load_feedback(path, self.profile))['location'], 'Baja')

    def test_batch_deduplication_replacements_and_reordering(self):
        listings = [sample_listing(role='Role '+str(i), url='https://example.test/'+str(i),
                    points=[0, 0, 0, 0, 2 if i==0 else 0, 0 if i==0 else 2, 0]).model_dump() for i in range(7)]
        ranked = rank_evaluations(listings + [listings[0]], normalize_weights(self.profile))
        first = available_batch(ranked, self.state)
        self.assertEqual(len(first), 5)
        hidden = [vacancy_id(item['oferta'].model_dump()) for item in first]
        self.assertEqual(len(available_batch(ranked, self.state, hidden)), 2)
        set_offer_action(self.state, first[0]['oferta'].model_dump(), 'discarded')
        self.assertEqual(len(available_batch(ranked, self.state)), 5)
        alternate = first[0]['oferta'].model_dump()
        alternate['enlace'] = 'https://another.test/original'
        self.assertEqual(vacancy_id(alternate), vacancy_id(first[0]['oferta'].model_dump()))
        self.assertEqual(vacancy_id({'enlace': 'https://example.test/a?utm_source=x#top'}),
                         vacancy_id({'enlace': 'https://example.test/a'}))
        for i in range(10, 13):
            self.discard(i, reason='location', scope='global')
        updated = rank_evaluations(listings, normalize_weights(effective_profile(self.state, self.profile)))
        self.assertNotEqual([x['oferta'].url for x in ranked[:7]], [x['oferta'].url for x in updated])

    def test_duplicate_publications_before_threshold_and_undo_survive_reload(self):
        first = self.listing(1)
        alias = dict(first, enlace='https://another.test/the-same-vacancy')
        self.discard(1, reason='location', scope='global')
        set_offer_action(self.state, alias, 'discarded', reason='location', scope='global')
        self.discard(2, reason='location', scope='global')
        self.assertEqual(len(self.state['signals']), 2)
        self.assertEqual(effective_priorities(self.state)['location'], 'Baja')
        save_json(self.path, self.state)
        self.state = load_feedback(self.path, self.profile)
        self.discard(3, reason='location', scope='global')
        save_json(self.path, self.state)
        self.state = load_feedback(self.path, self.profile)
        self.assertEqual(effective_priorities(self.state)['location'], 'Media')
        self.assertEqual(self.profile['importancia_ubicacion'], 'Baja')
        undo_adjustment(self.state, self.state['adjustments'][-1]['id'])
        save_json(self.path, self.state)
        self.state = load_feedback(self.path, self.profile)
        self.assertEqual(effective_priorities(self.state)['location'], 'Baja')
        self.discard(4, reason='location', scope='global')
        self.assertEqual(effective_priorities(self.state)['location'], 'Baja')
        self.assertEqual(len(self.state['adjustments']), 1)

    def test_configurable_threshold(self):
        self.state['threshold'] = 2
        self.discard(1, reason='location', scope='global')
        self.discard(2, reason='location', scope='global')
        self.assertEqual(effective_priorities(self.state)['location'], 'Media')


class FeedbackInterfaceTests(unittest.TestCase):
    # Reuse fixtures without inheriting and running unrelated tests twice.
    setUp = fixtures.InterfaceTests.setUp
    tearDown = fixtures.InterfaceTests.tearDown
    app = fixtures.InterfaceTests.app
    button = fixtures.InterfaceTests.button
    def test_saved_interest_and_discard_do_not_call_apis(self):
        app = self.app()
        self.button(app, 'Buscar ofertas').click().run()
        self.assertEqual(self.search.call_count, 1)
        self.button(app, 'Guardar').click().run()
        self.button(app, 'Descartar').click().run()
        self.button(app, 'Descartar sin indicar motivo').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.search.call_count, 1)
        state = load_feedback(self.file_path.parent / '.local_data' / 'offer_feedback.json', self.profile)
        record = next(iter(state['offers'].values()))
        self.assertTrue(record['saved'] and record['discarded'])
        self.assertFalse(any(b.label == 'Me interesa' for b in app.button))
        next(b for b in app.button if b.key and b.key.startswith('collection_discarded_')).click().run()
        self.button(app, 'Deshacer descarte').click().run()
        self.assertEqual(self.search.call_count, 1)
        self.assertFalse(app.exception)
        self.assertTrue(self.app().session_state.profile_saved)

    def test_three_ui_signals_reorder_locally_and_manual_edit_overrides(self):
        profile = migrate_profile(self.profile)
        profile['importancia_ubicacion'] = 'Baja'
        save_json(self.file_path, profile)
        self.search.return_value['evaluaciones'] = [sample_listing(role='Role '+str(i),
            url='https://example.test/'+str(i)).model_dump() for i in range(6)]
        app = self.app()
        self.button(app, 'Buscar ofertas').click().run()
        with patch('jobs.agent.reevaluate_listings') as reevaluate, patch('profiles.skills.suggest_skills') as suggest:
            for _ in range(3):
                self.button(app, 'Descartar').click().run()
                next(s for s in app.selectbox if s.label == 'Motivo (opcional)').select('location').run()
                next(r for r in app.radio if r.label == '¿Qué quieres indicar?').set_value('Este criterio pesa más para mí').run()
                self.button(app, 'Confirmar descarte').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(self.search.call_count, 1)
            self.assertFalse(reevaluate.called or suggest.called)
            state = load_feedback(self.file_path.parent / '.local_data' / 'offer_feedback.json', profile)
            self.assertEqual(effective_priorities(state)['location'], 'Media')
            self.assertFalse(any(e.label == 'Lo que he aprendido sobre ti' for e in app.expander))
            self.assertTrue(any('Importancia global de ubicación: Media' in c.value for c in app.caption))
            self.button(app, 'Cerrar aviso').click().run()
            app = self.app()
            self.assertFalse(any(b.label == 'Cerrar aviso' for b in app.button))
            state = load_feedback(self.file_path.parent / '.local_data' / 'offer_feedback.json', profile)
            self.assertEqual(effective_priorities(state)['location'], 'Media')
            app.button(key='resumen_editar_ubicaciones').click().run()
            next(s for s in app.selectbox if s.label == 'Importancia global de la ubicación').select('Baja').run()
            self.button(app, 'Guardar').click().run()
            self.assertFalse(app.exception)
            state = load_feedback(self.file_path.parent / '.local_data' / 'offer_feedback.json', profile)
            self.assertEqual(effective_priorities(state)['location'], 'Baja')
            self.assertEqual(self.search.call_count, 1)

    def test_all_action_undos_persist_across_new_sessions(self):
        app = self.app()
        self.button(app, 'Buscar ofertas').click().run()
        with patch('jobs.agent.reevaluate_listings') as reevaluate, patch('profiles.skills.suggest_skills') as suggest:
            self.button(app, 'Guardar').click().run()
            self.button(app, 'Descartar').click().run()
            self.button(app, 'Descartar sin indicar motivo').click().run()
            app = self.app()
            self.assertFalse(app.exception)
            next(b for b in app.button if b.key and b.key.startswith('collection_discarded_')).click().run()
            self.button(app, 'Deshacer descarte').click().run()
            app = self.app()
            self.button(app, 'Quitar de guardadas').click().run()
            app = self.app()
            self.assertFalse(app.exception)
            state = load_feedback(self.file_path.parent / '.local_data' / 'offer_feedback.json', migrate_profile(self.profile))
            record = next(iter(state['offers'].values()))
            self.assertFalse(record['saved'] or record['interested'] or record['discarded'])
            self.assertTrue(all(not signal['active'] for signal in state['signals']))
            self.assertEqual(self.search.call_count, 1)
            reevaluate.assert_not_called()
            suggest.assert_not_called()

    def test_other_batches_exhaust_locally_without_external_calls(self):
        listings = [sample_listing(role='Local role '+str(i), url='https://example.test/jobs/'+str(i)).model_dump()
                    for i in range(7)]
        self.search.return_value['evaluaciones'] = listings + [listings[0]]
        app = self.app()
        self.button(app, 'Buscar ofertas').click().run()
        def displayed_roles():
            return {heading.value for heading in app.subheader if heading.value.startswith('Local role ')}
        first = displayed_roles()
        self.assertEqual(len(first), 5)
        with patch('jobs.agent.reevaluate_listings') as reevaluate, patch('profiles.skills.suggest_skills') as suggest:
            self.button(app, 'Mostrar otras ofertas').click().run()
            second = displayed_roles()
            self.assertEqual(len(second), 2)
            self.assertFalse(first.intersection(second))
            self.button(app, 'Mostrar otras ofertas').click().run()
            self.assertFalse(displayed_roles())
            self.assertTrue(any(button.label == 'Buscar más ofertas' for button in app.button))
            self.assertEqual(self.search.call_count, 1)
            self.button(app, 'Volver a las ofertas anteriores').click().run()
            self.assertEqual(displayed_roles(), first)
            self.assertFalse(app.exception)
            reevaluate.assert_not_called()
            suggest.assert_not_called()

    def test_collection_contains_titles_and_opens_local_dialog(self):
        app = self.app()
        self.button(app, 'Buscar ofertas').click().run()
        self.button(app, 'Guardar').click().run()
        self.assertTrue(any(tab.label == 'Guardadas y descartadas' for tab in app.get('tab')))
        tab = next(tab for tab in app.get('tab') if tab.label == 'Guardadas')
        self.assertEqual(len(tab.get('subheader')), 0)
        self.assertEqual(len(tab.get('expander')), 0)
        title = next(b for b in app.button if b.key and b.key.startswith('collection_saved_'))
        self.assertEqual(title.label, 'Analista')
        title.click().run()
        self.assertTrue(app.session_state.selected_offer)
        self.assertGreaterEqual(sum(h.value == 'Analista · Empresa ficticia' for h in app.subheader), 2)
        self.assertEqual(self.search.call_count, 1)
        self.assertFalse(app.exception)
