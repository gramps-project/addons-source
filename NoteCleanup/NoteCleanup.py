#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2016      Paul Culley (some code by Nick Hall)
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

"""Tools/Utilities/Note Cleanup"""

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import os
import io
import re
import html

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
from gramps.gui.dialog import WarningDialog
from gramps.gui.editors import EditNote
from gramps.gen.lib import Note
from gramps.gen.errors import WindowActiveError
from gramps.gen.constfunc import conv_to_unicode
from gramps.gen.lib import (StyledText, StyledTextTag, StyledTextTagType)
from gramps.gui.widgets.styledtexteditor import StyledTextEditor


#-------------------------------------------------------------------------
#
# constants
#
#-------------------------------------------------------------------------
CLEANED = 0
LINK = 1
ISSUE = 2
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

#-------------------------------------------------------------------------
#
# Media Verify
#
#-------------------------------------------------------------------------
class NoteCleanup(tool.Tool, ManagedWindow):
    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate

        tool.Tool.__init__(self, dbstate, options_class, name)

        self.window_name = _('Note Cleanup Tool')
        ManagedWindow.__init__(self, uistate, [], self.__class__)

        self.dbstate = dbstate
        self.trans = None
        self.moved_files = []
        self.titles = [_('Cleaned Notes'), _('Links Only'),  
                       _('Issues')]
        self.models = []
        self.views = []
        self.changelist = []
        self.changelistidx = 0

        window = MyWindow(self.dbstate, self.uistate, [])
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        hbox.set_homogeneous(True)
        rvbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, width_request=400)
        vbox.pack_start(hbox, True, True, 5)
        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        self.notebook.connect('switch-page', self.pagesw)
        for title in self.titles:
            self.create_tab(title)
        hbox.pack_start(self.notebook, True, True, 3)
        hbox.pack_start(rvbox, True, True, 3)

        bbox = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.pack_start(bbox, False, False, 5)
        close = Gtk.Button(_('Close'))
        close.set_tooltip_text(_('Close the Note Cleanup Tool'))
        close.connect('clicked', self.close)
        save = Gtk.Button(_('Save All'))
        save.set_tooltip_text(_('Save All Changes'))
        save.connect('clicked', self.saveit)
        search = Gtk.Button(_('Search'))
        search.set_tooltip_text(_('Search for Untidy Notes'))
        search.connect('clicked', self.cleanup)
        testnote = Gtk.Button(_('Generate Test Notes'))
        testnote.set_tooltip_text(_(
            'Generate Test notes in range N99996-N99999.\n'
            'These are added to your database, so you may want to work with'
            ' a test database or delete them later.'))
        testnote.connect('clicked', self.gentest)
        export = Gtk.Button(_('Export'))
        export.set_tooltip_text(_('Export the results to a text file'))
        export.connect('clicked', self.export_results)
        bbox.add(search)
        bbox.add(testnote)
        bbox.add(export)
        bbox.add(save)
        bbox.add(close)
        self.tb = StyledTextEditor()
        self.tb.set_editable(False)
        self.tb.set_wrap_mode(Gtk.WrapMode.WORD)
        tbw = Gtk.ScrolledWindow()
        tbw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        tbw.add(self.tb)
        rvbox.pack_start(tbw, True, True, 0)
        self.ta = StyledTextEditor()
        self.ta.set_editable(True)
        self.ta.set_wrap_mode(Gtk.WrapMode.WORD)
        taw = Gtk.ScrolledWindow()
        taw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        taw.add(self.ta)
        tat=self.ta.get_toolbar()
        tat.set_icon_size(Gtk.IconSize.SMALL_TOOLBAR)
        tatb=tat.get_nth_item(5)
        tat.remove(tatb)
        tatb=tat.get_nth_item(5)
        tat.remove(tatb)
        rvbox.pack_start(tat, False, False, 0)
        rvbox.pack_start(taw, True, True, 0)
        self.clear_models()
        vbox.show_all()
        window.add(vbox)
        window.set_size_request(800, 400)
        self.set_window(window, None, self.window_name)
        self.show()

        self.show_tabs()
        WarningDialog(self.window_name,
              _("Please back up your database before running this tool.\n\n"
              "Start the tool by pressing the 'Search' button, then review"
              " the results.\n"
              "When satisifed press the 'Save All' button to save your work.\n"
              "You may export a summary list of the notes that"
              " were found using the 'Export' button."),
                self.window)


    def build_menu_names(self, obj):
        return (_('Clean up Notes'), 
                self.window_name)

    def create_tab(self, title):
        """
        Create a page in the notebook.
        """
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        view = Gtk.TreeView()
        column = Gtk.TreeViewColumn(_('Notes'))
        view.append_column(column)
        cell = Gtk.CellRendererText()
        column.pack_start(cell, True)
        column.add_attribute(cell, 'text', 0)
        column.set_sort_column_id(0)
        column.set_sort_indicator(True)
        model = Gtk.ListStore(str, int)
        view.set_model(model)
        page = self.notebook.get_n_pages()
        view.connect('button-press-event', self.button_press, page)
        selection = view.get_selection()
        selection.connect('changed', self.selection_changed, page)
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
                self.edit(value)


    def selection_changed(self, selection, page):
        """
        Called when selection changed within the notebook tab
        """
        model, iter_ = selection.get_selected()
        if iter_:
            value = model.get_value(iter_, 1)
            self.showit(value)
    
    def pagesw(self, notebook, page, pagenum):
        """
        called when we switch tabs in the notebook
        """
        selection = self.views[pagenum].get_selection()
        model, iter_ = selection.get_selected()
        if iter_:
            value = model.get_value(iter_, 1)
            self.showit(value)
    

    def edit(self,indx):
        """
        Edit the note object with the given handle.
        """
        handle = self.changelist[indx][0]
        note = self.db.get_note_from_handle(handle)
        try:
            EditNote(self.dbstate, self.uistate, [], note)
        except WindowActiveError:
            pass

    def showit(self, indx):
        """
        Show the selection on right hand panes
        """
        self.update_changelist()
        self.indx = indx
        value = self.changelist[indx]
        self.tb.set_text(value[1])
        self.ta.set_text(value[2])

    def update_changelist(self):
        if self.indx != []:
            y=self.ta.get_text()
            z=self.changelist[self.indx][2]
            if y.serialize() != z.serialize():    # if y != z: doesn't work!!!
                x=(self.changelist[self.indx][0],\
                    self.changelist[self.indx][1], y)
                self.changelist[self.indx] = x
             
    def gentest(self, button):
        """
        Create some test notes.
        """
        with DbTxn(_("Cleanup Test Notes"), self.db) as trans:
            gid = 'N99996'
            text='A note with &lt;a target=new href=&quot;'\
                'http://seekingmichigan.org&quot;&gt;'\
                'http://seekingmichigan.org&lt;/a&gt;.'
            self.add_note(gid, text, trans)
            gid = 'N99997'
            text='http://www.google.com'
            self.add_note(gid, text, trans)
            gid = 'N99998'
            text= 'Quick test of <i>italics</i>, <b>bold</b>, <u>underline'\
                '</u>, and <a href="http://www.google.com">Google</a>.'
            self.add_note(gid, text, trans)
            gid = 'N99999'
            text = 'An <??>issue</??> with this note'
            self.add_note(gid, text, trans)

    def add_note(self, gid, text, trans):
        new_note = self.db.get_note_from_gramps_id(gid)
        if new_note:
            new_note.set(text)
            self.db.commit_note(new_note, trans)
            msg = _("Add Test Note")
        else:
            new_note = Note(text)
            new_note.set_gramps_id(gid)
            self.db.add_note(new_note, trans)
            msg = _("Add Test Note")
        trans.set_description(msg)


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
            filename = conv_to_unicode(filename)
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
                selection = self.views[page].get_selection()
                selection.select_path(Gtk.TreePath.new_first())
                tab.show()
            else:
                tab.hide()

    def clear_models(self):
        """
        Clear the models.
        """
        for model in self.models:
            model.clear()
        self.changelist = []
        self.indx =[]
        self.tb.set_text(StyledText(_('\n\n'
            'Notes selected on the left pane are shown Before cleanup in'
            ' this box.')))
        self.ta.set_text(StyledText(_('\n\n'
            'Notes selected on the left pane are shown After cleanup in this'
            ' box.\n'
            'If you wish to make changes, you can make them here and'
            ' use the style controls in the toolbar above.')))
        
    def saveit(self, button):
        """
        Commit the changes to the database
        """
        self.update_changelist()
        progress = ProgressMeter(self.window_name, can_cancel=True,
                                 parent=self.window)

        length = len(self.changelist)
        progress.set_pass(_('Saving Notes'), length)

        with DbTxn(_("Saving Cleaned Notes"), self.db, batch=False) as trans:
            for changed in self.changelist:
                note = self.db.get_note_from_handle(changed[0])
                note.set_styledtext(changed[2])
                self.db.commit_note(note, trans)
                msg = _("Note Cleanup")
                trans.set_description(msg)
                progress.step()
                if progress.get_cancelled():
                    break
        self.clear_models()
        self.show_tabs()
        progress.close()


    def cleanup(self, button):
        """
        Cleanup Notes.
        """
        self.clear_models()

        progress = ProgressMeter(self.window_name, can_cancel=True,
                                 parent=self.window)

        length = self.db.get_number_of_notes()
        progress.set_pass(_('Scanning Notes'), length)

        for handle in self.db.get_note_handles():
            note = self.db.get_note_from_handle(handle)
            g_id = note.gramps_id
            stext = note.get_styledtext()
            handle = handle.decode('utf-8')
            optype = -1
            ## find the notes and do cleanup
            if not stext.tags:
                result = self.convert_to_styled(stext.string)
                indx = len(self.changelist)
                for styledtext_tag in result.tags:
                    if int(styledtext_tag.name) == StyledTextTagType.HIGHLIGHT:
                        optype = ISSUE
                        break
                    elif int(styledtext_tag.name) == StyledTextTagType.LINK:
                        optype = LINK
                while True:
                    if optype == ISSUE:
                        # make list of notes with errors
                        self.models[ISSUE].append((self.preview(stext, g_id), indx))
                    elif stext.string != result.string:
                        # Make list of edited notes
                        self.models[CLEANED].append((self.preview(stext, g_id), indx))
                    elif optype == LINK:
                        # make list of notes with only links
                        self.models[LINK].append((self.preview(stext, g_id), indx))
                    else:
                        break
                    self.changelist.append((handle, stext, result))
                    break

            progress.step()
            if progress.get_cancelled():
                break

        self.show_tabs()
        progress.close()
    
    def preview(self, stext, g_id):
        prev = " ".join(str(stext).split())
        if len(prev) > 80:
            text = '%s -> %s' % (g_id, prev[:80] + "...")
        else:
            text = '%s -> %s' % (g_id, prev)
        return text

    def convert_to_styled(self, data):
        """
        This scans incoming notes for possible html.  It converts a select few
        tags into StyledText and removes the rest of the tags.  Notes of this
        type occur in data from FTM and ancestry.com.  Result is a much
        cleaner note.
        
        @param data: a string of text possibly containg html
        @type data: str 
        
        """
        token_specification = [
            # Italics: must not be nested, any tag terminates
            ('ITALIC',  r'<i>.*?(?=<)'),
            # bolds: must not be nested, any tag terminates
            ('BOLD',    r'<b>.*?(?=<)'),
            # Underlines: must not be nested, any tag terminates
            ('UNDER',   r'<u>.*?(?=<)'),
            # Table Header Begin (start Bold)
            ('TBLHDRB', r'<tr><th>'),
            # Table Header End (end Bold and \n)
            ('TBLHDRE', r'</th></tr>'),
            # Table Header Cell (repl with ': ')
            ('TBLHDRC', r'(<\th>)?<th>'),
            # Table Cell break (repl with ':  ')
            ('TBLCELL', r'</td><td>'),
            # Table
            ('TABLE',   r'</?table.*?>'),
            # Href start to end
            ('HREF',    r'<+a .*?href=["\' ]*(?P<HREFL>.*?)'\
                        r'["\' ].*?>(?P<HREFT>.*?)</a>+'),
            # HTTP start to end (have to rstrip(' .:') for link)  
            ('HTTP',    r'https?:.*?(\s|$)'),
            # Paragraph end
            ('PARAEND', r'</p>|</li>|<tr>|<br>'),
            # Skip over these tags
            ('SKIP',    r'<ul>|</ul>|<li>|<p>|</tr>|<td>|</td>|<th>|'\
                        r'</a>|</i>|</b>|</u>'),
            # Unimplemented HTTP tags
            ('UNKNWN',  r'<.*?>'),
            ]
        tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
        
        prev = 0
        chunkpos = 0
        chunks = []
        italics = []
        bolds = []
        unders = []
        links = []
        reds = []
        bldpos = -1
        data = html.unescape(data)      # clean up escaped html "&lt;" etc.
        for mo in re.finditer(tok_regex, data, flags=(re.DOTALL | re.I)):
            kind = mo.lastgroup
            st_txt = mo.group(kind)
            in_start = mo.start()
            in_end = mo.end()
            if kind == 'SKIP' or kind == 'TABLE':
                if prev != in_start:
                    chunks.append(data[prev:in_start])
                    chunkpos += (in_start - prev)
            elif kind == 'PARAEND':
                chunks.append(data[prev:in_start] + '\n')
                chunkpos += (in_start - prev + 1)
            elif kind == 'ITALIC':
                chunks.append(data[prev:in_start] + data[(in_start + 3):in_end])
                newpos = chunkpos - prev + in_end - 3
                italics.append((chunkpos + in_start - prev, newpos))
                chunkpos = newpos
            elif kind == 'BOLD':
                chunks.append(data[prev:in_start] + data[(in_start + 3):in_end])
                newpos = chunkpos - prev + in_end - 3
                bolds.append((chunkpos + in_start - prev, newpos))
                chunkpos = newpos
            elif kind == 'UNDER':
                chunks.append(data[prev:in_start] + data[(in_start + 3):in_end])
                newpos = chunkpos - prev + in_end - 3
                unders.append((chunkpos + in_start - prev, newpos))
                chunkpos = newpos
            elif kind == 'HTTP':      #HTTP found
                st_txt = mo.group('HTTP')
                oldpos = chunkpos + in_start - prev
                chunks.append(data[prev:in_start] + st_txt)
                chunkpos += (in_start - prev + len(st_txt))
                st_txt = st_txt.rstrip(' .:)')
                newpos = oldpos + len(st_txt)
                links.append((st_txt, oldpos, newpos))
            elif kind == 'HREF':      #HREF found
                st_txt = mo.group('HREFT')
                lk_txt = mo.group('HREFL')
                # fix up relative links emmitted by ancestry.com
                if lk_txt.startswith("/search/dbextra") \
                            or lk_txt.startswith("/handler/domain"):
                    lk_txt = "http://search.ancestry.com" + lk_txt
                oldpos = chunkpos + in_start - prev
                # if tag (minus any trailing '.') is substring of link
                if st_txt[0:-1] in lk_txt:
                    st_txt = lk_txt   # just use the link
                else:                 # use link and tag
                    st_txt = " " + lk_txt + " (" + st_txt + ")"
                newpos = oldpos + len(st_txt)
                chunks.append(data[prev:in_start] + st_txt)
                chunkpos += (in_start - prev + len(st_txt))
                links.append((lk_txt, oldpos, newpos))
            elif kind == 'TBLCELL' or kind == 'TBLHDRC':      #Table cell break
                chunks.append(data[prev:in_start] + ':  ')
                chunkpos += (in_start - prev + 3)
            elif kind == 'TBLHDRB':      #header start
                if prev != in_start:
                    chunks.append(data[prev:in_start])
                    chunkpos += (in_start - prev)
                bldpos = chunkpos
            elif kind == 'TBLHDRE':      #Header end
                if bldpos == -1:
                    if prev != in_start:
                        chunks.append(data[prev:in_end])
                        newpos = chunkpos - prev + in_end
                        reds.append((chunkpos + in_start - prev, newpos))
                        chunkpos = newpos
                    print('Invalid table header, no start tag found')
                else:
                    if prev != in_start:
                        chunks.append(data[prev:in_start])
                        chunkpos += (in_start - prev)
                    bolds.append((bldpos, chunkpos))
                    bldpos = -1
            elif kind == 'UNKNWN':
                if prev != in_start:
                    chunks.append(data[prev:in_end])
                    newpos = chunkpos - prev + in_end
                    reds.append((chunkpos + in_start - prev, newpos))
                    chunkpos = newpos
                print('Unexpected or unimplemented HTML tag', st_txt)
            else: print("shouldn't get here")
        
            prev = in_end
        chunks.append(data[prev:])
                 
        result = ''.join(chunks)
        tags = []
        for link in links:
            tags.append(StyledTextTag(StyledTextTagType.LINK, link[0], [(link[1], link[2])]))
        if italics:
            tags.append(StyledTextTag(StyledTextTagType.ITALIC, False , italics))
        if bolds:
            tags.append(StyledTextTag(StyledTextTagType.BOLD, False , bolds))
        if unders:
            tags.append(StyledTextTag(StyledTextTagType.UNDERLINE, False , unders))
        if reds:
            tags.append(StyledTextTag(StyledTextTagType.HIGHLIGHT, '#FFFF00' , reds))
        return StyledText(result,tags)

#------------------------------------------------------------------------
#
# My own widow class (to provide a source for dbstate)
#
#------------------------------------------------------------------------
class MyWindow(Gtk.Window):
    def __init__(self, dbstate, uistate, track):
        self.dbstate = dbstate
        self.uistate = uistate
        self.track = track
        Gtk.Window.__init__(self)
 

#------------------------------------------------------------------------
#
# Note Cleanup Options
#
#------------------------------------------------------------------------
class NoteCleanupOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """
    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
