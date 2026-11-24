import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from auditalgpd import create_app
from auditalgpd.assessment import assessment
from auditalgpd.audit import Auditoria, advice_facts
from auditalgpd.domain import AuditResult, Check, Status
from auditalgpd.gemini import GeminiClient, LEGAL_REFS
from auditalgpd.security import AuditError, Page

SCORE = {"value": 13, "improvements": [
    {"key": "policy", "title": "Link de política", "category": "Transparência", "weight": 10, "gain": 10, "severity": "alta",
     "recommendation": "Disponibilize um link visível.", "detail": "Não foi identificado um link.", "evidence": []},
    {"key": "cookie_choices", "title": "Escolhas no aviso de cookies", "category": "Cookies", "weight": 10, "gain": 7, "severity": "media",
     "recommendation": "Ofereça escolhas.", "detail": "Só aceitar.", "evidence": ["aceitar"]}]}


def reply(payload):
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(payload)}]}}]}


class AdviseTests(unittest.TestCase):
    def test_valid_tips_are_kept_and_unknown_keys_and_refs_are_dropped(self):
        data = {"resumo": "Priorize o link da política.", "itens": [
            {"chave": "policy", "dica": "Coloque o link no rodapé.", "referencias": ["LGPD art. 9º", "Lei inventada art. 99", "LGPD art. 9º"]},
            {"chave": "inexistente", "dica": "Não deve aparecer.", "referencias": []},
            {"chave": "cookie_choices", "dica": "Adicione rejeitar e configurar.", "referencias": ["Guia de Cookies da ANPD"]}]}
        result = GeminiClient("fake", transport=lambda _: reply(data)).advise("loja.com.br", SCORE, {"campos_de_formulario": ["e-mail"]})
        self.assertEqual(set(result["tips"]), {"policy", "cookie_choices"})
        self.assertEqual(result["tips"]["policy"]["refs"], ["LGPD art. 9º"])
        self.assertTrue(all(r in LEGAL_REFS for tip in result["tips"].values() for r in tip["refs"]))
        self.assertEqual(result["summary"], "Priorize o link da política.")
        self.assertNotIn("score", result)

    def test_request_contains_only_summary_data_and_fixed_endpoint(self):
        seen = []
        data = {"resumo": "", "itens": [{"chave": "policy", "dica": "ok", "referencias": []}]}
        GeminiClient("fake-test-key", transport=lambda r: seen.append(r) or reply(data)).advise(
            "loja.com.br", SCORE, {"cookies_por_categoria": {"Estatística": 2}})
        request = seen[0]
        self.assertTrue(request.full_url.startswith("https://generativelanguage.googleapis.com/"))
        self.assertNotIn("fake-test-key", request.full_url)
        context = json.loads(json.loads(request.data)["contents"][0]["parts"][0]["text"])
        self.assertEqual(set(context), {"site", "nota_atual", "fatos_observados", "criterios_nao_identificados"})
        self.assertEqual(context["site"], "loja.com.br")
        self.assertEqual([i["titulo"] for i in context["criterios_nao_identificados"]], ["Link de política", "Escolhas no aviso de cookies"])
        self.assertEqual(context["fatos_observados"], {"cookies_por_categoria": {"Estatística": 2}})

    def test_empty_invalid_or_missing_input_fails_safely(self):
        with self.assertRaises(AuditError):
            GeminiClient("fake", transport=lambda _: reply({"resumo": "", "itens": []})).advise("a.com", SCORE, {})
        with self.assertRaises(AuditError):
            GeminiClient("fake", transport=lambda _: reply({"resumo": "x"})).advise("a.com", SCORE, {})
        with self.assertRaises(AuditError):
            GeminiClient().advise("a.com", SCORE, {})
        with self.assertRaises(AuditError):
            GeminiClient("fake", transport=lambda _: {}).advise("a.com", {"improvements": []}, {})


class FakeAI:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def review(self, text, source, host, score, facts):
        self.calls.append((host, score["value"] if score else None, facts))
        if self.fail:
            raise AuditError("O Gemini está com alta demanda neste momento.")
        advice = None
        if score:
            key = score["improvements"][0]["key"]
            advice = {"provider": "Google Gemini", "model": "m", "summary": "Resumo.", "tips": {key: {"text": "Dica.", "refs": ["LGPD art. 9º"]}}, "notice": "n"}
        analysis = {"provider": "Google Gemini", "model": "m", "source": source, "characters_sent": len(text), "truncated": False, "items": [], "notice": "n"} if text else None
        return {"analysis": analysis, "advice": advice, "errors": {}}


class Fetcher:
    def fetch(self, url, **kwargs):
        return Page(url, "<p>página simples</p>", True)


class IntegrationTests(unittest.TestCase):
    def test_low_score_with_ai_enabled_stores_advice_and_never_changes_the_score(self):
        ai = FakeAI()
        with_ai = Auditoria(Fetcher(), ai_client=ai).executar("https://loja.com.br", use_ai=True)
        without_ai = Auditoria(Fetcher(), ai_client=FakeAI()).executar("https://loja.com.br", use_ai=False)
        self.assertEqual(len(ai.calls), 1)
        self.assertEqual(ai.calls[0][0], "loja.com.br")
        self.assertTrue(with_ai.advice["tips"])
        self.assertTrue(with_ai.ai)  # a mesma chamada também devolveu a interpretação da política
        self.assertEqual((with_ai.score["value"], with_ai.score["grade"]), (without_ai.score["value"], without_ai.score["grade"]))
        self.assertEqual(without_ai.advice, {})

    def test_gemini_failure_keeps_the_report_and_records_the_reason(self):
        result = Auditoria(Fetcher(), ai_client=FakeAI(fail=True)).executar("https://loja.com.br", use_ai=True)
        self.assertEqual(result.advice, {"error": "O Gemini está com alta demanda neste momento."})
        self.assertIsNotNone(result.score["value"])

    def test_high_score_does_not_call_gemini(self):
        ai = FakeAI()
        high = {"value": 90, "improvements": SCORE["improvements"], "pending": [], "missing": [], "items": [], "categories": []}
        with mock.patch("auditalgpd.audit.assessment", return_value=high):
            result = Auditoria(Fetcher(), ai_client=ai).executar("https://loja.com.br", use_ai=True)
        self.assertTrue(all(call[1] is None for call in ai.calls))  # nota alta: nenhuma dica foi pedida
        self.assertEqual(result.advice, {})

    def test_facts_have_no_cookie_values_or_page_text(self):
        result = AuditResult("https://loja.com.br/", mode="browser", browser={
            "cookies": [{"name": "_ga", "domain": ".loja.com.br"}, {"name": "_fbp", "domain": ".loja.com.br"}],
            "domains": ["www.google-analytics.com", "cdn.desconhecido.io"]},
            checks=[Check("forms", "Formulários", Status.PRESENT, "x", ["Campos com indícios de dados pessoais: email."])])
        facts = advice_facts(result)
        self.assertEqual(facts["cookies_por_categoria"], {"Estatística": 1, "Publicidade": 1})
        self.assertEqual(facts["campos_de_formulario"], ["e-mail"])
        self.assertEqual(facts["servicos_de_terceiros"], ["Google (análise de audiência / gerenciador de tags)"])
        self.assertNotIn("desconhecido", json.dumps(facts))


class ScreenTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "SECRET_KEY": "t", "DATABASE": str(Path(self.directory.name) / "t.db"),
                               "AUDITOR": Auditoria(Fetcher())})
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def saved(self, **extra):
        audit = AuditResult("https://loja.com.br/", final_url="https://loja.com.br/", mode="browser", checks=[
            Check("https", "Conexão HTTPS", Status.PRESENT, "ok"), Check("policy", "Link de política", Status.ABSENT, "sem link"),
            Check("ai", "Interpretação com Gemini", Status.NOT_RUN, "IA desativada")], **extra)
        audit.score = assessment(audit)
        self.app.extensions["repository"].save(audit)
        return self.client.get(f"/auditorias/{audit.id}").data.decode("utf-8")

    def test_notice_and_tip_appear_only_with_advice(self):
        page = self.saved(advice={"summary": "Comece pelo link.", "tips": {"policy": {"text": "Coloque no rodapé.", "refs": ["LGPD art. 9º"]}}})
        self.assertIn("Parte dos textos desta seção foi escrita com ajuda do Gemini", page)
        self.assertIn("A IA pode cometer erros", page)
        self.assertIn("Coloque no rodapé.", page)
        self.assertIn("Base: LGPD art. 9º", page)
        self.assertIn("Comece pelo link.", page)
        plain = self.saved()
        self.assertNotIn("escrita com ajuda do Gemini", plain)
        self.assertNotIn("ai-tip", plain)

    def test_gemini_error_is_explained_inside_the_panel(self):
        page = self.saved(advice={"error": "O Gemini está com alta demanda neste momento."})
        self.assertIn("Não foi possível obter as dicas do Gemini", page)
        self.assertIn("alta demanda", page)

    def test_empty_gemini_card_is_hidden_unless_there_is_something_to_show(self):
        self.assertNotIn('id="ia"', self.saved())
        self.assertIn('id="ia"', self.saved(ai={"items": [], "notice": "n", "model": "m", "characters_sent": 1, "truncated": False}))


class FallbackTests(unittest.TestCase):
    OK = reply({"resumo": "r", "itens": [{"chave": "policy", "dica": "Dica.", "referencias": []}]})

    def call(self, behaviors, models=("a", "b")):
        import io
        calls = []

        class Opener:
            def open(self, request, timeout=None):
                model = request.full_url.split("/models/")[1].split(":")[0]
                calls.append(model)
                behavior = behaviors["gemini-" + model.split("gemini-")[1]]
                if isinstance(behavior, list):
                    behavior = behavior.pop(0)
                if isinstance(behavior, Exception):
                    raise behavior
                return io.BytesIO(json.dumps(behavior).encode())

        client = GeminiClient("fake", model="gemini-" + models[0], fallbacks=["gemini-" + m for m in models[1:]])
        with mock.patch("urllib.request.build_opener", return_value=Opener()), mock.patch("auditalgpd.gemini.time.sleep") as sleep:
            self.slept = sleep
            try:
                return client.advise("a.com", SCORE, {}), calls
            except AuditError as exc:
                return exc, calls

    def http(self, code):
        import urllib.error
        return urllib.error.HTTPError("https://example", code, "x", None, None)

    def test_unavailable_primary_model_falls_back_and_reports_who_answered(self):
        result, calls = self.call({"gemini-a": self.http(503), "gemini-b": self.OK})
        self.assertEqual(calls, ["gemini-a", "gemini-b"])
        self.assertEqual(result["model"], "gemini-b")
        self.assertIn("policy", result["tips"])

    def test_missing_model_and_timeouts_also_fall_back(self):
        result, calls = self.call({"gemini-a": self.http(404), "gemini-b": TimeoutError(), "gemini-c": self.OK}, ("a", "b", "c"))
        self.assertEqual(calls, ["gemini-a", "gemini-b", "gemini-c"])
        self.assertEqual(result["model"], "gemini-c")

    def test_key_and_permission_errors_do_not_try_other_models(self):
        for code in (401, 403):
            result, calls = self.call({"gemini-a": self.http(code), "gemini-b": self.OK})
            self.assertEqual(calls, ["gemini-a"])
            self.assertIsInstance(result, AuditError)

    def test_quota_is_per_model_so_another_model_is_tried(self):
        result, calls = self.call({"gemini-a": self.http(429), "gemini-b": self.OK})
        self.assertEqual(calls, ["gemini-a", "gemini-b"])
        self.assertEqual(result["model"], "gemini-b")

    def test_quota_exhausted_everywhere_reports_it_without_extra_rounds(self):
        result, calls = self.call({"gemini-a": self.http(429), "gemini-b": self.http(429)})
        self.assertEqual(calls, ["gemini-a", "gemini-b"])
        self.slept.assert_not_called()
        self.assertIn("cota", str(result))

    def test_all_models_busy_gives_a_clear_message_after_one_extra_round(self):
        result, calls = self.call({"gemini-a": self.http(503), "gemini-b": self.http(503)})
        self.assertEqual(calls, ["gemini-a", "gemini-b", "gemini-a", "gemini-b"])
        self.slept.assert_called_once_with(3)
        self.assertIn("alta demanda", str(result))

    def test_second_round_can_succeed_after_a_brief_overload(self):
        result, calls = self.call({"gemini-a": [self.http(503), self.OK], "gemini-b": [self.http(503), self.OK]})
        self.assertEqual(calls, ["gemini-a", "gemini-b", "gemini-a"])
        self.assertEqual(result["model"], "gemini-a")

    def test_timeouts_are_not_repeated(self):
        result, calls = self.call({"gemini-a": TimeoutError(), "gemini-b": TimeoutError()})
        self.assertEqual(calls, ["gemini-a", "gemini-b"])
        self.slept.assert_not_called()
        self.assertIn("prazo", str(result))

    def test_invalid_fallback_ids_are_ignored(self):
        client = GeminiClient("fake", model="gemini-a", fallbacks=["../x", "gemini-b"])
        client._ready()
        self.assertEqual(client.fallbacks, ["gemini-b"])


if __name__ == "__main__":
    unittest.main()
