"""Shared pytest configuration for GrampyScript tests."""

import sys
import os

# Make GrampyScript importable without installing it.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
