#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2007  Donald N. Allingham
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

"""Tools/Database Repair/Check and Repair Database for Missing Surnames"""

# -------------------------------------------------------------------------
#
# python modules
#
# -------------------------------------------------------------------------
from io import StringIO

# ------------------------------------------------------------------------
#
# Set up logging
#
# ------------------------------------------------------------------------
import logging

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
ngettext = glocale.translation.ngettext  # else "nearby" comments are ignored
from gramps.gen.lib import Surname
from gramps.gen.db import DbTxn
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.plug import tool
from gramps.gui.dialog import OkDialog
from gramps.gui.glade import Glade

class ProgressMeter:
    """ dummy ProgressMeter class """
    def __init__(self, *args, **kwargs):
        """ keep pylint happy """
        pass

    def set_pass(self, *args):
        """ keep pylint happy """
        pass

    def step(self):
        """ keep pylint happy """
        pass

    def close(self):
        """ keep pylint happy """
        pass

# -------------------------------------------------------------------------
#
# NoSurnameCheck
#
# -------------------------------------------------------------------------
class NoSurnameCheck(tool.BatchTool):
    """ NoSurnameCheck class """
    def __init__(self, dbstate, user, options_class, name, callback=None):
        """ constructor for NoSurnameCheck class """
        uistate = user.uistate

        tool.BatchTool.__init__(self, dbstate, user, options_class, name)
        if self.fail:
            return

        cli = uistate is None
        if uistate:
            from gramps.gui.utils import ProgressMeter as PM
            global ProgressMeter
            ProgressMeter = PM

        if self.db.readonly:
            return

        with DbTxn(_("Check Surname Integrity"), self.db, batch=True) as trans:
            self.db.disable_signals()
            checker = NoSurnameCheckIntegrity(dbstate, uistate, trans)
            checker.check_person_no_surname()

        self.db.enable_signals()
        self.db.request_rebuild()

        errs = checker.build_report(uistate)
        if errs:
            NoSurnameCheckReport(uistate, checker.text.getvalue(), cli)

# -------------------------------------------------------------------------
#
# NoSurnameCheckIntegrity:
#
# -------------------------------------------------------------------------
class NoSurnameCheckIntegrity:
    """ NoSurnameCheckIntegrity Class """
    def __init__(self, dbstate, uistate, trans):
        """ constructor for NoSurnameCheckIntegrity class """
        self.uistate = uistate
        if self.uistate:
            self.parent_window = self.uistate.window
        else:
            self.parent_window = None
        self.db = dbstate.db
        self.trans = trans
        self.invalid_surnames = 0
        self.text = StringIO()
        self.progress = ProgressMeter(_('Checking Database'), '',
                                      parent=self.parent_window)

    def check_person_no_surname(self):
        """ check for people with no Surname field """
        self.progress.set_pass(_('Looking for people with no surname field'),
                               self.db.get_number_of_people())
        logging.info('Looking for people with no surname field')

        for handle in self.db.get_person_handles():
            person = self.db.get_person_from_handle(handle)
            name = person.get_primary_name()
            if name.get_surname_list() == []: # bug 10078
                name.set_surname_list([Surname()]) # make a null surname
                person.set_primary_name(name)
                self.db.commit_person(person, self.trans)
                self.invalid_surnames += 1
            self.progress.step()

        if self.invalid_surnames == 0:
            logging.info('    OK: no people with missing surname field')

    def build_report(self, uistate=None):
        ''' build the report from various counters'''
        self.progress.close()
        invalid_surnames = self.invalid_surnames

        errors = (invalid_surnames)

        if errors == 0:
            if uistate:
                OkDialog(_("No errors were found"),
                         _('The database has passed internal checks'),
                         parent=uistate.window)
            else:
                print(_("No errors were found: the database has passed "
                        "internal checks."))
            return 0

        if invalid_surnames > 0:
            self.text.write(
                # translators: leave all/any {...} untranslated
                ngettext("{quantity} missing Surname field fixed\n",
                         "{quantity} missing Surname fields fixed\n",
                         invalid_surnames).format(quantity=invalid_surnames)
                )

        return errors

# -------------------------------------------------------------------------
#
# Display the results
#
# -------------------------------------------------------------------------
class NoSurnameCheckReport(ManagedWindow):
    """ Report out the results """
    def __init__(self, uistate, text, cli=0):
        """ constructor for NoSurnameCheckReport class """
        if cli:
            print(text)

        if uistate:
            ManagedWindow.__init__(self, uistate, [], self)

            topdialog = Glade('check.glade') # use the main tool's Glade file
            topdialog.get_object("close").connect('clicked', self.close)
            window = topdialog.toplevel
            textwindow = topdialog.get_object("textwindow")
            textwindow.get_buffer().set_text(text)

            self.set_window(window,
                            topdialog.get_object("title"),
                            _("No Surname Integrity Check Results"))
            self.setup_configs('interface.nosurnamecheckreport', 450, 400)

            self.show()

    def build_menu_names(self, obj):
        """ override the parent method """
        return (_('No Surname Check and Repair'), None)

# ------------------------------------------------------------------------
#
# NoSurnameCheckOptions
#
# ------------------------------------------------------------------------
class NoSurnameCheckOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        """ constructor for NoSurnameCheckOptions """
        tool.ToolOptions.__init__(self, name, person_id)
