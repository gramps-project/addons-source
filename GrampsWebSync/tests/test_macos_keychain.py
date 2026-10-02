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

"""Tests for the macOS keychain fallback in :mod:`adapters`.

Most of these replace ``subprocess.run`` and run on every platform. The last
class uses the real login keychain and runs on macOS only.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import types
import unittest
import uuid
from unittest import mock

from adapters import (
    MACOS_SECURITY,
    SECURITY_ITEM_NOT_FOUND,
    Keyring,
    MacOSKeychain,
    parse_security_password,
)

#: Secrets that exercise the quoting and the two output forms of ``security``.
AWKWARD = [
    "plain",
    "sp ace",
    'q"uote',
    "single'q",
    "back\\slash",
    'mix \\" end\\',
    "ünïcødé€",
    "$HOME `x`; rm",
    "trailing ",
    "0xdeadbeef",
    "c3bc6e",
]


def completed(returncode: int = 0, stderr: bytes = b""):
    """Return what ``subprocess.run`` would for one ``security`` call."""
    return subprocess.CompletedProcess([], returncode, None, stderr)


def found(secret: str) -> bytes:
    """Return the ``-g`` stderr for ``secret``, in the hex form."""
    return b"password: 0x" + secret.encode().hex().upper().encode() + b'  "..."\n'


class ParseSecurityPasswordTest(unittest.TestCase):
    """The two forms ``security find-generic-password -g`` prints."""

    def test_a_quoted_value_is_taken_literally(self) -> None:
        self.assertEqual(parse_security_password(b'password: "c3bc6e"\n'), "c3bc6e")

    def test_the_hex_form_is_decoded_as_utf8(self) -> None:
        self.assertEqual(parse_security_password(found('ünï "q"')), 'ünï "q"')

    def test_other_lines_are_skipped(self) -> None:
        output = b'keychain: "/x"\nclass: "genp"\npassword: "s3cret"\n'
        self.assertEqual(parse_security_password(output), "s3cret")

    def test_an_empty_password(self) -> None:
        self.assertEqual(parse_security_password(b"password: \n"), "")

    def test_unexpected_output_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_security_password(b"something else\n")


class MacOSKeychainTest(unittest.TestCase):
    """The ``security`` calls, with ``subprocess.run`` replaced."""

    def setUp(self) -> None:
        patcher = mock.patch("adapters.subprocess.run")
        self.run = patcher.start()
        self.addCleanup(patcher.stop)
        self.keychain = MacOSKeychain()

    def argvs(self) -> list[list[str]]:
        return [call.args[0] for call in self.run.call_args_list]

    def test_get_returns_the_stored_secret(self) -> None:
        self.run.return_value = completed(stderr=found("s3cret"))
        self.assertEqual(self.keychain.get_password("svc", "acct"), "s3cret")
        self.assertEqual(
            self.argvs(),
            [
                [
                    MACOS_SECURITY,
                    "find-generic-password",
                    "-s",
                    "svc",
                    "-a",
                    "acct",
                    "-g",
                ]
            ],
        )

    def test_get_returns_none_for_a_missing_item(self) -> None:
        self.run.return_value = completed(SECURITY_ITEM_NOT_FOUND)
        self.assertIsNone(self.keychain.get_password("svc", "acct"))

    def test_get_raises_other_failures(self) -> None:
        self.run.return_value = completed(51, b"User interaction is not allowed.")
        with self.assertRaises(OSError):
            self.keychain.get_password("svc", "acct")

    def test_the_secret_never_appears_on_a_command_line(self) -> None:
        """Other processes of the same user can read command lines."""
        self.run.side_effect = [completed(), completed(stderr=found("s3cret"))]
        self.keychain.set_password("svc", "acct", "s3cret")
        self.assertEqual(self.argvs()[0], [MACOS_SECURITY, "-i"])
        for argv in self.argvs():
            self.assertNotIn("s3cret", " ".join(argv))
        self.assertIn(b"s3cret", self.run.call_args_list[0].kwargs["input"])

    def test_awkward_values_are_quoted_as_single_arguments(self) -> None:
        for secret in AWKWARD:
            with self.subTest(secret=secret):
                self.run.reset_mock()
                self.run.side_effect = [completed(), completed(stderr=found(secret))]
                self.keychain.set_password("svc", 'ac"ct', secret)
                command = self.run.call_args_list[0].kwargs["input"].decode()
                self.assertTrue(command.endswith("\n"))
                self.assertEqual(
                    shlex.split(command),
                    ["add-generic-password", "-U", "-s", "svc", "-a", 'ac"ct']
                    + ["-w", secret],
                )

    def test_line_breaks_are_refused_before_running_anything(self) -> None:
        for secret in ("two\nlines", "carriage\rreturn"):
            with self.subTest(secret=secret), self.assertRaises(ValueError):
                self.keychain.set_password("svc", "acct", secret)
        self.run.assert_not_called()

    def test_a_write_that_does_not_read_back_fails(self) -> None:
        """``security -i`` exits 0 for some failed writes."""
        self.run.side_effect = [completed(), completed(SECURITY_ITEM_NOT_FOUND)]
        with self.assertRaises(OSError):
            self.keychain.set_password("svc", "acct", "s3cret")

    def test_a_failed_command_raises(self) -> None:
        self.run.return_value = completed(1, b"add-generic-password: returned 1")
        with self.assertRaises(OSError):
            self.keychain.set_password("svc", "acct", "s3cret")

    def test_deleting_a_missing_item_raises_like_keyring(self) -> None:
        self.run.return_value = completed(SECURITY_ITEM_NOT_FOUND)
        with self.assertRaises(OSError):
            self.keychain.delete_password("svc", "acct")


class KeyringFallbackTest(unittest.TestCase):
    """When :class:`Keyring` falls back to the macOS keychain."""

    def setUp(self) -> None:
        patcher = mock.patch("adapters.subprocess.run")
        self.run = patcher.start()
        self.addCleanup(patcher.stop)

    def without_keyring(self, mac: bool):
        """Make ``import keyring`` fail, on macOS or elsewhere."""
        modules = mock.patch.dict(sys.modules, {"keyring": None})
        platform = mock.patch.object(MacOSKeychain, "is_available", return_value=mac)
        modules.start()
        platform.start()
        self.addCleanup(modules.stop)
        self.addCleanup(platform.stop)

    def test_macos_without_the_package_uses_the_keychain(self) -> None:
        """The case in the macOS Gramps bundle: the password used to be lost."""
        self.without_keyring(mac=True)
        self.run.side_effect = [completed(), completed(stderr=found("s3cret"))]
        keyring = Keyring()
        self.assertTrue(keyring.set("https://example.org/api", "owner", "s3cret"))
        self.assertIsNone(keyring.unavailable)
        self.run.side_effect = None
        self.run.return_value = completed(stderr=found("s3cret"))
        self.assertEqual(keyring.get("https://example.org/api", "owner"), "s3cret")

    def test_deleting_what_was_never_stored_is_fine(self) -> None:
        self.without_keyring(mac=True)
        self.run.return_value = completed(SECURITY_ITEM_NOT_FOUND)
        keyring = Keyring()
        self.assertTrue(keyring.delete("https://example.org/api", "owner"))
        self.assertIsNone(keyring.unavailable)

    def test_a_failing_keychain_is_reported_as_unavailable(self) -> None:
        self.without_keyring(mac=True)
        self.run.return_value = completed(51, b"User interaction is not allowed.")
        keyring = Keyring()
        self.assertIsNone(keyring.get("https://example.org/api", "owner"))
        self.assertIsNotNone(keyring.unavailable)

    def test_elsewhere_without_the_package_it_stays_unavailable(self) -> None:
        self.without_keyring(mac=False)
        keyring = Keyring()
        self.assertIsNone(keyring.get("https://example.org/api", "owner"))
        self.assertIsNotNone(keyring.unavailable)
        self.run.assert_not_called()

    def test_the_keyring_package_is_still_preferred(self) -> None:
        package = types.SimpleNamespace(get_password=lambda service, user: "pkg")
        with mock.patch.dict(sys.modules, {"keyring": package}):
            self.assertEqual(Keyring().get("https://example.org/api", "owner"), "pkg")
        self.run.assert_not_called()


@unittest.skipUnless(
    sys.platform == "darwin" and os.access(MACOS_SECURITY, os.X_OK),
    "needs the macOS login keychain",
)
class RealKeychainTest(unittest.TestCase):
    """Round trips through the actual ``security`` tool."""

    def setUp(self) -> None:
        self.service = f"grampswebsync-test-{uuid.uuid4().hex}"
        self.keychain = MacOSKeychain()

    def tearDown(self) -> None:
        try:
            self.keychain.delete_password(self.service, "test")
        except OSError:
            pass

    def test_awkward_values_round_trip(self) -> None:
        for secret in AWKWARD:
            with self.subTest(secret=secret):
                self.keychain.set_password(self.service, "test", secret)
                self.assertEqual(
                    self.keychain.get_password(self.service, "test"), secret
                )

    def test_deleting_removes_the_item(self) -> None:
        self.keychain.set_password(self.service, "test", "s3cret")
        self.keychain.delete_password(self.service, "test")
        self.assertIsNone(self.keychain.get_password(self.service, "test"))
