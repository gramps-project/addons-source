#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017 Sam Manzi
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

"Import from TMG (The Master Genealogist) Projects"

#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
import glob  # used by insensitive_glob()
import os    # used by clearconsole()
import sys


#------------------------------------------------------------------------
#
# Set up logging
#
#------------------------------------------------------------------------
import logging
LOG = logging.getLogger(".TMGImport")


#------------------------------------------------------------------------
#
# External Libraries
#
#------------------------------------------------------------------------
# External Library: dbf.pypi
# https://pypi.python.org/pypi/dbf
try:
    from dbf import Table
except:
    print("\nFor TMGViewer to work you\nPlease install 'dbf' \
           from https://pypi.python.org/pypi/dbf ")
    sys.exit()


#------------------------------------------------------------------------
#
# TMG Database Viewer - Libraries
#
#------------------------------------------------------------------------


#------------------------------------------------------------------------
#
# TMG DBF tables
#
#------------------------------------------------------------------------
'''
All TMG DBF Tables
'''
#------------------------------------------------------------------------
#
#  Person File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
$.DBF - tmgPeople - Person File
'''


#------------------------------------------------------------------------
#
#  Source Type File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
A .dbf - tmgSourceCategories - Source Type File
'''


#------------------------------------------------------------------------
#
#  Focus Group Members
##TODO
#------------------------------------------------------------------------
'''

Table:
B .dbf - tmgFocusGroupMembers - Focus Group Member File
'''


#------------------------------------------------------------------------
#
#  Flag File
##TODO
#------------------------------------------------------------------------
'''

Table:
C.DBF - tmgCustomFlags - Flag File
'''



#------------------------------------------------------------------------
#
#  Data Set File
##TODO
#------------------------------------------------------------------------
'''

Table:
D .dbf - tmgDataSets - Data Set File
'''
'''
Fields:
-----------------------------
 0 - dsid      : 8                 # DataSet ID# (Primary key)
 1 - dsname    : u'Royal92 import' # DataSet Name
 2 - dslocation: u'royal92.ged'    # Original Import location
 3 - dstype    : 1                 # Import type
 4 - dslocked  : False             # Is DataSet Locked
 5 - dsenabled : True              # Is DataSet Enabled
 6 - property  : u''               #
 7 - dsp       : u''               #
 8 - dsp2      : u''               #
 9 - dcomment  : u'A comment here' # DataSet Comment
10 - host      : u''               #
11 - namestyle : 0                 # Default name style for this dataset
                                     Relates to st.styleid(ST.DBF).
12 - placestyle: 0                 # Default place style for this dataset
                                     Relates to st.styleid(ST.DBF).
13 - tt        : u' '              #
-----------------------------
'''
def d_dbf():
    with tmgDataSets:
        d_fields = {}
        print(tmgDataSets.fields)
        print(tmgDataSets.field_count)
        print(tmgDataSets.record_count)
        return d_fields


#------------------------------------------------------------------------
#
#  DNA
##TODO
#------------------------------------------------------------------------
'''

Table:
dna.dbf - tmgDNAinformation - DNA File
'''


#------------------------------------------------------------------------
#
#  Event Witness File
##TODO
#------------------------------------------------------------------------
'''

Table:
E.DBF - tmgParticipantsWitnesses -Event Witness File
'''


#------------------------------------------------------------------------
#
#  Parent/Child Relationship
##TODO
#------------------------------------------------------------------------
'''

Table:
F .dbf - tmgParentChildRelationships - Parent/Child Relationship
'''


#------------------------------------------------------------------------
#
#  Event File
##TODO
#------------------------------------------------------------------------
'''

Table:
G.DBF - tmgEvents - Event File
'''


#------------------------------------------------------------------------
#
#  Exhibits
##TODO
#------------------------------------------------------------------------
'''

Table:
I .dbf - tmgExhibits - Exhibit File
'''


#------------------------------------------------------------------------
#
#  Timeline
##TODO
#------------------------------------------------------------------------
'''

Table:
K .dbf - tmgTimelineLocks - Timeline Lock File
'''


#------------------------------------------------------------------------
#
#  Research Tasks
##TODO
#------------------------------------------------------------------------
'''

Table:
L .dbf - tmgResearchTasks - Research Log File
'''

#------------------------------------------------------------------------
#
#  Source File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
M .dbf - tmgSources - Source File
'''


#------------------------------------------------------------------------
#
#  Name File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
N.DBF - tmgNames - Name File
'''


#------------------------------------------------------------------------
#
#  Name Dictionary File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
ND.DBF - tmgNameDictionary - Name Dictionary File
'''


#------------------------------------------------------------------------
#
#  Name Part Type File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
NPT.DBF - tmgNamePartType - Name Part Type File
'''


#------------------------------------------------------------------------
#
#  Name Part Value File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
NPV.DBF - tmgNamePartValue - Name Part Value File
'''


#------------------------------------------------------------------------
#
#  Focus Groups
##TODO
#------------------------------------------------------------------------
'''

Table:
O .dbf - tmgFocusGroups - Focus Group File
'''


#------------------------------------------------------------------------
#
#  Place File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
P.DBF - tmgPlaces - Place File
'''


#------------------------------------------------------------------------
#
#  Place Dictionary File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
PD.DBF - tmgPlaceDictionary - Place Dictionary File
'''


#------------------------------------------------------------------------
#
#  Place Part Type File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
PPT.DBF - tmgPlacePartType - Place Part Type File
'''


#------------------------------------------------------------------------
#
#  Place Part Value File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
PPV.DBF - tmgPlacePartValue - Place Part Value File
'''


#------------------------------------------------------------------------
#
#  Repository File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
R .dbf - tmgRepositories - Repository File
'''


#------------------------------------------------------------------------
#
#  Source Citation File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
S .dbf - tmgCitations - Source Citation File
'''


#------------------------------------------------------------------------
#
#  Style File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
ST.DBF - tmgStyles - Style File
'''


#------------------------------------------------------------------------
#
#  Tag Type File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
T.DBF - tmgTagTypes - Tag Type File
'''


#------------------------------------------------------------------------
#
#  Source Element File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
U .dbf - tmgSourceComponents - Source Element File
'''


#------------------------------------------------------------------------
#
#  Repository Link File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
W .dbf - tmgSourceRepositoryLinks - Repository Link File
'''


#------------------------------------------------------------------------
#
#  Excluded Pair File
##TODO
#------------------------------------------------------------------------
'''

Table:
XD .dbf - tmgExcludedDuplicates - Excluded Pair File
'''


############################################################
# Testing (#TODO: move to seperate file and expand)
############################################################
if __name__ == '__main__':
    pass

