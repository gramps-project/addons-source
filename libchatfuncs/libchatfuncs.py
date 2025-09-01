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

from gramps.gen.db import Database
import gramps.gen.lib.place as place_displayer
from gramps.gen.simple import SimpleAccess

import re

from cache_manager import CacheManager, cache

SYSTEM_PROMPT = """
You are a genealogical research assistant with access to a comprehensive family history database. You can help users explore family trees, find relationships, and discover historical information about people and families.

## Database Structure and Data Types

### Person Data Dictionary
When you receive person data, it contains the following key fields:
- `primary_name`: Dictionary with person's main name including:
  - `first_name`: Given name
  - `surname_list`: List of surname dictionaries, each with `surname`, `prefix`, etc.
  - `title`, `suffix`, `call`, `nick`, `famnick`, `patronymic`: Additional name components
- `alternate_names`: List of alternative names the person was known by
- `gender`: Person's gender (0=unknown, 1=male, 2=female)
- `birth_ref`: Reference to birth event (handle string)
- `death_ref`: Reference to death event (handle string)
- `parent_family_list`: List of family handles where this person is a child
- `family_handle_list`: List of family handles where this person is a parent
- `event_ref_list`: List of event handles associated with this person
- `gramps_id`: Unique Gramps identifier for the person

### Family Data Dictionary
When you receive family data, it contains:
- `father_handle`: Handle of the father (if any)
- `mother_handle`: Handle of the mother (if any)
- `child_ref_list`: List of child reference objects, each with a `ref` field containing the child's handle
- `event_ref_list`: List of family events (marriages, divorces, etc.)
- `gramps_id`: Unique Gramps identifier for the family

### Event Data Dictionary
When you receive event data, it contains:
- `event_type`: Type of event (birth, death, marriage, baptism, etc.)
- `date`: Event date information
- `place`: Place where event occurred
- `description`: Event description
- `person_ref_list`: List of people associated with this event
- `gramps_id`: Unique Gramps identifier for the event

## Important Concepts

### Handles
- All entities (people, families, events) are identified by unique handle strings
- Handles are used to link related data together
- Person handles typically start with "I", family handles with "F", and event handles with "E"

### Relationships
- Use parent family lists to find a person's parents and siblings
- Use family handle lists to find a person's spouses and children
- Use event references to explore a person's life timeline

### Search Strategies
- Start with name searches to find specific people
- Use the default person as a starting point for exploration
- Follow family relationships to build complete family trees
- Use events to understand life milestones and historical context

## Best Practices
- Handle cases where relationships might be missing or incomplete
- Provide context about the genealogical significance of findings
- Suggest follow-up questions to help users explore further
- Be sensitive to potentially sensitive family information
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
        self.sa = SimpleAccess(self.db)
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
        method_names = [
            method_name for method_name in dir(self)
            if method_name.startswith("get_") or method_name.startswith("find_")
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
        return dict(data)

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
        return dict(data)

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
        return dict(data)

    def get_mother_of_person(
        self, person_handle: str
    ) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Find the mother(s) of a specific person in the genealogy database.

        This tool searches through all parent families of the given person to identify
        their mother(s). Useful for tracing maternal lineage and understanding family structure.

        Args:
            person_handle (str): The unique identifier of the person whose mother(s) to find

        Returns:
            Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
                - None if no mother is found
                - A single dictionary if one mother is found
                - A list of dictionaries if multiple mothers are found (e.g., in complex family situations)

        Example:
            mother_data = get_mother_of_person("I1234567890")
            if mother_data:
                print(f"Mother: {mother_data['primary_name']['first_name']}")
        """
        person_data = self.get_person(person_handle)
        mothers = []
        for family_handle in person_data["parent_family_list"]:
            family_data = self.get_family(family_handle)
            if family_data["mother_handle"]:
                mother_data = self.get_person(family_data["mother_handle"])
                mothers.append(mother_data)
        if len(mothers) == 0:
            return None
        elif len(mothers) == 1:
            return mothers[0]
        else:
            return mothers

    def get_father_of_person(
        self, person_handle: str
    ) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Find the father(s) of a specific person in the genealogy database.

        This tool searches through all parent families of the given person to identify
        their father(s). Useful for tracing paternal lineage and understanding family structure.

        Args:
            person_handle (str): The unique identifier of the person whose father(s) to find

        Returns:
            Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
                - None if no father is found
                - A single dictionary if one father is found
                - A list of dictionaries if multiple fathers are found (e.g., in complex family situations)

        Example:
            father_data = get_father_of_person("I1234567890")
            if father_data:
                print(f"Father: {father_data['primary_name']['first_name']}")
        """
        person_data = self.get_person(person_handle)
        fathers = []
        for family_handle in person_data["parent_family_list"]:
            family_data = self.get_family(family_handle)
            if family_data["father_handle"]:
                father_data = self.get_person(family_data["father_handle"])
                fathers.append(father_data)
        if len(fathers) == 0:
            return None
        elif len(fathers) == 1:
            return fathers[0]
        else:
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
        family_handle_list = person_data["family_handle_list"]

        children_data = []

        if family_handle_list:
            family_handle = family_handle_list[0]
            family_data = self.get_family(family_handle)
            child_handles = [handle.ref for handle in family_data["child_ref_list"]]

            for handle in child_handles:
                children_data.append(handle)

        return children_data

    def get_person_birth_date(self, person_handle: str) -> str:
        """
        Get the birth date of a specific person as a formatted string.

        This tool extracts and formats the birth date information for a person,
        making it easy to display or compare birth dates across the family tree.

        Args:
            person_handle (str): The unique identifier of the person

        Returns:
            str: Formatted birth date string, or empty string if no birth date is recorded

        Example:
            birth_date = get_person_birth_date("I1234567890")
            print(f"Born: {birth_date}")
        """
        person = self.db.get_person_from_handle(person_handle)
        return self.sa.birth_date(person)

    def get_person_death_date(self, person_handle: str) -> str:
        """
        Get the death date of a specific person as a formatted string.

        This tool extracts and formats the death date information for a person,
        useful for calculating lifespan or understanding family history.

        Args:
            person_handle (str): The unique identifier of the person

        Returns:
            str: Formatted death date string, or empty string if no death date is recorded

        Example:
            death_date = get_person_death_date("I1234567890")
            print(f"Died: {death_date}")
        """
        person = self.db.get_person_from_handle(person_handle)
        return self.sa.death_date(person)

    def get_person_birth_place(self, person_handle: str) -> str:
        """
        Get the birth place of a specific person as a formatted string.

        This tool extracts and formats the birth place information for a person,
        useful for understanding geographical origins and migration patterns.

        Args:
            person_handle (str): The unique identifier of the person

        Returns:
            str: Formatted birth place string, or empty string if no birth place is recorded

        Example:
            birth_place = get_person_birth_place("I1234567890")
            print(f"Born in: {birth_place}")
        """
        person = self.db.get_person_from_handle(person_handle)
        return self.sa.birth_place(person)

    def get_person_death_place(self, person_handle: str) -> str:
        """
        Get the death place of a specific person as a formatted string.

        This tool extracts and formats the death place information for a person,
        useful for understanding where people lived and died throughout their lives.

        Args:
            person_handle (str): The unique identifier of the person

        Returns:
            str: Formatted death place string, or empty string if no death place is recorded

        Example:
            death_place = get_person_death_place("I1234567890")
            print(f"Died in: {death_place}")
        """
        person = self.db.get_person_from_handle(person_handle)
        return self.sa.death_place(person)

    def get_person_event_list(self, person_handle: str) -> List[str]:
        """
        Get a list of all event handles associated with a specific person.

        This tool retrieves all events linked to a person, such as births, deaths,
        marriages, baptisms, graduations, etc. Use this to explore a person's life timeline.

        Args:
            person_handle (str): The unique identifier of the person

        Returns:
            List[str]: List of event handles that can be used with get_event() to get detailed event information

        Example:
            event_handles = get_person_event_list("I1234567890")
            for event_handle in event_handles:
                event_data = get_event(event_handle)
                print(f"Event: {event_data['event_type']}")
        """
        person_data = self.get_person(person_handle)
        return [ref.ref for ref in person_data["event_ref_list"]]

    def get_event_place(self, event_handle: str) -> str:
        """
        Get the place where a specific event occurred as a formatted string.

        This tool extracts and formats the location information for an event,
        useful for understanding where important life events took place.

        Args:
            event_handle (str): The unique identifier of the event

        Returns:
            str: Formatted place string where the event occurred, or empty string if no place is recorded

        Example:
            event_place = get_event_place("E1234567890")
            print(f"Event location: {event_place}")
        """
        event = self.db.get_event_from_handle(event_handle)
        return place_displayer.display_event(self.db, event)

    def get_child_in_families(self, person_handle: str) -> List[Dict[str, Any]]:
        """
        Get detailed information about all families where a person is listed as a child.

        This tool is essential for genealogical research as it reveals the person's siblings
        and parents by examining all family structures they belong to as a child.
        Useful for understanding complex family situations like multiple marriages or adoptions.

        Args:
            person_handle (str): The unique identifier of the person

        Returns:
            List[Dict[str, Any]]: List of complete family data dictionaries

        Example:
            families = get_child_in_families("I1234567890")
            for family in families:
                print(f"Family with {len(family['child_ref_list'])} children")
        """
        person_obj = self.db.get_person_from_handle(person_handle)
        families = self.sa.child_in(person_obj)
        family_data_list = []

        for family in families:
            family_data = self.get_family(family.handle)
            family_data_list.append(family_data)

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
        
        # Validate page number
        if page < 1:
            page = 1
        
        # Get the current page of results
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        current_page_handles = people_handles[start_index:end_index]
        
        # Check if we might have more results (if we found exactly what we needed)
        has_more = len(people_handles) == results_needed
        
        return {
            "handles": current_page_handles,
            "page": page,
            "page_size": page_size,
            "has_more": has_more
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
    if search_pattern.search(str(dict(name_data))):
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
            if search_pattern.search(name_data[part]):
                return True
    return False
