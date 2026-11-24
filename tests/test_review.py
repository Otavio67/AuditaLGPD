import json
import tempfile
import unittest
from pathlib import Path
from auditalgpd.ai_cache import AiCache
from auditalgpd.audit import advice_facts
from auditalgpd.domain import AuditResult, Check, Status
from auditalgpd.gemini import GeminiClient, TOPICS
from auditalgpd.security import AuditError
from auditalgpd.settings import Settings

TEXT = "A finalidade é prestar o serviço. Contato: ana@example.org."
SCORE = {"value": 13, "improvements": [
    {"key": "policy", "title": "Link de política", "category": "Transparência", "weight": 10, "gain": 10, "severity": "alta",
     "recommendation": "Disponibilize um link visível.", "detail": "Não foi identificado um link.", "evidence": []}]}


def combined(policy=True, advice=True, quote="A finalidade é prestar o serviço."):
    body = {}
    if policy:
        body["politica"] = {"temas": [{"chave": k, "estado": "identificado" if k == "purposes" else "nao_localizado",
                                       "citacao": quote if k == "purposes" else "", "explicacao": "Descrição."} for k in TOPICS]}
    if advice:
        body["dicas"] = {"resumo": "Priorize o link.", "itens": [{"chave": "policy", "dica": "Coloque o link no rodapé.", "referencias": ["LGPD art. 9º"]}]}
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(body)}]}}]}


class Counter:
    def __init__(self, response):
        self.response, self.requests = response, []

    def __call__(self, request):
        self.requests.append(request)
        return self.response


class ReviewTests(unittest.TestCase):
    def test_one_request_returns_policy_reading_and_tips(self):
        transport = Counter(combined())
        result = GeminiClient("fake-test-key", transport=transport).review(TEXT, "https://loja.com.br/p", "loja.com.br", SCORE, {"modo_de_analise": "simples"})
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(result["analysis"]["items"][0]["status"], "identificado")
        self.assertEqual(result["advice"]["tips"]["policy"]["refs"], ["LGPD art. 9º"])
        self.assertEqual(result["errors"], {})
        request = transport.requests[0]
        self.assertNotIn("fake-test-key", request.full_url)
        self.assertNotIn(b"ana@example.org", request.data)  # e-mail removido antes do envio
        tasks = json.loads(json.loads(request.data)["contents"][0]["parts"][0]["text"])
        self.assertEqual(set(tasks), {"politica", "dicas"})

    def test_only_the_needed_tasks_are_sent(self):
        policy_only = Counter(combined(advice=False))
        GeminiClient("k", transport=policy_only).review(TEXT, "s", "a.com", None, None)
        self.assertEqual(set(json.loads(json.loads(policy_only.requests[0].data)["contents"][0]["parts"][0]["text"])), {"politica"})
        advice_only = Counter(combined(policy=False))
        GeminiClient("k", transport=advice_only).review("", "s", "a.com", SCORE, {})
        self.assertEqual(set(json.loads(json.loads(advice_only.requests[0].data)["contents"][0]["parts"][0]["text"])), {"dicas"})
        with self.assertRaises(AuditError):
            GeminiClient("k", transport=Counter(combined())).review("", "s", "a.com", None, None)

    def test_one_invalid_part_does_not_discard_the_other(self):
        bad_advice = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(
            {"politica": json.loads(combined()["candidates"][0]["content"]["parts"][0]["text"])["politica"], "dicas": {"resumo": "x", "itens": []}})}]}}]}
        result = GeminiClient("k", transport=Counter(bad_advice)).review(TEXT, "s", "a.com", SCORE, {})
        self.assertIsNotNone(result["analysis"])
        self.assertIsNone(result["advice"])
        self.assertIn("advice", result["errors"])
        with self.assertRaises(AuditError):
            GeminiClient("k", transport=Counter({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]})).review(TEXT, "s", "a.com", SCORE, {})

    def test_fabricated_quote_is_still_discarded_in_the_combined_call(self):
        result = GeminiClient("k", transport=Counter(combined(quote="Texto inventado"))).review(TEXT, "s", "a.com", SCORE, {})
        self.assertEqual(result["analysis"]["items"][0]["status"], "incerto")


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "cache.sqlite3"

    def tearDown(self):
        self.directory.cleanup()

    def test_same_content_does_not_spend_quota_twice(self):
        transport = Counter(combined())
        client = GeminiClient("k", transport=transport, cache=AiCache(self.path))
        first = client.review(TEXT, "s", "a.com", SCORE, {"x": 1})
        second = client.review(TEXT, "s", "a.com", SCORE, {"x": 1})
        self.assertEqual(len(transport.requests), 1)
        self.assertNotIn("cached", first["advice"])
        self.assertTrue(second["advice"]["cached"] and second["analysis"]["cached"])
        self.assertEqual(second["advice"]["tips"], first["advice"]["tips"])
        client.review(TEXT, "s", "a.com", SCORE, {"x": 2, "cookies_observados": ["varia a cada carga"]})  # detalhes voláteis: continua em cache
        self.assertEqual(len(transport.requests), 1)
        client.review(TEXT + " Nova frase na política.", "s", "a.com", SCORE, {"x": 1})  # política mudou: nova chamada
        self.assertEqual(len(transport.requests), 2)
        client.review(TEXT, "s", "outro-site.com", SCORE, {"x": 1})  # outro site: nova chamada
        self.assertEqual(len(transport.requests), 3)
        other = {**SCORE, "improvements": [{**SCORE["improvements"][0], "gain": 5}]}
        client.review(TEXT, "s", "a.com", other, {"x": 1})  # critérios mudaram: nova chamada
        self.assertEqual(len(transport.requests), 4)

    def test_cache_is_shared_between_clients_and_expires(self):
        transport = Counter(combined())
        GeminiClient("k", transport=transport, cache=AiCache(self.path)).review(TEXT, "s", "a.com", SCORE, {})
        GeminiClient("other-key", transport=transport, cache=AiCache(self.path)).review(TEXT, "s", "a.com", SCORE, {})
        self.assertEqual(len(transport.requests), 1)
        GeminiClient("k", transport=transport, cache=AiCache(self.path, ttl=-1)).review(TEXT, "s", "a.com", SCORE, {})
        self.assertEqual(len(transport.requests), 2)

    def test_partial_results_and_errors_are_not_cached(self):
        bad = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(
            {"politica": json.loads(combined()["candidates"][0]["content"]["parts"][0]["text"])["politica"], "dicas": {"resumo": "x", "itens": []}})}]}}]}
        transport = Counter(bad)
        client = GeminiClient("k", transport=transport, cache=AiCache(self.path))
        client.review(TEXT, "s", "a.com", SCORE, {})
        client.review(TEXT, "s", "a.com", SCORE, {})
        self.assertEqual(len(transport.requests), 2)

    def test_unusable_cache_never_breaks_the_analysis(self):
        broken = AiCache(Path(self.directory.name) / "pasta" / "inexistente" / "c.sqlite3")
        result = GeminiClient("k", transport=Counter(combined()), cache=broken).review(TEXT, "s", "a.com", SCORE, {})
        self.assertIsNotNone(result["advice"])

    def test_settings_client_uses_a_cache_next_to_the_data(self):
        settings = Settings(self.directory.name)
        self.assertEqual(settings.client().cache.path, Path(self.directory.name) / "ai_cache.sqlite3")


class FactsTests(unittest.TestCase):
    def test_facts_carry_cookie_names_policy_findings_and_redact_excerpts(self):
        result = AuditResult("https://loja.com.br/", mode="browser",
                             browser={"cookies": [{"name": "_ga", "domain": ".loja.com.br", "value": "SEGREDO"}], "domains": []},
                             checks=[Check("purposes", "Finalidades do tratamento", Status.PRESENT, "x", ["Usamos seus dados; escreva para ana@example.org."]),
                                     Check("retention", "Retenção e eliminação", Status.ABSENT, "x"),
                                     Check("cookie_choices", "Escolhas no aviso de cookies", Status.ABSENT, "x", ["aceitar"])])
        facts = advice_facts(result, "caminho comum do mesmo domínio", 1200)
        self.assertEqual(facts["cookies_observados"], [{"nome": "_ga", "categoria": "Estatística", "dominio": ".loja.com.br"}])
        self.assertEqual(facts["controles_encontrados_no_aviso_de_cookies"], ["aceitar"])
        self.assertEqual(facts["politica"]["encontrada_por"], "caminho comum do mesmo domínio")
        self.assertEqual(facts["politica"]["caracteres_lidos"], 1200)
        topics = {t["tema"]: t for t in facts["politica"]["temas_buscados_por_heuristica"]}
        self.assertIn("[e-mail removido]", topics["Finalidades do tratamento"]["trecho"])
        self.assertEqual(topics["Retenção e eliminação"]["estado"], "nao_identificado")
        self.assertNotIn("SEGREDO", json.dumps(facts))
        self.assertNotIn("ana@example.org", json.dumps(facts))


if __name__ == "__main__":
    unittest.main()
