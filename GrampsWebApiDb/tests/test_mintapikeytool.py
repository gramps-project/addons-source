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
Unit tests for mintapikeytool.MintApiKeyTool's key minting: preferring a
sync-token key, falling back to a refresh-token key only on a server too
old for sync tokens, and explaining a duplicate key name or a full
key list.

The dialog itself isn't built: the methods under test are called unbound
on a mock ``self``, with GLib.idle_add run inline.

Run with::

    python3 -m unittest GrampsWebApiDb.tests.test_mintapikeytool -v
"""

import io
import json
import os
import sys
import unittest
from unittest import mock
from urllib.error import HTTPError

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gi
except ImportError as err:
    raise unittest.SkipTest("PyGObject not available: %s" % err)

try:
    import mintapikeytool
    from mintapikeytool import MintApiKeyTool
    from webapi_client import SyncTokensUnsupportedError, WebApiHandler
except ImportError as _err:
    raise unittest.SkipTest("gramps package not available: %s" % _err)

URL = "https://example.com/api"


def http_error_with_message(code, message):
    """An HTTPError carrying gramps-web-api's {"error": {"message": ...}}
    body, the way abort_with_message() sends it."""
    body = json.dumps({"error": {"code": code, "message": message}}).encode()
    return HTTPError(URL, code, "HTTP %d" % code, None, io.BytesIO(body))


class TestMintApiKey(unittest.TestCase):
    def setUp(self):
        self.tool = mock.Mock()
        self.tool._describe_mint_error = MintApiKeyTool._describe_mint_error
        patcher = mock.patch.object(
            mintapikeytool.GLib, "idle_add", lambda func, *args: func(*args)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _mint(self, label="laptop"):
        MintApiKeyTool._mint_api_key(self.tool, URL, "alice", "secret", label)

    def test_prefers_sync_token_key(self):
        with (
            mock.patch.object(
                WebApiHandler, "mint_sync_api_key", return_value="SYNCKEY"
            ) as mint_sync,
            mock.patch.object(WebApiHandler, "mint_api_key") as mint_refresh,
        ):
            self._mint()
        mint_sync.assert_called_once_with(URL, "alice", "secret", "laptop")
        mint_refresh.assert_not_called()
        self.tool._mint_succeeded.assert_called_once_with("SYNCKEY", True)

    def test_empty_label_defaults_to_hostname(self):
        with (
            mock.patch.object(mintapikeytool.socket, "gethostname", return_value="box"),
            mock.patch.object(
                WebApiHandler, "mint_sync_api_key", return_value="SYNCKEY"
            ) as mint_sync,
        ):
            self._mint(label="")
        self.assertIn("box", mint_sync.call_args.args[3])

    def test_old_server_falls_back_to_refresh_token_key(self):
        with (
            mock.patch.object(
                WebApiHandler,
                "mint_sync_api_key",
                side_effect=SyncTokensUnsupportedError("too old"),
            ),
            mock.patch.object(
                WebApiHandler, "mint_api_key", return_value="REFRESHKEY"
            ) as mint_refresh,
        ):
            self._mint()
        mint_refresh.assert_called_once_with(URL, "alice", "secret")
        self.tool._mint_succeeded.assert_called_once_with("REFRESHKEY", False)

    def test_duplicate_key_name_is_explained(self):
        conflict = HTTPError(URL, 409, "Conflict", None, None)
        with (
            mock.patch.object(WebApiHandler, "mint_sync_api_key", side_effect=conflict),
            mock.patch.object(WebApiHandler, "mint_api_key") as mint_refresh,
        ):
            self._mint()
        mint_refresh.assert_not_called()
        message = self.tool._mint_failed.call_args.args[0]
        self.assertIn('"laptop"', message)
        self.tool._mint_succeeded.assert_not_called()

    def test_duplicate_key_name_with_server_message(self):
        conflict = http_error_with_message(
            409, "An access token with this label exists"
        )
        with mock.patch.object(
            WebApiHandler, "mint_sync_api_key", side_effect=conflict
        ):
            self._mint()
        self.assertIn('"laptop"', self.tool._mint_failed.call_args.args[0])

    def test_key_limit_is_not_reported_as_duplicate_name(self):
        conflict = http_error_with_message(
            409, "Maximum number of access tokens reached"
        )
        with (
            mock.patch.object(WebApiHandler, "mint_sync_api_key", side_effect=conflict),
            mock.patch.object(WebApiHandler, "mint_api_key") as mint_refresh,
        ):
            self._mint()
        mint_refresh.assert_not_called()
        message = self.tool._mint_failed.call_args.args[0]
        self.assertIn("maximum number of API keys", message)
        self.assertNotIn('"laptop"', message)

    def test_other_error_shows_server_message(self):
        error = http_error_with_message(422, "Label too long")
        with mock.patch.object(WebApiHandler, "mint_sync_api_key", side_effect=error):
            self._mint()
        self.assertIn("Label too long", self.tool._mint_failed.call_args.args[0])

    def test_default_key_name_fits_server_limit(self):
        with (
            mock.patch.object(
                mintapikeytool.socket, "gethostname", return_value="h" * 300
            ),
            mock.patch.object(
                WebApiHandler, "mint_sync_api_key", return_value="SYNCKEY"
            ) as mint_sync,
        ):
            self._mint(label="")
        self.assertEqual(
            len(mint_sync.call_args.args[3]), mintapikeytool._KEY_NAME_MAX_LENGTH
        )

    def test_login_failure_is_not_retried_as_refresh_key(self):
        with (
            mock.patch.object(
                WebApiHandler,
                "mint_sync_api_key",
                side_effect=HTTPError(URL, 401, "Unauthorized", None, None),
            ),
            mock.patch.object(WebApiHandler, "mint_api_key") as mint_refresh,
        ):
            self._mint()
        mint_refresh.assert_not_called()
        self.assertIn("401", self.tool._mint_failed.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
