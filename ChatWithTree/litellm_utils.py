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
import inspect
import typing
from typing import Any, Callable, Dict, List, Optional


def function_to_litellm_definition(
    func: Callable, description: Optional[str] = None
) -> Dict[str, Any]:
    sig = inspect.signature(func)
    doc = description or func.__doc__ or ""

    properties: Dict[str, Dict[str, str]] = {}
    required: List[str] = []

    for name, param in sig.parameters.items():
        param_type = (
            param.annotation if param.annotation != inspect.Parameter.empty else str
        )
        json_type = python_type_to_json_type(param_type)
        properties[name] = {"type": json_type, "description": f"{name} parameter"}
        if param.default == inspect.Parameter.empty:
            required.append(name)

    function_def = {
        "name": func.__name__,
        "description": doc.strip(),
    }

    # If the function has parameters, we add them to the definition
    # as the start_point does not have any properties we deliberately
    # do not add the "parameters" key if there are no properties
    # - some smaller LLMs do not understand this and throw an error
    # for the start point function when they try to call it
    if properties:
        function_def["parameters"] = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    return {
        "type": "function",
        "function": function_def,
    }


def python_type_to_json_type(python_type: type) -> str:
    # Basic type mapping
    if python_type in [str]:
        return "string"
    elif python_type in [int]:
        return "integer"
    elif python_type in [float]:
        return "number"
    elif python_type in [bool]:
        return "boolean"
    elif python_type in [dict]:
        return "object"
    elif python_type in [list, typing.List]:
        return "array"
    else:
        return "string"  # default fallback
