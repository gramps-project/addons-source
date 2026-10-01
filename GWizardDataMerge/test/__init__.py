"""Unit tests for the GWizard File Merge addon.

Consolidated from ``gramps.gen.gwizard.test`` (backend import framework
and GEDCOM tests) and ``gramps.gui.gwizard.test`` (merge dialog field
and styling tests) as part of the permanent migration of GWizard to a
standalone addon plugin.
"""

import os as _os
import sys as _sys

_addon_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _addon_dir not in _sys.path:
    _sys.path.insert(0, _addon_dir)
