"""
Utility functions for use across Gramplet modules.

Includes:
- Boolean string parsing (`is_true`)
- Retrieval of system locale from GRAMPS_LOCALE
"""

from gramps.gen.const import GRAMPS_LOCALE as glocale


def is_true(value: str) -> bool:
    """
    Checks whether a given string value represents a boolean 'true'.

    Accepts common variants like "1", "true", "yes", "y".
    """
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def get_system_locale() -> str:
    """
    Extracts the system locale string from the GRAMPS_LOCALE object.
    """
    return (
        glocale.language[0] if isinstance(glocale.language, list) else glocale.language
    )
