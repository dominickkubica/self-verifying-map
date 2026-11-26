"""f16: with SESSION_EXPIRE_AT_BROWSER_CLOSE = True the session cookie must be
a browser-session cookie (no Max-Age, no Expires)."""

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings


def make_view(expiry=None):
    def view(request):
        request.session["key"] = "value"
        if expiry is not None:
            request.session.set_expiry(expiry)
        return HttpResponse()

    return view


@override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies")
class ExpireAtBrowserCloseTests(SimpleTestCase):
    def cookie(self, view):
        response = SessionMiddleware(view)(RequestFactory().get("/"))
        return response.cookies[settings.SESSION_COOKIE_NAME]

    @override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=True)
    def test_setting_gives_browser_session_cookie(self):
        cookie = self.cookie(make_view())
        self.assertEqual(cookie["max-age"], "")
        self.assertEqual(cookie["expires"], "")

    @override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=True)
    def test_explicit_expiry_overrides_setting(self):
        cookie = self.cookie(make_view(expiry=3600))
        self.assertEqual(int(cookie["max-age"]), 3600)

    def test_default_cookie_is_persistent(self):
        cookie = self.cookie(make_view())
        self.assertEqual(int(cookie["max-age"]), settings.SESSION_COOKIE_AGE)
        self.assertNotEqual(cookie["expires"], "")

    def test_set_expiry_zero(self):
        cookie = self.cookie(make_view(expiry=0))
        self.assertEqual(cookie["max-age"], "")
        self.assertEqual(cookie["expires"], "")
