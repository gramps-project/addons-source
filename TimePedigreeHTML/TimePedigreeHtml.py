""" 
    TimePedigreeHtml - a plugin for GRAMPS - version 0.0.2
    Outcome is an HTML file showing a pedigree with time scale
"""
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021  Manuela Kugel (gramps@ur-ahn.de)
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

# Version 0.0.2:
# - Limit of recursion with level highter than 100 to avoid endless loop on
#   error data
# - Person boxes with x component less or equal 0
# - International date format
# - Usage of symbols according to gramps class gramps.gen.utils.symbols
# - Additional scale on the right side
# - Added README.txt for license of background image and a js code snippet


import io
import math
import os
import shutil
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale, USER_PLUGINS
from gramps.gen.lib.person import Person
from gramps.gen.plug.report import (Report, 
                                    MenuReportOptions, 
                                    stdoptions)
from gramps.gen.plug.menu import (ColorOption,
                                  NumberOption,
                                  PersonOption,
                                  DestinationOption,
                                  StringOption,
                                  BooleanOption)
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback)
from gramps.gen.utils.symbols import Symbols
from gramps.gui.dialog import ErrorDialog
from gramps.plugins.webreport.common import get_gendex_data


try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


class TimePedigreeHtml(Report):
    """ class for add on """

    def __init__(self, database, options, user):
        Report.__init__(self, database, options, user)
        menu = options.menu
        self.db = database
        self.pid_list = {}
        self.pair_list = {}

        # General
        self.root_pid = menu.get_option_by_name('pid').get_value()
        self.root_pid_year = int(
            menu.get_option_by_name('pid_year').get_value()
        )
        dest_path = menu.get_option_by_name('dest_path').get_value()
        dest_file = menu.get_option_by_name('dest_file').get_value()
        self.age_difference = int(
            menu.get_option_by_name('age_diff').get_value()
        )
        self.set_locale(options.menu.get_option_by_name('trans').get_value())
        stdoptions.run_date_format_option(self, menu)
        self.rlocale = self._locale

        # What
        self.show_id = bool(menu.get_option_by_name('show_id').get_value())
        self.opt = bool(menu.get_option_by_name('optimize').get_value())

        # Color
        self.m_bg = menu.get_option_by_name('m_bg').get_value()
        self.w_bg = menu.get_option_by_name('w_bg').get_value()

        # Size
        self.year_to_pixel_factor = int(
            menu.get_option_by_name('year_to_pixel_factor').get_value()
        )
        self.offset_y = int(menu.get_option_by_name('offset_y').get_value())
        self.offset_x = int(menu.get_option_by_name('offset_y').get_value())
        self.box_width = int(menu.get_option_by_name('box_width').get_value())
        self.box_offset_x = int(
            menu.get_option_by_name('box_offset_x').get_value()
        )
        self.vert_length = int(
            menu.get_option_by_name('vert_length').get_value()
        )
        self.scale_x = int(menu.get_option_by_name('scale_x').get_value())

        # File and directory issues
        self.dest_html = os.path.join(dest_path, os.path.basename(dest_file))
        utils_path = os.path.join(USER_PLUGINS, "TimePedigreeHTML", "utils")
        js_source = os.path.join(utils_path, "wz_jsgraphics.js")
        js_target = os.path.join(dest_path, "wz_jsgraphics.js")
        jpg_source = os.path.join(utils_path, "bg.jpg")
        jpg_target = os.path.join(dest_path, "bg.jpg")
        jpg_source = os.path.join(utils_path, "README.txt")
        jpg_target = os.path.join(dest_path, "README.txt")
        if not os.path.isdir(dest_path):
            os.makedirs(dest_path) # create dir if necessary
        if not os.path.isfile(js_target):
            shutil.copyfile(js_source,  js_target)
        if not os.path.isfile(jpg_target):
            shutil.copyfile(jpg_source, jpg_target)

    # ---------------------------------------------------------------- *
    # ----- W R I T E _ R E P O R T ---------------------------------- *
    # ---------------------------------------------------------------- *
    def write_report(self):
        """ This method is called from "outside" to trigger the plugins
        functionality """

        # Root person details
        self.pid_list = { self.root_pid: { "children":[],
                                           "level"   : 0,
                                           "parent"  : [],
                                           "siblings": [], # not relevant
                                           "subtree" : [self.root_pid]
                                         }
                        }
        self.get_person_details(self.root_pid, True)

        # Collect all of the root persons descendants
        siblings = self.get_person_list_recursive(self.root_pid, 0)
        for sibling in siblings:
            self.pid_list[sibling]["siblings"] = siblings

        # Calculate x-Coordinate of all persons
        self.calculate_x()
        if self.opt:
            self.optimize() # Optimization of x coordinates

        # Collect all mother-father pairs
        self.get_pairs()

        # HTML output
        html = self.out_intro()
        html = self.out_lines_html(html)
        for pid in self.pid_list:
            if len(self.pid_list[pid]["parent"]) > 0 or pid == self.root_pid:
                html = self.out_person_html(pid, html)
        html = self.out_extro(html)

        try:
            with io.open(self.dest_html, 'w', encoding='UTF-8') as file:
                file.write(html) # Generate HTML File

        except IOError as msg:
            ErrorDialog(_("Failed writing " + self.dest_html + ": " + str(msg)),
                        parent=self._user.uistate.window)

    def out_intro(self):
        """ Draws the first part of html file """

        html = (  "<html>\n"
                + "<head>\n"
                + "<meta http-equiv='Content-Type' content='text/html; "
                + "charset=utf-8'/>\n\n"
                + "<script type='text/javascript' src='wz_jsgraphics.js'>"
                + "</script>\n\n"
                + "<style>\n"
                + "div.box {\n"
                + "  padding:          3px;\n"
                + "  font-size:        10px;\n"
                + "  font-family:      Arial,Helvetica Neue,Helvetica,"
                + "sans-serif;\n"
                + "  width:            " + str(self.box_width) + "px;\n"
                + "  position:         absolute;\n"
                + "  z-index:          0;\n"
                + "  box-shadow:       3px 3px 3px #808080;\n"
                + "}\n"
                + "div.personbox_m {"
                + "  background-color: " + self.m_bg + ";\n"
                + "  border:           1px solid black;\n"
                + "}\n"
                + "div.personbox_w {\n"
                + "  background-color: " + self.w_bg + ";\n"
                + "  border:           1px solid white;\n"
                + "}\n"
                + "div#main {\n"
                + "  z-index:           -10; \n"
                + "  background-image:  url('bg.jpg');\n"
                + "  background-repeat: no-repeat;\n"
                + "}\n"
                + "</style>\n"
                + "</head>\n\n"
                + "<body style='margin:0;'>\n"
        )
        return html

    def out_extro(self, html):
        """ Draws the last part of html file """

        html += "</body>\n</html>\n"
        return html

    def out_lines_html(self, html):
        """ Draws Scale and each line between boxes in HTML """

        x_max = 0
        y_max = 0
        x_max_year = 0
        x_min_year = 0

        for pid in self.pid_list:
            x_max      = max(x_max,      self.pid_list[pid]["x"])
            y_max      = max(y_max,      self.pid_list[pid]["y"])
            x_max_year = max(x_max_year, self.pid_list[pid]["birthyear"])

        x_min_year = self.pid_list[self.root_pid]["birthyear"]
        x_max = int(x_max) + self.box_width + self.offset_x
        # 60px is assumption of a box height without partner
        y_max = int(y_max) + 60 + self.offset_y

        # Pre
        html += ( "<div id='main' style='width:" + str(x_max)
                + "; height:" + str(y_max)
                + "; background-size:" + str(x_max) + "px "
                + str(y_max) + "px;'>\n"
        )

        # Draw Scales (vertical lines)
        sc_x = self.scale_x
        y_min = self.offset_y - 10
        if y_min < 0:
            y_min = 0
        html += ( "<script type='text/javascript'>\n"
                + "<!--\n"
                + "function draw()\n"
                + "{\n"
                + "  var jg = new jsGraphics('main');\n"
                + "  jg.setColor('#ffffff');\n"
                # Scale Verticale left
                + "  jg.drawLine(" + str(sc_x) + ", "
                + str(y_min) + ", " 
                + str(sc_x) + ", " + str(y_max - self.offset_y) + ");\n"
                # Scale Verticale Right
                + "  jg.drawLine(" + str(x_max - sc_x) + ", " 
                + str(y_min) + ", " 
                + str(x_max - sc_x) + ", " + str(y_max - self.offset_y) + ");\n"
        )

        # Draw scale tick on each year ending on 0 or 5
        for year in range(x_min_year, x_max_year + 5):
            if math.ceil(year/5) == year/5:
                yyy = ( (year-x_min_year) * self.year_to_pixel_factor
                    + self.offset_y
                )
                html += ( "  jg.drawLine(" + str(sc_x) + ", " + str(yyy) + ", "
                        + str(sc_x + 10) + ", " + str(yyy) + ");"
                        + "  jg.drawString('" + str(year) + "',"
                        + str(sc_x + 12) + "," + str(yyy - 7) + ");"
                        + "  jg.drawLine(" + str(x_max - sc_x) + ", " 
                        + str(yyy) + ", "
                        + str(x_max - sc_x - 10) + ", " + str(yyy) + ");"
                        + "  jg.drawString('" + str(year) + "',"
                        + str(x_max - sc_x - 43) + "," + str(yyy - 7) + ");"
                )

        # Draw Lines between people
        html = html + "  jg.setColor('#000000');\n" # black

        for pid in self.pid_list:
            if pid == self.root_pid:
                continue
            if len(self.pid_list[pid]["parent"]) == 0:
                continue # Other part of parents

            parent_pid = self.pid_list[pid]["parent"][0]
            html += ( "  jg.drawLine("
                    + str(self.pid_list[pid]["x"] + self.box_width/2) + ", "
                    + str(self.pid_list[pid]["y"]) + ", "
                    + str(self.pid_list[parent_pid]["x"]
                    + self.box_width/2) + ", "
                    + str(self.pid_list[parent_pid]["y"]
                    + self.vert_length) + ");\n"
                    + "  jg.drawLine("
                    + str(self.pid_list[parent_pid]["x"]
                    + self.box_width/2) + ", "
                    + str(self.pid_list[parent_pid]["y"] + 5) + ", "
                    + str(self.pid_list[parent_pid]["x"]
                    + self.box_width/2) + ", "
                    + str(self.pid_list[parent_pid]["y"]
                    + self.vert_length) + ");\n"
            )
            html += "  jg.paint();\n"

        # Post
        html += ( "}\n"
                + "draw();\n"
                + "//-->\n"
                + "</script>\n"
        )

        return html

    def out_person_html(self, pid, html):
        """ draws a box including most important data of a person """
        symbols = Symbols()
        birth_sym = symbols.get_symbol_for_html(symbols.SYMBOL_BIRTH)
        marr_sym  = symbols.get_symbol_for_html(symbols.SYMBOL_MARRIAGE)
        death_sym = symbols.get_death_symbol_for_html(symbols.DEATH_SYMBOL_SHADOWED_LATIN_CROSS)

        if self.pid_list[pid]["gender"] == Person.MALE:
            box_class = "box personbox_m"
        else:
            box_class = "box personbox_w"

        html += ( "<div class='" + box_class + "' id='" + pid
                + "' style='left:"
                + str(self.pid_list[pid]["x"]) + "px;top:"
                + str(self.pid_list[pid]["y"]) + "px;'>\n"
                + "<b>" + self.pid_list[pid]["firstname"] + "</b>\n"
                + "<br><b>" + self.pid_list[pid]["name"] + "</b>\n"
                + "<br>" + birth_sym + " " + self.pid_list[pid]["birthday"]
                + " " + self.pid_list[pid]["birthplace"] + "\n"
        )
        if self.pid_list[pid]["deathday"]:
            html += ( "<br>" + death_sym + " " + self.pid_list[pid]["deathday"]
                    + " " + self.pid_list[pid]["deathplace"] + "\n"
            )

        if pid in self.pair_list:
            for partner_id in self.pair_list[pid]:
                html += "<hr>"

                if self.pid_list[pid]["marr"][partner_id]:
                    if ( self.pid_list[pid]["marr"][partner_id][0] != "" or
                            self.pid_list[pid]["marr"][partner_id][1] != "" ):
                        html += ( "<font size=+1>" + marr_sym + "</font> "
                                + self.pid_list[pid]["marr"][partner_id][0]
                                + " "
                                + self.pid_list[pid]["marr"][partner_id][1]
                                + "<br>"
                        )

                html += ( "<b>" + self.pid_list[partner_id]["firstname"]
                        + " " + self.pid_list[partner_id]["name"] + "</b>\n"
                        + "<br>" + birth_sym + " " 
                        + self.pid_list[partner_id]["birthday"]
                        + " " + self.pid_list[partner_id]["birthplace"] + "\n"
                )
                if self.pid_list[partner_id]["deathday"]:
                    html += ( "<br>" + death_sym + " " 
                            + self.pid_list[partner_id]["deathday"] + " " 
                            + self.pid_list[partner_id]["deathplace"] + "\n"
                    )

        if self.show_id:
            html += ( "<div style='position:absolute;top:-12px;right:0px;'>"
                    + pid + "</div>"
            )

        html += "</div>\n"
        return html

    # ---------------------------------------------------------------- *
    # ----- O P T I M I Z E ------------------------------------------ *
    # ---------------------------------------------------------------- *
    def optimize(self):
        """ recalculate x coordinates to narrow boxes if possible """

        # Initialization
        year_x_left = {}  # each tuple is year: x

        # Loop at every leaf
        for pid_left in self.pid_list:
            if len(self.pid_list[pid_left]["children"]) == 0: # is leaf

                # find pid of next leaf
                found = False
                pid_right = 0
                for pid_right in self.pid_list:
                    if pid_right == pid_left:
                        found = True
                        continue
                    if not found:
                        continue
                    if len(self.pid_list[pid_right]["children"]) == 0:
                        break # is next leaf
                if pid_right == pid_left:
                    continue # last leaf

                # find all ancestors of pid_left and pid_right, who are
                # not ancestors of both
                pid_left_path = [pid_left]
                pid_right_path = [pid_right]

                pid_tmp = pid_left
                while pid_tmp != self.root_pid:
                    pid_tmp = self.pid_list[pid_tmp]["parent"][0]
                    pid_left_path.append(pid_tmp)

                pid_tmp = pid_right
                while pid_tmp != self.root_pid:
                    pid_tmp = self.pid_list[pid_tmp]["parent"][0]
                    pid_right_path.append(pid_tmp)

                pid_left_path_tmp = pid_left_path.copy()
                pid_right_path_tmp = pid_right_path.copy()
                pid_common = "" # this is the closest common ancestor
                for pid_tmp in pid_left_path_tmp:
                    if pid_tmp in pid_right_path_tmp:
                        if pid_common == "":
                            pid_common = pid_tmp
                        pid_left_path.remove(pid_tmp)
                        pid_right_path.remove(pid_tmp)

                # calculate year_min and year_max
                # assuming children are ordered by year of birth, then
                #   year_min is year of birth of child of common of left path
                # year max is maximum year of birth of both leafs
                year_min = (
                    self.pid_list[
                        self.pid_list[pid_common]["children"][0]]["birthyear"]
                         - 2
                )
                year_max = max( self.pid_list[pid_left]["birthyear"],
                                self.pid_list[pid_right]["birthyear"] ) + 8

                # calculate x + box_width and offset for left path and
                # x for right path for each year including line space
                pid_old = ""
                for pid_tmp in pid_left_path:
                    year_birth = self.pid_list[pid_tmp]["birthyear"]
                    x_tmp = int( self.pid_list[pid_tmp]["x"]
                               + self.box_width + self.box_offset_x
                    )
                    for year_tmp in range(year_birth - 2, year_birth + 10):
                        year_x_left[year_tmp] = x_tmp
                    pid_old = pid_tmp

                year_x_right = {}
                pid_old = ""
                for pid_tmp in pid_right_path:
                    # boxes (including 2 years before and about 2 years after)
                    year_birth = self.pid_list[pid_tmp]["birthyear"] # y1
                    x_tmp = int( self.pid_list[pid_tmp]["x"] )       # x1
                    for year_tmp in range(year_birth - 2, year_birth + 10):
                        year_x_right[year_tmp] = x_tmp

                    # lines between boxes
                    if pid_old != "":
                        # y2
                        year_birth_old = self.pid_list[pid_old]["birthyear"]
                        # x2
                        x_old = int( self.pid_list[pid_old]["x"] )
                        # y
                        for year_tmp in range(year_birth + 11,
                                              year_birth_old -2):
                            # x = x2 - ((y2-y)/(y2-y1))*(x2-x1)
                            # x
                            year_x_right[year_tmp] = int(
                                x_old - ((year_birth_old - year_tmp)
                                / (year_birth_old - year_birth))
                                * (x_old - x_tmp)
                            )

                    pid_old = pid_tmp

                # calculate gap (min difference each year)
                delta = 99999
                for year_tmp in range(year_min, year_max):
                    if year_tmp in year_x_left:
                        if year_tmp in year_x_right:
                            delta = min(delta, year_x_right[year_tmp]
                                      - year_x_left[year_tmp]
                                    )
                        # else: not relevant
                    else:
                        if year_tmp in year_x_right:
                            delta = min(delta, year_x_right[year_tmp]
                                      - self.offset_x
                                    )
                        # else: not relevant

                # if gap is greater than 0 move right SUBTREE (not only
                # path) below  person of last element in pid_right_path
                # gap pixel to the left (smaller: x = x - gap)
                # T O D O : why could there be negative delta?
                if delta > 0:
                    pid_root_subtree = pid_right_path[-1] # last list element
                    for pid_tmp in self.pid_list[pid_root_subtree]["subtree"]:
                        self.pid_list[pid_tmp]["x"] -= delta

                    # recalculate common ancestors and move the to the new
                    # center between oldest and youngest child in case this
                    # is possible (are there other "formerly" considered
                    # relatives with this new x coordinate)
                    pid_tmp = pid_right
                    while pid_tmp != self.root_pid:
                        pid_tmp = self.pid_list[pid_tmp]["parent"][0]
                        x_max = self.pid_list[self.pid_list[
                                        pid_tmp]["children"][0]]["x"]
                        x_min = self.pid_list[self.pid_list[
                                        pid_tmp]["children"][-1]]["x"]
                        x_new = int((x_max + x_min) / 2)
                        year_birth = self.pid_list[pid_tmp]["birthyear"]
                        x_max_left = 0

                        for year_tmp in range(year_birth - 2, year_birth + 10):
                            if year_tmp in year_x_left:
                                x_max_left = max(year_x_left[year_tmp],
                                                 x_max_left
                                             )
                        if x_max_left > x_new:
                            x_new = x_max_left
                        self.pid_list[pid_tmp]["x"] = x_new

    # ---------------------------------------------------------------- *
    # ----- X - c a l c u l a t i o n s ------------------------------ *
    # ---------------------------------------------------------------- *
    def calculate_x(self):
        """ calculate x coordinate of each person box """
        x_max = 0

        # Set x of leafs (last children in hierarchy)
        for pid in self.pid_list:
            if len(self.pid_list[pid]["children"]) == 0:
                x_max = self.calculate_x_leaf_children(pid, x_max)

        # adjust all parents
        something_changed = True
        while something_changed:
            something_changed = False
            for pid in self.pid_list:
                if self.pid_list[pid]["x"] == 0:
                    if self.calculate_x_adjust_parents(pid):
                        something_changed = True

    def calculate_x_adjust_parents(self, pid):
        """ returns, whether something changed (True) or not (False) """

        # Make sure, x-coordinates of all children are set
        for cid in self.pid_list[pid]["children"]:
            if self.pid_list[cid]["x"] == 0:
                return False

        c_list = self.pid_list[pid]["children"]
        last_child_idx = len(c_list) - 1
        x_min = self.pid_list[c_list[0]]["x"]
        x_max = self.pid_list[c_list[last_child_idx]]["x"]
        self.pid_list[pid]["x"] = int((x_min + x_max) / 2)
        return True

    def calculate_x_leaf_children(self, pid, x_max):
        """ calculate x coordinate of a child """
        x_max = max(self.offset_x, x_max)
        self.pid_list[pid]["x"] = x_max
        x_max = x_max + self.box_width + self.box_offset_x
        return x_max

    # ---------------------------------------------------------------- *
    # ----- B u i l d   D a t a   M o d e l -------------------------- *
    # ---------------------------------------------------------------- *
    def get_person_list_recursive(self, pid_old, level):
        """
        The list of all involved persons is built recursively here.
        There is no special order, just a list of IDs in self.pid_list
        """
        # Make recursion end at some time to avoid endless loop at wrong data
        if level > 100:
            return []

        person = self.db.get_person_from_gramps_id(pid_old)
        siblings_new  = []
        new_list_pid  = []
        new_list_year = []

        # Order children by year of birth, possibly children from
        # different families ("Halbgeschwister")
        for family_handle in person.get_family_handle_list():
            family = self.db.get_family_from_handle(family_handle)
            if family:
                for child_ref in family.get_child_ref_list():
                    (new_list_pid, new_list_year) = self.update_lists(
                        child_ref, pid_old, new_list_pid, new_list_year
                    )

        # Continue processing recursion
        for pid in new_list_pid:
            level = level + 1
            siblings_new.append(pid)

            # assign child to parent
            self.pid_list[pid_old]["children"].append(pid)

            # create list entry for child
            self.pid_list[pid] = { "children": [],
                                  "level"   : level,
                                  "parent"  : [pid_old],
                                  "siblings": [],
                                  "subtree" : [pid]
                                }
            self.get_person_details(pid, True)

            # get children of child
            siblings = self.get_person_list_recursive(pid, level)
            for pid_tmp in self.pid_list[pid]["subtree"]:
                self.pid_list[pid_old]["subtree"].append(pid_tmp)

            level = level - 1

            for sibling in siblings:
                self.pid_list[sibling]["siblings"] = siblings

        return siblings_new

    def update_lists(self, child_ref, pid_old, new_list_pid, new_list_year):
        """ fill new_list_pid and new_list_year """

        child = self.db.get_person_from_handle(child_ref.ref)
        cid = child.get_gramps_id()
        if child:
            birth_evt = get_birth_or_fallback(self.db, child)

            # get year of birth
            year = 0
            if birth_evt:
                bth = (birth_evt.get_date_object().
                        to_calendar("gregorian")
                    )
                if bth:
                    year = bth.get_year()

            if year == 0:
                year = (self.pid_list[pid_old]["birthyear"]
                        + self.age_difference
                )

            # sort childPid at the correct position
            cnt = 0
            for year_in_list in new_list_year:
                if year_in_list > year and cid not in new_list_pid:
                    new_list_pid.insert(cnt, cid)
                    new_list_year.insert(cnt, year)
                    break
                cnt = cnt + 1

            if cnt == len(new_list_pid) and cid not in new_list_pid:
                new_list_pid.append(cid)
                new_list_year.append(year)

        return (new_list_pid, new_list_year)

    def get_pairs(self):
        """ List self.pid_list would change its size => no loop possible"""
        tmp_list = self.pid_list.copy()

        for pid in tmp_list:
            if pid == self.root_pid:
                continue

            # [0] is always there except for root
            if len(self.pid_list[pid]["parent"]) > 1:
                partner_id = self.pid_list[pid]["parent"][1]
                old_id      = self.pid_list[pid]["parent"][0]

                if old_id in self.pair_list:
                    if partner_id not in self.pair_list[old_id]:
                        self.pair_list[old_id].append(partner_id)
                else:
                    self.pair_list[old_id] = [partner_id]

                # Fill (new) persons details
                if partner_id not in self.pid_list:
                    self.pid_list[partner_id] = { "children":[],
                                                  "level": 0,
                                                  "parent": []
                                                }
                    self.get_person_details(partner_id, False)

    def get_person_details(self, pid, with_parents):
        """ read details for each person from database """
        person = self.db.get_person_from_gramps_id(pid)

        # ----- Name ----- *
        name_object = person.get_primary_name()
        self.pid_list[pid]["name"]      = name_object.get_surname()
        self.pid_list[pid]["firstname"] = name_object.first_name

        # ----- Birth ----- *
        self.pid_list[pid]["birthyear"]  = 0
        self.pid_list[pid]["birthday"]   = ""
        dob, self.pid_list[pid]["birthplace"] =\
            get_gendex_data(self.db, person.get_birth_ref())

        birth_evt = get_birth_or_fallback(self.db, person)
        if birth_evt:
            bth = birth_evt.get_date_object().to_calendar("gregorian")
            if bth:
                self.pid_list[pid]["birthyear"] = bth.get_year()
                self.pid_list[pid]["birthday"] = self.rlocale.get_date(bth)

        if pid == self.root_pid:
            if self.pid_list[pid]["birthyear"] == 0:
                self.pid_list[pid]["birthyear"] = self.root_pid_year
        if self.pid_list[pid]["birthyear"] == 0:
            for parent in self.pid_list[pid]["parent"]:
                self.pid_list[pid]["birthyear"] = (
                    self.pid_list[parent]["birthyear"]
                  + self.age_difference
                )
                break

        # ----- Death ----- *
        self.pid_list[pid]["deathday"]   = ""
        dod, self.pid_list[pid]["deathplace"] =\
            get_gendex_data(self.db, person.get_death_ref())

        death_evt = get_death_or_fallback(self.db, person)
        if death_evt:
            dth = death_evt.get_date_object().to_calendar("gregorian")
            if dth:
                self.pid_list[pid]["deathday"] = self.rlocale.get_date(dth)

        # ----- Gender ----- *
        self.pid_list[pid]["gender"] = person.gender

        # ----- Coordinates ----- *
        self.pid_list[pid]["x"] = 0
        self.pid_list[pid]["y"] = (
            ( self.pid_list[pid]["birthyear"]
           - self.pid_list[self.root_pid]["birthyear"])
           * self.year_to_pixel_factor
           + self.offset_y
        )

        # ----- Other part of parents ----- *
        self.pid_list[pid]["ehe"] = {}
        if with_parents:
            family_hdl = person.get_main_parents_family_handle()
            if family_hdl:
                family_obj = self.db.get_family_from_handle(family_hdl)
                if family_obj:
                    mother_hdl = family_obj.get_mother_handle()
                    if mother_hdl:
                        mother_obj = (
                            self.db.get_person_from_handle(mother_hdl) # !!!
                        )
                        if mother_obj:
                            mother_pid = mother_obj.get_gramps_id()
                            if mother_pid:
                                if len(self.pid_list[pid]["parent"]) > 0:
                                    if self.pid_list[pid]["parent"][0] != (
                                        mother_pid
                                    ):
                                        self.pid_list[pid]["parent"].\
                                            append(mother_pid)
                    father_hdl = family_obj.get_father_handle()
                    if father_hdl:
                        father_obj = self.db.get_person_from_handle(father_hdl)
                        if father_obj:
                            father_pid = father_obj.get_gramps_id()
                            if father_pid:
                                if len(self.pid_list[pid]["parent"]) > 0:
                                    if self.pid_list[pid]["parent"][0] \
                                        != father_pid:
                                        self.pid_list[pid]["parent"].\
                                            append(father_pid)

        # ----- Marriage ----- *
        self.pid_list[pid]["marr"] = {}
        family_hdl_list = person.get_family_handle_list()
        for family_hdl in family_hdl_list:
            if family_hdl:
                family_obj = self.db.get_family_from_handle(family_hdl)
                if family_obj:
                    marrplace  = ""
                    marrday    = ""
                    marrperson = ""
                    event_ref_list = family_obj.get_event_list()
                    for event_ref in event_ref_list:
                        if event_ref:
                            event = self.db.get_event_from_handle(event_ref)
                            if event.get_type() == (_('Marriage')):
                                mar_d = event.get_date_object().\
                                    to_calendar("gregorian")
                                if mar_d:
                                    marrday = self.rlocale.get_date(mar_d)
                                if event.place:
                                    place_obj = self.db.get_place_from_handle(
                                        event.place
                                    )
                                    if place_obj:
                                        marrplace = place_obj.get_name().\
                                            get_value()
                    wife_pid = ""
                    wife_hdl = family_obj.get_mother_handle()
                    if wife_hdl:
                        wife_obj = self.db.get_person_from_handle(wife_hdl)
                        if wife_obj:
                            wife_pid = wife_obj.get_gramps_id()
                            if wife_pid != pid:
                                marrperson = wife_pid
                    husband_pid = ""
                    husband_hdl = family_obj.get_father_handle()
                    if husband_hdl:
                        husband_obj = self.db.get_person_from_handle(
                            husband_hdl
                        )
                        if husband_obj:
                            husband_pid = husband_obj.get_gramps_id()
                            if husband_pid != pid:
                                marrperson = husband_pid

                    if marrplace != "" or marrday != "" or marrperson != "":
                        self.pid_list[pid]["marr"].update(
                            {marrperson:[marrday, marrplace]}
                        )


########################################################################
class TimePedigreeHtmlOptions(MenuReportOptions):
    """ class to set options menu """
    def __init__(self, name, dbase):
        # pmgr = BasePluginManager.get_instance()
        self.db = dbase
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        """ Add options to the menu for the ancestral fan chart report. """
        # ---------------------------- *
        category_general = _("General")

        pid = PersonOption(_("Center Person"))
        pid.set_help(_("The center person for the report"))
        menu.add_option(category_general, "pid", pid)

        pid_year = NumberOption(_("Year of Birth of Center Person"),
            0, -9999, 9999
        )
        pid_year.set_help(_("The year of birth of the center person. "
                            "Estimate a year if unknown")
                         )
        menu.add_option(category_general, "pid_year", pid_year)

        dest_path = DestinationOption(_("Destination directory"),
                                      config.get('paths.website-directory')
                                     )
        dest_path.set_help(_("Path for generated files"))
        dest_path.set_directory_entry(True)
        menu.add_option(category_general, "dest_path", dest_path)

        dest_file = StringOption(_("Filename"), "index.html")
        dest_file.set_help(_("The destination file name for html content."))
        menu.add_option(category_general, "dest_file", dest_file)

        age_diff = StringOption(_("Default Age"), "25")
        age_diff.set_help(_("Default age of parent when child is born "
            "with unknown year of birth")
        )
        menu.add_option(category_general, "age_diff", age_diff)

        locale_opt = stdoptions.add_localization_option(menu, category_general)
        stdoptions.add_date_format_option(menu, category_general, locale_opt)

        # ---------------------------- *
        category_what   = _("What to show")

        show_id = BooleanOption(_("Show GrampsID"), True)
        show_id.set_help(_("Show GrampsID on top right of the box"))
        menu.add_option(category_what, "show_id", show_id)

        optimize = BooleanOption(_("Optimize"), True)
        optimize.set_help(_("Use as little space in horizontal "
            "direction as possible")
        )
        menu.add_option(category_what, "optimize", optimize)

        # ---------------------------- *
        category_color  = _("Color")

        m_bg = ColorOption(_("Male Box Color"), "#cda476")
        m_bg.set_help(_("Box background color for male person"))
        menu.add_option(category_color, "m_bg", m_bg)

        w_bg = ColorOption(_("Female Box Color"), "#efdfcf")
        w_bg.set_help(_("Box background color for female person"))
        menu.add_option(category_color, "w_bg", w_bg)

        # ---------------------------- *
        category_size   = _("Size")

        year_to_pixel_factor = StringOption(_("Number of pixel per year"), "8")
        year_to_pixel_factor.set_help(_("How many pixel height is one year?"))
        menu.add_option(category_size, "year_to_pixel_factor",
            year_to_pixel_factor
        )

        offset_x = StringOption(_("Offset X Coordinate"), "60")
        offset_x.set_help(
            _("How many pixel are unused besides the "
            "most left and most right boxes?")
        )
        menu.add_option(category_size, "offset_x", offset_x)

        offset_y = StringOption(_("Offset Y Coordinate"), "75")
        offset_y.set_help(_("How many pixel are unused above first box?"))
        menu.add_option(category_size, "offset_y", offset_y)

        box_width = StringOption(_("Width of a box in pixel"), "140")
        box_width.set_help(_("Width of the box of a person in pixel"))
        menu.add_option(category_size, "box_width", box_width)

        box_offset_x = StringOption(_("Horizontal space "
            "between boxes in pixel"), "20"
        )
        box_offset_x.set_help(_("Minimum horizontal space "
            "between 2 boxes in pixel")
        )
        menu.add_option(category_size, "box_offset_x", box_offset_x)

        vert_length = StringOption(
            _("Length of vertical part of a line in pixel"), "100"
        )
        vert_length.set_help(_("Parent and child boxes are connected "
            "with lines. This is the length of the vertical part of "
            "the lines in pixel")
        )
        menu.add_option(category_size, "vert_length", vert_length)

        scale_x = StringOption(
            _("Number of pixel between left border and scale"), "10"
        )
        scale_x.set_help(_("Number of pixel between left border and scale"))
        menu.add_option(category_size, "scale_x", scale_x)

        # T O D O :
        # options:
        # - box frame options (curved, no border, border color...)
        # - font faces and sizes and colors
        # - with image of a relative inside or besides the box
        # - fat line below the box if there cannot be children (e.g. to young)
        # - different background image
        # - switch on/off marriage, partner
        # - form of lines: e.g. alternatively horizontal/vertical only, no
        #   diagonals
        # - color, style, width of lines between boxes
        # - turn off optimization
        # check, whether self.pair_list is really necessary
        # onclick in a box should show a hidden div with a detail form
        # Improve to fulfill pylint policies
