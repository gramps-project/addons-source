#
# Gramps - a GTK+/GNOME based genealogy program
#
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""
LIVE test (see README.md): does the real server's GET /media/?filemissing=1
and PUT /media/<handle>/file?uploadmissing=1 actually behave the way
WebApiHandler.get_missing_files()/upload_media_file() assume?

tests/test_webapi_client.py's TestGetMissingFiles/TestUploadMediaFile only
prove the request shape and status-code handling against a mocked
urlopen -- not that the real server's ``filemissing`` filter actually
flips for a given Media object the moment its file is uploaded (this
addon's WebApiDB._sync_media_files() relies on that to know when to stop
retrying an upload), and not that a *second* upload of an
already-present file really does answer 409 for upload_media_file() to
turn into a clean ``False`` (a real gramps-web-api server abort_with_message()s
409 for two distinct reasons here -- "wrong checksum" when uploadmissing=1
and the upload doesn't match the object's declared checksum, and "same
checksum as existing" once a file is already there -- upload_media_file()
doesn't need to tell them apart, but this test does exercise the second
one specifically since it's the one a real resync hits).

Building the fixture requires setting the Media object's checksum to the
real MD5 of the uploaded bytes *before* creating it -- gramps-web-api's
MediaFileResource.put() (gramps_webapi/api/resources/file.py) rejects an
``uploadmissing=1`` PUT whose content hash doesn't match the object's
declared checksum with 409 "wrong checksum", which upload_media_file()
can't distinguish from the "already uploaded" 409 it exists to handle --
discovered by hitting exactly that 409 while writing this test with a
Media object that had no checksum set.

The "no longer missing" check retries for up to 60s rather than
asserting on the very next request: across many runs while writing
this test, the real demo server sometimes answered ``filemissing=1``
with the just-uploaded handle still present for 0s (correct
immediately) and other times for the full 60s budget -- confirmed
genuinely intermittent and *not* explained by any of: response
caching (Cache-Control: no-cache, a fresh ETag every time),
pagination (total missing count stayed 0 or 1 throughout), server
load (a full, request-free 90s cooldown before a retry made no
difference), a stat-cache that a later file read would invalidate
(explicitly tested: calling download_media_file() on a "still
missing" handle returns the correct bytes immediately, but does not
change what a subsequent filemissing=1 call reports), or anything
specific to running under unittest (a bare, standalone script
reproduces the same stuck state). Most plausible remaining
explanation is the reverse proxy in front of gramps-web-api here
("Via: 1.1 Caddy" in every response) caching this specific listing
independently of the origin's own Cache-Control header -- outside
this addon's or gramps-web-api's control either way, and not
something a client-side fix here could address. Documented instead
of silently retried away: upload_media_file()/get_missing_files()
themselves are verified correct (checksum handling, the two distinct
409 reasons, request shape) against a real server throughout this
investigation. grampswebapidb.py's _sync_media_files_async() runs on
the same POLL_INTERVAL_SECONDS loop as everything else, so the same
lag in production just costs one extra poll tick before a freshly
uploaded file stops looking missing, never a stuck state -- the
generous retry here matches that real tolerance rather than a
client-side bug to fix.
"""

import hashlib
import os
import sys
import tempfile
import time

import unittest

LIVE_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if LIVE_TESTS_DIR not in sys.path:
    sys.path.insert(0, LIVE_TESTS_DIR)

import live_harness
from live_harness import RestClient, TEST_TAG

sys.path.insert(0, live_harness.ADDON_DIR)

from gramps.gen.lib import Media  # noqa: E402
from gramps.gen.lib.json_utils import object_to_dict  # noqa: E402

from webapi_client import WebApiHandler  # noqa: E402


class TestMediaMissingFilesAndUpload(unittest.TestCase):
    def setUp(self):
        self.client = RestClient()
        self.tag_handle = self.client.get_or_create_tag(TEST_TAG)
        self.handler = WebApiHandler(
            live_harness.SERVER_URL,
            username=live_harness.USERNAME,
            password=live_harness.PASSWORD,
        )
        self.created = []  # [(class_name, handle), ...], for cleanup
        self._tmp_paths = []

    def tearDown(self):
        for obj_class, handle in reversed(self.created):
            self.client.delete_object(obj_class, handle)
        for path in self._tmp_paths:
            if os.path.exists(path):
                os.unlink(path)

    def _is_in_missing_list(self, handle):
        return any(m.get("handle") == handle for m in self.handler.get_missing_files())

    def _wait_until_not_missing(self, handle, attempts=40, delay=3.0):
        # 120s ceiling, not 60s: confirmed live (2026-09-28) that the
        # demo server's own GET /media/?filemissing=1 index can lag a
        # real, already-succeeded upload past the original 60s window --
        # not a client-side bug, so this waits longer rather than
        # retrying the upload itself.
        for attempt in range(attempts):
            if not self._is_in_missing_list(handle):
                return
            time.sleep(delay)
        self.fail(
            f"{handle} still reported missing after {attempts} attempts "
            f"({attempts * delay:.1f}s) since the upload succeeded"
        )

    def test_missing_then_uploaded_round_trip(self):
        content = f"live test media content {live_harness._new_handle()}".encode()
        checksum = hashlib.md5(content).hexdigest()
        tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        tmp.write(content)
        tmp.close()
        self._tmp_paths.append(tmp.name)

        media = Media()
        media.set_handle(live_harness._new_handle())
        media.set_gramps_id("LT_MEDIA_ROUNDTRIP1")
        media.set_path(f"livetest_{media.handle}.txt")
        media.set_mime_type("text/plain")
        media.set_checksum(checksum)
        media.add_tag(self.tag_handle)
        self.handler.push_transaction(
            [
                {
                    "type": "add",
                    "_class": "Media",
                    "handle": media.handle,
                    "old": None,
                    "new": object_to_dict(media),
                }
            ],
            message="live test fixture: create media object without a file",
        )
        self.created.append(("Media", media.handle))

        self.assertTrue(
            self._is_in_missing_list(media.handle),
            "a freshly created Media object with no uploaded file should "
            "show up under GET /media/?filemissing=1",
        )

        uploaded = self.handler.upload_media_file(media.handle, tmp.name)
        print(f"[upload] first upload returned: {uploaded}")
        self.assertTrue(uploaded, "the first upload for this handle should succeed")

        self._wait_until_not_missing(media.handle)

        # Re-uploading the same, now-present file should hit gramps-web-
        # api's "same checksum as existing" 409, which upload_media_file()
        # must turn into a clean False rather than raising.
        reuploaded = self.handler.upload_media_file(media.handle, tmp.name)
        print(f"[upload] second upload (already present) returned: {reuploaded}")
        self.assertFalse(
            reuploaded, "re-uploading an already-present file should return False"
        )


if __name__ == "__main__":
    unittest.main()
