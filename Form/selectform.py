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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA.
#

"""
Form selector.
"""


# ---------------------------------------------------------------
# Python imports
# ---------------------------------------------------------------
import os
import logging

# ---------------------------------------------------------------
# GTK modules
# ---------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango

# ---------------------------------------------------------------
# Gramps modules
# ---------------------------------------------------------------
from form import get_form_ids, get_form_id, get_form_type
from form import get_form_title, get_form_date
from form import DEFINITION_KEY
from gramps.gui.display import display_help
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from formtools import (dlginfo, sound_bell, inigeti, inigetb)
# from dbg_tools import dbg_dobj


# ---------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# ---------------------------------------------------------------
# Logging
# ---------------------------------------------------------------
_LOG = logging.getLogger("Form Gramplet")

# ---------------------------------------------------------------
# INI CONFIG
# ---------------------------------------------------------------
CONFIG = config.register_manager('form')
CONFIG.init()
CONFIG.load()


def _start_interactive_search(device):
    """
    Interactive search has started, logs a message saying so.
    """
    # pylint: disable=unused-argument
    _LOG.debug('interactive search started (CTRL+F or typing)')


# ---------------------------------------------------------------
# SelectForm class
# ---------------------------------------------------------------
class SelectForm(object):
    """
    Form Selector.
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=useless-object-inheritance


    # -----------------------------------------------------------------
    # Constants
    # -----------------------------------------------------------------
    COL_HANDLE = 0               # Source Handle or None if tree node
    COL_TEXT = 1                 # Text to be displayed
    COL_WEIGHT = 2               # Column that stores the font weight
    COL_VISIBLE = 3              # Controls if a row should be visible
    RESPONSE_CANCEL_FILTER = 99  # Reset filter button
    RESPONSE_COLLAPSE_TREE = 88  # Collapse all tree nodes
    EXPAND_BY_DEFAULT = True     # Expand tree node on match

    # -----------------------------------------------------------------
    # Form Country codes (ID=DK1870: DK = Denmark
    # -----------------------------------------------------------------
    _FORM_CC = {
        'DK':   'Denmark',
        'BE':   'Belgian',
        'CA':   'Canada',
        'CY':   'Wales',
        'FR':   'French',
        'IE':   'Ireland',
        'UK':   'England (sometimes includes Wales)',
        'USCO': 'United States/Colorado',
        'USFL': 'United States/Florida',
        'USIA': 'United States/Iowa',
        'USKS': 'United States/Kansas',
        'USMN': 'United States/Minnesota',
        'USMO': 'United States/Missouri',
        'USNC': 'United States/North Carolina',
        'USNE': 'United States/Nebraska',
        'USNY': 'United States/New York State',
        'USSD': 'United States/Dakota, South',
        'USND': 'United States/Dakota, North',
        'USWI': 'United States/Wisconsin',
        'USIL': 'United States/Illinois',
        'US':   'United States'
    }

    # -----------------------------------------------------------------
    # Sundry class variables
    # -----------------------------------------------------------------
    expand_subtree = True    # Needs more work use 'False'
    hover_expand = inigetb(CONFIG, 'selectform.hover-expand', False)

    def __init__(self, dbstate, uistate, track):
        # pylint: disable=unused-argument

        self.dbstate = dbstate
        self.uistate = uistate
        self.search_matches = 0
        self.search_filter_text = ''
        self.top = self._create_dialog()

    def _create_dialog(self):
        """
        Create a dialog box to select a form.
        """
        # pylint: disable-msg=E1101
        # pylint: disable=logging-not-lazy
        # pylint: disable=too-many-statements
        # pylint: disable=too-many-locals

        title = _("%(title)s - Gramps") % {'title': _("Select Form")}
        _LOG.debug('Select Form Dialog: %s' % title)
        top = Gtk.Dialog(title)
        dwidth = inigeti(CONFIG, 'selectform.form-width', 350)
        dheight = inigeti(CONFIG, 'selectform.form-height', 650)
        posx = inigeti(CONFIG, 'selectform.form-horiz-position', -1)
        posy = inigeti(CONFIG, 'selectform.form-vert-position', -1)
        _LOG.debug('Setting the default size & position of the dialog'
                   ' (W=%s, H=%s @ X=%s, Y=%s)',
                   dwidth, dheight, posx, posy)
        top.set_default_size(dwidth, dheight)
        top.resize(dwidth, dheight)
        if  posx != -1 and posy != -1:
            top.move(posx, posy)
        top.set_modal(True)
        top.set_transient_for(self.uistate.window)
        top.vbox.set_spacing(5)
        txt = '<span size="larger" weight="bold">%s</span>'
        label = Gtk.Label(label=txt % _("Select Form"))
        label.set_use_markup(True)
        top.vbox.pack_start(label, 0, 0, 5)
        box = Gtk.Box()
        top.vbox.pack_start(box, 1, 1, 5)

        # Define the model columns
        self.model = Gtk.TreeStore(str, str, Pango.Weight, bool)

        # Set up search
        self.search_filter_text = ""
        self.tree_filter = self.model.filter_new()
        self.tree_filter.set_visible_column(self.COL_VISIBLE)

        # Create Tree View
        self.tree = Gtk.TreeView(self.tree_filter)
        self.tree.connect('button-press-event', self.__button_press)

        # Pack everything into a single column (otherwise only the first
        # column would be indented according to its depth in the tree)
        text_renderer = Gtk.CellRendererText()
        ccol = Gtk.TreeViewColumn("Source")
        ccol.pack_start(text_renderer, True)
        ccol.add_attribute(text_renderer, "text", self.COL_TEXT)
        ccol.add_attribute(text_renderer, "weight", self.COL_WEIGHT)
        ccol.add_attribute(text_renderer, "visible", self.COL_VISIBLE)
        ccol.set_sort_column_id(1)
        self.tree.append_column(ccol)

        # CTRL+F used to fail, it now works
        self.tree.set_search_column(1)
        self.tree.set_hover_expand(self.hover_expand)
        self.tree.connect('start-interactive-search',
                          _start_interactive_search)
        self.tree.set_search_equal_func(self._search_equal_function)

        # This window will have scroll bars and buttons
        slist = Gtk.ScrolledWindow()
        slist.add(self.tree)
        slist.set_policy(Gtk.PolicyType.AUTOMATIC,
                         Gtk.PolicyType.AUTOMATIC)
        box.pack_start(slist, 1, 1, 5)
        help_button = top.add_button(_('_Help'), Gtk.ResponseType.HELP)
        reset_button = top.add_button(_('_Reset'),
                                      self.RESPONSE_CANCEL_FILTER)
        # How to pack RESET left like the help button?
        compact_button = top.add_button(_('_Compact'),
                                        self.RESPONSE_COLLAPSE_TREE)
        top.add_button(_('_Cancel'), Gtk.ResponseType.CANCEL)
        top.add_button(_('_OK'), Gtk.ResponseType.OK)
        top.show_all()

        # Help tooltip and stop buttons stealing focus
        st1 = _('You can start typing (or press CTRL+F (find) to ' +
                ' apply a filter to the results.')
        st2 = _("Any row that doesn't match is dropped and all" +
                ' matches are highlighted (case insensitive).')
        st3 = _('Matches occur if the text (in the tree or a source)' +
                ' CONTAINS the search text you typed.')
        st4 = _('This button resets any filter you may have applied' +
                ' and fully expands the tree.')
        reset_button.set_tooltip_text(
                        st1 + "  " + st2 + "  " + st3 + "\n\n" + st4)
        st1 = _('This collapses the tree and allows you to expand it' +
                ' as required yourself')
        compact_button.set_tooltip_text(st1)
        st1 = _('This opens help for the plugin (how to use it &' +
                ' how to create new forms)')
        help_button.set_tooltip_text(st1)
        reset_button.set_can_focus(False)
        compact_button.set_can_focus(False)
        help_button.set_can_focus(False)
        return top

    def _get_parent_for_tree(self, form_types, tree):
        """
            Any part of the tree we create needs to be added to the
            array passed as the first parameter
        """
        # pylint: disable=invalid-name disable=consider-using-enumerate

        if tree == "":
            tree = "??"
        tree_dirs = tree.split("/")
        this_tree = ''
        parent = None
        for ti in range(len(tree_dirs)):
            # Rebuild path for the current level
            tree_dirs_sn = tree_dirs[ti]
            if tree_dirs_sn == '':
                continue    # Ignore empty paths
            if this_tree != "":
                this_tree = this_tree + "/"
            this_tree = this_tree + tree_dirs_sn

            # get existing parent or create new
            if _(this_tree) in form_types:
                handle = form_types[_(this_tree)]
            else:
                handle = self.model.append(parent,
                                           (None, _(tree_dirs_sn),
                                            Pango.Weight.NORMAL, True))
                form_types[_(this_tree)] = handle
            parent = handle
        return parent

    def _get_tpath_fxml(self, form_id, backup_title):
        """
        Form id looks like "UK1861" if legacy method used, that is
        the first 2 characters represent the country.

        [2020-05-19]
        If the form xml title is missing (or empty) then
        "backup_title" (from source) is used.

        If the title begins with "/" it is now used to display in
        the select form dialog (currently unused).
        The path and text builts the tree nodes as well as the
        selectable items. If you don't want a path but you want
        to start with "/", put a space before it.

        If it doesn't begin with a slash (no existing entries do)
        then they are displayed as "census/uk" (type + first 2 chars
        of form_id or converted to contry name where known).

        RETURNS:
            [1] tree_path: "Census/UK"
            [2] tree_desc: "1841 England and Wales Census"
        """

        # get some values from the form XML
        form_title = get_form_title(form_id)  # 1871 England Census
        form_type = get_form_type(form_id)    # Census/Death etc
        form_date = get_form_date(form_id)    # Date as in the form
        if not form_title or form_title == '':
            form_title = backup_title
        if not form_date:
            form_date = ''

        # replace optional place markers ('{s}' needs to be done later)
        form_title = form_title.replace('{type}', form_type)
        form_title = form_title.replace('{date}', str(form_date))
        form_title = form_title.replace('{id}', form_id)

        # Path attached or legacy method to be used?
        if form_title[:1] == "/":
            # Tree specified in detail, split path from description
            tree_path = os.path.dirname(form_title)
            tree_desc = os.path.basename(form_title)

            # Used if user MUST have slashes in the desc (in URL etc)
            tree_desc = tree_desc.replace('{s}', '/')
        else:
            # Legacyish way (legacy + minor improvements)
            cc2 = form_id[:2]
            if cc2 == "US":
                cc4 = form_id[:4]
            else:
                cc4 = None
            try:
                country_name = self._FORM_CC[cc4]
            except KeyError:
                try:
                    country_name = self._FORM_CC[cc2]
                except KeyError:
                    country_name = cc2   # Fall back to the code
            tree_path = form_type + "/" + country_name  # "Census/UK"

            # User may have preceeded title with a space to get here!
            tree_desc = form_title.strip()
        return(tree_path, tree_desc)

    def reset_row(self, model, path, titer, font_weight, make_visible):
        """
            Reset some row attributes independent of row hierarchy:
            https://stackoverflow.com/questions/56029759/how-to-filter-a-gtk-tree-view-that-uses-a-treestore-and-not-a-liststore
        """
        # pylint: disable=unused-argument disable=too-many-arguments
        model.set_value(titer, self.COL_WEIGHT, font_weight)
        model.set_value(titer, self.COL_VISIBLE, make_visible)

    def make_path_visible(self, model, titer):
        """
            Make a row and its ancestors visible:
            https://stackoverflow.com/questions/56029759/how-to-filter-a-gtk-tree-view-that-uses-a-treestore-and-not-a-liststore
        """
        while titer:
            model.set_value(titer, self.COL_VISIBLE, True)
            titer = model.iter_parent(titer)

    def make_subtree_visible(self, model, titer):
        """
            Make descendants of a row visible:
            https://stackoverflow.com/questions/56029759/how-to-filter-a-gtk-tree-view-that-uses-a-treestore-and-not-a-liststore
        """
        for i in range(model.iter_n_children(titer)):
            subtree = model.iter_nth_child(titer, i)
            if model.get_value(subtree, self.COL_VISIBLE):
                # Subtree already visible
                continue
            model.set_value(subtree, self.COL_VISIBLE, True)
            self.make_subtree_visible(model, subtree)

    def show_matches(self, model, path, titer, search_query, smsubtrees):
        """
            All items currently not visible and have 'normal' font,
            will make matches visible and bold
            https://stackoverflow.com/questions/56029759/how-to-filter-a-gtk-tree-view-that-uses-a-treestore-and-not-a-liststore
        """
        # pylint: disable=unused-argument disable=too-many-arguments
        text = model.get_value(titer, self.COL_TEXT).lower()
        if search_query in text:
            # Keep count
            self.search_matches += 1

            # Highlight direct match with bold
            model.set_value(titer, self.COL_WEIGHT,
                            Pango.Weight.HEAVY)

            # Propagate visibility change up
            self.make_path_visible(model, titer)
            if smsubtrees:
                # Propagate visibility change down
                self.make_subtree_visible(model, titer)

    def _tell_user_if_no_forms_exist(self, form_types, src_attrs):
        """ Displays a dialog message if no forms matches found """
        # pylint: disable=logging-not-lazy

        if len(form_types) != 0:
            _LOG.debug('%d x GRAMPS SOURCE ID\'s' +
                       ' (in the "%s" attribute): %s',
                       len(src_attrs), str(DEFINITION_KEY),
                       str(src_attrs))
        else:
            # ERROR so find all form 'id' attributes from XML
            form_attrs = []
            for form_id in get_form_ids():
                form_attrs.append(form_id)

            # Report the issue
            txt = _("There were no Gramp's sources with a attribute of" +
                    ' "%s" that matched any form\'s "id" ' +
                    ' (loaded from XML).')
            dlginfo(
                'NO FORM & SOURCE MATCHES FOUND',
                (txt % DEFINITION_KEY) +
                '\n\n' +
                _("%s x IDs in Gramp's Sources") % len(src_attrs) +
                "\n" + '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~' + "\n" +
                str(src_attrs) +
                '\n\n' +
                _('%s x IDs from xml form files') % len(form_attrs) +
                '\n' +
                '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~' + "\n" +
                str(form_attrs))

    def _populate_model(self):
        """
        Populate the model.
        """
        # pylint: disable=logging-not-lazy

        self.model.clear()
        form_types = {}
        src_attrs = []
        for handle in self.dbstate.db.get_source_handles():
            source = self.dbstate.db.get_source_from_handle(handle)
            form_id = get_form_id(source)
            if form_id:
                src_attrs.append(form_id)
            if form_id in get_form_ids():
                # Get a tree node handle
                (tree_path, tree_desc) = self._get_tpath_fxml(
                    form_id, source.title)
                _LOG.debug('[TREE] PATH = "%s", DESC="%s"',
                           tree_path, tree_desc)

                # Get a parent/dir node handle to add the desc to
                parent = self._get_parent_for_tree(form_types,
                                                   tree_path)

                # Add the source to the node of the tree
                self.model.append(parent,
                                  (source.handle, tree_desc,
                                   Pango.Weight.NORMAL, True))
        self.model.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self.tree.expand_all()
        self._tell_user_if_no_forms_exist(form_types, src_attrs)

    def _filter_tree_view_for_text(self, query_text=''):
        """
            We make use of the CTRL+F interactive search only for
            it's entry field, the rest of the functionality has
            been replaced.

            This function performs all the filtering logic given
            query text.  The comparison used is "contains" on
            case insensitive value.
        """
        # pylint: disable=logging-not-lazy

        # query contains "reset character '*'?, if so at end?
        lci = query_text.rfind("*")
        if  lci != -1:
            _LOG.debug('Filter RESET ("*") found in: "%s"' % query_text)
            query_text = query_text[lci+1:]

        # Filter tree, keep count of matches
        if query_text == '':
            # Show all
            _LOG.debug('Resetting the filter (now viewing all)')
            self.search_matches = -1
            self.model.foreach(self.reset_row, Pango.Weight.NORMAL,
                               True)
        else:
            _LOG.debug('Filtering using "%s"', query_text)
            self.search_matches = 0
            self.model.foreach(self.reset_row,
                               Pango.Weight.NORMAL,  # LIGHT = too pale
                               False)
            self.model.foreach(self.show_matches,
                               query_text, self.expand_subtree)
            _LOG.debug('Searched for "%s" and found %s matches' +
                       '(expand nodes=%s)', query_text,
                       self.search_matches, self.expand_subtree)
        self.tree.expand_all()
        self.tree_filter.refilter()
        self.search_filter_text = ''
        # return the match count
        return self.search_matches

    def _search_equal_function(self, model, column, query, rowiter):
        """
            CTRL+F interactive search calls this when a key is pressed.
            The query string is all we use.
            Unfortunately, It doesn't call this if the query
            text is empty!
        """
        # pylint: disable=unused-argument
        # pylint: disable=logging-not-lazy

        # Perform the search
        matches = self._filter_tree_view_for_text(query)

        # No matches?
        if matches == 0:
            sound_bell()
            _LOG.warning('No matches found, we need to show all as' +
                         ' search will fail until at least one row' +
                         ' visible or form reopened!')
            self._filter_tree_view_for_text()
        return False   # returned value doesn't seem to matter

    def __button_press(self, obj, event):
        """
        Called when a button press is executed
        """
        # pylint: disable=protected-access
        # pylint: disable=unused-argument

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
        # pylint: disable=logging-not-lazy

        try:
            self._populate_model()
            source_handle = None
            while True:
                # Get response
                response = self.top.run()

                # Save window details to ini file
                (dwidth, dheight) = self.top.get_size()
                (posx, posy) = self.top.get_position()
                _LOG.debug("Saving dialog's current size & position" +
                           ' (W=%s, H=%s @ X=%s, Y=%s)',
                           dwidth, dheight, posx, posy)
                CONFIG.set('selectform.form-width', dwidth)
                CONFIG.set('selectform.form-height', dheight)
                CONFIG.set('selectform.form-horiz-position', posx)
                CONFIG.set('selectform.form-vert-position', posy)
                CONFIG.save()

                # Process response
                if response == Gtk.ResponseType.HELP:
                    display_help(webpage='Form_Addons')
                    continue
                if response == self.RESPONSE_CANCEL_FILTER:
                    self._filter_tree_view_for_text()
                    continue
                if response == self.RESPONSE_COLLAPSE_TREE:
                    _LOG.debug('Collapse tree button clicked')
                    self.tree.collapse_all()
                    continue
                if response == Gtk.ResponseType.CANCEL:
                    self.top.destroy()
                    break
                if response == Gtk.ResponseType.OK:
                    model, iter_ = self.tree.get_selection().get_selected()
                    source_handle = None
                    if iter_:
                        source_handle = model.get_value(iter_, 0)
                    if not source_handle:
                        # No selection to accept (or was on tree node)
                        sound_bell()
                        continue
                    self.top.destroy()
                else:
                    _LOG.debug('The dialog returned a response' +
                               " code of %d (which we don't"
                               ' specifically handle)',
                               response)
                    self.top.destroy()      # safest option
                    break

                return source_handle
        except:
            # Prevents multiple exception loops & ensures dialog closes
            _LOG.debug("Exception detected, destroying dialog")
            self.top.destroy()
            raise Exception()
