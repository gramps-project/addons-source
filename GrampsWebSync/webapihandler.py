# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021-2024       David Straub
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


"""Web API handler class for the Gramps Web Sync plugin."""

from __future__ import annotations

import base64
import gzip
import json
import logging
import os
import platform
import socket
import ssl
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from const import (
    AUTH_PASSWORD,
    AUTH_SYNC_TOKEN,
    SYNC_TOKEN_LABEL,
    SYNC_TOKEN_LABEL_MAX_LENGTH,
    SYNC_TOKEN_MAX_PER_USER,
)
from gramps.gen.lib.json_utils import remove_object
from gramps.gen.db import KEY_TO_CLASS_MAP, DbTxn
from gramps.gen.db.dbconst import TXNADD, TXNDEL, TXNUPD

LOG = logging.getLogger("grampswebsync")

#: Seconds before a request that has produced nothing is abandoned. Without
#: this, ``urlopen`` waits forever and an unreachable-but-listening server
#: hangs the tool with no way out.
TIMEOUT = 60


class ServerTaskFailed(Exception):
    """A background task on the server reported failure.

    Carries the server's own description rather than a stringified status dict,
    so the message shown to the user says what went wrong.
    """


def describe_task_failure(task_status: dict[str, Any]) -> str:
    """Extract a readable reason from a failed task status.

    The status dict carries the reason in one of a few shapes depending on how
    the task died. Stringifying the whole dict, as this once did, produced a
    message no user could act on.

    :param task_status: The server's task status document.
    :returns: The most specific description available.
    """
    info = task_status.get("info")
    if isinstance(info, dict):
        for key in ("message", "error", "detail"):
            value = info.get(key)
            if value:
                return str(value)
    elif info:
        return str(info)
    state = task_status.get("state", "FAILURE")
    return f"The server reported task state {state}."


def parse_version(version) -> tuple[int, int]:
    """Simple dependency-free version to parse a SemVer into a list of ints."""
    # Split version on the first "-" or "+" and take the main version part
    main_version = version.split("-", 1)[0].split("+", 1)[0]
    parts = [int(part) for part in main_version.split(".")]
    if not parts:
        return (0, 0)
    if len(parts) == 1:
        parts.append(0)
    return (parts[0], parts[1])


#: Apple's public roots — absent from the ``security list-keychains`` list.
MACOS_ROOT_KEYCHAIN = "/System/Library/Keychains/SystemRootCertificates.keychain"

#: The machine-wide keychain, where an administrator installs a private CA.
MACOS_ADMIN_KEYCHAIN = "/Library/Keychains/System.keychain"

KEYCHAIN_TIMEOUT = 30


def _macos_keychains() -> list[str]:
    """Return the keychains to read trust anchors from, in search order."""
    keychains = [MACOS_ROOT_KEYCHAIN, MACOS_ADMIN_KEYCHAIN]
    try:
        listed = subprocess.run(
            ["security", "list-keychains"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=KEYCHAIN_TIMEOUT,
        ).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError) as exc:
        LOG.warning("Could not list macOS keychains: %s", exc)
        listed = ""
    # Each entry is quoted and indented on its own line.
    for line in listed.splitlines():
        path = line.strip().strip('"')
        if path and path not in keychains:
            keychains.append(path)
    return keychains


def create_macos_ssl_context() -> ssl.SSLContext:
    """Create an SSL context trusting the CAs in the user's macOS keychains.

    Searches the hard-coded system keychains and the user keychains reported
    by ``security list-keychains``, so that a privately issued CA installed in
    the admin or login keychain is trusted alongside Apple's public roots.
    """
    ctx = ssl.create_default_context()
    pem_blocks: list[bytes] = []
    for keychain in _macos_keychains():
        try:
            result = subprocess.run(
                ["security", "find-certificate", "-a", "-p", keychain],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=KEYCHAIN_TIMEOUT,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            LOG.warning("Could not read certificates from %s: %s", keychain, exc)
            continue
        if result.stdout:
            pem_blocks.append(result.stdout)

    if not pem_blocks:
        LOG.warning(
            "No certificates found in the macOS keychains; TLS verification "
            "will fail for every server."
        )
        return ctx

    with NamedTemporaryFile("w+b", suffix=".pem") as tmp_file:
        tmp_file.write(b"\n".join(pem_blocks))
        # Without the flush, the tail of the buffer is still unwritten when
        # OpenSSL opens the file by name, silently truncating the anchors.
        tmp_file.flush()
        ctx.load_verify_locations(tmp_file.name)

    return ctx


def device_label() -> str:
    """Return the label for this computer's sync token."""
    host = socket.gethostname().split(".")[0] or "this computer"
    return (SYNC_TOKEN_LABEL % host)[:SYNC_TOKEN_LABEL_MAX_LENGTH]


def numbered_label(label: str, number: int) -> str:
    """Return ``label`` with `` (number)`` appended, within the length limit.

    Used when another computer's token already has this computer's label,
    for example because both have the same host name.
    """
    suffix = f" ({number})"
    return label[: SYNC_TOKEN_LABEL_MAX_LENGTH - len(suffix)] + suffix


def is_label_conflict(exc: HTTPError) -> bool:
    """Whether a 409 is about the label, rather than the token limit.

    The server answers 409 for both; only its message tells them apart.
    """
    try:
        message = json.loads(exc.read())["error"]["message"]
    except Exception:  # noqa: BLE001 -- no body, or not the API's error shape
        return False
    return "label" in str(message).lower()


class SyncTokensUnsupported(Exception):
    """The server can't create per-device sync tokens."""


def decode_jwt_payload(jwt: str) -> dict[str, Any]:
    """Decode and return the payload from a JWT."""
    payload_part = jwt.split(".")[1]
    padding = len(payload_part) % 4
    if padding > 0:
        payload_part += "=" * (4 - padding)
    decoded_bytes = base64.urlsafe_b64decode(payload_part)
    decoded_str = decoded_bytes.decode("utf-8")
    return json.loads(decoded_str)


class WebApiHandler:
    """Web API connection handler."""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        download_callback: Callable | None = None,
        auth: str = AUTH_PASSWORD,
    ) -> None:
        """Initialize given URL, user name, and password.

        :param auth: :data:`const.AUTH_SYNC_TOKEN` if ``password`` is a sync
            token stored in place of the password.
        """
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.auth = auth
        self._access_token: str | None = None
        self.download_callback = download_callback
        # Determine the appropriate SSL context based on platform
        self._ctx = (
            create_macos_ssl_context() if platform.system() == "Darwin" else None
        )

        # get and cache the access token
        self.fetch_token()
        self._metadata: dict | None = None

    def _open(self, req: Request):
        """Open ``req`` with this handler's SSL context and timeout."""
        return urlopen(req, context=self._ctx, timeout=TIMEOUT)

    @property
    def access_token(self) -> str:
        """Get the access token. Cached after first call unless refresh needed. Auto-refreshing"""
        if not self._access_token:
            self.fetch_token()
        remaining_time = self.get_access_token_remaining_time()
        if remaining_time is not None and remaining_time < 60:
            self.fetch_token()
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

    @property
    def metadata(self) -> dict:
        """Get server metadata. Cached after first call."""
        if not self._metadata:
            self.fetch_metadata()
        assert self._metadata
        return self._metadata

    def fetch_metadata(self) -> None:
        """Fetch and store server metadata."""
        LOG.debug("Fetching metadata from the server")
        req = Request(
            f"{self.url}/metadata/",
            headers={"Authorization": f"Bearer {self.access_token}", "User-Agent": "GrampsWebSync"},
        )
        with self._open(req) as res:
            self._metadata = json.load(res)

    def fetch_token(self) -> None:
        """Fetch and store an access token.

        A sync token is exchanged for an access token instead. There is no
        refresh token then: the exchange is repeated when the access token
        runs out, which :attr:`access_token` already does.
        """
        LOG.debug("Fetching an access token from the server")
        if self.auth == AUTH_SYNC_TOKEN:
            endpoint = "token/sync/"
            data = json.dumps({"token": self.password})
        else:
            endpoint = "token/"
            data = json.dumps({"username": self.username, "password": self.password})
        req = Request(
            f"{self.url}/{endpoint}",
            data=data.encode(),
            headers={"Content-Type": "application/json", "User-Agent": "GrampsWebSync"},
        )
        try:
            with self._open(req) as res:
                res_json = json.load(res)
        except (UnicodeDecodeError, json.JSONDecodeError, HTTPError):
            if "/api" not in self.url:
                self.url = f"{self.url}/api"
                return self.fetch_token()
            raise
        self._access_token = res_json["access_token"]

    def _call(self, method: str, path: str, body: dict | None = None) -> Any:
        """Call an authenticated JSON endpoint and return the decoded reply."""
        req = Request(
            f"{self.url}/{path}",
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "User-Agent": "GrampsWebSync",
            },
        )
        with self._open(req) as res:
            raw = res.read()
        return json.loads(raw) if raw else None

    def create_sync_token(self, label: str) -> tuple[str, int]:
        """Create a sync token for this computer.

        Needs a password login. Nothing is deleted: if another token already
        has ``label``, for example on a computer with the same host name, the
        label is numbered, ``"... (2)"`` and so on.

        :returns: The token value and its id, which revokes it later.
        :raises SyncTokensUnsupported: If the server has no per-device sync
            tokens (Gramps Web API before 3.23).
        :raises HTTPError: For anything else, such as the token limit.
        """
        path = "users/-/access-tokens/sync/tokens/"
        for number in range(1, SYNC_TOKEN_MAX_PER_USER + 1):
            candidate = label if number == 1 else numbered_label(label, number)
            try:
                reply = self._call("POST", path, {"label": candidate})
            except HTTPError as exc:
                if exc.code == 404:
                    raise SyncTokensUnsupported(str(exc.code)) from exc
                if (
                    exc.code == 409
                    and number < SYNC_TOKEN_MAX_PER_USER
                    and is_label_conflict(exc)
                ):
                    continue
                raise
            return reply["token"], reply["id"]
        raise AssertionError("unreachable")  # the last attempt returns or raises

    def revoke_sync_token(self, token_id: int) -> None:
        """Revoke one of the user's sync tokens. Needs a password login.

        A token that is gone already, revoked in Gramps Web for example, is
        not an error.
        """
        try:
            self._call("DELETE", f"users/-/access-tokens/sync/tokens/{token_id}/")
        except HTTPError as exc:
            if exc.code != 404:
                raise

    def get_permissions(self) -> set[str]:
        """Get the permissions of the current user."""
        return decode_jwt_payload(self.access_token).get("permissions", set())

    def get_lang(self) -> str | None:
        """Fetch language information."""
        return (self.metadata.get("locale") or {}).get("lang")

    def get_api_version(self) -> str | None:
        """Fetch API version info."""
        return (self.metadata.get("gramps_webapi") or {}).get("version")

    def get_tree_name(self) -> str:
        """Return the name the server gives the tree it is serving."""
        return ((self.metadata.get("database") or {}).get("name") or "")

    def has_task_queue(self) -> bool:
        """Whether the server runs transactions on a background task queue."""
        return bool((self.metadata.get("server") or {}).get("task_queue"))

    def download_xml(self) -> Path:
        """Download an XML export and return the path of the temp file."""
        url = f"{self.url}/exporters/gramps/file"
        temp = NamedTemporaryFile(delete=False)
        try:
            self._download_file(url=url, fobj=temp)
        finally:
            temp.close()
        unzipped_name = f"{temp.name}.gramps"
        with open(unzipped_name, "wb") as fu:
            with gzip.open(temp.name) as fz:
                fu.write(fz.read())
        os.remove(temp.name)
        return Path(unzipped_name)

    def commit(
        self,
        payload: list[dict[str, Any]],
        force: bool = True,
        progress_callback: Callable | None = None,
    ) -> None:
        """Commit the changes to the remote database."""
        if payload:
            data = json.dumps(payload).encode()
            # Always in the background. The version this addon requires always
            # supports it, and a server whose task queue is switched off is
            # refused at connect time rather than left to time out here.
            query = "force=1&background=1" if force else "background=1"
            endpoint = f"{self.url}/transactions/?{query}"
            req = Request(
                endpoint,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.access_token}",
                    "User-Agent": "GrampsWebSync"
                },
            )
            json_response: dict | None = None
            with self._open(req) as res:
                status_code = res.getcode()
                if status_code == 202:
                    json_response = json.load(res)
            if status_code == 202 and json_response:
                self.monitor_task_status(json_response, progress_callback)

    def monitor_task_status(
        self, task_response: dict, progress_callback: Callable | None
    ):
        """Monitor the status of a background task."""
        task_id = task_response["task"]["id"]
        while True:
            is_done = self.update_task_status(
                task_id, progress_callback=progress_callback
            )
            if is_done:
                if progress_callback:
                    progress_callback(1)  # 100%
                break
            sleep(1)

    def update_task_status(
        self, task_id: str, progress_callback: Callable | None
    ) -> bool:
        """Update the status of a background task.

        Returns True if the task is finished, False otherwise.
        """
        endpoint = f"{self.url}/tasks/{task_id}"
        req = Request(
            endpoint,
            headers={"Authorization": f"Bearer {self.access_token}", "User-Agent": "GrampsWebSync"},
        )
        # HTTPError and URLError are deliberately not wrapped: the caller
        # classifies them into specific, actionable messages, which converting
        # them to a ValueError would flatten into a generic server error.
        with self._open(req) as res:
            task_status = json.load(res)
            if task_status["state"] == "SUCCESS":
                return True
            if task_status["state"] in {"FAILURE", "REVOKED"}:
                LOG.warning("Server task failed: %s", task_status)
                raise ServerTaskFailed(describe_task_failure(task_status))
            if progress_callback:
                try:
                    progress = task_status["result_object"]["progress"]
                except (KeyError, TypeError):
                    progress = -1
                progress_callback(progress)
            return False

    def get_missing_files(self, retry: bool = True) -> list:
        """Get a list of remote media objects with missing files."""
        req = Request(
            f"{self.url}/media/?filemissing=1",
            headers={"Authorization": f"Bearer {self.access_token}", "User-Agent": "GrampsWebSync"},
        )
        try:
            with self._open(req) as res:
                res_json = json.load(res)
        except HTTPError as exc:
            if exc.code == 401 and retry:
                # in case of 401, retry once with a new token
                sleep(1)  # avoid server-side rate limit
                self.fetch_token()
                return self.get_missing_files(retry=False)
            raise
        return res_json

    def _download_file(
        self, url: str, fobj, retry: bool = True, token_url: bool = False
    ):
        """Download a file."""
        if token_url:
            req = Request(f"{url}?jwt={self.access_token}", headers={"User-Agent": "GrampsWebSync"})
        else:
            req = Request(
                url,
                headers={"Authorization": f"Bearer {self.access_token}", "User-Agent": "GrampsWebSync"},
            )
        try:
            with self._open(req) as res:
                chunk_size = 64 * 1024
                chunk = res.read(chunk_size)
                fobj.write(chunk)
                while chunk:
                    if self.download_callback is not None:
                        self.download_callback()
                    chunk = res.read(chunk_size)
                    fobj.write(chunk)
        except HTTPError as exc:
            if exc.code == 401 and retry:
                # in case of 401, retry once with a new token
                sleep(1)  # avoid server-side rate limit
                self.fetch_token()
                return self._download_file(
                    url=url, fobj=fobj, retry=False, token_url=token_url
                )
            raise

    def download_media_file(self, handle: str, path) -> bool:
        """Download a media file."""
        url = f"{self.url}/media/{handle}/file"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            self._download_file(url=url, fobj=f, token_url=True)
        return True

    def upload_media_file(self, handle: str, path) -> bool:
        """Upload a media file."""
        url = f"{self.url}/media/{handle}/file?uploadmissing=1"
        try:
            with open(path, "rb") as f:
                self._upload_file(url=url, fobj=f)
        except HTTPError as exc:
            if exc.code == 409:
                return False
            raise
        return True

    def _upload_file(self, url: str, fobj, retry: bool = True):
        """Upload a file."""
        req = Request(
            url,
            data=fobj,
            headers={"Authorization": f"Bearer {self.access_token}", "User-Agent": "GrampsWebSync"},
            method="PUT",
        )
        try:
            with self._open(req) as res:
                pass
        except HTTPError as exc:
            if exc.code == 401 and retry:
                # in case of 401, retry once with a new token
                sleep(1)  # avoid server-side rate limit
                self.fetch_token()
                return self._upload_file(url=url, fobj=fobj, retry=False)
            raise
        except (URLError, socket.timeout) as exc:
            if retry:
                sleep(1)
                return self._upload_file(url=url, fobj=fobj, retry=False)
            raise


def transaction_to_json(
    transaction: DbTxn, lang: str | None = None
) -> list[dict[str, Any]]:
    """Return a JSON representation of a database transaction."""
    out = []
    for recno in transaction.get_recnos(reverse=False):
        key, action, handle, old_data, new_data = transaction.get_record(recno)
        try:
            obj_cls_name = KEY_TO_CLASS_MAP[key]
        except KeyError:
            continue  # this happens for references
        trans_dict = {TXNUPD: "update", TXNDEL: "delete", TXNADD: "add"}
        item = {
            "type": trans_dict[action],
            "handle": handle,
            "_class": obj_cls_name,
            "old": None if old_data is None else remove_object(old_data),
            "new": None if new_data is None else remove_object(new_data),
        }
        out.append(item)
    return out
