#
# DescendantIndentedTree - a plugin for GRAMPS, the GTK+/GNOME based
#       genealogy program that creates an Ancestor Chart Map based on
#       the D3.js Indented Tree Layout scheme.
#
# Copyright (C) 2014  Matt Keenan <matt.keenan@gmail.com>
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

# version 0.1

# The idea behind this plugin is to create an descendants tree chart that can
# be interacted with via clicking on an individual to either collapse or expand
# descendants for that individual. The chart is SVG using D3.js layout engine.

"""Reports/Web Pages/Descendant Indented Tree"""

#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
from __future__ import unicode_literals
from functools import partial
from gi.repository.Gtk import ResponseType
import copy
import io
import os
import re
import shutil
import string
import sys
import unicodedata

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale, conv_to_unicode
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#------------------------------------------------------------------------
#
# gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.display.name import displayer as global_name_display
from gramps.gen.errors import ReportError
from gramps.gen.lib import ChildRefType
from gramps.gen.plug.menu import (ColorOption, NumberOption, PersonOption,
                                  EnumeratedListOption, DestinationOption,
                                  StringOption, BooleanOption)
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import utils as ReportUtils
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.proxy import LivingProxyDb, PrivateProxyDb
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback,
                                 get_marriage_or_fallback,
                                 get_divorce_or_fallback)
from gramps.gen.utils.file import media_path_full
from gramps.gen.utils.image import resize_to_jpeg
from gramps.gen.config import config
from gramps.gen.datehandler import get_date
from gramps.gen.plug.report import stdoptions
from gramps.gen.sort import Sort
from gramps.gui.dialog import ErrorDialog, QuestionDialog2
from gramps.plugins.lib.libnarrate import Narrator

#------------------------------------------------------------------------
#
# Constants
#
#------------------------------------------------------------------------
_INCLUDE_LIVING_VALUE = 99
EMPTY_ENTRY = "_____________"
MIN_GEN = 0
MAX_GEN = 100
MIN_AGE = -1
MAX_AGE = 100
MIN_FONT = 6
MAX_FONT = 29
MIN_BIO_FONT = 6
MAX_BIO_FONT = 50

#------------------------------------------------------------------------
#
# PrintSimple
#   Simple numbering system
#
#------------------------------------------------------------------------
class PrintSimple():
    def __init__(self, dups):
        self.dups = dups
        self.num = {0:1}

    def number(self, level):
        if self.dups:
            # Just show original simple numbering
            to_return = "%d." % level
        else:
            to_return = str(level)
            if level > 1:
                to_return += "-" + str(self.num[level-1])
            to_return += "."

            self.num[level] = 1
            self.num[level-1] = self.num[level-1] + 1

        return to_return
    
    
#------------------------------------------------------------------------
#
# PrintVlliers
#   de_Villiers_Pama numbering system
#
#------------------------------------------------------------------------
class PrintVilliers():
    def __init__(self):
        self.pama = 'abcdefghijklmnopqrstuvwxyz'
        self.num = {0:1}
    
    def number(self, level):
        to_return = self.pama[level-1]
        if level > 1:
            to_return += str(self.num[level-1])
        to_return += "."
        
        self.num[level] = 1
        self.num[level-1] = self.num[level-1] + 1

        return to_return
    

#------------------------------------------------------------------------
#
# PrintdAboville
#   d'Aboville numbering system
#
#------------------------------------------------------------------------
class PrintdAboville():
    def __init__(self):
        self.num = {0:1}
    
    def number(self, level):
        to_return = "1"
        if level > 1:
            i = 1
            while level > (i+1):
                to_return += "." + str(self.num[i]-1)
                i += 1
            to_return += "." + str(self.num[i])
        self.num[level] = 1
        self.num[level-1] = self.num[level-1] + 1

        return to_return
    

#------------------------------------------------------------------------
#
# PrintHenry
#   Henry numbering system
#
#------------------------------------------------------------------------
class PrintHenry():
    def __init__(self):
        self.num = {0:1}
    
    def number(self, level):
        to_return = "1"
        if level > 1:
            i = 1
            while level > (i+1):
                to_return += str(self.num[i]-1)
                i += 1
            to_return += str(self.num[i])
        self.num[level] = 1
        self.num[level-1] = self.num[level-1] + 1

        return to_return
    
#------------------------------------------------------------------------
#
# PrintRecord
#   Record-style (Modified Register) numbering system
#
#------------------------------------------------------------------------
class PrintRecord():
    def __init__(self):
        self.num = 0

    def reset(self):
        self.num = 0
    
    def number(self, level):
        self.num += 1
        return str(self.num)
    
#------------------------------------------------------------------------
#
# PrintMeurgey
#   Meurgey_de_Tupigny numbering system
#
#------------------------------------------------------------------------
class PrintMeurgey():
    def __init__(self):
        self.childnum = [""]
    
    def number(self, level):
        if level == 1:
            dash = ""
        else:
            dash = "-"
            if len(self.childnum) < level:
                self.childnum.append(1)
        
        to_return = (ReportUtils.roman(level) + dash +
                     str(self.childnum[level-1]) + ".")

        if level > 1:
            self.childnum[level-1] += 1
        
        return to_return

#------------------------------------------------------------------------
#
# Printinfo
#
#------------------------------------------------------------------------
class Printinfo():
    """
    A base class used to help make the individual numbering system classes.
    This class must first be initialized with set_class_vars
    """
    def __init__(self, database, numbering, showmarriage, showdivorce,\
                 name_display, showbio, dest_path, use_call, use_fulldate,
                 compute_age, verbose, inc_photo, rep_place, rep_date, locale,
                 hrefs, href_prefix, href_ext, href_delim, href_gen,
                 href_age, href_excl_spouse, href_excl_center, center_person):
        #classes
        self._name_display = name_display
        self.database = database
        self.numbering = numbering
        #variables
        self.showmarriage = showmarriage
        self.showdivorce = showdivorce
        self.showbio = showbio
        self.dest_path = dest_path
        self.use_call = use_call
        self.use_fulldate = use_fulldate
        self.compute_age = compute_age
        self.verbose = verbose
        self.inc_photo = inc_photo
        self.json_fp = None
        self.dest_prefix = None
        self.hrefs = hrefs
        self.href_prefix = href_prefix
        self.href_ext = href_ext
        self.href_delim = href_delim
        self.href_gen = href_gen
        self.href_age = href_age
        self.href_excl_spouse = href_excl_spouse
        self.href_excl_center = href_excl_center
        self.center_person = center_person
 
        # List of unique HREF's
        self.href_dict = {}

        if rep_date:
            empty_date = EMPTY_ENTRY
        else:
            empty_date = ""

        if rep_place:
            empty_place = EMPTY_ENTRY
        else:
            empty_place = ""

        self.narrator = Narrator(self.database,
                                 self.verbose,
                                 self.use_call,
                                 self.use_fulldate,
                                 empty_date,
                                 empty_place,
                                 nlocale=locale,
                                 get_endnote_numbers=self.endnotes)

    def endnotes(self, obj):
        # dummy endnote method
        return ""

    def set_dest_prefix(self, dest_prefix):
        self.dest_prefix = dest_prefix

    def set_json_fp(self, json_fp):
        self.json_fp = json_fp

    def get_date_place(self,event):
        if event:
            date = get_date(event)
            place_handle = event.get_place_handle()
            if place_handle:
                place = self.database.get_place_from_handle(
                    place_handle).get_title()
                
                return("%(event_abbrev)s %(date)s %(place)s" % {
                    'event_abbrev': event.type.get_abbreviation(),
                    'date' : date,
                    'place' : place,
                    })
            else:
                return("%(event_abbrev)s %(date)s" % {
                    'event_abbrev': event.type.get_abbreviation(),
                    'date' : date
                    })
        return ""

    def dump_biography(self, person, level):
        gen_pad = (level-1) * 2

        # Person ID will be used for image reference to person image
        if self.inc_photo:
            media_list = person.get_media_list()
            if len(media_list) > 0:
                photo = media_list[0]

                object_handle = photo.get_reference_handle()
                media_object = self.database.get_object_from_handle(
                    object_handle)
                mime_type = media_object.get_mime_type()
                if mime_type and mime_type.startswith("image"):
                    filename = media_path_full(self.database,
                                               media_object.get_path())
                    if os.path.exists(filename):
                        image_path = os.path.join(self.dest_path, "images",
                                                  self.dest_prefix)
                        image_ref = os.path.join("images",
                                                 self.dest_prefix,
                                                 person.gramps_id + ".jpg")
                        image_file = os.path.join(self.dest_path, "images",
                                                  self.dest_prefix,
                                                  person.gramps_id + ".jpg")
                        self.json_fp.write('%s"image_ref": "%s",\n' %
                            (self.pad_str(gen_pad+1), str(image_ref)))
                        # Copy media file to images directory
                        # Ensure image directory exists:
                        if not os.path.exists(image_path):
                            os.mkdir(image_path)

                        # resize image to a maz 3x3cm jpg
                        size = int(max(3.0, 3.0) * float(150.0/2.54))
                        resize_to_jpeg(filename, image_file, size, size, None)
                             
        # Build up biography string, similar to that of detailed descendant
        # report including, born, baptized, christened, died, buried, and
        # married.
        self.narrator.set_subject(person)
        bio_str = ""
        if not self.verbose:
            text = self.get_parents_string(person)
            if text:
                bio_str = bio_str + text.replace('"', "'")

        text = self.narrator.get_born_string()
        if text:
            bio_str = bio_str + text.replace('"', "'")

        text = self.narrator.get_baptised_string()
        if text:
            bio_str = bio_str + text.replace('"', "'")

        text = self.narrator.get_christened_string()
        if text:
            bio_str = bio_str + text.replace('"', "'")

        text = self.narrator.get_died_string(self.compute_age)
        if text:
            bio_str = bio_str + text.replace('"', "'")

        text = self.narrator.get_buried_string()
        if text:
            bio_str = bio_str + text.replace('"', "'")

        if self.verbose:
            text = self.get_parents_string(person)
            if text:
                bio_str = bio_str + text.replace('"', "'")

        text = self.get_marriage_string(person)
        if text:
            bio_str = bio_str + text.replace('"', "'")

        self.json_fp.write('%s"biography": "%s",\n' %
            (self.pad_str(gen_pad+1), str(bio_str)))

    def get_marriage_string(self, person):
        is_first = True
        mar_string = ""
        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            spouse_handle = ReportUtils.find_spouse(person, family)
            spouse = self.database.get_person_from_handle(spouse_handle)
            if spouse:
                name = self._name_display.display_formal(spouse)
            else:
                name = ""
            text = ""
            text = self.narrator.get_married_string(family, is_first,
                                                      self._name_display)
            if text:
                mar_string = mar_string + text
        return mar_string

    def get_parents_string(self, person):
        family_handle = person.get_main_parents_family_handle()
        text = None
        if family_handle:
            family = self.database.get_family_from_handle(family_handle)
            mother_handle = family.get_mother_handle()
            father_handle = family.get_father_handle()
            if mother_handle:
                mother = self.database.get_person_from_handle(mother_handle)
                mother_name = \
                    self._name_display.display_name(mother.get_primary_name())
            else:
                mother_name = ""
            if father_handle:
                father = self.database.get_person_from_handle(father_handle)
                father_name = \
                    self._name_display.display_name(father.get_primary_name())
            else:
                father_name = ""

            text = self.narrator.get_child_string(father_name, mother_name)
        return text

    def dump_string(self, person, level, family=None):
        gen_pad = (level-1) * 2

        born = self.get_date_place(get_birth_or_fallback(self.database, person))
        died = self.get_date_place(get_death_or_fallback(self.database, person))

        self.json_fp.write('%s"born": "%s",\n' %
            (self.pad_str(gen_pad+1), str(born)))
        self.json_fp.write('%s"died": "%s",\n' %
            (self.pad_str(gen_pad+1), str(died)))

        if family and self.showmarriage:
            marriage = self.get_date_place(
                get_marriage_or_fallback(self.database,
                                                              family))
            self.json_fp.write('%s"marriage": "%s",\n' %
                (self.pad_str(gen_pad+1), str(marriage)))
            
        if family and self.showdivorce:
            divorce = self.get_date_place(
                get_divorce_or_fallback(self.database, family))
            self.json_fp.write('%s"divorce": "%s",\n' %
                (self.pad_str(gen_pad+1), str(divorce)))

        # Only write out buigraphy information if showing of tooltips selected
        if self.showbio:
            self.dump_biography(person, level)

        self.json_fp.write('%s"gender": "%s"' %
            (self.pad_str(gen_pad+1), self.get_gender_str(person)))

    def pad_str(self, num_spaces):
        """
        Utility method to retrieve string with specific number of spaces
        """
        pad_str = ""
        for i in range(0, num_spaces):
            pad_str = pad_str + " "
        return pad_str

    def get_gender_str(self, person):
        """
        Return gender string of male/female/unknown
        """
        if person.get_gender() == 0:
            return "female"
        elif person.get_gender() == 1:
            return "male"
        else:
            return "unknown"

    def generate_href(self, person, level, spouse=False):
        """
        Wheter or not to generate a href link for this person
        """
        generate = False

        # General option to generate hrefs
        if self.hrefs:
            generate = True

            # Generation is less than/equal to specified generations
            if level > self.href_gen:
                generate = False

            # Exclude center person
            if self.href_excl_center and self.center_person == person:
                generate = False

            # Exclude spouses
            if spouse and self.href_excl_spouse:
                generate = False

            # Exclude people dying before specified age, Age < 0, don't exclude
            if self.href_age > 0:
                death_age = self.get_age_at_death(person)
                if death_age != -1 and death_age < self.href_age:
                    generate = False

        return generate

    def get_age_at_death(self, person):
        """
        Get estimated age at death, return -1 if alive or not determinable
        """
        if person is not None:
            birth_event = get_birth_or_fallback(self.database, person)

            if birth_event:
                birth = birth_event.get_date_object()
                birth_year_valid = birth.get_year_valid()
            else:
                birth_year_valid = False

            death_event = get_death_or_fallback(self.database, person)
            if death_event:
                death = death_event.get_date_object()
                death_year_valid = death.get_year_valid()
            else:
                death_year_valid = False
        else:
            birth_year_valid = False
            death_year_valid = False

        death_age = -1
        if birth_year_valid and death_year_valid:
            span = death - birth
            if span and span.is_valid():
                if span:
                    death_age = span.tuple()[0]
                else:
                    death_age = -1
            else:
                death_age = -1
        return death_age

    def generate_href_link(self, name):
        """
        Generate HREF link for person
        <a href='http://href_prefix/name/href_ext'>name</a>
        """
        # HREF ultimately a link to a real file, need to ensure it only
        # contains valid filename characters across all OS
        valid_filename_chars = \
            "-_.() %s%s" % (string.ascii_letters, string.digits)

        if self.href_delim == "None":
            delim = ""
        elif self.href_delim == "Dash":
            delim = "-"
        else:
            delim = "_"

        name_str = name.replace(" ", delim).lower()
        name_out = unicodedata.normalize('NFKD',
            conv_to_unicode(name_str)).encode('ascii', 'ignore')
        name_out = ''.join(c for c in conv_to_unicode(name_out) \
            if c in valid_filename_chars)

        # Ensure HREF does not already exist
        if name_out in self.href_dict:
            self.href_dict[name_out] = self.href_dict[name_out] + 1
            name_out = conv_to_unicode(name_out) + delim + \
                str(self.href_dict[name_out])
            self.href_dict[name_out] = 1
        else:
            self.href_dict[name_out] = 1
            name_out = conv_to_unicode(name_out) + delim + \
                str(self.href_dict[name_out])
            self.href_dict[name_out] = 1

        if self.href_prefix:
            href = "%s/%s" % \
                (self.href_prefix.rstrip("/"), str(name_out))
        else:
            href = "%s" % (str(name_out))

        if self.href_ext != "None":
            href = "%s.%s" % (re.sub(self.href_ext+"$", "", href),
                              self.href_ext)
        return href

    def print_person(self, level, person):
        display_num = self.numbering.number(level)
        name = self._name_display.display(person)
        gen_pad = (level-1) * 2

        self.json_fp.write('%s"display_num": "%s",\n' %
            (self.pad_str(gen_pad+1), str(display_num)))
        self.json_fp.write('%s"name": "%s",\n' %
            (self.pad_str(gen_pad+1), name.replace('"', "'")))
        if self.generate_href(person, level):
            self.json_fp.write('%s"href": "%s",\n' %
                (self.pad_str(gen_pad+1),
                 self.generate_href_link(name.replace('"', "'"))))
        self.json_fp.write('%s"spouse": "%s",\n' %
            (self.pad_str(gen_pad+1), "false"))
        self.dump_string(person, level)
        return display_num
    
    def print_spouse(self, level, spouse_handle, family_handle):
        #Currently print_spouses is the same for all numbering systems.
        gen_pad = (level-1) * 2

        if spouse_handle:
            spouse = self.database.get_person_from_handle(spouse_handle)
            name = self._name_display.display(spouse)

            self.json_fp.write('%s"display_num": "%s",\n' %
                (self.pad_str(gen_pad+1), "sp."))
            self.json_fp.write('%s"name": "%s",\n' %
                (self.pad_str(gen_pad+1), name.replace('"', "'")))
            if self.generate_href(spouse, level, spouse=True):
                self.json_fp.write('%s"href": "%s",\n' %
                    (self.pad_str(gen_pad+1),
                    self.generate_href_link(name.replace('"', "'"))))
            self.json_fp.write('%s"spouse": "%s",\n' %
                (self.pad_str(gen_pad+1), "true"))
            self.dump_string(spouse, level, family_handle)
        else:
            name = "Unknown"
            self.json_fp.write('%s"display_num": "%s",\n' %
                (self.pad_str(gen_pad+1), "sp."))
            self.json_fp.write('%s"name": "%s",\n' %
                (self.pad_str(gen_pad+1), name.replace('"', "'")))
            if self.generate_href(None, level, spouse=True):
                self.json_fp.write('%s"href": "%s",\n' %
                    (self.pad_str(gen_pad+1),
                    self.generate_href_link(name.replace('"', "'"))))
            self.json_fp.write('%s"spouse": "%s"\n' %
                (self.pad_str(gen_pad+1), "true"))

    def print_reference(self, level, person, display_num):
        #Person and their family have already been printed so
        #print reference here
        if person:
            gen_pad = (level-1) * 2
            sp_name = self._name_display.display(person)
            name = _("See %(reference)s : %(spouse)s" %
                    {'reference': display_num, 'spouse': sp_name})
            self.json_fp.write('%s{\n' % (self.pad_str(gen_pad)))
            self.json_fp.write('%s"display_num": "%s",\n' %
                (self.pad_str(gen_pad+1), "sp."))
            self.json_fp.write('%s"name": "%s",\n' %
                (self.pad_str(gen_pad+1), name.replace('"', "'")))
            self.json_fp.write('%s"spouse": "%s"\n' %
                (self.pad_str(gen_pad+1), "true"))

#------------------------------------------------------------------------
#
# RecurseDown
#
#------------------------------------------------------------------------
class RecurseDown():
    """
    A simple object to recurse from a person down through their descendants
    
    The arguments are:
    
    max_generations: The max number of generations
    database:  The database object
    objPrint:  A Printinfo derived class that prints person
               information on the report
    """
    def __init__(self, max_generations, database, objPrint, dups, marrs, divs,
                 user, title, numbering):
        self.max_generations = max_generations
        self.database = database
        self.objPrint = objPrint
        self.dups = dups
        self.marrs = marrs
        self.divs = divs
        self.user = user
        self.title = title
        self.numbering = numbering
        self.person_printed = {}
        self.person_counted = {}
        self.person_count = 0

    def pad_str(self, num_spaces):
        """
        Utility method to retrieve string with specific number of spaces
        """
        pad_str = ""
        for i in range(0, num_spaces):
            pad_str = pad_str + " "
        return pad_str

    def recurse_count(self, level, person, curdepth):
        self.person_count = self.person_count + 1
        display_num = self.numbering.number(level)
        if curdepth is None:
            ref_str = display_num
        else:
            ref_str = curdepth + " " + display_num
    
        family_num = 0
        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            family_num += 1

            spouse_handle = ReportUtils.find_spouse(person, family)

            if not self.dups and spouse_handle in self.person_counted:
                # Just print a reference
                continue
            else:
                self.person_count = self.person_count + 1
                if spouse_handle:
                    spouse_num = _("%s sp." % (ref_str))
                    self.person_counted[spouse_handle] = spouse_num

                if level >= self.max_generations:
                    continue

                childlist = family.get_child_ref_list()[:]
                first_child = True
                for child_ref in childlist:
                    child = self.database.get_person_from_handle(child_ref.ref)
                    self.recurse_count(level+1, child, ref_str)

    def recurse(self, level, person, curdepth):
        gen_pad = (level-1) * 2
        person_handle = person.get_handle()
        self.objPrint.json_fp.write('%s{\n' % (self.pad_str(gen_pad)))
        display_num = self.objPrint.print_person(level, person)
        if level == 1:
            if self.person_count == 0:
                self.person_count = 100
            self.user.begin_progress(self.title, _("Generating report..."),
                                     self.person_count)
        else:
            self.user.step_progress()

        if curdepth is None:
            ref_str = display_num
        else:
            ref_str = curdepth + " " + display_num

        if person_handle not in self.person_printed:
            self.person_printed[person_handle] = ref_str

        if len(person.get_family_handle_list()) > 0:
            self.objPrint.json_fp.write(',\n%s"children": [\n' %
                (self.pad_str(gen_pad)))

        family_num = 0
        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            family_num += 1

            spouse_handle = ReportUtils.find_spouse(person, family)

            if not self.dups and spouse_handle in self.person_printed:
                # Just print a reference
                spouse = self.database.get_person_from_handle(spouse_handle)
                if family_num > 1:
                    self.objPrint.json_fp.write(',%s{\n' %
                        (self.pad_str(gen_pad)))
                else:
                    self.objPrint.json_fp.write('%s{\n' %
                        (self.pad_str(gen_pad)))
                self.objPrint.print_reference(level, spouse,
                    self.person_printed[spouse_handle])
                self.objPrint.json_fp.write('%s}\n' % (self.pad_str(gen_pad)))
            else:
                if family_num > 1:
                    self.objPrint.json_fp.write(',%s{\n' %
                        (self.pad_str(gen_pad)))
                else:
                    self.objPrint.json_fp.write('%s{\n' %
                        (self.pad_str(gen_pad)))
                self.objPrint.print_spouse(level, spouse_handle, family)
                self.user.step_progress()

                if spouse_handle:
                    spouse_num = _("%s sp." % (ref_str))
                    self.person_printed[spouse_handle] = spouse_num

                if level >= self.max_generations:
                    self.objPrint.json_fp.write('%s}\n' %
                        (self.pad_str(gen_pad)))
                    continue

                childlist = family.get_child_ref_list()[:]
                first_child = True
                for child_ref in childlist:
                    if first_child:
                        first_child = False
                        self.objPrint.json_fp.write(',\n%s"children": [\n' %
                            (self.pad_str(gen_pad+1)))
                    else:
                        self.objPrint.json_fp.write(',')
                    child = self.database.get_person_from_handle(child_ref.ref)
                    self.recurse(level+1, child, ref_str)

                if not first_child:
                    self.objPrint.json_fp.write('\n%s]\n' %
                        (self.pad_str(gen_pad+1)))

                self.objPrint.json_fp.write('%s}\n' % (self.pad_str(gen_pad)))

        if len(person.get_family_handle_list()) > 0:
            self.objPrint.json_fp.write('%s]\n%s}\n' %
                (self.pad_str(gen_pad), self.pad_str(gen_pad)))
        else:
            self.objPrint.json_fp.write('\n%s}\n' % (self.pad_str(gen_pad)))

        if level == 1:
            self.user.end_progress()

#------------------------------------------------------------------------
#
# DescendantIndentedTreeReport
#
#------------------------------------------------------------------------
class DescendantIndentedTreeReport(Report):
    """
    Descendant Indented Tree Report class
    """
    def __init__(self, database, options, user):
        """
        Create the Descendant Indented Tree object that produces the
        Descendant Indented Tree report.

        The arguments are:

        database        - the GRAMPS database instance
        options         - instance of the Options class for this report
        user            - a gen.user.User() instance

        This report needs the following parameters (class variables)
        that come in the options class.

        max_gen       - Maximum number of generations to include.
        contraction   - Initial contraction level
        font_size     - Font size in pixels for nodes
        name_format   - Preferred format to display names
        numbering     - numbering system to use
        dups          - Whether to include duplicate descendant trees
        arrows        - How to expand/contract nodes
        showbio       - Show biography tooltips
        marrs         - Whether to include Marriage Info
        divs          - Whether to include Divorce Info
        dest_path     - Destination Path
        dest_file     - Destination HTML filename
        parent_bg     - Background color for expanded rows
        more_bg       - Background color expandable rows
        no_more_bg    - Background color non-expandable rows
        use_call      - Whether to use the call name as the first name.
        rep_place     - Whether to replace missing Places with ___________.
        rep_date      - Whether to replace missing Dates with ___________.
        compute_age   - Whether to compute age.
        use_fulldates - Whether to use full dates instead of just year.
        inc_photo     - Whether to include images.
        verbose       - Whether to use complete sentences.
        hrefs         - Whether to auto-generate node HREF links
        href_prefix   - URL Prefix for auto-generated HREF links
        href_ext      - URL file extension for auto-generated HREF links
        href_delim    - Delimeter to use when replacing white space
        href_gen      - Generations to generate HREF links
        href_age      - Exclude HREFs for people who died before age
        href_excl_spouse - Exclude HREFs generation for spouses
        href_excl_center - Exclude HREFs generation for center person
        inc_living    - How to deal with living people
        dead_years    - Years to determine if recently passed or not
        """
        Report.__init__(self, database, options, user)

        self.map = {}

        menu = options.menu
        self.database = database
        self.user = user
        self.title = _('Descendant Indented Tree')

        pid = menu.get_option_by_name('pid').get_value()
        self.center_person = self.database.get_person_from_gramps_id(pid)
        if (self.center_person == None) :
            raise ReportError(_("Person %s is not in the Database") % pid )

        self.inc_private = menu.get_option_by_name('inc_private').get_value()
        self.inc_living = menu.get_option_by_name('inc_living').get_value()
        self.dead_years = menu.get_option_by_name('dead_years').get_value()

        if not self.inc_private:
            self.database = PrivateProxyDb(database)

        if self.inc_living != _INCLUDE_LIVING_VALUE:
            self.database = LivingProxyDb(self.database, self.inc_living,
                                          None, self.dead_years)
        self.max_gen = menu.get_option_by_name('max_gen').get_value()
        self.contraction = menu.get_option_by_name('contraction').get_value()
        self.font_size = menu.get_option_by_name('font_size').get_value()
        self.parent_bg = menu.get_option_by_name('parent_bg').get_value()
        self.more_bg = menu.get_option_by_name('more_bg').get_value()
        self.no_more_bg = menu.get_option_by_name('no_more_bg').get_value()
        self.dest_path = conv_to_unicode(
            menu.get_option_by_name('dest_path').get_value(), 'utf8')
        self.dest_file = conv_to_unicode(
            menu.get_option_by_name('dest_file').get_value(), 'utf8')
        self.destprefix, self.destext = \
            os.path.splitext(os.path.basename(self.dest_file))
        self.destcss = conv_to_unicode(os.path.join(
            self.dest_path, "css", "indentedtree-%s.css" % (self.destprefix)))
        self.destjson = conv_to_unicode(os.path.join(
            self.dest_path, "json", "indentedtree-%s.json" % (self.destprefix)))
        self.destjs = conv_to_unicode(os.path.join(
            self.dest_path, "js", "indentedtree-%s.js" % (self.destprefix)))
        self.destexpandedjs = conv_to_unicode(os.path.join(
            self.dest_path, "js", "indentedtree-%s-expanded.js" %
            (self.destprefix)))
        self.desthtml = conv_to_unicode(
            os.path.join(self.dest_path, os.path.basename(self.dest_file)))
        self.arrows = menu.get_option_by_name('arrows').get_value()
        self.showbio = menu.get_option_by_name('showbio').get_value()
        self.barheight = int(self.font_size) * 2
        self.dy = round((self.barheight * 0.175), 1)

        sort = Sort(self.database)
        self.by_birthdate = sort.by_birthdate_key
    
        #Initialize the Printinfo class    
        self.dups = menu.get_option_by_name('dups').get_value()
        self.numbering = menu.get_option_by_name('numbering').get_value()
        if self.numbering == "Simple":
            self.num_obj = PrintSimple(self.dups)
        elif self.numbering == "d'Aboville":
            self.num_obj = PrintdAboville()
        elif self.numbering == "de Villiers/Pama":
            self.num_obj = PrintVilliers()
        elif self.numbering == "Henry":
            self.num_obj = PrintHenry()
        elif self.numbering == "Meurgey de Tupigny":
            self.num_obj = PrintMeurgey()
        elif self.numbering == "Record":
            self.num_obj = PrintRecord()
        else:
            raise AttributeError("no such numbering: '%s'" % self.numbering)

        self.marrs = menu.get_option_by_name('marrs').get_value()
        self.divs = menu.get_option_by_name('divs').get_value()
        self.hrefs = menu.get_option_by_name('hrefs').get_value()
        self.href_prefix = menu.get_option_by_name('href_prefix').get_value()
        self.href_ext = menu.get_option_by_name('href_ext').get_value()
        self.href_delim = menu.get_option_by_name('href_delim').get_value()
        self.href_gen = menu.get_option_by_name('href_gen').get_value()
        self.href_age = menu.get_option_by_name('href_age').get_value()
        self.href_excl_spouse = \
            menu.get_option_by_name('href_excl_spouse').get_value()
        self.href_excl_center = \
            menu.get_option_by_name('href_excl_center').get_value()

        if self.arrows == "None":
            self.hrefs = False

        # Biography contents options
        self.use_call = menu.get_option_by_name('use_call').get_value()
        self.use_fulldates = \
            menu.get_option_by_name('use_fulldates').get_value()
        self.compute_age = menu.get_option_by_name('compute_age').get_value()
        self.inc_photo = menu.get_option_by_name('inc_photo').get_value()
        self.verbose = menu.get_option_by_name('verbose').get_value()
        self.rep_place = menu.get_option_by_name('rep_place').get_value()
        self.rep_date = menu.get_option_by_name('rep_date').get_value()
        self.bio_bg = menu.get_option_by_name('bio_bg').get_value()
        self.bio_text = menu.get_option_by_name('bio_text').get_value()
        self.bio_header_font_size = \
            menu.get_option_by_name('bio_header_font_size').get_value()
        self.bio_body_font_size = \
            menu.get_option_by_name('bio_body_font_size').get_value()

        # Copy the global NameDisplay so that we don't change application
        # defaults.
        self._name_display = copy.deepcopy(global_name_display)
        name_format = menu.get_option_by_name("name_format").get_value()
        if name_format != 0:
            self._name_display.set_default_format(name_format)

        self.trans = menu.get_option_by_name('trans').get_value()
        self._locale = self.set_locale(self.trans)
        self.objPrint = Printinfo(self.database, self.num_obj, self.marrs,
                                  self.divs, self._name_display, self.showbio,
                                  self.dest_path, self.use_call,
                                  self.use_fulldates, self.compute_age,
                                  self.verbose, self.inc_photo,
                                  self.rep_place, self.rep_date, self._locale,
                                  self.hrefs, self.href_prefix, self.href_ext,
                                  self.href_delim, self.href_gen,
                                  self.href_age, self.href_excl_spouse,
                                  self.href_excl_center, self.center_person)

    def write_js(self, filename, contraction):
        """
        Convenience method to write js file with different contraction levels
        """
        with io.open(filename, 'w', encoding='utf8') as fp:
            fp.write('var margin = {top: 30, right: 20, bottom: '
                     '30, left: 20},\n')
            fp.write(' width = 1024 - margin.left - '
                     'margin.right,\n')
            if self.arrows != "None":
                fp.write(' textMargin = 20,\n')
            else:
                fp.write(' textMargin = 5.5,\n')
            fp.write(' barHeight = %s,\n' % (str(self.barheight)))
            fp.write(' i = 0,\n')
            fp.write(' duration = 400,\n')
            fp.write(' contraction = %s,\n' % (contraction))
            fp.write(' root;\n\n')
            fp.write('var tree = d3.layout.tree().'
                     'nodeSize([0, 20]);\n\n')
            fp.write('var diagonal = d3.svg.diagonal().'
                     'projection(function(d) {\n')
            fp.write(' return [d.y, d.x];\n')
            fp.write('});\n\n')
            fp.write('var maxWidth = width;\n\n')
            fp.write('var svg = d3.select("div.div_svg").'
                     'append("svg")\n')
            fp.write(' .attr("width", width + margin.left + '
                     'margin.right).append("g")\n')
            fp.write(' .attr("transform", "translate(" + '
                     'margin.left + "," + margin.top + ")");\n\n')

            fp.write('var calc_div = d3.select("div.calc_svg");\n')
            fp.write('var svg1 = d3.select("div.calc_svg").append("svg")\n')
            fp.write(' .attr("width", width + margin.left + '
                     'margin.right)\n')
            fp.write(' .append("g").attr("class", "node_test");\n\n')

            fp.write('d3.json("json/indentedtree-%s.json", ' %
                     (self.destprefix))
            fp.write('function(error, descendant) {\n')
            fp.write(' descendant.x0 = 0;\n')
            fp.write(' descendant.y0 = 0; \n')
            fp.write(' calc_max_width(root = descendant);\n')
            fp.write(' if (width < maxWidth) {\n')
            fp.write('  width = maxWidth;\n')
            fp.write('  d3.select("div.div_svg").select("svg").attr("width", '
                     'width + margin.left + margin.right);\n')
            fp.write(' }\n')
            fp.write('});\n\n')

            fp.write('function calc_max_width(source) {\n')
            fp.write(' var nodes = tree.nodes(root);\n')
            fp.write(' var node = svg1.selectAll("g.node_test")\n')
            fp.write('  .data(nodes)\n')
            fp.write('  .enter()\n')
            fp.write('  .append("text")\n')
            fp.write('  .text(set_text)\n')
            fp.write('  .each(function(d) {\n')
            fp.write('    wid = this.getBBox().width;\n')
            fp.write('    newmax = (wid + d.y + margin.right + '
                     'margin.left);\n')
            fp.write('    if (maxWidth < newmax) {\n')
            fp.write('     maxWidth = newmax;\n')
            fp.write('    }\n')
            fp.write('  });\n')
            fp.write(' calc_div.select("svg").remove();\n')
            fp.write('}\n\n')

            if self.showbio:
                fp.write('var tip = d3.tip()\n')
                fp.write(' .attr("class", "d3-tip")\n')
                fp.write(' .style("background", "%s")\n' % (self.bio_bg))
                fp.write(' .style("color", "%s")\n' % (self.bio_text))
                fp.write(' .offset([-10, 0])\n')
                fp.write(' .html(function(d) {\n')
                fp.write('  return set_biography_text(d);\n')
                fp.write(' });\n\n')
                fp.write('svg.call(tip);\n\n')

            out_str='d3.json("json/indentedtree-%s.json", ' % (self.destprefix)
            fp.write(out_str + 'function(error, descendant) {\n')
            fp.write(' descendant.x0 = 0;\n')
            fp.write(' descendant.y0 = 0;\n')
            fp.write(' set_initial_contraction(root = descendant);\n')
            fp.write(' update(root = descendant);\n')
            fp.write('});\n\n')
            fp.write('function set_initial_contraction(source) {\n')
            fp.write(' var nodes = tree.nodes(root);\n')
            fp.write(' nodes.forEach(function(n, i) {\n')
            fp.write('  if (n.depth >= (contraction-1) && n.children) {\n')
            fp.write('   n._children = n.children;\n')
            fp.write('   n.children = null;\n')
            fp.write('  }\n')
            fp.write(' });\n')
            fp.write('}\n\n')
            fp.write('function update(source) {\n')
            fp.write(' // Compute the flattened node list. '
                     'TODO use d3.layout.hierarchy.\n')
            fp.write(' var nodes = tree.nodes(root);\n')
            fp.write(' var height = Math.max(500, nodes.length *'
                     ' barHeight +\n')
            fp.write('  margin.top + margin.bottom);\n\n')
            fp.write(' d3.select("svg").transition().'
                     'duration(duration).attr("height", height);\n\n')
            fp.write(' d3.select(self.frameElement).'
                     'transition().duration(duration)\n')
            fp.write('  .style("height", height + "px");\n\n')
            fp.write(' // Compute the "layout".\n')
            fp.write(' nodes.forEach(function(n, i) {\n')
            fp.write('  // Set X Co-ordinate for each node\n')
            fp.write('  n.x = i * barHeight;\n')
            fp.write(' });\n\n')
            fp.write(' // Update the nodes\n')
            fp.write(' var node = svg.selectAll("g.node")\n')
            fp.write('  .data(nodes, function(d) { return '
                     'd.id || (d.id = ++i); });\n\n')
            fp.write(' var nodeEnter = node.enter().'
                     'append("g")\n')
            fp.write('  .attr("class", "node")\n')
            fp.write('  .attr("transform", function(d) {\n')
            fp.write('    return "translate(" + source.y0 + '
                     '"," + source.x0 + ")";\n')
            fp.write('   })\n')
            fp.write('  .style("opacity", 1e-6);\n\n')
            fp.write(' // Enter any new nodes at the parents '
                     'previous position.\n')
            fp.write(' nodeEnter.append("rect")\n')
            fp.write('  .attr("y", -barHeight / 2)\n')
            fp.write('  .attr("height", barHeight)\n')
            fp.write('  .attr("width", function(n) { return '
                     'maxWidth - n.y;})\n')

            if self.showbio:
                if not self.arrows != "None":
                    fp.write('  .attr("cursor", "pointer")\n')
                    fp.write('  .on("click", click)\n')
                else:
                    fp.write('  .attr("cursor", "default")\n')
                fp.write('  .on("mouseover", tip.show)\n')
                fp.write('  .on("mousemove", function(d) {\n')
                fp.write('   tip.style("top", (d3.event.pageY-10)+"px")\n')
                fp.write('   tip.style("left", '
                         '(d3.event.pageX+10)+"px");})\n')
                fp.write('  .on("mouseout", tip.hide)\n')
            else:
                if not self.arrows != "None":
                    fp.write('  .attr("cursor", "pointer")\n')
                    fp.write('  .on("click", click)\n')
                else:
                    fp.write('  .attr("cursor", "default")\n')

            fp.write('  .style("fill", color);\n\n')

            if self.arrows != "None":
                fp.write(' nodeEnter.append("image")\n')
                fp.write('  .on("click", click)\n')
                fp.write('  .attr("cursor", "pointer")\n')
                fp.write('  .attr("xlink:href", set_arrow)\n')
                fp.write('  .attr("height", 22)\n')
                fp.write('  .attr("width", 20)\n')
                fp.write('  .attr("y", -11)\n')
                fp.write('  .attr("x", 0);\n\n')

            if self.hrefs:
                fp.write(' nodeEnter.filter(function(d) {\n')
                fp.write('   if (d.href) {\n')
                fp.write('    return true;\n')
                fp.write('   } else {\n')
                fp.write('    return false;\n')
                fp.write('   }\n')
                fp.write('  }).append("a")\n')
                fp.write('  .attr({"xlink:href": ')
                fp.write('function(d) { return d.href;}})\n')
                fp.write('  .attr("class", "node_anchor")\n')
                fp.write('  .append("text")\n')
                fp.write('  .attr("dy", 3.5)\n')
                fp.write('  .attr("dx", textMargin)\n')
                fp.write('  .style("pointer-events", "auto")\n')
                fp.write('  .text(set_text);\n\n')

                fp.write(' nodeEnter.filter(function(d) {\n')
                fp.write('   if (d.href) {\n')
                fp.write('    return false;\n')
                fp.write('   } else {\n')
                fp.write('    return true;\n')
                fp.write('   }\n')
                fp.write('  })\n')
                fp.write('  .append("text")\n')
                fp.write('  .attr("dy", 3.5)\n')
                fp.write('  .attr("dx", textMargin)\n')
                fp.write('  .style("pointer-events", "none")\n')
                fp.write('  .style("fill", "black")\n')
                fp.write('  .text(set_text);\n\n')
            else:
                fp.write(' nodeEnter.append("text")\n')
                fp.write('  .attr("dy", 3.5)\n')
                fp.write('  .attr("dx", textMargin)\n')
                fp.write('  .text(set_text);\n\n')

            fp.write(' // Transition nodes to their new '
                     'position.\n')
            if self.arrows != "None":
                fp.write(' node.transition()\n')
                fp.write('  .select("image")\n')
                fp.write('  .attr("xlink:href", set_arrow);\n\n')
            fp.write(' node.transition()\n')
            fp.write('  .select("text")\n')
            fp.write('  .text(set_text);\n\n')
            fp.write(' nodeEnter.transition()\n')
            fp.write('  .duration(duration)\n')
            fp.write('  .attr("transform", function(d) {\n')
            fp.write('    return "translate(" + d.y + "," + d.x + ")";\n')
            fp.write('   })\n')
            fp.write('  .style("opacity", 1);\n\n')
            fp.write(' node.transition()\n')
            fp.write('  .duration(duration)\n')
            fp.write('  .attr("transform", function(d) {\n')
            fp.write('    return "translate(" + d.y + "," + d.x + ")";\n')
            fp.write('   })\n')
            fp.write('  .style("opacity", 1)\n')
            fp.write('  .select("rect")\n')
            fp.write('  .style("fill", color);\n\n')
            fp.write(' // Transition exiting nodes to the '
                     'parents new position.\n')
            fp.write(' node.exit().transition()\n')
            fp.write('  .duration(duration)\n')
            fp.write('  .attr("transform", function(d) {\n')
            fp.write('    return "translate(" + source.y + "," '
                     '+ source.x + ")";\n')
            fp.write('   })\n')
            fp.write('  .style("opacity", 1e-6)\n')
            fp.write('  .remove();\n\n')
            fp.write(' // Update the links\n')
            fp.write(' var link = svg.selectAll("path.link")\n')
            fp.write('  .data(tree.links(nodes), function(d) { '
                     'return d.target.id; });\n\n')
            fp.write(' // Enter any new links at the parents '
                     'previous position.\n')
            fp.write(' link.enter().insert("path", "g")\n')
            fp.write('  .attr("class", "link")\n')
            fp.write('  .attr("d", function(d) {\n')
            fp.write('    var o = {x: source.x0, y: source.y0};\n')
            fp.write('    return diagonal({source: o, target: o});\n')
            fp.write('   })\n')
            fp.write('  .transition()\n')
            fp.write('  .duration(duration)\n')
            fp.write('  .attr("d", diagonal);\n\n')
            fp.write(' // Transition links to their new position.\n')
            fp.write(' link.transition()\n')
            fp.write('  .duration(duration)\n')
            fp.write('  .attr("d", diagonal);\n\n')
            fp.write(' // Transition exiting nodes to the '
                     'parents new position.\n')
            fp.write(' link.exit().transition()\n')
            fp.write('  .duration(duration)\n')
            fp.write('  .attr("d", function(d) {\n')
            fp.write('    var o = {x: source.x, y: source.y};\n')
            fp.write('    return diagonal({source: o, target: o});\n')
            fp.write('   })\n')
            fp.write('  .remove();\n\n')
            fp.write(' // Stash the old positions for transition.\n')
            fp.write(' nodes.forEach(function(d) {\n')
            fp.write('  d.x0 = d.x;\n')
            fp.write('  d.y0 = d.y;\n')
            fp.write(' });\n')
            fp.write('}\n\n')
            fp.write('// Toggle children on click.\n')
            fp.write('function click(d) {\n')
            fp.write(' if (d.children) {\n')
            fp.write('  d._children = d.children;\n')
            fp.write('  d.children = null;\n')
            fp.write(' } else {\n')
            fp.write('  d.children = d._children;\n')
            fp.write('  d._children = null;\n')
            fp.write(' }\n')
            fp.write(' update(d);\n')
            fp.write('}\n\n')
            fp.write('function color(d) {\n')
            fp.write(' return d._children ? "' + self.more_bg +
                '" : d.children ? "' + self.parent_bg + '" : "' +
                self.no_more_bg + '";\n')
            fp.write('}\n\n')
            fp.write('function set_text(d) {\n')
            fp.write(' var ret_str = d.display_num')
            fp.write(' + " " + d.name + " (" + d.born')
            fp.write(' + " - " + d.died + ")";\n')
            fp.write(' if (d.display_num == "sp.") {\n')
            fp.write('  if (d.marriage !== undefined &&')
            fp.write(' d.marriage.length > 0) {\n')
            fp.write('   ret_str = ret_str + ", " + d.marriage;\n')
            fp.write('  }\n')
            fp.write('  if (d.divorve !== undefined &&')
            fp.write(' d.divorce.length > 0) {\n')
            fp.write('   ret_str = ret_str + ", " + d.divorce;\n')
            fp.write('  }\n')
            fp.write(' }\n')
            fp.write(' return ret_str;\n')
            fp.write('}\n\n')

            if self.showbio:
                fp.write('function set_biography_text(d) {\n')
                fp.write(' var ret_str = "<div class=\'bio_box\'>";\n')
                fp.write(' if (d.image_ref !== undefined) {\n')
                fp.write('    ret_str = ret_str + "<img align=\'right\' '
                         'alt=\'\' border=0 src=\'";\n')
                fp.write('    ret_str = ret_str + d.image_ref + "\'/>";\n')
                fp.write(' }\n')
                fp.write(' ret_str = ret_str + "<p class=\'bio_header\'>'
                         '<strong>" + d.name + "</strong></p>";\n')
                fp.write(' ret_str = ret_str + "<div class=\''
                         'bio_text\'>" + d.biography + "</div>";\n')
                fp.write(' ret_str = ret_str + "</div>";\n')
                fp.write('\n')
                fp.write(' return ret_str;\n')
                fp.write('}\n\n')

            if self.arrows != "None":
                fp.write('function set_arrow(d) {\n')
                fp.write(' if (d.children) {\n')
                if self.arrows == "Arrows":
                    fp.write('  return "images/less.png";\n')
                else:
                    fp.write('  return "images/minus.png";\n')
                fp.write(' } else if (d._children) {\n')
                if self.arrows == "Arrows":
                    fp.write('  return "images/more.png";\n')
                else:
                    fp.write('  return "images/plus.png";\n')
                fp.write(' } else {\n')
                fp.write('  return "images/none.png";\n')
                fp.write(' }\n')
                fp.write('}\n\n')

    def write_report(self):
        """
        The routine the actually creates the report. At this point, the document
        is opened and ready for writing.
        """
        name = self._name_display.display(self.center_person)
        title = "Descendant Indented Tree for " + name

        if not os.path.isdir(self.dest_path):
            prompt = QuestionDialog2(_('Invalid Destination Directory'),
                                     _('Destinaton diretory %s does not '
                                       'exist\nDo you want to attempt to '
                                       'create it.') % self.dest_path,
                                     _('_Yes'),
                                     _('_No'))
            if prompt.run():
                try:
                    os.mkdir(self.dest_path)
                except Exception as err:
                    ErrorDialog(_("Failed to create %s: %s") %
                                (self.dest_path, str(err)))
                    return
            else:
                return

        elif not os.access(self.dest_path, os.R_OK|os.W_OK|os.X_OK):
            ErrorDialog(_('Permission problem'),
                        _('You do not have permission to write under the '
                          'directory %s\n\nPlease select another directory '
                          'or correct the permissions.') % self.dest_path)
            return

        if os.path.isfile(self.desthtml):
            prompt = QuestionDialog2(_('File already exists'),
                                     _('Destination file %s already exists.\n'
                                       'Do you want to overwrite.') %
                                     (self.desthtml),
                                     _('_Yes'),
                                     _('_No'))
            if not prompt.run():
                return

        try:
            with io.open(self.desthtml, 'w', encoding='utf8') as fp:
                # Generate HTML File
                outstr = '<!DOCTYPE html>\n' + \
                    '<html>\n' + \
                    '  <head>\n' + \
                    '    <title>' + title + '</title>\n' + \
                    '    <meta http-equiv="Content-Type" ' + \
                    'content="text/html;charset=utf-8"/>\n' + \
                    '    <script type="text/javascript" ' + \
                    'src="js/d3/d3.min.js"></script>\n' + \
                    '    <script type="text/javascript" ' + \
                    'src="js/d3/d3.tip.v0.6.3.js"></script>\n' + \
                    '    <script type="text/javascript" ' + \
                    'src="js/jquery/jquery-2.0.3.min.js"></script>\n' + \
                    '    <link type="text/css" rel="stylesheet" ' + \
                    'href="css/d3.tip.css"/>\n' + \
                    '    <link type="text/css" rel="stylesheet" ' + \
                    'href="css/indentedtree-%s.css"/>\n' % (self.destprefix) + \
                    '  </head>\n' + \
                    '  <body>\n' + \
                    '    <div id="body">\n' + \
                    '      <div id="start">\n' + \
                    '       <h1>' + title + '</h1>\n' + \
                    '      </div>\n' + \
                    '      <div id="chart">\n' + \
                    '      </div>\n' + \
                    '      <div id="end">\n'
                if self.arrows == "None":
                    outstr = outstr + \
                        '        <h3>Click people to expand/collapse</h3>\n'
                elif self.arrows == "Arrows":
                    outstr = outstr + \
                        '        <h3>Click arrow images to expand/collapse</h3>\n'
                else:
                    outstr = outstr + \
                        '        <h3>Click plus/minus images to ' + \
                        'expand/collapse</h3>\n'
                if self.showbio:
                    outstr = outstr + \
                        '        <h3>Hover over person to see biography ' + \
                        'information.\n' + \
                        '        On touch-screen devices tap on person</h3>\n'
                outstr = outstr + \
                    '        <button class="button" id="default-button" ' + \
                    'type="button">%s</button>\n' % (_("Default View"))
                outstr = outstr + \
                    '        <button class="button" id="expand-button" ' + \
                    'type="button">%s</button>\n' % (_("Expand All"))
                outstr = outstr + \
                    '      </div>\n' + \
                    '    </div>\n' + \
                    '    <div class="div_svg">\n' + \
                    '    </div>\n' + \
                    '    <div class="calc_svg">\n' + \
                    '    </div>\n'
                outstr = outstr + \
                    '    <script type="text/javascript">\n' + \
                    '      var cur_view = "DEFAULT";\n' + \
                    '      window.onload = function() {\n' + \
                    '        $.getScript("js/indentedtree-' + \
                    '%s.js",' % (self.destprefix) + \
                    ' function( data, textStatus, jqxhr ) {\n' + \
                    '          // do some stuff after script is loaded\n' + \
                    '        });\n' + \
                    '        this.cur_view = "DEFAULT";\n' + \
                    '      };\n' + \
                    '      $("#default-button").on("click", function() {\n' + \
                    '        if (cur_view !== "DEFAULT") {\n' + \
                    '          d3.select("div.div_svg").select("svg").' + \
                    'remove();\n' + \
                    '          d3.select("div.d3-tip").remove();\n' + \
                    '          $.getScript("js/indentedtree-' + \
                    '%s.js",' % (self.destprefix) + \
                    ' function( data, textStatus, jqxhr ) {\n' + \
                    '            // do some stuff after script is loaded\n' + \
                    '          });\n' + \
                    '          cur_view = "DEFAULT";\n' + \
                    '        }\n' + \
                    '      });\n' + \
                    '      $("#expand-button").on("click", function() {\n' + \
                    '        if (cur_view == "DEFAULT") {\n' + \
                    '          d3.select("div.div_svg").select("svg").' + \
                    'remove();\n' + \
                    '          d3.select("div.d3-tip").remove();\n' + \
                    '          $.getScript("js/indentedtree-' + \
                    '%s-expanded.js",' % (self.destprefix) + \
                    ' function( data, textStatus, jqxhr ) {\n' + \
                    '            // do some stuff after script is loaded\n' + \
                    '          });\n' + \
                    '          cur_view = "EXPANDED";\n' + \
                    '        }\n' + \
                    '      });\n' + \
                    '    </script>\n' + \
                    '  </body>\n' + \
                    '</html>\n'
                fp.write(outstr)

        except IOError as msg:
            ErrorDialog(_("Failed writing %s: %s") % (self.desthtml, str(msg)))
            return

        # Create required directory structure
        try:
            if not os.path.exists(os.path.join(self.dest_path, "css")):
                os.mkdir(os.path.join(self.dest_path, "css"))
            if not os.path.exists(os.path.join(self.dest_path, "images")):
                os.mkdir(os.path.join(self.dest_path, "images"))
            if not os.path.exists(os.path.join(self.dest_path, "js")):
                os.mkdir(os.path.join(self.dest_path, "js"))
            if not os.path.exists(os.path.join(self.dest_path, "js", "d3")):
                os.mkdir(os.path.join(self.dest_path, "js", "d3"))
            if not os.path.exists(os.path.join(self.dest_path, "js", "jquery")):
                os.mkdir(os.path.join(self.dest_path, "js", "jquery"))
            if not os.path.exists(os.path.join(self.dest_path, "json")):
                os.mkdir(os.path.join(self.dest_path, "json"))
        except OSError as why:
            ErrorDialog(_("Failed to create directory structure : %s") % (why))
            return

        try:
            # Copy/overwrite css/images/js files
            plugin_dir = os.path.dirname(__file__)
            shutil.copy(os.path.join(plugin_dir, "css", "d3.tip.css"),
                os.path.join(self.dest_path, "css"))
            shutil.copy(os.path.join(plugin_dir, "images", "male.png"),
                os.path.join(self.dest_path, "images"))
            shutil.copy(os.path.join(plugin_dir, "images", "female.png"),
                os.path.join(self.dest_path, "images"))
            shutil.copy(os.path.join(plugin_dir, "images", "less.png"),
                os.path.join(self.dest_path, "images"))
            shutil.copy(os.path.join(plugin_dir, "images", "more.png"),
                os.path.join(self.dest_path, "images"))
            shutil.copy(os.path.join(plugin_dir, "images", "none.png"),
                os.path.join(self.dest_path, "images"))
            shutil.copy(os.path.join(plugin_dir, "images", "plus.png"),
                os.path.join(self.dest_path, "images"))
            shutil.copy(os.path.join(plugin_dir, "images", "minus.png"),
                os.path.join(self.dest_path, "images"))
            shutil.copy(
                os.path.join(plugin_dir, "images", "texture-noise.png"),
                os.path.join(self.dest_path, "images"))
            shutil.copy(os.path.join(plugin_dir, "js", "d3", "d3.min.js"),
                os.path.join(self.dest_path, "js", "d3"))
            shutil.copy(
                os.path.join(plugin_dir, "js", "d3", "d3.tip.v0.6.3.js"),
                os.path.join(self.dest_path, "js", "d3"))
            shutil.copy(
                os.path.join(
                    plugin_dir, "js", "jquery", "jquery-2.0.3.min.js"),
                os.path.join(self.dest_path, "js", "jquery"))
        except OSError as why:
            ErrorDialog(_("Failed to copy web files : %s") % (why))
            return

        # Generate <dest>.js customizing based on options selected
        try:
            self.write_js(self.destjs, self.contraction)
        except IOError as msg:
            ErrorDialog(_("Failed writing %s: %s") % (self.destjs, str(msg)))

        # Generate <destexpanded>.js customizing based on options selected
        try:
            self.write_js(self.destexpandedjs, 99)
        except IOError as msg:
            ErrorDialog(_("Failed writing %s: %s") % (self.destexpandedjs,
                        str(msg)))
            return

        # Generate <dest>.css options selected such as font-size
        try:
            with io.open(self.destcss, 'w', encoding='utf8') as fp:
                fp.write('body {\n')
                fp.write('    background: url(../images/texture-noise.png);\n')
                fp.write('    margin: 0;\n')
                fp.write('    font-size: 11px;\n')
                fp.write('    font-weight: bold;\n')
                fp.write('    font-family: "Helvetica Neue", Helvetica;\n')
                fp.write('}\n\n')

                fp.write('.node rect {\n')
                fp.write('    fill: #fff;\n')
                fp.write('    fill-opacity: .5;\n')
                fp.write('    stroke: #3182bd;\n')
                fp.write('    stroke-width: 1.5px;\n')
                fp.write('}\n\n')

                fp.write('.node text {\n')
                fp.write('    font: %spx sans-serif;\n' % (self.font_size))
                fp.write('    font-weight: bold;\n')
                fp.write('    pointer-events: none;\n')
                fp.write('}\n\n')

                fp.write('.node_test text {\n')
                fp.write('    font: %spx sans-serif;\n' % (self.font_size))
                fp.write('    font-weight: bold;\n')
                fp.write('    pointer-events: none;\n')
                fp.write('}\n\n')

                fp.write('svg a {\n')
                fp.write('    fill: blue;\n')
                fp.write('}\n\n')

                fp.write('svg a:visited {\n')
                fp.write('    fill: #800080;\n')
                fp.write('}\n\n')

                fp.write('path.link {\n')
                fp.write('    fill: none;\n')
                fp.write('    stroke: #9ecae1;\n')
                fp.write('    stroke-width: 1.5px;\n')
                fp.write('}\n\n')

                fp.write('.bio_box {\n')
                fp.write('    max-width: 400px;\n')
                fp.write('}\n\n')

                fp.write('.bio_header {\n')
                fp.write('    font: %spx sans-serif;\n' %
                         (self.bio_header_font_size))
                fp.write('    font-weight: bold;\n')
                fp.write('    text-align: left;\n')
                fp.write('    margin-right: 0.25cm; margin-left: 0.25cm;\n')
                fp.write('    margin-top: 0.25cm; margin-bottom: 0.25cm;\n')
                fp.write('    border-top:none; border-bottom:none;\n')
                fp.write('    border-left:none; border-right:none;\n')
                fp.write('}\n\n')

                fp.write('.bio_text {\n')
                fp.write('    font: %spx sans-serif;\n' %
                         (self.bio_body_font_size))
                fp.write('    font-weight: bold;\n')
                fp.write('    text-align: left;\n')
                fp.write('    margin-right: 0.25cm; margin-left: 0.25cm;\n')
                fp.write('    margin-top: 0.25cm; margin-bottom: 0.25cm;\n')
                fp.write('    border-top:none; border-bottom:none;\n')
                fp.write('    border-left:none; border-right:none;\n')
                fp.write('}\n\n')

                fp.write('.button{\n')
                fp.write('    background: #ECECEC;\n')
                fp.write('    border-radius: 10px;\n')
                fp.write('    padding: 5px 10px;\n')
                fp.write('    font-family: arial;\n')
                fp.write('    font-weight: bold;\n')
                fp.write('    text-decoration: none;\n')
                fp.write('    text-shadow:0px 1px 0px #fff;\n')
                fp.write('    border:2px solid #3182bd;\n')
                fp.write('    width: 145px;\n')
                fp.write('    margin:0px auto;\n')
                fp.write('    box-shadow: 0px 2px 1px white inset, 0px -2px ')
                fp.write('8px white, 0px 2px 5px rgba(0, 0, 0, 0.1), 0px 8px ')
                fp.write('10px rgba(0, 0, 0, 0.1);\n')
                fp.write('    -webkit-transition:box-shadow 0.5s;\n')
                fp.write('}\n\n')

                fp.write('.button:hover{\n')
                fp.write('    box-shadow: 0px 2px 1px white inset, 0px -2px ')
                fp.write('20px white, 0px 2px 5px rgba(0, 0, 0, 0.1), 0px 8px ')

                fp.write('10px rgba(0, 0, 0, 0.1);\n')
                fp.write('}\n\n')

                fp.write('.button:active{\n')
                fp.write('    box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.5) ')
                fp.write('inset, 0px -2px 20px white, 0px 1px 5px rgba(0, 0, ')
                fp.write('0, 0.1), 0px 2px 10px rgba(0, 0, 0, 0.1);\n')
                fp.write('    background:-webkit-linear-gradient(top, ')
                fp.write('#d1d1d1 0%,#ECECEC 100%);\n')
                fp.write('}\n\n')

        except IOError as msg:
            ErrorDialog(_("Failed writing %s: %s") % (self.destcss, str(msg)))
            return

        # Genearte json data file to be used
        try:
            with io.open(self.destjson, 'w', encoding='utf8') as self.json_fp:
                generation = 1
                self.objPrint.set_json_fp(self.json_fp)
                self.objPrint.set_dest_prefix(self.destprefix)
                recurse = RecurseDown(self.max_gen, self.database,
                                      self.objPrint, self.dups, self.marrs,
                                      self.divs, self.user, self.title,
                                      self.num_obj)
                recurse.recurse_count(generation, self.center_person, None)
                if self.numbering == "Record":
                    self.num_obj.reset()
                recurse.recurse(generation, self.center_person, None)

        except IOError as msg:
            ErrorDialog(_("Failed writing %s: %s") % (self.destjson, str(msg)))
            return

#------------------------------------------------------------------------
#
# DescendantIndentedTreeOptions
#
#------------------------------------------------------------------------
class DescendantIndentedTreeOptions(MenuReportOptions):

    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, dbase):
        self._dbase = dbase
        MenuReportOptions.__init__(self, name, dbase)

    def validate_gen(self):
        """
        Validate generations within range MIN_GEN and MAX_GEN
        """
        max_gen = self.max_gen.get_value()
        if max_gen < MIN_GEN:
            self.max_gen.set_value(MIN_GEN)
        if max_gen > MAX_GEN:
            self.max_gen.set_value(MAX_GEN)

        contraction = self.contraction.get_value()
        if contraction < MIN_GEN:
            self.contraction.set_value(MIN_GEN)
        if contraction > MAX_GEN:
            self.contraction.set_value(MAX_GEN)

        href_gen = self.href_gen.get_value()
        if href_gen < MIN_GEN:
            self.href_gen.set_value(MIN_GEN)
        if href_gen > MAX_GEN:
            self.href_gen.set_value(MAX_GEN)

        dead_years = self.dead_years.get_value()
        if dead_years < MIN_GEN:
            self.dead_years.set_value(MIN_GEN)
        if dead_years > MAX_GEN:
            self.dead_years.set_value(MAX_GEN)

    def validate_age(self):
        """
        Validate age within range MIN_AGE and MAX_AGE
        """
        href_age = self.href_age.get_value()
        if href_age < MIN_AGE:
            self.href_age.set_value(MIN_AGE)
        if href_age > MAX_AGE:
            self.href_age.set_value(MAX_AGE)

    def validate_font_size(self):
        """
        Validate font with range MIN_FONT and MAX_FONT
        """
        font_size = self.font_size.get_value()
        if font_size < MIN_FONT:
            self.font_size.set_value(MIN_FONT)
        if font_size > MAX_FONT:
            self.font_size.set_value(MAX_FONT)

    def validate_bio_font_size(self):
        """
        Validate font with range MIN_BIO_FONT and MAX_BIO_FONT
        """
        font_size = self.bio_header_font_size.get_value()
        if font_size < MIN_BIO_FONT:
            self.bio_header_font_size.set_value(MIN_BIO_FONT)
        if font_size > MAX_BIO_FONT:
            self.bio_header_font_size.set_value(MAX_BIO_FONT)

        font_size = self.bio_body_font_size.get_value()
        if font_size < MIN_BIO_FONT:
            self.bio_body_font_size.set_value(MIN_BIO_FONT)
        if font_size > MAX_BIO_FONT:
            self.bio_body_font_size.set_value(MAX_BIO_FONT)

    def add_menu_options(self, menu):
        """
        Add options to the menu for the descendant indented tree report.
        """
        category = _("Report Options")
        add_option = partial(menu.add_option, category)

        pid = PersonOption(_("Center Person"))
        pid.set_help(_("The center person for the report"))
        add_option("pid", pid)

        stdoptions.add_name_format_option(menu, category)

        numbering = EnumeratedListOption(_("Numbering system"), "Simple")
        numbering.set_items([
                ("Simple",      _("Simple numbering")),
                ("d'Aboville", _("d'Aboville numbering")),
                ("Henry", _("Henry numbering")),
                ("de Villiers/Pama", _("de Villiers/Pama numbering")),
                ("Meurgey de Tupigny", _("Meurgey de Tupigny numbering")),
                ("Record", _("Record (Modified Register) numbering"))])
        numbering.set_help(_("The numbering system to be used"))
        add_option("numbering", numbering)

        self.max_gen = NumberOption(_("Include Generations"),
                                    10, MIN_GEN, MAX_GEN)
        self.max_gen.set_help(_("The number of generations to include in the "
                                "report"))
        add_option("max_gen", self.max_gen)
        self.max_gen.connect('value-changed', self.validate_gen)

        self.contraction = NumberOption(_("Include contraction level"),
                                        3, MIN_GEN, MAX_GEN)
        self.contraction.set_help(_("The number of descendant levels to "
                                    "contract on initial display."))
        add_option("contraction", self.contraction)
        self.contraction.connect('value-changed', self.validate_gen)

        self.font_size = NumberOption(_("Font size"),
                                        10, MIN_FONT, MAX_FONT)
        self.font_size.set_help(_("The font size in pixels for each node."))
        add_option("font_size", self.font_size)
        self.font_size.connect('value-changed', self.validate_font_size)

        dest_path = DestinationOption(_("Destination"),
            config.get('paths.website-directory'))
        dest_path.set_help(_("The destination path for generated files."))
        dest_path.set_directory_entry(True)
        add_option("dest_path", dest_path)

        dest_file = StringOption(_("Filename"), "DescendantIndentedTree.html")
        dest_file.set_help(_("The destination file name for html content."))
        add_option("dest_file", dest_file)

        stdoptions.add_localization_option(menu, category)

        # Content
        add_option = partial(menu.add_option, _("Content"))

        marrs = BooleanOption(_('Show marriage info'), False)
        marrs.set_help(_("Whether to show marriage information in the report."))
        add_option("marrs", marrs)

        divs = BooleanOption(_('Show divorce info'), False)
        divs.set_help(_("Whether to show divorce information in the report."))
        add_option("divs", divs)

        dups = BooleanOption(_('Show duplicate trees'), True)
        dups.set_help(_("Whether to show duplicate family trees in the "
                        "report."))
        add_option("dups", dups)

        parent_bg = ColorOption(_("Expanded Row Background Color"), "#c6dbef")
        parent_bg.set_help(_("RGB-color for expanded row background."))
        add_option("parent_bg", parent_bg)

        more_bg = ColorOption(_("Expandable Background Color"),
            "#3182bd")
        more_bg.set_help(_("RGB-color for expandable row background."))
        add_option("more_bg", more_bg)

        no_more_bg = ColorOption(_("Non-Expandable Background Color"),
            "#fd8d3c")
        no_more_bg.set_help(_("RGB-color for non-expandable row "
                              "background."))
        add_option("no_more_bg", no_more_bg)

        self.inc_private = BooleanOption(_('Include records marked private'),
                                         False)
        self.inc_private.set_help(_("Whether to include private objects."))
        add_option("inc_private", self.inc_private)

        self.inc_living = EnumeratedListOption(_("Living People"),
                                               LivingProxyDb.MODE_EXCLUDE_ALL)
        self.inc_living.set_items([
                (LivingProxyDb.MODE_EXCLUDE_ALL, _("Exclude")),
                (LivingProxyDb.MODE_INCLUDE_LAST_NAME_ONLY,
                 _("Include Last Name Only")),
                (LivingProxyDb.MODE_INCLUDE_FULL_NAME_ONLY,
                 _("Include Full Name Only")),
                (_INCLUDE_LIVING_VALUE, _("Include"))])
        self.inc_living.set_help(_("How to handle living people."))
        add_option("inc_living", self.inc_living)
        self.inc_living.connect('value-changed', self.inc_living_changed)
        
        # Years from death to consider living
        self.dead_years = NumberOption(_("Years from death to consider living"),
                                       30, MIN_GEN, MAX_GEN)
        self.dead_years.set_help(_("Whether or not to include people who "
                                 "may have recently died."))
        add_option("dead_years", self.dead_years)
        self.dead_years.connect('value-changed', self.validate_gen)

        self.inc_living_changed()

        # Navigation
        add_option = partial(menu.add_option, _("Navigation"))

        self.arrows = EnumeratedListOption(_("Contraction/Expansion mechanism"),
                                         "None")
        self.arrows.set_items([
                ("None", _("Entire node.")),
                ("Arrows", _("Arrow images at start of node.")),
                ("Maths", _("Plus/Minus images at start of node."))])
        self.arrows.set_help(_("Where to click to expand/contract nodes."))
        add_option("arrows", self.arrows)
        self.arrows.connect('value-changed', self.arrows_changed)

        self.hrefs = BooleanOption(_('Auto-generate HREF links for nodes'),
                                   False)
        self.hrefs.set_help(_("Whether to auto-generate HTML links for each "
                              "node on the report."))
        add_option("hrefs", self.hrefs)
        self.hrefs.connect('value-changed', self.hrefs_changed)

        # URL Prefix
        self.href_prefix = StringOption(_("URL prefix path."),
                                        "http://my.family.tree.com/")
        self.href_prefix.set_help(_("URL prefix to apply to each "
                                    "auto-generated HREF link."))
        add_option("href_prefix", self.href_prefix)

        # URL Extension
        self.href_ext = EnumeratedListOption(
            _("URL file extension"), "None")
        self.href_ext.set_items([
                ("None", _("No file extension.")),
                ("html", _(".html")),
                ("htm", _(".htm")),
                ("shtml", _(".shtml")),
                ("php", _(".php")),
                ("php3", _(".php3")),
                ("cgi", _(".cgi"))])
        self.href_ext.set_help(_("Where to click to expand/contract nodes."))
        add_option("href_ext", self.href_ext)

        # URL Delimeter
        self.href_delim = EnumeratedListOption(
            _("URL file name delimeter"), "None")
        self.href_delim.set_items([
                ("None", _("Remove all whitespace.")),
                ("Dash", _("Replace whitespace with dash(-).")),
                ("Underscore", _("Replace whitespace with underscore(_)"))])
        self.href_delim.set_help(_("What to use as file name delimiter "
                                   "replacing whitespace."))
        add_option("href_delim", self.href_delim)

        # URL Generations
        self.href_gen = NumberOption(_("Generations to generate HREF links"),
                                     10, MIN_GEN, MAX_GEN)
        self.href_gen.set_help(_("The number of generations to generate "
                                 "HREF links."))
        add_option("href_gen", self.href_gen)
        self.href_gen.connect('value-changed', self.validate_gen)

        # Exclude persons not reaching age
        self.href_age = NumberOption(_("Exclude persons who died before "
                                       "(years)"),
                                     -1, -1, 100)
        self.href_age.set_help(_("Whether to generate links for people who "
                                 "died in infancy, -1 excludes nobody."))
        add_option("href_age", self.href_age)
        self.href_age.connect('value-changed', self.validate_age)

        # Exclude top person
        self.href_excl_center = BooleanOption(_('Exclude center person'), False)
        self.href_excl_center.set_help(_("Whether or not to generate links "
                                         "for center person."))
        add_option("href_excl_center", self.href_excl_center)

        # Exclude spouses
        self.href_excl_spouse = BooleanOption(_('Exclude Spouses'), False)
        self.href_excl_spouse.set_help(_("Whether or not to generate links "
                                         "for spouses."))
        add_option("href_excl_spouse", self.href_excl_spouse)

        self.arrows_changed()

        # Biography Options
        add_option = partial(menu.add_option, _("Biography Content"))

        self.showbio = BooleanOption(_('Show biography tooltips'), True)
        self.showbio.set_help(_("Whether to show biography tooltips when "
                                "hovering over a node."))
        add_option("showbio", self.showbio)
        self.showbio.connect('value-changed', self.showbio_changed)

        self.use_call = BooleanOption(_("Use callname for common name"), True)
        self.use_call.set_help(_("Whether to use the call name as the first "
                                 "name."))
        add_option("use_call", self.use_call)
        
        self.use_fulldates = BooleanOption(_("Use full dates instead of only "
                                             "the year"),
                                           True)
        self.use_fulldates.set_help(_("Whether to use full dates instead of "
                                      "just year."))
        add_option("use_fulldates", self.use_fulldates)

        self.compute_age = BooleanOption(_("Compute death age"),True)
        self.compute_age.set_help(_("Whether to compute a person's age at "
                                    "death."))
        add_option("compute_age", self.compute_age)

        self.inc_photo = BooleanOption(_("Include Photo/Images from Gallery"),
                                       True)
        self.inc_photo.set_help(_("Whether to include images."))
        add_option("inc_photo", self.inc_photo)

        self.verbose = BooleanOption(_("Use complete sentences"), True)
        self.verbose.set_help(
                 _("Whether to use complete sentences or succinct language."))
        add_option("verbose", self.verbose)

        self.rep_place = BooleanOption(_("Replace missing places with ______"),
                                       False)
        self.rep_place.set_help(_("Whether to replace missing Places with "
                                  "blanks."))
        add_option("rep_place", self.rep_place)

        self.rep_date = BooleanOption(_("Replace missing dates with ______"),
                                      False)
        self.rep_date.set_help(_("Whether to replace missing Dates with "
                                 "blanks."))
        add_option("rep_date", self.rep_date)

        self.bio_text = ColorOption(_("Text Color"),
            "#ffffff")
        self.bio_text.set_help(_("RGB-color for biography text."))
        add_option("bio_text", self.bio_text)

        self.bio_bg = ColorOption(_("Background Color"),
            "#000000")
        self.bio_bg.set_help(_("RGB-color for biography tooltip."))
        add_option("bio_bg", self.bio_bg)

        self.bio_header_font_size = NumberOption(_("Header Font size"),
                                                 12, MIN_FONT, MAX_FONT)
        self.bio_header_font_size.set_help(_("The font size in pixels for "
                                             "biography header text."))
        add_option("bio_header_font_size", self.bio_header_font_size)
        self.bio_header_font_size.connect('value-changed',
                                          self.validate_bio_font_size)

        self.bio_body_font_size = NumberOption(_("Body Font size"),
                                                10, MIN_FONT, MAX_FONT)
        self.bio_body_font_size.set_help(_("The font size in pixels for "
                                           "biography body text."))
        add_option("bio_body_font_size", self.bio_body_font_size)
        self.bio_body_font_size.connect('value-changed',
                                        self.validate_bio_font_size)

        self.showbio_changed()

    def showbio_changed(self):
        """
        Handles the changing nature of show biography tooltips page
        """
        if self.showbio.get_value():
            self.use_call.set_available(True)
            self.use_fulldates.set_available(True)
            self.compute_age.set_available(True)
            self.inc_photo.set_available(True)
            self.verbose.set_available(True)
            self.rep_place.set_available(True)
            self.rep_date.set_available(True)
            self.bio_bg.set_available(True)
            self.bio_text.set_available(True)
            self.bio_header_font_size.set_available(True)
            self.bio_body_font_size.set_available(True)
        else:
            self.use_call.set_available(False)
            self.use_fulldates.set_available(False)
            self.compute_age.set_available(False)
            self.inc_photo.set_available(False)
            self.verbose.set_available(False)
            self.rep_place.set_available(False)
            self.rep_date.set_available(False)
            self.bio_bg.set_available(False)
            self.bio_text.set_available(False)
            self.bio_header_font_size.set_available(False)
            self.bio_body_font_size.set_available(False)

    def inc_living_changed(self):
        """
        Handles the changing nature of living inclusion
        """
        if self.inc_living.get_value() == _INCLUDE_LIVING_VALUE:
            self.dead_years.set_available(False)
        else:
            self.dead_years.set_available(True)

    def arrows_changed(self):
        """
        Handles the changing nature of contraction/expansion click mechanism
        """
        arrow_val = self.arrows.get_value()

        if arrow_val == "None":
            self.hrefs.set_available(False)
            self.href_prefix.set_available(False)
            self.href_ext.set_available(False)
            self.href_delim.set_available(False)
            self.href_gen.set_available(False)
            self.href_age.set_available(False)
            self.href_excl_spouse.set_available(False)
            self.href_excl_center.set_available(False)
        else:
            self.hrefs.set_available(True)
            self.hrefs_changed()

    def hrefs_changed(self):
        """
        Handles the changing nature of auto-generate hrefs option
        """
        if self.arrows.get_value() != "None" and self.hrefs.get_value():
            self.href_prefix.set_available(True)
            self.href_ext.set_available(True)
            self.href_delim.set_available(True)
            self.href_gen.set_available(True)
            self.href_age.set_available(True)
            self.href_excl_spouse.set_available(True)
            self.href_excl_center.set_available(True)
        else:
            self.href_prefix.set_available(False)
            self.href_ext.set_available(False)
            self.href_delim.set_available(False)
            self.href_gen.set_available(False)
            self.href_age.set_available(False)
            self.href_excl_spouse.set_available(False)
            self.href_excl_center.set_available(False)
