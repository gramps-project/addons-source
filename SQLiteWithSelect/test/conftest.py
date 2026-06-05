import sys
import os

# Add the addon directory so local modules can be imported directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Add gramps source if not already importable
sys.path.insert(0, "/home/dsblank/gramps/gramps")
