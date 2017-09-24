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

'''
Import from an Wholly Genes - The Master Genealogist (TMG) Project backup file
(*.SQZ)
'''
'''
Parse and display TMG Date format & Convert to Gramps Date Object.
'''
'''
Special Field Values
====================

Dates
=====
Date fields contain a structured value as follows:

--------------------------------------------------
Irregular Dates
--------------------------------------------------
Position | Value    | Meaning
--------------------------------------------------
   1     |  “0”     | Irregular date code
--------------------------------------------------
  2-30   | (text)   | Irregular date value
--------------------------------------------------
Regular Dates
--------------------------------------------------
Position | Value    | Meaning
--------------------------------------------------
   1     |  “1”     | Regular date code
--------------------------------------------------
  2-9    |“YYYYMMDD”| Regular date value
--------------------------------------------------
   10    |   “0”    | Not Old Style
         |   “1”    | Old Style
--------------------------------------------------
   11    |   “0”    | Before date
         |   “1”    | Say date
         |   “2”    | Circa date
         |   “3”    | Exact date
         |   “4”    | After date
         |   “5”    | Between date
         |   “6”    | Or date
         |   “7”    | From…to date
--------------------------------------------------
  12-19  |“00000000”| Used for before, say,
         |          | circa, exact, and after
         |          | dates.
--------------------------------------------------
         |“YYYYMMDD”| Second date for between,
         |          | or, and from/to dates.
--------------------------------------------------
   20    |   “0”    | Used for before, say,        # Missing
         |          | circa, exact, and after      #(Not old style date 2)
         |          | dates.
.................................................. # Missing
         |   "1"    | Old style date 2             # Missing
--------------------------------------------------
  21     |   “0”    | No question mark
         |   “1”    | Question mark
--------------------------------------------------
  22-30  |(reserved)| (reserved)
--------------------------------------------------

Date Examples:
--------------------------------------------------
Stored as                   | Displayed As
--------------------------------------------------
“0Third Monday in January”  | “Third Monday in January”
--------------------------------------------------
“119610924000000000000   ”  | “Before 09 Sep 1961”
--------------------------------------------------
“117120100130000000000   ”  | “Jan 1712/13”
--------------------------------------------------
“119420000051943000000   ”  | “Between 1942 and 1943”
--------------------------------------------------
“100000000030000000000   ”  |(empty date)
--------------------------------------------------
Page: 22
The Master Genealogist (TMG) - File Structures for v9
Last Updated: July 2014
COPYRIGHT © 2014, Wholly Genes, Inc. All Rights Reserved.
Filename: TMG9_file_structures.rtf
URL: http://www.whollygenes.com/forums201/index.php?/topic/381-file-structures-for-the-master-genealogist-tmg/
'''
#TODO Convert to Gramps Date.set() [gramps.gen.lib.DateObjects]
#TODO Convert Gramps Date back to TMG Date for Export to TMG 9.05
#TODO from gramps.gen.datehandler import parser as _dp
#TODO _dp.parse(parse_date)  # Parses the text, returning a Date object.
#TODO https://gramps-project.org/docs/date.html#gramps.gen.datehandler._dateparser.DateParser.parse
#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
import calendar

#------------------------------------------------------------------------
#
#  num_to_month()
#
#------------------------------------------------------------------------


def num_to_month(convertmonth):
    '''
    Pass a two digit tmg month string in the form
    of MM and return Mmm (eg: 09 => Sep)
    '''
    convertmonth = int(convertmonth)
#    longmonth = calendar.month_name[convertmonth]
    shortmonth = calendar.month_abbr[convertmonth]
    return shortmonth

#------------------------------------------------------------------------
#
#  num_to_date()
#
#------------------------------------------------------------------------


def num_to_date(convertdate):
    '''
    Pass a 8 digit tmg string in the form of YYYYMMDD and return DD Mmm YYYY
    (eg: 20130920 => 20 Sep 2013)
    '''
    convertdate = convertdate
    YYYY, MM, DD = convertdate[0:4], convertdate[4:6], convertdate[6:8]
    dd1 = int(DD)
    mm1 = int(MM)
    yyyy1 = int(YYYY)

    mm2 = num_to_month(int(MM))

    # 000 if each field has no value return None
    if (dd1 <= 0) and (mm1 <= 0) and (yyyy1 <= 0):
        # return a blank field ""? or None? was '(empty date)'
        return

    # 001 display only the year
    if ((dd1 <= 0) and (mm1 <= 0)) and (yyyy1 > 0):
        shortdate = "{}".format(YYYY)
        return shortdate

    # 010 display only the month
    if ((dd1 <= 0) and (yyyy1 <= 0)) and (mm1 > 0):
        mm1date = "{}".format(mm2)
        return mm1date

    # 100 display only the day
    if ((mm1 <= 0) and (yyyy1 <= 0)) and (dd1 > 0):
        dd1date = "{}".format(dd1)
        return dd1date

    # 011 display only the month and year
    if ((mm1 > 0) and (yyyy1 > 0)) and (dd1 <= 0):
        mm1yyyy1date = "{} {}".format(mm2, YYYY)
        return mm1yyyy1date

    # 110 display only the day and month
    if ((dd1 > 0) and (mm1 > 0)) and (yyyy1 <= 0):
        dd1mm1date = "{} {}".format(dd1, mm2)
        return dd1mm1date

    # 111 If each field has a value return a full date
    if ((dd1 > 0) and (mm1 > 0) and (yyyy1 > 0)):
        fulldate = "{} {} {}".format(DD, mm2, YYYY)
        return fulldate

    return

#------------------------------------------------------------------------
#
# parse_date()
#
#------------------------------------------------------------------------


def parse_date(tmgdate):
    '''Parse TMG date string

    Usage:
    >>>parse_date("119420000051943000000")
    DISPLAY: Between 1942 and 1943
    '''
    datefieldtype = tmgdate[0]
    validdatecodes = ["0", "1"]

    if datefieldtype in validdatecodes:
        if datefieldtype == "1":
            '''Regular date code'''
            regulardate1value2_9 = tmgdate[1:9] # "YYYYMMDD"
            is_oldstyle10 = tmgdate[9] # "0" = No / "1" = Yes
            date2yyold = tmgdate[9:11] # Oldstyle YY
            datemodifier11 = tmgdate[10] # Before/Say/Circa/Exact/After/Between
                                         # Or/From...to
            validdatemodifiercodes = ["0", "1", "2", "3", "4", "5", "6", "7"]
            regulardate2value12_19 = tmgdate[11:19] # "00000000"
            is_eightzeros = None  # rename to empty field or emptydate?
            if regulardate2value12_19 == "00000000":
                is_eightzeros = True
            else:
                is_eightzeros = False
            regulardate3value12_19 = tmgdate[11:19] # "YYYYMMDD"
            is_oldstyledate2nd_20 = tmgdate[19] # "0" = No / "1" = Yes
            has_questionmark21 = tmgdate[20] # "0" = No / "1" = Yes
            questionmark = None
            if has_questionmark21 == "0":
                questionmark = ""
            else:
                questionmark = "?"
            regulardate4value22_30 = tmgdate[21:29] # (reserved)

            if is_oldstyle10 == "0":
                if datemodifier11 in validdatemodifiercodes:
                    if datemodifier11 == "0":
                        #before_date_mod
                        if is_eightzeros:
                            date1 = num_to_date(regulardate1value2_9)
                            return ('Before {}{}'.format(date1, questionmark))
                    elif datemodifier11 == "1":
                        #say_date_mod
                        if is_eightzeros:
                            date1 = num_to_date(regulardate1value2_9)
                            return ('Say {}{}'.format(date1, questionmark))
                    elif datemodifier11 == "2":
                        #circa_date_mod
                        if is_eightzeros:
                            date1 = num_to_date(regulardate1value2_9)
                            return ('Circa {}{}'.format(date1, questionmark))
                    elif datemodifier11 == "3":
                        #exact_date_mod
                        if is_eightzeros:
                            date1 = num_to_date(regulardate1value2_9)
                            return ('{}{}'.format(date1, questionmark))
                    elif datemodifier11 == "4":
                        #after_date_mod
                        if is_eightzeros:
                            date1 = num_to_date(regulardate1value2_9)
                            return ('After {}{}'.format(date1, questionmark))
                    elif datemodifier11 == "5":
                        #between_date_mod
                        date1 = num_to_date(regulardate1value2_9)
                        date2 = num_to_date(regulardate3value12_19)
                        return ('Between {} and {}{}'.format(date1, date2,
                                                             questionmark))
                    elif datemodifier11 == "6":
                        #or_date_mod
                        date1 = num_to_date(regulardate1value2_9)
                        date2 = num_to_date(regulardate3value12_19)
                        return ('{} or {}{}'.format(date1, date2,
                                                    questionmark))
                    elif datemodifier11 == "7":
                        #from_to_date_mod
                        date1 = num_to_date(regulardate1value2_9)
                        date2 = num_to_date(regulardate3value12_19)
                        return ('From {} to {}{}'.format(date1, date2,
                                                         questionmark))
                else:
                    # Invalid issue with database?
                    return tmgdate, "Invalid datemodifier11: ----------{}----------".format(datemodifier11)
            elif is_oldstyle10 == "1":
                date1 = num_to_date(regulardate1value2_9)
                YYold2 = date2yyold
                return ('{}/{}{}'.format(date1, YYold2, questionmark))
        elif datefieldtype == "0":
            '''Irregular date code'''
            irregulardatevalue = tmgdate[1:29]
            return irregulardatevalue
    else:
        # Invalid issue with database?
        return tmgdate, "Invalid datefieldtype: {}--------------------".format(datefieldtype)
