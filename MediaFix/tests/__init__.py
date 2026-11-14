"""Make the flat MediaFix addon modules importable when running the tests.

Gramps puts the addon directory on sys.path when it loads the plugin, but
``python3 -m unittest MediaFix.tests.<module>`` run from the directory that
holds the addon does not, so this package initializer adds it (and the
directories of the addons it depends on, when they sit alongside).
"""
import os
import sys

_ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARENT = os.path.dirname(_ADDON_DIR)
for _path in [os.path.join(_PARENT, _name) for _name in []] + [
    _ADDON_DIR
]:
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)
