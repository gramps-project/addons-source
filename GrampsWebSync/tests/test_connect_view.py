# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       scotCW
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

"""Which saved sign-in the connect pane sends.

The tool is built without its window: the panes and the session are mocks,
so no display is needed.
"""

from __future__ import annotations

import unittest
from unittest import mock

from const import AUTH_PASSWORD, AUTH_SYNC_TOKEN, TOKEN_PROBLEM_LIMIT
from grampswebsync import GrampsWebSyncTool
from session import State

from .fakes import MemoryCredentialStore
from .scenario import DEFAULT_URL as URL


class ViewCredentialStore(MemoryCredentialStore):
    """The memory store with the extra queries the view makes."""

    def keyring_error(self):
        return None

    def is_from_another_tree(self) -> bool:
        return False


class ConnectViewTest(unittest.TestCase):
    """The connect pane uses the token the store holds now."""

    def setUp(self) -> None:
        self.credentials = ViewCredentialStore(password="T1")
        self.credentials.auth = AUTH_SYNC_TOKEN
        self.credentials.token_ids[(URL, "owner")] = 1
        self.tool = object.__new__(GrampsWebSyncTool)
        self.tool.credentials = self.credentials
        self.tool.session = mock.MagicMock(login_error=None, token_problem=None)
        self.tool.connect_pane = mock.MagicMock()
        self.tool.connect_pane.url.get_text.return_value = URL
        self.tool.connect_pane.username.get_text.return_value = "owner"
        self.tool.connect_pane.password.get_text.return_value = ""
        self.tool.connect_pane.remember_password = True
        # What opening the window does.
        self.tool._load_saved_sign_in()
        self.tool._prepare_pane(State.CONNECT)

    def submitted(self):
        """Press Connect with the password field empty; return what was sent."""
        self.tool._submit()
        args, kwargs = self.tool.session.submit_credentials.call_args
        return args[2], kwargs["auth"]

    def test_the_stored_token_is_sent(self) -> None:
        self.assertEqual(self.submitted(), ("T1", AUTH_SYNC_TOKEN))

    def test_a_token_replaced_by_a_password_sign_in_is_not_sent(self) -> None:
        """Sign in with the password, then "Change server…" and Connect.

        The first token was revoked at that sign-in. Sending it would get a
        401, and the session would then forget the new one, leaving it live
        on the server with no id to revoke it by.
        """
        self.credentials.save_credentials(
            URL, "owner", "T2", auth=AUTH_SYNC_TOKEN, token_id=2
        )
        self.tool._prepare_pane(State.CONNECT)
        self.assertEqual(self.submitted(), ("T2", AUTH_SYNC_TOKEN))

    def test_a_rejected_token_is_not_sent_again(self) -> None:
        self.credentials.forget_secret(URL, "owner")
        self.tool._prepare_pane(State.CONNECT)
        self.assertEqual(self.submitted(), ("", AUTH_PASSWORD))

    def test_staying_signed_in_unticked_leaves_no_token_to_send(self) -> None:
        self.credentials.save_credentials(URL, "owner", None, remember_password=False)
        self.tool._prepare_pane(State.CONNECT)
        self.assertEqual(self.submitted(), ("", AUTH_PASSWORD))

    def test_a_sign_in_that_could_not_be_kept_is_explained(self) -> None:
        self.credentials.token_problem = TOKEN_PROBLEM_LIMIT
        self.tool._prepare_pane(State.CONNECT)
        notices = self.tool.connect_pane.set_notices.call_args[0][0]
        self.assertTrue(any("too many devices" in notice for notice in notices))


if __name__ == "__main__":
    unittest.main()
