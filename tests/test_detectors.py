import unittest
from auditalgpd.audit import analyze_page
from auditalgpd.detectors import parse_html, find_policy
from auditalgpd.domain import Status


class DetectorTests(unittest.TestCase):
    def test_invalid_or_script_policy_links_are_ignored(self):
        soup = parse_html('<a href="javascript:alert(1)">Privacidade</a><a href="http://[">Privacidade</a>')
        self.assertEqual(find_policy(soup, "https://example.com/"), [])

    def checks(self, html):
        return {item.key: item for item in analyze_page(html, "https://example.org/", True)}

    def test_banner_and_personal_form_are_identified_without_values(self):
        html = '<aside id="cookie-banner">Cookies <button>Recusar</button></aside><form><input type="email" value="segredo@example.org"></form>'
        checks = self.checks(html)
        self.assertEqual(checks["banner"].status, Status.PRESENT)
        self.assertEqual(checks["forms"].status, Status.PRESENT)
        self.assertNotIn("segredo", str(checks["forms"].evidence))

    def test_script_hidden_banner_and_search_are_not_positive(self):
        html = '<script>cookie_banner = true</script><div hidden id="cookies">Cookies<button>Aceitar</button></div><form><input type="search" name="q"></form>'
        checks = self.checks(html)
        self.assertEqual(checks["banner"].status, Status.ABSENT)
        self.assertEqual(checks["forms"].status, Status.ABSENT)

    def test_cookie_word_in_footer_is_not_a_banner(self):
        self.assertEqual(self.checks('<footer>Política de cookies</footer>')["banner"].status, Status.ABSENT)

    def test_policy_links_are_resolved_and_limited(self):
        soup = parse_html('<a href="/privacidade">Política de privacidade</a><a href="/privacidade">Privacidade</a>')
        self.assertEqual(find_policy(soup, "https://example.org/"), ["https://example.org/privacidade"])
