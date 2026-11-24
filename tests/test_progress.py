import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from auditalgpd import create_app
from auditalgpd.audit import Auditoria
from auditalgpd.jobs import Jobs
from auditalgpd.security import Page


class Fetcher:
    def fetch(self, url, **kwargs):
        return Page(url, "<p>página simples</p>", True)


class StubAI:
    def review(self, text, source, host, score, facts):
        advice = None
        if score:
            key = score["improvements"][0]["key"]
            advice = {"provider": "g", "model": "m", "summary": "", "tips": {key: {"text": "Dica.", "refs": []}}, "notice": "n"}
        analysis = {"provider": "g", "model": "m", "source": source, "characters_sent": len(text), "truncated": False, "items": [], "notice": "n"} if text else None
        return {"analysis": analysis, "advice": advice, "errors": {}}


class JobsTests(unittest.TestCase):
    def test_update_records_steps_percent_never_goes_back_and_done_is_100(self):
        jobs = Jobs()

        def work(update):
            update("Primeira etapa", 10, 30)
            update("Segunda etapa", 5)  # não pode voltar
            update("Terceira etapa", 60)
            return SimpleNamespace(id="abc")

        identifier = jobs.submit(work, label="loja.com.br")
        jobs.executor.shutdown(wait=True)
        job = jobs.get(identifier)
        self.assertEqual(job["state"], "done")
        self.assertEqual((job["percent"], job["until"], job["label"]), (100, 100, "loja.com.br"))
        steps = [(e["message"], e["percent"]) for e in job["log"]]
        self.assertEqual(steps, [("Iniciando a análise", 1), ("Primeira etapa", 10), ("Segunda etapa", 10), ("Terceira etapa", 60)])
        self.assertTrue(all(e["until"] >= e["percent"] for e in job["log"]))

    def test_get_returns_a_copy_of_the_log(self):
        jobs = Jobs()
        identifier = jobs.submit(lambda update: SimpleNamespace(id="x"))
        jobs.executor.shutdown(wait=True)
        jobs.get(identifier)["log"].append({"message": "adulterado"})
        self.assertNotIn("adulterado", [e["message"] for e in jobs.get(identifier)["log"]])


class AuditStepsTests(unittest.TestCase):
    def test_steps_come_in_order_with_increasing_percent(self):
        steps = []
        Auditoria(Fetcher()).executar("https://loja.com.br", progress=lambda message, percent=None, until=None: steps.append((message, percent)))
        messages = [m for m, _ in steps]
        self.assertEqual(messages[0], "Validando o endereço informado")
        for expected in ["Consultando o HTML da página", "Conferindo HTTPS, aviso de cookies e formulários", "Analisando as escolhas do aviso de cookies",
                         "Procurando o link da política de privacidade", "Calculando a nota pela rubrica", "Montando o relatório"]:
            self.assertIn(expected, messages)
        self.assertNotIn("Analisando os cookies e domínios observados", messages)  # só no modo avançado
        percents = [p for _, p in steps]
        self.assertEqual(percents, sorted(percents))
        self.assertEqual(steps[-1], ("Montando o relatório", 98))

    def test_gemini_steps_appear_only_when_ai_is_used(self):
        with_ai, without = [], []
        Auditoria(Fetcher(), ai_client=StubAI()).executar("https://loja.com.br", use_ai=True, progress=lambda m, p=None, u=None: with_ai.append(m))
        Auditoria(Fetcher(), ai_client=StubAI()).executar("https://loja.com.br", use_ai=False, progress=lambda m, p=None, u=None: without.append(m))
        self.assertIn("Gemini analisando a política e preparando as dicas de melhoria", with_ai)
        self.assertEqual(len([m for m in with_ai if "Gemini" in m]), 1)  # uma única etapa de IA
        self.assertFalse([m for m in without if "Gemini" in m])

    def test_progress_callback_is_optional(self):
        result = Auditoria(Fetcher()).executar("https://loja.com.br")
        self.assertIsNotNone(result.score["value"])


class PageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "SECRET_KEY": "t", "DATABASE": str(Path(self.directory.name) / "t.db"), "AUDITOR": Auditoria(Fetcher())})
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def token(self):
        self.client.get("/")
        with self.client.session_transaction() as session:
            return session["csrf"]

    def test_starting_an_analysis_points_to_the_progress_page(self):
        response = self.client.post("/auditorias", data={"csrf": self.token(), "url": "https://loja.com.br", "authorized": "yes"},
                                    headers={"X-Audita-Async": "1"})
        self.assertEqual(response.status_code, 202)
        self.assertIn("/analisando/", response.json["page_url"])
        self.app.extensions["jobs"].executor.shutdown(wait=True)
        page = self.client.get(response.json["page_url"])
        self.assertEqual(page.status_code, 200)
        text = page.data.decode("utf-8")
        self.assertIn("ANÁLISE EM ANDAMENTO · loja.com.br", text)
        self.assertIn('role="progressbar"', text)
        self.assertIn("/static/progress.js", text)
        self.assertNotIn(' style="', text)  # a política de segurança bloqueia estilos inline
        state = self.client.get(response.json["progress_url"]).json
        self.assertEqual((state["state"], state["percent"]), ("done", 100))
        self.assertGreater(len(state["log"]), 5)

    def test_unknown_job_is_404_and_script_is_served(self):
        self.assertEqual(self.client.get("/analisando/nao-existe").status_code, 404)
        script = self.client.get("/static/progress.js")
        self.assertEqual(script.status_code, 200)
        script.close()


if __name__ == "__main__":
    unittest.main()
