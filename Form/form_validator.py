#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Eduard Ralph
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

"""
Pure-Python validation for Form addon XML definition files.

Kept free of GTK/Gramps imports so it can be unit-tested without a GUI
environment.
"""

# ------------------------
# Python modules
# ------------------------
import xml.dom.minidom
import xml.parsers.expat

VALID_SECTION_TYPES = frozenset({"person", "family", "multi"})
REQUIRED_FORM_ATTRS = ("id", "title", "type")


def split_family_title(title: str) -> tuple[str, str]:
    """
    Split a family-section title of the form ``'X/Y'`` into ``(X, Y)``.

    Falls back gracefully when the separator is absent or the input is
    empty, so callers never raise ``ValueError`` on malformed XML.

    :param title: the raw title string from the XML (may be empty)
    :returns: a two-tuple of title parts; the second element is empty
              when the title contains no ``'/'``
    """
    if not title:
        return "", ""
    parts = title.split("/", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], ""


def validate_form_element(form) -> list[str]:
    """
    Validate a single ``<form>`` DOM element against the form schema.

    :param form: a DOM element for a single form definition
    :returns: a list of human-readable error messages scoped to this
              form; empty when the form is valid
    """
    errors: list[str] = []

    form_id = form.attributes["id"].value if "id" in form.attributes else "<missing id>"
    for required in REQUIRED_FORM_ATTRS:
        if required not in form.attributes:
            errors.append(
                "Form '%s': missing required attribute '%s'" % (form_id, required)
            )

    for section in form.getElementsByTagName("section"):
        role = section.attributes["role"].value if "role" in section.attributes else ""
        if not role:
            errors.append(
                "Form '%s': <section> is missing required attribute 'role'" % form_id
            )
            continue

        if "type" not in section.attributes:
            errors.append(
                "Form '%s': section '%s' is missing required attribute 'type'"
                % (form_id, role)
            )
            continue

        section_type = section.attributes["type"].value
        if not section_type:
            errors.append(
                "Form '%s': section '%s' has an empty 'type' attribute"
                % (form_id, role)
            )
            continue

        if section_type not in VALID_SECTION_TYPES:
            errors.append(
                "Form '%s': section '%s' has invalid type '%s' "
                "(expected one of: %s)"
                % (
                    form_id,
                    role,
                    section_type,
                    ", ".join(sorted(VALID_SECTION_TYPES)),
                )
            )
            continue

        title = (
            section.attributes["title"].value if "title" in section.attributes else ""
        )
        if section_type == "family":
            parts = title.split("/")
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                errors.append(
                    "Form '%s': family section '%s' requires a title "
                    "of the form 'Name1/Name2' (got '%s')" % (form_id, role, title)
                )

    return errors


def validate_form_dom(dom: xml.dom.minidom.Document) -> list[str]:
    """
    Validate the structure of a parsed form definitions DOM.

    Checks that:

    * a ``<forms>`` root element exists and contains at least one
      ``<form>`` definition;
    * each ``<form>`` element has ``id``, ``title`` and ``type`` attributes;
    * each ``<section>`` element has non-empty ``role`` and ``type``
      attributes;
    * each section's ``type`` is one of ``person``, ``family`` or ``multi``;
    * ``family``-type sections declare a title of the form ``'X/Y'`` with
      two non-empty parts.

    :param dom: a parsed ``xml.dom.minidom.Document``
    :returns: a list of human-readable error messages; empty when the
              document is valid
    """
    top = dom.getElementsByTagName("forms")
    if not top:
        return ["Missing <forms> root element"]

    errors: list[str] = []
    forms = top[0].getElementsByTagName("form")
    if not forms:
        errors.append("<forms> root element contains no <form> definitions")
    for form in forms:
        errors.extend(validate_form_element(form))
    return errors


def parse_and_validate(path: str) -> tuple[xml.dom.minidom.Document | None, list[str]]:
    """
    Parse ``path`` as XML and validate it against the form schema.

    :param path: filesystem path to a form definitions XML file
    :returns: a ``(dom, errors)`` tuple. When parsing fails, ``dom`` is
              ``None`` and ``errors`` contains a single description of
              the syntax error. When parsing succeeds, ``dom`` is the
              parsed document and ``errors`` lists any structural
              problems (empty when the file is valid).
    """
    try:
        dom = xml.dom.minidom.parse(path)
    except xml.parsers.expat.ExpatError as exc:
        return None, ["XML syntax error: %s" % exc]
    except (OSError, ValueError) as exc:
        return None, ["Failed to read file: %s" % exc]
    return dom, validate_form_dom(dom)
