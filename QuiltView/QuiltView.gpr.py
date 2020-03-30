#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2012 Nick Hall
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
if locals().get('uistate'):  # don't start GUI if in CLI mode, just ignore
    from gi.repository import Gtk, GdkPixbuf
    import os
    from gramps.gen.const import USER_PLUGINS
    fname = os.path.join(USER_PLUGINS, 'QuiltView')
    icons = Gtk.IconTheme().get_default()
    icons.append_search_path(fname)

register(VIEW,
    id = 'QuiltView',
    name = _('Quilt Chart'),
    category = ('Ancestry', _('Charts')),
    description =  _('The view shows a quilt chart visualisation of a family tree'),
    version = '1.0.14',
    gramps_target_version = '5.1',
    status = STABLE,
    fname = 'QuiltView.py',
    authors = ['Nick Hall', 'Serge Noiraud'],
    authors_email = ['nick__hall@hotmail.com', 'serge.noiraud@free.fr'],
    viewclass = 'QuiltView',
    stock_icon = 'gramps-quilt',
)
