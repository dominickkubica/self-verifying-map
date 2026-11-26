"""c14: `manage.py check --exclude-tag TAG` (repeatable) skips checks carrying
that tag; every other check, tagged or untagged, still runs."""

from io import StringIO

from django.core import checks
from django.core.management import call_command
from django.test import SimpleTestCase
from django.test.utils import override_system_checks


def alpha_check(app_configs=None, **kwargs):
    return [checks.Warning("alpha ran", id="hidden.W001")]


def beta_check(app_configs=None, **kwargs):
    return [checks.Warning("beta ran", id="hidden.W002")]


def untagged_check(app_configs=None, **kwargs):
    return [checks.Warning("untagged ran", id="hidden.W003")]


def alpha_beta_check(app_configs=None, **kwargs):
    return [checks.Warning("alpha-beta ran", id="hidden.W004")]


alpha_check.tags = ("alpha",)
beta_check.tags = ("beta",)
untagged_check.tags = ()
alpha_beta_check.tags = ("alpha", "beta")

ALL = [alpha_check, beta_check, untagged_check, alpha_beta_check]


@override_system_checks(ALL)
class CheckExcludeTagTests(SimpleTestCase):
    def run_check(self, *args):
        out, err = StringIO(), StringIO()
        call_command("check", *args, stdout=out, stderr=err)
        return out.getvalue() + err.getvalue()

    def test_without_option_all_checks_run(self):
        output = self.run_check()
        for check_id in ("hidden.W001", "hidden.W002", "hidden.W003", "hidden.W004"):
            self.assertIn(check_id, output)

    def test_exclude_one_tag(self):
        output = self.run_check("--exclude-tag", "alpha")
        self.assertNotIn("hidden.W001", output)
        self.assertNotIn("hidden.W004", output)
        self.assertIn("hidden.W002", output)
        self.assertIn("hidden.W003", output)

    def test_exclude_tag_is_repeatable(self):
        output = self.run_check("--exclude-tag", "alpha", "--exclude-tag", "beta")
        self.assertNotIn("hidden.W001", output)
        self.assertNotIn("hidden.W002", output)
        self.assertNotIn("hidden.W004", output)
        self.assertIn("hidden.W003", output)
