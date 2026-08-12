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
fetch/refresh and SSL-context handling. Originally dropped everything
specific to GrampsWebSync's push-a-local-transaction / XML-export /
media-file-sync job, since WebApiDB only needed auth plus reading the
transaction-history feed; media-file-sync (get_missing_files(),
download_media_file(), upload_media_file()) has since been ported back in
for grampswebapidb.py's own unattended media sync -- see that module's
docstring. Re-add pieces here (rather than importing GrampsWebSync
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
from urllib.parse import urlencode, urlparse
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

#: Chunk size used when streaming a media file download to disk -- see
#: download_media_file().
_DOWNLOAD_CHUNK_SIZE = 1024 * 64

#: First gramps-web-api version whose POST /transactions/ understands
#: ?background=1 (same gate GrampsWebSync's webapihandler.commit() uses).
BACKGROUND_MIN_API_VERSION = (2, 7)

#: How long to keep polling GET /tasks/<id> for a backgrounded push before
#: giving up, and how long to wait between polls. The give-up is a
#: TimeoutError (an OSError subclass), so callers that treat connection
#: errors as retryable pick it up as one.
TASK_TIMEOUT = 600
TASK_POLL_INTERVAL = 1.0

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


def parse_version(version):
    """Parse a SemVer-ish string into a ``(major, minor)`` tuple.

    Dependency-free, and tolerant of the pre-release/build suffixes a
    development build carries ("2.7.0-rc1", "2.7.0+dirty"). Returns None
    if the string doesn't start with something numeric, so callers can
    treat "I can't tell" differently from "it's old".

    Ported from GrampsWebSync's webapihandler.parse_version() (same repo,
    same license, credit David Straub), plus the None fallback.
    """
    if not version:
        return None
    main_version = str(version).split("-", 1)[0].split("+", 1)[0]
    parts = []
    for part in main_version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            break
    if not parts:
        return None
    if len(parts) == 1:
        parts.append(0)
    return (parts[0], parts[1])


def _task_error_message(body):
    """Pull a human-readable failure message out of a GET /tasks/<id>
    body for a FAILURE/REVOKED task.

    The server reports the same underlying result three ways -- a
    structured "result_object" (a {"error": {...}} dict when the task
    aborted through TaskError), plus "info"/"result" stringifications
    kept for backward compatibility (see gramps_webapi/api/resources/
    tasks.py). Prefer the structured form, fall back to the strings.
    """
    payload = body.get("result_object")
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if error:
            return str(error)
    for key in ("info", "result"):
        value = body.get(key)
        if value:
            return str(value)
    return "unknown error"


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
        self._metadata: dict[str, Any] | None = None
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
            headers={
                "Content-Type": "application/json",
                "User-Agent": "GrampsWebApiDb",
            },
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
                return self._refresh_access_token(
                    retry_on_rate_limit=retry_on_rate_limit
                )
            raise
        except (UnicodeDecodeError, json.JSONDecodeError):
            if "/api" not in self.url:
                self.url = f"{self.url}/api"
                return self._refresh_access_token(
                    retry_on_rate_limit=retry_on_rate_limit
                )
            raise
        self._access_token = res_json["access_token"]

    def get_permissions(self) -> set[str]:
        """Get the permissions of the current user."""
        return decode_jwt_payload(self.access_token).get("permissions", set())

    @property
    def hostname(self) -> str:
        """Server hostname, e.g. "hadaly.duckdns.org" for a url of
        "https://hadaly.duckdns.org/api"."""
        return urlparse(self.url).hostname or self.url

    def get_current_username(self) -> str:
        """Name of the user this handler is authenticated as.

        Set directly for a username+password login (mint_api_key()); the
        refresh-token credential the normal from_env() path uses carries no
        plaintext username (the access token's "sub" claim is a user id,
        not a name -- see gramps-web-api's token.py), so it is resolved
        once via GET /users/-/ (the "current user" alias) and cached here.
        """
        if self.username is None:
            data, _headers = self._get_json(f"{self.url}/users/-/")
            self.username = data["name"]
        return self.username

    def get_metadata(self) -> dict[str, Any]:
        """Server metadata (GET /metadata/), cached for this handler's
        lifetime -- it describes the deployment, which doesn't change
        while a tree is open. Needs no special permission beyond being
        authenticated (metadata.py's MetadataResource is a plain
        ProtectedResource)."""
        if self._metadata is None:
            data, _headers = self._get_json(f"{self.url}/metadata/")
            self._metadata = data
        return self._metadata

    def get_api_version(self) -> str | None:
        """gramps-web-api's own version string, e.g. "2.8.1"."""
        return (self.get_metadata().get("gramps_webapi") or {}).get("version")

    def get_gramps_version(self) -> str | None:
        """Version of the Gramps library the *server* runs on, e.g.
        "6.0.1". grampswebapidb.py gates on this: the transaction-history
        feed's object serialization only has the "_class"-tagged shape
        data_to_object() understands from Gramps 6.0 onwards."""
        return (self.get_metadata().get("gramps") or {}).get("version")

    def supports_background_transactions(self) -> bool:
        """Whether POST /transactions/ on this server understands
        ?background=1. Unknown/unparseable versions answer False -- the
        synchronous path works on every version, so it's the safe
        default."""
        version = parse_version(self.get_api_version())
        return version is not None and version >= BACKGROUND_MIN_API_VERSION

    def get_identity(self) -> str:
        """ "<username>@<hostname>" identifying the account+server this
        handler authenticates as -- see grampswebapidb.py's
        _check_identity(), which requires a Family Tree's own name to
        match this before trusting its local mirror."""
        return f"{self.get_current_username()}@{self.hostname}"

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
                sleep(
                    RATE_LIMIT_BACKOFF
                )  # avoid immediately re-tripping the rate limit
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

    def _get_binary(self, url: str, retry: bool = True) -> bytes:
        """GET ``url`` with the bearer token and return the raw response
        body, unlike _get_json() -- for endpoints that return a file
        rather than a JSON document (see download_export())."""
        req = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "User-Agent": "GrampsWebApiDb",
            },
        )
        try:
            with self._open(req) as res:
                return res.read()
        except HTTPError as exc:
            if exc.code == 401 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                self._authenticate()
                return self._get_binary(url, retry=False)
            if exc.code == 429 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                return self._get_binary(url, retry=False)
            raise
        except (URLError, socket.timeout):
            if retry:
                sleep(1)
                return self._get_binary(url, retry=False)
            raise

    def download_export(self, extension: str = "gramps") -> bytes:
        """
        Download a full backup export of the tree from the server --
        by default a gzip-compressed Gramps XML file, the exact on-disk
        shape Gramps' own ImportXml importer already reads (confirmed
        against a live server: GET /exporters/gramps/file runs
        synchronously and streams the file back, no task polling
        needed). Used by grampswebapidb.py's WebApiDB._full_resync() to
        rebuild the local mirror wholesale when the transaction-history
        feed can't describe what changed -- see that method's own doc
        comment on why.
        """
        url = f"{self.url}/exporters/{extension}/file"
        return self._get_binary(url)

    def get_missing_files(self) -> list[dict[str, Any]]:
        """
        List the server's Media objects that have no uploaded file yet
        (GET /media/?filemissing=1) -- the remote side of the
        missing-file comparison grampswebapidb.py's WebApiDB._sync_media_
        files() makes; the local side is a plain os.path.exists() check,
        nothing the server needs to be asked about. Each item is the
        server's own JSON Media object; only "handle" is used by the
        caller. Shares _get_json()'s existing 401/429/network retry
        handling.
        """
        body, _headers = self._get_json(f"{self.url}/media/?filemissing=1")
        return body

    def download_media_file(self, handle: str, path: str, retry: bool = True) -> None:
        """
        Download one media file from the server and write it to
        ``path``, creating any missing parent directory first. Streamed
        in chunks rather than buffered fully in memory the way
        _get_binary() is -- media files (video in particular) can be
        large.

        Ported from GrampsWebSync's webapihandler.download_media_file()/
        _download_file() (same repo, same license, credit David Straub),
        folded into one method and authenticated the same way every
        other request in this class already is -- a bearer header, not
        GrampsWebSync's ``?jwt=`` query-string variant (gramps-web-api
        accepts both; see JWT_TOKEN_LOCATION in its config.py, and there
        is no <img src=...>-style consumer here that would need the
        query-string form).
        """
        req = Request(
            f"{self.url}/media/{handle}/file",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "User-Agent": "GrampsWebApiDb",
            },
        )
        try:
            with self._open(req) as res:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    chunk = res.read(_DOWNLOAD_CHUNK_SIZE)
                    while chunk:
                        f.write(chunk)
                        chunk = res.read(_DOWNLOAD_CHUNK_SIZE)
        except HTTPError as exc:
            if exc.code == 401 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                self._authenticate()
                return self.download_media_file(handle, path, retry=False)
            if exc.code == 429 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                return self.download_media_file(handle, path, retry=False)
            raise
        except (URLError, socket.timeout):
            if retry:
                sleep(RATE_LIMIT_BACKOFF)
                return self.download_media_file(handle, path, retry=False)
            raise

    def upload_media_file(self, handle: str, path: str, retry: bool = True) -> bool:
        """
        Upload one local media file to the server for ``handle`` (PUT
        /media/<handle>/file?uploadmissing=1), streamed from disk rather
        than read fully into memory first. Returns False on a 409 --
        something else already uploaded a file for this object in the
        meantime, an expected outcome of a concurrent sync rather than a
        failure -- and True otherwise.

        Ported from GrampsWebSync's webapihandler.upload_media_file()/
        _upload_file(), folded into one method and sharing this class's
        retry conventions (401 re-auth, 429 backoff, one retry each)
        rather than the source's separate hand-rolled helper.
        """
        with open(path, "rb") as f:
            req = Request(
                f"{self.url}/media/{handle}/file?uploadmissing=1",
                data=f,
                method="PUT",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "User-Agent": "GrampsWebApiDb",
                },
            )
            try:
                with self._open(req) as res:
                    res.read()
            except HTTPError as exc:
                if exc.code == 409:
                    return False
                if exc.code == 401 and retry:
                    sleep(RATE_LIMIT_BACKOFF)
                    self._authenticate()
                    return self.upload_media_file(handle, path, retry=False)
                if exc.code == 429 and retry:
                    sleep(RATE_LIMIT_BACKOFF)
                    return self.upload_media_file(handle, path, retry=False)
                raise
            except (URLError, socket.timeout):
                if retry:
                    sleep(RATE_LIMIT_BACKOFF)
                    return self.upload_media_file(handle, path, retry=False)
                raise
        return True

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

    def wait_for_task(
        self,
        task_id: str,
        timeout: float = TASK_TIMEOUT,
        poll_interval: float = TASK_POLL_INTERVAL,
    ) -> None:
        """Poll GET /tasks/<id> until a backgrounded server task finishes.

        Returns normally on SUCCESS. A FAILURE/REVOKED task raises --
        WebApiPushConflict if it failed the server's old-data check (the
        same "Object has changed" sentinel a synchronous push reports as
        HTTP 400, so the caller's conflict handling works identically
        either way), otherwise ValueError carrying the server's message.
        Gives up after ``timeout`` seconds with a TimeoutError, which is
        an OSError and so reads as a transient/connection-ish failure to
        callers rather than a refusal.
        """
        deadline = time.monotonic() + timeout
        while True:
            body, _headers = self._get_json(f"{self.url}/tasks/{task_id}")
            state = body.get("state")
            if state == "SUCCESS":
                return
            if state in ("FAILURE", "REVOKED"):
                message = _task_error_message(body)
                if message == _CONFLICT_MESSAGE:
                    raise WebApiPushConflict(message)
                raise ValueError(f"Server task {state}: {message}")
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Server task {task_id} did not finish within {timeout}s"
                )
            sleep(poll_interval)

    def push_transaction(
        self,
        payload: list[dict[str, Any]],
        retry: bool = True,
        undo: bool = False,
        background: bool = False,
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

        ``undo=True`` sends the *same* payload a prior push_transaction()
        call already sent, with ?undo=1: the server reverses it itself
        (swaps old/new, add<->delete -- see
        gramps_webapi/api/resources/util.py's reverse_transaction()) before
        applying, so this is how grampswebapidb.py implements Undo without
        having to compute the inverse payload locally. Redo is *not* a
        variant of this -- it's just an ordinary push_transaction() call
        with the original (forward) payload again.

        ``background=True`` adds ?background=1, asking the server to queue
        the work and answer 202 immediately rather than holding the
        connection open while it processes -- the way to push a payload
        big enough to risk hitting TIMEOUT mid-request. Only meaningful on
        gramps-web-api >= BACKGROUND_MIN_API_VERSION; check
        supports_background_transactions() first. Two wrinkles the caller
        doesn't have to care about, both handled here so a backgrounded
        push raises exactly what a synchronous one would:

        - The server only *actually* backgrounds the work if it has a
          Celery queue configured; otherwise run_task() runs it inline and
          returns 200 (see gramps_webapi/api/tasks.py). So a 202 means
          "poll the task", and a 200 means it's already done.
        - On that inline path a conflict surfaces as HTTP **500**, not
          400: run_task() catches the ValueError process_transactions
          raises and re-aborts it as a 500 with the same
          {"error": {"message": ...}} body. Checked for the conflict
          sentinel here too, so it doesn't get misread as a transient
          server error and retried forever.
        """
        if not payload:
            return
        data = json.dumps(payload).encode()
        params = {}
        if undo:
            params["undo"] = "1"
        if background:
            params["background"] = "1"
        url = f"{self.url}/transactions/"
        if params:
            url += "?" + urlencode(params)
        req = Request(
            url,
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
                status = res.getcode()
                body = res.read()
        except HTTPError as exc:
            if exc.code == 401 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                self._authenticate()
                return self.push_transaction(
                    payload, retry=False, undo=undo, background=background
                )
            if exc.code == 429 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                return self.push_transaction(
                    payload, retry=False, undo=undo, background=background
                )
            # 400 is the synchronous conflict; 500 is the same conflict
            # re-wrapped by run_task() on the inline background path.
            if exc.code in (400, 500):
                _raise_for_push_conflict(exc)
            raise
        except (URLError, socket.timeout):
            if retry:
                sleep(RATE_LIMIT_BACKOFF)
                return self.push_transaction(
                    payload, retry=False, undo=undo, background=background
                )
            raise
        if status == 202:
            task_id = json.loads(body)["task"]["id"]
            self.wait_for_task(task_id)
