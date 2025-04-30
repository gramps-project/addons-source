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
import time
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from gramps.gen.lib.json_utils import remove_object
from gramps.gen.db import KEY_TO_CLASS_MAP, DbTxn
from gramps.gen.db.dbconst import TXNADD, TXNDEL, TXNUPD

LOG = logging.getLogger("grampswebsync")


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


def create_macos_ssl_context():
    import ssl
    import subprocess

    """Creates an SSL context using macOS system certificates."""
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


class WebApiHandler:
    """Web API connection handler."""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        download_callback: Callable | None = None,
    ) -> None:
        """Initialize given URL, user name, and password."""
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self._access_token: str | None = None
        self.download_callback = download_callback
        # Determine the appropriate SSL context based on platform
        self._ctx = (
            create_macos_ssl_context() if platform.system() == "Darwin" else None
        )

        # get and cache the access token
        self.fetch_token()
        self._metadata: dict | None = None

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
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        with urlopen(req, context=self._ctx) as res:
            self._metadata = json.load(res)

    def fetch_token(self) -> None:
        """Fetch and store an access token."""
        LOG.debug("Fetching an access token from the server")
        data = json.dumps({"username": self.username, "password": self.password})
        req = Request(
            f"{self.url}/token/",
            data=data.encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, context=self._ctx) as res:
                res_json = json.load(res)
        except (UnicodeDecodeError, json.JSONDecodeError, HTTPError):
            if "/api" not in self.url:
                self.url = f"{self.url}/api"
                return self.fetch_token()
            raise
        self._access_token = res_json["access_token"]

    def get_permissions(self) -> set[str]:
        """Get the permissions of the current user."""
        return decode_jwt_payload(self.access_token).get("permissions", set())

    def get_lang(self) -> str | None:
        """Fetch language information."""
        return (self.metadata.get("locale") or {}).get("lang")

    def get_api_version(self) -> str | None:
        """Fet API version info."""
        return (self.metadata.get("gramps_webapi") or {}).get("version")

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
        payload: dict[str, Any],
        force: bool = True,
        progress_callback: Callable | None = None,
    ) -> None:
        """Commit the changes to the remote database."""
        if payload:
            api_version = self.get_api_version()
            background = api_version and parse_version(api_version) >= (2, 7)
            data = json.dumps(payload).encode()
            endpoint = f"{self.url}/transactions/"
            if force:
                endpoint = f"{endpoint}?force=1"
                if background:
                    endpoint = f"{endpoint}&background=1"
            elif background:
                endpoint = f"{endpoint}?background=1"
            req = Request(
                endpoint,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.access_token}",
                },
            )
            json_response: dict | None = None
            with urlopen(req, context=self._ctx) as res:
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
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        try:
            with urlopen(req, context=self._ctx) as res:
                task_status = json.load(res)
                if task_status["state"] == "SUCCESS":
                    return True
                if task_status["state"] in {"FAILURE", "REVOKED"}:
                    LOG.error(f"Server task failed: {task_status}")
                    raise ValueError(task_status.get("info", "Server task failed"))
                if progress_callback:
                    try:
                        progress = task_status["result_object"]["progress"]
                    except (KeyError, TypeError):
                        progress = -1
                    progress_callback(progress)
                return False
        except HTTPError as e:
            LOG.error(f"HTTPError while fetching task status: {e.code} - {e.reason}")
        except URLError as e:
            LOG.error(f"URLError while fetching task status: {e.reason}")

    def get_missing_files(self, retry: bool = True) -> list:
        """Get a list of remote media objects with missing files."""
        req = Request(
            f"{self.url}/media/?filemissing=1",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        try:
            with urlopen(req, context=self._ctx) as res:
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
            req = Request(f"{url}?jwt={self.access_token}")
        else:
            req = Request(
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
        try:
            with urlopen(req, context=self._ctx) as res:
                chunk_size = 1024
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
            headers={"Authorization": f"Bearer {self.access_token}"},
            method="PUT",
        )
        try:
            with urlopen(req, context=self._ctx) as res:
                pass
        except HTTPError as exc:
            if exc.code == 401 and retry:
                # in case of 401, retry once with a new token
                sleep(1)  # avoid server-side rate limit
                self.fetch_token()
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
