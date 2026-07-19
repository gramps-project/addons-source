#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Dmitry Bryndin
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

import unittest
from name_processor.presentation.markup import (
    pango_escape,
    generate_pango_diff,
    format_confidence,
)


class TestPangoEscape(unittest.TestCase):
    def test_escapes_ampersand(self):
        self.assertEqual(pango_escape("AT&T"), "AT&amp;T")

    def test_escapes_less_than(self):
        self.assertEqual(pango_escape("a<b"), "a&lt;b")

    def test_escapes_greater_than(self):
        self.assertEqual(pango_escape("a>b"), "a&gt;b")

    def test_escapes_all_special_chars(self):
        self.assertEqual(pango_escape("<a&b>"), "&lt;a&amp;b&gt;")


class TestGeneratePangoDiff(unittest.TestCase):
    def test_old_to_new_diff(self):
        self.assertEqual(
            generate_pango_diff("Иванович", "Ивановна"),
            "Иванович → <span weight='bold'>Ивановна</span>",
        )

    def test_empty_old_bold_new(self):
        self.assertEqual(
            generate_pango_diff("", "Ивановна"),
            "<span weight='bold'>Ивановна</span>",
        )

    def test_empty_new_old_only(self):
        self.assertEqual(generate_pango_diff("Иванович", ""), "Иванович")

    def test_both_empty(self):
        self.assertEqual(generate_pango_diff("", ""), "")

    def test_xml_escaping_in_diff(self):
        self.assertEqual(
            generate_pango_diff("<old>", "<new>"),
            "&lt;old&gt; → <span weight='bold'>&lt;new&gt;</span>",
        )


class TestFormatConfidence(unittest.TestCase):
    def test_zero_confidence(self):
        self.assertEqual(format_confidence(0.0), "0%")

    def test_half_confidence(self):
        self.assertEqual(format_confidence(0.5), "50%")

    def test_full_confidence(self):
        self.assertEqual(format_confidence(1.0), "100%")

    def test_fractional_confidence(self):
        self.assertEqual(format_confidence(0.75), "75%")
