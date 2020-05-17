#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015      Nick Hall
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

"""
Form selector.
"""

#------------------------------------------------------------------------
#
# GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Gdk

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from form import get_form_ids, get_form_id, get_form_type
from form import DEFINITION_KEY, FormDlgInfo, GetEnvInt


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

#------------------------------------------------------------------------
# Logging
#------------------------------------------------------------------------
import logging
_LOG = logging.getLogger("Form Gramplet")



#------------------------------------------------------------------------
#
# SelectForm class
#
#------------------------------------------------------------------------
class SelectForm(object):
    """
    Form Selector.
    """
    def __init__(self, dbstate, uistate, track):
        self.dbstate = dbstate
        self.uistate = uistate
        self.top = self._create_dialog()

    def _create_dialog(self):
        """
        Create a dialog box to select a form.
        """
        # pylint: disable-msg=E1101
        title = _("%(title)s - Gramps") % {'title': _("Select Form")}
        _LOG.debug('Select Form Dialog: %s' % title)
        top = Gtk.Dialog(title)
        top.set_default_size(GetEnvInt('G.FORM.SF.W', 400), GetEnvInt('G.FORM.SF.H', 350))
        top.set_modal(True)
        top.set_transient_for(self.uistate.window)
        top.vbox.set_spacing(5)
        label = Gtk.Label(label='<span size="larger" weight="bold">%s</span>'
                          % _("Select Form"))
        label.set_use_markup(True)
        top.vbox.pack_start(label, 0, 0, 5)
        box = Gtk.Box()
        top.vbox.pack_start(box, 1, 1, 5)

        self.model = Gtk.TreeStore(str, str)

        self.tree = Gtk.TreeView(model=self.model)
        self.tree.connect('button-press-event', self.__button_press)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Source", renderer, text=1)
        column.set_sort_column_id(1)
        self.tree.append_column(column)

        slist = Gtk.ScrolledWindow()
        slist.add(self.tree)
        slist.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        box.pack_start(slist, 1, 1, 5)
        top.add_button(_('_Cancel'), Gtk.ResponseType.CANCEL)
        top.add_button(_('_OK'), Gtk.ResponseType.OK)
        top.show_all()
        return top

    def _populate_model(self):
        """
        Populate the model.
        """
        self.model.clear()
        form_types = {}
        SrcAttrs = []
        for handle in self.dbstate.db.get_source_handles():
            source = self.dbstate.db.get_source_from_handle(handle)
            form_id = get_form_id(source)
            if form_id: SrcAttrs.append(form_id)
            if form_id in get_form_ids():
                form_type = get_form_type(form_id)
                if _(form_type) in form_types:
                    parent = form_types[_(form_type)]
                else:
                    parent = self.model.append(None, (None, _(form_type)))
                    form_types[_(form_type)] = parent
                self.model.append(parent, (source.handle, source.title))
                #_LOG.warning("model form_type =%s" % form_type)
                #_LOG.warning("model.append 1=%s, 2=%s" % (source.handle, source.title))
        self.model.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self.tree.expand_all()

        # Check for user or installation mistake (form empty)
        if  len(form_types) != 0:
            _LOG.debug('%s SOURCE ID\'s (in the "%s" attribute): %s' % (len(SrcAttrs), DEFINITION_KEY, str(SrcAttrs)))
        else:
            # NO MATCHES FOUND, Report error if no matches were found
            FrmAttrs = []
            for form_id in get_form_ids():
                FrmAttrs.append(form_id)
            FormDlgInfo('NO FORM & SOURCE MATCHES FOUND',
                          _('There were no sources with a attribute of "%s" which matched any form\'s "id" (loaded from XML).') % DEFINITION_KEY
                        + '\n\n'
                        + _('%s IDs in Sources') % len(SrcAttrs) + "\n"
                        + '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~' + "\n"
                        + str(SrcAttrs)
                        + '\n\n'
                        + _('%s IDs in loaded from form xml') % len(FrmAttrs) + "\n"
                        + '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~' + "\n"
                        + str(FrmAttrs)
                       )

    def __button_press(self, obj, event):
        """
        Called when a button press is executed
        """
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            model, iter_ = self.tree.get_selection().get_selected()
            if iter_:
                source_handle = model.get_value(iter_, 0)
                if source_handle:
                    self.top.response(Gtk.ResponseType.OK)

    def run(self):
        """
        Run the dialog and return the result.
        """
        self._populate_model()
        source_handle = None
        while True:
            response = self.top.run()
            if response == Gtk.ResponseType.HELP:
                display_help(webpage='Form_Addons')
            else:
                model, iter_ = self.tree.get_selection().get_selected()
                if iter_:
                    source_handle = model.get_value(iter_, 0)
                self.top.destroy()

            return source_handle
