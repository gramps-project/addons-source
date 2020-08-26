# encoding:utf-8
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Benny Malengier
# Copyright (C) 2009 Felix Heß
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

# $Id: TimelinePedigreeview.gpr.py 13881 2009-12-21 13:43:50Z flix007 $

#------------------------------------------------------------------------
#
# default views of Gramps
#
#------------------------------------------------------------------------
if locals().get('uistate'):  # don't start GUI if in CLI mode, just ignore
    from gi.repository import Gtk, GdkPixbuf
    import os
    from gramps.gen.const import USER_PLUGINS
    fname = os.path.join(USER_PLUGINS, 'TimelinePedigreeView')
    icons = Gtk.IconTheme().get_default()
    icons.append_search_path(fname)

register(VIEW,
    id    = 'TimelinePedigreeView',
    name  = _("Timeline Pedigree"),
    category = ("Ancestry", _("Ancestry")),
    description =  _("The view shows a timeline pedigree with ancestors and "
                     "descendants of the selected person"),
    version = '0.1.60',
    gramps_target_version = "5.1",
    status = STABLE,
    fname = 'TimelinePedigreeView.py',
    authors = ["Felix Heß"],
    authors_email = ["xilef@nurfuerspam.de"],
    viewclass = 'TimelinePedigreeView',
    stock_icon = 'gramps-timelinepedigree',
    )
