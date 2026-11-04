# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       David Straub
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

"""Tests for downloading the remote tree as a background export.

The server builds the export in a background task
(``POST /api/exporters/gramps/file``), and the addon then downloads the
finished file (``GET /api/exporters/gramps/file/processed/<file name>``).
"""

from __future__ import annotations

import gzip
import os
import unittest
from unittest import mock

from presentation import error_message
from session import ErrorKind, SyncSession
from webapihandler import ExportFailed, WebApiHandler

from .scenario import DEFAULT_URL as URL
from .test_sync_token import FakeHttp, jwt

EXPORT = f"{URL}/exporters/gramps/file"
TASK = f"{URL}/tasks/abc"
FILE_NAME = "0b6e9c2e-4f1a-4c8e-9d1e-2a3b4c5d6e7f.gramps"
PROCESSED = f"{EXPORT}/processed/{FILE_NAME}"
XML = b"<?xml version='1.0'?><database/>"
RESULT = {"file_name": FILE_NAME, "file_type": ".gramps"}


class ExportHandlerTest(unittest.TestCase):
    """:meth:`webapihandler.WebApiHandler.download_xml`."""

    def login(self, routes: dict) -> tuple[WebApiHandler, FakeHttp]:
        http = FakeHttp({("POST", f"{URL}/token/"): {"access_token": jwt()}, **routes})
        for target, value in (
            ("webapihandler.urlopen", http),
            ("webapihandler.platform.system", lambda: "Linux"),
            ("webapihandler.sleep", lambda _seconds: None),
        ):
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        return WebApiHandler(URL, "owner", "secret"), http

    def download(self, routes: dict) -> tuple[bytes, list]:
        handler, http = self.login(routes)
        self.progress: list[float] = []
        path = handler.download_xml(self.progress.append)
        self.addCleanup(os.remove, path)
        return path.read_bytes(), http.calls()[1:]

    def test_the_export_runs_as_a_task_and_the_file_is_downloaded(self) -> None:
        content, calls = self.download(
            {
                ("POST", EXPORT): {"task": {"id": "abc"}},
                ("GET", TASK): [
                    {"state": "PENDING", "result_object": None},
                    {"state": "PROGRESS", "result_object": {"progress": 0.5}},
                    {"state": "SUCCESS", "result_object": RESULT},
                ],
                ("GET", PROCESSED): gzip.compress(XML),
            }
        )
        self.assertEqual(content, XML)
        self.assertEqual(
            calls,
            [("POST", EXPORT)] + [("GET", TASK)] * 3 + [("GET", PROCESSED)],
        )
        self.assertEqual(self.progress, [-1, 0.5, 1])

    def test_a_server_without_a_task_queue_answers_with_the_file_at_once(
        self,
    ) -> None:
        content, calls = self.download(
            {
                ("POST", EXPORT): RESULT,
                ("GET", PROCESSED): gzip.compress(XML),
            }
        )
        self.assertEqual(content, XML)
        self.assertEqual(calls, [("POST", EXPORT), ("GET", PROCESSED)])

    def test_a_failed_export_says_so(self) -> None:
        handler, _ = self.login(
            {
                ("POST", EXPORT): {"task": {"id": "abc"}},
                ("GET", TASK): {"state": "FAILURE", "info": "disk full"},
            }
        )
        with self.assertRaises(ExportFailed) as caught:
            handler.download_xml()
        error = SyncSession._classify(mock.Mock(), caught.exception)
        self.assertEqual(error.kind, ErrorKind.EXPORT_FAILED)
        message = error_message(error.kind, error.detail)
        self.assertIn("disk full", message)
        self.assertIn("export", message)


if __name__ == "__main__":
    unittest.main()
