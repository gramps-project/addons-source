#
# DescendantSpaceTree - a plugin for GRAMPS, the GTK+/GNOME based
#       genealogy program that creates an Descendant Space Tree
#       for efficient viewing, even for many generatioins.
#
#
# Copyright 2018-2025  Thomas S. Poindexter <tpoindex@gmail.com>
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
# ------------------------------------------------------------------------
# See LICENSE.txt for the full text of the license.
# ------------------------------------------------------------------------


"""Reports/Web Pages/Descendant Space Tree"""

# ------------------------------------------------------------------------
#
# python modules
#
# ------------------------------------------------------------------------
from __future__ import unicode_literals
from functools import partial
import io
import html
import os
import logging

# ------------------------------------------------------------------------
#
# Internationalisation
#
# ------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale


# ------------------------------------------------------------------------
#
# gramps modules
#
# ------------------------------------------------------------------------
# from gramps.gen.display.name import displayer as global_name_display
from gramps.gen.datehandler._datedisplay import DateDisplay
from gramps.gen.lib.date import Date
from gramps.gen.lib.person import Person
from gramps.gen.plug.menu import (
    NumberOption,
    PersonOption,
    DestinationOption,
    StringOption,
    EnumeratedListOption,
)
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.utils.db import (
    get_birth_or_fallback,
    get_death_or_fallback,
    get_marriage_or_fallback,
)
from gramps.gui.dialog import ErrorDialog, QuestionDialog2
from gramps.gen.config import config


try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


MIN_GEN = 1
DEF_GEN = 20
MAX_GEN = 100
DEF_BIRTH_YEAR = 1900

# alternate lineage id suffix
ALT_SUFFIX = "_ALT"

LOG = logging.getLogger(__name__)

# default date display
DT_DISP = DateDisplay().display_formatted
DATE_EMPTY = Date(Date.EMPTY)

# branch_pref items
PATRIARCHAL_LINE = _("Patriarchal Line (Male ancestor)")
MATRIARCHAL_LINE = _("Matriarchal Line (Female ancestor)")


def _q_double(s):
    """
    Quote a string for use in a double-quoted string.
    """
    return s.replace('"', '\\"')


def get_date_from_event_or_empty(ev):
    """
    Get the date from an event or return an empty date object.
    """
    if ev:
        ev_date = ev.get_date_object()
        if ev_date and ev_date.is_valid():
            return ev_date

    return DATE_EMPTY


# ------------------------------------------------------------------------
#
# PersonInfo
#
# ------------------------------------------------------------------------


class PersonInfo:
    """
    Person Info class
    Collect information about a person for easy access and use in determining any duplicates
    """

    def __init__(
        self,
        pid=None,
        gramps_id=None,
        full_name=None,
        surname=None,
        given_name=None,
        gender=None,
        birth=None,
        death=None,
        father_idname=None,
        mother_idname=None,
        total_descendants=0,
        spouses=None,
        children=None,
        ancestor_line=None,
    ):
        self.pid = pid
        self.gramps_id = gramps_id
        self.full_name = full_name
        self.surname = surname
        self.given_name = given_name
        self.gender = gender
        self.birth = birth
        self.death = death
        self.father_idname = father_idname
        self.mother_idname = mother_idname
        self.total_descendants = total_descendants
        self.spouses = spouses
        self.children = children
        self.ancestor_line = ancestor_line
        self.is_duplicate = False
        self.is_descendant = False
        self.alternate_ancestor_line = []
        self.prefer_primary_ancestor_line = True

    def __str__(self):
        """
        Return a string representation of the PersonInfo object.
        """
        return (
            f"PersonInfo(\n"
            f'    pid = "{self.pid}", '
            f'    gramps_id = "{self.gramps_id}", '
            f'    full_name = "{self.full_name}",\n'
            f'    surname = "{self.surname}", '
            f'    given_name = "{self.given_name}", '
            f"    gender = {self.gender},"
            f'    birth = "{self.birth}", '
            f'    death = "{self.death}",\n'
            f'    father_idname = "{self.father_idname}", '
            f'    mother_idname = "{self.mother_idname}", '
            f"    total_descendants = {self.total_descendants},\n"
            f'    spouse = "{self.spouses}", '
            f'    children = "{self.children}", '
            f'    ancestor_line = "{self.ancestor_line}",\n'
            f"    is_duplicate = {self.is_duplicate}, "
            f"    is_descendant = {self.is_descendant}, "
            f"    alternate_ancestor_line = {self.alternate_ancestor_line}, "
            f'    prefer_primary_ancestor_line = "{self.prefer_primary_ancestor_line}",\n'
            ")"
        )

    @staticmethod
    def from_database(database, person_id, ancestor_line):
        """
        Query the GRAMPS database by person id, retrieve their details,
        and populate a PersonInfo object with the retrieved information.
        This method should only be invoked when a person_id is not already in
        the people_map.
        """
        person = database.get_person_from_gramps_id(person_id)
        if not person:
            raise ValueError(
                f"Person with id {person_id} not found in the database"
            )

        gramps_id = person.get_gramps_id()
        full_name = person.get_primary_name().get_regular_name()
        surname = person.get_primary_name().get_surname()
        given_name = person.get_primary_name().get_first_name()
        gender = person.get_gender()
        birth = get_date_from_event_or_empty(
            get_birth_or_fallback(database, person)
        )
        death = get_date_from_event_or_empty(
            get_death_or_fallback(database, person)
        )

        father_idname = None
        mother_idname = None
        total_descendants = 0
        spouses = []
        children = []

        father_idname = None
        mother_idname = None
        main_parents_handle = person.get_main_parents_family_handle()
        if main_parents_handle is not None:
            father_hand = database.get_family_from_handle(
                main_parents_handle
            ).get_father_handle()
            if father_hand is not None:
                father_person = database.get_person_from_handle(father_hand)
                father_idname = (
                    father_person.get_gramps_id(),
                    father_person.get_primary_name().get_regular_name(),
                )

            mother_hand = database.get_family_from_handle(
                main_parents_handle
            ).get_mother_handle()
            if mother_hand is not None:
                mother_person = database.get_person_from_handle(mother_hand)
                mother_idname = (
                    mother_person.get_gramps_id(),
                    mother_person.get_primary_name().get_regular_name(),
                )

        families = person.get_family_handle_list()
        for fam_id in families:
            family = database.get_family_from_handle(fam_id)

            fam_mother_handle = family.get_mother_handle()
            fam_father_handle = family.get_father_handle()

            fam_father_person = None
            fam_mother_person = None
            if fam_mother_handle is not None:
                fam_mother_person = database.get_person_from_handle(
                    fam_mother_handle
                )
            if fam_father_handle is not None:
                fam_father_person = database.get_person_from_handle(
                    fam_father_handle
                )

            # get spouse of this family, the parent that is not the person_id
            spouse_person = None
            if (
                fam_father_person is not None
                and fam_father_person.get_gramps_id() == person_id
            ):
                spouse_person = fam_mother_person
            elif (
                fam_mother_person is not None
                and fam_mother_person.get_gramps_id() == person_id
            ):
                spouse_person = fam_father_person
            else:
                LOG.error(
                    "Could not determine spouse for person %s in family %s",
                    gramps_id,
                    family.get_gramps_id(),
                )
                continue

            marriage = get_date_from_event_or_empty(
                get_marriage_or_fallback(database, family)
            )

            # spouses list is elements of (spouse_id, marriage_date)
            if spouse_person is not None:
                spouses.append((spouse_person.get_gramps_id(), marriage))
            else:
                spouses.append((None, marriage))

            child_ref_list = family.get_child_ref_list()
            for child_ref in child_ref_list:
                child_person = database.get_person_from_handle(child_ref.ref)
                child_birth = get_date_from_event_or_empty(
                    get_birth_or_fallback(database, child_person)
                )

                children.append((child_person.get_gramps_id(), child_birth))

        # sort spouse,marraige_date list by marriage date
        spouses.sort(key=lambda spouse_marriage: spouse_marriage[1].sortval)

        # sort children list by birth date
        children.sort(key=lambda child_birth: child_birth[1].sortval)

        total_descendants += len(children)

        person = PersonInfo(
            pid=person_id,
            gramps_id=gramps_id,
            full_name=full_name,
            surname=surname,
            given_name=given_name,
            gender=gender,
            birth=birth,
            death=death,
            father_idname=father_idname,
            mother_idname=mother_idname,
            total_descendants=total_descendants,
            spouses=spouses,
            children=children,
            ancestor_line=ancestor_line,
        )
        return person

    def choose_ancestor_line(self, people_map, branch_pref):
        """
        Determine which ancestor line should be primary by using the branch_pref.
        Sets the flag prefer_primary_ancestor_line to True to prefer the
        primary ancestor line; False to prefer the alternate ancestor line.
        This is only used in case of duplicates.

        """
        if not self.is_duplicate:
            self.prefer_primary_ancestor_line = True
            return

        # search the two ancestor lines to find the last common ancestor id
        common_id = None
        reversed_ancestor_line = self.ancestor_line + []
        reversed_ancestor_line.reverse()
        reversed_alternate_line = self.alternate_ancestor_line + []
        reversed_alternate_line.reverse()

        for search_id in reversed_ancestor_line:
            if search_id in reversed_alternate_line:
                common_id = search_id
                break

        if common_id is None:
            # we didn't find a common ancestor.  this shouldn't happen, but
            # if so, return a default
            self.prefer_primary_ancestor_line = True
            LOG.warning(
                "choose_ancestor_line: no common ancestor found for person_id = %s",
                self.gramps_id,
            )
            return

        # get the ids, before the common_id in each list
        prev_primary = None
        prev_alternate = None

        idx = reversed_ancestor_line.index(common_id)
        if idx > 0:
            prev_primary = reversed_ancestor_line[idx - 1]
        idx = reversed_alternate_line.index(common_id)
        if idx > 0:
            prev_alternate = reversed_alternate_line[idx - 1]

        # now choose the ancestor line based on the branch_pref
        # first check if either previous id is None
        if prev_primary is None and prev_alternate is not None:
            self.prefer_primary_ancestor_line = False
            return
        if (prev_alternate is None and prev_primary is not None) or (
            prev_primary is None and prev_alternate is None
        ):
            self.prefer_primary_ancestor_line = True
            return

        # choose the ancestor line based on the branch_pref
        if (
            people_map[prev_alternate].gender == Person.FEMALE
            and branch_pref == MATRIARCHAL_LINE
        ) or (
            people_map[prev_alternate].gender == Person.MALE
            and branch_pref == PATRIARCHAL_LINE
        ):
            self.prefer_primary_ancestor_line = False
            return
        else:
            # otherwise, prefer the primary ancestor line
            self.prefer_primary_ancestor_line = True
            return


# ------------------------------------------------------------------------
#
# DescendantSpaceTreeReport
#
# ------------------------------------------------------------------------
class DescendantSpaceTreeReport(Report):
    """
    Descendant SpaceTree Report class
    """

    NAV_BUTTON_CONTINUE = _("Continue Descendant Tree")
    NAV_BUTTON_ALT = _("Alternate Descendant Tree")

    def __init__(self, database, options, user):
        """

        This report needs the following parameters (class variables)
        that come in the options class.

        pid              - Center person ID
        max_gen          - Maximum number of generations to include.
        branch_pref      - Partriarchal or Matriachal line to expand, other line is pruned
        birth_year_limit - Maximum birth year to show birth/death years
        dest_path        - Destination directory
        dest_file        - Destination file name
        output_type      - Single file or Multiple files


        """
        Report.__init__(self, database, options, user)

        # map of id to PersonInfo for center person and all descendants, excluding duplicates
        self.people_map = {}
        # spouse of familes get a separte map
        self.spouse_map = {}

        menu = options.menu
        self.database = database
        self.user = user
        self.title = _("Descendant SpaceTree")

        self.pid = menu.get_option_by_name("pid").get_value()
        self.max_gen = menu.get_option_by_name("max_gen").get_value()
        self.branch_pref = menu.get_option_by_name("branch_pref").get_value()
        self.birth_year_limit = menu.get_option_by_name(
            "birth_year_limit"
        ).get_value()
        self.dest_path = menu.get_option_by_name("dest_path").get_value()
        self.dest_file = menu.get_option_by_name("dest_file").get_value()

    def _dump_people_map(self):
        """
        Dump the people_map to the log for debugging purposes.
        """
        print("------------------------------------------------------------")
        print("people_map: ")
        print("------------------------------------------------------------")
        sorted_keys = sorted(self.people_map.keys())
        for person_id in sorted_keys:
            print(
                self.people_map[person_id],
            )
            print("\n-------\n")
        print("------------------------------------------------------------")

    def _populate_people_map(self, person_id, ancestor_line):
        """
        Populate the people_map by retrieving database information
        using the PersonInfo.from_database method.  Check for duplicates.
        Trickle up the total descendants count for each ancestor (with
        special handling for duplicates).
        """
        person_info = PersonInfo()

        # check if person_id is already in people_map.  this would
        # be a result of a convergence of two branches of the same family,
        # or a spouse was added, but it also an ancestor in another branch.
        if (
            person_id in self.people_map
            and len(self.people_map[person_id].ancestor_line) > 0
        ):
            self.people_map[person_id].is_duplicate = True
            self.people_map[person_id].alternate_ancestor_line = ancestor_line
            self.people_map[person_id].choose_ancestor_line(
                self.people_map, self.branch_pref
            )
            # trickle up the total descendants count for each ancestor,
            # but don't add count to common ancestors
            n_descendants = self.people_map[person_id].total_descendants
            for ancestor_id in ancestor_line:
                if ancestor_id not in self.people_map[person_id].ancestor_line:
                    self.people_map[
                        ancestor_id
                    ].total_descendants += n_descendants

            return

        try:
            person_info = PersonInfo.from_database(
                self.database, person_id, ancestor_line
            )
        except ValueError:
            # Handle the case where the person is not found in the database
            LOG.error("cannot find person = {person_id}")
            return

        person_info.is_descendant = True

        # get PersonInfo for each spouse
        for spouse_tuple in person_info.spouses:
            spouse_id = spouse_tuple[0]
            if spouse_id is None:
                # this is a family with no spouse
                continue
            try:
                if spouse_id not in self.spouse_map:
                    # check if spouse is in the people_map/
                    if spouse_id in self.people_map:
                        spouse_info = self.people_map[spouse_id]
                    else:
                        spouse_info = PersonInfo.from_database(
                            self.database, spouse_id, []
                        )
                    self.spouse_map[spouse_id] = spouse_info
            except ValueError:
                # Handle the case where the spouse is not found in the database
                LOG.warning(
                    "cannot find spouse = {person_id}  for person = {person_id}"
                )
                return

        # trickle up the total descendants count for each ancestor
        # if total_descendants is 0, then this is the first time we
        # are descending this branch.  do not count duplicates.

        self.people_map[person_id] = person_info

        # recurse for each descendant child
        next_ancestor_line = ancestor_line + [person_id]
        for child_tuple in person_info.children:
            child_id = child_tuple[0]
            # trickle up the total descendants count for each ancestor,
            # but don't add count to common ancestors that have already been
            # counted.
            self._populate_people_map(child_id, next_ancestor_line)
            for ancestor_id in ancestor_line:
                if self.people_map[child_id].is_duplicate:
                    if (
                        ancestor_id
                        not in self.people_map[child_id].ancestor_line
                    ):
                        self.people_map[ancestor_id].total_descendants += 1
                else:
                    self.people_map[ancestor_id].total_descendants += 1
            # recurse for each child

    def _generate_descendant_recursive_data(
        self, pid, parent_pid, num_generations
    ):
        """
        Generate the JSON data for the descendant tree, recursing through the descendants.
        Returns the JSON data and list of search names.
        """
        if num_generations > self.max_gen:
            return "", []

        person = self.people_map[pid]
        gramps_id = "@" + person.gramps_id + "@"

        names_list = []

        # check for is_duplicate, determine nav button id, set whether to descend
        # the parend_pid should exists in either the ancestor_line
        # or alternate_ancestor_line, not both should be the last one in either list
        descend = True
        nav_button_id = None
        nav_button_text = ""
        disp_name = _q_double(html.escape(person.full_name))
        names_list.append(disp_name + " " + gramps_id)

        if person.is_duplicate:
            if (
                person.prefer_primary_ancestor_line
                and parent_pid in person.ancestor_line
            ) or (
                not person.prefer_primary_ancestor_line
                and parent_pid in person.alternate_ancestor_line
            ):
                # this is the ancestor line we want to descend
                descend = True
                nav_button_id = gramps_id + ALT_SUFFIX
                nav_button_text = DescendantSpaceTreeReport.NAV_BUTTON_ALT
            else:
                # this is the alternate ancestor line, so don't descend
                # don't include the ALT id in names_list
                descend = False
                nav_button_id = gramps_id
                nav_button_text = DescendantSpaceTreeReport.NAV_BUTTON_CONTINUE
                gramps_id = gramps_id + ALT_SUFFIX
                # print("duplicate id = ", gramps_id, " ", disp_name)

        # create ged data object
        json = "\n\n{\n"
        json += f'id:"{gramps_id}",\n'
        json += f'name:"{disp_name}",\n'
        json += "data:{"  # data js object contains left panel html info
        json += f'info:"<h3>{disp_name}</h3><br>'
        json += _("Id")
        json += f": @{person.gramps_id}@<br>"
        if person.father_idname is not None:
            fdisp_name = _q_double(html.escape(person.father_idname[1]))
            json += _("Father")
            json += f": {fdisp_name}<br>"
        if person.mother_idname is not None:
            mdisp_name = _q_double(html.escape(person.mother_idname[1]))
            json += _("Mother")
            json += f": {mdisp_name}<br>"
        json += _("Total descendants")
        json += f": {person.total_descendants}<br>"

        # add birth/death display
        if (
            person.birth is not None
            and person.birth is not DATE_EMPTY
            and person.birth.get_year() <= self.birth_year_limit
        ):
            bdate = DT_DISP(person.birth)
            json += _("Birth")
            json += f": {bdate}<br>"
            if (
                person.death is not None
                and person.death is not DATE_EMPTY
                and person.death.get_year() <= self.birth_year_limit
            ):
                ddate = DT_DISP(person.death)
                json += _("Death")
                json += f": {ddate}<br>"

        # add spouses display

        if len(person.spouses) > 0:
            json += _("Marriages/Families:<ul>")
            for spouse_id, marraige_date in person.spouses:
                if spouse_id is None:
                    continue
                spouse = self.spouse_map[spouse_id]
                spouse_disp = _q_double(html.escape(spouse.full_name))
                json += f"<li>{spouse_disp}<br>"
                json += "Id"
                json += f": @{spouse.gramps_id}@<br>"

                # add marriage/birth/death display
                if spouse.birth is not None and spouse.birth is not DATE_EMPTY:
                    bdate = DT_DISP(spouse.birth)
                    json += _("Birth")
                    json += f": {bdate}<br>"
                    if (
                        spouse.death is not None
                        and spouse.death is not DATE_EMPTY
                    ):
                        ddate = DT_DISP(spouse.death)
                        json += _("Death")
                        json += f": {ddate}<br>"

                if (
                    marraige_date is not None
                    and marraige_date is not DATE_EMPTY
                    and marraige_date.get_year() <= self.birth_year_limit
                ):
                    mdate = DT_DISP(marraige_date)
                    json += _("Married")
                    json += f": {mdate}<br>"
                json += "</li>"
                names_list.append(
                    _q_double(html.escape(spouse.full_name))
                    + " +@"
                    + person.gramps_id
                    + "@"
                )
            json += "</ul><br>"

        # add nav button, if is_duplicate
        if nav_button_id is not None:
            json += f"<button onClick='nav_goto(\\\"{nav_button_id}\\\");'>"
            json += f"{nav_button_text}</button>"

        json += '"},\n'  # close data js object

        # descend into each child, if any
        json += "children" + ":[\n"
        if (
            descend
            and len(person.children) > 0
            and num_generations < self.max_gen
        ):
            comma = ""
            for child_tuple in person.children:
                child_id = child_tuple[0]
                json += comma
                data_blob, nlist = self._generate_descendant_recursive_data(
                    child_id, pid, num_generations + 1
                )
                json += data_blob
                names_list += nlist
                comma = ","

        json += "\n]}\n"  # close children js list and data js object
        return json, names_list

    def _generate_descendant_json(self, pid):
        person = self.people_map[pid]
        name = _q_double(html.escape(person.full_name))

        tree_data, names_list = self._generate_descendant_recursive_data(
            pid, "", 0
        )

        # remove duplicates from names_list and sort
        names_list = list(dict.fromkeys(names_list))
        names_list.sort()

        json = f'\nged_root = "@{person.gramps_id}@";\n'
        json += f'ged_name = "{name}";\n'
        json += "ged_data = "
        json += tree_data + "\n;\n"
        names_str = '"\n,"'.join(names_list)
        json += f'ged_names = [\n "{names_str}"\n];\n'
        return json

    def write_report(self):
        """
        Create the DescendantSpaceTree html  file
        """

        # check/create output directory
        # descend starting at center person, collecting ids, and if id is seen more than once
        # for each duplicate check surname to preferred surname list, produce duplicate id list
        # descend starting at center person, producing space tree js
        #   - add space tree node, id, name (name + any/all spouses)
        #   - add space tree node, data (name, birth/death, parent names
        #   - total descendants, spouses w/ birth/death & marriage years.
        # recurse
        # write files

        # center_person = self.database.get_person_from_handle(self.pid)
        # name = self._name_display.display(center_person)
        # title = "Descendant SpaceTree for " + name

        ###################################################################################
        # check/create output directory

        if not os.path.isdir(self.dest_path):
            prompt = QuestionDialog2(
                _("Invalid Destination Directory"),
                _(
                    "Destination Directory %s does not "
                    "exist\nDo you want to attempt to "
                    "create it."
                )
                % self.dest_path,
                _("_Yes"),
                _("_No"),
                parent=self.user.uistate.window,
            )
            if prompt.run():
                try:
                    os.mkdir(self.dest_path)
                except OSError as err:
                    ErrorDialog(
                        _("Failed to create %s: %s")
                        % (self.dest_path, str(err)),
                        parent=self.user.uistate.window,
                    )
                    return
            else:
                return

        elif not os.access(self.dest_path, os.R_OK | os.W_OK | os.X_OK):
            ErrorDialog(
                _("Permission problem"),
                _(
                    "You do not have permission to write under the "
                    "directory %s\n\nPlease select another directory "
                    "or correct the permissions."
                )
                % self.dest_path,
                parent=self.user.uistate.window,
            )
            return

        plugin_dir = os.path.dirname(__file__)
        proto = ""
        proto_file = os.path.join(plugin_dir, "proto", "descendant_tree.html")
        try:
            with io.open(proto_file, "r", encoding="utf8") as f:
                proto = f.read()
        except IOError as e:
            ErrorDialog(
                _("Failed to read proto file %s: %s") % (proto_file, str(e)),
                parent=self.user.uistate.window,
            )
            return

        html_out = os.path.join(self.dest_path, self.dest_file)

        if os.path.isfile(html_out):
            prompt = QuestionDialog2(
                _("File already exists"),
                _(
                    "Destination file %s already exists.\n"
                    "Do you want to overwrite?"
                )
                % (html_out),
                _("_Yes"),
                _("_No"),
                parent=self.user.uistate.window,
            )
            if not prompt.run():
                return

        # populate people_map
        self._populate_people_map(self.pid, [])
        # self._dump_people_map()
        # generate JSON data
        ged_data = self._generate_descendant_json(self.pid)

        # write html file
        try:
            with io.open(html_out, "w", encoding="utf8") as fp:
                # Generate HTML File, replacing ___GED_DATA___ with ged_data
                outstr = proto.replace("___GED_DATA___", ged_data)
                outstr = self._i18n_html(outstr)
                fp.write(outstr)

        except IOError as msg:
            ErrorDialog(
                _("Failed writing file: ") + "%s: %s" % (html_out, str(msg)),
                parent=self.user.uistate.window,
            )
            return

    def _i18n_html(self, proto):
        """
        Replace the i18n placeholder strings in the proto file with
        the translated strings.
        """

        # IMPORTANT: Note thet help text lines also contain substitutions, which will be resolved
        # Translation should not translate the placeholders.

        html_text_subs = [
            (
                "___DESCENDANTS_OF___",
                html.escape(_("Descendants of")),
            ),
            (
                "___HELP_TITLE___",
                html.escape(_("How to Use the DescendantSpaceTree Viewer")),
            ),
            (
                "___HELP_TEXT1___",
                html.escape(
                    _(
                        "For the best viewing experience, maximize your "
                        "browser window to use the entire screen and reload "
                        "this page.  The viewer is fitted to your screen size."
                    )
                ),
            ),
            (
                "___HELP_TEXT2___",
                html.escape(
                    _(
                        "Click on a node to focus on a descendant and expand "
                        "any children."
                    )
                ),
            ),
            (
                "___HELP_TEXT3___",
                html.escape(
                    _(
                        "Click and drag anywhere on the viewer to position "
                        "the descendant tree."
                    )
                ),
            ),
            (
                "___HELP_TEXT4___",
                html.escape(
                    _(
                        "Click on the reset button ___HELP_RESET_BUTTON___ to "
                        "reset back to the starting descendant."
                    )
                ),
            ),
            (
                "___HELP_TEXT5___",
                html.escape(
                    _(
                        "Search for a person by typing into the search box.  "
                        "At least three characters are required to search.  "
                        "Click on any of the suggestions to quickly navigate "
                        "to that person.  A person may appear more than once "
                        "in a search, a plus sign (+) after the name "
                        "indicates that person appears as a spouse."
                    )
                ),
            ),
            (
                "___HELP_TEXT6___",
                html.escape(
                    _(
                        "A descendant and any spouses are listed in the "
                        "same node.  Children of all of the descendant's "
                        "families are grouped together."
                    )
                ),
            ),
            (
                "___HELP_TEXT7___",
                html.escape(
                    _(
                        "Persons born after a specified date may not display "
                        "their birth or death dates."
                    )
                ),
            ),
            (
                "___HELP_TEXT8___",
                html.escape(
                    _(
                        "Person nodes are colored to indicate the number of "
                        "children, the deeper tint of the coloring, the "
                        "greater number of children."
                    )
                ),
            ),
            (
                "___HELP_TEXT9___",
                html.escape(
                    _(
                        "The currently selected descendant and all of the "
                        "ancestors of that person are highlighted in yellow."
                    )
                ),
            ),
            (
                "___HELP_TEXT10___",
                html.escape(
                    _(
                        "A person may occur in different branches.  This is "
                        "usually because of inter-family marriages (such as "
                        "that of cousins.)  In this case, a button will also "
                        "appear for that person,  ___NAV_BUTTON_CONTINUE___ "
                        "or ___NAV_BUTTON_ALT___  to navigate the "
                        "other branch.  Only one branch will expand "
                        "descendants of this person. "
                    )
                ),
            ),
            (
                "___HELP_CREDITS___",
                html.escape(
                    _(
                        "The following open source projects are used in "
                        "building this viewer, see source code LICENSE*.txt "
                        "files for complete licenses and required notices."
                    )
                ),
            ),
        ]

        for placeholder, text in html_text_subs:
            proto = proto.replace(placeholder, text)

        # replace the placeholders in the help text
        proto = proto.replace(
            "___HELP_RESET_BUTTON___", "<b> &nbsp;  &#10227;  &nbsp; </b>"
        )
        proto = proto.replace(
            "___NAV_BUTTON_CONTINUE___",
            "<b>" + DescendantSpaceTreeReport.NAV_BUTTON_CONTINUE + "</b>",
        )
        proto = proto.replace(
            "___NAV_BUTTON_ALT___",
            "<b>" + DescendantSpaceTreeReport.NAV_BUTTON_ALT + "</b>",
        )

        # replace the search input box placeholder
        proto = proto.replace(
            "___SEARCH___",
            _("Search. . ."),
        )

        return proto


# ------------------------------------------------------------------------
#
# DescendantSpaceTreeOptions
#
# ------------------------------------------------------------------------
class DescendantSpaceTreeOptions(MenuReportOptions):
    """
    Defines options and provides handling interface.

        This report needs the following parameters (class variables)
        that come in the options class.
        pid              - Center person ID
        max_gen          - Maximum number of generations to include.
        birth_year_limit - Maximum birth year to show birth/death years
        dest_path        - Destination directory
        dest_file        - Destination file name

    """

    def __init__(self, name, dbase):
        self._dbase = dbase
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        """
        Add options to the menu for the descendant indented tree report.
        """
        category = _("Report Options")
        add_option = partial(menu.add_option, category)

        #
        pid = PersonOption(_("Center Person"))
        pid.set_help(_("The center person for the report"))
        add_option("pid", pid)

        #
        max_gen = NumberOption(
            _("Include Generations"), DEF_GEN, MIN_GEN, MAX_GEN
        )
        max_gen.set_help(
            _("The number of generations to include in the report")
        )
        add_option("max_gen", max_gen)

        #
        branch_pref = EnumeratedListOption(
            _("Branch to expand when duplicated"), PATRIARCHAL_LINE
        )
        branch_pref.set_items(
            [
                (PATRIARCHAL_LINE, PATRIARCHAL_LINE),
                (MATRIARCHAL_LINE, MATRIARCHAL_LINE),
            ]
        )
        branch_pref.set_help(
            _(
                "When a descendant appears more than once, prefer"
                " the selected lineage to expand descendancy line"
            )
        )
        add_option("branch_pref", branch_pref)

        #
        birth_year_limit = NumberOption(
            _("Maximum display birth year"), DEF_BIRTH_YEAR, 0, 2400
        )
        birth_year_limit.set_help(
            _("Birth/date dates will not be displayed after this year")
        )
        add_option("birth_year_limit", birth_year_limit)

        #
        dest_path = DestinationOption(
            _("Destination"), config.get("paths.website-directory")
        )
        dest_path.set_help(_("The destination path for generated files."))
        dest_path.set_directory_entry(True)
        add_option("dest_path", dest_path)

        #
        dest_file = StringOption(
            _("Destination File"), "DescendantSpaceTree.html"
        )
        dest_file.set_help(_("The destination file name for the report."))
        add_option("dest_file", dest_file)
