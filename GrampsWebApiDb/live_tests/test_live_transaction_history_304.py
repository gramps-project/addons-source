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
LIVE test (see README.md): does the real server's answer to a repeated,
unchanged transaction-history request actually reach
WebApiHandler.get_transaction_history() as a clean ``([], total_count)``
now, instead of raising?

tests/test_webapi_client.py's TestTransactionHistory 304 cases are mocked
at the ``urlopen`` replacement level, so they can only prove the code
does what its author intended a 304 to look like -- and the bug this
addon shipped was exactly that the mocked shape (a "successful" response
object whose ``getcode()`` returns 304) can never happen for real:
``urllib.request.urlopen`` runs every response through
``HTTPErrorProcessor``, which raises ``HTTPError`` for anything outside
200-299, 304 included. Only a real round trip against a real
gramps-web-api server can show whether the fix (handling
``exc.code == 304`` in the ``except HTTPError`` branch, reading
``X-Total-Count``/``ETag`` off ``exc.headers``) actually lines up with
what the server sends on the wire.

Note on flakiness: this repeats the exact same request twice with
nothing deliberately changed server-side in between, which is the
steady-state idle poll grampswebapidb.py's ``_poll_tick()`` makes
forever. Since the demo tree is shared with other visitors (see
README.md), a concurrent edit by someone else between the two calls
would make the server answer 200 instead of 304 -- this test does not
retry around that, so an occasional failure here may just mean someone
else edited the tree mid-test, not a regression.
"""

import os
import sys

import unittest

LIVE_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if LIVE_TESTS_DIR not in sys.path:
    sys.path.insert(0, LIVE_TESTS_DIR)

import live_harness
from live_harness import RestClient, TEST_TAG

sys.path.insert(0, live_harness.ADDON_DIR)

from webapi_client import WebApiHandler  # noqa: E402


class TestTransactionHistory304(unittest.TestCase):
    def setUp(self):
        # Just to confirm the account/server are reachable and tagged
        # test data stays discoverable by sweep.py even though this test
        # creates no objects of its own.
        self.client = RestClient()
        self.client.get_or_create_tag(TEST_TAG)

    def test_repeated_idle_poll_gets_a_real_304_not_an_exception(self):
        handler = WebApiHandler(
            live_harness.SERVER_URL,
            username=live_harness.USERNAME,
            password=live_harness.PASSWORD,
        )

        # First call: establishes handler._history_etag from whatever the
        # server currently reports for this exact set of args.
        first_transactions, first_total = handler.get_transaction_history(
            after_id=0, pagesize=1, sort="-id"
        )
        etag_after_first = handler._history_etag
        self.assertIsNotNone(
            etag_after_first,
            "server sent no ETag -- can't exercise the 304 path against "
            "it (too old? see HISTORY_ID_CURSOR_MIN_API_VERSION)",
        )
        print(f"[etag] after first call: {etag_after_first}")

        # Second call: identical args, nothing changed server-side. Before
        # the fix, get_transaction_history() would hit the except
        # HTTPError branch's unconditional `raise` here -- exactly the
        # every-poll-logged-as-a-failure symptom the review flagged.
        second_transactions, second_total = handler.get_transaction_history(
            after_id=0, pagesize=1, sort="-id"
        )
        print(
            f"[304 result] transactions={second_transactions!r} "
            f"total={second_total} etag={handler._history_etag}"
        )
        self.assertEqual(second_transactions, [])
        self.assertEqual(second_total, first_total)
        self.assertEqual(handler._history_etag, etag_after_first)


if __name__ == "__main__":
    unittest.main()
