# encoding:utf-8
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2016-     Serge Noiraud
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
# Geography view for the ancestor view
#
#------------------------------------------------------------------------

from gi import Repository

#from gramps.gen.plug._pluginreg import register, VIEW, STABLE #, END, START

if locals().get('uistate'):  # don't start GUI if in CLI mode, just ignore
    from gi.repository import Gtk, GdkPixbuf
    import os
    from gramps.gen.const import USER_PLUGINS
    fname = os.path.join(USER_PLUGINS, 'GeoAncestor')
    icons = Gtk.IconTheme().get_default()
    icons.append_search_path(fname)

#-------------------------------------------------------------------------
#
# set up logging
#
#-------------------------------------------------------------------------
import logging
_LOG = logging.getLogger("Geography")

# Attempting to import OsmGpsMap gives an error dialog if OsmGpsMap is not
# available so test first and log just a warning to the console instead.
OSMGPSMAP = False
REPOSITORY = Repository.get_default()
if REPOSITORY.enumerate_versions("OsmGpsMap"):
    try:
        # current osmgpsmap support GTK3
        import gi
        gi.require_version('OsmGpsMap', '1.0')
        from gi.repository import OsmGpsMap as osmgpsmap
        OSMGPSMAP = True
    except:
        pass

if not OSMGPSMAP:
    from gramps.gen.config import config
    if not config.get('interface.ignore-osmgpsmap'):
        from gramps.gen.constfunc import has_display
        if has_display():
            from gramps.gui.dialog import MessageHideDialog
            from gramps.gen.const import URL_WIKISTRING
            OSMGPS_DICT = {'gramps_wiki_build_osmgps_url' : URL_WIKISTRING +
                           "GEPS_029:_GTK3-GObject_introspection"
                           "_Conversion#OsmGpsMap_for_Geography"}
            TITLE = _("OsmGpsMap module not loaded.")
            MESSAGE = _("Geography functionality will not be available.\n"
                        "To build it for Gramps see "
                        "%(gramps_wiki_build_osmgps_url)s") % OSMGPS_DICT
            if uistate:
                MessageHideDialog(TITLE, MESSAGE,
                                  'interface.ignore-osmgpsmap',
                                  parent=uistate.window)
            else:
                MessageHideDialog(TITLE, MESSAGE,
                                  'interface.ignore-osmgpsmap')
else:
    # Load the view only if osmgpsmap library is present.
    register(VIEW,
             id='geoancestor',
             name=_("Ancestors map"),
             description=_("A view showing ancestors places on the map."),
             version = '1.0.6',
             gramps_target_version='5.1',
             status=STABLE,
             fname='GeoAncestor.py',
             authors=["Serge Noiraud"],
             authors_email=[""],
             category=("Geography", _("Geography")),
             viewclass='GeoAncestor',
             stock_icon='geo-ancestor',
             )
