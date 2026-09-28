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
lists a Media object that has no file yet, that an ``uploadmissing=1``
PUT really stores the file, and not that a *second* upload of an
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

After the upload, this test deliberately does *not* re-ask
``filemissing=1``: that listing is served from gramps-web-api's request
cache (``@request_cache_decorator`` on the list endpoint,
gramps_webapi/api/cache.py), keyed on the tree's ``meta_data.db``
mtime, with ``CACHE_DEFAULT_TIMEOUT: 0`` (never expires). The
``uploadmissing=1`` PUT only writes the file -- no DbTxn, so the mtime
doesn't move -- and the pre-upload ``filemissing=1`` call this test
makes has already primed that cache with the handle listed as missing.
The stale answer then persists until some unrelated write to the tree
bumps the mtime, which is why earlier versions of this test (waiting
up to 60s, then 120s) passed or failed depending on what else was
touching the demo server. That's a gramps-web-api cache-invalidation
bug, not something this client can fix. Instead, "the file is really
there now" is proven two uncached ways: download_media_file() returns
the uploaded bytes, and a second upload hits the "same checksum as
existing" 409, which the server decides with a direct
file_handler.file_exists() check.
"""

import hashlib
import os
import sys
import tempfile

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

        # Not _is_in_missing_list() again -- see the module docstring:
        # that listing is cached server-side and stays stale after an
        # uploadmissing=1 PUT.
        download_path = tmp.name + ".downloaded"
        self._tmp_paths.append(download_path)
        self.handler.download_media_file(media.handle, download_path)
        with open(download_path, "rb") as fp:
            self.assertEqual(
                fp.read(), content, "the server should serve back the uploaded bytes"
            )

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
