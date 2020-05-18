#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009-2015 Nick Hall
# Copyright (C) 2011      Gary Burton
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
Form editor.
"""

#------------------------------------------------------------------------
#
# GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.editors.objectentries import PlaceEntry
from gramps.gui.widgets import (MonitoredEntry, MonitoredDate,
                                ValidatableMaskedEntry)
from gramps.gui.editors import EditPerson, EditFamily
from gramps.gui.display import display_help
from gramps.gui.dialog import ErrorDialog
from gramps.gui.selectors import SelectorFactory
from gramps.gui.editors.displaytabs import GalleryTab, GrampsTab
from gramps.gen.config import config
from gramps.gen.lib import (Event, EventType, EventRef, EventRoleType,
                            Person, Family, Attribute)
from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.datehandler import get_date, displayer
from form import ORDER_ATTR, GROOM, BRIDE
from form import (get_form_id, get_form_date, get_form_type, get_form_headings,
                  get_form_sections, get_section_title, get_section_type,
                  get_section_columns, get_form_citation)
from entrygrid import EntryGrid
from form import ( get_form_dateRO, get_form_dateLbl,
                   get_form_locn,   get_form_locnLbl,
                   get_form_ref,    get_form_refLbl,
                   FormDlgError, FormDlgInfo, FormDlgDebug,
                   GetObjectClass, get_help_file
                 )

# from datetime import datetime (fails for .today()!)
from datetime import date, datetime
from gramps.gen.lib           import Place, PlaceName
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.lib import Date
from gramps.gen.lib.date import Today
from gramps.gen.datehandler import parser  as DateParser
from gi.repository import Gdk
import os
import logging
_LOG = logging.getLogger("Form Gramplet")





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
#
# EditForm class
#
#------------------------------------------------------------------------
class EditForm(ManagedWindow):
    """
    Form Editor.
    """
    def __init__(self, dbstate, uistate, track, citation, callback):
        _LOG.debug('###############\n\nEditForm() starting')

        self.dbstate = dbstate
        self.uistate = uistate
        self.track = track
        self.db = dbstate.db

        self.citation = citation
        self.event = find_form_event(self.db, self.citation)
        self.callback = callback

        ManagedWindow.__init__(self, uistate, track, citation)

        self.HeadingsNeedsClicking = True
        self.widgets = {}
        top = self.__create_gui()
        self.set_window(top, None, self.get_menu_title())

        self.date_field = MonitoredDate(self.widgets['date_text'],
                                        self.widgets['date_button'],
                                        self.event.get_date_object(),
                                        self.uistate, self.track,
                                        self.db.readonly)

        self.place_field = PlaceEntry(self.dbstate, self.uistate, self.track,
                                      self.widgets['place_text'],
                                      self.widgets['place_event_box'],
                                      self.event.set_place_handle,
                                      self.event.get_place_handle,
                                      self.widgets['place_add'],
                                      self.widgets['place_share'])

        self.ref_field = MonitoredEntry(
            self.widgets['ref_entry'],
            self.citation.set_page,
            self.citation.get_page,
            self.db.readonly)

        self.__populate_gui(self.event)

        self.show()

        self._config = config.get_manager('form')
        width = self._config.get('interface.form-width')
        height = self._config.get('interface.form-height')
        self.window.resize(width, height)
        horiz_position = self._config.get('interface.form-horiz-position')
        vert_position = self._config.get('interface.form-vert-position')
        if horiz_position != -1:
            self.window.move(horiz_position, vert_position)

    def _add_tab(self, notebook, page):
        notebook.insert_page(page, page.get_tab_widget(), -1)
        page.label.set_use_underline(True)
        return page

    def _remove_tab(self, notebook, page):
        page_num = notebook.page_num(page.get_tab_widget())
        notebook.remove_page(page_num)

    def get_menu_title(self):
        """
        Get the menu title.
        """
        if self.event.get_handle():
            date = get_date(self.event)
            if not date:
                date = 'unknown'
            dialog_title = _('Form: %s')  % date
        else:
            dialog_title = _('New Form')
        return dialog_title

    def build_menu_names(self, event):
        """
        Build menu names. Overrides method in ManagedWindow.
        """
        return (_('Edit Form'), self.get_menu_title())

    def __create_gui(self):
        """
        Create and display the GUI components of the editor.
        """
        root = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        root.set_transient_for(self.uistate.window)
        # Initial position for first run
        root.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_margin_left(2)
        vbox.set_margin_right(2)
        vbox.set_margin_top(2)
        vbox.set_margin_bottom(2)

        grid = Gtk.Grid()
        grid.set_margin_left(6)
        grid.set_margin_right(6)
        grid.set_row_spacing(6)
        grid.set_column_spacing(6)
        self.widgets['grid'] = grid

        source_label = Gtk.Label(label=_("Source:"))
        source_label.set_halign(Gtk.Align.START)
        source_label.set_valign(Gtk.Align.CENTER)
        grid.attach(source_label, 0, 0, 1, 1)

        source_text = Gtk.Label()
        source_text.set_hexpand(True)
        source_text.set_halign(Gtk.Align.START)
        source_text.set_valign(Gtk.Align.CENTER)
        self.widgets['source_text'] = source_text
        grid.attach(source_text, 1, 0, 1, 1)

        ref_label = Gtk.Label(label=_("Reference:"))
        ref_label.set_halign(Gtk.Align.START)
        ref_label.set_valign(Gtk.Align.CENTER)
        self.widgets['ref_label'] = ref_label
        grid.attach(ref_label, 0, 1, 1, 1)

        ref_entry = Gtk.Entry()
        ref_entry.set_hexpand(True)
        grid.attach(ref_entry, 1, 1, 1, 1)
        self.widgets['ref_entry'] = ref_entry


        date_label = Gtk.Label(label=_("Date:"))
        date_label.set_halign(Gtk.Align.START)
        date_label.set_valign(Gtk.Align.CENTER)
        self.widgets['date_label'] = date_label
        grid.attach(date_label, 0, 2, 1, 1)

        date_text = ValidatableMaskedEntry()
        date_text.set_hexpand(True)
        grid.attach(date_text, 1, 2, 1, 1)
        self.widgets['date_text'] = date_text

        date_button = Gtk.Button()
        grid.attach(date_button, 2, 2, 1, 1)
        self.widgets['date_button'] = date_button

        place_label = Gtk.Label(label=_("Place:"))
        place_label.set_halign(Gtk.Align.START)
        place_label.set_valign(Gtk.Align.CENTER)
        self.widgets['place_label'] = place_label
        grid.attach(place_label, 0, 3, 1, 1)

        place_text = Gtk.Label()
        place_text.set_hexpand(True)
        place_text.set_halign(Gtk.Align.START)
        place_text.set_valign(Gtk.Align.CENTER)
        self.widgets['place_text'] = place_text

        place_event_box = Gtk.EventBox()
        place_event_box.add(place_text)
        grid.attach(place_event_box, 1, 3, 1, 1)
        self.widgets['place_event_box'] = place_event_box


        #[CREATE] Fixed button order to be consistent with Gramps & the others on this form!
        image = Gtk.Image()
        image.set_from_icon_name('list-add', Gtk.IconSize.BUTTON)
        place_add = Gtk.Button()
        place_add.set_relief(Gtk.ReliefStyle.NONE)
        place_add.add(image)
        grid.attach(place_add, 2, 3, 1, 1)
        self.widgets['place_add'] = place_add

        #[USE EXISTING]
        image = Gtk.Image()
        image.set_from_icon_name('gtk-index', Gtk.IconSize.BUTTON)
        place_share = Gtk.Button()
        place_share.set_relief(Gtk.ReliefStyle.NONE)
        place_share.add(image)
        grid.attach(place_share, 3, 3, 1, 1)
        self.widgets['place_share'] = place_share

        # Add a Help Frame & Control (will be removed if not required later)
        HelpFrame  = Gtk.Frame()
        HelpControl = Gtk.Label('')
        HelpControl.set_use_markup(True)
        HelpControl.set_selectable(True)    #May include URLs or other Info
        HelpColor = Gdk.color_parse('blue')
        HelpControl.modify_fg(Gtk.StateFlags.NORMAL, HelpColor)

        HelpControl.set_line_wrap(True)
        #HelpControl.set_lines(3)            #This doesn't fail but doesn't work either: https://athenajc.gitbooks.io/python-gtk-3-api/content/gtk-group/gtklabel.html#setlines
        #place_text.set_vexpand(False)       #Also fail
        HelpFrame.add(HelpControl)
        grid.attach(HelpFrame, 0, 4, 4, 1)
        self.widgets['HelpFrame']   = HelpFrame
        self.widgets['HelpControl'] = HelpControl

        button_box = Gtk.ButtonBox()
        button_box.set_layout(Gtk.ButtonBoxStyle.END)

        help_btn = Gtk.Button(label=_('_Help'), use_underline=True)
        help_btn.connect('clicked', self.help_clicked)
        button_box.add(help_btn)
        button_box.set_child_secondary(help_btn, True)

        cancel_btn = Gtk.Button(label=_('_Cancel'), use_underline=True)
        cancel_btn.connect('clicked', self.close)
        button_box.add(cancel_btn)

        ok_btn = Gtk.Button(label=_('_OK'), use_underline=True)
        ok_btn.connect('clicked', self.save)
        button_box.add(ok_btn)

        self.notebook = Gtk.Notebook()

        vbox.pack_start(grid, expand=False, fill=True, padding=6)
        vbox.pack_start(self.notebook, expand=True, fill=True, padding=3)
        vbox.pack_end(button_box, expand=False, fill=True, padding=0)

        root.add(vbox)

        return root


    def GetPlaceFromName(self, place_name):
        """ This will create the place if it doesn't aready exist """

        # Look through all handles for the wanted place name
        if  place_name == "":
            return None
        place_list = self.dbstate.db.get_place_handles()
        for place_handle in place_list:
            place = self.dbstate.db.get_place_from_handle(place_handle)
            place_title = place_displayer.display(self.dbstate.db, place)
            #_LOG.debug('[GPFN] Looking at: : ' + place_title)
            if  place_title.strip() == place_name:
                _LOG.debug('[GPFN] Place found in DB [%s]: %s' % (place.get_gramps_id(), place_name))
                return place

        # The place doesn't already exist, create it [TODO: Now to set TYPE=FORMS (user can manually edit those for now)
        place = Place()
        place.set_title(place_name)
        place.set_type('_FORM')     #User can easy find these
        place.set_name(PlaceName(value=place_name))

        with DbTxn(_("Form Create New Place (%s)") % place_name, self.dbstate.db) as self.trans:
            self.dbstate.db.add_place(place, self.trans)
            self.dbstate.db.commit_place(place, self.trans)
        _LOG.debug("[GPFN] Place wasn't in DB, Created it: [%s] %s" % (place.get_gramps_id(), place_name))
        return place


    def NoteBookPageSelected(self, notebook, tab, index):
        if  tab == self.headings:
            _LOG.info('NoteBookPageSelected(): Headings Tab selected')
            self.HeadingsNeedsClicking = False

    def __populate_gui(self, event):
        """
        Populate the GUI for a given form event.
        """
        # Set source
        handle = self.citation.get_reference_handle()
        source = self.db.get_source_from_handle(handle)
        source_text = self.widgets['source_text']
        source_text.set_text(source.get_title())
        form_id = get_form_id(source)
        _LOG.debug('FORM ID = %s', form_id)

        # Set event type
        event_type = EventType()
        event_type.set_from_xml_str(get_form_type(form_id))
        self.event.set_type(event_type)

        # Set date LABEL TEXT
        dateLBL = get_form_dateLbl(form_id)       #From stored XML
        if  dateLBL != '':
            dateLBL = dateLBL + ":"
            _LOG.debug("Date Label = " + dateLBL)
            date_label = self.widgets['date_label']
            date_label.set_text(dateLBL)

        # Set Reference LABEL TEXT
        RefLbl = get_form_refLbl(form_id)       #From stored XML
        if  RefLbl != "":
            RefLbl = RefLbl + ":"
            _LOG.debug("Reference Label = " + RefLbl)
            ref_label = self.widgets['ref_label']
            ref_label.set_text(RefLbl)

        # Set Location LABEL TEXT
        LocnLbl = get_form_locnLbl(form_id)       #From stored XML
        if  LocnLbl != "":
            LocnLbl = LocnLbl + ":"
            _LOG.debug("Location Label   = " + LocnLbl)
            place_label = self.widgets['place_label']
            place_label.set_text(LocnLbl)


        # Set DEFAULT Reference Value
        ref_entry = self.widgets['ref_entry']
        RefDef = ref_entry.get_text()
        if  RefDef == "":                         #Currently no data in the field
            RefDef = get_form_ref(form_id)        #From stored XML
            if  RefDef != "":
                # Display in the form
                _LOG.debug("Setting DEFAULT Reference: " + RefDef)
                ref_entry.set_text(RefDef)

        # Set DEFAULT Location Value
        place_text = self.widgets['place_text']
        LocnDef = place_text.get_text()
        if  LocnDef in PlaceEntry.EMPTY_TEXT:     #Currently no data in the field, #EMPTY_TEXT looks like "<i>...text...</i>
            # This is not editing an existing event (with perhaps a different Location #
            LocnDef = get_form_locn(form_id)      #From stored XML
            if  LocnDef != "":
                # Display in the form
                _LOG.debug("Location Default = " + LocnDef)
                place_text.set_text(LocnDef)

                # Update the event
                NamePlace = self.GetPlaceFromName(LocnDef)
                event.set_place_handle(NamePlace.get_handle())

        # Determine if help text available or we wish to insert any (if no help remove the controls)
        HelpFrame   = self.widgets['HelpFrame']
        HelpControl = self.widgets['HelpControl']
        HelpContents = ''
        HelpFile = get_help_file(form_id)
        if  HelpFile:
            _LOG.debug("HELP FILE EXISTS: %s" % HelpFile)
            try:
                with open(HelpFile, 'r') as f:
                    # Read the file (don't strip remove leading & trailing whitespace yet)
                    HelpContents = f.read()

                    # Allow a paragraph to be broken up into multiple lines (spaces before the "\" are preserved so the user has full control of formatting)
                    HelpContents = HelpContents.replace('\\\n', '')

                    # Do strip after fixing "\" so all (including last definately removed
                    HelpContents = HelpContents.strip()
            except Exception as xArgs:
                _LOG.debug('Failed reading help file: %s' % str(xArgs))
        NumberHeadings = len( get_form_headings(form_id) )
        if  NumberHeadings != 0:
            # Add a warning to the help (about the "hidden" headings)
            if  HelpContents != '':
                HelpContents = '\n\n' + HelpContents
            HeadingsHelp = _('There are in {0} fields in the "Headings" tab.')
            HelpContents = '<span foreground="orange"><b>' + HeadingsHelp.format(NumberHeadings) + '</b></span>' + HelpContents
        if HelpContents == '':
            _LOG.debug("No help available (will hide the help controls)")
            grid = self.widgets['grid']
            grid.remove_row(4)
        else:
            # set_markup() has no return code so need to add error message first!
            HelpControl.set_markup( _('If you are seeing this, then the help text is incorrectly formatted with pango markup, see:\n')
                                    + '<b>https://developer.gnome.org/pango/stable/pango-Markup.html</b>\n\n'
                                    + _('HELP FILE')
                                    + ': '
                                    + str(HelpFile)
                                  )
            _LOG.debug("HELP CONTENTS: \n\n### HELP START ###\n%s\n### HELP END ###\n" % HelpContents)
            HelpControl.set_markup(HelpContents)        #How stupid, no RC, no error location/text!
            FrameText = _('Help for this form: [%s]') % form_id
            HelpFrame.set_label(' ' + FrameText + ' ')

        # Set date
        form_date  = get_form_date(form_id)          #From stored XML
        FormDateRO = get_form_dateRO(form_id)
        date_text = self.widgets['date_text']
        date_button = self.widgets['date_button']
        if form_date is not None:
            _LOG.debug("Adding the DATE for the event: %s (read-only=%s)" % (form_date, FormDateRO))
            date_text.set_text(displayer.display(form_date))
            self.event.set_date_object(form_date)
            self.citation.set_date_object(form_date)
            date_text.set_editable(not FormDateRO)
            date_button.set_sensitive(not FormDateRO)
        else:
            date_text.set_text(get_date(event))
            date_text.set_editable(True)
            date_button.set_sensitive(True)

        if  FormDateRO:
            DateTT = _('The date was set up by the form definition and is read-only')
        else:
            DateTT = _('You can enter "%s" or any other valid date string (or use the date picker)' % _('today'))
        _LOG.debug("Date Tooltip: %s" % DateTT)
        date_text.set_tooltip_text(DateTT)
        date_label.set_tooltip_text(DateTT)
        date_button.set_tooltip_text(DateTT)

        # Create tabs
        self.details = DetailsTab(self.dbstate,
                             self.uistate,
                             self.track,
                             self.event,
                             self.citation,
                             form_id)

        self.headings = HeadingsTab(self.dbstate,
                                       self.uistate,
                                       self.track,
                                       self.event,
                                       self.citation,
                                       form_id)

        self.gallery_list = GalleryTab(self.dbstate,
                                       self.uistate,
                                       self.track,
                                       self.citation.get_media_list())

        self._add_tab(self.notebook, self.details)
        #if  self.headings.is_empty:            #[BUG] The function always returns true!
        HeadingCnt = len(get_form_headings(form_id))
        if  HeadingCnt == 0:
            _LOG.debug('The Headings tab is empty so we are not displaying it.')
            self.HeadingsNeedsClicking = False
        else:
            _LOG.debug('The Headings tab has %d fields (so adding the tab)' % HeadingCnt)
            self._add_tab(self.notebook, self.headings)
        self._add_tab(self.notebook, self.gallery_list)

        self.notebook.show_all()
        self.notebook.set_current_page(0)

        # If headings exist then we want to be able to tell that a user at least looked at them
        self.notebook.connect('switch-page', self.NoteBookPageSelected)

    def save(self, button):
        """
        Called when the user clicks the OK button.
        """

        date_text   = self.widgets['date_text']
        GuiDateText = date_text.get_text().strip() #Date in the form's entry field
        EvtDateObj  = self.event.get_date_object() #Date in the Event Object (#gramps/gen/database.py)
        EvtDateText = str(EvtDateObj)
        if  EvtDateText == '0000-00-00':
            EvtDateText = ''
        if  EvtDateText == '.':                    #Force update
            EvtDateText = ''
        _LOG.debug('EditForm.Save() - OK button clicked, Saving to DB, EVENT DATE : %s'  % EvtDateText)
        if  GuiDateText == EvtDateText:
            _LOG.debug('The dates in the entry field match those in the event object :-)')
        else:
            _LOG.debug("The dates in the entry field don't match those in the event object :-(")
            _LOG.debug('The ENTRY FIELD (updated by user but not synced to object): %s' % GuiDateText)
            if  GuiDateText == '.':
                # User typed in "." for todays date (field was red but still accepted)
                Now = Today()
                _LOG.debug('User typed in "." (for today), Today\'s date = %s' % Now)
                self.event.set_date_object(Now)
            else:
                # User typed in a date in multiple possible formats, need to parse to date (that could fail)
                GuiDateObj = DateParser.parse(GuiDateText)
                if  GuiDateObj.is_valid():
                    # User's date parsed OK
                    _LOG.debug('User typed in "%s", Converted to = %s' % (GuiDateText, GuiDateObj))
                    self.event.set_date_object(GuiDateObj)
                else:
                    # Date supplied by user is not valid
                    FormDlgInfo(_("Invalid Date Format: ") + GuiDateText, _("The date you provided is invalid, the control should have had a red border (the only 'valid' entry with a red border is '.')..."))
                    return

        # Have a valid date?
        if  str(EvtDateObj) == '' or str(EvtDateObj) == '0000-00-00':
            FormDlgInfo(_("MISSING DATE"), _("You should fill in the manditory date information"))
            return

        # Have a valid REFERENCE?
        ref_entry = self.widgets['ref_entry']
        RefDef = ref_entry.get_text()
        if  RefDef == "":
            RefDef = _('NO REF')
            FormDlgInfo(_("MISSING REFERENCE"), _("You should fill in the manditory reference information"))
            return

        # Have a valid Reference? If so set up the "Description" of the event to be created
        if self.citation:
           # Get the Source Information
           source_handle = self.citation.get_reference_handle()
           source = self.db.get_source_from_handle(source_handle)
           source_text = source.get_title()

           # Add the description
           EvtDesc = RefDef + " @ " + source_text + " [" + _("form") + "]"
           _LOG.debug("Setting DESCRIPTION for the event: " + EvtDesc)
           self.event.set_description(EvtDesc)

        # For now just check user went to the Headings Tab (if that was required)
        if  self.HeadingsNeedsClicking:
            FormDlgInfo(_("Headings tab unvisited!"), _("There are headings to be filled in and you haven't gone and at least looked at them!"))
            return


        with DbTxn(self.get_menu_title(), self.db) as trans:
            if not self.event.get_handle():
                self.db.add_event(self.event, trans)

            citation_handle = self.citation.get_handle()
            if not self.citation.get_handle():
                self.db.add_citation(self.citation, trans)
                self.event.add_citation(self.citation.get_handle())
            else:
                self.db.commit_citation(self.citation, trans)

            self.headings.save()
            self.details.save(trans)

            self.db.commit_event(self.event, trans)
        self.close()
        self.callback()

    def close(self, *args):
        """
        Close the editor window.
        """
        (width, height) = self.window.get_size()
        self._config.set('interface.form-width', width)
        self._config.set('interface.form-height', height)
        (width, height) = self.window.get_position()
        self._config.set('interface.form-horiz-position', width)
        self._config.set('interface.form-vert-position', height)
        self._config.save()
        self.gallery_list.clean_up()
        ManagedWindow.close(self)

    def help_clicked(self, obj):
        """
        Display the relevant portion of Gramps manual
        """
        display_help(webpage='Form_Addons')

#------------------------------------------------------------------------
#
# Headings Tab
#
#------------------------------------------------------------------------
class HeadingsTab(GrampsTab):
    """
    Headings tab in the form editor.
    """
    def __init__(self, dbstate, uistate, track, event, citation, form_id):
        GrampsTab.__init__(self, dbstate, uistate, track, _('Headings'))
        self.db = dbstate.db
        self.event = event
        self.citation = citation

        self.heading_list = get_form_headings(form_id)
        self.create_table()
        self._set_label()

    def get_icon_name(self):
        return 'gramps-attribute'

    def build_interface(self):
        """
        Builds the interface.
        """
        self.model = Gtk.ListStore(str, str)
        self.view = Gtk.TreeView(model=self.model)
        self.selection = self.view.get_selection()

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Key'), renderer, text=0)
        self.view.append_column(column)

        renderer = Gtk.CellRendererText()
        renderer.set_property('editable', True)
        renderer.connect('edited', self.__cell_edited, (self.model, 1))
        column = Gtk.TreeViewColumn(_('Value'), renderer, text=1)
        self.view.append_column(column)

        scrollwin = Gtk.ScrolledWindow()
        scrollwin.add(self.view)
        scrollwin.set_policy(Gtk.PolicyType.AUTOMATIC,
                             Gtk.PolicyType.AUTOMATIC)

        self.pack_start(scrollwin, expand=True, fill=True, padding=0)

    def is_empty(self):
        """
        Indicate if the tab contains any data. This is used to determine
        how the label should be displayed.
        """
        for row in self.model:
            if row[1]:
                return False
        return True

    def create_table(self):
        """
        Create the list of headings.
        """
        self.model.clear()
        attr_list = self.event.get_attribute_list()
        for heading in self.heading_list:
            attr = get_attribute(attr_list, heading)
            if attr:
                self.model.append((heading, attr.get_value()))
            else:
                self.model.append((heading, ''))
        self._set_label()

    def save(self):
        """
        Save the form headings to the database.
        """
        new_list = []
        for attr in self.event.get_attribute_list():
            if attr.get_type() not in self.heading_list:
                new_list.append(attr)

        for row in self.model:
            if row[1]:
                attr = Attribute()
                attr.set_type(row[0])
                attr.set_value(row[1])
                attr.add_citation(self.citation.handle)
                new_list.append(attr)

        self.event.set_attribute_list(new_list)

    def __cell_edited(self, cell, path, new_text, data):
        """
        Called when a cell is edited in the list of headings.
        """
        model, column = data
        model[path][column] = new_text
        self._set_label()

#------------------------------------------------------------------------
#
# Details Tab
#
#------------------------------------------------------------------------
class DetailsTab(GrampsTab):
    """
    Details tab in the form editor.
    """
    def __init__(self, dbstate, uistate, track, event, citation, form_id):
        self.db = dbstate.db
        self.event = event
        self.citation = citation
        self.form_id = form_id
        GrampsTab.__init__(self, dbstate, uistate, track, _('Details'))

        self.populate_gui(event)
        self._set_label()

    def get_icon_name(self):
        return 'gramps-attribute'

    def build_interface(self):
        """
        Builds the interface.
        """
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.sections = {}
        for role in get_form_sections(self.form_id):
            section_type = get_section_type(self.form_id, role)
            if section_type == 'multi':
                section = MultiSection(self.dbstate, self.uistate, self.track,
                                       self.event, self.citation, self.form_id,
                                       role)
            elif section_type == 'person':
                section = PersonSection(self.dbstate, self.uistate, self.track,
                                        self.event, self.citation, self.form_id,
                                        role)
            else:
                section = FamilySection(self.dbstate, self.uistate, self.track,
                                        self.event, self.citation, self.form_id,
                                        role)
            vbox.pack_start(section, False, False, 0)
            self.sections[role] = section
        scrollwin = Gtk.ScrolledWindow()
        scrollwin.add(vbox)
        scrollwin.set_policy(Gtk.PolicyType.AUTOMATIC,
                             Gtk.PolicyType.AUTOMATIC)

        self.pack_start(scrollwin, expand=True, fill=True, padding=0)

    def is_empty(self):
        """
        Indicate if the tab contains any data. This is used to determine
        how the label should be displayed.
        """
        for role in self.sections:
            if not self.sections[role].is_empty():
                return False
        return True

    def populate_gui(self, event):
        """
        Populate the model.
        """
        for role in self.sections:
            self.sections[role].populate_gui(self.event)
        self._set_label()

    def save(self, trans):
        """
        Save the form to the database.
        """
        for role in self.sections:
            self.sections[role].save(trans)

#------------------------------------------------------------------------
#
# Multi Section
#
#------------------------------------------------------------------------
class MultiSection(Gtk.Box):

    SelectPerson = SelectorFactory('Person')

    def __init__(self, dbstate, uistate, track, event, citation, form_id,
                 section):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        self.dbstate = dbstate
        self.db = dbstate.db
        self.uistate = uistate
        self.track = track
        self.form_id = form_id
        self.section = section
        self.event = event
        self.citation = citation

        self.model = None
        self.columns = []
        self.initial_people = []

        self.role = EventRoleType()
        self.role.set_from_xml_str(section)

        hbox = Gtk.Box()
        hbox.set_spacing(6)

        title = get_section_title(form_id, section)
        if title:
            label = Gtk.Label(label='<b>%s</b>' % title)
            label.set_use_markup(True)
            label.set_halign(Gtk.Align.START)
            label.set_valign(Gtk.Align.CENTER)
            label.set_margin_left(6)
            hbox.pack_start(label, expand=False, fill=False, padding=0)

        image = Gtk.Image()
        image.set_from_icon_name('list-add', Gtk.IconSize.BUTTON)
        add_btn = Gtk.Button()
        add_btn.set_relief(Gtk.ReliefStyle.NONE)
        add_btn.add(image)
        add_btn.connect('clicked', self.__add_person)
        hbox.pack_start(add_btn, expand=False, fill=True, padding=0)

        image = Gtk.Image()
        image.set_from_icon_name('gtk-index', Gtk.IconSize.BUTTON)
        share_btn = Gtk.Button()
        share_btn.set_relief(Gtk.ReliefStyle.NONE)
        share_btn.add(image)
        share_btn.connect('clicked', self.__share_person)
        hbox.pack_start(share_btn, expand=False, fill=True, padding=0)

        image = Gtk.Image()
        image.set_from_icon_name('list-remove', Gtk.IconSize.BUTTON)
        del_btn = Gtk.Button()
        del_btn.set_relief(Gtk.ReliefStyle.NONE)
        del_btn.add(image)
        del_btn.connect('clicked', self.__remove_person)
        hbox.pack_start(del_btn, expand=False, fill=True, padding=0)

        image = Gtk.Image()
        image.set_from_icon_name('go-up', Gtk.IconSize.BUTTON)
        up_btn = Gtk.Button()
        up_btn.set_relief(Gtk.ReliefStyle.NONE)
        up_btn.add(image)
        up_btn.connect('clicked', self.__move_person, 'up')
        hbox.pack_start(up_btn, expand=False, fill=True, padding=0)

        image = Gtk.Image()
        image.set_from_icon_name('go-down', Gtk.IconSize.BUTTON)
        down_btn = Gtk.Button()
        down_btn.set_relief(Gtk.ReliefStyle.NONE)
        down_btn.add(image)
        down_btn.connect('clicked', self.__move_person, 'down')
        hbox.pack_start(down_btn, expand=False, fill=True, padding=0)

        self.entry_grid = EntryGrid(callback=self.change_person)

        self.pack_start(hbox, expand=False, fill=True, padding=0)
        self.pack_start(self.entry_grid, expand=True, fill=True, padding=0)

        self.create_table()

    def is_empty(self):
        """
        Indicate if the tab contains any data. This is used to determine
        how the label should be displayed.
        """
        if self.model is None:
            return True
        return len(self.model) == 0

    def __add_person(self, button):
        """
        Create a new person and add them to the form.
        """
        person = Person()
        EditPerson(self.dbstate, self.uistate, self.track, person,
                   self.__person_added)

    def __person_added(self, person):
        """
        Called when a person is added to the form.
        """
        self.model.append(self.__new_person_row(person))

    def __edit_person(self, treeview, path, view_column):
        """
        Edit a person from selection.
        """
        model, iter_ = self.selection.get_selected()
        if iter_:
            handle = model.get_value(iter_, 0)
            if handle:
                person = self.dbstate.db.get_person_from_handle(handle)
                EditPerson(self.dbstate, self.uistate, self.track, person)

    def __share_person(self, button):
        """
        Select an existing person and add them to the form.
        """
        handle = None
        if len(self.model) > 0:
            iter_ = self.entry_grid.get_selected()
            if iter_: # get from selection:
                handle = self.model.get_value(iter_, 0)
            else: # get from first row
                handle = self.model[0][0]
        else: # no rows, let's try to get active person:
            handle = self.uistate.get_active('Person')

        sel = self.SelectPerson(self.dbstate, self.uistate, self.track,
                                _("Select Person"), default=handle)
        person = sel.run()
        if person:
            self.model.append(self.__new_person_row(person))

    def change_person(self, model, iter_):
        """
        Change an existing person in the form.
        """
        skip_list = []
        handle = self.model.get_value(iter_, 0)

        sel = self.SelectPerson(self.dbstate, self.uistate, self.track,
                   _("Select Person"), skip=skip_list, default=handle)
        person = sel.run()

        if person:
            self.model.set_value(iter_, 0, person.get_handle())

    def __new_person_row(self, person):
        """
        Create a new model entry for a person.
        """
        row = [None] * (len(self.columns) + 1)
        row[0] = person.handle

        # Insert name in column called "Name", if present
        if _('Name') in self.columns:
            name = name_displayer.display(person)
            row[self.columns.index(_('Name')) + 1] = name

        return row

    def __remove_person(self, button):
        """
        Remove a person from the form.
        """
        iter_ = self.entry_grid.get_selected()
        if iter_:
            self.model.remove(iter_)

    def __move_person(self, button, direction):
        """
        Change the position of a person in the list.
        """
        iter_ = self.entry_grid.get_selected()
        if iter_ is None:
            return

        row = self.model.get_path(iter_)[0]
        if direction == 'up' and row > 0:
            self.model.move_before(iter_, self.model.get_iter((row - 1,)))

        if direction == 'down' and row < len(self.model) - 1:
            self.model.move_after(iter_, self.model.get_iter((row + 1,)))

    def create_table(self):
        """
        Create a model and treeview for the form details.
        """
        columns = get_section_columns(self.form_id, self.section)

        self.columns = [column[0] for column in columns]
        self.model = Gtk.ListStore(*[str] * (len(columns) + 1))
        self.entry_grid.set_model(self.model)
        tooltips = [column[1] for column in columns]
        self.entry_grid.set_columns(self.columns, tooltips)
        self.entry_grid.build()

    def populate_gui(self, event):
        """
        Populate the model.
        """
        person_list = []
        for item in self.db.find_backlink_handles(event.get_handle(),
                             include_classes=['Person']):
            handle = item[1]
            person = self.db.get_person_from_handle(handle)
            for event_ref in person.get_event_ref_list():
                if (event_ref.ref == event.get_handle() and
                    event_ref.get_role() == self.role):
                    self.initial_people.append(handle)
                    attrs = {}
                    order = 0
                    for attr in event_ref.get_attribute_list():
                        attr_type = str(attr.get_type())
                        if attr_type == ORDER_ATTR:
                            order = int(attr.get_value())
                        else:
                            attrs[attr_type] = attr.get_value()
                    name = name_displayer.display(person)
                    person_list.append([order, handle, name, attrs])

        person_list.sort()

        for person_data in person_list:
            row = person_data[1:2] # handle
            for attr in self.columns:
                if attr == _('Name'):
                    row.append(person_data[3].get(attr, person_data[2]))
                else:
                    row.append(person_data[3].get(attr))
            self.model.append(tuple(row))

    def save(self, trans):
        """
        Save the form details to the database.
        """
        # Update people on the form
        all_people = []
        for order, row in enumerate(self.model):
            all_people.append(row[0])
            person = self.db.get_person_from_handle(row[0])
            event_ref = get_event_ref(self.event, person, self.role)

            # Write attributes
            set_attribute(self.citation, event_ref, ORDER_ATTR, str(order + 1))
            for offset, name in enumerate(self.columns):
                value = row[offset + 1]
                set_attribute(self.citation, event_ref, name, value)
            self.db.commit_person(person, trans)

        # Remove links to people no longer on form
        for handle in (set(self.initial_people) - set(all_people)):
            person = self.db.get_person_from_handle(handle)
            ref_list = [event_ref for event_ref in person.get_event_ref_list()
                                if event_ref.ref != self.event.handle]
            person.set_event_ref_list(ref_list)
            self.db.commit_person(person, trans)

#------------------------------------------------------------------------
#
# Person Section
#
#------------------------------------------------------------------------
class PersonSection(Gtk.Box):

    InstCounter = 0

    def __IncreaseInstCounter(self):
        #type(self).InstCounter += 1
        self.InstCounter += 1
        _LOG.debug("### CONSTRUCTOR ### self.InstCounter +1 = %d", self.InstCounter)

    def __DecreaseInstCounter(self):
        #type(self).InstCounter -= 1
        self.InstCounter -= 1
        _LOG.debug("### DESTRUCTOR ### self.InstCounter -1 = %d", self.InstCounter)

    def __del__(self):
        self.__DecreaseInstCounter()


    SelectPerson = SelectorFactory('Person')


    def __PersonAddedCommon(self, PersonHandle):
        self.handle = PersonHandle

        #Person added to the form (get their name from their handle)
        person = self.db.get_person_from_handle(self.handle)
        name   = name_displayer.display(person)

        #Log message
        SelRole = self.widgets['PersonRole']
        _LOG.debug("PERSON ADDED: [%s]: %s" % (SelRole.get_text(), name))

        #Update the correct section (so user can see name)
        SelText = self.widgets['PersonName']
        SelText.set_markup("[<b><small>%s</small></b>]" % name)


        for heading in self.headings:
            self.widgets[heading].set_sensitive(True)
            if heading == _('Name'):
               self.widgets[heading].set_text(name)

    def _PersonDefaultSet(self, PersonHandle):         #PersonSelection class
        self.__PersonAddedCommon(PersonHandle)


    def __init__(self, dbstate, uistate, track, event, citation, form_id,
                 section):
        self.__IncreaseInstCounter()

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        self.dbstate = dbstate
        self.db = dbstate.db
        self.uistate = uistate
        self.track = track
        self.form_id = form_id
        self.section = section
        self.event = event
        self.citation = citation
        self.handle = None
        self.widgets = {}
        self.initial_handle = None

        self.role = EventRoleType()
        self.role.set_from_xml_str(section)

        hbox = Gtk.Box()

        title = get_section_title(form_id, section)
        label = Gtk.Label(label='<b>%s</b>' % title)
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.CENTER)
        self.widgets['PersonRole'] = label
        hbox.pack_start(label, expand=False, fill=False, padding=3)

        PersonName =_("no one selected yet")
        label = Gtk.Label(label='<i>%s</i>' % PersonName)
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.CENTER)
        self.widgets['PersonName'] = label
        hbox.pack_start(label, expand=False, fill=False, padding=10)

        image = Gtk.Image()
        image.set_from_icon_name('list-add', Gtk.IconSize.BUTTON)
        add_btn = Gtk.Button()
        add_btn.set_relief(Gtk.ReliefStyle.NONE)
        add_btn.add(image)
        add_btn.connect('clicked', self.__add_clicked)
        hbox.pack_start(add_btn, expand=False, fill=False, padding=3)

        image = Gtk.Image()
        image.set_from_icon_name('gtk-index', Gtk.IconSize.BUTTON)
        share_btn = Gtk.Button()
        share_btn.set_relief(Gtk.ReliefStyle.NONE)
        share_btn.add(image)
        share_btn.connect('clicked', self.__share_clicked)
        hbox.pack_start(share_btn, expand=False, fill=False, padding=3)

        #Not sure why but after my change the whole thing is being vertically centered in the page (DB$)
        self.pack_start(hbox, False, False, 0)
        self.grid = Gtk.Grid()
        self.pack_start(self.grid, False, False, 0)
        self.show()

        # Add this person's columns/questions
        self.set_columns()

        # Get selected person - NEED TO DO THIS ONE TIME ONLY (as we can only pick up one and in any case the selection order is meaningless
        _LOG.debug("DEFAULT THE PERSON? [IFF %d == 1]" % self.InstCounter)
        if  self.InstCounter == 1:
            handle = self.uistate.get_active('Person')
            self._PersonDefaultSet(handle)


    def is_empty(self):
        return False if self.handle else True

    def set_columns(self):
        """
            [PersonSection class]
            Adds a person (section) columns to the UI, the questions
            will take up as many lines as required.
        """
        columns = get_section_columns(self.form_id, self.section)
        self.headings = [column[0] for column in columns]
        self.tooltips = [column[1] for column in columns]

        # The person's controls go into a flowbox
        fbox = Gtk.FlowBox(
                            orientation=Gtk.Orientation.HORIZONTAL,
                            min_children_per_line=2,   #If I set to 2 then I can set expand to False (and have all controls on top (not centered!)
                            expand=False               #If not True (and min col=1), they get drawn vertically!!!!!!
                          )
        fbox.set_valign(Gtk.Align.START)
        for col, heading in enumerate(self.headings):
            # Each label/entry pair placed into its own vbox
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            fbox.add(vbox)

            label = Gtk.Label(label=heading)
            label.set_halign(Gtk.Align.START)
            label.set_valign(Gtk.Align.CENTER)
            label.show()

            entry = MyEntry(heading)
            entry.set_tooltip_text(self.tooltips[col])
            entry.set_sensitive(False)
            self.widgets[heading] = entry
            entry.show()

            vbox.pack_start(label, expand=False, fill=True, padding=2)
            vbox.pack_start(entry, expand=True,  fill=True, padding=2)

        # Attach the fbox to scrolling window and it to the grid
        self.grid.attach(fbox, 0, 0, 1, 1)


    def __add_clicked(self, obj):
        person = Person()
        EditPerson(self.dbstate, self.uistate, self.track, person,
                   self.__added)

    def __share_clicked(self, obj):
        handle = self.uistate.get_active('Person')
        sel = self.SelectPerson(self.dbstate, self.uistate, self.track,
                                _("Select Person"), default=handle)
        obj = sel.run()
        if obj:
            self.__added(obj)

    def __added(self, obj):         #PersonSelection class
        self.__PersonAddedCommon(obj.handle)

    def populate_gui(self, event):
        for item in self.db.find_backlink_handles(event.get_handle(),
                             include_classes=['Person']):
            handle = item[1]
            obj = self.db.get_person_from_handle(item[1])

            for event_ref in obj.get_event_ref_list():
                if (event_ref.ref == self.event.get_handle() and
                    event_ref.get_role() == self.role):

                    attrs = {}
                    for attr in event_ref.get_attribute_list():
                        attr_type = str(attr.get_type())
                        attrs[attr_type] = attr.get_value()

                    self.__populate(obj, attrs)


    def __populate(self, obj, attrs):
        self.initial_handle = obj.handle
        self.__added(obj)
        for heading in self.headings:
            self.widgets[heading].set_text(attrs.get(heading, ''))

    def save(self, trans):
        if not self.handle:
            FormDlgInfo(_("ABORTING SAVE"), _("No person selected"))
            return

        obj = self.dbstate.db.get_person_from_handle(self.handle)
        event_ref = get_event_ref(self.event, obj, self.role)

        row = []
        for heading in self.headings:
            row.append(self.widgets[heading].get_text())
        write_attributes(self.citation, row, event_ref, self.headings)
        self.dbstate.db.commit_person(obj, trans)

        # Remove link to person no longer on form
        if self.initial_handle and self.handle != self.initial_handle:
            person = self.db.get_person_from_handle(self.initial_handle)
            ref_list = [event_ref for event_ref in obj.get_event_ref_list()
                                if event_ref.ref != self.event.handle]
            person.set_event_ref_list(ref_list)
            self.db.commit_person(person, trans)


#------------------------------------------------------------------------
#
# Family Section
#
#------------------------------------------------------------------------
class FamilySection(Gtk.Box):

    SelectFamily = SelectorFactory('Family')

    def __init__(self, dbstate, uistate, track, event, citation, form_id,
                 section):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        self.dbstate = dbstate
        self.db = dbstate.db
        self.uistate = uistate
        self.track = track
        self.form_id = form_id
        self.section = section
        self.event = event
        self.citation = citation
        self.handle = None
        self.widgets = {}
        self.widgets2 = {}
        self.initial_handle = None

        self.role = EventRoleType()
        self.role.set_from_xml_str(section)

        hbox = Gtk.Box()

        title = get_section_title(form_id, section)
        title1, title2 = title.split('/')

        label = Gtk.Label(label='<b>%s</b>' % title1)
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.CENTER)
        hbox.pack_start(label, expand=False, fill=False, padding=3)

        image = Gtk.Image()
        image.set_from_icon_name('list-add', Gtk.IconSize.BUTTON)
        add_btn = Gtk.Button()
        add_btn.set_relief(Gtk.ReliefStyle.NONE)
        add_btn.add(image)
        add_btn.connect('clicked', self.__add_clicked)
        hbox.pack_start(add_btn, expand=False, fill=False, padding=3)

        image = Gtk.Image()
        image.set_from_icon_name('gtk-index', Gtk.IconSize.BUTTON)
        share_btn = Gtk.Button()
        share_btn.set_relief(Gtk.ReliefStyle.NONE)
        share_btn.add(image)
        share_btn.connect('clicked', self.__share_clicked)
        hbox.pack_start(share_btn, expand=False, fill=False, padding=3)

        self.pack_start(hbox, False, False, 0)
        self.grid = Gtk.Grid()
        self.pack_start(self.grid, False, False, 0)

        label = Gtk.Label(label='<b>%s</b>' % title2)
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.CENTER)
        self.pack_start(label, expand=False, fill=False, padding=3)

        self.grid2 = Gtk.Grid()
        self.pack_start(self.grid2, False, False, 0)
        self.show()

        columns = get_section_columns(self.form_id, self.section)
        self.headings = [column[0] for column in columns]
        self.tooltips = [column[1] for column in columns]

        self.set_columns(self.widgets, self.grid)
        self.set_columns(self.widgets2, self.grid2)

    def is_empty(self):
        return False if self.handle else True

    def set_columns(self, widgets, grid):
        for col, heading in enumerate(self.headings):
            label = Gtk.Label(label=heading)
            label.set_halign(Gtk.Align.START)
            label.set_valign(Gtk.Align.CENTER)
            label.show()
            entry = MyEntry(heading)
            entry.set_tooltip_text(self.tooltips[col])
            entry.set_sensitive(False)
            widgets[heading] = entry
            entry.show()
            grid.attach(label, col, 0, 1, 1)
            grid.attach(entry, col, 1, 1, 1)

    def __add_clicked(self, obj):
        family = Family()
        EditFamily(self.dbstate, self.uistate, self.track, family,
                   self.__added)

    def __share_clicked(self, obj):
        handle = self.uistate.get_active('Family')
        sel = self.SelectFamily(self.dbstate, self.uistate, self.track,
                                default=handle)
        obj = sel.run()
        if obj:
            self.__added(obj)

    def __added(self, obj):
        self.handle = obj.handle
        for heading in self.headings:
            self.widgets[heading].set_sensitive(True)
            self.widgets2[heading].set_sensitive(True)
            if heading == _('Name'):
                family = self.db.get_family_from_handle(self.handle)
                father_handle = family.get_father_handle()
                if father_handle:
                    person = self.db.get_person_from_handle(father_handle)
                    name = name_displayer.display(person)
                    self.widgets[heading].set_text(name)
                mother_handle = family.get_mother_handle()
                if mother_handle:
                    person = self.db.get_person_from_handle(mother_handle)
                    name = name_displayer.display(person)
                    self.widgets2[heading].set_text(name)

    def populate_gui(self, event):
        for item in self.db.find_backlink_handles(event.get_handle(),
                             include_classes=['Family']):
            handle = item[1]
            obj = self.db.get_family_from_handle(item[1])

            for event_ref in obj.get_event_ref_list():
                if (event_ref.ref == self.event.get_handle() and
                    event_ref.get_role() == self.role):

                    attrs = {}
                    for attr in event_ref.get_attribute_list():
                        attr_type = str(attr.get_type())
                        attrs[attr_type] = attr.get_value()

                    self.__populate(obj, attrs)

    def __populate(self, obj, attrs):
        self.initial_handle = obj.handle
        self.__added(obj)
        for heading in self.headings:
            self.widgets[heading].set_text(attrs.get(GROOM + ' ' + heading, ''))
            self.widgets2[heading].set_text(attrs.get(BRIDE + ' ' + heading, ''))

    def save(self, trans):
        if not self.handle:
            return

        obj = self.dbstate.db.get_family_from_handle(self.handle)
        event_ref = get_event_ref(self.event, obj, self.role)

        row = []
        for heading in self.headings:
            row.append(self.widgets[heading].get_text())
        write_attributes(self.citation, row, event_ref, self.headings,
                         prefix=GROOM)
        row = []
        for heading in self.headings:
            row.append(self.widgets2[heading].get_text())
        write_attributes(self.citation, row, event_ref, self.headings,
                         prefix=BRIDE)
        self.dbstate.db.commit_family(obj, trans)

        # Remove link to family no longer on form
        if self.initial_handle and self.handle != self.initial_handle:
            family = self.db.get_family_from_handle(self.initial_handle)
            ref_list = [event_ref for event_ref in obj.get_event_ref_list()
                                if event_ref.ref != self.event.handle]
            family.set_event_ref_list(ref_list)
            self.db.commit_family(family, trans)


class MyEntry(Gtk.Entry):
    """
    A Gtk type Entry that resizes based on content
    """
    def __init__(self, labeltxt):
        Gtk.Entry.__init__(self)
        self.set_width_chars(len(labeltxt))
        self.connect('changed', self._changed)

    def _changed(self, entry):
        layout = entry.get_layout()
        width, height = layout.get_pixel_size()
        entry.set_size_request(width + 18, -1)

#------------------------------------------------------------------------
#
# Helper functions
#
#------------------------------------------------------------------------
def get_event_ref(event, obj, role):
    """
    Return the event reference for a given person or family that points
    to the event being edited.
    """
    for event_ref in obj.get_event_ref_list():
        if (event_ref.ref == event.get_handle() and
            event_ref.get_role() == role):
            return event_ref

    # Add new event reference
    event_ref = EventRef()
    event_ref.ref = event.get_handle()
    event_ref.set_role(role)
    obj.add_event_ref(event_ref)
    return event_ref

def write_attributes(citation, row, event_ref, columns, prefix=None):
    for offset, name in enumerate(columns):
        value = row[offset]
        if prefix is not None:
            name = '%s %s' % (prefix, name)
        set_attribute(citation, event_ref, name, value)

def get_attribute(attrs, name):
    """
    Return a named attribute from a list of attributes.  Return 'None' if
    the attribute is not in the list.
    """
    for attr in attrs:
        if attr.get_type() == name:
            return attr
    return None

def set_attribute(citation, event_ref, name, value):
    """
    Set a named attribute to a given value.  Create the attribute if it
    does not already exist.  Delete it if the value is None or ''.
    """
    attrs = event_ref.get_attribute_list()
    attr = get_attribute(attrs, name)
    if attr is None:
        if value:
            # Add
            attr = Attribute()
            attr.set_type(name)
            attr.set_value(value)
            attr.add_citation(citation.handle)
            if name == ORDER_ATTR:
                attr.set_privacy(True)
            event_ref.add_attribute(attr)
    else:
        if not value:
            # Remove
            event_ref.remove_attribute(attr)
        elif attr.get_value() != value:
            # Update
            attr.set_value(value)

def find_form_event(db, citation):
    """
    Given a citation for a form source, find the corresponding event.
    """
    handle = citation.get_reference_handle()
    source = db.get_source_from_handle(handle)
    form_type = get_form_type(get_form_id(source))

    for item in db.find_backlink_handles(citation.handle, ['Event']):
        event = db.get_event_from_handle(item[1])
        if event.get_type().xml_str() == form_type:
            return event

    return Event()
