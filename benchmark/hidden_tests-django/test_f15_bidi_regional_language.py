"""f15: right-to-left detection must work for regional language codes such as
he-il or fa-ir, not only for the bare base language."""

from django.template import Context, Engine
from django.template.context_processors import i18n
from django.test import RequestFactory, SimpleTestCase
from django.utils import translation

TEMPLATE = "{% load i18n %}{% get_current_language_bidi as bidi %}{{ bidi }}"


class RegionalBidiTests(SimpleTestCase):
    def render(self, language):
        engine = Engine(libraries={"i18n": "django.templatetags.i18n"})
        with translation.override(language):
            return engine.from_string(TEMPLATE).render(Context())

    def test_template_tag_regional_rtl(self):
        for language in ("he-il", "fa-ir", "ar-sa", "ur-pk"):
            with self.subTest(language=language):
                self.assertEqual(self.render(language), "True")

    def test_template_tag_base_and_ltr(self):
        self.assertEqual(self.render("he"), "True")
        self.assertEqual(self.render("de-at"), "False")
        self.assertEqual(self.render("en-us"), "False")

    def test_context_processor_regional(self):
        request = RequestFactory().get("/")
        with translation.override("he-il"):
            self.assertIs(i18n(request)["LANGUAGE_BIDI"], True)
        with translation.override("pt-br"):
            self.assertIs(i18n(request)["LANGUAGE_BIDI"], False)
