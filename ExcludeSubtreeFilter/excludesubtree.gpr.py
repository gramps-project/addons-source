#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Jonathan Biegert
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

# https://github.com/gramps-project/gramps/blob/master/gramps/gen/plug/_pluginreg.py
register(
    RULE,
    id="ExcludeSubtree",
    name=_("People reachable from <Person>, stopping at <Filter> matches"),
    description=_(
        "Matches people who are reachable starting from <Person> "
        "(walking all parents and children of attached families, "
        "recursively) stopping at persons in <Filter>."
    ),
    version="0.6",
    authors=["Jonathan Biegert"],
    authors_email=["azrdev@gmail.com"],
    gramps_target_version="6.0",
    status=BETA,
    fname="excludesubtree.py",
    ruleclass="ExcludeSubtree",
    namespace="Person",
)
