#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017-2018 Nick Hall
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

#------------------------------------------------------------------------
#
# Ancestor Tree
#
#------------------------------------------------------------------------

register(REPORT,
         id = 'ancestor_tree',
         name  = _("Ancestor Tree"),
         description =  _("Ancestor tree using LaTeX genealogytree"),
         version = '1.0.2',
         gramps_target_version = '5.0',
         status = STABLE,
         fname = 'ancestor.py',
         authors = ["Nick Hall"],
         authors_email = ["nick-h@gramps-project.org"],
         category = CATEGORY_TREE,
         reportclass = 'AncestorTree',
         optionclass = 'AncestorTreeOptions',
         report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI],
        )

#------------------------------------------------------------------------
#
# Descendant Tree
#
#------------------------------------------------------------------------

register(REPORT,
         id = 'descendant_tree',
         name  = _("Descendant Tree"),
         description =  _("Descendant tree using LaTeX genealogytree"),
         version = '1.0.2',
         gramps_target_version = '5.0',
         status = STABLE,
         fname = 'descendant.py',
         authors = ["Nick Hall"],
         authors_email = ["nick-h@gramps-project.org"],
         category = CATEGORY_TREE,
         reportclass = 'DescendantTree',
         optionclass = 'DescendantTreeOptions',
         report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI],
        )

#------------------------------------------------------------------------
#
# Grandparent Tree
#
#------------------------------------------------------------------------

register(REPORT,
         id = 'grandparent_tree',
         name  = _("Grandparent Tree"),
         description =  _("Grandparent tree using LaTeX genealogytree"),
         version = '1.0.2',
         gramps_target_version = '5.0',
         status = STABLE,
         fname = 'grandparent.py',
         authors = ["Nick Hall"],
         authors_email = ["nick-h@gramps-project.org"],
         category = CATEGORY_TREE,
         reportclass = 'GrandparentTree',
         optionclass = 'GrandparentTreeOptions',
         report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI],
        )

#------------------------------------------------------------------------
#
# Sandclock Tree
#
#------------------------------------------------------------------------

register(REPORT,
         id = 'sandclock_tree',
         name  = _("Sandclock Tree"),
         description =  _("Sandclock tree using LaTeX genealogytree"),
         version = '1.0.2',
         gramps_target_version = '5.0',
         status = STABLE,
         fname = 'sandclock.py',
         authors = ["Nick Hall"],
         authors_email = ["nick-h@gramps-project.org"],
         category = CATEGORY_TREE,
         reportclass = 'SandclockTree',
         optionclass = 'SandclockTreeOptions',
         report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI],
        )
