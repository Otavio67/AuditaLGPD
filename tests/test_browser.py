import unittest
import json
from unittest.mock import Mock
from auditalgpd.browser_proxy import proxy_target, PublicProxy
from auditalgpd.browser_worker import cookie_inventory, fit_screenshot, navigation_error, page_cookies, page_network
from auditalgpd.security import UnsafeURL


class BrowserResultTests(unittest.TestCase):
    def test_blocked_navigation_names_status_and_suggests_simple_mode(self):
        message = navigation_error({"status": 403})
        self.assertIn("HTTP 403", message)
        self.assertIn("análise simples", message)
        self.assertIn("Nenhuma nota", message)
        self.assertIn("HTTP 500", navigation_error({"status": 500}))
        self.assertIn("não conseguiu se conectar", navigation_error({"status": 502}))
        self.assertIn("não retornou", navigation_error(None))

    def test_large_screenshot_is_reduced_not_discarded(self):
        from io import BytesIO
        import os
        from PIL import Image
        noise = Image.frombytes("RGB", (900, 700), os.urandom(900 * 700 * 3))
        buffer = BytesIO()
        noise.save(buffer, "PNG")
        large = buffer.getvalue()
        self.assertGreater(len(large), 1_000_000)
        reduced = fit_screenshot(large)
        self.assertTrue(reduced.startswith(b"\x89PNG"))
        self.assertLessEqual(len(reduced), 1_000_000)
        self.assertLess(Image.open(BytesIO(reduced)).width, 900)
        small = b"\x89PNG small"
        self.assertIs(fit_screenshot(small), small)
        self.assertEqual(fit_screenshot(b"not an image" * 200_000), b"")


class BrowserSafetyTests(unittest.TestCase):
    def test_proxy_rejects_private_destinations_and_nonstandard_ports(self):
        for target, connect in [("127.0.0.1:443", True), ("10.0.0.1:443", True), ("example.org:8443", True),
                                ("http://localhost/", False), ("http://example.org:8080/", False)]:
            with self.subTest(target=target), self.assertRaises(UnsafeURL):
                proxy_target(target, connect)

    def test_proxy_connects_to_validated_ip_not_dns_name(self):
        connector = Mock()
        proxy = PublicProxy(resolver=lambda *_: ["93.184.216.34"], connector=connector)
        try:
            proxy.open_public(proxy_target("example.org:443", True))
            connector.assert_called_once_with(("93.184.216.34", 443), timeout=5)
        finally:
            proxy.server_close()

    def test_proxy_falls_back_to_next_validated_address(self):
        connector = Mock(side_effect=[TimeoutError("sem rota"), "socket"])
        proxy = PublicProxy(resolver=lambda *_: ["34.223.124.45", "2600:1f13::1"], connector=connector)
        try:
            self.assertEqual(proxy.open_public(proxy_target("example.org:443", True)), "socket")
            self.assertEqual([c.args[0] for c in connector.call_args_list], [("34.223.124.45", 443), ("2600:1f13::1", 443)])
            connector.side_effect = TimeoutError("sem rota")
            with self.assertRaises(OSError):
                proxy.open_public(proxy_target("example.org:443", True))
        finally:
            proxy.server_close()

    def test_inventory_never_contains_cookie_value(self):
        result = cookie_inventory([{"name": "sid", "domain": "example.org", "value": "SECRET", "secure": True, "httpOnly": True}])
        self.assertNotIn("SECRET", str(result))
        self.assertNotIn("value", result[0])

    def test_browser_background_cookies_are_not_attributed_to_page(self):
        cookies = [{"name":"background", "domain":".bing.com"}, {"name":"page", "domain":".example.org"}]
        self.assertEqual([c["name"] for c in page_cookies(cookies, ["www.example.org"])], ["page"])
        self.assertEqual(page_cookies(cookies, ["notexample.org"]), [])

    def test_network_events_from_old_page_are_not_attributed_to_current_loader(self):
        def request(url, loader):
            return {'message':json.dumps({'message':{'method':'Network.requestWillBeSent','params':{
                'frameId':'main','loaderId':loader,'request':{'url':url}}}})}
        events = [request('https://ntp.msn.com/old', 'old'), request('https://example.org/current', 'new')]
        domains, _ = page_network(events, {'main':'new'}, 'main')
        self.assertEqual(domains, ['example.org'])
