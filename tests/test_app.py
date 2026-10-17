import tempfile
import unittest
from threading import Event
from pathlib import Path
from auditalgpd import create_app
from auditalgpd.audit import Auditoria
from auditalgpd.domain import AuditResult, Check, Status
from auditalgpd.security import AuditError, Page


class FixtureFetcher:
    def fetch(self, url, **kwargs):
        return Page(url, '<form><input type="email" value="PRIVATE-VALUE"></form>', True)


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-only", "DATABASE": str(Path(self.directory.name) / "test.db"), "AUDITOR": Auditoria(FixtureFetcher())})
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def token(self):
        self.client.get("/")
        with self.client.session_transaction() as session:
            return session["csrf"]

    def test_home_demo_and_empty_history(self):
        for path in ["/", "/historico", "/demonstracao", "/health"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(self.app.extensions["repository"].latest(), [])
        self.assertIn("Demonstração".encode(), self.client.get("/demonstracao").data)

    def test_post_requires_csrf_and_authorization(self):
        self.assertEqual(self.client.post("/auditorias", data={"url": "https://example.com"}).status_code, 400)
        self.assertEqual(self.client.post("/auditorias", data={"url": "https://example.com", "csrf": self.token()}).status_code, 400)
        self.assertEqual(self.app.extensions["repository"].latest(), [])

    def test_invalid_url_is_not_stored(self):
        response = self.client.post("/auditorias", data={"url": "http://127.0.0.1", "csrf": self.token(), "authorized": "yes"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.app.extensions["repository"].latest(), [])

    def test_complete_flow_persists_redacted_result_and_downloads_pdf(self):
        response = self.client.post("/auditorias", data={"url": "https://example.com/?secret=TOKEN", "csrf": self.token(), "authorized": "yes"})
        self.assertEqual(response.status_code, 303)
        report = self.client.get(response.headers["Location"])
        self.assertEqual(report.status_code, 200)
        self.assertNotIn(b"TOKEN", report.data)
        self.assertNotIn(b"PRIVATE-VALUE", report.data)
        stored = self.app.extensions["repository"].latest()[0]
        self.assertEqual(stored.url, "https://example.com/")
        pdf = self.client.get(response.headers["Location"] + "/relatorio.pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.data.startswith(b"%PDF-"))
        self.assertIn("attachment", pdf.headers["Content-Disposition"])

    def test_evidence_is_escaped_in_html_and_pdf_handles_markup(self):
        result = AuditResult("https://example.com/", checks=[Check("test", "Título", Status.PRESENT, '<script>alert("x")</script>', ['<img src=x onerror="x">'])])
        self.app.extensions["repository"].save(result)
        response = self.client.get("/auditorias/" + result.id)
        self.assertNotIn(b'<script>alert(', response.data)
        self.assertIn(b'&lt;script&gt;', response.data)
        self.assertEqual(self.client.get(f"/auditorias/{result.id}/relatorio.pdf").status_code, 200)

    def test_missing_and_oversized_requests(self):
        for path in ["/auditorias/missing", "/auditorias/missing/relatorio.pdf"]:
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.post("/auditorias", data={"url": "x" * 17000}).status_code, 413)

    def test_untrusted_host_is_rejected(self):
        response = self.client.get("/", headers={"Host": "unexpected.example"})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.content_type.startswith("text/plain"))
        self.assertNotIn(b"unexpected.example", response.data)

    def test_failed_collection_remains_error_and_not_run(self):
        class BrokenFetcher:
            def fetch(self, *args, **kwargs):
                raise AuditError("Conexão não concluída.")
        audit = Auditoria(BrokenFetcher()).executar("https://example.com")
        self.assertEqual(audit.checks[0].status, Status.ERROR)
        self.assertTrue(all(check.status == Status.NOT_RUN for check in audit.checks[1:]))

    def test_settings_key_never_echoes_and_requires_csrf(self):
        self.assertEqual(self.client.post('/configuracoes', data={'api_key':'private-test-key'}).status_code, 400)
        response = self.client.post('/configuracoes', data={'csrf':self.token(), 'api_key':'private-test-key', 'model':'gemini-3.5-flash-lite','browser':'edge'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'private-test-key', response.data)
        self.assertNotIn('private-test-key', (Path(self.directory.name)/'preferences.json').read_text())
        home = self.client.get('/')
        self.assertNotIn(b'name="use_ai" value="yes" disabled', home.data)

    def test_async_progress_and_parallel_analysis_rejection(self):
        started, release, finished = Event(), Event(), Event()
        original = self.app.extensions['auditor']
        class WaitingAuditor:
            def executar(self, url, **kwargs):
                started.set()
                release.wait(timeout=5)
                result = original.executar(url)
                finished.set()
                return result
        self.app.extensions['auditor'] = WaitingAuditor()
        data = {'csrf':self.token(), 'url':'https://example.com', 'authorized':'yes'}
        try:
            response = self.client.post('/auditorias', data=data, headers={'X-Audita-Async':'1'})
            self.assertEqual(response.status_code, 202)
            self.assertTrue(started.wait(timeout=2))
            self.assertEqual(self.client.get(response.json['progress_url']).json['state'], 'running')
            self.assertEqual(self.client.post('/auditorias', data=data, headers={'X-Audita-Async':'1'}).status_code, 409)
        finally:
            release.set()
            self.app.extensions['jobs'].executor.shutdown(wait=True)
        state = self.client.get(response.json['progress_url'])
        self.assertEqual(state.json['state'], 'done')
        self.assertEqual(self.client.get(state.json['result_url']).status_code, 200)

    def test_ai_results_render_and_missing_screenshot_is_404(self):
        audit = AuditResult('https://example.com', ai={'notice':'Fixture', 'model':'test', 'characters_sent':10, 'items':[
            {'title':'Finalidade','status':'identificado','quote':'<script>quoted</script>','explanation':'Texto de teste.'}]})
        self.app.extensions['repository'].save(audit)
        response = self.client.get('/auditorias/' + audit.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'&lt;script&gt;', response.data)
        self.assertEqual(self.client.get('/auditorias/' + audit.id + '/captura.png').status_code, 404)
        self.assertEqual(self.client.get('/auditorias/' + audit.id + '/relatorio.pdf').status_code, 200)
