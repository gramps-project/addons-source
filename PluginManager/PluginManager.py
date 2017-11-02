#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2007  Donald N. Allingham
# Copyright (C) 2008       Raphael Ackermann
# Copyright (C) 2010       Benny Malengier
# Copyright (C) 2010       Nick Hall
# Copyright (C) 2012       Doug Blank <doug.blank@gmail.com>
# Copyright (C) 2017       Paul Culley <paulr2787_at_gmail.com>
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
""" Help/Plugin Manager
This module implements the enhanced Plugin manager """
#-------------------------------------------------------------------------
#
# Standard python modules
#
#-------------------------------------------------------------------------
import sys
import os
import traceback
import logging
import datetime
from operator import itemgetter
import shutil
#-------------------------------------------------------------------------
#
# GTK/Gnome modules
#
#-------------------------------------------------------------------------
from gi.repository import GObject  # pylint: disable=import-error
from gi.repository import Gdk      # pylint: disable=import-error
from gi.repository import Gtk      # pylint: disable=import-error

#-------------------------------------------------------------------------
#
# gramps modules
#
#-------------------------------------------------------------------------
#from gramps.gen.plug.utils import available_updates
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.const import URL_MANUAL_PAGE, VERSION_DIR
from gramps.gen.utils.configmanager import safe_eval
from gramps.gen.plug import PluginRegister, BasePluginManager
from gramps.gen.plug import load_addon_file, version_str_to_tup
from gramps.gen.plug._pluginreg import VIEW, GRAMPLET, PTYPE_STR
from gramps.gen.plug.utils import urlopen_maybe_no_check_cert
from gramps.cli.grampscli import CLIManager
from gramps.gui.plug import tool
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.pluginmanager import GuiPluginManager
from gramps.gui.listmodel import ListModel, NOSORT, TOGGLE
from gramps.gui.display import display_help
from gramps.gui.utils import open_file_with_default_application
from gramps.gui.configure import ConfigureDialog
from gramps.gui.widgets import BasicLabel
from gramps.gui.dialog import OkDialog, QuestionDialog2
from gramps.gui.glade import Glade
from gramps.gui.widgets.progressdialog import (LongOpStatus, ProgressMonitor,
                                               GtkProgressDialog)
#-------------------------------------------------------------------------
#
# set up translation, logging and constants
#
#-------------------------------------------------------------------------
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
ngettext = _trans.ngettext  # else "nearby" comments are ignored

LOG = logging.getLogger(".gui.plug")

WIKI_PAGE = 'Plugin_Manager_Plugin'
TITLE = _("Plugin Manager - Enhanced")
# some static data, available across instantiations
static = sys.modules[__name__]
static.check_done = False
static.panel = 0

RELOAD_RES = 777    # A custom Gtk response_type for the Reload button
UPDATE_RES = 666    # A custom Gtk response_type for the Update button
IGNORE_RES = 888    # A custom Gtk response_type for the checkboxes

# status bit mask values
INSTALLED = 1   # INSTALLED, AVAILABLE, and BUILTIN are mutually exclusive
AVAILABLE = 2   # set = available
BUILTIN = 4     # set = builtin
HIDDEN = 8      # set = hidden
UPDATE = 16     # set = Update available

# plugins model column numbers
R_TYPE = 0
R_STAT_S = 1
R_NAME = 2
R_DESC = 3
R_ID = 4
R_STAT = 5

# the following removes a class of pylint errors that are not properly ignored;
# supposed to be fixed in pylint v1.7
# pylint: disable=unused-argument


#-------------------------------------------------------------------------
#
# Plugin Manager
#
#-------------------------------------------------------------------------
class PluginStatus(tool.Tool, ManagedWindow):
    """ Plugin manager loading controls """

    def __init__(self, dbstate, uistate, track):
        self.uistate = uistate
        self.dbstate = dbstate
        self._show_builtins = None
        self._show_hidden = None
        self.options = PluginManagerOptions('pluginmanager')
        #tool.Tool.__init__(self, dbstate, options_class, 'pluginmanager')
        self.options.load_previous_values()
        self.options_dict = self.options.handler.options_dict
        self.window = Gtk.Dialog(title=TITLE)
        ManagedWindow.__init__(self, uistate, track, self.__class__)
        self.set_window(self.window, None, TITLE, None)
        self._pmgr = GuiPluginManager.get_instance()
        self._preg = PluginRegister.get_instance()
        #obtain hidden plugins from the pluginmanager
        self.hidden = self._pmgr.get_hidden_plugin_ids()
        self.setup_configs('interface.pluginstatus', 750, 400)

        help_btn = self.window.add_button(  # pylint: disable=no-member
            _("_Help"), Gtk.ResponseType.HELP)

        update_btn = self.window.add_button(  # pylint: disable=no-member
            _("Check for updated addons now"), UPDATE_RES)
        btn_box = help_btn.get_parent()
        btn_box.set_child_non_homogeneous(update_btn, True)

        if __debug__:
            # Only show the "Reload" button when in debug mode
            # (without -O on the command line)
            reload_btn = self.window.add_button(  # pylint: disable=no-member
                _("Reload"), RELOAD_RES)
            btn_box.set_child_non_homogeneous(reload_btn, True)
        self.window.add_button(_('_Close'), Gtk.ResponseType.CLOSE)
        labeltitle, widget = self.registered_plugins_panel(None)
        self.window.vbox.pack_start(widget, True, True, 0)
        sep = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        self.window.vbox.pack_start(sep, False, False, 3)
        self.restart_needed = False
        self.window.connect('response', self.done)
        self.show()
        self.__populate_reg_list()

    def done(self, dialog, response_id):
        if response_id == RELOAD_RES:
            self.__reload(dialog)
            return
        elif response_id == UPDATE_RES:
            self._check_for_updates()
            return
        elif response_id == Gtk.ResponseType.HELP:
            self._web_help()
            return
        elif response_id == IGNORE_RES:
            return
        else:   # response_id == CLOSE or response_id == DELETE_EVENT
            if self.restart_needed:
                OkDialog(_("Restart..."),
                         _("Please Restart Gramps so that your addon changes "
                           "can be safely completed."),
                         parent=self.window)
            self.options.handler.save_options()
            self.close(dialog)

    def __reload(self, _obj):
        """ Callback function from the "Reload" button """
        self._pmgr.reload_plugins()
        self.__rebuild_reg_list('0')

    def __show_hidden_chk(self, obj):
        """ Callback from Hide hidden checkbox """
        self._show_hidden = obj.get_active()
        self.options_dict['show_hidden'] = self._show_hidden
        # config.set('behavior.do-not-show-hidden-addons',
        #            bool(self._show_hidden))
        self.__rebuild_reg_list('0', rescan=False)

    def __show_builtins_chk(self, obj):
        """ Callback from Hide builtins checkbox """
        self._show_builtins = obj.get_active()
        self.options_dict['show_builtins'] = self._show_builtins
        # config.set('behavior.do-not-show-builtins',
        #            bool(self._show_builtins))
        self.__rebuild_reg_list('0', rescan=False)

    def __info(self, _obj, list_obj):
        """ Callback function from the "Info" button
        """
        model, node = list_obj.get_selection().get_selected()
        if not node:
            return
        pid = model.get_value(node, R_ID)
        pdata = self._preg.get_plugin(pid)
        if pdata:
            name = pdata.name
            typestr = PTYPE_STR[pdata.ptype]
            desc = pdata.description
            vers = pdata.version
            auth = ' - '.join(pdata.authors)
            email = ' - '.join(pdata.authors_email)
            fname = pdata.fname
            fpath = pdata.fpath
        else:
            for addon in self.addons:
                if addon['i'] == pid:
                    name = addon['n']
                    typestr = addon['t']
                    desc = addon['d']
                    vers = addon['v']
                    auth = ''
                    email = ''
                    fname = addon['z']
                    fpath = ''
                    break

        if len(auth) > 60:
            auth = auth[:60] + '...'
        if len(email) > 60:
            email = email[:60] + '...'
        infotxt = (
            "%(plugnam)s: %(name)s [%(typestr)s]\n\n"
            "%(plug_id)s: %(id)s\n"
            "%(plugdes)s: %(descr)s\n%(plugver)s: %(version)s\n"
            "%(plugaut)s: %(authors)s\n%(plugmel)s: %(email)s\n"
            "%(plugfil)s: %(fname)s\n%(plugpat)s: %(fpath)s\n\n" % {
                'id': pid,
                'name': name,
                'typestr': typestr,
                'descr': desc,
                'version': vers,
                'authors': auth,
                'email': email,
                'fname': fname,
                'fpath': fpath,
                'plug_id': _("Id"),
                'plugnam': _("Plugin name"),
                'plugdes': _("Description"),
                'plugver': _("Version"),
                'plugaut': _("Authors"),
                'plugmel': _("Email"),
                'plugfil': _("Filename"),
                'plugpat': _("Location")})
        success_list = self._pmgr.get_success_list()
        if pdata:
            for i in success_list:
                if pdata.id == i[2].id:
                    infotxt += _('Loaded') + ' '
                    break
        if pid in self.hidden:
            infotxt += _('Hidden')
        fail_list = self._pmgr.get_fail_list()
        for i in fail_list:
            # i = (filename, (exception-type, exception, traceback), pdata)
            if pdata == i[2]:
                infotxt += '\n\n' + _('Failed') + '\n\n' + str(i[1][0]) + \
                    '\n' + str(i[1][1]) + '\n' + ''.join(
                        traceback.format_exception(i[1][0], i[1][1], i[1][2]))
                break
        PluginInfo(self.uistate, self.track, infotxt, name)

    def __hide(self, _obj, list_obj):
        """ Callback function from the "Hide" button
        """
        selection = list_obj.get_selection()
        model, node = selection.get_selected()
        if not node:
            return
        pid = model.get_value(node, R_ID)
        status = model.get_value(node, R_STAT)
        status_str = model.get_value(node, R_STAT_S)
        if pid in self.hidden:
            #unhide
            self.hidden.remove(pid)
            self._pmgr.unhide_plugin(pid)
            status = model.get_value(node, R_STAT)
            status_str = status_str.replace("<s>", '').replace("</s>", '')
            status &= ~ HIDDEN
            model.set_value(node, R_STAT, status)
            self._hide_btn.set_label(_("Hide"))
        else:
            #hide
            self.hidden.add(pid)
            self._pmgr.hide_plugin(pid)
            if not self._show_hidden:
                model.remove(node)
                return
            status |= HIDDEN
            status_str = "<s>%s</s>" % status_str
            self._hide_btn.set_label(_("Unhide"))
        model.set_value(node, R_STAT, status)
        model.set_value(node, R_STAT_S, status_str)

    def __load(self, _obj, list_obj):
        """ Callback function from the "Load" button
        """
        selection = list_obj.get_selection()
        model, node = selection.get_selected()
        if not node:
            return
        idv = model.get_value(node, R_ID)
        pdata = self._preg.get_plugin(idv)
        if self._pmgr.load_plugin(pdata):
            self._load_btn.set_sensitive(False)
        else:
            path = model.get_path(node)
            self.__rebuild_reg_list(path, rescan=False)

    def __edit(self, _obj, list_obj):
        """ Callback function from the "Edit" button
        """
        selection = list_obj.get_selection()
        model, node = selection.get_selected()
        if not node:
            return
        pid = model.get_value(node, R_ID)
        pdata = self._preg.get_plugin(pid)
        if pdata.fpath and pdata.fname:
            open_file_with_default_application(
                os.path.join(pdata.fpath, pdata.fname),
                self.uistate)

    def __install(self, _obj, _list_obj):
        """ Callback function from the "Install" button
        """
        model, node = self._selection_reg.get_selected()
        if not node:
            return
        path = model.get_path(node)
        pid = model.get_value(node, R_ID)
        status = model.get_value(node, R_STAT)
        if (status & INSTALLED) and not (status & UPDATE):
            self.__uninstall(pid, path)
            return
        for addon in self.addons:
            if addon['i'] == pid:
                name = addon['n']
                fname = addon['z']
        url = "%s/download/%s" % (config.get("behavior.addons-url"), fname)
        load_ok = load_addon_file(url, callback=LOG.debug)
        if not load_ok:
            OkDialog(_("Installation Errors"),
                     _("The following addons had errors: ") +
                     name,
                     parent=self.window)
            return
        self.__rebuild_reg_list(path)
        pdata = self._pmgr.get_plugin(pid)
        if (status & UPDATE) and (pdata.ptype == VIEW or
                                  pdata.ptype == GRAMPLET):
            self.restart_needed = True

    def __uninstall(self, pid, path):
        """ Uninstall the plugin """
        pdata = self._pmgr.get_plugin(pid)
        try:
            if os.path.islink(pdata.fpath):  # linux link
                os.unlink(pdata.fpath)
            elif os.stat(pdata.fpath).st_ino != os.lstat(pdata.fpath).st_ino:
                # it's probably a Windows junction or softlink
                os.rmdir(pdata.fpath)
            else:  # it's a real directory
                shutil.rmtree(pdata.fpath)
        except:  # pylint: disable=bare-except
            OkDialog(_("Error"),
                     _("Error removing the '%s' directory, The uninstall may "
                       "have failed") % pdata.fpath,
                     parent=self.window)
        self.__rebuild_reg_list(path)
        self.restart_needed = True

    def registered_plugins_panel(self, _configdialog):
        """ This implements the gui portion of the Plugins panel """
        vbox_reg = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrolled_window_reg = Gtk.ScrolledWindow()
        self._list_reg = Gtk.TreeView()
        self._list_reg.set_grid_lines(Gtk.TreeViewGridLines.HORIZONTAL)
        #  model: plugintype, hidden, pluginname, plugindescr, pluginid
        self._model_reg = Gtk.ListStore(
            GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_STRING,
            GObject.TYPE_STRING, GObject.TYPE_STRING, int)
        self._selection_reg = self._list_reg.get_selection()
        self._list_reg.set_model(self._model_reg)
        self._list_reg.connect('button-press-event', self.button_press_reg)
        self._cursor_hndlr = self._selection_reg.connect('changed',
                                                         self._cursor_changed)
        col0_reg = Gtk.TreeViewColumn(
            title=_('Type'), cell_renderer=Gtk.CellRendererText(),
            text=R_TYPE)
        col0_reg.set_sort_column_id(R_TYPE)
        col0_reg.set_resizable(True)
        self._list_reg.append_column(col0_reg)

        col1 = Gtk.TreeViewColumn(
            cell_renderer=Gtk.CellRendererText(wrap_mode=2, wrap_width=65),
            markup=R_STAT_S)
        label = Gtk.Label(_('Status'))
        label.show()
        label.set_tooltip_markup(
            _("'*' items are supplied by 3rd party authors,\n"
              "<s>strikeout</s> items are hidden"))
        col1.set_widget(label)
        col1.set_resizable(True)
        col1.set_sort_column_id(R_STAT_S)
        self._list_reg.append_column(col1)

        col2_reg = Gtk.TreeViewColumn(
            title=_('Name'),
            cell_renderer=Gtk.CellRendererText(wrap_mode=2, wrap_width=150),
            markup=R_NAME)
        col2_reg.set_sort_column_id(R_NAME)
        col2_reg.set_resizable(True)
        self._list_reg.append_column(col2_reg)

        col = Gtk.TreeViewColumn(
            title=_('Description'),
            cell_renderer=Gtk.CellRendererText(wrap_mode=2, wrap_width=400),
            markup=R_DESC)
        col.set_sort_column_id(R_DESC)
        col.set_resizable(True)
        self._list_reg.append_column(col)
        self._list_reg.set_search_column(2)

        scrolled_window_reg.add(self._list_reg)
        vbox_reg.pack_start(scrolled_window_reg, True, True, 0)
        # panel button box
        hbutbox = Gtk.ButtonBox()
        hbutbox.set_layout(Gtk.ButtonBoxStyle.SPREAD)

        __info_btn = Gtk.Button(label=_("Info"))
        hbutbox.add(__info_btn)
        __info_btn.connect('clicked', self.__info, self._list_reg)
        self._hide_btn = Gtk.Button(label=_("Hide"))
        hbutbox.add(self._hide_btn)
        self._hide_btn.connect('clicked', self.__hide, self._list_reg)
        self._install_btn = Gtk.Button(label=_("Install"))
        hbutbox.add(self._install_btn)
        self._install_btn.connect('clicked', self.__install, self._list_reg)
        self._edit_btn = Gtk.Button(label=_("Edit"))
        self._edit_btn.connect('clicked', self.__edit, self._list_reg)
        self._load_btn = Gtk.Button(label=_("Load"))
        self._load_btn.connect('clicked', self.__load, self._list_reg)
        if __debug__:
            hbutbox.add(self._edit_btn)
            hbutbox.add(self._load_btn)
        vbox_reg.pack_start(hbutbox, False, False, 2)
        # checkbox row
        hbutbox = Gtk.ButtonBox()
        hbutbox.set_layout(Gtk.ButtonBoxStyle.SPREAD)

        _show_hidden_chk = Gtk.CheckButton.new_with_label(
            _("Show hidden items"))
        hbutbox.add(_show_hidden_chk)
        self._show_hidden = self.options_dict['show_hidden']
        #self._show_hidden = config.get('behavior.do-not-show-hidden-addons')
        _show_hidden_chk.set_active(self._show_hidden)
        _show_hidden_chk.connect('clicked', self.__show_hidden_chk)

        _show_builtin_chk = Gtk.CheckButton.new_with_label(
            _("Show Built-in items"))
        hbutbox.add(_show_builtin_chk)
        self._show_builtins = self.options_dict['show_builtins']
        # self._show_builtins = config.get('behavior.do-not-show-builtins')
        _show_builtin_chk.set_active(self._show_builtins)
        _show_builtin_chk.connect('clicked', self.__show_builtins_chk)

        label = Gtk.Label(_("* indicates 3rd party addon"))
        hbutbox.add(label)

        vbox_reg.pack_start(hbutbox, False, False, 0)

        return _('Plugins'), vbox_reg

    def button_press_reg(self, obj, event):
        """ Callback function from the user clicking on a line in reg plugin
        """
        # pylint: disable=protected-access
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            self.__info(obj, self._list_reg)

    def __rebuild_reg_list(self, path=None, rescan=True):
        self._selection_reg.handler_block(self._cursor_hndlr)
        self._model_reg.clear()
        if rescan:
            CLIManager.do_reg_plugins(self, self.dbstate, self.uistate,
                                      rescan=True)
        self.__populate_reg_list()
        self._selection_reg.handler_unblock(self._cursor_hndlr)
        if not path or int(str(path)) >= len(self._model_reg):
            path = '0'
        self._selection_reg.select_path(path)
        if len(self._model_reg):
            self._list_reg.scroll_to_cell(path, None, True, 0.5, 0)

    def _cursor_changed(self, obj):
        model, node = obj.get_selected()
        if not node:
            return
        status = model.get_value(node, R_STAT)
        pid = model.get_value(node, R_ID)
        if (status & (INSTALLED | BUILTIN)) and (
                VIEW == self._pmgr.get_plugin(pid).ptype):
            self._hide_btn.set_sensitive(False)
        else:
            self._hide_btn.set_sensitive(True)
        if status & HIDDEN:
            self._hide_btn.set_label(_("Unhide"))
        else:
            self._hide_btn.set_label(_("Hide"))
        show_load = False
        if status & (INSTALLED | BUILTIN):
            show_load = True
            self._edit_btn.set_sensitive(True)
            success_list = self._pmgr.get_success_list()
            for i in success_list:
                if pid == i[2].id:
                    show_load = False
                    break
        else:
            self._edit_btn.set_sensitive(False)
        self._load_btn.set_sensitive(show_load)
        if status & (AVAILABLE | UPDATE):
            self._install_btn.set_label(_("Install"))
            self._install_btn.set_sensitive(True)
        elif status & INSTALLED:
            self._install_btn.set_label(_("Uninstall"))
            self._install_btn.set_sensitive(True)
        else:
            self._install_btn.set_sensitive(False)

    def _check_for_updates(self):
        """ handle the check for updates button """
        try:
            available_updates()
        except:  # pylint: disable=bare-except
            OkDialog(_("Checking Addons Failed"),
                     _("The addon repository appears to be unavailable. "
                       "Please try again later."),
                     parent=self.window)
        self.__rebuild_reg_list()

    def _web_help(self):
        display_help(WIKI_PAGE)

    def __populate_reg_list(self):
        """ Build list of plugins"""
        self.addons = []
        new_addons_file = os.path.join(VERSION_DIR, "new_addons.txt")
        if not os.path.isfile(new_addons_file) and not static.check_done:
            if QuestionDialog2(TITLE,
                               _("3rd party addons are not shown until the "
                                 "addons update list is downloaded.  Would "
                                 "you like to check for updated addons now?"),
                               _("Yes"), _("No"),
                               parent=self.window).run():
                self._check_for_updates()
            else:
                static.check_done = True
        try:
            with open(new_addons_file,
                      encoding='utf-8') as filep:
                for line in filep:
                    try:
                        plugin_dict = safe_eval(line)
                        if not isinstance(plugin_dict, dict):
                            raise TypeError("Line with addon metadata is not "
                                            "a dictionary")
                    except:  # pylint: disable=bare-except
                        LOG.warning("Skipped a line in the addon listing: " +
                                    str(line))
                        continue
                    self.addons.append(plugin_dict)
        except FileNotFoundError:
            pass
        except Exception as err:  # pylint: disable=broad-except
            LOG.warning("Failed to open addon status file: %s", err)

        addons = []
        updateable = []
        for plugin_dict in self.addons:
            pid = plugin_dict["i"]
            plugin = self._pmgr.get_plugin(pid)
            if plugin:  # check for an already registered plugin
                LOG.debug("Comparing %s > %s",
                          version_str_to_tup(plugin_dict["v"], 3),
                          version_str_to_tup(plugin.version, 3))
                # Check for a update
                if (version_str_to_tup(plugin_dict["v"], 3) >
                        version_str_to_tup(plugin.version, 3)):
                    LOG.debug("Update for '%s'...", plugin_dict["z"])
                    updateable.append(pid)
                else:  # current plugin is up to date.
                    LOG.debug("   '%s' is up to date", plugin_dict["n"])
            else:  # new addon
                LOG.debug("   '%s' is not installed", plugin_dict["n"])
                hidden = pid in self.hidden
                status_str = _("*Available")
                status = AVAILABLE
                if hidden:
                    status_str = "<s>%s</s>" % status_str
                    status |= HIDDEN
                row = [_(plugin_dict["t"]), status_str, plugin_dict["n"],
                       plugin_dict["d"], plugin_dict["i"], status]
                addons.append(row)

        fail_list = self._pmgr.get_fail_list()
        for (_type, typestr) in PTYPE_STR.items():
            for pdata in self._preg.type_plugins(_type):
                #  model: plugintype, hidden, pluginname, plugindescr, pluginid
                if 'gramps/plugins' in pdata.fpath.replace('\\', '/'):
                    status_str = _("Built-in")
                    status = BUILTIN
                    if not self._show_builtins:
                        continue
                else:
                    status_str = _("*Installed")
                    status = INSTALLED
                # i = (filename, (exception-type, exception, traceback), pdata)
                for i in fail_list:
                    if pdata == i[2]:
                        status_str += ', ' + '<span color="red">%s</span>' % \
                            _("Failed")
                        break
                if pdata.id in updateable:
                    status_str += ', ' + _("Update Available")
                    status |= UPDATE
                hidden = pdata.id in self.hidden
                if hidden:
                    status_str = "<s>%s</s>" % status_str
                    status |= HIDDEN
                addons.append([typestr, status_str, pdata.name,
                               pdata.description, pdata.id, status])
        for row in sorted(addons, key=itemgetter(R_TYPE, R_NAME)):
            if self._show_hidden or (row[R_ID] not in self.hidden):
                self._model_reg.append(row)
        self._selection_reg.select_path('0')

    def build_menu_names(self, obj):
        return (TITLE, ' ')


#-------------------------------------------------------------------------
#
# Details for an individual plugin
#
#-------------------------------------------------------------------------
class PluginInfo(ManagedWindow):
    """Displays a dialog showing the status of plugins"""

    def __init__(self, uistate, track, data, name):
        self.name = name
        title = _("%(str1)s: %(str2)s") % {'str1': _("Detailed Info"),
                                           'str2': name}
        ManagedWindow.__init__(self, uistate, track, self)

        dlg = Gtk.Dialog(title="", transient_for=uistate.window,
                         destroy_with_parent=True)
        dlg.add_button(_('_Close'), Gtk.ResponseType.CLOSE)
        self.set_window(dlg, None, title)
        self.setup_configs('interface.plugininfo', 720, 520)
        self.window.connect('response',  # pylint: disable=no-member
                            self.close)

        scrolled_window = Gtk.ScrolledWindow(expand=True)
#         scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
#                                    Gtk.PolicyType.AUTOMATIC)
        self.text = Gtk.TextView()
        scrolled_window.add(self.text)
        self.text.get_buffer().set_text(data)

        # pylint: disable=no-member
        self.window.get_content_area().add(scrolled_window)
        self.show()

    def build_menu_names(self, obj):
        return (self.name, None)


#-------------------------------------------------------------------------
#
# Local Functions
#
#-------------------------------------------------------------------------

def available_updates():
    whattypes = config.get('behavior.check-for-addon-update-types')
    do_not_show_prev = config.get(
        'behavior.do-not-show-previously-seen-addon-updates')
    prev_seen = config.get('behavior.previously-seen-addon-updates')

    LOG.debug("Checking for updated addons...")
    langs = glocale.get_language_list()
    langs.append("en")
    # now we have a list of languages to try:
    fp = None
    for lang in langs:
        URL = ("%s/listings/addons-%s.txt" %
               (config.get("behavior.addons-url"), lang))
        LOG.debug("   trying: %s", URL)
        try:
            fp = urlopen_maybe_no_check_cert(URL)
        except:
            try:
                URL = ("%s/listings/addons-%s.txt" %
                       (config.get("behavior.addons-url"), lang[:2]))
                fp = urlopen_maybe_no_check_cert(URL)
            except Exception as err:  # some error
                LOG.warning("Failed to open addon metadata for %s %s: %s",
                            lang, URL, err)
                fp = None
        if fp and fp.getcode() == 200:  # ok
            break

    try:
        wfp = open(os.path.join(VERSION_DIR, "new_addons.txt"), mode='wt',
                   encoding='utf-8')
    except Exception as err:
        LOG.warning("Failed to open addon status file: %s", err)

    pmgr = BasePluginManager.get_instance()
    addon_update_list = []
    if fp and fp.getcode() == 200:
        lines = list(fp.readlines())
        count = 0
        for line in lines:
            line = line.decode('utf-8')
            try:
                plugin_dict = safe_eval(line)
                if type(plugin_dict) != type({}):
                    raise TypeError("Line with addon metadata is not "
                                    "a dictionary")
            except:
                LOG.warning("Skipped a line in the addon listing: " +
                            str(line))
                continue
            if wfp:
                wfp.write(str(plugin_dict) + '\n')
            pid = plugin_dict["i"]
            plugin = pmgr.get_plugin(pid)
            if plugin:
                LOG.debug("Comparing %s > %s",
                          version_str_to_tup(plugin_dict["v"], 3),
                          version_str_to_tup(plugin.version, 3))
                if (version_str_to_tup(plugin_dict["v"], 3) >
                        version_str_to_tup(plugin.version, 3)):
                    LOG.debug("   Downloading '%s'...", plugin_dict["z"])
                    if "update" in whattypes:
                        if (not do_not_show_prev or
                                plugin_dict["i"] not in prev_seen):
                            addon_update_list.append(
                                (_("Updated"), "%s/download/%s" %
                                 (config.get("behavior.addons-url"),
                                  plugin_dict["z"]), plugin_dict))
                else:
                    LOG.debug("   '%s' is ok", plugin_dict["n"])
            else:
                LOG.debug("   '%s' is not installed", plugin_dict["n"])
                if "new" in whattypes:
                    if (not do_not_show_prev or
                            plugin_dict["i"] not in prev_seen):
                        addon_update_list.append(
                            (_("updates|New"), "%s/download/%s" %
                             (config.get("behavior.addons-url"),
                              plugin_dict["z"]), plugin_dict))
        config.set("behavior.last-check-for-addon-updates",
                   datetime.date.today().strftime("%Y/%m/%d"))
        count += 1
        if fp:
            fp.close()
        if wfp:
            wfp.close()
    else:
        LOG.debug("Checking Addons Failed")
    LOG.debug("Done checking!")

    return addon_update_list


def load_on_reg(dbstate, uistate, plugin):
    """
    Runs when plugin is registered.
    """
    if uistate:
        # Monkey patch my version of available_updates into the system
        import gramps.gen.plug.utils
        gramps.gen.plug.utils.__dict__['available_updates'] = available_updates
        import gramps.gui.configure
        gramps.gui.configure.__dict__['available_updates'] = available_updates
        import gramps.gui.utils
        gramps.gui.utils.__dict__['available_updates'] = available_updates
        import gramps.gui.viewmanager
        gramps.gui.viewmanager.__dict__[
            'PluginWindows'].PluginStatus = PluginStatus
#------------------------------------------------------------------------
#
#
#
#------------------------------------------------------------------------


class PluginManagerOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

        # Options specific for this report
        self.options_dict = {
            'show_hidden'   : True,
            'show_builtins' : True,
        }
        self.options_help = {
            'show_hidden': ("=0/1", "Show hidden Plugins",
                            ["Do not show hidden Plugins",
                             "Show hidden Plugins"],
                            True),
            'show_builtins': ("=0/1", "Show builtin Plugins",
                              ["Do not show builtin Plugins",
                               "Show builtin Plugins"],
                              True),
            }
