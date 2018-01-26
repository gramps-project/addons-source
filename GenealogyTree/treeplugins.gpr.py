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

plg = newplugin()
plg.id = 'ancestor_tree'
plg.name  = _("Ancestor Tree")
plg.description =  _("Ancestor tree using LaTeX genealogytree")
plg.version = '1.0.0'
plg.gramps_target_version = '5.0'
plg.status = STABLE
plg.fname = 'ancestor.py'
plg.ptype = REPORT
plg.authors = ["Nick Hall"]
plg.authors_email = ["nick-h@gramps-project.org"]
plg.category = CATEGORY_TREE
plg.reportclass = 'AncestorTree'
plg.optionclass = 'AncestorTreeOptions'
plg.report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI]

#------------------------------------------------------------------------
#
# Descendant Tree
#
#------------------------------------------------------------------------

plg = newplugin()
plg.id = 'descendant_tree'
plg.name  = _("Descendant Tree")
plg.description =  _("Descendant tree using LaTeX genealogytree")
plg.version = '1.0.0'
plg.gramps_target_version = '5.0'
plg.status = STABLE
plg.fname = 'descendant.py'
plg.ptype = REPORT
plg.authors = ["Nick Hall"]
plg.authors_email = ["nick-h@gramps-project.org"]
plg.category = CATEGORY_TREE
plg.reportclass = 'DescendantTree'
plg.optionclass = 'DescendantTreeOptions'
plg.report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI]

#------------------------------------------------------------------------
#
# Grandparent Tree
#
#------------------------------------------------------------------------

plg = newplugin()
plg.id = 'grandparent_tree'
plg.name  = _("Grandparent Tree")
plg.description =  _("Grandparent tree using LaTeX genealogytree")
plg.version = '1.0.0'
plg.gramps_target_version = '5.0'
plg.status = STABLE
plg.fname = 'grandparent.py'
plg.ptype = REPORT
plg.authors = ["Nick Hall"]
plg.authors_email = ["nick-h@gramps-project.org"]
plg.category = CATEGORY_TREE
plg.reportclass = 'GrandparentTree'
plg.optionclass = 'GrandparentTreeOptions'
plg.report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI]

#------------------------------------------------------------------------
#
# Sandclock Tree
#
#------------------------------------------------------------------------

plg = newplugin()
plg.id = 'sandclock_tree'
plg.name  = _("Sandclock Tree")
plg.description =  _("Sandclock tree using LaTeX genealogytree")
plg.version = '1.0.0'
plg.gramps_target_version = '5.0'
plg.status = STABLE
plg.fname = 'sandclock.py'
plg.ptype = REPORT
plg.authors = ["Nick Hall"]
plg.authors_email = ["nick-h@gramps-project.org"]
plg.category = CATEGORY_TREE
plg.reportclass = 'SandclockTree'
plg.optionclass = 'SandclockTreeOptions'
plg.report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI]
