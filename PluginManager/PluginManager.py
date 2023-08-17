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
from gi.repository.GLib import markup_escape_text
#-------------------------------------------------------------------------
#
# gramps modules
#
#-------------------------------------------------------------------------
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.const import URL_MANUAL_PAGE
from gramps.gen.utils.requirements import Requirements
from gramps.gen.plug import (
    PluginRegister, load_addon_file, version_str_to_tup,
    AUDIENCETEXT, STATUSTEXT)
from gramps.gen.plug._pluginreg import VIEW, GRAMPLET, PTYPE_STR
from gramps.gen.plug.utils import get_all_addons
from gramps.cli.grampscli import CLIManager
from gramps.gui.plug import tool
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.pluginmanager import GuiPluginManager
from gramps.gui.display import display_help, display_url
from gramps.gui.utils import open_file_with_default_application
from gramps.gui.dialog import OkDialog

#-------------------------------------------------------------------------
#
# set up translation, logging and constants
#
#-------------------------------------------------------------------------
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.sgettext
ngettext = _trans.ngettext  # else "nearby" comments are ignored

LOG = logging.getLogger(".gui.plug")

WIKI_PAGE = 'Addon:Plugin_ManagerV2'
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
# Enhanced Plugin Manager
#
#-------------------------------------------------------------------------
class PluginStatus(tool.Tool, ManagedWindow):
    """ Plugin manager loading controls """

    def __init__(self, dbstate, uistate, track):
        self.uistate = uistate
        self.dbstate = dbstate
        self._show_builtins = None
        self._show_hidden = None
        self.addons = []
        self.infodata = ''  # information pane text
        self.name = ''
        self.help = ''
        self.helpname = ''

        self.options = PluginManagerOptions('pluginmanager')
        #tool.Tool.__init__(self, dbstate, options_class, 'pluginmanager')
        self.options.load_previous_values()
        self.options_dict = self.options.handler.options_dict
        self.window = Gtk.Dialog(title=TITLE)
        ManagedWindow.__init__(self, uistate, track, self.__class__)
        self.set_window(self.window, None, TITLE, None)
        self._pmgr = GuiPluginManager.get_instance()
        self._preg = PluginRegister.get_instance()
        # obtain hidden plugins from the pluginmanager
        self.hidden = self._pmgr.get_hidden_plugin_ids()
        self.setup_configs('interface.pluginstatus', 750, 600)

        help_btn = self.window.add_button(  # pylint: disable=no-member
            _("_Help"), Gtk.ResponseType.HELP)
        self.btn_box = help_btn.get_parent()
        self.btn_box.set_child_non_homogeneous(help_btn, True)

        # filter input box
        self.filter_entry = Gtk.SearchEntry()
        self.filter_entry.set_tooltip_text(
            _("Enter search words to filter the addons.\n"
              "All the words must be present somewhere in the row or\n"
              "the addon filename to be included in the search.\n"
              "Word case and order is ignored."))
        self.filter_entry.set_placeholder_text(_("Search..."))
        self.btn_box.pack_start(self.filter_entry, True, True, 0)
        #self.btn_box.set_child_non_homogeneous(self.filter_entry, True)
        self.filter_entry.connect('search-changed', self.filter_str_changed)

        if __debug__:
            # Only show the "Reload" button when in debug mode
            # (without -O on the command line)
            reload_btn = self.window.add_button(  # pylint: disable=no-member
                _("Reload"), RELOAD_RES)
            self.btn_box.set_child_non_homogeneous(reload_btn, True)
            _w0, _wx_ = reload_btn.get_preferred_width()
        else:
            _w0 = 0

        cls_btn = self.window.add_button(_('_Close'), Gtk.ResponseType.CLOSE)
        self.btn_box.set_child_non_homogeneous(cls_btn, True)
        # make room for a larger filter entry
        _w1, dummy = help_btn.get_preferred_width()
        _w2, dummy = cls_btn.get_preferred_width()
        _we = 790 - _w0 - _w1 - _w2 - 60
        self.filter_entry.set_size_request(_we, -1)
        # set up double pane window
        self.vpane = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.vpane.set_position(self.options_dict['pane_setting'])
        self.window.vbox.pack_start(self.vpane, True, True, 0)
        # upper pane
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        _labeltitle, widget = self.registered_plugins_panel(None)
        vbox.pack_start(widget, True, True, 0)
        sep = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        vbox.pack_start(sep, False, False, 3)
        self.vpane.pack1(vbox, resize=True, shrink=False)
        # lower pane
        scrolled_window = Gtk.ScrolledWindow(expand=True)
        info_text_view = Gtk.TextView()
        scrolled_window.add(info_text_view)
        self.info_text_buf = info_text_view.get_buffer()
        self.info_text_buf.set_text(self.infodata)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(scrolled_window, True, True, 0)
        self.vpane.pack2(vbox, resize=True, shrink=False)
        self.restart_needed = False
        self.window.connect('response', self.done)
        self.show()
        self.__populate_reg_list()

    def done(self, dialog, response_id):
        if response_id == RELOAD_RES:
            self.__reload(dialog)
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
            self.options_dict['pane_setting'] = self.vpane.get_position()
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

    def __hide(self, _obj, list_obj):
        """ Callback function from the "Hide" button
        """
        selection = list_obj.get_selection()
        model, node = selection.get_selected()
        if not node:
            return
        path = model.get_path(node)
        pid = model.get_value(node, R_ID)
        if pid in self.hidden:
            # unhide
            self.hidden.remove(pid)
            self._pmgr.unhide_plugin(pid)
        else:
            # hide
            self.hidden.add(pid)
            self._pmgr.hide_plugin(pid)
        self.__rebuild_reg_list(path, rescan=False)

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
        if pdata and (status & UPDATE) and (pdata.ptype == VIEW or
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

        # model: plugintype, hidden, pluginname, plugindescr, pluginid
        self._model_reg = Gtk.ListStore(
            GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_STRING,
            GObject.TYPE_STRING, GObject.TYPE_STRING, int)
        self._selection_reg = self._list_reg.get_selection()
        # add filter capabilities
        self._tree_filter = self._model_reg.filter_new()
        self._tree_filter.set_visible_func(self._apply_filter)

        # set model with sorting enabled
        self._list_reg.set_model(Gtk.TreeModelSort(model=self._tree_filter))
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
        label = Gtk.Label(label=_('Status'))
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

        self._wiki_btn = Gtk.Button(label=_("Wiki"))
        hbutbox.add(self._wiki_btn)
        self._wiki_btn.connect('clicked', self._wiki)
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

        label = Gtk.Label(label=_("* indicates 3rd party addon"))
        hbutbox.add(label)

        vbox_reg.pack_start(hbutbox, False, False, 0)

        return _('Plugins'), vbox_reg

    def button_press_reg(self, obj, event):
        """ Callback function from the user clicking on a line in reg plugin
        """
        # pylint: disable=protected-access
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            self._cursor_changed(obj)

    def filter_str_changed(self, _widget):
        """
        Called when filter string is changed.
        """
        self.__rebuild_reg_list(rescan=False)

    def _apply_filter(self, model, tr_iter, _data):
        """
        Check if we need hide or show row acording the filter.
        This is for "self._tree_filter.set_visible_func".
        """
        filter_str = self.filter_entry.get_text().lower()
        # if no string - show the row
        if not filter_str:
            return True

        # get addon filename
        pdata = self._preg.get_plugin(model.get_value(tr_iter, R_ID))
        p_txt = ''
        if pdata:
            p_txt = pdata.fname
        for col in (R_TYPE, R_STAT_S, R_NAME, R_DESC, R_ID):
            p_txt = p_txt + model[tr_iter][col]

        # check all row columns and hide it if some query word doesn't present
        filter_words = filter_str.split()
        p_txt = p_txt.lower()
        for word in filter_words:
            if word not in p_txt:
                # if some of words not present - hide the row
                return False
        # else - show the row
        return True

    def __rebuild_reg_list(self, path=None, rescan=True):
        """
        Called when creating list of plugins.
        """
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
        if len(self._tree_filter):
            self._list_reg.scroll_to_cell(path, None, True, 0.5, 0)
        self._cursor_changed(None)

    def _cursor_changed(self, _obj):
        """
        Update buttons etc, when selecting a new row
        """
        model, node = self._selection_reg.get_selected()
        if not node:
            self.infodata = ''
            self.info_text_buf.set_text(self.infodata)
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
        self.infodata, faildata = self.__info(pid)  # get text of plugin data
        self.info_text_buf.set_text('')
        _iter = self.info_text_buf.get_start_iter()
        self.info_text_buf.insert_markup(_iter, self.infodata, -1)
        _iter = self.info_text_buf.get_end_iter()
        self.info_text_buf.insert(_iter, faildata, -1)
        if self.help:
            self._wiki_btn.set_sensitive(True)
        else:
            self._wiki_btn.set_sensitive(False)

    def __info(self, pid):
        """ Gather information on a plugin
        """
        # from uninstalled plugins
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
            self.help = pdata.help_url if pdata.help_url else ''
            aud = AUDIENCETEXT[pdata.audience]
            status = STATUSTEXT[pdata.status]

            # assemble requirements
            reqs = ''
            dep_re = pdata.requires_exe
            if dep_re:
                reqs += "    <b>{0}:</b>: {1}\n".format(
                    _("Executables"), ' '.join(dep_re))
            dep_rg = pdata.requires_gi
            if dep_rg:
                reqs += "    <b>{0}:</b> ".format(
                    _("GObject introspection modules"))
                tup = dep_rg[0]
                reqs += tup[0] + ' ' + tup[1]
                for i in range(1, len(dep_rg)):
                    if i != 0:
                        reqs += ', '
                    tup = dep_rg[i]
                    reqs += tup[0] + ' ' + tup[1]
                reqs += '\n'
            dep_rm = pdata.requires_mod
            if dep_rm:
                reqs += "    <b>{0}:</b>: {1}\n".format(
                    _("Python modules"), ' '.join(dep_rm))
        else:   # from installed plugins
            for addon in self.addons:
                if addon['i'] == pid:
                    name = addon['n']
                    typestr = PTYPE_STR[addon['t']]
                    desc = addon['d']
                    vers = addon['v']
                    auth = ''
                    email = ''
                    fname = addon['z']
                    fpath = addon['_u']
                    self.help = addon['h']
                    aud = AUDIENCETEXT[addon['a']]
                    status = STATUSTEXT[addon['s']]

                    # Requirements
                    reqs = ''
                    info = Requirements().info(addon)
                    for i in range(0, len(info), 2):
                        reqs += '    <b>{0}:</b> '.format(info[i])
                        req_lst = info[i+1]
                        reqs += ' '.join(req_lst[0])
                        for j in range(1, len(req_lst)):
                            reqs += ', ' + ' '.join(req_lst[j])
                        reqs += '\n'
                    break

        if len(auth) > 60:
            auth = auth[:60] + '...'
        if len(email) > 60:
            email = email[:60] + '...'
        infotxt = (
            "<b>%(plugnam)s:</b> %(name)s [%(typestr)s]    "
            "<b>%(plug_id)s:</b> %(id)s    <b>%(plugver)s:</b> %(version)s\n"
            "<b>%(plugdes)s:</b> %(descr)s\n"
            "<b>%(plugfil)s:</b> %(fname)s    <b>%(plugpat)s:</b> %(fpath)s\n"
             % {
                'id': pid,
                'name': name,
                'typestr': typestr,
                'descr': desc,
                'version': vers,
                'fname': fname,
                'fpath': fpath,
                'plug_id': _("Id"),
                'plugnam': _("Plugin name"),
                'plugdes': _("Description"),
                'plugver': _("Version"),
                'plugfil': _("Filename"),
                'plugpat': _("Location")})
        if auth:
            infotxt += "<b>{0}:</b> {1}\n".format(_("Authors"), auth)
        if email:
            infotxt += "<b>{0}:</b> {1}\n".format(_("Email"), email)
        infotxt += ("<b>%(plugaud)s:</b> %(aud)s    <b>%(plugstat)s:</b> %(status)s\n"
            % {
                'aud' : aud,
                'status': status,
                'plugaud': _("Audience"),
                'plugstat': _("Status")})
        self.helpname = ""
        if not self.help:
            if 'gramplet' in fpath:
                self.help = URL_MANUAL_PAGE + "_-_Gramplets"
                self.helpname = name
            if 'tools' in fpath:
                self.help = URL_MANUAL_PAGE + "_-_Tools"
                self.helpname = name
            if 'report' in fpath:
                self.help = URL_MANUAL_PAGE + "_-_Reports"
                self.helpname = name

        if self.help:   # Wiki help
            infotxt += ("<b>{0}:</b> {1}".format(_("Help"), self.help) +
                        (('#' + self.helpname) if self.helpname else '') + '\n')

        if reqs:        # Requirements
            infotxt += "<b>{0}:</b>\n {1}".format(_("Requires"), reqs)
        # Loaded plugins
        success_list = self._pmgr.get_success_list()
        if pdata:
            for i in success_list:
                if pdata.id == i[2].id:
                    infotxt += '<span color="green">{0}</span>  '.format(_('Loaded'))
                    break
        if pid in self.hidden:  # hidden plugins
            infotxt += '<span color="red">{0}</span>'.format(_('Hidden'))
        # Handle failed plugins
        fail_list = self._pmgr.get_fail_list()
        failtxt = ''
        for i in fail_list:
            # i = (filename, (exception-type, exception, traceback), pdata)
            if pdata == i[2]:
                tb = ''.join(
                    traceback.format_exception(i[1][0], i[1][1], i[1][2]))
                infotxt += '<span color="red">{0}</span>\n'.format(_('Failed'))
                failtxt = '{0}\n{1}\n<{2}'.format(str(i[1][0]),
                    str(i[1][1]), tb)
                break
        return infotxt, failtxt

    def _web_help(self):
        display_help(WIKI_PAGE)

    def __populate_reg_list(self):
        """ Build list of plugins"""
        if not self.addons:
            self.addons = get_all_addons()

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
                row = [PTYPE_STR[plugin_dict["t"]], status_str,
                       markup_escape_text(plugin_dict["n"]),
                       markup_escape_text(plugin_dict["d"]),
                       plugin_dict["i"], status]
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
                addons.append([typestr, status_str,
                               markup_escape_text(pdata.name),
                               markup_escape_text(pdata.description),
                               pdata.id, status])
        for row in sorted(addons, key=itemgetter(R_TYPE, R_NAME)):
            if self._show_hidden or (row[R_ID] not in self.hidden):
                self._model_reg.append(row)
        self._selection_reg.select_path('0')

    def build_menu_names(self, _obj):
        return (TITLE, ' ')

    def _wiki(self, _obj):
        """
        Display the wiki page for the addon.
        """
        if self.help.startswith(("http://", "https://")):
            display_url(self.help)
        else:
            display_help(self.help, self.helpname)


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
            'pane_setting'  : 400
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
            'pane_setting': ("=num", "pane setting", 'pane setting in pix')}
