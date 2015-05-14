#
# Copyright (C) 2011 Matt Keenan <matt.keenan@gmail.com>
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

#-------------------------------------------------------------------------
#
# GTK+ modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
import gramps.gen.errors as Errors
import logging
LOG = logging.getLogger(".")

from gramps.gen.plug import BasePluginManager
from gramps.gen.plug.report import CATEGORY_TEXT
from gramps.gui.utils import open_file_with_default_application
from gramps.gui.user import User
from gramps.gui.plug.report._textreportdialog import TextReportDialog


#------------------------------------------------------------------------
#
# RunReport
#
#------------------------------------------------------------------------
#def RunReport(dbstate, uistate, report_class, options_class, trans_name, name)
def RunReport(dbstate, uistate, mod_str, name, trans_name, report_str, options_str):

    dialog_class = TextReportDialog

    mod = __import__(mod_str)
    report_class = getattr(mod, report_str)
    options_class = getattr(mod, options_str)

    dialog = dialog_class(dbstate, uistate, options_class, name, trans_name)

    while True:
        response = dialog.window.run()
        if response == Gtk.ResponseType.OK:
            dialog.close()
            try:
                user = User()
                MyReport = report_class(dialog.db, dialog.options, user)
                
                def do_report():
                    MyReport.doc.init()
                    MyReport.begin_report()
                    MyReport.write_report()
                    MyReport.end_report()

                do_report()

                if dialog.open_with_app.get_active():
                    out_file = dialog.options.get_output()
                    open_file_with_default_application(out_file)
            
            except Errors.FilterError as msg:
                (m1, m2) = msg.messages()
                ErrorDialog(m1, m2)
            except IOError as msg:
                ErrorDialog(_("Report could not be created"), str(msg))
            except Errors.ReportError as msg:
                (m1, m2) = msg.messages()
                ErrorDialog(m1, m2)
            except Errors.DatabaseError as msg:                
                ErrorDialog(_("Report could not be created"), str(msg))
                raise
            except:
                LOG.error("Failed to run report.", exc_info=True)
            break
        elif response == Gtk.ResponstType.CANCEL:
            dialog.close()
            break
        elif response == Gtk.ResponseType.DELETE_EVENT:
            #just stop, in ManagedWindow, delete-event is already coupled to
            #correct action.
            break

    #do needed cleanup
    dialog.db = None
    dialog.options = None
    if hasattr(dialog, 'window'):
        delattr(dialog, 'window')
    if hasattr(dialog, 'notebook'):
        delattr(dialog, 'notebook')
    del dialog


def GetReportClasses(name):
    """Get Report and Options class for this module"""
    report_class = None
    options_class = None

    pmgr = BasePluginManager.get_instance()
    _cl_list = pmgr.get_reg_reports(gui=False)
    for pdata in _cl_list:
        if name == pdata.id:
            mod = pmgr.load_plugin(pdata)
            if not mod:
                return report_class, options_class
            report_class_str = pdata.reportclass + "Report"
            report_class = eval('mod.' + report_class_str)
            options_class_str = name + "Options"
            options_class = eval('mod.' + options_class_str)

            return report_class, options_class

    return report_class, options_class
