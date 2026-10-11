"""Test search contracts with local fixtures and simulated services. Exercise regression behavior without live APIs; unit and Streamlit simulations do not establish complete browser-flow validation."""

import unittest
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jobs.job_search import (Criterion, TavilyTools, Recommendation, EvaluationResult,
                      validate_recommendations)


class SearchTests(unittest.TestCase):
    def test_distinguishes_error_technical_and_page_inaccessible(self):
        import httpx
        events = []
        client = Mock()
        tools = TavilyTools(client, lambda *e: events.append(e))
        client.post.side_effect = httpx.ConnectError("Error ficticio")
        tools.execute("search", {"query": "ofertas ficticias"})
        self.assertTrue(any(e[0] == "error_tecnico" for e in events))
        client.post.side_effect = None
        url = "https://example.com/oferta"
        tools.discovered[url] = {}
        client.post.return_value.json.return_value = {"results": [], "failed_results": [{"url": url}]}
        tools.execute("extract", {"urls": [url]})
        self.assertTrue(any(e[0] == "inaccesible" and e[2] == url for e in events))

    def test_agent_chains_model_job_search_extraction_and_evaluation(self):
        from jobs.agent import search_listings
        from tests.test_interface import sample_listing
        listing = sample_listing()
        text = "Empresa ficticia Analista Madrid Analizar datos Python"
        search_call = SimpleNamespace(type="function_call", name="search", call_id="1",
            arguments=json.dumps({"query": "Analista Madrid"}))
        extract_call = SimpleNamespace(type="function_call", name="extract", call_id="2",
            arguments=json.dumps({"urls": [listing.url]}))
        with patch('jobs.agent.load_dotenv'), patch('jobs.agent.save_diagnostics'), patch.dict("os.environ", {
            "OPENAI_API_KEY": "clave-ficticia", "TAVILY_API_KEY": "clave-ficticia"}),\
            patch('jobs.agent.OpenAI') as openai, patch('jobs.agent.httpx.Client') as http:
            model = openai.return_value.__enter__.return_value
            model.responses.create.side_effect = [
                SimpleNamespace(status="completed", output=[search_call]),
                SimpleNamespace(status="completed", output=[extract_call]),
                SimpleNamespace(status="completed", output=[])]
            model.responses.parse.return_value = SimpleNamespace(status="completed",
                output_parsed=EvaluationResult(job_listings=[listing], discarded=[]))
            client = http.return_value.__enter__.return_value
            answers = [Mock(), Mock()]
            answers[0].json.return_value = {"results": [{"url": listing.url, "title": "Analista"}]}
            answers[1].json.return_value = {"results": [{"url": listing.url, "raw_content": text}]}
            client.post.side_effect = answers
            result = search_listings({"perfil": {"confirmado": {"skills": ["Python"]}, "preferencias": {"puestos_objetivo": ["Analista"]}}})
            self.assertFalse(result["error"])
            self.assertEqual(result["llamadas"], 2)
            self.assertEqual(len(result["evaluaciones"]), 1)
            self.assertEqual([c.args[0] for c in client.post.call_args_list], ["/search", "/extract"])
            self.assertFalse(model.responses.parse.call_args.kwargs["store"])
            from shared.paths import PROJECT_ROOT
            base_instructions = (PROJECT_ROOT / 'agent_instructions.md').read_text()
            self.assertTrue(model.responses.create.call_args.kwargs['instructions'].startswith(base_instructions))
            self.assertTrue(model.responses.parse.call_args.kwargs['instructions'].startswith(base_instructions))
            context = {"perfil": {"confirmado": {"skills": ["Python"]},
                                   "preferencias": {"puestos_objetivo": ["Analista"]}},
                        "empresa_excluida": "Empresa ficticia Ltd"}
            model.responses.create.side_effect = [
                SimpleNamespace(status="completed", output=[search_call]),
                SimpleNamespace(status="completed", output=[extract_call]),
                SimpleNamespace(status="completed", output=[])]
            client.post.side_effect = answers
            excluded = search_listings(context)
            self.assertEqual(excluded["evaluaciones"], [])
            self.assertEqual(excluded["metricas"]["validas_antes_exclusion"], 1)

    def test_diagnostics_not_saves_text_free_or_urls(self):
        from shared.diagnostics import sanitized_event
        event = sanitized_event("descartada", "Texto con perfil, salario, clave y experiencia privados")
        self.assertEqual(event, {"categoria": "descartada", "codigo": "descartada"})
        from profiles.user_profile import employer_is_excluded
        self.assertTrue(employer_is_excluded("ACME, Inc.", "Acme"))
        self.assertFalse(employer_is_excluded("Acme Technology", "Acme"))

    def test_quotes_tolerate_format_but_not_paraphrases(self):
        from jobs.evaluation import quote_is_documented
        self.assertTrue(quote_is_documented("Build AI-based solutions.", "• Build AI–based\n solutions"))
        self.assertFalse(quote_is_documented("Build AI solutions", "Build AI based solutions"))
        self.assertFalse(quote_is_documented("Requires Python", "Does not require Python"))
        self.assertFalse(quote_is_documented("SQL", "PostgreSQL"))

    def test_batches_small_preserve_results_if_one_batch_fails(self):
        import httpx
        from openai import APIConnectionError
        from jobs.agent import search_listings
        from tests.test_interface import sample_listing
        job_listings = [sample_listing(role=f"Analista {n}", url=f"https://example.com/{n}") for n in range(4)]
        search = SimpleNamespace(type="function_call", name="search", call_id="1", arguments=json.dumps({"query": "Analista"}))
        extract = SimpleNamespace(type="function_call", name="extract", call_id="2", arguments=json.dumps({"urls": [o.url for o in job_listings]}))
        with patch('jobs.agent.load_dotenv'), patch('jobs.agent.save_diagnostics'), patch.dict("os.environ", {
            "OPENAI_API_KEY": "ficticia", "TAVILY_API_KEY": "ficticia"}),\
            patch('jobs.agent.OpenAI') as openai, patch('jobs.agent.httpx.Client') as http:
            model = openai.return_value.__enter__.return_value
            model.responses.create.side_effect = [SimpleNamespace(status="completed", output=[search]),
                SimpleNamespace(status="completed", output=[extract]), SimpleNamespace(status="completed", output=[])]
            model.responses.parse.side_effect = [APIConnectionError(request=httpx.Request("POST", "https://example.com")),
                SimpleNamespace(status="completed", output_parsed=EvaluationResult(job_listings=[job_listings[-1]], discarded=[]))]
            client = http.return_value.__enter__.return_value
            r1, r2 = Mock(), Mock()
            r1.json.return_value = {"results": [{"url": o.url, "title": o.role} for o in job_listings]}
            r2.json.return_value = {"results": [{"url": o.url, "raw_content": f"Empresa ficticia {o.role} Madrid Analizar datos Python"} for o in job_listings]}
            client.post.side_effect = [r1, r2]
            result = search_listings({"perfil": {"confirmado": {"skills": ["Python"]}, "preferencias": {"puestos_objetivo": ["Analista"]}}})
            self.assertFalse(result["error"])
            self.assertEqual(len(result["evaluaciones"]), 1)
            self.assertEqual(result["metricas"]["lotes_fallidos"], 1)
            self.assertEqual(result["metricas"]["lotes_evaluados"], 1)
            for call in model.responses.parse.call_args_list:
                self.assertLessEqual(len(json.loads(call.kwargs["input"])["ofertas"]), 3)

    def test_limit_includes_failures_and_blocks_eleventh_call(self):
        client = Mock()
        client.post.return_value.json.return_value = {"results": []}
        tools = TavilyTools(client)
        with patch("builtins.print"):
            for _ in range(12):
                tools.execute("search", {"query": "ofertas ficticias"})
        self.assertEqual(tools.calls, 10)
        self.assertEqual(client.post.call_count, 10)

    def test_extraction_rejects_url_fabricated_and_description_empty(self):
        client = Mock()
        tools = TavilyTools(client)
        url = "https://example.com/empleo"
        with patch("builtins.print"):
            tools.execute("extract", {"urls": [url]})
            client.post.assert_not_called()
            tools.discovered[url] = {}
            client.post.return_value.json.return_value = {
                "results": [{"url": url, "raw_content": " "}]}
            tools.execute("extract", {"urls": [url]})
        self.assertEqual(tools.retrieved, {})

    def test_evidence_and_duplicates(self):
        from tests.test_interface import sample_listing
        listing = sample_listing()
        other = listing.model_copy(update={'url': "https://example.com/2"})
        text = "Empresa ficticia Analista Madrid Analizar datos Python"
        profile = {"confirmado": {"skills": ["Python"]}, "preferencias": {"puestos_objetivo": ["Analista"]}}
        retrieved = {url: {"descripcion_recuperada": text} for url in (listing.url, other.url)}
        result = EvaluationResult(job_listings=[listing, other], discarded=[])
        valid = validate_recommendations(result, retrieved, profile)
        self.assertEqual(len(valid), 1)
        listing.criteria[1].profile_evidence = "Capacidad inventada"
        result = EvaluationResult(job_listings=[listing], discarded=[])
        valid = validate_recommendations(result, retrieved, profile)
        # Reject the fabricated quote; Python separately recognizes the skill
        # actually declared and required, without inferring professional proficiency.
        self.assertEqual(valid[0].criteria[1].points, 1)
        self.assertEqual(valid[0].criteria[1].declared_skills, ["Python"])
        self.assertNotIn("Capacidad inventada", valid[0].criteria[1].profile_evidence_quotes)
        self.assertEqual(validate_recommendations(result, {}, profile), [])


if __name__ == "__main__":
    unittest.main()
