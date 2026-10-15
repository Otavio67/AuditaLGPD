import io
from email.message import Message
import unittest
from unittest.mock import patch

from auditalgpd.security import AuditError, SafeFetcher, UnsafeURL, normalize_url, resolve_public


class Response:
    def __init__(self, body=b"<html>ok</html>", status=200, headers=None):
        self.status = status
        self.body = io.BytesIO(body)
        self.headers = Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"
        for key, value in (headers or {}).items():
            self.headers.replace_header(key, value) if key in self.headers else self.headers.__setitem__(key, value)

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def read1(self, size):
        return self.body.read(size)


class Connection:
    def __init__(self, response):
        self.response = response
        self.closed = False

    def request(self, *args, **kwargs):
        self.request_args = args

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class SecurityTests(unittest.TestCase):
    def test_rejects_private_schemes_ports_and_credentials(self):
        for url in ["http://127.0.0.1", "http://10.1.1.1", "http://169.254.169.254", "http://[::1]",
                    "http://[::ffff:127.0.0.1]", "http://224.0.0.1", "http://localhost", "http://machine.local",
                    "file:///etc/passwd", "https://user:pass@example.org", "https://example.org:8080",
                    "https://example.org\r\nX: injected", "http://2130706433", "http://127.1"]:
            with self.subTest(url=url), self.assertRaises(UnsafeURL):
                normalize_url(url)

    def test_resolver_rejects_mixed_public_private_answers(self):
        records = [(2, 1, 6, "", ("93.184.216.34", 443)), (2, 1, 6, "", ("127.0.0.1", 443))]
        with patch("socket.getaddrinfo", return_value=records), self.assertRaises(UnsafeURL):
            resolve_public("example.org", 443)

    def test_redirect_is_checked_before_second_connection(self):
        connections = []
        def connector(*args):
            connections.append(Connection(Response(status=302, headers={"Location": "http://127.0.0.1/admin"})))
            return connections[-1]
        fetcher = SafeFetcher(resolver=lambda *_: ["93.184.216.34"], connector=connector)
        with self.assertRaises(UnsafeURL):
            fetcher.fetch("https://example.org")
        self.assertEqual(len(connections), 1)
        self.assertTrue(connections[0].closed)

    def test_collector_pins_validated_address_and_limits_body(self):
        calls = []
        def connector(target, address, timeout):
            calls.append(address)
            return Connection(Response(b"123456"))
        fetcher = SafeFetcher(max_bytes=5, resolver=lambda *_: ["93.184.216.34"], connector=connector)
        with self.assertRaises(AuditError):
            fetcher.fetch("https://example.org")
        self.assertEqual(calls, ["93.184.216.34"])

    def test_policy_cannot_leave_origin(self):
        fetcher = SafeFetcher(resolver=lambda *_: ["93.184.216.34"])
        with self.assertRaises(UnsafeURL):
            fetcher.fetch("https://other.example.org/privacy", origin=("https", "example.org", 443))

    def test_html_is_required(self):
        fetcher = SafeFetcher(resolver=lambda *_: ["93.184.216.34"], connector=lambda *_: Connection(Response(headers={"Content-Type": "application/pdf"})))
        with self.assertRaises(AuditError):
            fetcher.fetch("https://example.org")
