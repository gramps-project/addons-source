"""Make the flat GWizard addon modules importable when running the tests."""
import os
import sys

_ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ADDON_DIR not in sys.path:
    sys.path.insert(0, _ADDON_DIR)
