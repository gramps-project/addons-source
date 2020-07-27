#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020  Matthias Kemmer
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
#
"""Mass-edit the family relationship type for a group of families."""

# -------------------------------------------------
#
# GRAMPS modules
#
# -------------------------------------------------
from gramps.gui.plug import MenuToolOptions, PluginWindows
from gramps.gen.plug.menu import FilterOption
from gramps.gen.lib.familyreltype import FamilyRelType
from gramps.gen.db import DbTxn
from gramps.gen.filters import CustomFilters, GenericFilterFactory, rules
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext


# ----------------------------------------------------------------------------
#
# Tool Option Class
#
# ----------------------------------------------------------------------------
class FamilyRelationshipToolOptions(MenuToolOptions):
    """Class for creating menu options."""

    def __init__(self, name, person_id=None, dbstate=None):
        self.db = dbstate.get_database()
        MenuToolOptions.__init__(self, name, person_id, dbstate)

    def add_menu_options(self, menu):
        """Add the menu options for the tool."""
        # Get generic 'all families' filter and all custom familiy filters
        menu.filter_list = CustomFilters.get_filters("Family")
        all_families = GenericFilterFactory("Family")()
        all_families.set_name(_("All Families"))
        all_families.add_rule(rules.family.AllFamilies([]))
        all_filter_in_list = False
        for fltr in menu.filter_list:
            if fltr.get_name() == all_families.get_name():
                all_filter_in_list = True
        if not all_filter_in_list:
            menu.filter_list.insert(0, all_families)

        # family filter menu option
        fam = FilterOption(_("Family Filter"), 0)
        fam.set_help(_("Choose the set of families to process.\n"
                     "Create custom filters if empty."))
        fam.set_filters(menu.filter_list)
        menu.add_option(_("Options"), "families", fam)

        # add family relationship type menu option
        rel = FilterOption(_("Relationship Type"), 0)
        rel.set_help(_("Choose the new family relationship type.\n"
                     "Custom relationship types aren't supported."))
        rel.set_items([(0, _("Married")), (1, _("Unmarried")),
                       (2, _("Civil Union")), (3, _("Unknown"))])
        menu.add_option(_("Options"), "relationship", rel)


# ----------------------------------------------------------------------------
#
# Tool Class
#
# ----------------------------------------------------------------------------
class FamilyRelationshipTool(PluginWindows.ToolManagedWindowBatch):
    """Class for tool processing."""

    def get_title(self):
        """Window title."""
        return _("Family Relationship Tool")

    def initial_frame(self):
        """Category tab title."""
        return _("Options")

    def run(self):
        """Tool processing."""
        db = self.dbstate.get_database()
        filter_ = self.__opt("families").get_filter()
        rel_value = int(self.__opt("relationship").get_value())
        rel = FamilyRelType._DATAMAP[rel_value]
        all_families = db.iter_family_handles()
        families = filter_.apply(db, all_families)
        num = len(families)
        name = _("Family Relationship Tool")

        with DbTxn(name, db, batch=True) as self.trans:
            db.disable_signals()
            self.progress.set_pass(_('Process relationships...'), num)
            for handle in families:
                family = db.get_family_from_handle(handle)
                family.set_relationship(rel)
                db.commit_family(family, self.trans)
                self.progress.step()
        db.enable_signals()
        db.request_rebuild()

    def __opt(self, opt_name):
        """Get a menu option by its name."""
        return self.options.menu.get_option_by_name(opt_name)
