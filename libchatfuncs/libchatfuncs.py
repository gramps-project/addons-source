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

from typing import Dict, Union, List, Any, Pattern, Optional, Tuple
import re

from gramps.gen.db import Database
from gramps.gen.lib import Date, Place, Person, Event, Family
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.datehandler import displayer
from gramps.gen.lib.json_utils import data_to_object

from cache_manager import CacheManager, cache


def _format_date_from_raw(date_dict):
    """
    Fast helper function to format a date from raw event data.

    Args:
        date_dict: Raw date data dict from get_raw_event_data

    Returns:
        str: Formatted date string
    """
    date_obj = data_to_object(date_dict)
    if date_obj.is_valid():
        return displayer.display(date_obj)
    elif date_obj.text:
        return date_obj.text
    else:
        return ""


SYSTEM_PROMPT = """
You are a genealogical research assistant with access to a comprehensive family history database. You can help users explore family trees, find relationships, and discover historical information about people and families.

## Available Functions

### Core Data Retrieval
- `get_person(person_handle)`: Get complete person data including names, relationships, events
- `get_family(family_handle)`: Get family data including parents, children, marriage events
- `get_event(event_handle)`: Get event details including type, date, place, participants
- `get_place(place_handle)`: Get place information and location details

### Search and Discovery
- `find_people_by_name(search_string, page=1)`: Search for people by name with pagination
- `get_initial_person()`: Get the starting/default person for exploration

### Relationship Navigation
- `get_mother_of_person(person_handle)`: Returns list of mother data (empty if none)
- `get_father_of_person(person_handle)`: Returns list of father data (empty if none)
- `get_children_of_person(person_handle)`: Returns list of (child_handle, child_data) tuples
- `get_child_in_families(person_handle)`: Get all families where person is a child

### Life Events and Timeline
- `get_person_birth_date(person_handle)`: Get formatted birth date string
- `get_person_death_date(person_handle)`: Get formatted death date string
- `get_person_birth_place(person_handle)`: Get formatted birth place string
- `get_person_death_place(person_handle)`: Get formatted death place string
- `get_person_event_list(person_handle)`: Get list of all event handles for a person
- `get_event_place(event_handle)`: Get formatted place where event occurred

## Data Structure Guide

### Person Data Dictionary
Key fields in person data:
- `primary_name`: Main name with `first_name`, `surname_list`, `title`, `suffix`, etc.
- `alternate_names`: List of alternative names
- `gender`: 0=unknown, 1=male, 2=female
- `parent_family_list`: Family handles where this person is a child
- `family_handle_list`: Family handles where this person is a parent
- `event_ref_list`: Event handles associated with this person
- `gramps_id`: Unique identifier

### Family Data Dictionary
Key fields in family data:
- `father_handle`: Father's handle (if any)
- `mother_handle`: Mother's handle (if any)
- `child_ref_list`: List of child references with `ref` field containing child handle
- `event_ref_list`: Family events (marriages, divorces, etc.)
- `gramps_id`: Unique identifier

### Event Data Dictionary
Key fields in event data:
- `event_type`: Type of event (birth, death, marriage, baptism, etc.)
- `date`: Event date information
- `place`: Place handle where event occurred
- `description`: Event description
- `person_ref_list`: People associated with this event
- `gramps_id`: Unique identifier

## Usage Patterns

### Starting Exploration
1. Use `get_initial_person()` to find the default starting person
2. Or use `find_people_by_name("name")` to search for specific people
3. Get person data with `get_person(person_handle)`

### Building Family Trees
1. Get parents: `get_mother_of_person()` and `get_father_of_person()`
2. Get children: `get_children_of_person()` (returns tuples of handle and data)
3. Get siblings: Use `get_child_in_families()` to find families where person is a child
4. Follow family relationships using family handles

### Exploring Life Events
1. Get event list: `get_person_event_list(person_handle)`
2. Get specific events: `get_event(event_handle)`
3. Get formatted dates/places: `get_person_birth_date()`, `get_person_death_place()`, etc.

### Search Strategies
- Use `find_people_by_name()` with partial names (first name, surname, or full name)
- Pagination: Use `page` parameter for large result sets
- Handle empty results gracefully - not all searches will find matches

## Important Notes

### Return Types
- Parent functions (`get_mother_of_person`, `get_father_of_person`) return lists (empty if none found)
- `get_children_of_person` returns list of tuples: `[(handle, data), ...]`
- Date/place functions return formatted strings (empty string if not available)
- Search functions return paginated results with metadata

### Error Handling
- All functions handle invalid handles gracefully
- Missing data returns empty containers (lists) or empty strings
- Always check if results are empty before processing

### Best Practices
- Start with broad searches, then narrow down
- Use the initial person as a starting point for exploration
- Provide context about genealogical significance of findings
- Suggest follow-up questions to help users explore further
- Be sensitive to potentially sensitive family information
- Handle cases where relationships might be missing or incomplete
"""


class ChatFunctions:
    """
    A class that encapsulates the Gramps database and provides cached versions
    of libchatfuncs functions as methods.
    """

    def __init__(self, db: Database, cache_max_size: int = 10000):
        """
        Initialize the cached libchatfuncs with a database and cache manager.

        Args:
            db: Gramps database instance
            cache_max_size: Maximum cache size per method
        """
        self.db = db
        self.cache_manager = CacheManager(cache_max_size)

    # Cache management methods
    def clear_all_caches(self):
        """Clear all method caches."""
        self.cache_manager.clear_cache()

    def clear_method_cache(self, method_name: str):
        """Clear cache for a specific method."""
        self.cache_manager.clear_cache(method_name)

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics for all methods."""
        return self.cache_manager.get_cache_stats()

    def set_cache_max_size(self, max_size: int):
        """Set the maximum cache size for new methods."""
        self.cache_manager.set_max_size(max_size)

    @property
    def tools(self):
        """
        Get the methods from this class that are tools
        for an LLM
        """
        # Exclude cache management methods from LLM tools
        excluded_methods = {
            "get_cache_stats",
            "clear_all_caches",
            "clear_method_cache",
            "set_cache_max_size",
        }

        method_names = [
            method_name
            for method_name in dir(self)
            if (method_name.startswith("get_") or method_name.startswith("find_"))
            and method_name not in excluded_methods
        ]
        return {method_name: getattr(self, method_name) for method_name in method_names}

    @cache()
    def get_person(self, person_handle: str) -> Dict[str, Any]:
        """
        Retrieve complete information about a person from the Gramps database.

        This tool fetches all available data for a specific person including their names,
        birth/death information, family relationships, events, and other attributes.

        Args:
            person_handle (str): The unique identifier (handle) of the person in the database

        Returns:
            Dict[str, Any]: Complete person data dictionary

        Example:
            person_data = get_person("I1234567890")
            print(person_data["primary_name"]["first_name"])
        """
        data = self.db.get_raw_person_data(person_handle)
        if data is None:
            return {}
        return dict(data)

    def _get_person_object(self, person_handle: str) -> Person:
        """
        Get a person object from handle.
        """
        data = self.get_person(person_handle)
        return data_to_object(data)

    @cache()
    def get_place(self, place_handle: str) -> Dict[str, Any]:
        """
        Retrieve complete information about a place from the Gramps database.

        This tool fetches all available data for a specific place including its name,
        location information, and other attributes.

        Args:
            place_handle (str): The unique identifier (handle) of the place in the database

        Returns:
            Dict[str, Any]: Complete place data dictionary

        Example:
            place_data = get_place("P1234567890")
            print(place_data["title"])
        """
        data = self.db.get_raw_place_data(place_handle)
        if data is None:
            return {}
        return dict(data)

    def _get_place_object(self, place_handle: str) -> Place:
        """
        Get a Place object.
        """
        data = self.get_place(place_handle)
        return data_to_object(data)

    @cache()
    def get_family(self, family_handle: str) -> Dict[str, Any]:
        """
        Retrieve complete information about a family from the Gramps database.

        This tool fetches all available data for a specific family including the parents,
        children, marriage information, and other family attributes.

        Args:
            family_handle (str): The unique identifier (handle) of the family in the database

        Returns:
            Dict[str, Any]: Complete family data dictionary

        Example:
            family_data = get_family("F1234567890")
            print(family_data["father_handle"])
        """
        data = self.db.get_raw_family_data(family_handle)
        if data is None:
            return {}
        return dict(data)

    def _get_family_object(self, family_handle: str) -> Family:
        """
        Get a Family object.
        """
        data = self.get_family(family_handle)
        return data_to_object(data)

    @cache()
    def get_event(self, event_handle: str) -> Dict[str, Any]:
        """
        Retrieve complete information about an event from the Gramps database.

        This tool fetches all available data for a specific event including the event type,
        date, place, description, and participants.

        Args:
            event_handle (str): The unique identifier (handle) of the event in the database

        Returns:
            Dict[str, Any]: Complete event data dictionary

        Example:
            event_data = get_event("E1234567890")
            print(event_data["event_type"])
        """
        data = self.db.get_raw_event_data(event_handle)
        if data is None:
            return {}
        return dict(data)

    def _get_event_object(self, event_handle: str) -> Event:
        """
        Get an Event object.
        """
        data = self.get_event(event_handle)
        if not data:
            return None
        return data_to_object(data)

    def get_mother_of_person(self, person_handle: str) -> List[Dict[str, Any]]:
        """
        Find the mother(s) of a specific person in the genealogy database.

        This tool searches through all parent families of the given person to identify
        their mother(s). Useful for tracing maternal lineage and understanding family structure.

        Args:
            person_handle (str): The unique identifier of the person whose mother(s) to find

        Returns:
            List[Dict[str, Any]]: List of mother data dictionaries. Empty list if no mothers found.

        Example:
            mothers = get_mother_of_person("I1234567890")
            for mother in mothers:
                print(f"Mother: {mother['primary_name']['first_name']}")
        """
        person_data = self.get_person(person_handle)
        if not person_data or "parent_family_list" not in person_data:
            return []

        mothers = []
        for family_handle in person_data["parent_family_list"]:
            family_data = self.get_family(family_handle)
            if family_data and family_data.get("mother_handle"):
                mother_data = self.get_person(family_data["mother_handle"])
                if mother_data:
                    mothers.append(mother_data)
        return mothers

    def get_father_of_person(self, person_handle: str) -> List[Dict[str, Any]]:
        """
        Find the father(s) of a specific person in the genealogy database.

        This tool searches through all parent families of the given person to identify
        their father(s). Useful for tracing paternal lineage and understanding family structure.

        Args:
            person_handle (str): The unique identifier of the person whose father(s) to find

        Returns:
            List[Dict[str, Any]]: List of father data dictionaries. Empty list if no fathers found.

        Example:
            fathers = get_father_of_person("I1234567890")
            for father in fathers:
                print(f"Father: {father['primary_name']['first_name']}")
        """
        person_data = self.get_person(person_handle)
        if not person_data or "parent_family_list" not in person_data:
            return []

        fathers = []
        for family_handle in person_data["parent_family_list"]:
            family_data = self.get_family(family_handle)
            if family_data and family_data.get("father_handle"):
                father_data = self.get_person(family_data["father_handle"])
                if father_data:
                    fathers.append(father_data)
        return fathers

    def get_initial_person(self) -> Optional[str]:
        """
        Get the initial/starting person's handle in the genealogy database.

        This tool retrieves the person's handle designated as the starting point for the family tree.
        This is typically the main person of interest or the root of the genealogical research.
        Useful for beginning genealogical exploration or when no specific person is identified.

        Args:
            None - This tool takes no parameters

        Returns:
            str: the initial person's handle

        Example:
            person_handle = get_start_point()
            if person_handle:
                person_data = get_person(person_handle)
        """
        return self.db.get_default_handle()

    def get_children_of_person(
        self, person_handle: str
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Get all children of a specific person from their primary family.

        This tool retrieves information about all children of the given person from their
        first family relationship. Useful for understanding family size and identifying siblings.

        Args:
            person_handle (str): The unique identifier of the person whose children to find

        Returns:
            List[Tuple[str, Dict[str, Any]]]: A list of tuples, where each tuple contains:
                - The child's handle (str)
                - The child's complete person data (dict)

        Example:
            children = get_children_of_person("I1234567890")
            for child_handle, child_data in children:
                print(f"Child: {child_data['primary_name']['first_name']}")
        """
        person_data = self.get_person(person_handle)
        if not person_data or "family_handle_list" not in person_data:
            return []

        family_handle_list = person_data["family_handle_list"]
        children_data = []

        if family_handle_list:
            family_handle = family_handle_list[0]
            family_data = self.get_family(family_handle)
            if family_data and "child_ref_list" in family_data:
                child_handles = [
                    handle["ref"] for handle in family_data["child_ref_list"]
                ]

                for handle in child_handles:
                    child_data = self.get_person(handle)
                    children_data.append((handle, child_data))

        return children_data

    def get_person_birth_date(self, person_handle: str) -> str:
        """
        Get the birth date of a specific person as a formatted string.

        Args:
            person_handle (str): The unique identifier of the person

        Returns:
            str: Formatted birth date string, or empty string if no birth date is recorded
        """
        person_data = self.get_person(person_handle)
        if person_data and "birth_ref_index" in person_data:
            birth_ref_index = person_data["birth_ref_index"]
            if birth_ref_index is not None and "event_ref_list" in person_data:
                event_ref_list = person_data["event_ref_list"]
                if birth_ref_index >= 0 and birth_ref_index < len(event_ref_list):
                    event_handle = event_ref_list[birth_ref_index]["ref"]
                    if event_handle:
                        event_data = self.get_event(event_handle)
                        if event_data and event_data.get("date"):
                            return _format_date_from_raw(event_data["date"])
        return ""

    def get_person_death_date(self, person_handle: str) -> str:
        """
        Get the death date of a specific person as a formatted string.

        Args:
            person_handle (str): The unique identifier of the person

        Returns:
            str: Formatted death date string, or empty string if no death date is recorded
        """
        person_data = self.get_person(person_handle)
        if person_data and "death_ref_index" in person_data:
            death_ref_index = person_data["death_ref_index"]
            if death_ref_index is not None and "event_ref_list" in person_data:
                event_ref_list = person_data["event_ref_list"]
                if death_ref_index >= 0 and death_ref_index < len(event_ref_list):
                    event_handle = event_ref_list[death_ref_index]["ref"]
                    if event_handle:
                        event_data = self.get_event(event_handle)
                        if event_data and event_data.get("date"):
                            return _format_date_from_raw(event_data["date"])
        return ""

    def get_person_birth_place(self, person_handle: str) -> str:
        """
        Get the birth place of a specific person as a formatted string.

        Args:
            person_handle (str): The unique identifier of the person

        Returns:
            str: Formatted birth place string, or empty string if no birth place is recorded
        """
        person_data = self.get_person(person_handle)
        if person_data:
            birth_ref_index = person_data["birth_ref_index"]
            if birth_ref_index is not None:
                event_handle = person_data["event_ref_list"][birth_ref_index]["ref"]
                if event_handle:
                    event_data = self.get_event(event_handle)
                    if event_data:
                        # Get the place object from the database to use with place_displayer
                        place_handle = event_data["place"]
                        if place_handle:
                            place_obj = self._get_place_object(place_handle)
                            if place_obj:
                                return place_displayer.display(self.db, place_obj)
        return ""

    def get_person_death_place(self, person_handle: str) -> str:
        """
        Get the death place of a specific person as a formatted string.

        Args:
            person_handle (str): The unique identifier of the person

        Returns:
            str: Formatted death place string, or empty string if no death place is recorded
        """
        person_data = self.get_person(person_handle)
        if person_data:
            death_ref_index = person_data["death_ref_index"]
            if death_ref_index is not None:
                event_handle = person_data["event_ref_list"][death_ref_index]["ref"]
                if event_handle:
                    event_data = self.get_event(event_handle)
                    if event_data and event_data.get("place"):
                        # Get the place object from the database to use with place_displayer
                        place_handle = event_data["place"]
                        if place_handle:
                            place_obj = self._get_place_object(place_handle)
                            if place_obj:
                                return place_displayer.display(self.db, place_obj)
        return ""

    def get_person_event_list(self, person_handle: str) -> List[str]:
        """
        Get a list of all event handles associated with a specific person.

        Args:
            person_handle (str): The unique identifier of the person

        Returns:
            List[str]: List of event handles that can be used with get_event() to get detailed event information
        """
        person_data = self.get_person(person_handle)
        if not person_data or "event_ref_list" not in person_data:
            return []
        return [ref["ref"] for ref in person_data["event_ref_list"]]

    def get_event_place(self, event_handle: str) -> str:
        """
        Get the place where a specific event occurred as a formatted string.

        Args:
            event_handle (str): The unique identifier of the event

        Returns:
            str: Formatted place string where the event occurred, or empty string if no place is recorded
        """
        event_obj = self._get_event_object(event_handle)
        if event_obj:
            return place_displayer.display_event(self.db, event_obj)
        return ""

    def get_child_in_families(self, person_handle: str) -> List[Dict[str, Any]]:
        """
        Get information about all families where a person is listed as a child.

        This tool reveals the person's siblings and parents by examining all family
        structures they belong to as a child.

        Args:
            person_handle (str): The unique identifier of the person

        Returns:
            List[Dict[str, Any]]: List of family dictionaries, each containing:
                - family_handle: The family's handle
                - mother: Mother's handle (if any)
                - father: Father's handle (if any)
                - children: List of child handles in this family
        """
        person_data = self.get_person(person_handle)
        family_data_list = []

        if person_data and "parent_family_list" in person_data:
            for family_handle in person_data["parent_family_list"]:
                family_data = self.get_family(family_handle)
                if family_data:
                    data = {
                        "family_handle": family_handle,
                        "mother": family_data.get("mother_handle"),
                        "father": family_data.get("father_handle"),
                    }
                    if "child_ref_list" in family_data:
                        data["children"] = [
                            child["ref"] for child in family_data["child_ref_list"]
                        ]
                    else:
                        data["children"] = []
                    family_data_list.append(data)

        return family_data_list

    def find_people_by_name(self, search_string: str, page: int = 1) -> Dict[str, Any]:
        """
        Search for people in the genealogy database by name with pagination support.

        This tool performs a comprehensive name search across the database, looking for
        matches in primary names, alternate names, first names, surnames, nicknames,
        and other name variations. The search is case-insensitive and uses word boundaries.
        Results are paginated to avoid overwhelming the LLM with too many matches.
        The search is optimized to stop once enough results are found for the requested page.

        Args:
            search_string (str): The name to search for. Can be a full name
                like "John Smith" or just part of a name like "John" or "Smith"
            page (int): The page number to return (1-based). Default is 1.

        Returns:
            Dict[str, Any]: A dictionary containing:
                - "handles": List of person handles for the current page
                - "page": Current page number
                - "page_size": Number of results per page
                - "has_more": Boolean indicating if there might be more results

        Example:
            # Find people with "John" in their name (first page)
            result = find_people_by_name("John", page=1)
            print(f"Found {len(result['handles'])} matches on this page")
            for person_handle in result['handles']:
                get_person(person_handle)

            # Get the second page
            result = find_people_by_name("John", page=2)
            for person_handle in result['handles']:
                get_person(person_handle)
        """
        page_size = 25
        people_handles = []
        search_pattern = create_search_pattern(search_string)

        if search_pattern:
            # Calculate how many results we need to find
            results_needed = page * page_size

            for handle in self.db.iter_person_handles():
                person_data = self.get_person(handle)
                # Don't even consider if search_string isn't anywhere in data:
                if search_pattern.search(str(dict(person_data))):
                    for name_data in [person_data["primary_name"]] + person_data[
                        "alternate_names"
                    ]:
                        if match_name_data(search_pattern, name_data):
                            people_handles.append(handle)
                            break

                # Stop searching if we have enough results for the requested page
                if len(people_handles) >= results_needed:
                    break
        else:
            # No search pattern, so no results needed
            results_needed = 0

        # Validate page number
        if page < 1:
            page = 1

        # Get the current page of results
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        current_page_handles = people_handles[start_index:end_index]

        # Check if we might have more results (if we found exactly what we needed)
        has_more = (
            len(people_handles) == results_needed if results_needed > 0 else False
        )

        return {
            "handles": current_page_handles,
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
        }


def create_search_pattern(search_string: str) -> Optional[Pattern]:
    """
    Creates a case-insensitive regex pattern to match any of the words
    in a given search string, using word boundaries.

    Args:
        search_string: The string containing words to search for.

    Returns:
        A compiled regex Pattern object.
    """
    search_string = search_string.strip()

    if search_string == "":
        return None

    search_terms = search_string.split()
    escaped_terms = [re.escape(term) for term in search_terms]
    regex_or_pattern = "|".join(escaped_terms)
    pattern = re.compile(r"\b(?:" + regex_or_pattern + r")\b", re.IGNORECASE)
    return pattern


def match_name_data(search_pattern: Pattern, name_data: Dict[str, Any]) -> bool:
    """
    Given a search string, return True if name_data contains it.
    """
    # First, see if it search_pattern matches whole name:
    if search_pattern.search(str(dict(name_data))):
        # If it matches, then make sure it is a name match:
        for surname in name_data["surname_list"]:
            for surname_part in ["prefix", "surname"]:
                if search_pattern.search(surname[surname_part]):
                    return True
        for part in [
            "first_name",
            "suffix",
            "title",
            "call",
            "nick",
            "famnick",
            "patronymic",
        ]:
            if part in name_data and search_pattern.search(name_data[part]):
                return True
    return False
