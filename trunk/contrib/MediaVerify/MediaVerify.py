#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013      Nick Hall
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

"""Tools/Utilities/Media Verify"""

from __future__ import unicode_literals

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import os
import sys
import io
import hashlib

#-------------------------------------------------------------------------
#
# Gtk modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Gdk

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gui.plug import tool
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.utils import ProgressMeter, open_file_with_default_application
from gramps.gen.db import DbTxn
from gramps.gen.lib import Attribute, AttributeType
from gramps.gen.utils.file import (media_path_full, relative_path,
                                   get_unicode_path_from_file_chooser)
from gramps.gui.dialog import WarningDialog
from gramps.gui.editors import EditMedia
from gramps.gen.errors import WindowActiveError

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.get_addon_translator(__file__).gettext

#-------------------------------------------------------------------------
#
# Media Verify
#
#-------------------------------------------------------------------------
class MediaVerify(tool.Tool, ManagedWindow):
    def __init__(self, dbstate, uistate, options_class, name, callback=None):

        tool.Tool.__init__(self, dbstate, options_class, name)

        self.window_name = _('Media Verify Tool')
        ManagedWindow.__init__(self, uistate, [], self.__class__)

        self.dbstate = dbstate
        self.moved_files = []
        self.titles = [_('Moved/Renamed Files'), _('Missing Files'),  
                       _('Duplicate Files'), _('Extra Files'), 
                       _('No md5 Generated'), _('Errors')]
        self.models = []
        self.views = []

        window = Gtk.Window()
        vbox = Gtk.VBox()

        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        for title in self.titles:
            self.create_tab(title)
        vbox.pack_start(self.notebook, True, True, 5)

        bbox = Gtk.HButtonBox()
        vbox.pack_start(bbox, False, False, 5)
        close = Gtk.Button(_('Close'))
        close.set_tooltip_text(_('Close the Media Verify Tool'))
        close.connect('clicked', self.close)
        generate = Gtk.Button(_('Generate'))
        generate.set_tooltip_text(_('Generate md5 hashes for media objects'))
        generate.connect('clicked', self.generate_md5)
        verify = Gtk.Button(_('Verify'))
        verify.set_tooltip_text(_('Check media paths and report missing, '
                                  'duplicate and extra files'))
        verify.connect('clicked', self.verify_media)
        export = Gtk.Button(_('Export'))
        export.set_tooltip_text(_('Export the results to a text file'))
        export.connect('clicked', self.export_results)
        fix = Gtk.Button(_('Fix'))
        fix.set_tooltip_text(_('Fix media paths of moved and renamed files'))
        fix.connect('clicked', self.fix_media)
        bbox.add(close)
        bbox.add(generate)
        bbox.add(verify)
        bbox.add(export)
        bbox.add(fix)
        vbox.show_all()

        window.add(vbox)
        window.set_size_request(500, 300)
        self.set_window(window, None, self.window_name)
        self.show()

        self.show_tabs()

    def build_menu_names(self, obj):
        return (_('Verify Gramps media using md5 hashes'), 
                self.window_name)

    def create_tab(self, title):
        """
        Create a page in the notebook.
        """
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        view = Gtk.TreeView()
        column = Gtk.TreeViewColumn(_('Files'))
        view.append_column(column)
        cell = Gtk.CellRendererText()
        column.pack_start(cell, True)
        column.add_attribute(cell, 'text', 0)
        column.set_sort_column_id(0)
        column.set_sort_indicator(True)
        model = Gtk.ListStore(str, str)
        view.set_model(model)
        page = self.notebook.get_n_pages()
        view.connect('button-press-event', self.button_press, page)
        scrolled_window.add(view)
        self.models.append(model)
        self.views.append(view)
        label = Gtk.Label(title)
        self.notebook.append_page(scrolled_window, label)

    def button_press(self, view, event, page):
        """
        Called when a button is pressed on a treeview.
        """
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            model, iter_ = view.get_selection().get_selected()
            if iter_:
                value = model.get_value(iter_, 1)
                if page in (0, 1, 4):
                    self.edit(value)
                elif page in (2, 3):
                    self.display(unicode(value))

    def edit(self, handle):
        """
        Edit the media object with the given handle.
        """
        media = self.db.get_object_from_handle(handle)
        try:
            EditMedia(self.dbstate, self.uistate, [], media)
        except WindowActiveError:
            pass

    def display(self, path):
        """
        Display the given file.
        """
        full_path = media_path_full(self.db, path)
        open_file_with_default_application(full_path)

    def export_results(self, button):
        """
        Export the results to a text file.
        """
        chooser = Gtk.FileChooserDialog(
            _("Export results to a text file"), 
            self.uistate.window, 
            Gtk.FileChooserAction.SAVE, 
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, 
             Gtk.STOCK_SAVE, Gtk.ResponseType.OK))
        chooser.set_do_overwrite_confirmation(True)

        while True:
            value = chooser.run()
            filename = chooser.get_filename()
            filename = get_unicode_path_from_file_chooser(filename)
            if value == Gtk.ResponseType.OK:
                if filename:
                    chooser.destroy()
                    break
            else:
                chooser.destroy()
                return
        try:
            with io.open(filename, 'w') as report_file:
                for title, model in zip(self.titles, self.models):
                    self.export_page(report_file, title, model)
        except IOError as err:
            WarningDialog(self.window_name,
                          _('Error when writing the report: %s') % err.strerror,
                            self.window)

    def export_page(self, report_file, title, model):
        """
        Export a page of the report to a text file.
        """
        if len(model) == 0:
            return
        report_file.write(title + '\n')
        for row in model:
            report_file.write('    %s\n' % row[0])

    def show_tabs(self):
        """
        Show notebook tabs containing data.
        """
        for page, model in enumerate(self.models):
            tab = self.notebook.get_nth_page(page)
            if len(model) > 0:
                tab.show()
            else:
                tab.hide()

    def clear_models(self):
        """
        Clear the models.
        """
        for model in self.models:
            model.clear()

    def generate_md5(self, button):
        """
        Generate md5 hashes for media files and attach them as attributes to
        media objects.
        """
        self.clear_models()

        progress = ProgressMeter(self.window_name, can_cancel=True,
                                 parent=self.window)

        length = self.db.get_number_of_media_objects()
        progress.set_pass(_('Generating media hashes'), length)

        with DbTxn(_("Set media hashes"), self.db, batch=True) as trans:

            for handle in self.db.get_media_object_handles():
                media = self.db.get_object_from_handle(handle)

                full_path = media_path_full(self.db, media.get_path())
                try:
                    with io.open(full_path, 'rb') as media_file:
                        md5sum = hashlib.md5(media_file.read()).hexdigest()
                except IOError as err:
                    error_msg = '%s: %s' % (err.strerror, full_path)
                    self.models[5].append((error_msg, None))
                    progress.step()
                    continue

                for attr in media.get_attribute_list():
                    if str(attr.get_type()) == 'md5':
                        media.remove_attribute(attr)
                        break

                attr = Attribute()
                attr.set_type(AttributeType('md5'))
                attr.set_value(md5sum)

                media.add_attribute(attr)
                
                self.db.commit_media_object(media, trans)

                progress.step()
                if progress.get_cancelled():
                    break

        self.show_tabs()
        progress.close()

    def verify_media(self, button):
        """
        Verify media objects have the correct path to files in the media
        directory.  List missing files, duplicate files, and files that do not
        yet have a media file in Gramps.
        """
        self.clear_models()
        self.moved_files = []

        media_path = self.db.get_mediapath()
        if media_path is None:
            WarningDialog(self.window_name,
                          _('Media path not set.  You must set the "Base path '
                            'for relative media paths" in the Preferences.'),
                            self.window)
            return

        progress = ProgressMeter(self.window_name, can_cancel=True,
                                 parent=self.window)

        length = 0
        for root, dirs, files in os.walk(media_path):
            length += len(files)
        progress.set_pass(_('Finding files'), length)

        all_files = {}
        for root, dirs, files in os.walk(media_path):
            for file_name in files:
                full_path = os.path.join(root, file_name)
                try:
                    with io.open(full_path, 'rb') as media_file:
                        md5sum = hashlib.md5(media_file.read()).hexdigest()
                except IOError as err:
                    error_msg = '%s: %s' % (err.strerror, full_path)
                    self.models[5].append((error_msg, None))
                    progress.step()
                    continue

                rel_path = relative_path(full_path, media_path)
                rel_path = rel_path.decode(sys.getfilesystemencoding())
                if md5sum in all_files:
                    all_files[md5sum].append(rel_path)
                else:
                    all_files[md5sum] = [rel_path]

                progress.step()
                if progress.get_cancelled():
                    break

        length = self.db.get_number_of_media_objects()
        progress.set_pass(_('Checking paths'), length)

        in_gramps = []
        for handle in self.db.get_media_object_handles():
            media = self.db.get_object_from_handle(handle)

            md5sum = None
            for attr in media.get_attribute_list():
                if str(attr.get_type()) == 'md5':
                    md5sum = attr.get_value()
                    in_gramps.append(md5sum)
                    break

            # Moved files
            gramps_path = media.get_path()
            if md5sum in all_files:
                file_path = all_files[md5sum]
                if gramps_path not in file_path:
                    if len(file_path) == 1:
                        self.moved_files.append((handle, file_path[0]))
                        text = '%s -> %s' % (gramps_path, file_path[0])
                        self.models[0].append((text, handle))
                    else:
                        gramps_name = os.path.basename(gramps_path)
                        for path in file_path:
                            if os.path.basename(path) == gramps_name:
                                self.moved_files.append((handle, path))
                                text = '%s -> %s' % (gramps_path, path)
                                self.models[0].append((text, handle))
            elif md5sum is None:
                text = '[%s] %s' % (media.get_gramps_id(), gramps_path)
                self.models[4].append((text, handle))
            else:
                self.models[1].append((gramps_path, handle))

            progress.step()
            if progress.get_cancelled():
                break

        # Duplicate files or files not in Gramps
        for md5sum in all_files:
            if len(all_files[md5sum]) > 1:
                text = ', '.join(all_files[md5sum])
                self.models[2].append((text, all_files[md5sum][0]))
            if md5sum not in in_gramps:
                text = ', '.join(all_files[md5sum])
                self.models[3].append((text, all_files[md5sum][0]))

        self.show_tabs()
        progress.close()

    def fix_media(self, button):
        """
        Fix paths to moved media files.
        """
        progress = ProgressMeter(self.window_name, can_cancel=True,
                                 parent=self.window)
        progress.set_pass(_('Fixing file paths'), len(self.moved_files))

        with DbTxn(_("Fix media paths"), self.db, batch=True) as trans:
            
            for handle, new_path in self.moved_files:
                media = self.db.get_object_from_handle(handle)
                media.set_path(new_path)
                self.db.commit_media_object(media, trans)

                progress.step()
                if progress.get_cancelled():
                    break

        self.models[0].clear()
        self.show_tabs()
        progress.close()

#------------------------------------------------------------------------
#
# Media Verify Options
#
#------------------------------------------------------------------------
class MediaVerifyOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """
    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
