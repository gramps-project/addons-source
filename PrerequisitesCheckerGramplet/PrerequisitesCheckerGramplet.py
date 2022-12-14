#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2016-2018 Sam Manzi
# Copyright (C) 2022      Brian McCullough
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

# ----------------------------------------------------------------------------
''' A diagnostic tool to help work out if users have the prerequistes installed
as well as the latest version of Gramps also helps on OS's like windows and
mac where it's difficult for users to use the command line to get information
on gramps via ( gramps -v )!
Possibly only for GNU-Linux or detect if AIO for Windows or dmg for MacOS and
mention that its only informational.

[]Test that the User directory has the correct permissions?
    - list names of family tree along with total eg: You have 7 family trees.
[]test for bsddb on gramps 3.x series (as shows as not installed)
[]test for gtk2 on gramps 3.x series (as shows as not installed)
[]test if alternate keybinding accel list loaded (on mac)
[]List media path (and that permissions are correct)
[]See const file (gramps/const.py )
[]for each section add a total eg :  Total: 10 ( 7 fail / 3 success)
[]for each addon show an overall "Success/Failed" message
[]? Test if Addon installed & show version number
[]For gramps version message; report the user_version and then a string
  related to the OS version.
[]Link to Gramps website ( bugs / wiki / documentation)
[]Cleanup and PEP8 code.
[]test against each gramps series:

Tested with Gramps:
[ ] 5.1 master (python3/gtk3) - Github feed
[ ] 5.0 (python3/gtk3) - Github feed
[ ] 4.2 (python3/gtk3) - Github feed
.....
[ ] 4.1 (python2/gtk3) - SF SVN feed
[ ] 4.0 (python2/gtk3) - SF SVN feed  (no Win AIO)
.....
[ ] 3.4 (python2/gtk2) - SF SVN feed
    ([x]Changed to use imports for Gramps 3.x series)
    (current addon management introduced)  (No win aio)
.....
    ???restarts gramps twice ??
[ ] 3.3 (python2/gtk2) - SF SVN feed
    (Oldstyle plugin manager located as a tab in plugin manager)
[ ] 3.2 (python2/gtk2) - SF SVN feed
    (Oldstyle plugin manager located as a tab in plugin manager)

[]simplfy repeating code and use a dictionary to return:
   {{package_name:"GTK+"},{min_ver:(x,x,x)},{installed_ver:(y,y,y)},
    {result:"Success"},{Description:"why,what,how"},{URL:"http://xxxx}}

 Possible Example output:
 Gramps installed version: 3.4.9
 Status: Unsupported - EOL (End of Life : YYYMMDD)  # table of releases
 Latest Gramps Release: 5.0.0

           |   Requires      | Installed  | Status | Comment
-------------------------------------------------------------------------
 Python    |      3.2        |    2.7     | Failed | ???? link
'''
# -------------------------------------------------------------------------
#
# Python modules
#
# -------------------------------------------------------------------------
import sys
import os
import time
import gi
from threading import Thread
from subprocess import Popen, PIPE
from urllib import request

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
try:
    from gramps.gen.plug import Gramplet
    from gramps.gen.constfunc import win, get_env_var
    from gramps.gen.utils.file import search_for

    # print("Gramps 4.x series or greater")
    ENVVAR = True
except ImportError:
    # print("Gramps 3.x series - location of files is different")
    from gen.plug import Gramplet
    from constfunc import win  # ??? get_env_var
    from Utils import search_for

    ENVVAR = False  # don't believe it exist in 3.x series?

# ------------------------------------------------------------------------
#
# Internationalisation
#
# ------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# pylint: disable=W0511,C0103,W0703,E1101,W0212,E0611
# -------------------------------------------------------------------------
#
# Checker
#
# -------------------------------------------------------------------------


class PrerequisitesCheckerGramplet(Gramplet):
    """
    Diagnostic Prerequisites Checker Gramplet to help indicate if you can
    upgrade to the latest version of Gramps
    """

    def init(self):
        '''Brief description of purpose'''
        self.set_use_markup(True)
        self.render_text(_(
            """Diagnostic Gramplet to help evaluate if """
            """<a href="https://gramps-project.org/">Gramps"""
            """</a> has all <a href="https://github.com/"""
            """gramps-project/gramps/blob/master/README.md">"""
            """prerequisites</a> installed.\n"""))
        self.set_tooltip(_(
            "Diagnostic Gramplet to help evaluate if Gramps has "
            "all prerequisites installed."))
        # Get current Gramps version from wiki
        self.latest_gramps_version = False
        thread = Thread(target=latest_version_thread,
                        args=(self,), daemon=True)
        thread.start()

    def main(self):
        """
        This gets called at initialization and again after each 'yield'.
        Since it may be called before the gramps latest version arrives from
        the web, we just yield again if not ready.
        """
        while self.latest_gramps_version is False:
            yield True
        self.gramps_version()
        # Gramps for requirements mentioned in Gramps 5.0.0 readme & elsewhere
        # https://github.com/gramps-project/gramps/blob/master/gramps/grampsapp.py#L187
        # Requirements
        self.render_text(_("""\n<u><b>REQUIRED</b></u>\n"""))
        self.render_text(_(
            "<i>Installations of the following packages are"
            " <b>ABSOLUTELY REQUIRED</b>\n"
            " (Requires the minimum version or greater.)</i>:\n"))
        self.check1_python()
        self.check2_gtk()
        self.check3_pygobject()
        self.check4_cairo()
        self.check5_pango()
        self.check6_bsddb3()
        self.check7_sqlite3()
        # self.append_text("\n")
        self.check8_xdgutils()
        self.check9_librsvg2()
        self.check10_languagepackgnomexx()
        self.append_text("\n")
        yield True
        # STRONGLY RECOMMENDED
        self.render_text(_("""\n<u><b>RECOMMENDED</b></u>\n"""))
        self.render_text(_(
            "<i>Installations of the following packages are"
            " <b>STRONGLY RECOMMENDED</b>"
            " as necessary for Geography and Charts</i>:\n"))
        self.check11_osmgpsmap()
        self.append_text("\n • ")
        self.check12_graphviz()
        self.check13_pyicu()
        self.check14_ghostscript()
        self.append_text("\n")
        self.check_fontconfig()
        self.append_text("\n")
        yield True
        # Optional
        self.render_text(_("""\n<u><b>Optional</b></u>\n"""))
        self.render_text(_(
            "<i>Installations of the following packages are"
            " <b>optional</b></i>:\n"))
        # TODO mention what they add
        self.append_text(_("Gtkspell enables spell checking in the notes.\n"))
        self.check15_gtkspell()
        self.check16_rcs()
        self.append_text("\n")
        self.append_text(_(
            "Python Image Library (PIL) is needed for cropping images "
            "and LaTeX output."))
        self.append_text("\n • ")
        self.check17_pillow()
        # self.append_text("\n")
        self.check18_gexiv2()
        self.check19_geocodeglib()
        # self.append_text("\n")
        self.check20_ttffreefont()
        self.append_text("\n")
        yield True
        # required development packages
        # TODO only show this section if running in development mode?
        self.render_text(_("\n<u><b>Development & Translation Requirements</b>"
                           "</u>\n"))
        self.render_text(_(
            "<i>Installations of the following packages are"
            " <b>RECOMMENDED</b> if you intend to"
            " translate or do any development (addons etc.)</i>:\n"))
        self.gettext_version()
        self.intltool_version()
        self.sphinx_check()
        self.append_text("\n")
        yield True
        # Optional packages required by Third-party Addons
        self.render_text(_("\n<u><b>Optional packages required by Third-party "
                           "Addons</b></u>\n"))
        self.render_text(_(
            """<i>Prerequistes required for the following <a href="https://"""
            """gramps-project.org/wiki/index.php?title=Third-party_Addons">"""
            """Third-party Addons</a> to work</i>:\n"""))
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
        # self.render_text("""\n<u><b>List of installed Addons.</b></u>\n""")
        # self.list_all_plugins()
        yield True
        # Diagnostic checks
        self.append_text("\n")
        self.render_text(_("""\n<u><b>Diagnostic checks</b></u>\n"""))
        self.append_text(_("Check for potential issues.\n"))
        self.append_text(_("\nEnvironment settings:\n"))
        self.platform_details()
        self.append_text("\n")
        self.locale_settings()
        self.gramps_environment_variables()
        self.render_text(_("\n\n<u><b>Locales available:</b>"
                           "</u>\n"))
        self.locales_installed()
        # mention backing up
        self.append_text("\n")
        self.render_text(_("\n<u><b>Back Up Your Genealogy Files.</b></u>\n"))
        self.append_text(_("If you have a reason to be checking Prerequisites,"
                           " it is the right time to back up your genealogy files,"
                           " and then test your backups!\n\n"))
        self.render_text(_(
            """<i><a href="https://gramps-project.org/wiki/index.php?title"""
            """=How_to_make_a_backup">Backup to Gramps XML</a> You will """
            """find "Make Backup..." in the Family Tree menu of recent Gramps """
            """versions, otherwise use "Export..." in the same menu but uncheck """
            """privacy options in the Exporter Assistant in order to export"""
            """ all data.</i>\n\n"""))
        self.append_text(_(" • Backups can be made at any time and, at a minimum, on "
                           "the first day of every month. But preferrably more often.\n"))
        self.append_text(_(" • It is strongly recommended to backup each"
                           " of your Family Trees before any upgrade.\n"))
        self.append_text(_(" • Test your backups by creating a new Family Tree "
                           "and then importing the backup."),
                         scroll_to="begin")

    def gramps_version(self):
        '''Report Currently installed Gramps Version

        #if current < installed version then mention current version?
        #if current == installed version then don't mention current version?
        #if current > installed version then don't mention current version
                                        running test or development version?

        https://gramps-project.org/wiki/index.php?title=Previous_releases_of_Gramps
        '''
        self.append_text("\n")
        # Start check
        latest_release_message = ("Gramps " +
                                  verstr(self.latest_gramps_version) +
                                  _(", is the most current version.\n"))

        try:
            try:
                from gramps.gen.const import VERSION, VERSION_TUPLE
                gramps_str = VERSION
                gramps_ver = VERSION_TUPLE
            except ImportError:
                # Gramps 3.x series
                from const import VERSION, VERSION_TUPLE
                gramps_str = VERSION
                gramps_ver = VERSION_TUPLE
        except ImportError:
            gramps_str = _('not found')

        # Test
        if not gramps_ver >= self.latest_gramps_version:
            # print("Failed")
            result = (_("You have Gramps %s. Please make a backup and then "
                        "upgrade.\n%s") % (gramps_str, latest_release_message))
        else:
            if not gramps_ver == self.latest_gramps_version:
                result = (_("You have Gramps %s installed; an unreleased "
                            "development version. Thank you for contributing "
                            "and testing; please report any issues. Backups "
                            "are your friend.\n" % (gramps_str)))
                # print(gramps_ver)
            else:
                # print("Success")
                # TODO add further check that this is true?
                result = (_("You have Gramps %s. Congratulations, you have the"
                            " current version.\n") % (gramps_str))

        # End check
        self.render_text(result)
        # self.append_text(result)

    # Requirements
    def check1_python(self):
        '''Check python version Gramps is currently running with against min
        version required

        #TODO - does not handle an older version of Gramps using python 2 on
        that a system that has python 3 installed (same for each of the other
        test)
        '''
        # Start check
        MIN_PYTHON_VERSION = (3, 3, 0)
        min_py_str = verstr(MIN_PYTHON_VERSION)

        # version to check against
        # Gramps running version of python
        py_str = '%d.%d.%d' % sys.version_info[:3]
        check1 = " • Python "

        if not sys.version_info >= MIN_PYTHON_VERSION:
            # print("Failed")
            messagefailed1 = _(" (Requires version ")
            messagefailed3 = _(" or greater installed.)\n")

            messagefailed = messagefailed1 + min_py_str + messagefailed3

            result = check1 + py_str + messagefailed
        else:
            # print("Success")
            messagesuccess1 = _(" (Passed: version ")
            messagesuccess3 = _(" or greater installed.)\n")

            messagesuccess = messagesuccess1 + min_py_str + messagesuccess3

            result = check1 + py_str + messagesuccess
        # End check
        self.append_text(result)

    def check2_gtk(self):
        '''Check GTK+ version

        GTK 3.10 or greater - A cross-platform widget toolkit for creating
        graphical user interfaces. http://www.gtk.org/

        min: GTK+ 3.10.0
        '''
        # Start check
        MIN_GTK_VERSION = (3, 12, 0)

        try:
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk
            try:
                gtk_result = (Gtk.get_major_version(), Gtk.get_minor_version(),
                              Gtk.get_micro_version())
                gtkver_str = '%d.%d.%d' % gtk_result
            except Exception:  # any failure to 'get' the version
                gtkver_str = _('unknown version')
                gtk_result = (0, 0, 0)
        except ImportError:
            gtkver_str = _('not found')
            gtk_result = (0, 0, 0)
            # no DISPLAY is a RuntimeError in an older pygtk
            # (e.g. 2.17 in Fedora 14)
        except RuntimeError:
            gtkver_str = _('DISPLAY not set')
            gtk_result = (0, 0, 0)
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
        # no DISPLAY is a RuntimeError in an older pygtk
                        (e.g. 2.17 in Fedora 14)
        except RuntimeError:
            gtkver_str = 'DISPLAY not set'
            pygtkver_str = 'DISPLAY not set'
        '''

        # Test
        if not gtk_result >= MIN_GTK_VERSION:
            # print("Failed")
            result = (" • GTK+ " + gtkver_str + _(" (Requires version ") +
                      verstr(MIN_GTK_VERSION) + _(" or greater.)\n"))
        else:
            # print("Success")
            result = (" • GTK+ " + gtkver_str + _(" (Passed: version ") +
                      verstr(MIN_GTK_VERSION) + _(" or greater installed.)\n"))

        # End check
        self.append_text(result)

    def check3_pygobject(self):
        '''Check for pygobject

        pygobject 3.12 or greater - Python Bindings for GLib/GObject/GIO/GTK+
        https://wiki.gnome.org/Projects/PyGObject

         # pygobject 3.12+
        '''
        # Start check
        MIN_PYGOBJECT_VERSION = (3, 12, 0)

        try:
            from gi.repository import GObject
            try:
                pygobjectver_str = verstr(GObject.pygobject_version)
                pygobject_result = GObject.pygobject_version
            except Exception:  # any failure to 'get' the version
                pygobjectver_str = _('unknown version')
                pygobject_result = (0, 0, 0)

        except ImportError:
            pygobjectver_str = _('not found')
            pygobject_result = (0, 0, 0)

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
            # print("Failed")
            result = (" • PyGObject " + pygobjectver_str +
                      _(" (Requires version ") +
                      verstr(MIN_PYGOBJECT_VERSION) + _(" or greater.)\n"))
        else:
            # print("Success")
            result = (" • PyGObject " + pygobjectver_str +
                      _(" (Passed: version ") +
                      verstr(MIN_PYGOBJECT_VERSION) +
                      _(" or greater installed.)\n"))

        # End check
        self.append_text(result)

    def check4_cairo(self):
        '''Check cairo installed with GObject Introspection bindings
        (the gi package)
        '''
        # Start check
        MIN_CAIRO_VERSION = (1, 13, 1)
        # min version that pycairo supports is 1.13.1
        MIN_PYCAIRO_VERSION = (1, 13, 3)

        try:
            import cairo
            try:
                cairover_str = cairo.cairo_version_string()
                cairover_tpl = vertup(cairover_str)

                pycairo_result = cairo.version_info
                pycairover_str = cairo.version
                # print("pycairo_result : " + str(pycairo_result))

                cairo_result = cairover_tpl
                # print("cairo_result : " + str(cairo_result))
            except Exception:  # any failure to 'get' the version
                pycairover_str = _('unknown version')
                cairover_str = _('unknown version')

        except ImportError:
            pycairover_str = _('not found')
            cairover_str = _('not found')

        # Test Cairo
        if not cairo_result >= MIN_CAIRO_VERSION:
            # print("Failed")
            result = (" • Cairo " + cairover_str + _(" (Requires version ") +
                      verstr(MIN_CAIRO_VERSION) + _(" or greater.)\n"))
        else:
            # print("Success")
            result = (" • Cairo " + cairover_str + _(" (Passed: version ") +
                      verstr(MIN_CAIRO_VERSION) +
                      _(" or greater installed.)\n"))

        self.append_text(result)
        # Test pycairo
        if not pycairo_result >= MIN_PYCAIRO_VERSION:
            # print("Failed")
            result = (" • Pycairo " + pycairover_str + _(" (Requires ") +
                      verstr(MIN_PYCAIRO_VERSION) + _(" or greater.)\n"))
        else:
            # print("Success")
            result = (" • Pycairo " + pycairover_str + _(" (Passed: version ") +
                      verstr(MIN_PYCAIRO_VERSION) +
                      _(" or greater installed.)\n"))

        # End check
        self.append_text(result)

    def check5_pango(self):
        '''Check pango is installed with GObject Introspection bindings
        (the gi package)

        pangocairo - Allows you to use Pango with Cairo
        '''
        # Start check
        PANGO_MIN_VER = (1, 29, 3)  # TODO Find out min supported version

        try:
            from gi.repository import Pango
            try:
                pangover_str = Pango.version_string()
                # print("pangover_str " + pangover_str)
                pango_result = vertup(pangover_str)
            except Exception:  # any failure to 'get' the version
                pangover_str = _('unknown version')
                pango_result = (0, 0, 0)

        except ImportError:
            pangover_str = _('not found')
            pango_result = (0, 0, 0)

        # Test Pango
        if not pango_result >= PANGO_MIN_VER:
            # print("Failed")
            result = (" • Pango " + pangover_str + _(" (Requires version ") +
                      verstr(PANGO_MIN_VER) + _(" or greater.)\n"))
        else:
            # print("Success")
            result = (" • Pango " + pangover_str + _(" (Passed: version ") +
                      verstr(PANGO_MIN_VER) + _(" or greater installed.)\n"))

        # TODO add the following test to gramps -v
        try:
            # import cairo
            # from gi.repository import Pango
            from gi.repository import PangoCairo
            pangocairo_str = PangoCairo._version
            # print("pangocairo_str " + str(pangocairo_str))
        except ImportError:
            pangocairo_str = _("not found")

        '''
        # Test Pangocairo
        if not pango_result >= PANGO_MIN_VER:
            #print("Failed")
            result = (" • Pango " + pangover_str + " (Requires version " +
                      verstr(PANGO_MIN_VER) + " or greater.)\n")
        else:
            #print("Success")
            result = (" • Pango " + pangover_str + " (Passed: version " +
                      verstr(PANGO_MIN_VER) + " or greater installed.)\n")
        '''
        # to be added here
        result += " • PangoCairo " + str(pangocairo_str)
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
            bsddb_str = bsddb.__version__  # Python adaptation layer
            # Underlying DB library
            bsddb_db_str = str(bsddb.db.version()).replace(', ', '.') \
                .replace('(', '').replace(')', '')
        except ImportError:
            bsddb_str = _('not found')
            bsddb_db_str = _('not found')

        result = (_(" • Berkeley Database library (bsddb3: ") + bsddb_db_str +
                  ") (Python-bsddb3 : " + bsddb_str + ")")
        # End check
        self.append_text(result)

    def check7_sqlite3(self):
        '''sqlite3
        #TODO need to add to required section readme

        https://stackoverflow.com/a/1546162
        '''
        self.append_text("\n")
        # Start check
        # SQLITE_MIN_VERSION = (0, 0, 0)

        try:
            import sqlite3
            # sqlite3.version - pysqlite version
            sqlite3_py_version_str = sqlite3.version
            # sqlite3.sqlite_version - sqlite version
            sqlite3_version_str = sqlite3.sqlite_version
        except ImportError:
            sqlite3_version_str = _('not found')
            sqlite3_py_version_str = _('not found')

        result = (_(" • SQLite Database library (sqlite3: ") +
                  sqlite3_version_str + ") (Python-sqlite3: " +
                  sqlite3_py_version_str + ")")
        # End check
        self.append_text(result)

    def check8_xdgutils(self):
        '''xdg-utils

        #TODO where is this used in the gramps code?  or how?
        '''
        self.append_text("\n")
        # Start check

        result = _(" • xdg-utils (Manual check see instructions link)")
        # End check
        self.append_text(result)

    def check9_librsvg2(self):
        '''librsvg2

        #TODO where is this used in the gramps code?
        or it a support library for cairo?
        '''
        self.append_text("\n")
        # Start check

        result = _(" • librsvg2 (Manual check see instructions link)")
        # End check
        self.append_text(result)

    def check10_languagepackgnomexx(self):
        '''Check language-pack-gnome-xx for currently used Locale?'''
        self.append_text("\n")
        # Start check

        # self.render_text("""<b> x :</b> """)
        # <a href="https://gramps-project.org/wiki/index.php?title=xxx">xxx</a>
        result = _(" • language-pack-gnome-xx (Manual check see instructions "
                   "link) for your Language <show locale here TBD>")
        # End check
        self.append_text(result)

    # STRONGLY RECOMMENDED
    def check11_osmgpsmap(self):
        '''osmgpsmap'''
        # Start check
        OSMGPSMAP_MIN_VERSION = (1, 0)
        OSMGPSMAP_FOUND = False

        try:
            from gi import Repository
            repository = Repository.get_default()
            if repository.enumerate_versions("OsmGpsMap"):
                gi.require_version('OsmGpsMap', '1.0')
                from gi.repository import OsmGpsMap as osmgpsmap
                try:
                    osmgpsmap_str = osmgpsmap._version
                    OSMGPSMAP_FOUND = True
                except Exception:  # any failure to 'get' the version
                    osmgpsmap_str = _('unknown version')
            else:
                osmgpsmap_str = _('not found')

        except ImportError:
            osmgpsmap_str = _('not found')

        if OSMGPSMAP_FOUND:
            result = (" • osmgpsmap " + osmgpsmap_str +
                      _(" (Passed: version ") + verstr(OSMGPSMAP_MIN_VERSION) +
                      _(" or greater installed.)"))
        else:
            result = (" • osmgpsmap " + osmgpsmap_str +
                      _(" (Requires version ") +
                      verstr(OSMGPSMAP_MIN_VERSION) + _(" or greater)"))

        # End check
        self.append_text(result)

    def check12_graphviz(self):
        '''Graphviz

        Needs the liblasi library with utf-8 support to create ps/ps2 output

        GRAPHVIZ_MIN_VER = (2, 28)


        https://github.com/Alexpux/MINGW-packages/issues/737#issuecomment-147185667
        # bpisoj commented that Gramps needs a version of Graphviz that :
        [needs additional]...library be added to msys2-mingw stack as
        libann, libgts and liblasi?
        I am interested in last one as only that support utf-8 characters
        in ps/ps2 output.
        '''
        # self.append_text("\n")
        # Start check

        try:
            dotversion_str = Popen(['dot', '-V'],
                                   stderr=PIPE).communicate(input=None)[1]
            if isinstance(dotversion_str, bytes) and sys.stdin.encoding:
                dotversion_str = dotversion_str.decode(sys.stdin.encoding)
            if dotversion_str:
                dotversion_str = dotversion_str.replace('\n', '')[23:27]
        except Exception:
            dotversion_str = _('Graphviz not in system PATH')

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
            except Exception:  # any failure to 'get' the version
                pyicu_str = _('unknown version')
                icu_str = _('unknown version')

        except ImportError:
            pyicu_str = _('not found')
            icu_str = _('not found')

        result = " • PyICU " + pyicu_str + "(ICU " + icu_str + ")"
        # End check
        self.append_text(result)

    def check14_ghostscript(self):
        '''Ghostscript - need to add to strongly recomended or optional?
        section of readme

        Q:What does it do ?
        A:
        https://www.gramps-project.org/wiki/index.php?title=Gramps_5.0_Wiki_Manual_-_Reports_-_part_5#Graphviz_Layout
        *Number of Horizontal Pages: (1 default) Graphviz can create very
         large graphs by spreading the graph across a rectangular array of
         pages. This controls the number of pages in the array horizontally.
         Only valid for dot and pdf via Ghostscript.
        *Number of Vertical Pages: (1 default) Graphviz can create very large
         graphs by spreading the graph across a rectangular array of pages.
         This controls the number of pages in the array vertically.
         Only valid for dot and pdf via Ghostscript.
        '''
        self.append_text("\n")
        # Start check

        try:
            if win():
                try:
                    gsvers_str = Popen(['gswin32c', '--version'],
                                       stdout=PIPE).communicate(input=None)[0]
                except Exception:
                    gsvers_str = Popen(['gswin64c', '--version'],
                                       stdout=PIPE).communicate(input=None)[0]
            else:
                gsvers_str = Popen(['gs', '--version'],
                                   stdout=PIPE).communicate(input=None)[0]
            if isinstance(gsvers_str, bytes) and sys.stdin.encoding:
                gsvers_str = gsvers_str.decode(sys.stdin.encoding)
            if gsvers_str:
                gsvers_str = gsvers_str.replace('\n', '')
        except Exception:
            gsvers_str = _('Ghostscript not in system PATH')

        result = " • Ghostscript " + gsvers_str
        # End check
        self.append_text(result)

    def check_fontconfig(self):
        ''' The python-fontconfig library is used to support the Genealogical
        Symbols tab of the Preferences.  Without it Genealogical Symbols don't
        work '''
        try:
            import fontconfig
            vers = fontconfig.__version__
            if vers.startswith("0.5."):
                result = (" • python-fontconfig " + vers +
                          _(" (Passed: version 0.5.x is installed.)"))
            else:
                result = (" • python-fontconfig " + vers +
                          _(" (Requires version 0.5.x)"))
        except ImportError:
            result = _(
                " • python-fontconfig not found, (Requires version 0.5.x)")
        except AttributeError:
            result = _(" • python-fontconfig installed, version unavailable")
        # End check
        self.append_text(result)

    # Optional
    def check15_gtkspell(self):
        '''gtkspell & enchant

        #TODO add check for gtspell to "gramps -v"  section

        https://github.com/gramps-project/gramps/blob/maintenance/gramps50/gramps/gui/spell.py

        # TODO (check what MacOS uses?) look like it uses this one.
        https://gramps-project.org/wiki/index.php?title=Download#Mac_OS_X
        Gramps uses a different spell checker than the one provided by
        Mac OS X, with different spelling dictionary requirements.

        Enable spell checking in the notes. Gtkspell depends on enchant.
        A version of gtkspell with gobject introspection is needed,
        so minimally version 3.0.0

        ---------
        # typing "import enchant"  works for the AIO but no version string
        -------------
        #TODO list installed dictionaries (issues with win ver if they are not
        all installed! eg: csv imports from other languages)
        '''
        # Start check
        GTKSPELL_MIN_VER = (3, 0)
        gtkspell_min_ver_str = verstr(GTKSPELL_MIN_VER)
        # ENCHANT_MIN_VER = (0, 0)  # TODO ?
        gtkspell_ver_tp = (0, 0)
        # Attempting to import gtkspell gives an error dialog if gtkspell is
        # not available so test first and log just a warning to the console
        # instead.
        try:
            from gi import Repository
            repository = Repository.get_default()
            gtkspell_ver = _("not found")
            if repository.enumerate_versions("GtkSpell"):
                try:
                    gi.require_version('GtkSpell', '3.0')
                    from gi.repository import GtkSpell as Gtkspell
                    gtkspell_ver = str(Gtkspell._version)
                    aaa = Gtkspell._version.split(".")
                    v1 = int(aaa[0])
                    v2 = int(aaa[1])
                    gtkspell_ver_tp = (v1, v2)
                    # print("gtkspell_ver " + gtkspell_ver)
                except Exception:
                    gtkspell_ver = _("not found")
            elif repository.enumerate_versions("Gtkspell"):
                try:
                    gi.require_version('Gtkspell', '3.0')
                    from gi.repository import Gtkspell
                    gtkspell_ver = str(Gtkspell._version)
                    gtkspell_ver_tp = Gtkspell._version
                    # print("gtkspell_ver " + gtkspell_ver)
                except Exception:
                    gtkspell_ver = _("not found")
        except Exception:
            gtkspell_ver = _("not found")

        # test for enchant
        try:
            from ctypes import cdll, c_char_p
            try:
                enchant = cdll.LoadLibrary("libenchant")
            except FileNotFoundError:
                enchant = cdll.LoadLibrary("libenchant-2")
            enchant_ver_call = enchant.enchant_get_version
            enchant_ver_call.restype = c_char_p
            enchant_result = enchant_ver_call().decode("utf-8")
        except Exception:
            enchant_result = _("not found")

        if gtkspell_ver_tp >= GTKSPELL_MIN_VER:
            result = (" • GtkSpell " + gtkspell_ver + _(" (Passed: version ") +
                      gtkspell_min_ver_str +
                      _(" or greater installed.) (enchant module: ") +
                      enchant_result + ")")
        else:
            result = (" • GtkSpell " + gtkspell_ver + _(" (Requires version ") +
                      gtkspell_min_ver_str +
                      _(" or greater installed.) (enchant module: ") +
                      enchant_result + ")")

        # End check
        self.append_text(result)

    def check16_rcs(self):
        '''GNU Revision Control System (RCS)

        The GNU Revision Control System (RCS) can be used to manage multiple
        revisions of your family trees. Only rcs is needed, NO python bindings
        are required. See info at
        https://gramps-project.org/wiki/index.php?title=Gramps_5.0_Wiki_Manual_-_Manage_Family_Trees#Archiving_a_Family_Tree

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
        License GPLv3+: GNU GPL version 3 or later
        <http://gnu.org/licenses/gpl.html>
        This is free software: you are free to change and redistribute it.
        There is NO WARRANTY, to the extent permitted by law.
        '''
        self.append_text("\n")
        # Start check
        RCS_MIN_VER = (5, 9, 4)
        rcs_ver_str = verstr(RCS_MIN_VER)
        # print("os.environ: %s " % os.environ)
        try:
            if win():
                _RCS_FOUND = os.system("rcs -V >nul 2>nul") == 0
                RCS_RESULT = _("installed")
                # print("rcs -V : " + os.system("rcs -V"))
                if _RCS_FOUND and "TZ" not in os.environ:
                    # RCS requires the "TZ" variable be set.
                    os.environ["TZ"] = str(time.timezone)
            else:
                _RCS_FOUND = os.system("rcs -V >/dev/null 2>/dev/null") == 0
                # print("xx rcs -V : " + os.system("rcs -V"))
                RCS_RESULT = _("installed")
        except Exception:
            _RCS_FOUND = False
            RCS_RESULT = _("not found")

        # Test
        if _RCS_FOUND:  # TODO actually test for version
            result = (_(" • rcs %s TBD (Passed: version %s or greater "
                        "installed. If not on Microsoft Windows)") %
                      (RCS_RESULT, rcs_ver_str))
        else:
            result = (_(" • rcs %s TBD (Requires version %s or greater "
                        "installed. If not on Microsoft Windows)") %
                      (RCS_RESULT, rcs_ver_str))

        # End check
        self.append_text(result)

    def check17_pillow(self):
        '''PILLOW
        Allows Production of jpg images from non-jpg images in LaTeX documents

        #TODO prculley mentions that : And PIL (Pillow) is also used by the
        main Gramps ([]narrativeweb and []other reports for image cropping)
        as well as [x]editexifmetadata and the
        new [x]latexdoc type addons (genealogytree).

        #TODO add check for PILLOW to "gramps -v"  section

        https://github.com/gramps-project/gramps/blob/maintenance/gramps50/gramps/plugins/docgen/latexdoc.py
        '''
        # self.append_text("\n")
        # Start check

        try:
            import PIL
            # from PIL import Image
            try:
                pil_ver = PIL.__version__
            except Exception:
                try:
                    pil_ver = str(PIL.PILLOW_VERSION)
                except Exception:
                    try:
                        # print(dir(PIL))
                        pil_ver = str(PIL.VERSION)
                    except Exception:
                        pil_ver = _("Installed but does not supply version")
        except ImportError:
            pil_ver = _("not found")

        result = "(PILLOW " + pil_ver + ")"
        # End check
        self.append_text(result)

    def check18_gexiv2(self):
        ''' wrapper for Options '''
        self.append_text("\n • ")
        self.check_gexiv2()

    def check_gexiv2(self):
        '''GExiv2 - is a GObject wrapper around the Exiv2 photo metadata
        library. It allows for Gramps to inspect EXIF, IPTC, and XMP metadata
        in photo and video files of various formats.
        https://wiki.gnome.org/Projects/gexiv2

        which requires the:  Exiv2 library - to manage image metadata.
        http://www.exiv2.org/

        GEXIV_MIN: GObject Introspection support added in gexiv2 0.5,
        now has excellent bindings for Python 2 & 3 available.

        https://github.com/GNOME/gexiv2/blob/gexiv2-0.10/configure.ac
        # m4_define([gexiv2_major_version], [0])
        # m4_define([gexiv2_minor_version], [10])
        # m4_define([gexiv2_micro_version], [6])
        MAJOR_VERSION, MICRO_VERSION, MINOR_VERSION

        EXIV2_MIN: To build the current version of gexiv2, you will first
        need to install libexiv2 version 0.21 or better,
        # m4_define([exiv2_required_version], [0.21])

        dir(GExiv2)
        ['LogLevel', 'MAJOR_VERSION', 'MICRO_VERSION', 'MINOR_VERSION',
         'Metadata', 'MetadataClass', 'MetadataPrivate', 'Orientation',
         'PreviewImage', 'PreviewImageClass', 'PreviewImagePrivate',
         'PreviewProperties', 'PreviewPropertiesClass',
         'PreviewPropertiesPrivate', 'StructureType', 'XmpFormatFlags',
         '_introspection_module', '_namespace', '_overrides_module',
         '_version', 'get_version', 'initialize', 'log_get_level',
         'log_set_level', 'log_use_glib_logging']
        '''
        # Start check

        try:
            from gi import Repository
            repository = Repository.get_default()
            if repository.enumerate_versions("GExiv2"):
                gi.require_version('GExiv2', '0.10')
                from gi.repository import GExiv2
                try:
                    gexiv2_str = GExiv2._version
                except Exception:  # any failure to 'get' the version
                    gexiv2_str = _('unknown version')
            else:
                gexiv2_str = _('not found')

        except ImportError:
            gexiv2_str = _('not found')
        except ValueError:
            gexiv2_str = ('not new enough')

        try:
            vers_str = Popen(['exiv2', '-V'],
                             stdout=PIPE).communicate(input=None)[0]
            if isinstance(vers_str, bytes) and sys.stdin.encoding:
                vers_str = vers_str.decode(sys.stdin.encoding)
            indx = vers_str.find('exiv2 ') + 6
            vers_str = vers_str[indx: indx + 4]
        except Exception:
            vers_str = _('not found')
        result = _("GExiv2 : %s (Exiv2 library : %s)") % (gexiv2_str, vers_str)
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
        except Exception:
            geocodeglib_ver = _("not found")
            GEOCODEGLIB = False

        if GEOCODEGLIB:
            result = (" • geocodeglib " + geocodeglib_ver +
                      _(" (Passed: version ") + geocodeglib_min_ver +
                      _(" or greater installed.)"))
        else:
            result = (" • geocodeglib " + geocodeglib_ver +
                      _(" (Requires version ") + geocodeglib_min_ver +
                      _(" or greater installed.)"))

        # End check
        self.append_text(result)

    def check20_ttffreefont(self):
        '''ttf-freefont
        More font support in the reports

        #where is this refered to in the gramps code?
        which reports are being reffered to?

        https://askubuntu.com/questions/552979/how-can-i-determine-which-fonts-are-installed-from-the-command-line-and-what-is

        use console command (this command should be available for all
        ubuntu-based distributions) :

        fc-list
        # Start check

        result = _(" • ttf-freefont (Manual check see instructions link)")
        # End check
        self.append_text(result)
        '''

        self.append_text("\n")
        # Start check
        import subprocess
        try:
            cmd = 'fc-match "White Rabbit"'
            retcode, version_str = subprocess.getstatusoutput(cmd)
            _ver = version_str.find('Whi')
            ver_ = version_str.find('bit')
            if _ver > 0 and ver_ > 0:
                vers = version_str[_ver:ver_ + 3]
            else:
                vers = _("found another font")
            if retcode != 0:
                vers = _("not found")
        except Exception:
            vers = _("not found")
        result = " • Installed font: %s\n" % vers
        # End check
        self.render_text(_(
            """For addon Networkchart, font <a href="https://"""
            """www.fontsquirrel.com/fonts/white-rabbit">White """
            """Rabbit</a> provides an extremely """
            """readable result.\n"""))
        self.append_text(result)

    # Optional packages required by Third-party Addons
    def check21_familysheet(self):
        '''Family Sheet
        (requires PILLOW should already be installed as part of Gramps)'''
        self.render_text(
            """ 01. <b><a href="https://gramps-project.org/wiki"""
            """/index.php?title=Addon:Family_Sheet#Prerequisites">"""
            """Addon:Family Sheet</a> :</b> """)
        # Start check
        self.check17_pillow()
        # End check
        # self.append_text("\n")

    def check22_graphview(self):
        '''
        Graph View - Requires: PyGoocanvas and Goocanvas and
        graphviz (python-pygoocanvas, gir1.2-goocanvas-2.0)
        '''
        self.append_text("\n")
        self.render_text(
            """ 02. <b><a href="https://gramps-project.org/wiki"""
            """/index.php?title=Addon:Graph_View#Prerequisites">"""
            """Addon:Graph View</a> :</b> """)
        # Start check

        # check for GooCanvas
        try:
            try:
                gi.require_version('GooCanvas', '2.0')
            except Exception:
                print(_("Why, when same code works in Graphview"))
            from gi.repository import GooCanvas
            goocanvas_ver = str(GooCanvas._version)
            # print("GooCanvas version:" + goocanvas_ver)
        except ImportError:
            goocanvas_ver = _("not installed")

        result = "(GooCanvas:" + goocanvas_ver + ")(PyGoocanvas: TBD?)"
        # End check
        self.append_text(result)
        self.append_text("(")
        self.check12_graphviz()
        self.append_text(")")

    def check23_pedigreechart(self):
        '''PedigreeChart - Can optionally use - NumPy if installed

        https://github.com/gramps-project/addons-source/blob/master/PedigreeChart/PedigreeChart.py
        '''
        self.append_text("\n")
        self.render_text(""" 03. <b><a href="https://gramps-project.org/wiki"""
                         """/index.php?title=Addon:PedigreeChart#Prerequisites">"""
                         """Addon:PedigreeChart</a> :</b> """)
        # Start check

        try:
            import numpy
            numpy_ver = str(numpy.__version__)
            # print("numpy.__version__ :" + numpy_ver )
            # NUMPY_check = True
        except ImportError:
            numpy_ver = _("not found")
            # NUMPY_check = False

        result = "(NumPy : " + numpy_ver + " )"
        # End check
        self.append_text(result)
        # self.append_text("\n")

    def check24_networkchart(self):
        '''Network Chart - requires networkx 1.11, pygraphviz,
           (need to add to readme) '''
        self.append_text("\n")
        self.render_text(""" 04. <b><a href="https://gramps-project.org/wiki"""
                         """/index.php?title=Addon:NetworkChart#Prerequisites">"""
                         """Addon:Network Chart</a> :</b> """)
        # Start check
        # To get "libcgraph" for pygraphviz you first need to install
        # the development package of graphviz eg: graphviz-dev

        try:
            # import importlib
            # module1 = importlib.find_loader("networkx") is not None
            import networkx
            networkx_ver = str(networkx.__version__)
            # print("networkx version:" + networkx_ver)
        except Exception:
            networkx_ver = _("not installed")
            # module1 = "Not tested"

        try:
            # import importlib
            # module2 = importlib.find_loader("pydotplus") is not None
            import pydotplus
            pydotplus_ver = str(pydotplus.pyparsing_version)
            # print("pydotplus version:" + pydotplus_ver)
        except Exception:
            pydotplus_ver = _("not installed")
            # module2 = "Not tested"

        try:
            # import importlib
            # module3 = importlib.find_loader("pygraphviz") is not None
            import pygraphviz
            pygraphviz_ver = str(pygraphviz.__version__)
            # print("pygraphviz version:" + pygraphviz_ver)
        except Exception:
            pygraphviz_ver = _("not installed")
            # module3 = "Not tested"

        # End check
        self.append_text("(networkx " + networkx_ver + ")(")
        self.check12_graphviz()
        self.append_text(")\n")
        self.append_text(_("     and one of either: (pydotplus: ") +
                         pydotplus_ver +
                         _(") or (pygraphviz: ") + pygraphviz_ver + ")")

    def check25_genealogytree(self):
        '''genealogytrees - requires texlive including the
        textlive-pictures package and  genealogytree and
        lualatex for pdf conversion

        * PILLOW

        #TODO need to add to readme

        https://github.com/gramps-project/addons-source/tree/maintenance/gramps50/GenealogyTree
        https://gramps-project.org/bugs/view.php?id=10223
        https://github.com/gramps-project/gramps/blob/maintenance/gramps50/gramps/gen/plug/docgen/treedoc.py
        '''
        self.append_text("\n")
        self.render_text(""" 05. <b><a href="https://gramps-project.org/wiki"""
                         """/index.php?title=Addon:GenealogyTree#Prerequisites">"""
                         """Addon:GenealogyTree</a> :</b> """)
        # Start check
        _LATEX_RESULT = _("not found")
        if win():
            if search_for("lualatex.exe"):
                # print("_LATEX_FOUND win: " + str(_LATEX_FOUND) )
                _LATEX_RESULT = _("Installed(MS-Windows)")
        else:
            if search_for("lualatex"):
                # print("_LATEX_FOUND lin/mac: " + str(_LATEX_FOUND) )
                _LATEX_RESULT = _("Installed(Linux/Mac)")

        result = "(lualatex :" + _LATEX_RESULT + ")"
        # End check
        self.append_text(result)
        self.check17_pillow()
        # self.append_text("\n")

    def check26_htmlview(self):
        '''HTMLView

        Html Renderer
        Can use the Webkit or Gecko ( Mozilla ) library

        https://github.com/gramps-project/addons-source/blob/maintenance/gramps50/HtmlView/htmlview.py
        '''
        self.append_text("\n")
        self.render_text(""" 06. <b><a href="https://gramps-project.org/wiki"""
                         """/index.php?title=Addon:HtmlView#Prerequisites">"""
                         """Addon:HTMLView</a> :</b> """)
        # Start check
        NOWEB = 0
        WEBKIT = 1
        # MOZILLA = 2
        KITNAME = ["None", "WebKit", "Mozilla"]
        TOOLKIT = NOWEB

        try:
            gi.require_version('WebKit', '3.0')
            from gi.repository import WebKit as webkit
            webkit_ver = str(webkit._version)
            # print("webkit version " + webkit_ver)
            TOOLKIT = WEBKIT
        except Exception:
            webkit_ver = _("not installed ")
            TOOLKIT = NOWEB

        if TOOLKIT is NOWEB:
            # print("0")
            result012 = ")"
        else:
            # print("1/2")
            result012 = " / " + str(KITNAME[TOOLKIT]) + ")"

        result = "(Webkit: " + webkit_ver + result012
        # End check
        self.append_text(result)
        # self.append_text("\n")

    def check27_googlemapkml(self):
        r'''GoogleMapKML - Needs Google Earth Desktop Program installed to
                           view locations

        https://www.google.com/earth/desktop/
        [x]Google Earth Standard:
        C:\Program Files (x86)\Google\Google Earth\client

        [ ]Google Earth Pro:
        C:\Program Files (x86)\Google\Google Earth Pro\client

        [ ]Google Earth for Chrome:
        ??

        https://github.com/gramps-project/addons-source/blob/maintenance/gramps50/GoogleEarthWriteKML/GoogleEarthWriteKML.py

        #TODO rename wiki page (so as not to clash with builtin map services
        then make it redirect to user manual)
        '''
        self.append_text("\n")
        self.render_text(""" 07. <b><a href="https://gramps-project.org/wiki"""
                         """/index.php?title=Addon:MapService-GoogleEarth#Prerequisites">"""
                         """Addon:GoogleMapKML</a> :</b> """)
        # Start check

        # Check if zip is installed
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
        _GOOGLEEARTH_STATUS = _("not found.")
        if os.sys.platform == 'win32':
            FILE_PATH = r'"%s\Google\Google Earth\googleearth.exe"' \
                        % (os.getenv('ProgramFiles'))
            NORM_PATH = os.path.normpath(FILE_PATH)
            _GOOGLEEARTH_OK = search_for(NORM_PATH)
            _GOOGLEEARTH_STATUS = "Standard. found."

            if not _GOOGLEEARTH_OK:
                # For Win 7 with 32 Gramps
                FILE_PATH = r'"%s\Google\Google Earth\client\googleearth.exe"' \
                            % (os.getenv('ProgramFiles'))
                NORM_PATH = os.path.normpath(FILE_PATH)
                _GOOGLEEARTH_OK = search_for(NORM_PATH)
                _GOOGLEEARTH_STATUS = "Standard. found2."

            if not _GOOGLEEARTH_OK:
                # For Win 7 with 64 Gramps, find path to 32 bits programs
                FILE_PATH = r'"%s\Google\Google Earth\client\googleearth.exe"' \
                            % (os.getenv('ProgramFiles(x86)'))
                NORM_PATH = os.path.normpath(FILE_PATH)
                _GOOGLEEARTH_OK = search_for(NORM_PATH)
                _GOOGLEEARTH_STATUS = _("Standard. Passed: program installed -"
                                        " 32bit on 64bit Win OS.")

        else:
            FILE_PATH = "googleearth"
            SEARCH = os.environ['PATH'].split(':')
            for lpath in SEARCH:
                prog = os.path.join(lpath, FILE_PATH)
                if os.path.isfile(prog):
                    _GOOGLEEARTH_OK = True
                    _GOOGLEEARTH_STATUS = _("Installed")
            if not _GOOGLEEARTH_OK:
                FILE_PATH = "google-earth"
                SEARCH = os.environ['PATH'].split(':')
                for lpath in SEARCH:
                    prog = os.path.join(lpath, FILE_PATH)
                    if os.path.isfile(prog):
                        _GOOGLEEARTH_OK = True
                        _GOOGLEEARTH_STATUS = _("Installed")

        result = ("""(<a href="https://www.google.com/earth/desktop/">"""
                  "Google Earth on Desktop</a> : " + _GOOGLEEARTH_STATUS + ")")
        # (_ZIP_OK :""" + str(_ZIP_OK) + """)"""
        # End check
        self.render_text(result)
        # self.append_text("\n")

    def check28_webconnectpacks(self):
        '''Webconnect Pack - needs the gramps addon : "libwebconnect"
            installed at the same time.

        libwebconnect is the support Library for web site collections.
        '''
        self.append_text("\n")
        self.render_text(""" 08. <b><a href="https://gramps-project.org/wiki/"""
                         """index.php?title=Addon:Web_Connect_Pack#Prerequisites">"""
                         """Addon:Webconnect Pack</a> :</b> """)
        # Start check

        try:
            import libwebconnect
            LIBWEBCONNECT_test = True
            LIBWEBCONNECT_result = _("Installed")
            # TODO add version addon string.
        except Exception:
            LIBWEBCONNECT_test = False
            LIBWEBCONNECT_result = _("not found")

        if LIBWEBCONNECT_test:
            result = "(libwebconnect : " + LIBWEBCONNECT_result + ")(Passed)"
        else:
            result = ("(libwebconnect : " + LIBWEBCONNECT_result +
                      _(") (Requires the gramps addon listed under "
                        "'Plugin lib')"))
        # End check
        self.append_text(result)
        # self.append_text("\n")

    def check29_tmgimporter(self):
        '''
        TMG Importer Addon

        Import from an Whollygenes - The Master Genealogist (TMG)
        Project backup file(*.SQZ)

        requires DBF 0.96.8 or greater to function

        Please install DBF from https://pypi.python.org/pypi/dbf

        # initial reason I made this prerequistes addon.
        '''
        self.append_text("\n")
        self.render_text(""" 09. <b><a href="https://gramps-project.org/wiki"""
                         """/index.php?title=Addon:TMGimporter#Prerequisites">"""
                         """Addon:TMG Importer</a> :</b> """)
        # Start check
        DBF_MIN_VERSION = (0, 96, 8)

        try:
            # External Library: dbf.pypi
            # https://pypi.python.org/pypi/dbf
            import dbf
            dbf_ver = dbf.version
            dbf_ver_str = str(dbf_ver)
            # print("DBF version = ", dbf_ver)
            dbfavailable = _("DBF installed")
        except ImportError:
            dbf_ver = (0, 0, 0)
            dbf_ver_str = _("not found")
            dbfavailable = _("not found")
        # test version
        if not dbf_ver >= DBF_MIN_VERSION:
            # print("Failed")
            result = (" (DBF " + dbfavailable + _(".)(Requires version ") +
                      verstr(DBF_MIN_VERSION) + _(" or greater installed.)"))
        else:
            # print("Success")
            result = (" (DBF " + dbf_ver_str +
                      _(" installed.)(Passed: version ") +
                      verstr(DBF_MIN_VERSION) + _(" or greater installed.)"))

        # result = "(DBF : " + dbf_ver + ")" + dbfavailable
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
        The number is formed by converting the major, minor, and revision
        numbers into two-decimal-digit numbers and appending them together.
        For example, version 8.1.5 will be returned as 80105.

        command line:
        psql -V
        '''
        self.append_text("\n")
        self.render_text(""" 10. <b><a href="https://gramps-project.org/wiki"""
                         """/index.php?title=DB-API_Database_Backend#"""
                         """Postgresql">Addon:PostgreSQL#Prerequisites</a></b>"""
                         """ Database library Support : """)
        # Start check
        try:
            import psycopg2
            psycopg2_ver = str(psycopg2.__version__)
            # print(dir(psycopg2))
            # print("psycopg2" + psycopg2_ver)
            try:
                libpq_ver = str(psycopg2.__libpq_version__)
            except AttributeError:
                libpq_ver = _("not found.")
        except ImportError:
            psycopg2_ver = _("not found.")
            libpq_ver = _("not found.")

        result = ("(PostgreSQL " + libpq_ver + ")(psycopg2 : " +
                  psycopg2_ver + ")")
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
        self.render_text(""" 11. <b><a href="https://gramps-project.org/"""
                         """wiki/index.php?title=Addon:Edit_Image_Exif_Metadata#Prerequisites">"""
                         """Addon:Edit Image Exif Metadata</a> :</b> """)

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
        self.append_text(" ")
        self.check_gexiv2()

    def check32_phototagginggramplet(self):
        '''PhotoTaggingGramplet - Gramplet for tagging people in photos

        If the OpenCV is not found, the automatic face detection feature will
        be unavailable, but the Gramplet should otherwise function correctly.

        Automatic detection of faces requires the following to be installed:

        * OpenCV, its dependencies and Python bindings. This library should be
          available in common Linux distributions. For example, Debian package
          python-opencv provides the Python bindings for the library. It will
          require the core library packages (libopencv-*) and the
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
        self.render_text(""" 12. <b><a href="https://gramps-project.org/wiki"""
                         """/index.php?title=Addon:Photo_Tagging_Gramplet#Prerequisites">"""
                         """Addon:Photo Tagging Gramplet</a> :</b> """)
        # Start check

        try:
            import cv2
            cv2_ver = cv2.__version__
            # print(dir(cv2))
        except ImportError:
            cv2_ver = _("not found.")
        try:
            import numpy
            numpy_ver = str(numpy.__version__)
            # print("numpy.__version__ :" + numpy_ver )
        except ImportError:
            numpy_ver = _("not found.")

        self.append_text("(NumPy: " + numpy_ver + ")")
        self.append_text(_("(OpenCV facedetection: %s)") % cv2_ver)

    def check33_lxmlgramplet(self):
        ''' Lxml Gramplet - Gramplet for testing lxml and XSLT

        lxml gramplet is an experimental gramplet working under POSIX
        platform(s), which reads, writes (not the original one; safe read
        only state), transforms content of our Gramps XML file on the fly
        without an import into our database (Gramps session).

        https://www.gramps-project.org/wiki/index.php?title=Lxml_Gramplet
        https://github.com/gramps-project/addons-source/tree/master/lxml

        requires:
        * lxml is a Pythonic binding for the C libraries libxml2 and libxslt.
        It is known for good performances by using C-level (Cython).
        '''
        self.append_text("\n")
        self.render_text(""" 13. <b><a href="https://www.gramps-project.org/"""
                         """wiki/index.php?title=Addon:Lxml_Gramplet#Prerequisites">"""
                         """Addon:Lxml Gramplet</a> :</b> """)
        # Start check
        LXML_OK = False

        REQ_LXML_VERSION = "3.3.3"
        try:
            from lxml import etree  # objectify
            LXML_OK = True
            # current code is working with:
            # LIBXML_VERSION (2, 9, 1))
            # LIBXSLT_VERSION (1, 1, 28))
            LXML_VERSION = etree.LXML_VERSION
            LIBXML_VERSION = etree.LIBXML_VERSION
            LIBXSLT_VERSION = etree.LIBXSLT_VERSION
            # print("lxml found")
        except ImportError:
            LXML_OK = False
            # print('No lxml')

        # test version
        if LXML_OK:
            # print("Success")
            result = (" (lxml: " + verstr(LXML_VERSION) +
                      ")(libxml: " + verstr(LIBXML_VERSION) +
                      ")(libxslt: " + verstr(LIBXSLT_VERSION) + ")")
        else:
            # print("Failed")
            result = (_(" (lxml: not found. Requires version ") +
                      REQ_LXML_VERSION + _(" or greater installed.)"))
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
        self.render_text(""" 14. <b><a href="https://www.gramps-project.org/"""
                         """wiki/index.php?title=Addon:MongoDB#Prerequisites">"""
                         """Addon:MongoDB</a> :</b> """)

        result = _(" • Requires: MongoDB TBD / pymongo TBD")
        # End checks
        self.append_text(result)

    # Diagnostic checks #####################################################
    def platform_details(self):
        '''Which operating system if this'''
        # self.append_text("\n")
        # Start check
        if hasattr(os, "uname"):
            kernel = os.uname()[2]
        else:
            kernel = None

        self.append_text(_(' • Operating System: %s' % sys.platform))
        if kernel:
            self.append_text('\n kernel: %s' % kernel)

        # End check
        self.append_text("\n")

    def locale_settings(self):
        '''Locale Check

        # Test Locale settings are correct for system?
        eg: not using LANG=C LC_ALL=C see issue #10407

        [ ] Mention that if you don't see Gramps in your language and the
        settings are correct that if on windows you may need to reinstall
        Gramps and select the needed language and dictionary

        LC_MESSAGES
        LC_TIME
        '''
        # self.append_text("\n")
        self.render_text(_("""<u><b><a href="https://gramps-project.org/wiki"""
                           """/index.php?title=Gramps_5.0_Wiki_Manual_-_"""
                           """Command_Line#LANG.2C_LANGUAGE.2C_LC_MESSAGE."""
                           """2C_LC_TIME">Locale Settings:</a></b></u>\n"""))
        # Start check
        if ENVVAR:
            lang_str = get_env_var('LANG', _('not set'))
            language_str = get_env_var('LANGUAGE', _('not set'))
            lcmessage_str = get_env_var('LC_MESSAGES', _('not set'))
            lctime_str = get_env_var('LC_TIME', _('not set'))
        else:
            lang_str = _('not tested')
            language_str = _('not tested')
            lcmessage_str = _('not tested')
            lctime_str = _('not tested')

        result = (" • LANG:  " + lang_str + "\n • LANGUAGE:  " + language_str +
                  "\n • LC_MESSAGES:  " + lcmessage_str +
                  "\n • LC_TIME:  " + lctime_str)
        # End check
        self.append_text(result)

    def locales_installed(self):
        '''
        Test and list installed locales because of Gramps AIO!

        Used for the GUI

        Used in reports as the option called: "Translation:" The translation
        to be used for the report. Language selector showing all languages
        supported by Gramps. Defaults to the language you are using Gramps in.
        '''
        from gramps.gen.const import GRAMPS_LOCALE as glocale

        self.append_text(_("\nInstalled Locales\Translations (If only English "
                           "is listed please re-install Gramps again and make "
                           "sure to select all the Translations and "
                           "Dictionaries)\n\n"))

        result = ""
        # TODO: Add test to count languages and compare total

        languages = glocale.get_language_dict()
        for language in sorted(languages, key=glocale.sort_key):
            # print(languages[language], language)
            result = languages[language] + " : " + language + "\n"
            self.append_text(result)
            # result.append(str(language))

        # End check
        # self.append_text(result)

    def gramps_environment_variables(self):
        '''Gramps Environment variables
        https://gramps-project.org/wiki/index.php?title=Gramps_5.0_Wiki_Manual_-_Command_Line#Environment_variables
        '''
        self.append_text("\n")
        # Start check
        if ENVVAR:
            grampsi18n_str = get_env_var('GRAMPSI18N', _('not set'))
            grampshome_str = get_env_var('GRAMPSHOME', _('not set'))
            grampsdir_str = get_env_var('GRAMPSDIR', _('not set'))
            gramps_resources_str = get_env_var('GRAMPS_RESOURCES',
                                               _('not set'))
        else:
            grampsi18n_str = _('not tested')
            grampshome_str = _('not tested')
            grampsdir_str = _('not tested')
            gramps_resources_str = _('not tested')

        # End check
        self.append_text(_("\nGramps Environment variables:\n"))
        self.append_text(' • GRAMPSI18N:  %s' % grampsi18n_str)
        self.append_text('\n • GRAMPSHOME:  %s' % grampshome_str)
        self.append_text('\n • GRAMPSDIR:  %s' % grampsdir_str)
        self.append_text('\n • GRAMPS_RESOURCES:  %s' % gramps_resources_str)

    def intltool_version(self):
        '''
        Intltool collection - The internationalization tool collection

        https://freedesktop.org/wiki/Software/intltool/

        Return the version of intltool as a tuple.

        Note from setup.py : No intltool or version < 0.25.0, build_intl is
                             aborting'

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

        cmd = "intltool-update --version"
        try:
            retcode, version_str = subprocess.getstatusoutput(cmd)
            _ver = version_str.find(') ')
            ver_ = version_str.find('\n')
            if _ver > 0 and ver_ > 0:
                vers = version_str[_ver + 2:ver_]
            else:
                vers = _('found')
            if retcode != 0:
                vers = _("not found")
        except Exception:
            vers = _("not found")
        result = " • intltool-update: %s\n" % vers
        # End checks
        self.append_text(result)

    #         if sys.platform == 'win32':
    #             cmd = ["perl", "-e print qx(intltool-update --version) "
    #                    "=~ m/(\d+.\d+.\d+)/;"]
    #             try:
    #                 ver, ret = subprocess.Popen(cmd ,stdout=subprocess.PIPE,
    #                     stderr=subprocess.PIPE, shell=True).communicate()
    #                 ver = ver.decode("utf-8")
    #                 if ver > "":
    #                     version_str = ver
    #                 else:
    #                     return (0,0,0)
    #             except Exception:
    #                 return (0,0,0)
    #         else:
    #             cmd = 'intltool-update --version 2> /dev/null'
    #             # pathological case
    #             retcode, version_str = subprocess.getstatusoutput(cmd)
    #             if retcode != 0:
    #                 return None
    #             cmd = ('intltool-update --version 2> /dev/null | head -1 | '
    #                    'cut -d" " -f3')
    #             retcode, version_str = subprocess.getstatusoutput(cmd)
    #             if retcode != 0:
    #                 # unlikely but just barely imaginable, so leave it
    #                 return None
    #         return tuple([int(num) for num in version_str.split('.')])

    def gettext_version(self):
        '''GNU gettext utilities - for translation

        https://en.wikipedia.org/wiki/Gettext

        ver: 0.19.8.1

        * msgfmt  - generates a binary message catalog from a textual
                    translation description.

        https://github.com/gramps-project/gramps/blob/master/po/test/po_test.py
        https://github.com/gramps-project/gramps/blob/master/gramps/gui/grampsgui.py
        https://github.com/gramps-project/gramps/blob/master/gramps/gen/datehandler/_datestrings.py
        https://github.com/gramps-project/gramps/blob/master/gramps/gen/utils/grampslocale.py
        '''
        # self.append_text("\n")
        # Start check
        import subprocess
        try:
            cmd = 'msgfmt -V'
            retcode, version_str = subprocess.getstatusoutput(cmd)
            _ver = version_str.find(') ')
            ver_ = version_str.find('\n')
            if _ver > 0 and ver_ > 0:
                vers = version_str[_ver + 2:ver_]
            else:
                vers = _('found')
            if retcode != 0:
                vers = _("not found")
            # import gettext
            # print(dir(gettext))
            # import sgettext
            # print(dir(sgettext))
            # print("gettext found ")
        except Exception:
            vers = _("not found")

        result = " • gettext (msgfmt): %s\n" % vers
        # End checks
        self.append_text(result)

    def sphinx_check(self):
        '''
        Sphinx is a tool that build the Gramps development documentation and
        man pages

        http://sphinx-doc.org/

        # TODO ???
        https://github.com/gramps-project/gramps/blob/master/data/man/update_man.py
        https://github.com/gramps-project/gramps/blob/master/docs/update_doc.py
        '''
        # Start check
        import subprocess
        try:
            cmd = 'sphinx-quickstart --version'
            retcode, version_str = subprocess.getstatusoutput(cmd)
            _ver = version_str.find('t ')
            ver_ = len(version_str)
            if _ver > 0 and ver_ > 0:
                vers = version_str[_ver + 2:ver_]
            else:
                vers = _('found')
            if retcode != 0:
                vers = _("not found")
        except Exception:
            vers = _("not found")
        result = " • Sphinx: %s\n" % vers
        # End check
        self.append_text(_("Sphinx is a tool that builds the Gramps "
                           "development documentation and man pages\n"))
        self.append_text(result)


def latest_version_thread(self):
    """
    Load the latest version from the wiki.  Done in thread to allow other
    parts of GUI to continue running via the 'yield' for the Gramplet.
    """
    try:
        req = request.Request("https://gramps-project.org/wiki/index.php"
                              "?title=Template:Version&action=raw",
                              headers={"User-Agent": "Mozilla/5.0"})
        fp = request.urlopen(req)
        text = str(fp.read().decode('utf-8'))
        evers = text.find('<')
        if 4 < evers < 8:
            self.latest_gramps_version = vertup(text[0:evers])
        else:
            self.latest_gramps_version = (0, 0, 0)
    except Exception:
        self.latest_gramps_version = (0, 0, 0)


def verstr(nums):
    return '.'.join(str(num) for num in nums)


def vertup(ver_str):
    return tuple(map(int, ver_str.split(".")))
