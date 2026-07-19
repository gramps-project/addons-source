"""Guard: the repo-root test suite pins GTK/GDK to 3 (via tests/__init__.py)."""

import unittest


class GtkGdkVersionPin(unittest.TestCase):
    def test_suite_pins_gtk_and_gdk_to_3(self):
        try:
            import gi
        except ImportError:
            self.skipTest("PyGObject not available")
        repo = gi.Repository.get_default()
        if "3.0" not in repo.enumerate_versions("Gtk") or \
           "3.0" not in repo.enumerate_versions("Gdk"):
            self.skipTest("GTK/GDK 3.0 introspection typelibs not installed")
        # Importing the tests package ran tests/__init__.py, which must pin both.
        self.assertEqual(gi.get_required_version("Gtk"), "3.0")
        self.assertEqual(gi.get_required_version("Gdk"), "3.0")
