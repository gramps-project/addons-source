#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021-2024 David Straub
# Copyright (C) 2026      Douglas S. Blank <doug.blank@gmail.com>
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
Minimal Gramps Web API client: authentication and read access.

Trimmed from the WebApiHandler class in the GrampsWebSync addon (same
repo, same license) -- credit to David Straub for the original token
fetch/refresh and SSL-context handling. Dropped everything specific to
GrampsWebSync's push-a-local-transaction / XML-export / media-file-sync
job, since WebApiDB only needs auth plus reading the transaction-history
feed for now. Re-add pieces here (rather than importing GrampsWebSync
directly) so this addon has no runtime dependency on another addon being
installed.

This file is a vendored copy: the canonical, standalone source is now the
gramps-api-client package (not yet published; local checkout at
~/gramps/gramps-api-client as of this writing), module
gramps_api_client/client.py, class Client -- the same class as
WebApiHandler below, just renamed. It was split out so the client could
be discoverable/pip-installable on its own, independent of the Gramps
addon ecosystem. Gramps addons are self-contained tarballs with no
mechanism to declare a pip dependency, so this copy has to stay vendored
here rather than importing that package directly; sync changes by hand in
both directions.

Credentials
-----------
Two ways in: username+password (POST /token/, matches GrampsWebSync), or
a GRAMPS_WEB_API_KEY-shaped string: "<REFRESH_TOKEN>*<BASE64URL(URL)>".

The REFRESH_TOKEN half is a JWT *refresh* token obtained once via
POST /token/ with include_refresh (gramps-web-api's JWT_REFRESH_TOKEN_EXPIRES
is False by default, so it doesn't expire on its own). From then on,
POST /token/refresh/ trades it for fresh short-lived access tokens --
no username/password re-entry, no server-side change needed. This is
*not* the same as a real scoped/revocable personal access token
(gramps-web-api has that machinery too, but today it's hardcoded to a
single "anniversaries_ics" scope and isn't wired into general request
auth) -- it's a shortcut that works today at the cost of not being
independently revocable. '*' is a safe delimiter here: neither a JWT
(base64url segments joined by '.') nor base64url output ever contains it.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import platform
import socket
import time
from tempfile import NamedTemporaryFile
from time import sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LOG = logging.getLogger("grampswebapidb")

#: Environment variable read by WebApiHandler.from_env().
API_KEY_ENV_VAR = "GRAMPS_WEB_API_KEY"

#: Seconds before a request that has produced nothing is abandoned. Without
#: this, ``urlopen`` waits forever and an unreachable-but-listening server
#: hangs Gramps with no way out.
TIMEOUT = 60

#: gramps-web-api rate-limits /token/ and /token/refresh/ to 1/second (no
#: Retry-After header is sent on 429); this is how long to back off before
#: the one retry attempt. Found by live testing: minting a key and then
#: immediately constructing another WebApiHandler in the same second
#: reliably 429s otherwise.
RATE_LIMIT_BACKOFF = 1.1

#: The exact message gramps_webapi/api/tasks.py's old_unchanged() check
#: raises as ValueError("Object has changed"), which POST /transactions/
#: (without force=1) surfaces as HTTP 400 {"error": {"message": ...}}.
#: push_transaction() matches on this to tell a real conflict apart from
#: the endpoint's other 400s (malformed payload, missing Gramps ID, ...),
#: which are our own bugs, not conflicts, and should propagate as-is.
_CONFLICT_MESSAGE = "Object has changed"


class WebApiPushConflict(Exception):
    """A push was rejected because the server-side object changed since
    the local mirror's snapshot of it (see push_transaction())."""


def _raise_for_push_conflict(exc: HTTPError) -> None:
    """Given a 400 from POST /transactions/, raise WebApiPushConflict if
    it's the server's old-data-mismatch check; otherwise re-raise ``exc``
    unchanged (a genuinely different 400, e.g. a malformed payload)."""
    try:
        body = json.loads(exc.read())
        message = body["error"]["message"]
    except (ValueError, KeyError, TypeError):
        raise exc
    if message == _CONFLICT_MESSAGE:
        raise WebApiPushConflict(message) from exc
    raise exc


def create_macos_ssl_context():
    """Create an SSL context using macOS system certificates."""
    import ssl
    import subprocess

    ctx = ssl.create_default_context()
    macos_ca_certs = subprocess.run(
        [
            "security",
            "find-certificate",
            "-a",
            "-p",
            "/System/Library/Keychains/SystemRootCertificates.keychain",
        ],
        stdout=subprocess.PIPE,
    ).stdout

    with NamedTemporaryFile("w+b") as tmp_file:
        tmp_file.write(macos_ca_certs)
        ctx.load_verify_locations(tmp_file.name)

    return ctx


def decode_jwt_payload(jwt: str) -> dict[str, Any]:
    """Decode and return the payload from a JWT."""
    payload_part = jwt.split(".")[1]
    padding = len(payload_part) % 4
    if padding > 0:
        payload_part += "=" * (4 - padding)
    decoded_bytes = base64.urlsafe_b64decode(payload_part)
    decoded_str = decoded_bytes.decode("utf-8")
    return json.loads(decoded_str)


def parse_api_key(api_key: str) -> tuple[str, str]:
    """Split a GRAMPS_WEB_API_KEY value into ``(refresh_token, url)``."""
    try:
        token, encoded_url = api_key.split("*", 1)
    except ValueError as exc:
        raise ValueError(
            "Malformed GRAMPS_WEB_API_KEY: expected '<TOKEN>*<ENCODED-URL>'"
        ) from exc
    padding = "=" * (-len(encoded_url) % 4)
    try:
        url = base64.urlsafe_b64decode(encoded_url + padding).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Malformed GRAMPS_WEB_API_KEY: bad URL encoding") from exc
    if not token or not url:
        raise ValueError("Malformed GRAMPS_WEB_API_KEY: empty token or URL")
    return token, url


def make_api_key(refresh_token: str, url: str) -> str:
    """Build a GRAMPS_WEB_API_KEY value from a refresh token and URL."""
    encoded_url = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii")
    return f"{refresh_token}*{encoded_url.rstrip('=')}"


class WebApiHandler:
    """Web API connection handler: token auth plus authenticated GET."""

    def __init__(
        self,
        url: str,
        username: str | None = None,
        password: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        """
        Initialize given a server URL, plus either a username+password or
        a non-expiring refresh token (exactly one of the two is expected).
        """
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._ctx = (
            create_macos_ssl_context() if platform.system() == "Darwin" else None
        )
        self._authenticate()

    @classmethod
    def from_api_key(cls, api_key: str) -> "WebApiHandler":
        """Build a handler from a GRAMPS_WEB_API_KEY-shaped string."""
        token, url = parse_api_key(api_key)
        return cls(url, refresh_token=token)

    @classmethod
    def from_env(cls, env_var: str = API_KEY_ENV_VAR) -> "WebApiHandler":
        """
        Build a handler from an environment variable holding a
        GRAMPS_WEB_API_KEY-shaped string. This is the SDK entry point:
        ``client = WebApiHandler.from_env()``.
        """
        api_key = os.environ.get(env_var)
        if not api_key:
            raise ValueError(f"{env_var} is not set")
        return cls.from_api_key(api_key)

    @classmethod
    def mint_api_key(cls, url: str, username: str, password: str) -> str:
        """
        One-time username+password login that returns a GRAMPS_WEB_API_KEY
        value for all future non-interactive use. This is the client-side
        half of what a future "Generate SDK Key" UI button would automate
        server-side; until that exists, this is how a key gets created at
        all.
        """
        handler = cls(url, username=username, password=password)
        if not handler._refresh_token:
            raise ValueError("Server did not return a refresh token")
        return make_api_key(handler._refresh_token, handler.url)

    def _open(self, req: Request):
        """Open ``req`` with this handler's SSL context and timeout."""
        return urlopen(req, context=self._ctx, timeout=TIMEOUT)

    @property
    def access_token(self) -> str:
        """Get the access token. Cached after first call unless refresh needed."""
        if not self._access_token:
            self._authenticate()
        remaining_time = self.get_access_token_remaining_time()
        if remaining_time is not None and remaining_time < 60:
            self._authenticate()
        assert self._access_token  # for type checker
        return self._access_token

    def get_access_token_remaining_time(self) -> int | None:
        """Get the remaining time of the access token in seconds."""
        if self._access_token is None:
            return None
        payload = decode_jwt_payload(self._access_token)
        if "exp" not in payload:
            return None
        expires = payload["exp"]
        now = time.time()
        return int(expires - now)

    def _authenticate(self) -> None:
        """Get a fresh access token, via whichever credential we hold."""
        if self._refresh_token:
            self._refresh_access_token()
        else:
            self.fetch_token()

    def fetch_token(self, retry_on_rate_limit: bool = True) -> None:
        """Fetch and store an access token via username+password."""
        LOG.debug("Fetching an access token from the server")
        data = json.dumps({"username": self.username, "password": self.password})
        req = Request(
            f"{self.url}/token/",
            data=data.encode(),
            headers={"Content-Type": "application/json", "User-Agent": "GrampsWebApiDb"},
        )
        try:
            with self._open(req) as res:
                res_json = json.load(res)
        except HTTPError as exc:
            if exc.code == 429 and retry_on_rate_limit:
                sleep(RATE_LIMIT_BACKOFF)
                return self.fetch_token(retry_on_rate_limit=False)
            if "/api" not in self.url:
                self.url = f"{self.url}/api"
                return self.fetch_token(retry_on_rate_limit=retry_on_rate_limit)
            raise
        except (UnicodeDecodeError, json.JSONDecodeError):
            if "/api" not in self.url:
                self.url = f"{self.url}/api"
                return self.fetch_token(retry_on_rate_limit=retry_on_rate_limit)
            raise
        self._access_token = res_json["access_token"]
        # /token/ with username+password always includes a refresh token
        # (TokenResource.post() calls get_tokens(..., include_refresh=True)).
        if "refresh_token" in res_json:
            self._refresh_token = res_json["refresh_token"]

    def _refresh_access_token(self, retry_on_rate_limit: bool = True) -> None:
        """Trade the stored refresh token for a new access token."""
        LOG.debug("Refreshing access token from stored refresh token")
        req = Request(
            f"{self.url}/token/refresh/",
            method="POST",
            headers={
                "Authorization": f"Bearer {self._refresh_token}",
                "User-Agent": "GrampsWebApiDb",
            },
        )
        try:
            with self._open(req) as res:
                res_json = json.load(res)
        except HTTPError as exc:
            if exc.code == 429 and retry_on_rate_limit:
                sleep(RATE_LIMIT_BACKOFF)
                return self._refresh_access_token(retry_on_rate_limit=False)
            if "/api" not in self.url:
                self.url = f"{self.url}/api"
                return self._refresh_access_token(retry_on_rate_limit=retry_on_rate_limit)
            raise
        except (UnicodeDecodeError, json.JSONDecodeError):
            if "/api" not in self.url:
                self.url = f"{self.url}/api"
                return self._refresh_access_token(retry_on_rate_limit=retry_on_rate_limit)
            raise
        self._access_token = res_json["access_token"]

    def get_permissions(self) -> set[str]:
        """Get the permissions of the current user."""
        return decode_jwt_payload(self.access_token).get("permissions", set())

    def _get_json(self, url: str, retry: bool = True) -> tuple[Any, dict]:
        """GET ``url`` with the bearer token and return ``(body, headers)``."""
        req = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "User-Agent": "GrampsWebApiDb",
            },
        )
        try:
            with self._open(req) as res:
                return json.load(res), dict(res.headers)
        except HTTPError as exc:
            if exc.code == 401 and retry:
                # in case of 401, retry once with a new token
                sleep(RATE_LIMIT_BACKOFF)  # avoid immediately re-tripping the rate limit
                self._authenticate()
                return self._get_json(url, retry=False)
            if exc.code == 429 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                return self._get_json(url, retry=False)
            raise
        except (URLError, socket.timeout):
            if retry:
                sleep(1)
                return self._get_json(url, retry=False)
            raise

    def get_transaction_history(
        self, after: float = 0, page: int = 1, pagesize: int = 100
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Fetch one page of the server's transaction history committed
        after ``after`` (a Unix timestamp), ascending by transaction id,
        including the post-change raw object data.

        :returns: ``(transactions, total_count)``. ``total_count`` comes
            from the ``X-Total-Count`` response header, so the caller can
            tell whether more pages remain.
        """
        params = {
            "after": after,
            "new": "1",
            "sort": "id",
            "page": page,
            "pagesize": pagesize,
        }
        url = f"{self.url}/transactions/history/?{urlencode(params)}"
        body, headers = self._get_json(url)
        total_count = int(headers.get("X-Total-Count", len(body)))
        return body, total_count

    def push_transaction(
        self, payload: list[dict[str, Any]], retry: bool = True
    ) -> None:
        """
        POST a batch of local changes to /transactions/ (no force=1): the
        server compares each item's "old" snapshot -- the local mirror's
        state of the object *before* the local edit -- against its own
        current data, and rejects the whole batch with HTTP 400
        ``{"error": {"message": "Object has changed"}}`` on any mismatch
        (see gramps_webapi/api/tasks.py's process_transactions ->
        old_unchanged()). That's a real, if coarse, optimistic-concurrency
        check: it fires whenever the server-side object was edited (by
        anyone) since the local mirror last synced, which is exactly what
        a conflict is. Raised here as WebApiPushConflict so the caller
        (grampswebapidb.py's transaction_commit) can tell "the server
        rejected this because something changed underneath it" apart from
        a network/auth failure. Actual merge resolution is still out of
        scope -- the caller's response to a conflict is to resync from the
        server, not to retry the push.
        """
        if not payload:
            return
        data = json.dumps(payload).encode()
        req = Request(
            f"{self.url}/transactions/",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
                "User-Agent": "GrampsWebApiDb",
            },
        )
        try:
            with self._open(req) as res:
                res.read()
        except HTTPError as exc:
            if exc.code == 401 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                self._authenticate()
                return self.push_transaction(payload, retry=False)
            if exc.code == 429 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                return self.push_transaction(payload, retry=False)
            if exc.code == 400:
                _raise_for_push_conflict(exc)
            raise
        except (URLError, socket.timeout):
            if retry:
                sleep(RATE_LIMIT_BACKOFF)
                return self.push_transaction(payload, retry=False)
            raise
