"""c13: SECURE_CROSS_ORIGIN_EMBEDDER_POLICY makes SecurityMiddleware send a
Cross-Origin-Embedder-Policy header (default None: no header)."""

from django.conf import settings
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.test import RequestFactory, SimpleTestCase, override_settings

HEADER = "Cross-Origin-Embedder-Policy"


class CrossOriginEmbedderPolicyTests(SimpleTestCase):
    def process(self, response=None):
        request = RequestFactory().get("/")
        middleware = SecurityMiddleware(lambda req: response or HttpResponse())
        return middleware(request)

    def test_default_is_none_and_sends_no_header(self):
        self.assertIsNone(settings.SECURE_CROSS_ORIGIN_EMBEDDER_POLICY)
        self.assertNotIn(HEADER, self.process())

    @override_settings(SECURE_CROSS_ORIGIN_EMBEDDER_POLICY="require-corp")
    def test_header_sent_with_configured_value(self):
        self.assertEqual(self.process().headers[HEADER], "require-corp")

    @override_settings(SECURE_CROSS_ORIGIN_EMBEDDER_POLICY="credentialless")
    def test_other_value(self):
        self.assertEqual(self.process().headers[HEADER], "credentialless")

    @override_settings(SECURE_CROSS_ORIGIN_EMBEDDER_POLICY="require-corp")
    def test_existing_header_left_alone(self):
        response = HttpResponse()
        response.headers[HEADER] = "unsafe-none"
        self.assertEqual(self.process(response).headers[HEADER], "unsafe-none")

    @override_settings(SECURE_CROSS_ORIGIN_EMBEDDER_POLICY=None)
    def test_none_sends_no_header(self):
        self.assertNotIn(HEADER, self.process())
