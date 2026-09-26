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

LOG = logging.getLogger(".grampswebapidb")

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

#: The "object_counts" buckets GET /metadata/ reports that correspond to
#: the ten primary types Gramps' own DbGeneric.get_total() counts -- see
#: get_object_count(). Summed by name rather than over whatever keys the
#: response happens to carry, so a server that grows an extra bucket
#: can't make a perfectly good local mirror look permanently short of it.
OBJECT_COUNT_KEYS = (
    "people",
    "families",
    "events",
    "places",
    "repositories",
    "sources",
    "citations",
    "media",
    "notes",
    "tags",
)

#: Chunk size used when streaming a media file download to disk -- see
#: download_media_file().
_DOWNLOAD_CHUNK_SIZE = 1024 * 64

#: First gramps-web-api version whose POST /transactions/ understands
#: ?background=1 (same gate GrampsWebSync's webapihandler.commit() uses).
BACKGROUND_MIN_API_VERSION = (2, 7)

#: First gramps-web-api version whose GET /transactions/history/
#: understands after_id/before_id, the exact transaction-id cursor
#: get_transaction_history() now sends on every call (PR #925/#927,
#: both first released in this version) -- see that method's own
#: docstring on why it switched off the older, float timestamp-based
#: ``after`` cursor. Unlike BACKGROUND_MIN_API_VERSION, there is no safe
#: fallback for an older server here: gramps-web-api's own query-arg
#: parser rejects any *unrecognized* query argument outright (RAISE, not
#: silently ignore -- see its api/util.py Parser), so after_id 422s
#: every single history request on a server below this version.
#: grampswebapidb.py checks this once at load() (_check_history_cursor_
#: support_async()) and refuses to open rather than let every poll fail.
HISTORY_ID_CURSOR_MIN_API_VERSION = (3, 21)

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


def _request_target(req: Request) -> str:
    """The path+query of ``req`` for a log line -- scheme and host
    dropped as noise (one server per handler), credentials never
    involved: they travel in headers, not the URL. See _open()."""
    parts = urlparse(req.full_url)
    return parts.path + (f"?{parts.query}" if parts.query else "")


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
        #: Last ETag get_transaction_history() saw, echoed back as
        #: If-None-Match on the next call -- see that method's own
        #: docstring for why.
        self._history_etag: str | None = None
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
        """Open ``req`` with this handler's SSL context and timeout.

        Every request this client makes funnels through here, so this is
        also where each one is traced at DEBUG: method, path, outcome and
        round-trip time, one line apiece. Only the path+query is logged,
        never headers -- the bearer token lives in a header, and nothing
        this addon sends puts a credential in a URL. The timing stops at
        the response headers, before the body is read, which is what makes
        it useful for telling a slow server apart from a slow transfer.
        """
        started = time.monotonic()
        target = _request_target(req)
        try:
            res = urlopen(req, context=self._ctx, timeout=TIMEOUT)
        except HTTPError as exc:
            LOG.debug(
                "%s %s -> HTTP %s (%.2fs)",
                req.get_method(),
                target,
                exc.code,
                time.monotonic() - started,
            )
            raise
        except (URLError, socket.timeout) as exc:
            LOG.debug(
                "%s %s -> %s (%.2fs)",
                req.get_method(),
                target,
                exc,
                time.monotonic() - started,
            )
            raise
        LOG.debug(
            "%s %s -> %s (%.2fs)",
            req.get_method(),
            target,
            getattr(res, "status", "?"),
            time.monotonic() - started,
        )
        return res

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

    def get_object_count(self) -> int:
        """How many primary objects the server's tree currently holds:
        GET /metadata/'s "object_counts", summed over OBJECT_COUNT_KEYS.

        Deliberately *not* routed through get_metadata()'s cache. That
        cache is for the deployment description -- versions, server
        features -- which cannot change while a tree is open; an object
        count is live state, and the only reason to ask for it is to
        compare it against what a local mirror holds right now (see
        grampswebapidb.py's _mirror_is_short_of_the_server()).
        """
        data, _headers = self._get_json(f"{self.url}/metadata/")
        counts = data.get("object_counts") or {}
        return sum(
            count
            for key, count in counts.items()
            if key in OBJECT_COUNT_KEYS and isinstance(count, int)
        )

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

    def get_person_birth_death_indices(self) -> dict[str, tuple[int, int]]:
        """{handle: (birth_ref_index, death_ref_index)} for every Person
        the server currently holds -- the ground truth for the one thing
        a Gramps XML export/reimport cannot preserve (see
        grampswebapidb.py's _snapshot_birth_death_indices() docstring:
        neither field has any XML representation at all, so ImportXml
        recomputes both by a document-order heuristic that's only
        sometimes right). GET /people/ serializes with
        GrampsJSONEncoder.extract_object() -- not the data_to_object()-
        compatible shape (see _resync_after_conflict_async()'s docstring
        on why that rules out reconstructing a whole Person from it) --
        but it does include these two plain integer fields verbatim, and
        that's all this needs.

        Costs one full paginated listing of the tree's People endpoint --
        proportionate for a bootstrap resync, which already does a
        full-tree XML export/reimport of comparable size; deliberately
        *not* called on every ordinary conflict-triggered resync, where a
        local mirror already has a correct prior value to carry forward
        instead (see _bootstrap_full_resync()'s own comment on why
        bootstrap specifically has no such value to carry).
        """
        result: dict[str, tuple[int, int]] = {}
        page = 1
        pagesize = 200
        while True:
            params = {"page": page, "pagesize": pagesize}
            data, _headers = self._get_json(f"{self.url}/people/?{urlencode(params)}")
            if not data:
                break
            for person in data:
                handle = person.get("handle")
                if handle is None:
                    continue
                result[handle] = (
                    person.get("birth_ref_index", -1),
                    person.get("death_ref_index", -1),
                )
            if len(data) < pagesize:
                break
            page += 1
        return result

    def get_identity(self) -> str:
        """ "<username>@<hostname>" identifying the account+server this
        handler authenticates as -- see grampswebapidb.py's
        _check_identity_async(), which requires a Family Tree's own name to
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

    def _post_json(self, url: str, retry: bool = True) -> tuple[Any, int]:
        """POST ``url`` with the bearer token and an empty body, returning
        ``(body, status)`` -- unlike _get_json(), the status code itself
        is meaningful here (202 "queued, go poll the task" vs. 200/201
        "already done"), the same distinction push_transaction() draws
        for its own background=1 POST. Used by download_export()."""
        req = Request(
            url,
            data=b"",
            method="POST",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "User-Agent": "GrampsWebApiDb",
            },
        )
        try:
            with self._open(req) as res:
                return json.load(res), res.getcode()
        except HTTPError as exc:
            if exc.code == 401 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                self._authenticate()
                return self._post_json(url, retry=False)
            if exc.code == 429 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                return self._post_json(url, retry=False)
            raise
        except (URLError, socket.timeout):
            if retry:
                sleep(1)
                return self._post_json(url, retry=False)
            raise

    def _get_binary(self, url: str, retry: bool = True, on_chunk=None) -> bytes:
        """GET ``url`` with the bearer token and return the raw response
        body, unlike _get_json() -- for endpoints that return a file
        rather than a JSON document (see download_export()).

        ``on_chunk``, if given, is called with no arguments after each
        _DOWNLOAD_CHUNK_SIZE bytes arrive, and switches the read from one
        blocking res.read() to a chunked loop. It exists for a caller
        blocking a GUI thread on this call: a multi-megabyte export is
        one uninterruptible read otherwise, long enough for the window
        manager to decide the application has stopped responding.
        grampswebapidb.py no longer passes this (its WebApiDB._full_
        resync_async() runs this call on a worker thread instead, where
        there is no main loop to keep alive) -- kept here, unused by that
        caller, since this file is also the vendored source for the
        standalone gramps-api-client package (see this module's own
        docstring), and a single-threaded caller elsewhere may still want
        it.
        """
        req = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "User-Agent": "GrampsWebApiDb",
            },
        )
        try:
            with self._open(req) as res:
                if on_chunk is None:
                    return res.read()
                chunks = []
                while True:
                    chunk = res.read(_DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    on_chunk()
                return b"".join(chunks)
        except HTTPError as exc:
            if exc.code == 401 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                self._authenticate()
                return self._get_binary(url, retry=False, on_chunk=on_chunk)
            if exc.code == 429 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                return self._get_binary(url, retry=False, on_chunk=on_chunk)
            raise
        except (URLError, socket.timeout):
            if retry:
                sleep(1)
                return self._get_binary(url, retry=False, on_chunk=on_chunk)
            raise

    def download_export(
        self, extension: str = "gramps", on_chunk=None, on_wait=None
    ) -> bytes:
        """
        Download a full backup export of the tree from the server --
        by default a gzip-compressed Gramps XML file, the exact on-disk
        shape Gramps' own ImportXml importer already reads. Used by
        grampswebapidb.py's WebApiDB._full_resync_async() to rebuild the
        local mirror wholesale when the transaction-history feed can't
        describe what changed -- see that method's own doc comment on
        why.

        Goes through POST /exporters/<extension>/file, not the GET
        variant of the same URL. GET runs the export inline on the
        request thread gramps-web-api answers it on -- fine for a small
        tree, but it ties up a web worker for however long a large
        export takes, and exists server-side only for backwards
        compatibility. POST triggers the same run_export() through
        Celery when a task queue is configured (202 -- poll
        wait_for_task(), same as push_transaction(background=True)) or
        inline otherwise (201 -- the finished file's own url comes back
        immediately in the response body); this is the same request
        Gramps Web's own frontend makes for every export (see
        gramps-connect's store/exportersApi.ts, runExport()). Either
        way, the actual bytes are then one more GET, to a
        ``/exporters/<extension>/file/processed/<uuid>.<ext>`` url the
        task/response names -- delete-on-read server-side, so this can
        only succeed once. That url comes back as a path only (already
        prefixed with "/api"), so it's resolved against this handler's
        own scheme+host rather than against self.url (which already
        ends in "/api" itself).

        ``on_chunk``/``on_wait`` are passed through to _get_binary()/
        wait_for_task() respectively: hooks a caller on a GUI thread can
        use to keep its main loop alive across what is easily the
        longest-running operation this client makes. See
        _get_binary()'s own docstring on why grampswebapidb.py no
        longer passes on_chunk.
        """
        url = f"{self.url}/exporters/{extension}/file"
        result, status = self._post_json(url)
        if status == 202:
            task_body = self.wait_for_task(result["task"]["id"], on_wait=on_wait)
            result = task_body.get("result_object") or {}
        origin = urlparse(self.url)
        file_url = f"{origin.scheme}://{origin.netloc}{result['url']}"
        return self._get_binary(file_url, on_chunk=on_chunk)

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
        self,
        after_id: int = 0,
        page: int = 1,
        pagesize: int = 100,
        sort: str = "id",
        after: float | None = None,
        retry: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Fetch one page of the server's transaction history with an id
        strictly greater than ``after_id``, sorted per ``sort``
        ("id" ascending by default), including the post-change raw
        object data.

        Cursors on the transaction id, not a timestamp. gramps-web-api
        compares the older, timestamp-based ``after`` param as
        ``after * 1e9`` server-side, and that float round-trip (a Python
        float here, re-parsed as a server float after a trip through the
        query string) can lose enough precision to make the same
        trailing transaction compare as "still after the cursor"
        forever -- an infinite-redelivery loop: harmless (replaying an
        already-applied change is a no-op -- see grampswebapidb.py's
        _apply_change()) but wasteful, forever, on every poll tick.
        ``after_id`` is an exact integer compare (gramps-web-api PR
        #927), with no such failure mode. gramps-connect's own browser
        client hit this exact loop (Gramplets re-running on every 5s
        poll indefinitely) and made the identical switch -- see its
        store/historyPoll.ts, commit 5ae65da.

        ``after`` (the old timestamp cursor) is still accepted, off by
        default, purely for grampswebapidb.py's own
        _migrate_sync_cursor_to_id() -- a one-time upgrade of a mirror
        whose persisted cursor predates this method's switch to
        after_id, which has nothing but that old timestamp to ask the
        server "where was I" with. New code should use after_id.

        Sends the previous call's ETag as If-None-Match. gramps-web-api
        >= 3.21.0's history endpoint (the same release that added
        after_id -- see HISTORY_ID_CURSOR_MIN_API_VERSION) computes that
        from a cheap aggregate query (max transaction id, count) plus
        the request's own args, and checks it *before* doing any
        change-log query/serialize work -- answering a bodyless 304 when
        nothing matching those args has changed since (see
        gramps_webapi/api/resources/history.py's transactions_etag()/
        etag_unchanged()). Unlike after_id, an older server simply
        never sends an ETag back, so self._history_etag stays None and
        this addon never sends If-None-Match either -- no version gate
        needed for this half. grampswebapidb.py's
        _poll_tick() calls this with the same (after_id, page, pagesize)
        every idle tick until new data actually moves the cursor
        forward, which is exactly the steady state this turns into a
        cheap 304 instead of a full fetch -- the same optimization
        gramps-connect's store/historyPoll.ts adopted for its own poll
        loop. Sending a *stale* etag left over from a different set of
        args is harmless: those args are folded into the etag too, so a
        mismatched one just never matches and the server answers
        normally with a fresh one.

        :returns: ``(transactions, total_count)``. On a 304,
            ``transactions`` is ``[]`` -- total_count still comes from
            the X-Total-Count header, which the server sends either way
            -- so an idle tick with nothing new looks to the caller
            exactly like a tick that fetched an empty page the slow way.
        """
        params = {
            "after_id": after_id,
            "new": "1",
            "sort": sort,
            "page": page,
            "pagesize": pagesize,
        }
        if after is not None:
            params["after"] = after
        url = f"{self.url}/transactions/history/?{urlencode(params)}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "GrampsWebApiDb",
        }
        if self._history_etag is not None:
            headers["If-None-Match"] = self._history_etag
        req = Request(url, headers=headers)
        try:
            with self._open(req) as res:
                status = res.getcode()
                response_headers = dict(res.headers)
                if status == 304:
                    body: list = []
                else:
                    body = json.load(res)
                    etag = response_headers.get("ETag")
                    if etag is not None:
                        self._history_etag = etag
        except HTTPError as exc:
            if exc.code == 401 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                self._authenticate()
                return self.get_transaction_history(
                    after_id, page, pagesize, sort, after, retry=False
                )
            if exc.code == 429 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                return self.get_transaction_history(
                    after_id, page, pagesize, sort, after, retry=False
                )
            raise
        except (URLError, socket.timeout):
            if retry:
                sleep(1)
                return self.get_transaction_history(
                    after_id, page, pagesize, sort, after, retry=False
                )
            raise
        total_count = int(response_headers.get("X-Total-Count", len(body)))
        return body, total_count

    def wait_for_task(
        self,
        task_id: str,
        timeout: float = TASK_TIMEOUT,
        poll_interval: float = TASK_POLL_INTERVAL,
        on_wait=None,
    ) -> dict:
        """Poll GET /tasks/<id> until a backgrounded server task finishes.

        ``on_wait``, if given, is called with no arguments once per poll,
        before sleeping. A backgrounded push can occupy the server for
        minutes (TASK_TIMEOUT allows ten), which is that much time a
        caller blocking a GUI thread on this call would otherwise spend
        inside this loop without touching its main loop.
        grampswebapidb.py no longer passes this (its own push machinery
        runs this call on a worker thread, where blocking in
        time.sleep() is exactly what the thread is for) -- kept here,
        unused by that caller, for the same vendored-package reason
        _get_binary()'s ``on_chunk`` is.

        Returns the task's own status body on SUCCESS -- its
        "result_object" key holds whatever the task function returned
        server-side (e.g. download_export()'s ``{"url": ...}``);
        push_transaction() doesn't need it and just discards it. A
        FAILURE/REVOKED task raises instead -- WebApiPushConflict if it
        failed the server's old-data check (the same "Object has
        changed" sentinel a synchronous push reports as HTTP 400, so the
        caller's conflict handling works identically either way),
        otherwise ValueError carrying the server's message. Gives up
        after ``timeout`` seconds with a TimeoutError, which is an
        OSError and so reads as a transient/connection-ish failure to
        callers rather than a refusal.
        """
        deadline = time.monotonic() + timeout
        while True:
            body, _headers = self._get_json(f"{self.url}/tasks/{task_id}")
            state = body.get("state")
            if state == "SUCCESS":
                return body
            if state in ("FAILURE", "REVOKED"):
                message = _task_error_message(body)
                if message == _CONFLICT_MESSAGE:
                    raise WebApiPushConflict(message)
                raise ValueError(f"Server task {state}: {message}")
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Server task {task_id} did not finish within {timeout}s"
                )
            if on_wait is not None:
                on_wait()
            sleep(poll_interval)

    def push_transaction(
        self,
        payload: list[dict[str, Any]],
        retry: bool = True,
        undo: bool = False,
        background: bool = False,
        on_wait=None,
        message: str | None = None,
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

        ``message``, if given, becomes the ``?message=`` query param --
        the description gramps-web-api stores for this transaction in its
        own history log (gramps_webapi/api/resources/transactions.py's
        TransactionsQueryArgs). Left unset, the server defaults it to the
        generic "Raw transaction", which is what every push from this
        addon showed in the server's revision history before callers
        started passing the local DbTxn's own description through (see
        grampswebapidb.py's transaction_commit()) -- the same per-edit
        message ("Add Person (Jane Doe)", "Edit Family", ...) Gramps
        desktop's own editors already set on the DbTxn, and the same
        convention gramps-web-api's own per-object PUT/POST endpoints use
        (DbTxn(f"Edit {class_name}", ...) in
        gramps_webapi/api/resources/base.py) -- so a push from this addon
        shows up in the server's history the same way an edit made
        directly in Gramps Web would.
        """
        if not payload:
            return
        data = json.dumps(payload).encode()
        params = {}
        if undo:
            params["undo"] = "1"
        if background:
            params["background"] = "1"
        if message:
            params["message"] = message
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
                    payload,
                    retry=False,
                    undo=undo,
                    background=background,
                    on_wait=on_wait,
                    message=message,
                )
            if exc.code == 429 and retry:
                sleep(RATE_LIMIT_BACKOFF)
                return self.push_transaction(
                    payload,
                    retry=False,
                    undo=undo,
                    background=background,
                    on_wait=on_wait,
                    message=message,
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
                    payload,
                    retry=False,
                    undo=undo,
                    background=background,
                    on_wait=on_wait,
                    message=message,
                )
            raise
        if status == 202:
            task_id = json.loads(body)["task"]["id"]
            self.wait_for_task(task_id, on_wait=on_wait)
