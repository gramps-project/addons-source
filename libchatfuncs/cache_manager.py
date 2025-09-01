#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Doug Blank <doug.blank@gmail.com>
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

from typing import Dict, Union, List, Any, Pattern, Optional, Tuple, Callable

from collections import OrderedDict
import functools
import hashlib
import json


class CacheManager:
    """
    A cache manager that stores function results and provides utilities
    to clear caches.
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize the cache manager.

        Args:
            max_size: Maximum number of cached items per function
        """
        self._caches: Dict[str, OrderedDict] = {}
        self._max_size = max_size

    def get_cache(self, func_name: str) -> OrderedDict:
        """
        Get or create a cache for a function.

        Args:
            func_name: Name of the function to get cache for

        Returns:
            The cache dictionary for the function
        """
        if func_name not in self._caches:
            self._caches[func_name] = OrderedDict()
        return self._caches[func_name]

    def clear_cache(self, func_name: Optional[str] = None):
        """
        Clear cache for a specific function or all functions.

        Args:
            func_name: Name of the function to clear cache for. If None, clears all caches.
        """
        if func_name is None:
            self._caches.clear()
        elif func_name in self._caches:
            self._caches[func_name].clear()

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about cache usage.

        Returns:
            Dictionary mapping function names to their cache sizes
        """
        return {func_name: len(cache) for func_name, cache in self._caches.items()}

    def set_max_size(self, max_size: int):
        """
        Set the maximum cache size for new functions.

        Args:
            max_size: Maximum number of cached items per function
        """
        self._max_size = max_size


def _make_hashable(obj: Any) -> Any:
    """
    Convert an object to a hashable form for caching.

    Args:
        obj: Object to make hashable

    Returns:
        Hashable representation of the object
    """
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, (list, tuple)):
        return tuple(_make_hashable(item) for item in obj)
    elif isinstance(obj, dict):
        return tuple(sorted((k, _make_hashable(v)) for k, v in obj.items()))
    else:
        # For other objects, try to convert to string representation
        return str(obj)


def _create_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """
    Create a cache key from function name and arguments.

    Args:
        func_name: Name of the function
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        A string cache key
    """
    # Make arguments hashable
    hashable_args = _make_hashable(args)
    hashable_kwargs = _make_hashable(kwargs)

    # Create a string representation
    key_data = (func_name, hashable_args, hashable_kwargs)
    key_string = json.dumps(key_data, sort_keys=True, default=str)

    # Create a hash for shorter keys
    return hashlib.md5(key_string.encode()).hexdigest()


def cache(max_size: Optional[int] = None):
    """
    Decorator that caches method results.

    Args:
        max_size: Maximum number of cached items for this method.
                 If None, uses the instance's cache manager default.

    Returns:
        Decorated method with caching
    """

    def decorator(method: Callable) -> Callable:
        method_name = method.__name__

        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            # Get cache from the instance's cache manager
            cache = self.cache_manager.get_cache(method_name)
            local_max_size = (
                max_size if max_size is not None else self.cache_manager._max_size
            )

            # Create cache key
            cache_key = _create_cache_key(method_name, args, kwargs)

            # Check if result is cached
            if cache_key in cache:
                # Move to end (most recently used)
                result = cache.pop(cache_key)
                cache[cache_key] = result
                return result

            # Compute result and cache it
            result = method(self, *args, **kwargs)
            cache[cache_key] = result

            # Enforce max size
            if len(cache) > local_max_size:
                cache.popitem(last=False)  # Remove least recently used

            return result

        return wrapper

    return decorator
