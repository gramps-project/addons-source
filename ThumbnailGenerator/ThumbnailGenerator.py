#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011      Nick Hall
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# $Id$

"""Tools/Utilities/Thumbnail Generator"""

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gui.plug import tool
from gramps.gui.utils import ProgressMeter
from gramps.gui.thumbnails import get_thumbnail_image, SIZE_NORMAL, SIZE_LARGE
from gramps.gen.utils.file import media_path_full

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#-------------------------------------------------------------------------
#
# Thumbnail Generator
#
#-------------------------------------------------------------------------
class ThumbnailGenerator(tool.Tool):
    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate

        tool.Tool.__init__(self, dbstate, options_class, name)

        self.db = dbstate.db
        progress = ProgressMeter(_('Thumbnail Generator'), can_cancel=True)
            
        length = self.db.get_number_of_media_objects()
        progress.set_pass(_('Generating media thumbnails'),
                               length)
        for media in dbstate.db.iter_media_objects():
            full_path = media_path_full(dbstate.db, media.get_path())
            mime_type = media.get_mime_type()
            generate_thumbnail(full_path, mime_type)
            progress.step()
            if progress.get_cancelled():
                break
            
        length = self.db.get_number_of_people()
        progress.set_pass(_('Generating thumbnails for person references'),
                               length)
        for person in dbstate.db.iter_people():
            self.generate_thumbnails(person)
            progress.step()
            if progress.get_cancelled():
                break

        length = self.db.get_number_of_families()
        progress.set_pass(_('Generating thumbnails for family references'),
                               length)
        for family in dbstate.db.iter_families():
            self.generate_thumbnails(family)
            progress.step()
            if progress.get_cancelled():
                break

        length = self.db.get_number_of_events()
        progress.set_pass(_('Generating thumbnails for event references'),
                               length)
        for event in dbstate.db.iter_events():
            self.generate_thumbnails(event)
            progress.step()
            if progress.get_cancelled():
                break

        length = self.db.get_number_of_places()
        progress.set_pass(_('Generating thumbnails for place references'),
                               length)
        for place in dbstate.db.iter_places():
            self.generate_thumbnails(place)
            progress.step()
            if progress.get_cancelled():
                break

        length = self.db.get_number_of_sources()
        progress.set_pass(_('Generating thumbnails for source references'),
                               length)
        for source in dbstate.db.iter_sources():
            self.generate_thumbnails(source)
            progress.step()
            if progress.get_cancelled():
                break

        progress.close()

    def generate_thumbnails(self, obj):
        """
        Generate thumbnails for media references of a given object. 
        """
        for media_ref in obj.get_media_list():
            handle = media_ref.get_reference_handle()
            media = self.db.get_object_from_handle(handle)
            full_path = media_path_full(self.db, media.get_path())
            mime_type = media.get_mime_type()
            rectangle = media_ref.get_rectangle()
            generate_thumbnail(full_path, mime_type, rectangle)

def generate_thumbnail(full_path, mime_type, rectangle=None):
    """
    Generate thumbnails for an image rectangle.
    """
    get_thumbnail_image(full_path, mime_type, rectangle, SIZE_NORMAL)
    get_thumbnail_image(full_path, mime_type, rectangle, SIZE_LARGE)

#------------------------------------------------------------------------
#
# Thumbnail Generator Options
#
#------------------------------------------------------------------------
class ThumbnailGeneratorOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """
    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
