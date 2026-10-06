import importlib
from types import SimpleNamespace
from unittest import mock

from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import TestCase
from django.urls import reverse

from .adapters import SocialAdapter
from .middleware import user_marker
from .models import Task

User = get_user_model()
PASSWORD = "Tr0ub4dor&3xyz"


class AuthPageTests(TestCase):
    def test_anonymous_visitors_are_sent_to_login_and_keep_their_place(self):
        response = self.client.get("/tasks/?q=rice")
        self.assertRedirects(response, "/accounts/login/?next=/tasks/%3Fq%3Drice", fetch_redirect_response=False)

    def test_login_page_has_back_button_and_password_toggle(self):
        html = self.client.get(reverse("account_login")).content.decode()
        self.assertIn("data-back", html)
        self.assertIn("data-pw-toggle", html)
        self.assertNotIn("autofocus", html)  # would pop the keyboard up on phones

    def test_signup_lists_every_password_problem_not_just_the_first(self):
        response = self.client.post(reverse("account_signup"), {
            "username": "maria", "email": "m@example.com",
            "password1": "abc", "password2": "abc",
        })
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("too short", html)
        self.assertIn("too common", html)
        self.assertIn('aria-invalid="true"', html)
        self.assertFalse(User.objects.filter(username="maria").exists())

    def test_signup_logs_the_new_user_in(self):
        response = self.client.post(reverse("account_signup"), {
            "username": "maria", "email": "m@example.com",
            "password1": PASSWORD, "password2": PASSWORD,
        })
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_pages_do_not_load_anything_from_other_sites(self):
        response = self.client.get(reverse("account_login"))
        policy = response.headers["Content-Security-Policy"]
        self.assertNotIn("googleapis", policy)
        self.assertNotIn("gstatic", policy)
        self.assertNotIn("<script>", response.content.decode())  # no inline scripts

    def test_pwa_meta_has_no_inline_script(self):
        # django-pwa's own template adds one, which the CSP blocks
        self.assertNotIn("<script", self.client.get(reverse("account_login")).content.decode().split("</head>")[0])


class OfflineSupportTests(TestCase):
    def setUp(self):
        self.maria = User.objects.create_user("maria", password=PASSWORD)
        self.sam = User.objects.create_user("sam", password=PASSWORD)

    def test_signed_in_pages_carry_a_per_user_tag_for_the_service_worker(self):
        self.client.login(username="maria", password=PASSWORD)
        tag = self.client.get("/").headers["X-Hangarin-Uid"]
        self.assertEqual(tag, user_marker(self.maria))
        self.assertNotEqual(tag, user_marker(self.sam))
        self.assertRegex(tag, r"^[0-9a-f]{16}$")  # a hash, not the account id

    def test_anonymous_pages_have_no_tag_so_they_are_never_saved(self):
        self.assertNotIn("X-Hangarin-Uid", self.client.get(reverse("account_login")).headers)

    def test_signed_in_pages_are_not_kept_by_the_browser_cache(self):
        self.client.login(username="maria", password=PASSWORD)
        cache_control = self.client.get("/").headers["Cache-Control"]
        self.assertIn("private", cache_control)
        self.assertIn("no-cache", cache_control)

    def test_offline_page_manifest_and_worker_work_without_logging_in(self):
        for path in ("/offline/", "/manifest.json", "/serviceworker.js"):
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_worker_only_queues_the_paths_the_server_accepts(self):
        # the pattern in serviceworker.js must stay in step with urls.py
        for name, args in (("task-create", []), ("task-update", [1]), ("task-delete", [1]),
                           ("task-toggle-status", [1]), ("subtask-toggle-status", [1]),
                           ("note-create", []), ("category-create", []), ("priority-create", [])):
            path = reverse(name, args=args)
            self.assertRegex(path, r"^/(tasks|subtasks|notes|categories|priorities)/(new/|\d+/(edit|delete|toggle-status)/)$", name)

    def test_status_toggle_works_with_no_request_body(self):
        # this is exactly what the status buttons send, and what gets replayed
        task = Task.objects.create(owner=self.maria, title="Rice", status="Pending")
        self.client.login(username="maria", password=PASSWORD)
        response = self.client.post(reverse("task-toggle-status", args=[task.pk]),
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "In Progress")

    def test_nobody_can_open_or_change_someone_elses_task(self):
        task = Task.objects.create(owner=self.maria, title="Private", status="Pending")
        self.client.login(username="sam", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("task-detail", args=[task.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("task-toggle-status", args=[task.pk])).status_code, 404)


class SiteDomainMigrationTests(TestCase):
    def setUp(self):
        self.migration = importlib.import_module("todo.migrations.0005_site_domain")

    def test_placeholder_domain_is_replaced(self):
        Site.objects.update(domain="example.com", name="example.com")
        self.migration.fix_site_domain(apps, None)
        self.assertNotEqual(Site.objects.get().domain, "example.com")

    def test_a_domain_someone_chose_is_left_alone(self):
        Site.objects.update(domain="tasks.mycollege.edu", name="Mine")
        self.migration.fix_site_domain(apps, None)
        self.assertEqual(Site.objects.get().domain, "tasks.mycollege.edu")


class SocialLoginMatchingTests(TestCase):
    """Signing in with Google/GitHub when the same email already has an account."""

    def setUp(self):
        self.owner = User.objects.create_user("maria", "maria@example.com", PASSWORD)
        self.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))

    def login(self, email, verified, existing=False):
        return SimpleNamespace(
            is_existing=existing,
            email_addresses=[EmailAddress(email=email, verified=verified, primary=True)],
            account=SimpleNamespace(get_provider=lambda: SimpleNamespace(name="GitHub")),
            connect=mock.Mock(),
        )

    def run_adapter(self, sociallogin):
        with mock.patch("todo.adapters.messages"):
            SocialAdapter().pre_social_login(self.request, sociallogin)

    def test_verified_email_joins_the_existing_account(self):
        sociallogin = self.login("Maria@Example.com", verified=True)
        self.run_adapter(sociallogin)
        sociallogin.connect.assert_called_once_with(self.request, self.owner)
        self.assertTrue(EmailAddress.objects.get(user=self.owner, email="maria@example.com").verified)

    def test_unverified_email_is_not_trusted(self):
        sociallogin = self.login("maria@example.com", verified=False)
        with self.assertRaises(ImmediateHttpResponse):
            self.run_adapter(sociallogin)
        sociallogin.connect.assert_not_called()

    def test_a_new_email_carries_on_to_normal_sign_up(self):
        sociallogin = self.login("someone.new@example.com", verified=True)
        self.run_adapter(sociallogin)
        sociallogin.connect.assert_not_called()

    def test_an_already_linked_login_is_left_alone(self):
        sociallogin = self.login("maria@example.com", verified=True, existing=True)
        self.run_adapter(sociallogin)
        sociallogin.connect.assert_not_called()

    def test_two_accounts_on_one_email_is_never_guessed(self):
        User.objects.create_user("maria2", "maria@example.com", PASSWORD)
        sociallogin = self.login("maria@example.com", verified=True)
        with self.assertRaises(ImmediateHttpResponse):
            self.run_adapter(sociallogin)
        sociallogin.connect.assert_not_called()
