#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009       Peter Landgren
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

# $Id: GoogleEarthWriteKML.py.py 11946 2009-02-13 06:06:14Z ldnp $

"""
Contains the interface to allow  places to get shown using
GoogleEarth  kml or kmz file format.
"""

#-------------------------------------------------------------------------
#
# python modules
#
#-------------------------------------------------------------------------
import os
import sys
import codecs
from gramps.gen.utils.trans import get_addon_translator
_ = get_addon_translator().gettext

#-------------------------------------------------------------------------
#
# GRAMPS modules
#
#-------------------------------------------------------------------------
from gramps.gui.dialog import ErrorDialog, QuestionDialog2
from gramps.plugins.lib.libmapservice import MapService
from gramps.gui.utils import open_file_with_default_application
from gramps.gen.utils.file import search_for, get_unicode_path_from_env_var

# Check i zip is installed
_ZIP_OK = False
FILE_PATH = "zip"
NORM_PATH = os.path.normpath(FILE_PATH)
if os.sys.platform == 'win32':
    _ZIP_OK = search_for(FILE_PATH + ".exe")
else:
    SEARCH = os.environ['PATH'].split(':')
    for lpath in SEARCH:
        prog = os.path.join(lpath, FILE_PATH)
        if os.path.isfile(prog):
            _ZIP_OK = True

# Check i googleearth is installed
_GOOGLEEARTH_OK = False
if os.sys.platform == 'win32':
    FILE_PATH = '"%s\Google\Google Earth\googleearth.exe"'\
                  % (os.getenv('ProgramFiles'))
    NORM_PATH = os.path.normpath(FILE_PATH)
    _GOOGLEEARTH_OK = search_for(NORM_PATH)

    if not _GOOGLEEARTH_OK:
        # For Win 7 with 32 Gramps
        FILE_PATH = '"%s\Google\Google Earth\client\googleearth.exe"'\
                    % (os.getenv('ProgramFiles'))
        NORM_PATH = os.path.normpath(FILE_PATH)
        _GOOGLEEARTH_OK = Utils.search_for(NORM_PATH)

    if not _GOOGLEEARTH_OK:
        # For Win 7 with 64 Gramps, need to find path to 32 bits programs
        FILE_PATH = '"%s\Google\Google Earth\client\googleearth.exe"'\
                    % (os.getenv('ProgramFiles(x86)'))
        NORM_PATH = os.path.normpath(FILE_PATH)
        _GOOGLEEARTH_OK = Utils.search_for(NORM_PATH)

else:
    FILE_PATH = "googleearth"
    SEARCH = os.environ['PATH'].split(':')
    for lpath in SEARCH:
        prog = os.path.join(lpath, FILE_PATH)
        if os.path.isfile(prog):
            _GOOGLEEARTH_OK = True

def _combine(str1, str2):
    """
    Combines two strings to one if both are not empty
    If they are equal return one
    If one empty return the other
    """
    if str1 == str2 == None:
        return _("No place description")
    if str1 == str2:
        return str1
    if str1 == "":
        return str2
    if str2 == "":
        return str1
    return str1 + u', ' + str2

#-------------------------------------------------------------------------
#
# Writes a file with marked places to a kml/kmz file for GoogleEarth
#
#-------------------------------------------------------------------------

class GoogleEarthService(MapService):
    """
    Map  service using GoogleEarth
    """
    def __init__(self):
        MapService.__init__(self)
        self.kml_file = None

    def calc_url(self):
        """
        Creates a file for use with GoogleEarth
        and launches GoogleEarth if in system
        """
        home_dir = os.path.expanduser("~")
        default_filename = 'GrampsPlacesForGoogleEarth'
        filename = os.path.join(home_dir, default_filename)
        if not _GOOGLEEARTH_OK:
            qd2 = QuestionDialog2(
                _(u"GoogleEarth not installed!"),
                (_(u"Create kmz/kml file ''%s''\n"
                  u"in user directory ''%s''?")\
                      % (default_filename, home_dir)),
                _(u"Yes"),
                _(u"No"))
            if not qd2.run():
                return
        base = os.path.dirname(filename)
        # Check if directory exists
        if not os.path.exists(os.path.normpath(base)):
            ErrorDialog((_(u"Failure writing to %s") % base),
                         _(u"Directory does not exist"))
            return

        full_filename = filename + ".kml"
        zip_filename = filename + ".kmz"
        home_dir = get_unicode_path_from_env_var(home_dir)
        # Check if kml/kmz file exits
        if os.path.exists(full_filename) or os.path.exists(zip_filename):
            qd2 = QuestionDialog2(
                _(u"GoogleEarth file exists!"),
                (_(u"Overwrite kmz/kml file ''%s''\n"
                  u"in user home directory ''%s''?")\
                    % (default_filename, home_dir)),
                _(u"Yes"),
                _(u"No"))
            if not qd2.run():
                return
            # Delete olf zipped file before a new kmz.
            elif os.path.exists(zip_filename):
                os.remove(zip_filename)

        if sys.version_info[0] < 3:
            kml_file = open(full_filename,"w")
        else:
            kml_file = open(full_filename,"wb")

        self.kml_file = codecs.getwriter("utf8")(kml_file)
        self.write_kml_head()
        self.write_kml_point_data()
        self.write_kml_tail()
        kml_file.close()

        if _ZIP_OK:
            os.system("zip -q %s %s" % (zip_filename, full_filename) )

        # Run GoogleEarth if on system, else keep created file
        if _GOOGLEEARTH_OK:
            if _ZIP_OK:
                open_file_with_default_application(zip_filename)
            else:
                open_file_with_default_application(full_filename)
        # Remove the unzipped file.
        if _ZIP_OK:
            os.remove(full_filename)
        return

    def write_kml_head(self):
        """
        Writes the header part of the kml/kmz file.
        """
        self.kml_file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.kml_file.write('<kml xmlns="http://earth.google.com/kml/2.1">\n')

    def write_kml_tail(self):
        """
        Writes the tail part of the kml/kmz file.
        """
        self.kml_file.write("</kml>\n")

    def write_kml_point_data(self):
        """
        Writes the point data of the kml/kmz file.
        """
        self.kml_file.write('<Document>\n')
        self.kml_file.write('    <name>GrampsPlaces</name>\n')
        for place, descr in self._all_places():
            latitude, longitude = self._lat_lon(place)
            if latitude == None or longitude == None:
                continue
            if not descr:
                descr = place.get_title()

            parish_descr = place.get_main_location().get_parish().strip()
            city = place.get_main_location().get_city()
            county = place.get_main_location().get_county()
            city_county_descr = _combine(city.strip(), county.strip())

            state = place.get_main_location().get_state()
            country = place.get_main_location().get_country()
            state_country_descr = _combine(state.strip(), country.strip())
            id = place.get_gramps_id()

            self.kml_file.write('    <Placemark id="%s">\n' % id)
            self.kml_file.write("        <name>%s</name>\n" % descr)
            self.kml_file.write("        <description>\n")
            self.kml_file.write("            <![CDATA[\n")
            self.kml_file.write("              %s\n" %  parish_descr)
            self.kml_file.write("              %s\n" %  city_county_descr)
            self.kml_file.write("              %s\n" %  state_country_descr)
            self.kml_file.write("            ]]>\n")
            self.kml_file.write("        </description>\n")
            self.kml_file.write("        <Point>\n")
            self.kml_file.write("            <coordinates>%s" % longitude)
            self.kml_file.write(",%s</coordinates>\n" % latitude)
            self.kml_file.write("        </Point>\n")
            self.kml_file.write("    </Placemark>\n")
        self.kml_file.write("</Document>\n")
