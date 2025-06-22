from typing import Dict, Any, List, Optional

import os
import json
import sys

try:
    import litellm
except ImportError:
    raise Exception("GrampsChat requires litellm")
# import markdown

from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.simple import SimpleAccess
from gramps.gen.db.utils import open_database
from gramps.gen.display.place import displayer as place_displayer

from opik.opik_context import get_current_span_data

_ = glocale.translation.gettext

HELP_TEXT = """
GrampsChat uses the following OS environment variables:

```
export GRAMPS_AI_MODEL_NAME="<ENTER MODEL NAME HERE>"
```

This is always needed. Examples: "ollama/deepseek-r1:1.5b", "openai/gpt-4o-mini"

```
export GRAMPS_AI_MODEL_URL="<ENTER URL HERE>" 
```

This is needed if running your own LLM server. Example: "http://127.0.0.1:8000"

You can find a list of litellm providers here:
https://docs.litellm.ai/docs/providers

You can find a list of ollama models here:
https://ollama.com/library/deepseek-r1:1.5b

### Optional

If you are running a commercial AI model provider, you will need their API key.

#### Example

For OpenAI:

```
export OPENAI_API_KEY="sk-..."
```

To record your conversations in Opik:

```
export OPIK_API_KEY="<ENTER OPIK API KEY HERE>"
```

To get an Opik API Key:
https://www.comet.com/site/
"""

SYSTEM_PROMPT = """
You are a helpful genealogist and an expert in the
Gramps open source genealogy program. Never mention to
the user what an item's handle is. Never give a handle
as an answer, always look up the details of a handle (like
the person's name, or a family parents' names).
"""

GRAMPS_AI_MODEL_NAME = os.environ.get("GRAMPS_AI_MODEL_NAME")
GRAMPS_AI_MODEL_URL = os.environ.get("GRAMPS_AI_MODEL_URL")
OPIK_API_KEY = os.environ.get("OPIK_API_KEY")
OPIK_PROJECT_NAME = os.environ.get("OPIK_PROJECT_NAME")
if OPIK_PROJECT_NAME is None:
    os.environ["OPIK_PROJECT_NAME"] = "gramps"

if OPIK_API_KEY:
    try:
        from litellm.integrations.opik.opik import OpikLogger
    except Exception:
        raise Exception("GrampsChat with OPIK_API_KEY set requires opik")

    opik_logger = OpikLogger()
    litellm.callbacks = [opik_logger]

from litellm_utils import function_to_litellm_definition


class Chatbot:
    def __init__(self, database_name):
        self.db = open_database(database_name, force_unlock=True)
        if self.db is None:
            raise Exception(f"Unable to open database {database_name}")
        self.messages = []
        self.sa = SimpleAccess(self.db)
        self.tool_map = {
            "get_home_person": self.get_home_person,
            "get_mother_of_person": self.get_mother_of_person,
            "get_family": self.get_family,
            "get_person": self.get_person,
            "get_children_of_person": self.get_children_of_person,
            "get_father_of_person": self.get_father_of_person,
            "get_person_birth_date": self.get_person_birth_date,
            "get_person_death_date": self.get_person_death_date,
            "get_person_birth_place": self.get_person_birth_place,
            "get_person_death_place": self.get_person_death_place,
            "get_person_event_list": self.get_person_event_list,
            "get_event": self.get_event,
            "get_event_place": self.get_event_place,
        }
        self.tool_definitions = [
            function_to_litellm_definition(self.get_home_person),
            function_to_litellm_definition(self.get_mother_of_person),
            function_to_litellm_definition(self.get_family),
            function_to_litellm_definition(self.get_person),
            function_to_litellm_definition(self.get_children_of_person),
            function_to_litellm_definition(self.get_father_of_person),
            function_to_litellm_definition(self.get_person_birth_date),
            function_to_litellm_definition(self.get_person_death_date),
            function_to_litellm_definition(self.get_person_birth_place),
            function_to_litellm_definition(self.get_person_death_place),
            function_to_litellm_definition(self.get_person_event_list),
            function_to_litellm_definition(self.get_event),
            function_to_litellm_definition(self.get_event_place),
        ]

    def chat(self):
        self.messages.append({"role": "system", "content": SYSTEM_PROMPT})
        query = input("\n\nEnter your question: ")
        while query:
            self.get_chatbot_response(query)
            query = input("\n\nEnter your question: ")

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
            # stream=True,
            metadata={
                "opik": {
                    "current_span_data": get_current_span_data(),
                },
            },
            # **self.model_kwargs,
        )
        return response

    def get_chatbot_response(
        self,
        user_input: str,
        seed: int = 42,
    ) -> Any:
        self.messages.append({"role": "user", "content": user_input})
        retval = self._llm_loop(seed)
        print("\n\n>>>", retval),  # is_user=False)
        self.messages.append(
            {
                "role": "assistant",
                "content": retval,
            }
        )

    def _llm_loop(self, seed):
        # Tool-calling loop
        final_response = "I was unable to find the desired information."
        count = 0
        print("   Thinking...", end="")
        sys.stdout.flush()
        while count < 10:
            count += 1
            response = self._llm_complete(self.messages, self.tool_definitions, seed)
            msg = response.choices[0].message
            self.messages.append(msg.to_dict())
            if msg.tool_calls:
                for tool_call in msg["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])
                    print(".", end="")
                    sys.stdout.flush()
                    tool_func = self.tool_map.get(tool_name)
                    try:
                        tool_result = (
                            tool_func(**arguments)
                            if tool_func is not None
                            else "Unknown tool"
                        )
                    except Exception as exc:
                        print(exc)
                        tool_result = f"Error in calling tool `{tool_name}`"
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": str(tool_result),
                        }
                    )
            else:
                final_response = response.choices[0].message.content
                break
        return final_response

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
        """
        person_obj = self.db.get_person_from_handle(person_handle)
        obj = self.sa.mother(person_obj)
        data = dict(self.db.get_raw_person_data(obj.handle))
        return data

    def get_family(self, family_handle: str) -> Dict[str, Any]:
        """
        Get a family's data given the family handle. Note that family
        handles are different from a person handle. You can use a person's
        family data to get the family handle.
        """
        data = dict(self.db.get_raw_family_data(family_handle))
        return data

    def get_home_person(self) -> Dict[str, Any]:
        """
        Get the home person data.
        """
        obj = self.db.get_default_person()
        if obj:
            data = dict(self.db._get_raw_person_from_id_data(obj.gramps_id))
            return data
        return None

    def get_children_of_person(self, person_handle: str) -> List[str]:
        """
        Get a list of children handles of a person's main family,
        given a person's handle.
        """
        obj = self.db.get_person_from_handle(person_handle)
        family_handle_list = obj.get_family_handle_list()
        if family_handle_list:
            family_id = family_handle_list[0]
            family = self.db.get_family_from_handle(family_id)
            return [handle.ref for handle in family.get_child_ref_list()]
        else:
            return []

    def get_father_of_person(self, person_handle: str) -> Dict[str, Any]:
        """
        Given a person's handle, return their father's data dictionary.
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


if __name__ == "__main__":
    chatbot = Chatbot("Gramps Example")
    chatbot.chat()
