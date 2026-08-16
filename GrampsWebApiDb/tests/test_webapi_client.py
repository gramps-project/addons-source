#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026 Douglas S. Blank <doug.blank@gmail.com>
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
#

"""
Unit tests for webapi_client.WebApiHandler and its helper functions.

No real Gramps Web API server is contacted: urlopen() is patched throughout,
via a small FakeResponse context manager and a queue of canned
responses/exceptions. Covers:

  - the GRAMPS_WEB_API_KEY codec (make_api_key/parse_api_key round trip)
  - JWT payload decoding
  - username/password vs. refresh-token authentication
  - the 429 rate-limit backoff-and-retry-once behavior
  - the "no /api prefix yet" fallback retry
  - 401 re-authentication on expired access tokens
  - transaction_history/push_transaction request shape

Run with::

    python3 -m unittest GrampsWebApiDb.tests.test_webapi_client -v
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import base64
import io
import json
import os
import sys
import tempfile
import unittest
from urllib.error import HTTPError, URLError
from unittest import mock

# -------------------------------------------------------------------------
#
# Make the addon importable the way Gramps loads it: its own directory on
# sys.path (grampswebapidb.py/webapi_client.py use bare, not package-
# relative, imports of each other -- see CLAUDE.md Testing conventions).
#
# -------------------------------------------------------------------------
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gramps  # noqa: F401  (only to trigger the SkipTest below if absent)
except ImportError as _err:
    raise unittest.SkipTest("gramps package not available: %s" % _err)

from GrampsWebApiDb import webapi_client
from GrampsWebApiDb.webapi_client import (
    WebApiHandler,
    WebApiPushConflict,
    decode_jwt_payload,
    make_api_key,
    parse_api_key,
)


# -------------------------------------------------------------------------
#
# Test helpers
#
# -------------------------------------------------------------------------
def b64url_json(payload: dict) -> str:
    """Base64url-encode a dict, stripped of padding, like a real JWT segment."""
    raw = json.dumps(payload).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def fake_jwt(payload: dict) -> str:
    """A JWT-shaped string whose payload segment decodes to ``payload``.

    decode_jwt_payload() only ever looks at segment [1], so the header and
    signature segments don't need to be real.
    """
    return f"header.{b64url_json(payload)}.signature"


def token(tag: str) -> str:
    """A distinct, real-JWT-shaped access token for ``tag``.

    Every access token this module hands back (even a canned "AT1"-style
    placeholder) is real enough to satisfy decode_jwt_payload(), because
    access_token's getter unconditionally checks the token's remaining
    lifetime -- see get_access_token_remaining_time().
    """
    return fake_jwt({"tag": tag})


class FakeResponse:
    """Stand-in for the object returned by ``urlopen(...).__enter__()``.

    ``status`` matters to push_transaction(), which distinguishes a 202
    ("the server queued a background task, go poll it") from a plain 200
    -- see that method's ``background`` param.
    """

    def __init__(self, body=None, headers=None, status=200):
        self._body = json.dumps(body if body is not None else {}).encode()
        self.headers = headers or {}
        self._status = status

    def read(self):
        return self._body

    def getcode(self):
        return self._status

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeBinaryResponse:
    """Like FakeResponse, but for endpoints that return a raw file body
    rather than JSON (see download_export()/_get_binary())."""

    def __init__(self, body: bytes, headers=None):
        self._body = body
        self.headers = headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeChunkedResponse:
    """Stand-in for a streamed download response: read(n) returns up to
    n bytes at a time, like a real socket-backed file object -- unlike
    FakeResponse.read(), which ignores any argument and returns
    everything at once. Needed for download_media_file(), which reads in
    a chunked loop."""

    def __init__(self, body: bytes, headers=None):
        self._buf = io.BytesIO(body)
        self.headers = headers or {}

    def read(self, size=-1):
        return self._buf.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def http_error(code, url="https://example.com/api"):
    return HTTPError(url, code, f"HTTP {code}", None, None)


def http_error_with_body(code, body, url="https://example.com/api"):
    """An HTTPError whose .read() yields a JSON-encoded body, the way a
    real gramps-web-api error response (abort_with_message()) looks."""
    fp = io.BytesIO(json.dumps(body).encode())
    return HTTPError(url, code, f"HTTP {code}", None, fp)


class QueuedUrlopen:
    """``urlopen`` replacement that returns/raises each queued item in turn,
    recording every ``Request`` it was called with."""

    def __init__(self, items):
        self._items = list(items)
        self.requests = []

    def __call__(self, req, context=None, timeout=None):
        self.requests.append(req)
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


# -------------------------------------------------------------------------
#
# TestApiKeyCodec
#
# -------------------------------------------------------------------------
class TestApiKeyCodec(unittest.TestCase):
    """make_api_key()/parse_api_key() are inverses, and reject malformed input."""

    def test_roundtrip(self):
        key = make_api_key("refresh-tok-123", "https://example.com/api")
        self.assertEqual(
            parse_api_key(key), ("refresh-tok-123", "https://example.com/api")
        )

    def test_roundtrip_with_padding_needed(self):
        # A URL whose base64url encoding needs '=' padding restored.
        url = "https://example.com/api/x"
        key = make_api_key("tok", url)
        self.assertEqual(parse_api_key(key), ("tok", url))

    def test_missing_delimiter_is_malformed(self):
        with self.assertRaises(ValueError):
            parse_api_key("no-delimiter-here")

    def test_bad_url_encoding_is_malformed(self):
        with self.assertRaises(ValueError):
            parse_api_key("tok*not-valid-base64---")

    def test_empty_token_is_rejected(self):
        encoded_url = base64.urlsafe_b64encode(b"https://example.com").decode()
        with self.assertRaises(ValueError):
            parse_api_key("*" + encoded_url)

    def test_empty_url_is_rejected(self):
        encoded_empty = base64.urlsafe_b64encode(b"").decode()
        with self.assertRaises(ValueError):
            parse_api_key("tok*" + encoded_empty)


# -------------------------------------------------------------------------
#
# TestDecodeJwtPayload
#
# -------------------------------------------------------------------------
class TestDecodeJwtPayload(unittest.TestCase):
    def test_decodes_payload_claims(self):
        jwt_str = fake_jwt({"sub": "user1", "exp": 1234})
        self.assertEqual(decode_jwt_payload(jwt_str), {"sub": "user1", "exp": 1234})

    def test_handles_payload_needing_padding(self):
        # Pick a payload whose base64url segment length isn't a multiple of 4,
        # to exercise the padding-restoration branch.
        jwt_str = fake_jwt({"a": "bit-of-text-to-shift-the-length"})
        payload = decode_jwt_payload(jwt_str)
        self.assertEqual(payload["a"], "bit-of-text-to-shift-the-length")


# -------------------------------------------------------------------------
#
# TestAuthentication
#
# -------------------------------------------------------------------------
class TestAuthentication(unittest.TestCase):
    """Constructing a handler authenticates once, via whichever credential
    was supplied."""

    def test_username_password_login(self):
        fake = QueuedUrlopen(
            [FakeResponse({"access_token": token("AT1"), "refresh_token": "RT1"})]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler(
                "https://example.com/api", username="alice", password="secret"
            )
        self.assertEqual(handler._access_token, token("AT1"))
        self.assertEqual(handler._refresh_token, "RT1")
        req = fake.requests[0]
        self.assertEqual(req.full_url, "https://example.com/api/token/")
        self.assertEqual(
            json.loads(req.data), {"username": "alice", "password": "secret"}
        )

    def test_refresh_token_login(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT2")})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT0")
        self.assertEqual(handler._access_token, token("AT2"))
        # Refresh token is unchanged; the endpoint used is /token/refresh/.
        self.assertEqual(handler._refresh_token, "RT0")
        req = fake.requests[0]
        self.assertEqual(req.full_url, "https://example.com/api/token/refresh/")
        self.assertEqual(req.get_header("Authorization"), "Bearer RT0")

    def test_mint_api_key_returns_encoded_key(self):
        fake = QueuedUrlopen(
            [FakeResponse({"access_token": token("AT1"), "refresh_token": "RT1"})]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            key = WebApiHandler.mint_api_key(
                "https://example.com/api", "alice", "secret"
            )
        self.assertEqual(parse_api_key(key), ("RT1", "https://example.com/api"))

    def test_mint_api_key_requires_refresh_token_in_response(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT1")})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(ValueError):
                WebApiHandler.mint_api_key("https://example.com/api", "alice", "pw")

    def test_from_env_missing_var_raises(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                WebApiHandler.from_env()

    def test_from_env_builds_handler_from_refresh_key(self):
        key = make_api_key("RT9", "https://example.com/api")
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT9")})])
        with mock.patch.dict(os.environ, {webapi_client.API_KEY_ENV_VAR: key}):
            with mock.patch.object(webapi_client, "urlopen", fake):
                handler = WebApiHandler.from_env()
        self.assertEqual(handler.url, "https://example.com/api")
        self.assertEqual(handler._access_token, token("AT9"))


# -------------------------------------------------------------------------
#
# TestAccessTokenProperty
#
# -------------------------------------------------------------------------
class TestAccessTokenProperty(unittest.TestCase):
    def _handler_with_token(self, exp_offset):
        """A handler whose access token expires ``exp_offset`` seconds from now."""
        fake = QueuedUrlopen(
            [FakeResponse({"access_token": fake_jwt({"exp": time_now() + exp_offset})})]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        return handler, fake

    def test_remaining_time_none_without_exp_claim(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": fake_jwt({})})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        self.assertIsNone(handler.get_access_token_remaining_time())

    def test_access_token_refreshes_when_near_expiry(self):
        handler, fake = self._handler_with_token(exp_offset=30)  # < 60s left
        fake._items.append(FakeResponse({"access_token": token("FRESH")}))
        with mock.patch.object(webapi_client, "urlopen", fake):
            refreshed = handler.access_token
        self.assertEqual(refreshed, token("FRESH"))
        self.assertEqual(len(fake.requests), 2)  # initial auth + re-auth

    def test_access_token_reused_when_far_from_expiry(self):
        handler, fake = self._handler_with_token(exp_offset=3600)
        access_token = handler.access_token
        self.assertEqual(len(fake.requests), 1)  # no re-auth triggered
        self.assertTrue(access_token)

    def test_get_permissions_reads_token_claim(self):
        fake = QueuedUrlopen(
            [
                FakeResponse(
                    {"access_token": fake_jwt({"permissions": ["edit", "view"]})}
                )
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        self.assertEqual(handler.get_permissions(), ["edit", "view"])


# -------------------------------------------------------------------------
#
# TestIdentity
#
# hostname/get_current_username()/get_identity() resolve who and where a
# credential authenticates as -- grampswebapidb.py's _check_identity() uses
# get_identity() to bind a local mirror to one particular server account
# (see that module's docstring).
#
# -------------------------------------------------------------------------
class TestIdentity(unittest.TestCase):
    def _handler(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT1")})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        return handler, fake

    def test_hostname_strips_scheme_and_path(self):
        handler, _fake = self._handler()
        self.assertEqual(handler.hostname, "example.com")

    def test_get_current_username_resolves_via_users_dash_and_caches(self):
        # A refresh-token credential (the normal from_env() path) carries
        # no plaintext username -- unlike get_permissions()'s claim, this
        # isn't in the JWT at all, so it takes a real GET /users/-/.
        handler, fake = self._handler()
        fake._items.append(FakeResponse({"name": "dblank"}))
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertEqual(handler.get_current_username(), "dblank")
        self.assertEqual(handler.username, "dblank")
        self.assertEqual(fake.requests[-1].full_url, "https://example.com/api/users/-/")

        # Cached: a second call makes no further request.
        fake._items.append(FakeResponse({"name": "someone-else"}))
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertEqual(handler.get_current_username(), "dblank")

    def test_get_current_username_skips_lookup_for_password_login(self):
        # A username+password login already knows its own username --
        # no need to ask the server to confirm it.
        fake = QueuedUrlopen(
            [FakeResponse({"access_token": token("AT1"), "refresh_token": "RT"})]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler(
                "https://example.com/api", username="dblank", password="pw"
            )
            self.assertEqual(handler.get_current_username(), "dblank")
        self.assertEqual(len(fake.requests), 1)

    def test_get_identity_combines_username_and_hostname(self):
        handler, fake = self._handler()
        fake._items.append(FakeResponse({"name": "dblank"}))
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertEqual(handler.get_identity(), "dblank@example.com")


def time_now():
    import time

    return time.time()


# -------------------------------------------------------------------------
#
# TestRateLimitAndFallbackRetries
#
# -------------------------------------------------------------------------
class TestRateLimitAndFallbackRetries(unittest.TestCase):
    """429 responses back off and retry once; a URL missing '/api' is
    retried with it appended."""

    def test_fetch_token_retries_once_after_429(self):
        fake = QueuedUrlopen(
            [
                http_error(429),
                FakeResponse({"access_token": token("AT"), "refresh_token": "RT"}),
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ) as mock_sleep:
            handler = WebApiHandler(
                "https://example.com/api", username="alice", password="pw"
            )
        self.assertEqual(handler._access_token, token("AT"))
        mock_sleep.assert_called_once_with(webapi_client.RATE_LIMIT_BACKOFF)

    def test_refresh_retries_once_after_429(self):
        fake = QueuedUrlopen(
            [http_error(429), FakeResponse({"access_token": token("AT")})]
        )
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        self.assertEqual(handler._access_token, token("AT"))

    def test_fetch_token_appends_api_prefix_on_non_rate_limit_error(self):
        fake = QueuedUrlopen(
            [
                http_error(404, url="https://example.com/token/"),
                FakeResponse({"access_token": token("AT"), "refresh_token": "RT"}),
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler(
                "https://example.com", username="alice", password="pw"
            )
        self.assertEqual(handler.url, "https://example.com/api")
        self.assertEqual(fake.requests[1].full_url, "https://example.com/api/token/")

    def test_fetch_token_does_not_re_append_api_prefix(self):
        # If the URL already ends in /api, a second failure must propagate
        # rather than looping.
        fake = QueuedUrlopen([http_error(404), http_error(404)])
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(HTTPError):
                WebApiHandler("https://example.com/api", username="a", password="p")


# -------------------------------------------------------------------------
#
# TestGetJsonRetries
#
# -------------------------------------------------------------------------
class TestGetJsonRetries(unittest.TestCase):
    """_get_json() re-authenticates on 401, backs off on 429, and retries
    once on a transient network error."""

    def _authed_handler(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT0")})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        return handler

    def test_401_triggers_reauth_and_one_retry(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                http_error(401),
                FakeResponse({"access_token": token("AT1")}),  # the re-auth call
                FakeResponse({"ok": True}),
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            body, _headers = handler._get_json("https://example.com/api/thing/")
        self.assertEqual(body, {"ok": True})
        self.assertEqual(handler._access_token, token("AT1"))

    def test_429_retries_once(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([http_error(429), FakeResponse({"ok": True})])
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            body, _headers = handler._get_json("https://example.com/api/thing/")
        self.assertEqual(body, {"ok": True})

    def test_network_error_retries_once(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [URLError("connection refused"), FakeResponse({"ok": True})]
        )
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            body, _headers = handler._get_json("https://example.com/api/thing/")
        self.assertEqual(body, {"ok": True})

    def test_second_failure_propagates(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([http_error(500), http_error(500)])
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(HTTPError):
                handler._get_json("https://example.com/api/thing/")


# -------------------------------------------------------------------------
#
# TestTransactionHistory
#
# -------------------------------------------------------------------------
class TestTransactionHistory(unittest.TestCase):
    def _authed_handler(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT0")})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        return handler

    def test_request_shape_and_total_count_header(self):
        handler = self._authed_handler()
        body = [{"id": 1, "timestamp": 10.0, "changes": []}]
        fake = QueuedUrlopen([FakeResponse(body, headers={"X-Total-Count": "5"})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            transactions, total = handler.get_transaction_history(
                after=100, page=2, pagesize=50
            )
        self.assertEqual(transactions, body)
        self.assertEqual(total, 5)
        url = fake.requests[0].full_url
        self.assertIn("after=100", url)
        self.assertIn("new=1", url)
        self.assertIn("sort=id", url)
        self.assertIn("page=2", url)
        self.assertIn("pagesize=50", url)

    def test_total_count_falls_back_to_body_length(self):
        handler = self._authed_handler()
        body = [{"id": 1, "timestamp": 1.0, "changes": []}] * 3
        fake = QueuedUrlopen([FakeResponse(body)])  # no X-Total-Count header
        with mock.patch.object(webapi_client, "urlopen", fake):
            _transactions, total = handler.get_transaction_history()
        self.assertEqual(total, 3)


# -------------------------------------------------------------------------
#
# TestDownloadExport
#
# -------------------------------------------------------------------------
class TestDownloadExport(unittest.TestCase):
    """download_export() (grampswebapidb.py's _full_resync() fallback)
    hits GET /exporters/<extension>/file and returns the raw body,
    sharing _get_binary()'s 401/429/network retry behavior with
    _get_json()."""

    def _authed_handler(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT0")})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        return handler

    def test_request_url_and_returns_raw_bytes(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeBinaryResponse(b"gzip-bytes-here")])
        with mock.patch.object(webapi_client, "urlopen", fake):
            data = handler.download_export()
        self.assertEqual(data, b"gzip-bytes-here")
        self.assertEqual(
            fake.requests[0].full_url, "https://example.com/api/exporters/gramps/file"
        )

    def test_on_chunk_streams_the_body_and_fires_between_chunks(self):
        # A multi-megabyte export read in one go is one uninterruptible
        # call -- long enough for the window manager to decide Gramps has
        # stopped responding. See grampswebapidb._pump_main_loop().
        handler = self._authed_handler()
        body = b"x" * (webapi_client._DOWNLOAD_CHUNK_SIZE * 2 + 17)
        fake = QueuedUrlopen([FakeChunkedResponse(body)])
        calls = []
        with mock.patch.object(webapi_client, "urlopen", fake):
            data = handler.download_export(on_chunk=lambda: calls.append(1))
        self.assertEqual(data, body)
        self.assertEqual(len(calls), 3)

    def test_without_on_chunk_the_body_is_read_in_one_go(self):
        # FakeBinaryResponse.read() takes no size argument, so this also
        # pins that the unchunked path stays a plain read().
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeBinaryResponse(b"gzip-bytes-here")])
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertEqual(handler.download_export(), b"gzip-bytes-here")

    def test_extension_is_configurable(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeBinaryResponse(b"gedcom-bytes")])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler.download_export(extension="ged")
        self.assertEqual(
            fake.requests[0].full_url, "https://example.com/api/exporters/ged/file"
        )

    def test_401_triggers_reauth_and_retry(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                http_error(401),
                FakeResponse({"access_token": token("AT1")}),  # the re-auth call
                FakeBinaryResponse(b"data-after-reauth"),
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            data = handler.download_export()
        self.assertEqual(data, b"data-after-reauth")

    def test_429_retries_once(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([http_error(429), FakeBinaryResponse(b"data")])
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            data = handler.download_export()
        self.assertEqual(data, b"data")

    def test_second_failure_propagates(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([http_error(500), http_error(500)])
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(HTTPError):
                handler.download_export()


# -------------------------------------------------------------------------
#
# TestGetMissingFiles
#
# -------------------------------------------------------------------------
class TestGetMissingFiles(unittest.TestCase):
    """get_missing_files() (grampswebapidb.py's _missing_remote_media_
    handles()) hits GET /media/?filemissing=1 and returns the decoded
    body as-is, sharing _get_json()'s retry behavior."""

    def _authed_handler(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT0")})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        return handler

    def test_request_url_and_returns_body(self):
        handler = self._authed_handler()
        body = [{"handle": "H1", "gramps_id": "O0001"}]
        fake = QueuedUrlopen([FakeResponse(body)])
        with mock.patch.object(webapi_client, "urlopen", fake):
            result = handler.get_missing_files()
        self.assertEqual(result, body)
        self.assertEqual(
            fake.requests[0].full_url,
            "https://example.com/api/media/?filemissing=1",
        )

    def test_empty_response(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse([])])
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertEqual(handler.get_missing_files(), [])


# -------------------------------------------------------------------------
#
# TestDownloadMediaFile
#
# -------------------------------------------------------------------------
class TestDownloadMediaFile(unittest.TestCase):
    """download_media_file() streams GET /media/<handle>/file to disk in
    chunks, creating any missing parent directory, and shares the same
    401/429/network retry-once behavior as the rest of this class."""

    def _authed_handler(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT0")})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        return handler

    def test_writes_body_to_path_and_creates_parent_dirs(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeChunkedResponse(b"binary-image-data")])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "dir", "photo.jpg")
            with mock.patch.object(webapi_client, "urlopen", fake):
                handler.download_media_file("H1", path)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"binary-image-data")
        self.assertEqual(
            fake.requests[0].full_url, "https://example.com/api/media/H1/file"
        )
        self.assertEqual(
            fake.requests[0].get_header("Authorization"), f"Bearer {token('AT0')}"
        )

    def test_streams_content_larger_than_one_chunk(self):
        handler = self._authed_handler()
        body = b"x" * (webapi_client._DOWNLOAD_CHUNK_SIZE * 2 + 100)
        fake = QueuedUrlopen([FakeChunkedResponse(body)])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "photo.jpg")
            with mock.patch.object(webapi_client, "urlopen", fake):
                handler.download_media_file("H1", path)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), body)

    def test_401_triggers_reauth_and_retry(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                http_error(401),
                FakeResponse({"access_token": token("AT1")}),
                FakeChunkedResponse(b"data-after-reauth"),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "photo.jpg")
            with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
                webapi_client, "sleep"
            ):
                handler.download_media_file("H1", path)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"data-after-reauth")

    def test_429_retries_once(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([http_error(429), FakeChunkedResponse(b"data")])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "photo.jpg")
            with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
                webapi_client, "sleep"
            ):
                handler.download_media_file("H1", path)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"data")

    def test_second_failure_propagates(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([http_error(500), http_error(500)])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "photo.jpg")
            with mock.patch.object(webapi_client, "urlopen", fake):
                with self.assertRaises(HTTPError):
                    handler.download_media_file("H1", path)


# -------------------------------------------------------------------------
#
# TestUploadMediaFile
#
# -------------------------------------------------------------------------
class TestUploadMediaFile(unittest.TestCase):
    """upload_media_file() streams a local file to PUT
    /media/<handle>/file?uploadmissing=1, returns False (rather than
    raising) on a 409, and shares the class's 401/429/network
    retry-once behavior otherwise."""

    def _authed_handler(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT0")})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        return handler

    def _tmp_file(self, tmp, content=b"local-bytes"):
        path = os.path.join(tmp, "photo.jpg")
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_request_url_and_method(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({})])
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tmp_file(tmp)
            with mock.patch.object(webapi_client, "urlopen", fake):
                result = handler.upload_media_file("H1", path)
        self.assertTrue(result)
        req = fake.requests[0]
        self.assertEqual(
            req.full_url, "https://example.com/api/media/H1/file?uploadmissing=1"
        )
        self.assertEqual(req.get_method(), "PUT")
        self.assertEqual(req.get_header("Authorization"), f"Bearer {token('AT0')}")

    def test_409_returns_false_without_retry(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([http_error(409)])
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tmp_file(tmp)
            with mock.patch.object(webapi_client, "urlopen", fake):
                result = handler.upload_media_file("H1", path)
        self.assertFalse(result)
        self.assertEqual(len(fake.requests), 1)

    def test_401_triggers_reauth_and_retry(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                http_error(401),
                FakeResponse({"access_token": token("AT1")}),
                FakeResponse({}),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tmp_file(tmp)
            with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
                webapi_client, "sleep"
            ):
                result = handler.upload_media_file("H1", path)
        self.assertTrue(result)
        self.assertEqual(handler._access_token, token("AT1"))

    def test_429_retries_once(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([http_error(429), FakeResponse({})])
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tmp_file(tmp)
            with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
                webapi_client, "sleep"
            ):
                result = handler.upload_media_file("H1", path)
        self.assertTrue(result)
        self.assertEqual(len(fake.requests), 2)

    def test_second_failure_propagates(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([http_error(500), http_error(500)])
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tmp_file(tmp)
            with mock.patch.object(webapi_client, "urlopen", fake):
                with self.assertRaises(HTTPError):
                    handler.upload_media_file("H1", path)


# -------------------------------------------------------------------------
#
# TestParseVersion
#
# -------------------------------------------------------------------------
class TestParseVersion(unittest.TestCase):
    def test_plain_version(self):
        self.assertEqual(webapi_client.parse_version("2.7.1"), (2, 7))

    def test_major_only_gets_a_zero_minor(self):
        self.assertEqual(webapi_client.parse_version("3"), (3, 0))

    def test_prerelease_and_build_suffixes_are_ignored(self):
        self.assertEqual(webapi_client.parse_version("2.7.0-rc1"), (2, 7))
        self.assertEqual(webapi_client.parse_version("2.7.0+dirty"), (2, 7))

    def test_unparseable_returns_none(self):
        # None rather than a guess, so callers can distinguish "old" from
        # "can't tell" -- see supports_background_transactions().
        self.assertIsNone(webapi_client.parse_version("unknown"))
        self.assertIsNone(webapi_client.parse_version(""))
        self.assertIsNone(webapi_client.parse_version(None))

    def test_trailing_garbage_after_a_numeric_prefix_is_truncated(self):
        self.assertEqual(webapi_client.parse_version("2.7.x"), (2, 7))


# -------------------------------------------------------------------------
#
# TestMetadata
#
# -------------------------------------------------------------------------
class TestMetadata(unittest.TestCase):
    METADATA = {
        "gramps": {"version": "6.0.1"},
        "gramps_webapi": {"version": "2.8.0", "schema": "2.8.0"},
    }

    def _authed_handler(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT0")})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        return handler

    def test_fetches_and_caches_metadata(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse(self.METADATA)])
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertEqual(handler.get_metadata(), self.METADATA)
            # Second call must not hit the network again.
            handler.get_metadata()
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(fake.requests[0].full_url, "https://example.com/api/metadata/")

    def test_version_accessors(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse(self.METADATA)])
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertEqual(handler.get_gramps_version(), "6.0.1")
            self.assertEqual(handler.get_api_version(), "2.8.0")

    def test_missing_sections_return_none(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertIsNone(handler.get_gramps_version())
            self.assertIsNone(handler.get_api_version())

    def test_background_supported_from_2_7(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({"gramps_webapi": {"version": "2.7.0"}})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertTrue(handler.supports_background_transactions())

    def test_background_not_supported_before_2_7(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({"gramps_webapi": {"version": "2.6.9"}})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertFalse(handler.supports_background_transactions())

    def test_unknown_version_does_not_claim_background_support(self):
        # The synchronous path works on every version, so it's the safe
        # answer when the version can't be determined.
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertFalse(handler.supports_background_transactions())

    def test_object_count_sums_every_type(self):
        handler = self._authed_handler()
        counts = {"object_counts": {"people": 4668, "families": 2855, "tags": 13}}
        fake = QueuedUrlopen([FakeResponse(counts)])
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertEqual(handler.get_object_count(), 4668 + 2855 + 13)

    def test_object_count_without_the_section_is_zero(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({"gramps": {"version": "6.0.1"}})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertEqual(handler.get_object_count(), 0)

    def test_object_count_ignores_non_numeric_entries(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [FakeResponse({"object_counts": {"people": 3, "note": "n/a"}})]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertEqual(handler.get_object_count(), 3)

    def test_object_count_is_not_served_from_the_metadata_cache(self):
        # Live state, unlike the versions get_metadata() caches: two calls
        # must produce two requests, and must not poison that cache.
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                FakeResponse({"object_counts": {"people": 1}}),
                FakeResponse({"object_counts": {"people": 2}}),
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            self.assertEqual(handler.get_object_count(), 1)
            self.assertEqual(handler.get_object_count(), 2)
        self.assertEqual(len(fake.requests), 2)
        self.assertIsNone(handler._metadata)


# -------------------------------------------------------------------------
#
# TestWaitForTask
#
# -------------------------------------------------------------------------
class TestWaitForTask(unittest.TestCase):
    """wait_for_task() polls GET /tasks/<id> until the backgrounded push
    finishes, translating a failed task into the same exceptions a
    synchronous push would raise."""

    def _authed_handler(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT0")})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        return handler

    def test_success_returns(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({"state": "SUCCESS"})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler.wait_for_task("T1")  # must not raise
        self.assertEqual(fake.requests[0].full_url, "https://example.com/api/tasks/T1")

    def test_polls_until_the_task_leaves_pending(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                FakeResponse({"state": "PENDING"}),
                FakeResponse({"state": "STARTED"}),
                FakeResponse({"state": "SUCCESS"}),
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            handler.wait_for_task("T1")
        self.assertEqual(len(fake.requests), 3)

    def test_on_wait_fires_once_per_poll(self):
        # TASK_TIMEOUT allows ten minutes of this loop; a caller on the
        # GUI thread has to be able to keep its main loop alive across it.
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                FakeResponse({"state": "PENDING"}),
                FakeResponse({"state": "STARTED"}),
                FakeResponse({"state": "SUCCESS"}),
            ]
        )
        calls = []
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            handler.wait_for_task("T1", on_wait=lambda: calls.append(1))
        # Once before each of the two sleeps; the SUCCESS poll returns
        # without waiting again.
        self.assertEqual(len(calls), 2)

    def test_conflict_in_a_failed_task_raises_push_conflict(self):
        # The whole point: a conflict must look the same whether it came
        # back as a synchronous 400 or as a failed background task.
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [FakeResponse({"state": "FAILURE", "info": "Object has changed"})]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(WebApiPushConflict):
                handler.wait_for_task("T1")

    def test_structured_error_payload_is_preferred(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                FakeResponse(
                    {
                        "state": "FAILURE",
                        "result_object": {
                            "error": {"code": 400, "message": "Object has changed"}
                        },
                        "info": "something less specific",
                    }
                )
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(WebApiPushConflict):
                handler.wait_for_task("T1")

    def test_other_failure_raises_value_error_with_the_message(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [FakeResponse({"state": "FAILURE", "info": "Gramps ID missing"})]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(ValueError) as ctx:
                handler.wait_for_task("T1")
        self.assertNotIsInstance(ctx.exception, WebApiPushConflict)
        self.assertIn("Gramps ID missing", str(ctx.exception))

    def test_revoked_is_also_a_failure(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({"state": "REVOKED", "info": "cancelled"})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(ValueError):
                handler.wait_for_task("T1")

    def test_timeout_raises_timeout_error(self):
        # TimeoutError is an OSError, so grampswebapidb.py's connection-error
        # handling treats a stuck task as retryable rather than a refusal.
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({"state": "PENDING"})] * 10)
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            with self.assertRaises(TimeoutError):
                handler.wait_for_task("T1", timeout=-1)
        self.assertIsInstance(TimeoutError(), OSError)


# -------------------------------------------------------------------------
#
# TestPushTransaction
#
# -------------------------------------------------------------------------
class TestPushTransaction(unittest.TestCase):
    def _authed_handler(self):
        fake = QueuedUrlopen([FakeResponse({"access_token": token("AT0")})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler = WebApiHandler("https://example.com/api", refresh_token="RT")
        return handler

    def test_empty_payload_sends_no_request(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler.push_transaction([])
        self.assertEqual(fake.requests, [])

    def test_non_empty_payload_posts_without_force(self):
        # No force=1: the server's old-data-mismatch check must run, or
        # WebApiPushConflict can never fire -- see push_transaction()'s
        # docstring.
        handler = self._authed_handler()
        payload = [{"type": "add", "handle": "H1", "_class": "Person"}]
        fake = QueuedUrlopen([FakeResponse({})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler.push_transaction(payload)
        req = fake.requests[0]
        self.assertEqual(req.full_url, "https://example.com/api/transactions/")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(json.loads(req.data), payload)
        self.assertEqual(req.get_header("Authorization"), f"Bearer {token('AT0')}")

    def test_undo_appends_query_param(self):
        handler = self._authed_handler()
        payload = [{"type": "add", "handle": "H1", "_class": "Person"}]
        fake = QueuedUrlopen([FakeResponse({})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler.push_transaction(payload, undo=True)
        req = fake.requests[0]
        self.assertEqual(req.full_url, "https://example.com/api/transactions/?undo=1")
        # The payload itself is the original (forward) one -- the server
        # reverses it, not the caller. See push_transaction()'s docstring.
        self.assertEqual(json.loads(req.data), payload)

    def test_undo_defaults_to_false(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler.push_transaction([{"type": "add"}])
        self.assertEqual(
            fake.requests[0].full_url, "https://example.com/api/transactions/"
        )

    def test_undo_flag_survives_401_retry(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                http_error(401),
                FakeResponse({"access_token": token("AT1")}),
                FakeResponse({}),
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            handler.push_transaction([{"type": "add"}], undo=True)
        # requests[0] = failed push, [1] = re-auth, [2] = retried push
        self.assertEqual(
            fake.requests[2].full_url, "https://example.com/api/transactions/?undo=1"
        )

    def test_401_triggers_reauth_and_retry(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                http_error(401),
                FakeResponse({"access_token": token("AT1")}),
                FakeResponse({}),
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            handler.push_transaction([{"type": "add"}])
        self.assertEqual(handler._access_token, token("AT1"))

    def test_429_retries_once(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([http_error(429), FakeResponse({})])
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            handler.push_transaction([{"type": "add"}])
        self.assertEqual(len(fake.requests), 2)

    def test_object_changed_400_raises_push_conflict(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                http_error_with_body(
                    400, {"error": {"code": 400, "message": "Object has changed"}}
                )
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(WebApiPushConflict):
                handler.push_transaction([{"type": "add"}])
        # Not retried -- a conflict isn't transient, so exactly one request.
        self.assertEqual(len(fake.requests), 1)

    def test_other_400_reasons_are_not_conflicts(self):
        # e.g. a payload item missing a required Gramps ID -- our own bug,
        # not a concurrent edit -- must propagate as a plain HTTPError.
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                http_error_with_body(
                    400, {"error": {"code": 400, "message": "Gramps ID missing"}}
                )
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(HTTPError) as ctx:
                handler.push_transaction([{"type": "add"}])
        self.assertNotIsInstance(ctx.exception, WebApiPushConflict)

    def test_background_appends_query_param(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler.push_transaction([{"type": "add"}], background=True)
        self.assertIn("background=1", fake.requests[0].full_url)

    def test_background_combines_with_undo(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({})])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler.push_transaction([{"type": "add"}], undo=True, background=True)
        url = fake.requests[0].full_url
        self.assertIn("undo=1", url)
        self.assertIn("background=1", url)

    def test_202_response_waits_for_the_task(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                FakeResponse(
                    {"task": {"id": "T7", "href": "/api/tasks/T7"}}, status=202
                ),
                FakeResponse({"state": "SUCCESS"}),
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler.push_transaction([{"type": "add"}], background=True)
        self.assertEqual(fake.requests[1].full_url, "https://example.com/api/tasks/T7")

    def test_200_response_in_background_mode_does_not_poll(self):
        # A server without a Celery queue runs the work inline and answers
        # 200 even for ?background=1 -- nothing left to wait for.
        handler = self._authed_handler()
        fake = QueuedUrlopen([FakeResponse({}, status=200)])
        with mock.patch.object(webapi_client, "urlopen", fake):
            handler.push_transaction([{"type": "add"}], background=True)
        self.assertEqual(len(fake.requests), 1)

    def test_conflict_from_a_backgrounded_task_raises_push_conflict(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                FakeResponse({"task": {"id": "T7"}}, status=202),
                FakeResponse({"state": "FAILURE", "info": "Object has changed"}),
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(WebApiPushConflict):
                handler.push_transaction([{"type": "add"}], background=True)

    def test_500_carrying_the_conflict_message_is_a_conflict(self):
        # run_task() re-wraps process_transactions()'s "Object has changed"
        # ValueError as a 500 when it runs the work inline, so the same
        # conflict arrives with a different status code -- it must not be
        # mistaken for a transient server error.
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                http_error_with_body(
                    500, {"error": {"code": 500, "message": "Object has changed"}}
                )
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(WebApiPushConflict):
                handler.push_transaction([{"type": "add"}], background=True)

    def test_ordinary_500_still_propagates_as_http_error(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                http_error_with_body(
                    500, {"error": {"code": 500, "message": "Database is locked"}}
                )
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(HTTPError) as ctx:
                handler.push_transaction([{"type": "add"}])
        self.assertNotIsInstance(ctx.exception, WebApiPushConflict)

    def test_background_flag_survives_401_retry(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen(
            [
                http_error(401),
                FakeResponse({"access_token": token("AT1")}),
                FakeResponse({}),
            ]
        )
        with mock.patch.object(webapi_client, "urlopen", fake), mock.patch.object(
            webapi_client, "sleep"
        ):
            handler.push_transaction([{"type": "add"}], background=True)
        self.assertIn("background=1", fake.requests[2].full_url)

    def test_400_with_unparseable_body_propagates_as_http_error(self):
        handler = self._authed_handler()
        fake = QueuedUrlopen([http_error_with_body(400, "not-a-dict-body")])
        with mock.patch.object(webapi_client, "urlopen", fake):
            with self.assertRaises(HTTPError) as ctx:
                handler.push_transaction([{"type": "add"}])
        self.assertNotIsInstance(ctx.exception, WebApiPushConflict)


if __name__ == "__main__":
    unittest.main()
