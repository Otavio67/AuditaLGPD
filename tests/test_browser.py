import unittest
import json
from unittest.mock import Mock
from auditalgpd.browser_proxy import proxy_target, PublicProxy
from auditalgpd.browser_worker import cookie_inventory, page_cookies, page_network
from auditalgpd.security import UnsafeURL


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
