# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       Florian J. Breunig
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

"""The macOS trust store is assembled from every keychain, not just Apple's.

``security`` is stubbed throughout, so these run on any platform and never
touch the host's real keychains.
"""

from __future__ import annotations

import subprocess
import unittest
import unittest.mock

from webapihandler import (
    MACOS_ADMIN_KEYCHAIN,
    MACOS_ROOT_KEYCHAIN,
    _macos_keychains,
    create_macos_ssl_context,
)

LOGIN_KEYCHAIN = "/Users/someone/Library/Keychains/login.keychain-db"

#: What ``security list-keychains`` prints: indented and quoted.
LIST_OUTPUT = f'    "{LOGIN_KEYCHAIN}"\n    "{MACOS_ADMIN_KEYCHAIN}"\n'


def fake_security(list_output: str = LIST_OUTPUT, certs: dict | None = None):
    """Return a ``subprocess.run`` stub answering the two ``security`` calls.

    ``certs`` maps a keychain path to the PEM bytes it should yield; a path
    mapped to an exception has that exception raised instead, standing in for
    a keychain that cannot be read.
    """
    certs = {} if certs is None else certs

    def run(cmd, **kwargs):
        if cmd[1] == "list-keychains":
            return subprocess.CompletedProcess(cmd, 0, stdout=list_output.encode())
        keychain = cmd[-1]
        result = certs.get(keychain, b"")
        if isinstance(result, Exception):
            raise result
        return subprocess.CompletedProcess(cmd, 0, stdout=result)

    return run


class KeychainListTest(unittest.TestCase):
    """Which keychains are searched, and in what order."""

    def test_apple_roots_and_admin_keychain_come_first(self):
        with unittest.mock.patch("subprocess.run", fake_security()):
            keychains = _macos_keychains()
        self.assertEqual(keychains[:2], [MACOS_ROOT_KEYCHAIN, MACOS_ADMIN_KEYCHAIN])

    def test_search_list_is_appended(self):
        """A CA in the login keychain is reachable — the point of the fix."""
        with unittest.mock.patch("subprocess.run", fake_security()):
            keychains = _macos_keychains()
        self.assertIn(LOGIN_KEYCHAIN, keychains)

    def test_no_duplicates(self):
        """The admin keychain is usually in the search list as well."""
        with unittest.mock.patch("subprocess.run", fake_security()):
            keychains = _macos_keychains()
        self.assertEqual(len(keychains), len(set(keychains)))

    def test_survives_security_failing(self):
        """Without a usable search list, the two known keychains still stand."""

        def boom(cmd, **kwargs):
            raise OSError("security not found")

        with unittest.mock.patch("subprocess.run", boom):
            keychains = _macos_keychains()
        self.assertEqual(keychains, [MACOS_ROOT_KEYCHAIN, MACOS_ADMIN_KEYCHAIN])


class SSLContextTest(unittest.TestCase):
    """What ends up in the file handed to OpenSSL."""

    def load_verify_calls(self, certs):
        """Collect the PEM bytes ``create_macos_ssl_context`` loads."""
        loaded: list[bytes] = []

        def load_verify_locations(path):
            with open(path, "rb") as handle:
                loaded.append(handle.read())

        ctx = unittest.mock.Mock()
        ctx.load_verify_locations.side_effect = load_verify_locations
        with unittest.mock.patch("subprocess.run", fake_security(certs=certs)):
            with unittest.mock.patch("ssl.create_default_context", return_value=ctx):
                create_macos_ssl_context()
        return loaded

    def test_certificates_from_every_keychain_are_loaded(self):
        loaded = self.load_verify_calls(
            {
                MACOS_ROOT_KEYCHAIN: b"-----BEGIN CERTIFICATE-----\napple\n",
                MACOS_ADMIN_KEYCHAIN: b"-----BEGIN CERTIFICATE-----\nprivate-ca\n",
                LOGIN_KEYCHAIN: b"-----BEGIN CERTIFICATE-----\nuser-ca\n",
            }
        )
        self.assertEqual(len(loaded), 1)
        self.assertIn(b"apple", loaded[0])
        self.assertIn(b"private-ca", loaded[0])
        self.assertIn(b"user-ca", loaded[0])

    def test_written_file_is_flushed_before_openssl_reads_it(self):
        """A buffered write would truncate a realistically sized anchor list."""
        bulk = b"".join(
            b"-----BEGIN CERTIFICATE-----\n%d\n" % index for index in range(4000)
        )
        loaded = self.load_verify_calls(
            {MACOS_ROOT_KEYCHAIN: bulk, MACOS_ADMIN_KEYCHAIN: b"tail-marker\n"}
        )
        self.assertIn(b"tail-marker", loaded[0])
        self.assertEqual(len(loaded[0]), len(bulk) + len(b"\ntail-marker\n"))

    def test_unreadable_keychain_does_not_lose_the_others(self):
        loaded = self.load_verify_calls(
            {
                MACOS_ROOT_KEYCHAIN: b"apple\n",
                MACOS_ADMIN_KEYCHAIN: subprocess.TimeoutExpired("security", 30),
                LOGIN_KEYCHAIN: b"user-ca\n",
            }
        )
        self.assertIn(b"apple", loaded[0])
        self.assertIn(b"user-ca", loaded[0])

    def test_no_certificates_at_all_is_not_fatal(self):
        """An empty store still returns a context rather than raising."""
        self.assertEqual(self.load_verify_calls({}), [])


if __name__ == "__main__":
    unittest.main()
