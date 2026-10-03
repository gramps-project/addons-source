# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       scotCW
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Tests for remembering a sync token instead of the password.

After a password login, the addon creates a sync token for this computer
(``POST /api/users/-/access-tokens/sync/tokens/``) and stores it in the
password's place. Later runs exchange it for an access token
(``POST /api/token/sync/``), so the password is neither stored nor needed.
"""

from __future__ import annotations

import base64
import io
import json
import time
import unittest
from unittest import mock
from urllib.error import HTTPError

from const import AUTH_PASSWORD, AUTH_SYNC_TOKEN, SYNC_TOKEN_LABEL_MAX_LENGTH
from presentation import error_message
from session import ErrorKind, State
from webapihandler import SyncTokensUnsupported, WebApiHandler, device_label

from .fakes import http_error
from .scenario import DEFAULT_URL as URL
from .scenario import T1, SyncScenario
from .test_credentials import FakeKeyring, StoreTestCase

TOKEN = "test-sync-token"


class TokenSessionTest(unittest.TestCase):
    """The session storing and using a sync token."""

    def setUp(self) -> None:
        self.scenario = SyncScenario()
        self.addCleanup(self.scenario.close)
        self.scenario.seed_person("I0001")
        self.scenario.share()

    def test_a_remembered_password_login_stores_a_token_instead(self) -> None:
        self.scenario.run()
        self.assertEqual(self.scenario.server.token_labels, [device_label()])
        self.assertEqual(
            self.scenario.credentials.saved[-1], (URL, "owner", "sync-token-1")
        )
        self.assertEqual(self.scenario.credentials.auth, AUTH_SYNC_TOKEN)
        self.assertEqual(
            self.scenario.backend_calls, [(URL, "owner", "secret", AUTH_PASSWORD)]
        )

    def test_without_remembering_no_token_is_created(self) -> None:
        self.scenario.run(remember_password=False)
        self.assertEqual(self.scenario.server.token_labels, [])
        self.assertIsNone(self.scenario.credentials.password)
        self.assertEqual(self.scenario.credentials.auth, AUTH_PASSWORD)

    def test_a_server_without_sync_tokens_keeps_the_password(self) -> None:
        """Gramps Web API from before per-device sync tokens."""
        self.scenario.server.sync_tokens = False
        result = self.scenario.run()
        self.assertEqual(self.scenario.credentials.saved[-1], (URL, "owner", "secret"))
        self.assertEqual(self.scenario.credentials.auth, AUTH_PASSWORD)
        self.assertIsNot(result.session.state, State.CONNECT)

    def test_failing_to_create_a_token_never_fails_the_login(self) -> None:
        self.scenario.server.fail_next("create_sync_token", http_error(500))
        result = self.scenario.run()
        self.assertIsNone(result.session.login_error)
        self.assertEqual(self.scenario.credentials.saved[-1], (URL, "owner", "secret"))
        self.assertEqual(self.scenario.credentials.auth, AUTH_PASSWORD)

    def test_no_token_for_a_server_that_is_turned_away(self) -> None:
        self.scenario.server.task_queue = False
        result = self.scenario.run()
        self.assertIs(result.session.login_error.kind, ErrorKind.SERVER_NO_TASK_QUEUE)
        self.assertEqual(self.scenario.server.token_labels, [])

    def test_a_stored_token_signs_in_without_creating_another(self) -> None:
        self.scenario.local.add_person("I0002", changed_at=T1)
        result = self.scenario.run(password=TOKEN, auth=AUTH_SYNC_TOKEN)
        self.assertEqual(
            self.scenario.backend_calls, [(URL, "owner", TOKEN, AUTH_SYNC_TOKEN)]
        )
        self.assertEqual(self.scenario.server.token_labels, [])
        self.assertEqual(self.scenario.credentials.saved[-1], (URL, "owner", TOKEN))
        self.assertEqual(self.scenario.credentials.auth, AUTH_SYNC_TOKEN)
        self.assertIs(result.final_state, State.DONE)
        self.assertIsNotNone(self.scenario.remote.person("I0002"))

    def test_a_rejected_stored_token_is_forgotten(self) -> None:
        """Revoked in Gramps Web: the password is asked for instead."""
        self.scenario.server.fail_next("get_api_version", http_error(401))
        result = self.scenario.run(password=TOKEN, auth=AUTH_SYNC_TOKEN)
        self.assertIs(result.session.state, State.CONNECT)
        self.assertIs(result.session.login_error.kind, ErrorKind.AUTH_FAILED)
        self.assertEqual(self.scenario.credentials.forgotten, [(URL, "owner")])

    def test_a_wrong_password_forgets_nothing(self) -> None:
        self.scenario.server.fail_next("get_api_version", http_error(401))
        self.scenario.run()
        self.assertEqual(self.scenario.credentials.forgotten, [])


class TokenCredentialStoreTest(StoreTestCase):
    """How :class:`adapters.ConfigCredentialStore` keeps a sync token."""

    def test_entries_from_before_sync_tokens_hold_a_password(self) -> None:
        store = self.make_store()
        store.save_credentials(URL, "owner", "secret")
        self.assertEqual(store.get_auth(), AUTH_PASSWORD)

    def test_a_stored_token_is_offered_again(self) -> None:
        config, keyring = self.make_config(), FakeKeyring()
        self.make_store(config, keyring).save_credentials(
            URL, "owner", TOKEN, auth=AUTH_SYNC_TOKEN
        )
        reopened = self.make_store(config, keyring)
        self.assertEqual(reopened.get_auth(), AUTH_SYNC_TOKEN)
        self.assertEqual(reopened.get_password(), TOKEN)

    def test_not_remembering_stores_no_token(self) -> None:
        store = self.make_store()
        store.save_credentials(
            URL, "owner", TOKEN, remember_password=False, auth=AUTH_SYNC_TOKEN
        )
        self.assertEqual(store.get_auth(), AUTH_PASSWORD)
        self.assertIsNone(store.get_password())

    def test_forgetting_the_secret_keeps_the_entry_and_baseline(self) -> None:
        keyring = FakeKeyring()
        store = self.make_store(keyring=keyring)
        store.save_credentials(URL, "owner", TOKEN, auth=AUTH_SYNC_TOKEN)
        store.set_timestamp(URL, "owner", 123.0)
        store.forget_secret(URL, "owner")
        self.assertIsNone(store.get_password())
        self.assertEqual(store.get_auth(), AUTH_PASSWORD)
        self.assertEqual(store.get_url(), URL)
        self.assertEqual(store.get_timestamp(URL, "owner"), 123.0)
        self.assertIn((URL, "owner"), keyring.deleted)


class TokenErrorMessageTest(unittest.TestCase):
    """Wording for a stored sync token the server no longer accepts."""

    def test_a_rejected_saved_sign_in_asks_for_the_password(self) -> None:
        message = error_message(ErrorKind.AUTH_FAILED, "401", AUTH_SYNC_TOKEN)
        self.assertIn("enter your password", message)
        self.assertNotIn("check your username", message)

    def test_forbidden_does_not_mention_the_password(self) -> None:
        message = error_message(ErrorKind.FORBIDDEN, "403", AUTH_SYNC_TOKEN)
        self.assertNotIn("password", message.lower())

    def test_other_errors_keep_their_wording(self) -> None:
        for kind in (ErrorKind.NOT_FOUND, ErrorKind.TREE_DISABLED):
            with self.subTest(kind=kind):
                self.assertEqual(
                    error_message(kind, "", AUTH_SYNC_TOKEN), error_message(kind)
                )

    def test_password_wording_is_unchanged(self) -> None:
        self.assertIn(
            "username and password", error_message(ErrorKind.AUTH_FAILED, "401")
        )


def jwt(**claims) -> str:
    """Return an unsigned JWT; the handler only reads its payload."""
    payload = {"exp": time.time() + 900, **claims}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"x.{body.rstrip('=')}.y"


class FakeHttp:
    """Answers the handler's requests and records them.

    :param routes: ``(method, url)`` -> a JSON body, an HTTP status to fail
        with, or a list of those, answered in turn.
    """

    def __init__(self, routes: dict) -> None:
        self.routes = routes
        self.requests: list = []

    def __call__(self, req, context=None, timeout=None):
        self.requests.append(req)
        answer = self.routes.get((req.get_method(), req.full_url), 404)
        if isinstance(answer, list):
            answer = answer.pop(0)
        if isinstance(answer, int):
            raise HTTPError(req.full_url, answer, "fake", {}, None)  # type: ignore[arg-type]
        return io.BytesIO(json.dumps(answer).encode() if answer is not None else b"")

    def calls(self) -> list[tuple[str, str]]:
        return [(r.get_method(), r.full_url) for r in self.requests]

    def bodies(self) -> list:
        return [json.loads(r.data) if r.data else None for r in self.requests]


TOKENS = f"{URL}/users/-/access-tokens/sync/tokens/"


class TokenHandlerTest(unittest.TestCase):
    """:class:`webapihandler.WebApiHandler` talking to the API."""

    def http(self, routes: dict) -> FakeHttp:
        fake = FakeHttp(routes)
        for target, value in (
            ("webapihandler.urlopen", fake),
            # No macOS keychain lookup for an SSL context in these tests.
            ("webapihandler.platform.system", lambda: "Linux"),
        ):
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        return fake

    def login(self, routes: dict) -> tuple[WebApiHandler, FakeHttp, str]:
        access = jwt()
        http = self.http(
            {("POST", f"{URL}/token/"): {"access_token": access}, **routes}
        )
        return WebApiHandler(URL, "owner", "secret"), http, access

    def test_creating_a_token_posts_the_label(self) -> None:
        handler, http, access = self.login(
            {("POST", TOKENS): {"id": 1, "token": TOKEN}}
        )
        self.assertEqual(handler.create_sync_token("Laptop"), TOKEN)
        self.assertEqual(http.calls()[-1], ("POST", TOKENS))
        self.assertEqual(http.bodies()[-1], {"label": "Laptop"})
        self.assertEqual(
            http.requests[-1].get_header("Authorization"), f"Bearer {access}"
        )

    def test_signing_in_again_replaces_this_computers_token(self) -> None:
        handler, http, _ = self.login(
            {
                ("POST", TOKENS): [409, {"id": 7, "token": "new"}],
                ("GET", TOKENS): [
                    [{"id": 3, "label": "Desktop"}, {"id": 5, "label": "Laptop"}]
                ],
                ("DELETE", f"{TOKENS}5/"): None,
            }
        )
        self.assertEqual(handler.create_sync_token("Laptop"), "new")
        self.assertEqual(
            http.calls()[1:],
            [
                ("POST", TOKENS),
                ("GET", TOKENS),
                ("DELETE", f"{TOKENS}5/"),
                ("POST", TOKENS),
            ],
        )

    def test_the_maximum_still_fails(self) -> None:
        """No token of this computer to replace: the second attempt fails too."""
        handler, _, _ = self.login(
            {
                ("POST", TOKENS): [409, 409],
                ("GET", TOKENS): [[{"id": 3, "label": "Desktop"}]],
            }
        )
        with self.assertRaises(HTTPError):
            handler.create_sync_token("Laptop")

    def test_a_server_without_sync_tokens_is_recognised(self) -> None:
        for status in (404, 405, 422):
            with self.subTest(status=status):
                handler, _, _ = self.login({("POST", TOKENS): status})
                with self.assertRaises(SyncTokensUnsupported):
                    handler.create_sync_token("Laptop")

    def test_a_stored_token_is_exchanged_at_the_sync_endpoint(self) -> None:
        http = self.http({("POST", f"{URL}/token/sync/"): {"access_token": jwt()}})
        WebApiHandler(URL, "owner", TOKEN, auth=AUTH_SYNC_TOKEN)
        self.assertEqual(http.calls(), [("POST", f"{URL}/token/sync/")])
        self.assertEqual(http.bodies(), [{"token": TOKEN}])

    def test_an_expiring_access_token_is_exchanged_again(self) -> None:
        """There is no refresh token: the sync token is simply sent again."""
        http = self.http(
            {
                ("POST", f"{URL}/token/sync/"): {
                    "access_token": jwt(exp=time.time() + 30)
                }
            }
        )
        handler = WebApiHandler(URL, "owner", TOKEN, auth=AUTH_SYNC_TOKEN)
        handler.access_token  # pylint: disable=pointless-statement
        self.assertEqual(http.bodies(), [{"token": TOKEN}, {"token": TOKEN}])

    def test_a_password_login_is_unchanged(self) -> None:
        _, http, _ = self.login({})
        self.assertEqual(http.bodies(), [{"username": "owner", "password": "secret"}])


class DeviceLabelTest(unittest.TestCase):
    """The label that names this computer's token in Gramps Web."""

    def test_names_the_host_without_its_domain(self) -> None:
        with mock.patch("webapihandler.socket.gethostname", lambda: "laptop.lan"):
            self.assertEqual(device_label(), "Gramps Web Sync on laptop")

    def test_stays_within_the_servers_limit(self) -> None:
        with mock.patch("webapihandler.socket.gethostname", lambda: "x" * 300):
            self.assertEqual(len(device_label()), SYNC_TOKEN_LABEL_MAX_LENGTH)
