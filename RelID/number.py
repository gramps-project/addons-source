#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015 geggi
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
Utilities to number identifiers
"""

#-------------------------------------------------------------------------
#
# Standard python modules
#
#-------------------------------------------------------------------------

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------

#-------------------------------------------------------------------------
#
# get_number
#
#-------------------------------------------------------------------------

def get_number(Ga, Gb, rel_a, rel_b):
    if Ga is None or Gb is None or rel_a is None or rel_b is None:
        return "u"  # Return "u" for undefined or invalid inputs

    if Ga < 0 or Gb < 0:
        return get_number_down(rel_b)
    elif Ga == Gb:
        return search_number(Ga)
    elif Ga == 0:  # the other_person (B) is a direct descendant of A
        return get_number_down(rel_b)
    elif Gb == 0:  # the other_person (B) is a direct ancestor of A
        return get_number_up(rel_a)
    else:
        return "u"  # Return "u" for undefined or invalid inputs

def get_number_up(rel_a):
    if not rel_a or not isinstance(rel_a, str):
        return "nb"  # Return "nb" for invalid inputs

    rel_num = 1
    for i in range(0, len(rel_a)):
        c = rel_a[i]
        if c == 'f':
            rel_num = rel_num * 2
        elif c == 'm':
            rel_num = (rel_num * 2) + 1
        else:  # we do not care about non-birth relationship (or we forgot to capture one character above)
            return "nb"  # Return "nb" for non-birth relationships or invalid characters

    return rel_num

def get_number_down(rel_b): #experimental sosa miror
    if not rel_b or not isinstance(rel_b, str):
        return "nb"  # Return "nb" for invalid inputs

    # Start with the root person's number (1)
    rel_num = 1.0

    # Iterate through the relationship path to build the descendant number
    for i in range(0, len(rel_b)):
        c = rel_b[i]
        if c == 'f' or c == 'm':
            # Divide the parent's number by 2 for each child
            rel_num = rel_num / 2
        else:
            return "nb"  # Return "nb" for non-birth relationships or invalid characters

    return rel_num

def search_number(Ga): # TODO: Implement logic for numbering cousins or other relationships
    if Ga <= 0:
        return "u"  # Return "u" for undefined or invalid inputs

    # Example: Return a unique identifier for cousins based on Ga
    return f"cousin_{Ga}"  # Placeholder: Replace with actual logic
