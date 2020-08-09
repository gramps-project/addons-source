#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2018  Paul Culley
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

"""Tools/Family Tree Processing/Merge Media"""

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
import logging
LOG = logging.getLogger(".media")

#-------------------------------------------------------------------------
#
# GNOME libraries
#
#-------------------------------------------------------------------------
from gi.repository import Gtk
import re
import os

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gen.utils.file import media_path_full
from gramps.gui.plug import tool
from gramps.gui.dialog import OkDialog
from gramps.gen.merge import MergeMediaQuery
from gramps.gen.errors import MergeError

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

ngettext = glocale.translation.ngettext  # else "nearby" comments are ignored
#-------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------

WIKI_PAGE = ('https://gramps-project.org/wiki/index.php/'
             'Addon:MediaMergeTool')


#-------------------------------------------------------------------------
#
# The Actual tool.
#
#-------------------------------------------------------------------------
class MediaMerge(tool.BatchTool):
    """
    Look for media that have same path, and merges them.
    """

    def __init__(self, dbstate, user, options_class, name, callback=None):
        self.user = user
        self.dbstate = dbstate
        tool.BatchTool.__init__(self, dbstate, user, options_class, name)

        if not self.fail:
            self.run()

    def run(self):
        """
        Perform the actual extraction of information.
        """
        # finds prefix, number, suffix of a Gramps ID ignoring a leading or
        # trailing space.  The number must be at least three digits.
        _prob_id = re.compile(r'^ *([^\d]*)(\d{3,9})([^\d]*) *$')

        self.db.disable_signals()
        self.change = False
        num_merges = 0

        with self.user.progress(_("Media Merge"), '',
                                self.db.get_number_of_media()) as step:
            path_dict = {}
            for media in self.db.iter_media():
                # this should collapse '../' constructs, deal with Windows '\'
                # and deal with Windows case insensitivity as well as deal
                # with relative paths and paths with environment variables.
                # it won't properly compare a Windows UNC path with an assigned
                # drive letter to that UNC path
                path = os.path.normcase(os.path.normpath(
                    media_path_full(self.db, media.get_path())))
                if path in path_dict:
                    try:
                        media1 = path_dict[path]
                        # lets keep the shorter path, or if same
                        # try to select the lower gramps_id
                        # or lower handle  as phoenix
                        match = _prob_id.match(media.gramps_id)
                        match1 = _prob_id.match(media1.gramps_id)
                        mqo = media, media1
                        if len(media1.get_path()) < len(media.get_path()):
                            mqo = media1, media
                        elif len(media1.get_path()) == len(media.get_path()):
                            if match and match1:
                                if match1.groups()[1] < match.groups()[1]:
                                    mqo = media1, media
                                else:  # not (match and match1)
                                    if media1.handle < media.handle:
                                        mqo = media1, media
                        query = MergeMediaQuery(self.dbstate, *mqo)
                        # update to one we are keeping
                        path_dict[path] = mqo[0]
                        query.execute()
                    except AssertionError:
                        print("Tool/Family Tree processing/MediaMerge",
                              "media1 gramps_id",
                              path_dict[path].gramps_id,
                              "media2 gramps_id", media.gramps_id)
                    num_merges += 1
                else:
                    path_dict[path] = media
                step()
        self.db.enable_signals()
        self.db.request_rebuild()
        # translators: leave all/any {...} untranslated
        message = ngettext("{number_of} media merged",
                           "{number_of} media merged", num_merges
                           ).format(number_of=num_merges)
        if num_merges:
            OkDialog(_("Number of merges done"), message,
                     parent=self.user.uistate.window)
        else:
            OkDialog(_('No modifications made'),
                     _("No media items merged."),
                     parent=self.user.uistate.window)


#------------------------------------------------------------------------
#
#  The options (none in this case)
#
#------------------------------------------------------------------------
class MediaMergeOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
