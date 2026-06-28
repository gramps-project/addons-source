"""Shared pytest configuration for GrampsAssist tests."""

import sys
import os

# Make GrampsAssist importable without installing it.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
