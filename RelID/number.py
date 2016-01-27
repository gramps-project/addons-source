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
    number = 0
    if Ga<0 or Gb<0:
        number = get_number_down(rel_a, rel_b)
    elif Ga==Gb:
        number = search_number(Ga)
    elif Ga==0: # the other_person (B) is a direct descendant of A
        number = get_number_down(rel_b)
    elif Gb==0: # the other_person (B) is a direct ancestor of A
        number = get_number_up(rel_a)
    return str(number)

def get_number_up(rel_a):
    rel_num = 1
    for i in range(0, len(rel_a)):
        c = rel_a[i]
        if c=='f':
            rel_num = rel_num * 2
        elif c=='m':
            rel_num = (rel_num * 2) + 1
        else:   # we do not care about non-birth relationship (or we forgot to capture one character above)
            rel_num = "nb"
    return rel_num

def get_number_down(rel_b): #experimental sosa miror
    rel_num = -1
    for i in range(0, len(rel_b)):
        c = rel_b[i]
        if c=='f':
            rel_num = rel_num / 2
        elif c=='m':
            rel_num = rel_num
        else:   # we do not care about non-birth relationship (or we forgot to capture one character above)
            rel_num = "nb"
    return rel_num

def search_number(Ga): #TODO
    return "u"
