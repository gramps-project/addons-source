"""
Provides utility methods for working with URLs in the WebSearch Gramplet.

Includes functions for compiling regex patterns, extracting and cleaning URLs,
and formatting structured data into the expected tuple format.
"""

import re
from constants import URL_REGEX, URL_RSTRIP


class UrlUtils:
    """A collection of static utility methods for processing and formatting URLs."""

    @staticmethod
    def compile_regex():
        """Compile and return a regular expression for detecting URLs."""
        return re.compile(URL_REGEX)

    @staticmethod
    def extract_url(text, regex=None):
        """Extract the first URL from the given text using a regex."""
        regex = regex or UrlUtils.compile_regex()
        match = regex.search(text)
        return match.group(0) if match else None

    @staticmethod
    def clean_url(url):
        """Remove unwanted trailing characters from a URL."""
        return (url or "").rstrip(URL_RSTRIP)
