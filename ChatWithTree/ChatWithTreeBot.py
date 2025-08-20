#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Melle Koning
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
import logging
LOG = logging.getLogger(".")

try:
    from typing import Dict, Any, List, Optional, Tuple, Pattern, Iterator
    import os
    import json
    import sys
    import time
    import re
    import inspect
    import litellm
except ImportError as e:
    LOG.warning(e)
    raise Exception("ChatWithTree requires litellm")

litellm.drop_params = True

from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.simple import SimpleAccess
from gramps.gen.db.utils import open_database
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.config import CONFIGMAN

# gramps translation support for this module
_ = glocale.translation.gettext

# interface that we use in the gramplet
from chatwithllm import IChatLogic, YieldType

HELP_TEXT = """
ChatWithTree uses the following OS environment variables:

```
export GRAMPS_AI_MODEL_NAME="<ENTER MODEL NAME HERE>"
```

This is always needed. Examples: "ollama/deepseek-r1:1.5b", "openai/gpt-4o-mini", "gemini/gemini-2.5-flash"

```
export GRAMPS_AI_MODEL_URL="<ENTER URL HERE>"
```

This is needed if running your own LLM server. Example: "http://127.0.0.1:8000"

You can find a list of litellm providers here:
https://docs.litellm.ai/docs/providers

You can find a list of ollama models here:
https://ollama.com/library/

### Optional

If you are running a commercial AI model provider, you will need their API key.

#### Example

For OpenAI:

```
export OPENAI_API_KEY="sk-..."
```

For Moonshot:
export MOONSHOT_API_KEY="sk-..."
For Deepseek:
export DEEPSEEK_API_KEY="sk-..."
For Gemini:
export GEMINI_API_KEY="gemini-key..."
export GRAMPS_AI_MODEL_NAME="gemini/gemini-2.5-flash"

for Anthropic:
export ANTHROPIC_API_KEY="sk-..."

Commands:
/help - show this help text
/history - show the full chat history in JSON format
/setmodel <model_name> - set the model name to use for the LLM

The <model_name> depends on the LLM provider you are using.
Usually the model name can be found on the provider's website.

Examples:
/setmodel ollama/deepseek-r1:1.5b
/setmodel openrouter/moonshotai/kimi-k2:free
"""

SYSTEM_PROMPT = """
You are a helpful and highly analytical genealogist, an expert in the Gramps open source genealogy program.
Your primary goal is to assist the user by providing accurate and relevant genealogical information.

**Crucial Guidelines for Tool Usage and Output:**

1.  **Prioritize User Response:** Always aim to provide a direct answer to the user's query as soon as you have sufficient information.
2.  **Tool Purpose:** Use tools to gather specific information that directly helps answer the user's request.
3.  **About data details from tools:**
    * Use database keys, grampsID keys, or a person's 'handle' for internal reference to person data but present data based on retrieved names of persons.
    * Do present names of people to communicate human readable data received from tools
4.  **Progress Monitoring & Self-Correction:**
    * **Assess Tool Results:** After each tool call, carefully evaluate its output. Did it provide the expected information?
      Is it sufficient to progress towards the user's goal?
    * **Tool use** Use as many tool calls in one go as you want, but do not call the same tool with the same arguments more than once.
5.  **Graceful Exit with Partial Results:**
    * **Summarize Findings:** Synthesize all the information you have gathered so far. Clearly state what you found and what information you were unable to obtain.

You can get the start point of the genealogy tree using the `start_point` tool.
"""

GRAMPS_AI_MODEL_NAME = os.environ.get("GRAMPS_AI_MODEL_NAME")
GRAMPS_AI_MODEL_URL = os.environ.get("GRAMPS_AI_MODEL_URL")

from litellm_utils import function_to_litellm_definition

# ===
# ChatBot class gets initialized when a Gramps database
# is selected (on db change)
# ===
class ChatBot(IChatLogic):
    def __init__(self, gramplet_instance):
        self.gramplet_instance = gramplet_instance
        self.dbstate = gramplet_instance.dbstate
        self.db = self.dbstate.db
        self.sa = SimpleAccess(self.db)
        
        self.messages = []
        self.messages.append({"role": "system", "content": SYSTEM_PROMPT})
        LOG.debug("Chatbot init and SimpleAccess created successfully")
        self.tool_map = {
            "start_point": self.start_point,
            "get_person": self.get_person,
            "get_family": self.get_family,
            "get_children_of_person": self.get_children_of_person,
            "get_mother_of_person": self.get_mother_of_person,
            "get_father_of_person": self.get_father_of_person,
            "get_person_birth_date": self.get_person_birth_date,
            "get_person_death_date": self.get_person_death_date,
            "get_person_birth_place": self.get_person_birth_place,
            "get_person_death_place": self.get_person_death_place,
            "get_person_event_list": self.get_person_event_list,
            "get_event": self.get_event,
            "get_event_place": self.get_event_place,
            "get_child_in_families": self.get_child_in_families,
            "find_people_by_name": self.find_people_by_name,
        }
        self.tool_definitions = [
            function_to_litellm_definition(func) for func in self.tool_map.values()
        ]

        # This dictionary maps command names to their handler methods
        self.command_handlers = {
            "/help": self.command_handle_help,
            "/history": self.command_handle_history,
            "/setmodel": self.command_handle_setmodel,
        }

    def command_handle_help(self, message: str) -> Iterator[Tuple[YieldType, str]]:
        '''
        returns the helptext to the user including
        the current model name and model url
        '''
        yield (YieldType.FINAL, f"{HELP_TEXT}"
            f"\nGRAMPS_AI_MODEL_NAME: {GRAMPS_AI_MODEL_NAME}"
            f"\nGRAMPS_AI_MODEL_URL: {GRAMPS_AI_MODEL_URL}")
        
    def command_handle_history(self, message: str) -> Iterator[Tuple[YieldType, str]]:
        ''' 
        returns the full chat history to the user
        '''
        yield (YieldType.FINAL, json.dumps(self.messages, indent=4, sort_keys=True))
        
    def command_handle_setmodel(self, message: str) -> Iterator[Tuple[YieldType, str]]:
        '''
        sets the model name to use for the LLM
        usage: /setmodel <model_name>
        Example: /setmodel ollama/deepseek-r1:1.5b
        '''
        global GRAMPS_AI_MODEL_NAME
        parts = message.split(' ', 1)
        if len(parts) != 2 or not parts[1].strip():
            yield (YieldType.FINAL, "Usage: /setmodel <model_name>")
            return
        new_model_name = parts[1].strip()
        GRAMPS_AI_MODEL_NAME = new_model_name
        yield (YieldType.FINAL, f"Model name set to: {GRAMPS_AI_MODEL_NAME}")

    # The implementation of the IChatLogic interface
    def get_reply(self, message: str) -> Iterator[Tuple[YieldType, str]]:
        """
        Processes the message and returns a reply.
        """
        # Strip leading/trailing whitespace
        message = message.strip()

        if message.startswith('/'):
            # Split the message into command and arguments (if any)
            command_key = message.split(' ', 1)[0]
            
            # Look up the command in the dictionary
            commandhandler = self.command_handlers.get(command_key)
            
            if commandhandler:
                # Call the handler and yield from its generator
                yield from commandhandler(message)
            else:
                # Handle unknown command
                yield (YieldType.FINAL, f"Unknown command: {command_key}")
            return # prevent command to be sent to LLM
        if GRAMPS_AI_MODEL_NAME:
            # yield from returns all yields from the calling func
            yield from self.get_chatbot_response(message)
        else:
            yield (YieldType.FINAL, "Error: ensure to set GRAMPS_AI_MODEL_NAME and GRAMPS_AI_MODEL_URL environment variables.")
      
    

   # @_throttle.rate_limited(_limiter)
    def _llm_complete(
        self,
        all_messages: List[Dict[str, str]],
        tool_definitions: Optional[List[Dict[str, str]]],
        seed: int,
    ) -> Any:
        response = litellm.completion(
            model=GRAMPS_AI_MODEL_NAME,  # self.model,
            messages=all_messages,
            seed=seed,
            tools=tool_definitions,
            tool_choice="auto" if tool_definitions is not None else None,
        )

        # logger.debug("\033[92mResponse from AI Model:\033[0m")
        # Convert response to a dictionary if possible
        response_dict = response.to_dict() if hasattr(response, 'to_dict') else str(response)
        # logger.debug(json.dumps(response_dict, indent=2))
        return response

    def get_chatbot_response(
        self,
        user_input: str,
        seed: int = 42,
    ) -> Iterator[Tuple[YieldType, str]]:
        self.messages.append({"role": "user", "content": user_input})
        yield from self._llm_loop(seed)

    def execute_tool(self, tool_call):
        # logger.debug(f"Executing tool call: {tool_call['function']['name']}")
        tool_name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"])
        sys.stdout.flush()
        tool_func = self.tool_map.get(tool_name)
        try:
            if tool_func is not None:
                sig = inspect.signature(tool_func)
                if len(sig.parameters) == 0:
                    # Ignore any arguments, call with none
                    tool_result = tool_func()
                else:
                    tool_result = tool_func(**arguments)

            else:
                tool_result = f"Unknown tool: {tool_name}"

            content_for_llm = ""
            if isinstance(tool_result, (dict, list)):
                content_for_llm = json.dumps(tool_result)
            else:
                content_for_llm = str(tool_result)

            #logger.debug("\033[93mTool call result:\033[0m")
            #logger.debug(content_for_llm)

        except Exception as exc:
            #logger.debug(exc)
            content_for_llm = f"Error in calling tool `{tool_name}`: {exc}"  # Include exception for LLM clarity

        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": content_for_llm,
            }
        )

    def _llm_loop(self, seed: int) -> Iterator[Tuple[YieldType, str]]:
        # Tool-calling loop
        final_response = "I was unable to find the desired information."
        limit_loop = 6
        # logger.debug("   Thinking...")
        sys.stdout.flush()

        found_final_result = False

        for count in range(limit_loop): # Iterates from 0 to 5
            time.sleep(1)  # Add a one-second delay to prevent overwhelming the AI remote

            messages_for_llm = list(self.messages)
            tools_to_send = self.tool_definitions  # Send all tools on each attempt

            response = self._llm_complete(messages_for_llm, tools_to_send, seed)

            if not response.choices:
                # logger.debug("No response choices available from the AI model.")
                found_final_result = True
                break

            msg = response.choices[0].message
            self.messages.append(msg.to_dict())  # Add the actual message to the persistent history

            if msg.tool_calls:
                # sometimes there is no content returned in the msg.content
                # if there is then usually an explained strategy what the
                # model will do to achieve the final result
                if msg.content:    
                    yield (YieldType.PARTIAL, msg.content)
                for tool_call in msg["tool_calls"]:
                    yield (YieldType.TOOL_CALL, tool_call['function']['name'])
                    self.execute_tool(tool_call)
            else:
                final_response = response.choices[0].message.content
                found_final_result = True
                break

        # If the loop completed without being interrupted (no break), force a final response.
        if not found_final_result:
            # Append a temporary system message to guide the final response
            messages_for_llm = list(self.messages)  # Start from the current message history
            messages_for_llm.append(
                {
                    "role": "system",
                    "content": "You have reached the maximum number of "
                    "tool-calling attempts. Based on the information gathered "
                    "so far, provide the most complete answer you can, or "
                    "clearly state what information you could not obtain. Do "
                    "not attempt to call any more tools."
                }
            )
            response = self._llm_complete(messages_for_llm, None, seed)  # No tools!
            if response.choices:
                final_response = response.choices[0].message.content

        # Ensure final_response is set in case of edge cases
        if final_response == "I was unable to find the desired information." and self.messages and self.messages[-1].get("content"):
            final_response = self.messages[-1]["content"]

        yield (YieldType.FINAL, final_response)

    # Tools:
    def get_person(self, person_handle: str) -> Dict[str, Any]:
        """
        Given a person's handle, get the data dictionary of that person.
        """
        data = dict(self.db.get_raw_person_data(person_handle))
        return data
        

    def get_mother_of_person(self, person_handle: str) -> Dict[str, Any]:
        """
        Given a person's handle, return their mother's data dictionary.
        The person_handle to pass to this func is the "person_handle" (a string) for the person
        whose mother you want to find.
        """
        person_obj = self.db.get_person_from_handle(person_handle)
        obj = self.sa.mother(person_obj)
        data = dict(self.db.get_raw_person_data(obj.handle))
        return data

    def get_family(self, family_handle: str) -> Dict[str, Any]:
        """
        Get the data of a family given the family handle in the argument.
        * family handles are different from a person handle.
        * a person has family handles in two different fields:
        - "parent_family_list" has the list of family handles the person is a child in
        - "family_list" has the list of family handles the person is a parent in
        The result of "get_family" tool contains several handles as follows:
        "father_handle": person_handle of the father in the family
        "mother_handle": person_handle of the mother in the family
        "child_ref_list": list of person_handles of children in the family,
        each item in the "child_ref_list" has a "ref" which is the person_handle of children of the family.
        Details of the persons can be retrieved using the "get_person" tool
        """
        data = dict(self.db.get_raw_family_data(family_handle))
        return data

    def start_point(self) -> Dict[str, Any]:
        """
        Get the start point of the genealogy tree, i.e., the default person.
        This tool does not take any "arguments".
        * Call this tool without arguments
        * Use this tool to get the first person in the genealogy tree.

        The result of start_point contains values for:
        * The "first_name" contains the first name of this person.
        * The "surname_list" and then "surname" contains the last name(s) of this person.
        * The "handle" is the key that looks like a hash string for this person to use for other tool calls.
        * "family_list" is a list of handles where this person is a parent.
        * "parent_family_list" is a list of handles for the families where this person is listed as a child.
        """
        obj = self.db.get_default_person()
        if obj:
            data = dict(self.db.get_raw_person_data(obj.handle))
            return data
        return None

    def get_children_of_person(self, person_handle: str) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Get a list of children handles and their details for a person's main family,
        given a person's handle.

        Returns a list of tuples, where each tuple contains:
        - The child's handle (str)
        - The child's details (dict) as returned by get_person
        """
        obj = self.db.get_person_from_handle(person_handle)
        family_handle_list = obj.get_family_handle_list()
        children_data = []

        if family_handle_list:
            family_id = family_handle_list[0]
            family = self.db.get_family_from_handle(family_id)
            child_handles = [handle.ref for handle in family.get_child_ref_list()]

            for handle in child_handles:
                person_data = self.get_person(handle)  # Use the existing get_person tool
                children_data.append((handle, person_data))

        return children_data

    def get_father_of_person(self, person_handle: str) -> Dict[str, Any]:
        """
        Given a person's handle, return their father's data dictionary.
        The "person_handle" to pass to this func is the "person_handle" (a string)
        for the person whose father you want to find.
        """
        person_obj = self.db.get_person_from_handle(person_handle)
        obj = self.sa.father(person_obj)
        data = dict(self.db.get_raw_person_data(obj.handle))
        return data

    def get_person_birth_date(self, person_handle: str) -> str:
        """
        Given a person's handle, return the birth date as a string.
        """
        person = self.db.get_person_from_handle(person_handle)
        return self.sa.birth_date(person)

    def get_person_death_date(self, person_handle: str) -> str:
        """
        Given a person's handle, return the death date as a string.
        """
        person = self.db.get_person_from_handle(person_handle)
        return self.sa.death_date(person)

    def get_person_birth_place(self, person_handle: str) -> str:
        """
        Given a person's handle, return the birth date as a string.
        """
        person = self.db.get_person_from_handle(person_handle)
        return self.sa.birth_place(person)

    def get_person_death_place(self, person_handle: str) -> str:
        """
        Given a person's handle, return the death place as a string.
        """
        person = self.db.get_person_from_handle(person_handle)
        return self.sa.death_place(person)

    def get_person_event_list(self, person_handle: str) -> List[str]:
        """
        Get a list of event handles associated with a person,
        given the person handle. Use `get_event(event_handle)`
        to look up details about an event.
        """
        obj = self.db.get_person_from_handle(person_handle)
        if obj:
            return [ref.ref for ref in obj.get_event_ref_list()]

    def get_event(self, event_handle: str) -> Dict[str, Any]:
        """
        Given an event_handle, get the associated data dictionary.
        """
        data = dict(self.db.get_raw_event_data(event_handle))
        return data

    def get_event_place(self, event_handle: str) -> str:
        """
        Given an event_handle, return the associated place string.
        """
        event = self.db.get_event_from_handle(event_handle)
        return place_displayer.display_event(self.db, event)

    def get_child_in_families(self, person_handle: str) -> List[Dict[str, Any]]:
        """
        Retrieve detailed information about all families where the given person is listed as a child.
        This tool is essential for genealogical research, allowing users to identify the person's siblings
        and parents by examining the family structures they belong to. It returns a list of dictionaries,
        each containing comprehensive data about a family, facilitating in-depth family tree analysis.
        """
        person_obj = self.db.get_person_from_handle(person_handle)
        families = self.sa.child_in(person_obj)
        family_data_list = []

        for family in families:
            family_data = self.get_family(family.handle)
            family_data_list.append(family_data)

        return family_data_list

    def create_search_pattern(self, search_string: str) -> Pattern:
        """
        Creates a case-insensitive regex pattern to match any of the words
        in a given search string, using word boundaries.
        
        Args:
            search_string: The string containing words to search for.
        
        Returns:
            A compiled regex Pattern object.
        """
        # 1. Split the search string into individual words.
        search_terms = search_string.split()
        
        # Handle the case of an empty search string
        if not search_terms:
            # Return a pattern that will not match anything
            return re.compile(r'$^')

        # 2. Escape each term to treat special regex characters as literals.
        escaped_terms = [re.escape(term) for term in search_terms]

        # 3. Join the escaped terms with the regex "OR" operator.
        regex_or_pattern = "|".join(escaped_terms)
        
        # 4. Add word boundaries to the pattern and compile it.
        final_pattern = re.compile(r'\b(?:' + regex_or_pattern + r')\b', re.IGNORECASE)
        
        return final_pattern

    def find_people_by_name(self, search_string: str) -> List[Dict[str, Any]]:
        """
        Searches the Gramps database for people whose primary or alternate names
        contain the given search string.

        Argument:
            One string to match in person names.

        Returns:
            A list of dictionaries, where each dictionary contains the raw data
            of a matching person.
        
         Example:
            To find people named "Chris Woods", call the tool with:
            find_people_by_name(search_string="Chris Woods")
        """
        matching_people_raw_data = []
        #search_pattern = re.compile(re.escape(search_string), re.IGNORECASE)
        search_pattern = self.create_search_pattern(search_string)

        for person_obj in self.sa.all_people():
            matched = False

            # Helper function to check fields within a Name or Surname object
            def check_name_fields(name_or_surname_obj: Any) -> bool:
                """Checks relevant string fields of a Name or Surname object for a match."""
                fields_to_check = []

                # Fields common to Name object (primary_name or alternate_name elements)
                if hasattr(name_or_surname_obj, 'first_name'):
                    fields_to_check.append(name_or_surname_obj.first_name)
                # Corrected: 'prefix' and 'suffix' are properties of the Name object itself, not the Surname object.
                if hasattr(name_or_surname_obj, 'prefix'):
                    fields_to_check.append(name_or_surname_obj.prefix)
                if hasattr(name_or_surname_obj, 'suffix'):
                    fields_to_check.append(name_or_surname_obj.suffix)
                if hasattr(name_or_surname_obj, 'title'):
                    fields_to_check.append(name_or_surname_obj.title)
                if hasattr(name_or_surname_obj, 'call'):
                    fields_to_check.append(name_or_surname_obj.call)
                if hasattr(name_or_surname_obj, 'nick'):
                    fields_to_check.append(name_or_surname_obj.nick)
                if hasattr(name_or_surname_obj, 'famnick'):
                    fields_to_check.append(name_or_surname_obj.famnick)
                if hasattr(name_or_surname_obj, 'patronymic'):
                    fields_to_check.append(name_or_surname_obj.patronymic)

                # Fields specific to Surname object (within surname_list)
                if hasattr(name_or_surname_obj, 'surname'): # This means it's a Surname object
                    fields_to_check.append(name_or_surname_obj.surname)
                    # Note: Surname objects can also have their own 'prefix' and 'connector'
                    # which are separate from the 'prefix' of the main Name object.
                    if hasattr(name_or_surname_obj, 'connector'):
                        fields_to_check.append(name_or_surname_obj.connector)

                for field_value in fields_to_check:
                    # Ensure field_value is a non-empty string before attempting search
                    if isinstance(field_value, str) and field_value and search_pattern.search(field_value):
                        return True
                return False

            # Check primary name fields
            if person_obj.primary_name:
                if check_name_fields(person_obj.primary_name):
                    matched = True

                # Surnames are in a list, iterate through each Surname object
                if not matched and hasattr(person_obj.primary_name, 'surname_list'):
                    for surname_obj in person_obj.primary_name.surname_list:
                        if check_name_fields(surname_obj): # Check the Surname object
                            matched = True
                            break

            # Check alternate name fields if not already matched
            if not matched and hasattr(person_obj, 'alternate_names') and person_obj.alternate_names:
                for alt_name in person_obj.alternate_names:
                    if check_name_fields(alt_name):
                        matched = True
                        break

                    # Check surnames within alternate name
                    if not matched and hasattr(alt_name, 'surname_list'):
                        for alt_surname_obj in alt_name.surname_list:
                            if check_name_fields(alt_surname_obj):
                                matched = True
                                break
                        if matched: # Break from outer alt_names loop if matched
                            break

            if matched:
                # Use the existing _get_raw_person_from_id_data to get raw data
                # self.db is assumed to be the database access object within the tool's class.
                raw_data = dict(self.db._get_raw_person_from_id_data(person_obj.gramps_id))
                desired_fields = {
                    "handle": raw_data.get("handle"),
                    "first_name": raw_data.get("primary_name", {}).get("first_name"),
                    "surname": raw_data.get("primary_name", {}).get("surname_list", [{}])[0].get("surname"),
                    "prefix": raw_data.get("primary_name", {}).get("surname_list", [{}])[0].get("prefix")
                }
                matching_people_raw_data.append(desired_fields)

        return matching_people_raw_data




    