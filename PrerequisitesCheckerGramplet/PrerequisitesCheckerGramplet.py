#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2016-2018 Sam Manzi
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

#------------------------------------------------------------------------------------------
# A diagnotic tool to help work out if users have the prerequistes installed as well as the latest version of Gramps
# also helps on OS's like windows and mac where it's difficult for users to use the command line to get information on gramps via ( gramps -v )!
# Possibly only for Linux or detect if AIO for Windows or dmg for MacOS and mention that its only informational
#
# []Test that the User directory has the correct permissions?
#        - list names of family tree along with total eg: You have 7 family trees.
# []test for bsddb on gramps 3.x series (as shows as not installed)
# []test for gtk2 on gramps 3.x series (as shows as not installed)
# []test if alternate keybinding accel list loaded (on mac)
# []List media path (and that permissions are correct)
# []See const file (gramps/const.py )
# []for each section add a total eg :  Total: 10 ( 7 fail / 3 success)
# []for each addon show an overall "Success/Failed" message
# []? Test if Addon installed & show version number
# []For gramps version message; report the user_version and then a string related to the OS version.
# []Link to Gramps website ( bugs / wiki / documentation)
# []Cleanup and PEP8 code.
# []test against each gramps series:
'''
Tested with Gramps:
[ ] 5.1 master (python3/gtk3) - Github feed
[ ] 5.0 (python3/gtk3) - Github feed
[ ] 4.2 (python3/gtk3) - Github feed
.....
[ ] 4.1 (python2/gtk3) - SF SVN feed
[ ] 4.0 (python2/gtk3) - SF SVN feed  (no Win AIO)
.....
[ ] 3.4 (python2/gtk2) - SF SVN feed ([x]Changed to use imports for Gramps 3.x series)  (current addon management introduced)  (No win aio)
.....
???restarts gramps twice ?? [ ] 3.3 (python2/gtk2) - SF SVN feed (Oldstyle plugin manager located as a tab in plugin manager)
[ ] 3.2 (python2/gtk2) - SF SVN feed (Oldstyle plugin manager located as a tab in plugin manager)
'''
# []simplfy repeating code and use a dictionary to return:
#   {{package_name:"GTK+"},{min_ver:(x,x,x)},{installed_ver:(y,y,y)},{result:"Success"},{Description:"why,what,how"},{URL:"http://xxxx}}
#
# Possible Example output:
# Gramps installed version: 3.4.9
# Status: Unsupported - EOL (End of Life : YYYMMDD)  # table of releases
# Latest Gramps Release: 5.0.0
#
#           |   Requires      | Installed  | Status | Comment
#-------------------------------------------------------------------------
# Python    |      3.2        |    2.7     | Failed | ???? link

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import sys
import os
from subprocess import Popen, PIPE

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
try:
    from gramps.gen.plug import Gramplet
    from gramps.gen.constfunc import win, get_env_var
    from gramps.gen.utils.file import search_for
    #print("Gramps 4.x series or greater")
    ENVVAR = True
except:
    #print("Gramps 3.x series - location of files is different")
    from gen.plug import Gramplet
    from constfunc import win  #??? get_env_var
    from Utils import search_for
    ENVVAR = False # don't believe it exist in 3.x series?


#-------------------------------------------------------------------------
#
# Checker
#
#-------------------------------------------------------------------------

class PrerequisitesCheckerGramplet(Gramplet):
    """
    Diagnostic Prerequisites Checker Gramplet to help indicate if you can upgrade to the latest version of Gramps
    """
    def init(self):
        '''Brief description of purpose'''
        self.set_use_markup(True)
        self.render_text("""Diagnostic Gramplet to help evaluate if <a href="https://gramps-project.org/">Gramps</a> has all <a href="https://github.com/gramps-project/gramps/blob/master/README.md">prerequisites</a> installed.\n""")
        self.set_tooltip("Diagnostic Gramplet to help evaluate if Gramps has all prerequisites installed.")
        self.gramps_version()
        # Gramps for requirements mentioned in Gramps 5.0.0 readme and elsewhere
        # https://github.com/gramps-project/gramps/blob/master/gramps/grampsapp.py#L187
        #Requirements
        self.render_text("""\n<u><b>Requirements</b></u>\n""")
        self.render_text("""The following packages <b>MUST</b> be installed (Requires the minimum version or greater.):\n""")
        self.check1_python()
        self.check2_gtk()
        self.check3_pygobject()
        self.check4_cairo()
        self.check5_pango()
        self.check6_bsddb3()
        self.check7_sqlite3()
        #self.append_text("\n")
        self.check8_xdgutils()
        self.check9_librsvg2()
        self.check10_languagepackgnomexx()
        self.append_text("\n")
        #STRONGLY RECOMMENDED
        self.render_text("""\n<u><b>STRONGLY RECOMMENDED</b></u>\n""")
        self.render_text("""The following packages are <b>STRONGLY RECOMMENDED</b> to be installed:\n""")   # mention why
        self.check11_osmgpsmap()
        self.append_text("\n* ")
        self.check12_graphviz()
        self.check13_pyicu()
        self.check14_ghostscript()
        #self.append_text("\n")
        #Optional
        self.render_text("""\n<u><b>Optional</b></u>\n""")
        self.append_text("The following packages are optional:\n")  # mention what they add
        self.check15_gtkspell()
        self.check16_rcs()
        self.append_text("\n* ")
        self.check17_pillow()
        #self.append_text("\n")
        self.check18_gexiv2()
        self.check19_geocodeglib()
        #self.append_text("\n")
        self.check20_ttffreefont()
        #self.append_text("\n")
        # required developement packages #TODO only show this section if running in development mode?
        self.render_text("""\n<u><b>Development & Translation Requirements</b></u>\n""")
        self.render_text("""The following packages should be installed if you intend to translate or do any development(addons etc):\n""")
        self.gettext_version()
        self.append_text("\n* intltool_version: " + str(self.intltool_version))
        self.sphinx_check()
        #Optional packages required by Third-party Addons
        self.render_text("""\n<u><b>Optional packages required by Third-party Addons</b></u>\n""")
        self.render_text("""Prerequistes required for the following <a href="https://gramps-project.org/wiki/index.php?title=Third-party_Addons">Third-party Addons</a> to work:\n""")
        self.check21_familysheet()
        self.check22_graphview()
        self.check23_pedigreechart()
        self.check24_networkchart()
        self.check25_genealogytree()
        self.check26_htmlview()
        self.check27_googlemapkml()
        self.check28_webconnectpacks()
        self.check29_tmgimporter()
        self.check30_PostgreSQL()
        self.check31_EditExifMetadata()
        self.check32_phototagginggramplet()
        self.check33_lxmlgramplet()
        self.check34_mongodb()
        #self.render_text("""\n<u><b>List of installed Addons.</b></u>\n""")
        #self.list_all_plugins()
        # Diagnostic checks
        self.append_text("\n")
        self.render_text("""\n<u><b>Diagnostic checks</b></u>\n""")
        self.append_text("Check for potential issues.\n")
        self.append_text("\nEnvironment settings:\n")
        self.platform_details()
        self.append_text("\n")
        self.locale_settings()
        self.gramps_environment_variables()
        # mention backing up
        self.append_text("\n")
        self.render_text("""\n<u><b>Back Up Your Genealogy Files.</b></u>\n""")
        self.append_text("Time to back up your genealogy files, and then test your backups!\n")
        self.render_text("""<i><a href="https://gramps-project.org/wiki/index.php?title=How_to_make_a_backup">Backup to Gramps XML</a> You will find backup in the Family Tree menu of recent Gramps versions, otherwise use Export in the same menu but uncheck privacy options in the Exporter Assistant in order to export all data.</i>\n""")
        self.append_text("* Backups can be made at any time and at least on the first day of every month, if not more often.\n")
        self.append_text("* Before any upgrade it is strongly recommended to backup each of your Family Trees.\n")
        self.append_text("* Test your backups by creating a new Family Tree and importing the backup.")

    def gramps_version(self):
        '''Report Currently installed Gramps Version

        #if current version < installed version then mention current version?
        #if current version == installed version then don't mention current version?
        #if current version > installed version then don't mention current version running test or development version?

        https://gramps-project.org/wiki/index.php?title=Previous_releases_of_Gramps
        '''
        self.append_text("\n")
        # Start check
        LATEST_GRAMPS_VERSION = (4, 2, 8)
        LATEST_GRAMPS_DATE    = "2018-02-09"
        latest_release_message = "Gramps " + str(LATEST_GRAMPS_VERSION[0]) + "." + str(LATEST_GRAMPS_VERSION[1]) + "." + str(LATEST_GRAMPS_VERSION[2]) + "  released " + LATEST_GRAMPS_DATE + " is the most current version.\n"

        try:
            try:
                from gramps.gen.const import VERSION, VERSION_TUPLE
                gramps_str = VERSION
                gramps_ver = VERSION_TUPLE
            except:
                # Gramps 3.x series
                from const import VERSION, VERSION_TUPLE
                gramps_str = VERSION
                gramps_ver = VERSION_TUPLE
        except:
            gramps_str = 'not found'

        # Test
        if not gramps_ver >= LATEST_GRAMPS_VERSION:
            #print("Failed")
            result = """You have Gramps %s . Please make a backup and then upgrade.\n%s""" % (gramps_str, latest_release_message)
        else:
            if not gramps_ver == LATEST_GRAMPS_VERSION:
                result = """You have Gramps %s installed; an unreleased development version. Thank you for contributing and testing; please report any issues. Backups are your friend.\n""" % (gramps_str)
                #print(gramps_ver)
            else:
                #print("Success")
                #TODO add further check that this is true?
                result = """You have Gramps %s . Congratulations you have the current version.\n""" % (gramps_str)

        # End check
        self.render_text(result)
        #self.append_text(result)

    #Requirements
    def check1_python(self):
        '''Check python version Gramps is currently running with against min version required

        #TODO - does not handle an older version of Gramps using python 2 on that a system that has python 3 installed (same for each of the other test
        '''
        # Start check
        MIN_PYTHON_VERSION = (3, 2, 0)
        min_py_str = str(MIN_PYTHON_VERSION[0]) + "." + str(MIN_PYTHON_VERSION[1]) + "." + str(MIN_PYTHON_VERSION[2])

        # version to check against
        # Gramps running version of python
        py_str = '%d.%d.%d' % sys.version_info[:3]
        check1= "* Python "

        if not sys.version_info >= MIN_PYTHON_VERSION:
            #print("Failed")
            messagefailed1 = " (Requires version "
            messagefailed3= " or greater installed.)\n"

            messagefailed= messagefailed1 + min_py_str + messagefailed3

            result= check1 + py_str + messagefailed
        else:
            #print("Success")
            messagesuccess1 = " (Successs version "
            messagesuccess3= " or greater installed.)\n"

            messagesuccess= messagesuccess1 + min_py_str + messagesuccess3

            result= check1 + py_str + messagesuccess
        # End check
        self.append_text(result)

    def check2_gtk(self):
        '''Check GTK+ version
        
        GTK 3.10 or greater - A cross-platform widget toolkit for creating graphical user interfaces. http://www.gtk.org/

        min: GTK+ 3.10.0
        '''
        # Start check
        MIN_GTK_VERSION = (3, 10, 0)

        try:
            import gi
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk
            try:
                gtkver_str = '%d.%d.%d' % (Gtk.get_major_version(),
                            Gtk.get_minor_version(), Gtk.get_micro_version())
                v1 = Gtk.get_major_version()
                v2 = Gtk.get_minor_version()
                v3 = Gtk.get_micro_version()
                gtk_result = ( v1, v2, v3)
            except:  # any failure to 'get' the version
                gtkver_str = 'unknown version'
                gtk_result = ( 0, 0, 0)
        except ImportError:
            gtkver_str = 'not found'
            gtk_result = ( 0, 0, 0)
            # no DISPLAY is a RuntimeError in an older pygtk (e.g. 2.17 in Fedora 14)
        except RuntimeError:
            gtkver_str = 'DISPLAY not set'
            gtk_result = ( 0, 0, 0)
            # exept TypeError: To handle back formatting on version split

        '''
        # test for older GTK 2
        # https://github.com/gramps-project/gramps/blob/maintenance/gramps34/src/gramps.py
        try:
            import gtk
            try:
                gtkver_str = '%d.%d.%d' % gtk.gtk_version
            except : # any failure to 'get' the version
                gtkver_str = 'unknown version'
            try:
                pygtkver_str = '%d.%d.%d' % gtk.pygtk_version
            except :# any failure to 'get' the version
                pygtkver_str = 'unknown version'
        except ImportError:
            gtkver_str = 'not found'
            pygtkver_str = 'not found'
        # no DISPLAY is a RuntimeError in an older pygtk (e.g. 2.17 in Fedora 14)
        except RuntimeError:
            gtkver_str = 'DISPLAY not set'
            pygtkver_str = 'DISPLAY not set'
        '''

        # Test
        if not gtk_result >= MIN_GTK_VERSION:
            #print("Failed")
            result = "* GTK+ " + gtkver_str + " (Requires version " + str(MIN_GTK_VERSION[0]) + "." + str(MIN_GTK_VERSION[1]) + "." + str(MIN_GTK_VERSION[2]) + " or greater.)\n"
        else:
            #print("Success")
            result = "* GTK+ " + gtkver_str + " (Success version " + str(MIN_GTK_VERSION[0]) + "." + str(MIN_GTK_VERSION[1]) + "." + str(MIN_GTK_VERSION[2]) + " or greater installed.)\n"

        # End check
        self.append_text(result)

    def check3_pygobject(self):
        '''Check for pygobject
        
        pygobject 3.12 or greater - Python Bindings for GLib/GObject/GIO/GTK+ https://wiki.gnome.org/Projects/PyGObject

         # pygobject 3.12+
        '''
        # Start check
        MIN_PYGOBJECT_VERSION = (3, 12, 0)

        try:
            from gi.repository import GObject
            try:
                pygobjectver_str = '%d.%d.%d' % GObject.pygobject_version
                v1 = GObject.pygobject_version[0]
                v2 = GObject.pygobject_version[1]
                v3 = GObject.pygobject_version[2]
                #print("test" + str(v1) + str(v2) + str(v3))
                pygobject_result = ( v1, v2, v3)
            except:  # any failure to 'get' the version
                pygobjectver_str = 'unknown version'
                pygobject_result = ( 0, 0, 0)

        except ImportError:
            pygobjectver_str = 'not found'
            pygobject_result = ( 0, 0, 0)

        '''
        # test for older pygobject for gtk 2
        # https://github.com/gramps-project/gramps/blob/maintenance/gramps34/src/gramps.py
        try:
            import gobject
            try:
                gobjectver_str = '%d.%d.%d' % gobject.pygobject_version
            except :# any failure to 'get' the version
                gobjectver_str = 'unknown version'

        except ImportError:
            gobjectver_str = 'not found'
        '''

        # Test
        if not pygobject_result >= MIN_PYGOBJECT_VERSION:
            #print("Failed")
            result = "* PyGObject " + pygobjectver_str + " (Requires version " + str(MIN_PYGOBJECT_VERSION[0]) + "." + str(MIN_PYGOBJECT_VERSION[1]) + "." + str(MIN_PYGOBJECT_VERSION[2]) + " or greater.)\n"
        else:
            #print("Success")
            result = "* PyGObject " + pygobjectver_str + " (Success version " + str(MIN_PYGOBJECT_VERSION[0]) + "." + str(MIN_PYGOBJECT_VERSION[1]) + "." + str(MIN_PYGOBJECT_VERSION[2]) + " or greater installed.)\n"

        # End check
        self.append_text(result)

    def check4_cairo(self):
        '''Check cairo installed with GObject Introspection bindings (the gi package)
        '''
        # Start check
        MIN_CAIRO_VERSION = (1, 13, 1) # min version that pycairo supports is 1.13.1
        MIN_PYCAIRO_VERSION = (1, 13, 3)

        try:
            import cairo
            try:
                pycairover_str = '%d.%d.%d' % cairo.version_info
                cairover_str = cairo.cairo_version_string()
                cairover_str2 = cairover_str.split(".")
                c1 = int(cairover_str2[0])
                c2 = int(cairover_str2[1])
                c3 = int(cairover_str2[2])
                cairover_tpl = (c1, c2, c3)

                pycairo_result = (cairo.version_info[0], cairo.version_info[1], cairo.version_info[2])
                #print("pycairo_result : " + str(pycairo_result))

                cairo_result = cairover_tpl
                #print("cairo_result : " + str(cairo_result))
            except:  # any failure to 'get' the version
                pycairover_str = 'unknown version'
                cairover_str = 'unknown version'

        except ImportError:
            pycairover_str = 'not found'
            cairover_str = 'not found'

        # Test Cairo
        if not cairo_result >= MIN_CAIRO_VERSION:
            #print("Failed")
            result = "* Cairo " + cairover_str + " (Requires version " + str(MIN_CAIRO_VERSION[0]) + "." + str(MIN_CAIRO_VERSION[1]) + "." + str(MIN_CAIRO_VERSION[2]) + " or greater.)\n"
        else:
            #print("Success")
            result = "* Cairo " + cairover_str + " (Success version " + str(MIN_CAIRO_VERSION[0]) + "." + str(MIN_CAIRO_VERSION[1]) + "." + str(MIN_CAIRO_VERSION[2]) + " or greater installed.)\n"

        self.append_text(result)
        # Test pycairo
        if not pycairo_result >= MIN_PYCAIRO_VERSION:
            #print("Failed")
            result = "* Pycairo " + pycairover_str + " (Requires " + str(MIN_PYCAIRO_VERSION[0]) + "." + str(MIN_PYCAIRO_VERSION[1]) + "." + str(MIN_PYCAIRO_VERSION[2]) + " or greater.)\n"
        else:
            #print("Success")
            result = "* Pycairo " + pycairover_str + " (Success version " + str(MIN_PYCAIRO_VERSION[0]) + "." + str(MIN_PYCAIRO_VERSION[1]) + "." + str(MIN_PYCAIRO_VERSION[2]) + " or greater installed.)\n"

        # End check
        self.append_text(result)

    def check5_pango(self):
        '''Check pango is installed with GObject Introspection bindings (the gi package)

        pangocairo - Allows you to use Pango with Cairo
        '''
        # Start check
        PANGO_MIN_VER = (1, 29, 3)  #TODO Find out min supported version

        try:
            from gi.repository import Pango
            try:
                pangover_str = Pango.version_string()
                #print("pangover_str " + pangover_str)
                pango_ver = pangover_str.split(".")
                pango_result = (int(pango_ver[0]), int(pango_ver[1]), int(pango_ver[2]))
            except:  # any failure to 'get' the version
                pangover_str = 'unknown version'
                pango_result = (0, 0, 0)

        except ImportError:
            pangover_str = 'not found'
            pango_result = (0, 0, 0)

        # Test Pango
        if not pango_result >= PANGO_MIN_VER:
            #print("Failed")
            result = "* Pango " + pangover_str + " (Requires version " + str(PANGO_MIN_VER[0]) + "." + str(PANGO_MIN_VER[1]) + "." + str(PANGO_MIN_VER[2]) + " or greater.)\n"
        else:
            #print("Success")
            result = "* Pango " + pangover_str + " (Success version " + str(PANGO_MIN_VER[0]) + "." + str(PANGO_MIN_VER[1]) + "." + str(PANGO_MIN_VER[2]) + " or greater installed.)\n"

        #TODO add the following test to gramps -v
        try:
            import cairo
            from gi.repository import Pango
            from gi.repository import PangoCairo
            pangocairo_str = PangoCairo._version
            #print("pangocairo_str " + str(pangocairo_str))
        except:
            pangocairo_str = "Not found"

        '''
        # Test Pangocairo
        if not pango_result >= PANGO_MIN_VER:
            #print("Failed")
            result = "* Pango " + pangover_str + " (Requires version " + str(PANGO_MIN_VER[0]) + "." + str(PANGO_MIN_VER[1]) + "." + str(PANGO_MIN_VER[2]) + " or greater.)\n"
        else:
            #print("Success")
            result = "* Pango " + pangover_str + " (Success version " + str(PANGO_MIN_VER[0]) + "." + str(PANGO_MIN_VER[1]) + "." + str(PANGO_MIN_VER[2]) + " or greater installed.)\n"
        '''
        # to be added here
        result += "* PangoCairo " + str(pangocairo_str)
        # End check
        self.append_text(result)

    def check6_bsddb3(self):
        '''bsddb3 - Python Bindings for Oracle Berkeley DB

        requires Berkeley DB

        PY_BSDDB3_VER_MIN = (6, 0, 1) # 6.x series at least
        '''
        self.append_text("\n")
        # Start check

        try:
            import bsddb3 as bsddb
            bsddb_str = bsddb.__version__
            bsddb_db_str = str(bsddb.db.version()).replace(', ', '.')\
                                        .replace('(', '').replace(')', '')
            bsddb_location_str = bsddb.__file__
        except:
            bsddb_str = 'not found'
            bsddb_db_str = 'not found'
            bsddb_location_str = 'not found'

        result = "* Berkeley Database library (bsddb3: " + bsddb_str + ") (bsddb_db_str : " + bsddb_db_str + ")"
        # End check
        self.append_text(result)

    def check7_sqlite3(self):
        '''sqlite3
        #TODO need to add to required section readme

        https://stackoverflow.com/a/1546162
        '''
        self.append_text("\n")
        # Start check
        #SQLITE_MIN_VERSION = (0, 0, 0)

        try:
            import sqlite3
            sqlite3_py_version_str = sqlite3.version  # sqlite3.version - pysqlite version
            sqlite3_version_str = sqlite3.sqlite_version # sqlite3.sqlite_version - sqlite version
            sqlite3_location_str = sqlite3.__file__
        except:
            sqlite3_version_str = 'not found'
            sqlite3_py_version_str = 'not found'
            sqlite3_location_str = 'not found'

        result = "* SQLite Database library (sqlite3: " + sqlite3_py_version_str + ") (sqlite3_version_str : " + sqlite3_version_str + ")"
        # End check
        self.append_text(result)

    def check8_xdgutils(self):
        '''xdg-utils

        #TODO where is this used in the gramps code?  or how?
        '''
        self.append_text("\n")
        # Start check

        result = "* xdg-utils (Manual check see instructions link)"
        # End check
        self.append_text(result)

    def check9_librsvg2(self):
        '''librsvg2

        #TODO where is this used in the gramps code? or it a support library for cario?
        '''
        self.append_text("\n")
        # Start check

        result = "* librsvg2 (Manual check see instructions link)"
        # End check
        self.append_text(result)

    def check10_languagepackgnomexx(self):
        '''Check language-pack-gnome-xx for currently used Locale?'''
        self.append_text("\n")
        # Start check

        #self.render_text("""<b> x :</b> """)
        # <a href="https://gramps-project.org/wiki/index.php?title=xxx">xxx</a>
        result = "* language-pack-gnome-xx (Manual check see instructions link) for your Language <show locale here TBD>"
        # End check
        self.append_text(result)

    #STRONGLY RECOMMENDED
    def check11_osmgpsmap(self):
        '''osmgpsmap'''
        # Start check
        OSMGPSMAP_MIN_VERSION = (1, 0)
        OSMGPSMAP_FOUND = False

        try:
            from gi import Repository
            repository = Repository.get_default()
            if repository.enumerate_versions("OsmGpsMap"):
                import gi
                gi.require_version('OsmGpsMap', '1.0')
                from gi.repository import OsmGpsMap as osmgpsmap
                try:
                    osmgpsmap_str = osmgpsmap._version
                    OSMGPSMAP_FOUND = True
                except:  # any failure to 'get' the version
                    osmgpsmap_str = 'unknown version'
            else:
                osmgpsmap_str = 'not found'

        except ImportError:
            osmgpsmap_str = 'not found'

        if OSMGPSMAP_FOUND:
            result = "* osmgpsmap " + osmgpsmap_str + " (Success version " + str(OSMGPSMAP_MIN_VERSION[0]) + "."+ str(OSMGPSMAP_MIN_VERSION[1]) + " or greater installed.)"
        else:
            result = "* osmgpsmap " + osmgpsmap_str + " (Requires version " + str(OSMGPSMAP_MIN_VERSION[0]) + "."+ str(OSMGPSMAP_MIN_VERSION[1]) + " or greater)"

        # End check
        self.append_text(result)

    def check12_graphviz(self):
        '''Graphviz

        Needs the liblasi library with utf-8 support to create ps/ps2 output

        GRAPHVIZ_MIN_VER = (2, 28)


        https://github.com/Alexpux/MINGW-packages/issues/737#issuecomment-147185667
        # bpisoj commented that Gramps needs a version of Graphviz that :
        [needs additional]...library be added to msys2-mingw stack as libann, libgts and liblasi?
        I am interested in last one as only that support utf-8 characters in ps/ps2 output.
        '''
        #self.append_text("\n")
        # Start check

        try:
            dotversion_str = Popen(['dot', '-V'], stderr=PIPE).communicate(input=None)[1]
            if isinstance(dotversion_str, bytes) and sys.stdin.encoding:
                dotversion_str = dotversion_str.decode(sys.stdin.encoding)
            if dotversion_str:
                dotversion_str = dotversion_str.replace('\n', '')[23:27]
        except:
            dotversion_str = 'Graphviz not in system PATH'

        result = "Graphviz " + dotversion_str
        # End check
        self.append_text(result)

    def check13_pyicu(self):
        '''PyICU'''
        self.append_text("\n")
        # Start check

        try:
            import PyICU
            try:
                pyicu_str = PyICU.VERSION
                icu_str = PyICU.ICU_VERSION
            except:  # any failure to 'get' the version
                pyicu_str = 'unknown version'
                icu_str = 'unknown version'

        except ImportError:
            pyicu_str = 'not found'
            icu_str = 'not found'

        result = "* PyICU " + pyicu_str + "(ICU " + icu_str + ")"
        # End check
        self.append_text(result)

    def check14_ghostscript(self):
        '''Ghostscript - need to add to strongly recomended or optional? section of readme

        Q:What does it do ?
        A:
        https://www.gramps-project.org/wiki/index.php?title=Gramps_5.0_Wiki_Manual_-_Reports_-_part_5#Graphviz_Layout
        *Number of Horizontal Pages: (1 default) Graphviz can create very large graphs by spreading the graph across a rectangular array of pages. This controls the number of pages in the array horizontally. Only valid for dot and pdf via Ghostscript.
        *Number of Vertical Pages: (1 default) Graphviz can create very large graphs by spreading the graph across a rectangular array of pages. This controls the number of pages in the array vertically. Only valid for dot and pdf via Ghostscript.
        '''
        self.append_text("\n")
        # Start check

        try:
            if win():
                try:
                    gsversion_str = Popen(['gswin32c', '--version'], stdout=PIPE).communicate(input=None)[0]
                except:
                    gsversion_str = Popen(['gswin64c', '--version'], stdout=PIPE).communicate(input=None)[0]
            else:
                gsversion_str = Popen(['gs', '--version'], stdout=PIPE).communicate(input=None)[0]
            if isinstance(gsversion_str, bytes) and sys.stdin.encoding:
                gsversion_str = gsversion_str.decode(sys.stdin.encoding)
            if gsversion_str:
                gsversion_str = gsversion_str.replace('\n', '')
        except:
            gsversion_str = 'Ghostscript not in system PATH'

        result = "* Ghostscript " + gsversion_str
        # End check
        self.append_text(result)

    #Optional
    def check15_gtkspell(self):
        '''gtkspell & enchant

        #TODO add check for gtspell to "gramps -v"  section

        https://github.com/gramps-project/gramps/blob/maintenance/gramps50/gramps/gui/spell.py

        # TODO (check what MacOS uses?) look like it uses this one.
        https://gramps-project.org/wiki/index.php?title=Download#Mac_OS_X
        Gramps uses a different spell checker than the one provided by Mac OS X, with different spelling dictionary requirements.

        Enable spell checking in the notes. Gtkspell depends on enchant. A version of gtkspell with gobject introspection is needed, so minimally version 3.0.0

        ---------
        # typing "import enchant"  works for the AIO but no version string
        -------------
        #TODO list installed dictionaries (issues with win ver if they are not all installed! eg: csv imports from other languages)
        '''
        # Start check
        GTKSPELL_MIN_VER = (3, 0)
        gtkspell_min_ver_str = str(GTKSPELL_MIN_VER[0]) + "." + str(GTKSPELL_MIN_VER[1])
        HAVE_GTKSPELL = False
        ENCHANT_MIN_VER = (0, 0)  #TODO ?

        # Attempting to import gtkspell gives an error dialog if gtkspell is not
        # available so test first and log just a warning to the console instead.
        try:
            from gi import Repository
            repository = Repository.get_default()
            gtkspell_ver = "Not found"
            if repository.enumerate_versions("GtkSpell"):
                try:
                    import gi
                    gi.require_version('GtkSpell', '3.0')
                    from gi.repository import GtkSpell as Gtkspell
                    gtkspell_ver = str(Gtkspell._version)
                    aaa = Gtkspell._version.split(".")
                    v1 = int(aaa[0])
                    v2 = int(aaa[1])
                    gtkspell_ver_tp = (v1,v2)
                    #print("gtkspell_ver " + gtkspell_ver)
                    HAVE_GTKSPELL = True
                except:
                    gtkspell_ver = "Not found"
                    gtkspell_ver_tp = (0, 0)
                    HAVE_GTKSPELL = False
                    pass
            elif repository.enumerate_versions("Gtkspell"):
                try:
                    import gi
                    gi.require_version('Gtkspell', '3.0')
                    from gi.repository import Gtkspell
                    gtkspell_ver = str(Gtkspell._version)
                    gtkspell_ver_tp = Gtkspell._version
                    #print("gtkspell_ver " + gtkspell_ver)
                    HAVE_GTKSPELL = True
                except:
                    gtkspell_ver = "Not found"
                    gtkspell_ver_tp = (0, 0)
                    HAVE_GTKSPELL = False
                    pass
        except:
            gtkspell_ver = "Not found"
            gtkspell_ver_tp = (0, 0)
            HAVE_GTKSPELL = False
            pass

        # test for enchant
        try:
            import enchant
            #print("Success enchant found")
            enchant_result = "Installed"
        except:
            #print("enchant not found")
            enchant_result = "Not found"

        if gtkspell_ver_tp >= GTKSPELL_MIN_VER:
            result = "* GtkSpell " + gtkspell_ver + " (Success version " + gtkspell_min_ver_str +" or greater installed.)(enchant : " + enchant_result + ")"
        else:
            result = "* GtkSpell " + gtkspell_ver + " (Requires version " + gtkspell_min_ver_str +" or greater installed.)(enchant : " + enchant_result + ")"


        # End check
        self.append_text(result)

    def check16_rcs(self):
        '''GNU Revision Control System (RCS)
        
        The GNU Revision Control System (RCS) can be used to manage multiple revisions of your family trees. Only rcs is needed, NO python bindings are required. See info at https://gramps-project.org/wiki/index.php?title=Gramps_5.0_Wiki_Manual_-_Manage_Family_Trees#Archiving_a_Family_Tree

        #TODO add check for rcs to "gramps -v"  section

        https://github.com/gramps-project/gramps/blob/maintenance/gramps50/gramps/gui/dbman.py

        # (check if on windows and ignore?)

        $ rcs -V
        RCS version 5.7.1

        $ rcs --version
        rcs (GNU RCS) 5.9.4
        Copyright (C) 2010-2015 Thien-Thi Nguyen
        Copyright (C) 1990-1995 Paul Eggert
        Copyright (C) 1982,1988,1989 Walter F. Tichy, Purdue CS
        License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>
        This is free software: you are free to change and redistribute it.
        There is NO WARRANTY, to the extent permitted by law.
        '''
        self.append_text("\n")
        # Start check
        RCS_MIN_VER = (5, 9, 4)
        rcs_ver_str = "%s.%s.%s" % (RCS_MIN_VER[0], RCS_MIN_VER[1], RCS_MIN_VER[2])
        #print("os.environ: %s " % os.environ)
        try:
            if win():
                _RCS_FOUND = os.system("rcs -V >nul 2>nul") == 0
                RCS_RESULT = "installed"
                #print("rcs -V : " + os.system("rcs -V"))
                if _RCS_FOUND and "TZ" not in os.environ:
                    # RCS requires the "TZ" variable be set.
                    os.environ["TZ"] = str(time.timezone)
            else:
                _RCS_FOUND = os.system("rcs -V >/dev/null 2>/dev/null") == 0
                #print("xx rcs -V : " + os.system("rcs -V"))
                RCS_RESULT = "installed"
        except:
            _RCS_FOUND = False
            RCS_RESULT = "Not found"

        #Test
        if _RCS_FOUND:  #TODO actually test for version
            result = "* rcs %s TBD (Success version %s or greater installed. If not on Microsoft Windows)" % (RCS_RESULT, rcs_ver_str)
        else:
            result = "* rcs %s TBD (Requires version %s or greater installed. If not on Microsoft Windows)" % (RCS_RESULT, rcs_ver_str)

        # End check
        self.append_text(result)

    def check17_pillow(self):
        '''PILLOW
        Allows Production of jpg images from non-jpg images in LaTeX documents

        #TODO prculley mentions that : And PIL (Pillow) is also used by the main Gramps ([]narrativeweb and []other reports for image cropping) as well as [x]editexifmetadata and the new [x]latexdoc type addons (genealogytree).
        
        #TODO add check for PILLOW to "gramps -v"  section

        https://github.com/gramps-project/gramps/blob/maintenance/gramps50/gramps/plugins/docgen/latexdoc.py
        '''
        #self.append_text("\n")
        # Start check

        try:
            import PIL
            from PIL import Image
            try:
                #print(dir(PIL))
                pil_ver = str(PIL.VERSION)
                pillow_ver = str(PIL.PILLOW_VERSION)
                #print("Pillow version:" + pillow_ver)
            except:
                pil_ver = "Installed but does not supply version"
                pillow_ver = "old version of PIL with no version"
            HAVE_PIL = True
        except ImportError:
            pillow_ver = "Not found"
            pil_ver = "Not found"
            HAVE_PIL = False

        result = "(PILLOW " + pillow_ver + ")(PIL " + pil_ver + ")"
        # End check
        self.append_text(result)

    def check18_gexiv2(self):
        '''GExiv2 - is a GObject wrapper around the Exiv2 photo metadata library. It allows for Gramps to inspect EXIF, IPTC, and XMP metadata in photo and video files of various formats.
        https://wiki.gnome.org/Projects/gexiv2

        which requires the:  Exiv2 library - to manage image metadata.
        http://www.exiv2.org/

        GEXIV_MIN: GObject Introspection support added in gexiv2 0.5,  now has excellent bindings for Python 2 & 3 available.

        https://github.com/GNOME/gexiv2/blob/gexiv2-0.10/configure.ac
        # m4_define([gexiv2_major_version], [0])
        # m4_define([gexiv2_minor_version], [10])
        # m4_define([gexiv2_micro_version], [6])
        MAJOR_VERSION, MICRO_VERSION, MINOR_VERSION

        EXIV2_MIN: To build the current version of gexiv2, you will first need to install libexiv2 version 0.21 or better,
        # m4_define([exiv2_required_version], [0.21])

        dir(GExiv2)
['LogLevel', 'MAJOR_VERSION', 'MICRO_VERSION', 'MINOR_VERSION', 'Metadata', 'MetadataClass', 'MetadataPrivate', 'Orientation', 'PreviewImage', 'PreviewImageClass', 'PreviewImagePrivate', 'PreviewProperties', 'PreviewPropertiesClass', 'PreviewPropertiesPrivate', 'StructureType', 'XmpFormatFlags',  '_introspection_module', '_namespace', '_overrides_module', '_version', 'get_version', 'initialize', 'log_get_level', 'log_set_level', 'log_use_glib_logging']
        '''
        self.append_text("\n")
        # Start check

        try:
            from gi import Repository
            repository = Repository.get_default()
            if repository.enumerate_versions("GExiv2"):
                import gi
                gi.require_version('GExiv2', '0.10')
                from gi.repository import GExiv2
                try:
                    gexiv2_str = GExiv2._version
                except:  # any failure to 'get' the version
                    gexiv2_str = 'unknown version'
            else:
                gexiv2_str = 'not found'

        except ImportError:
            gexiv2_str = 'not found'
        except ValueError:
            gexiv2_str = 'not new enough'

        result = "* GExiv2 : " + gexiv2_str + "(Exiv2 library : TBD? )"
        # End check
        self.append_text(result)

    def check19_geocodeglib(self):
        '''geocodeglib
        # added to gramps master v5.1.0
        #TODO: add to gramps-v check

        https://github.com/gramps-project/gramps/blob/maintenance/gramps50/gramps/plugins/lib/maps/placeselection.py
        '''
        self.append_text("\n")
        # Start check
        geocodeglib_min_ver = "1.0"

        try:
            gi.require_version('GeocodeGlib', '1.0')
            from gi.repository import GeocodeGlib
            geocodeglib_ver = str(GeocodeGlib._version)
            GEOCODEGLIB = True
        except:
            geocodeglib_ver = "Not found"
            GEOCODEGLIB = False

        if GEOCODEGLIB:
            result = "* geocodeglib " + geocodeglib_ver + " (Success version " + geocodeglib_min_ver +" or greater installed.)"
        else:
            result = "* geocodeglib " + geocodeglib_ver + " (Requires version " + geocodeglib_min_ver +" or greater installed.)"

        # End check
        self.append_text(result)

    def check20_ttffreefont(self):
        '''ttf-freefont
        More font support in the reports

        #where is this refered to in the gramps code?  which reports are being reffered to?

        https://askubuntu.com/questions/552979/how-can-i-determine-which-fonts-are-installed-from-the-command-line-and-what-is

        use console command (this command should be available for all ubuntu-based distributions) :

        fc-list
        '''
        self.append_text("\n")
        # Start check

        result = "* ttf-freefont (Manual check see instructions link)"
        # End check
        self.append_text(result)

    #Optional packages required by Third-party Addons
    def check21_familysheet(self):
        '''Family Sheet (requires PILLOW should already be installed as part of Gramps)'''
        self.render_text("""<b>01. <a href="https://gramps-project.org/wiki/index.php?title=Family_Sheet">Addon:Family Sheet</a> :</b> """)
        # Start check
        self.check17_pillow()
        # End check
        #self.append_text("\n")

    def check22_graphview(self):
        '''Graph View - Requires: PyGoocanvas and Goocanvas and graphviz (python-pygoocanvas, gir1.2-goocanvas-2.0)'''
        self.append_text("\n")
        self.render_text("""<b>02. <a href="https://gramps-project.org/wiki/index.php?title=Graph_View">Addon:Graph View</a> :</b> """)
        # Start check

        # check for GooCanvas
        try:
            import gi
            gi.require_version('GooCanvas', '2.0')
            from gi.repository import GooCanvas
            goocanvas_ver = str(GooCanvas._version)
            #print("GooCanvas version:" + goocanvas_ver)
            GOOCANVAS_check = True
        except ImportError:
            goocanvas_ver = "Not installed"
            GOOCANVAS_check = False

        result = "(GooCanvas:" + goocanvas_ver + ")(PyGoocanvas: TBD?)"
        # End check
        self.append_text(result)
        self.append_text("(" + str(self.check12_graphviz()) + ")")
        self.append_text("\n")
        self.check4_cairo()
        #self.append_text("\n")

    def check23_pedigreechart(self):
        '''PedigreeChart - Can optionally use - NumPy if installed

        https://github.com/gramps-project/addons-source/blob/master/PedigreeChart/PedigreeChart.py
        '''
        self.append_text("\n")
        self.render_text("""<b>03. <a href="https://gramps-project.org/wiki/index.php?title=PedigreeChart">Addon:PedigreeChart</a> :</b> """)
        # Start check

        try:
            import numpy
            numpy_ver = str(numpy.__version__)
            #print("numpy.__version__ :" + numpy_ver )
            NUMPY_check = True
        except ImportError:
            numpy_ver = "Not found"
            NUMPY_check = False

        result = "(NumPy : " + numpy_ver + " )"
        # End check
        self.append_text(result)
        #self.append_text("\n")

    def check24_networkchart(self):
        '''Network Chart - requires networkx 1.11, pygraphviz , (need to add to readme) '''
        self.append_text("\n")
        self.render_text("""<b>04. <a href="https://gramps-project.org/wiki/index.php?title=NetworkChart">Addon:Network Chart</a> :</b> """)
        # Start check
        # To get "libcgraph" for pygraphviz you first need to install the development package of graphviz eg: graphviz-dev

        try:
            import importlib
            module1 = importlib.find_loader("networkx") is not None
            import networkx
            networkx_ver = str(networkx.__version__)
            #print("networkx version:" + networkx_ver)
        except:
            networkx_ver = "Not installed"
            module1 = "Not tested"

        try:
            import importlib
            module2 = importlib.find_loader("pydotplus") is not None
            import pydotplus
            pydotplus_ver = str(pydotplus.__version__)
            print("pydotplus version:" + pydotplus_ver)
        except:
            pydotplus_ver = "Not Installed"
            module2 = "Not tested"

        try:
            import importlib
            module3 = importlib.find_loader("pygraphviz") is not None
            import pygraphviz
            pygraphviz_ver = str(pygraphviz.__version__)
            #print("pygraphviz version:" + pygraphviz_ver)
        except:
            pygraphviz_ver = "Not Installed"
            module3 = "Not tested"

        result = "(networkx " + networkx_ver + ")(pydotplus: " + pydotplus_ver + ")(pygraphviz: " + pygraphviz_ver + ")("
        # End check
        self.append_text(result)
        self.check12_graphviz()
        self.append_text(")")

    def check25_genealogytree(self):
        '''genealogytrees - requires texlive including the textlive-pictures package and  genealogytree and lualatex for pdf conversion
        
        * PILLOW

        #TODO need to add to readme

        https://github.com/gramps-project/addons-source/tree/maintenance/gramps50/GenealogyTree
        https://gramps-project.org/bugs/view.php?id=10223
        https://github.com/gramps-project/gramps/blob/maintenance/gramps50/gramps/gen/plug/docgen/treedoc.py
        '''
        self.append_text("\n")
        self.render_text("""<b>05. <a href="https://gramps-project.org/wiki/index.php?title=Addon:GenealogyTree">Addon:GenealogyTree</a> :</b> """)
        # Start check
        _LATEX_RESULT = "Not found"
        if win():
            _LATEX_FOUND = search_for("lualatex.exe")
            #print("_LATEX_FOUND win: " + str(_LATEX_FOUND) )
            _LATEX_RESULT = "Installed(MS-Windows)"
        else:
            _LATEX_FOUND = search_for("lualatex")
            #print("_LATEX_FOUND lin/mac: " + str(_LATEX_FOUND) )
            _LATEX_RESULT = "Installed(Linux/Mac)"

        result = "(lualatex :" + _LATEX_RESULT + ")"
        # End check
        self.append_text(result)
        self.check17_pillow()
        self.append_text("\n")

    def check26_htmlview(self):
        '''HTMLView

        Html Renderer
        Can use the Webkit or Gecko ( Mozilla ) library

        https://github.com/gramps-project/addons-source/blob/maintenance/gramps50/HtmlView/htmlview.py
        '''
        self.append_text("\n")
        self.render_text("""<b>06. <a href="https://gramps-project.org/wiki/index.php?title=Addon:HtmlView">Addon:HTMLView</a> :</b> """)
        # Start check
        NOWEB   = 0
        WEBKIT  = 1
        MOZILLA = 2
        KITNAME = [ "None", "WebKit", "Mozilla" ]
        TOOLKIT = NOWEB

        try:
            import gi
            gi.require_version('WebKit', '3.0')
            from gi.repository import WebKit as webkit
            webkit_ver = str(webkit.__version__)
            #print("webkit version " + webkit_ver)
            TOOLKIT = WEBKIT
        except:
            webkit_ver = "Not installed "
            TOOLKIT == NOWEB
            pass

        if TOOLKIT is 0:
            #print("0")
            result012 = ")"
        else:
            #print("1/2")
            result012 = " / " + str(KITNAME[TOOLKIT]) + ")"

        result = "(Webkit: " + webkit_ver + result012
        # End check
        self.append_text(result)
        #self.append_text("\n")

    def check27_googlemapkml(self):
        '''GoogleMapKML - Needs Google Earth Desktop Program installed to view locations

        https://www.google.com/earth/desktop/
        [x]Google Earth Standard:
        C:\Program Files (x86)\Google\Google Earth\client

        [ ]Google Earth Pro:
        C:\Program Files (x86)\Google\Google Earth Pro\client

        [ ]Google Earth for Chrome:
        ??

        https://github.com/gramps-project/addons-source/blob/maintenance/gramps50/GoogleEarthWriteKML/GoogleEarthWriteKML.py

        #TODO rename wiki page (so as not to clash with builtin map services then make it redirect to user manual)
        '''
        self.append_text("\n")
        self.render_text("""<b>07. <a href="https://gramps-project.org/wiki/index.php?title=Map_Services">Addon:GoogleMapKML</a> :</b> """)
        # Start check


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
        _GOOGLEEARTH_STATUS = "Not found."
        if os.sys.platform == 'win32':
            FILE_PATH = '"%s\Google\Google Earth\googleearth.exe"'\
                        % (os.getenv('ProgramFiles'))
            NORM_PATH = os.path.normpath(FILE_PATH)
            _GOOGLEEARTH_OK = search_for(NORM_PATH)
            _GOOGLEEARTH_STATUS = "Standard. found."

            if not _GOOGLEEARTH_OK:
                # For Win 7 with 32 Gramps
                FILE_PATH = '"%s\Google\Google Earth\client\googleearth.exe"'\
                            % (os.getenv('ProgramFiles'))
                NORM_PATH = os.path.normpath(FILE_PATH)
                _GOOGLEEARTH_OK = search_for(NORM_PATH)
                _GOOGLEEARTH_STATUS = "Standard. found2."

            if not _GOOGLEEARTH_OK:
                # For Win 7 with 64 Gramps, need to find path to 32 bits programs
                FILE_PATH = '"%s\Google\Google Earth\client\googleearth.exe"'\
                            % (os.getenv('ProgramFiles(x86)'))
                NORM_PATH = os.path.normpath(FILE_PATH)
                _GOOGLEEARTH_OK = search_for(NORM_PATH)
                _GOOGLEEARTH_STATUS = "Standard. Success program installed - 32bit on 64bit Win OS."

        else:
            FILE_PATH = "googleearth"
            SEARCH = os.environ['PATH'].split(':')
            for lpath in SEARCH:
                prog = os.path.join(lpath, FILE_PATH)
                if os.path.isfile(prog):
                    _GOOGLEEARTH_OK = True
                    _GOOGLEEARTH_STATUS = "Installed"
            if not _GOOGLEEARTH_OK:
                FILE_PATH = "google-earth"
                SEARCH = os.environ['PATH'].split(':')
                for lpath in SEARCH:
                    prog = os.path.join(lpath, FILE_PATH)
                    if os.path.isfile(prog):
                        _GOOGLEEARTH_OK = True
                        _GOOGLEEARTH_STATUS = "Installed"


        result = """(<a href="https://www.google.com/earth/desktop/">Google Earth on Desktop</a> : """ + _GOOGLEEARTH_STATUS + """)""" # (_ZIP_OK :""" + str(_ZIP_OK) + """)"""
        # End check
        self.render_text(result)
        #self.append_text("\n")

    def check28_webconnectpacks(self):
        '''Webconnect Pack - needs the gramps addon : "libwebconnect" installed at the same time.

        libwebconnect is the support Library for web site collections.
        '''
        self.append_text("\n")
        self.render_text("""<b>08. <a href="https://gramps-project.org/wiki/index.php?title=Web_Connect_Pack">Addon:Webconnect Pack</a> :</b> """)
        # Start check

        try:
            import libwebconnect
            LIBWEBCONNECT_test = True
            LIBWEBCONNECT_result = "Installed" #TODO add version addon string.
        except:
            LIBWEBCONNECT_test = False
            LIBWEBCONNECT_result = "Not found"

        if LIBWEBCONNECT_test:
            result = "(libwebconnect : " + str(LIBWEBCONNECT_result) + ")(Success)"
        else:
            result = "(libwebconnect : " + str(LIBWEBCONNECT_result) + ")(Requires the gramps addon listed under 'Plugin lib')"
        # End check
        self.append_text(result)
        #self.append_text("\n")

    def check29_tmgimporter(self):
        '''
        TMG Importer Addon

        Import from an Whollygenes - The Master Genealogist (TMG) Project backup file(*.SQZ)

        requires DBF 0.96.8 or greater to function

        Please install DBF from https://pypi.python.org/pypi/dbf

        # initial reason I made this prerequistes addon.
        '''
        self.append_text("\n")
        self.render_text("""<b>09. <a href="https://gramps-project.org/wiki/index.php?title=Addon:TMGimporter">Addon:TMG Importer</a> :</b> """)
        # Start check
        DBF_MIN_VERSION = (0, 96, 8)

        try:
            # External Library: dbf.pypi
            # https://pypi.python.org/pypi/dbf
            import dbf
            dbf_ver = dbf.version
            dbf_ver_str = str(dbf_ver)
            #print("DBF version = ", dbf_ver)
            dbfavailable = "DBF installed"
        except ImportError:
            dbf_ver = (0, 0, 0)
            dbf_ver_str = "Not found"
            dbfavailable = "Not found"
        # test version
        if not dbf_ver >= DBF_MIN_VERSION:
            #print("Failed")
            result = " (DBF " + dbfavailable + ".)(Requires version " + str(DBF_MIN_VERSION[0]) + "." + str(DBF_MIN_VERSION[1]) + "." + str(DBF_MIN_VERSION[2]) + " or greater installed.)"
        else:
            #print("Success")
            result = "(DBF " + dbf_ver_str + " installed.)(Success version " + str(DBF_MIN_VERSION[0]) + "." + str(DBF_MIN_VERSION[1]) + "." + str(DBF_MIN_VERSION[2]) + " or greater installed.)"

        #result = "(DBF : " + dbf_ver + ")" + dbfavailable
        # End check
        self.append_text(result)

    def check30_PostgreSQL(self):
        '''
        PostgreSQL Database

        requires: PostgreSQL -
        requires: psycopg2 - Python-PostgreSQL Database Adapter

        # https://pypi.python.org/pypi/psycopg2

        # https://gramps-project.org/wiki/index.php?title=DB-API_Database_Backend#Postgresql

        # https://github.com/gramps-project/addons-source/tree/maintenance/gramps50/PostgreSQL

        https://stackoverflow.com/a/39451451

        How get PostgreSQL version using psycopg2?

        According to documentation it is server_version property of connection:

        conn = psycopg2.connect(settings.DB_DSN)
        >>> conn.server_version
        90504
        The number is formed by converting the major, minor, and revision numbers into two-decimal-digit numbers and appending them together. For example, version 8.1.5 will be returned as 80105.

        command line:
        psql -V
        '''
        self.append_text("\n")
        self.render_text("""<b>10. <a href="https://gramps-project.org/wiki/index.php?title=DB-API_Database_Backend#Postgresql">Addon:PostgreSQL</a></b> Database library Support : """)
        # Start check
        try:
            import psycopg2
            psycopg2_ver = str(psycopg2.__version__)
            #print(dir(psycopg2))
            libpq_ver = str(psycopg2.__libpq_version__)
            #print("psycopg2" + psycopg2_ver)
            psycopg2_found = "found"
        except:
            psycopg2_ver = "Not found."
            libpq_ver = "Not found."
            psycopg2_found = "Not found"

        result = "(PostgreSQL " + libpq_ver + ")(psycopg2 : " + psycopg2_ver + ")"
        # End checks
        self.append_text(result)

    def check31_EditExifMetadata(self):
        '''Edit Image Exif Metadata - 
        
        requires:
        * PIL (Pillow)
        * pyexiv2  ( 0.2.0 )
        * exiv2
        
        https://github.com/gramps-project/addons-source/tree/master/EditExifMetadata
        '''
        self.append_text("\n")
        self.render_text("""<b>11. <a href="https://gramps-project.org/wiki/index.php?title=Edit_Image_Exif_Metadata">Addon:Edit Image Exif Metadata</a> :</b> """)

        # Start check
        self.check17_pillow()
        '''
        # validate that pyexiv2 is installed and its version...
        import pyexiv2

        # v0.1 has a different API to v0.2 and above
        if hasattr(pyexiv2, 'version_info'):
            OLD_API = False
        else:
        # version_info attribute does not exist prior to v0.2.0
            OLD_API = True
        
        # validate the exiv2 is installed and its executable
        system_platform = os.sys.platform
        if system_platform == "win32":
            EXIV2_FOUND = "exiv2.exe" if search_for("exiv2.exe") else False
        else:
            EXIV2_FOUND = "exiv2" if search_for("exiv2") else False
        if not EXIV2_FOUND:
            msg = 'You must have exiv2 and its development file installed.'
            raise SystemExit(msg)
        '''
        # End checks
        self.append_text(" TODO ( pyexiv2  ( 0.2.0 ) & exiv2 )")

    def check32_phototagginggramplet(self):
        '''PhotoTaggingGramplet - Gramplet for tagging people in photos
        
        If the OpenCV is not found, the automatic face detection feature will be unavailable, but the Gramplet should otherwise function correctly.

        Automatic detection of faces requires the following to be installed:

        * OpenCV, its dependencies and Python bindings. This library should be available in common Linux distributions. For example, Debian package python-opencv provides the Python bindings for the library. It will require the core library packages (libopencv-*) and the
        * python-numpy package.
        
        https://gramps-project.org/wiki/index.php?title=Photo_Tagging_Gramplet
        https://github.com/gramps-project/addons-source/blob/master/PhotoTaggingGramplet/facedetection.py
        https://github.com/gramps-project/addons-source/tree/master/PhotoTaggingGramplet
        ......
        ubuntu:
        pip3 install opencv-python
        
        import cv2
        cv2.__version__
        '3.4.0'
        '''
        self.append_text("\n")
        self.render_text("""<b>12. <a href="https://gramps-project.org/wiki/index.php?title=Photo_Tagging_Gramplet">Addon:Photo Tagging Gramplet</a> :</b> """)
        # Start check

        try:
            import cv2
            computer_vision_available = True
            cv2_ver = cv2.__version__
            facedetection_found = "Installed"
            #print(dir(cv2))
        except ImportError:
            computer_vision_available = False
            facedetection_found = "Not found"
            cv2_ver = "Not found"

        result = "xxx Check = TBD"
        # End checks
        #self.append_text(result)
        self.append_text(" TODO (numpy check available in self.check23_pedigreechart() / ) OpenCV facedetection: %s  %s" % (facedetection_found, cv2_ver))

    def check33_lxmlgramplet(self):
        ''' Lxml Gramplet - Gramplet for testing lxml and XSLT
        
        lxml gramplet is an experimental gramplet working under POSIX platform(s), which reads, writes (not the original one; safe read only state), transforms content of our Gramps XML file on the fly without an import into our database (Gramps session). 
        
        https://www.gramps-project.org/wiki/index.php?title=Lxml_Gramplet
        https://github.com/gramps-project/addons-source/tree/master/lxml
        
        requires:
        * lxml is a Pythonic binding for the C libraries libxml2 and libxslt. It is known for good performances by using C-level (Cython).
        '''
        self.append_text("\n")
        self.render_text("""<b>13. <a href="https://www.gramps-project.org/wiki/index.php?title=Lxml_Gramplet">Addon:Lxml Gramplet</a> :</b> """)
        # Start check

        try:
            from lxml import etree, objectify
            LXML_OK = True
            # current code is working with:
            # LXML_VERSION (3, 3, 3)
            # LIBXML_VERSION (2, 9, 1))
            # LIBXSLT_VERSION (1, 1, 28))
            LXML_VERSION = etree.LXML_VERSION
            LIBXML_VERSION = etree.LIBXML_VERSION
            LIBXSLT_VERSION = etree.LIBXSLT_VERSION
            print("lxml found")
        except:
            LXML_OK = False
            print('Missing python3 lxml. Please, try to install "python3 lxml" package.')
            print('No lxml')

        # test version
        if LXML_VERSION:
            #print("Failed")
            result = " (lxml " + str(LXML_OK) + ".)(Requires version " + str(LXML_VERSION) + " or greater installed.)TBD fixthis"
        else:
            #print("Success")
            result = " (lxml " + str(LXML_OK) + " " + str(LXML_VERSION) + ".)(Success version " + str(LXML_VERSION) + " or greater installed.) TBD fixthis"

        # End checks
        self.append_text(result)
        
    def check34_mongodb(self):
        '''
        MongoDB
        
        requires:
        * MongoDB
        & pymongo
        '''
        self.append_text("\n")
        self.render_text("""<b>14. <a href="https://www.gramps-project.org/wiki/index.php?title=MongoDB">Addon:MongoDB</a> :</b> """)

        result = "* Requires: MongoDB TBD / pymongo TBD"
        # End checks
        self.append_text(result)

    # Diagnostic checks #######################################################################################
    def platform_details(self):
        '''Which operating system if this'''
        #self.append_text("\n")
        # Start check
        if hasattr(os, "uname"):
            kernel = os.uname()[2]
        else:
            kernel = None

        self.append_text('* Operating System: %s' % sys.platform)
        if kernel:
            self.append_text('\n kernel: %s' % kernel)

        # End check
        self.append_text("\n")

    def locale_settings(self):
        '''Locale Check

        # Test Locale settings are correct for system? eg: not using LANG=C LC_ALL=C see issue #10407

        [ ] Mention that if you don see Gramps in your language and the settings are correct that if on windows you may need to reinstall Gramps and select the needed language and dictionary

        LC_MESSAGES
        LC_TIME
        '''
        #self.append_text("\n")
        self.render_text("""<u><b><a href="https://gramps-project.org/wiki/index.php?title=Gramps_5.0_Wiki_Manual_-_Command_Line#LANG.2C_LANGUAGE.2C_LC_MESSAGE.2C_LC_TIME">Locale Settings:</a></b></u>\n""")
        # Start check
        if ENVVAR:
            lang_str = get_env_var('LANG', 'not set')
            language_str = get_env_var('LANGUAGE', 'not set')
            lcmessage_str = get_env_var('LC_MESSAGES', 'not set')
            lctime_str = get_env_var('LC_TIME', 'not set')
        else:
            lang_str = 'not tested'
            language_str = 'not tested'
            lcmessage_str = 'not tested'
            lctime_str = 'not tested'

        result = "* LANG : " + lang_str + "\n* LANGUAGE :" + language_str + "\n* LC_MESSAGES :" + lcmessage_str + "\n* LC_TIME :" + lctime_str
        # End check
        self.append_text(result)

    def gramps_environment_variables(self):
        '''Gramps Environment variables
        https://gramps-project.org/wiki/index.php?title=Gramps_5.0_Wiki_Manual_-_Command_Line#Environment_variables
        '''
        self.append_text("\n")
        # Start check
        if ENVVAR:
            grampsi18n_str = get_env_var('GRAMPSI18N', 'not set')
            grampshome_str = get_env_var('GRAMPSHOME', 'not set')
            grampsdir_str = get_env_var('GRAMPSDIR', 'not set')
            gramps_resources_str = get_env_var('GRAMPS_RESOURCES', 'not set')
        else:
            grampsi18n_str = 'not tested'
            grampshome_str = 'not tested'
            grampsdir_str = 'not tested'
            gramps_resources_str = 'not tested'

        # End check
        self.append_text("\nGramps Environment variables:\n")
        self.append_text('* GRAMPSI18N : %s' % grampsi18n_str)
        self.append_text('\n* GRAMPSHOME : %s' % grampshome_str)
        self.append_text('\n* GRAMPSDIR : %s' % grampsdir_str)
        self.append_text('\n* GRAMPS_RESOURCES : %s' % gramps_resources_str)

    def intltool_version():
        '''
        Intltool collection - The internationalization tool collection
        
        https://freedesktop.org/wiki/Software/intltool/
        
        Return the version of intltool as a tuple.
        
        Note from setup.py : No intltool or version < 0.25.0, build_intl is aborting'
        
        Uses:
        intltool-update   (min version:  0.25.0 )
        intltool-merge
        
        Which all require:
        * perl
        
        https://github.com/gramps-project/gramps/blob/maintenance/gramps50/setup.py
        https://github.com/gramps-project/gramps/blob/master/po/genpot.sh
        
        ver 0.51.0
        '''
        import subprocess

        if sys.platform == 'win32':
            cmd = ["perl", "-e print qx(intltool-update --version) =~ m/(\d+.\d+.\d+)/;"]
            try:
                ver, ret = subprocess.Popen(cmd ,stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, shell=True).communicate()
                ver = ver.decode("utf-8")
                if ver > "":
                    version_str = ver
                else:
                    return (0,0,0)
            except:
                return (0,0,0)
        else:
            cmd = 'intltool-update --version 2> /dev/null' # pathological case
            retcode, version_str = subprocess.getstatusoutput(cmd)
            if retcode != 0:
                return None
            cmd = 'intltool-update --version 2> /dev/null | head -1 | cut -d" " -f3'
            retcode, version_str = subprocess.getstatusoutput(cmd)
            if retcode != 0: # unlikely but just barely imaginable, so leave it
                return None
        return tuple([int(num) for num in version_str.split('.')])

    def gettext_version(self):
        '''GNU gettext utilities - for translation
        
        https://en.wikipedia.org/wiki/Gettext
        
        ver: 0.19.8.1
                
        * msgfmt  - generates a binary message catalog from a textual translation description. 
        
        https://github.com/gramps-project/gramps/blob/master/po/test/po_test.py
        https://github.com/gramps-project/gramps/blob/master/gramps/gui/grampsgui.py
        https://github.com/gramps-project/gramps/blob/master/gramps/gen/datehandler/_datestrings.py
        https://github.com/gramps-project/gramps/blob/master/gramps/gen/utils/grampslocale.py
        '''
        #self.append_text("\n")
        # Start check
        try:
            import gettext
            #print(dir(gettext))
            import sgettext
            #print(dir(sgettext))
            print("gettext found")
        except:
            print("gettext not found")
        
        result = "* gettext (msgfmt) Check = TBD"
        # End checks
        self.append_text(result)

    def sphinx_check(self):
        '''
        Sphinx is a tool that build the Gramps development documentation and man pages
        
        http://sphinx-doc.org/
        
        #TODO
        https://github.com/gramps-project/gramps/blob/master/data/man/update_man.py
        https://github.com/gramps-project/gramps/blob/master/docs/update_doc.py
        '''
        
        self.append_text("\n* Sphinx is a tool that build the Gramps development documentation and man pages  TBD")
        pass
