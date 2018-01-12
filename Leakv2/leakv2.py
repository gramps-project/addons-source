#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2003-2006  Donald N. Allingham
# Copyright (C) 2008       Brian G. Matherly
# Copyright (C) 2010       Jakim Friant
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
Show uncollected objects in a window.
"""
#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
import sys
from types import FrameType
import gc
try:
    from bsddb3.db import DBError
except:
    class DBError(Exception):
        """
        Dummy.
        """
#------------------------------------------------------------------------
#
# GNOME/GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Gdk

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gui.dialog import InfoDialog
from gramps.gui.utils import is_right_click, ProgressMeter
from gramps.gui.utils import get_primary_mask
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext


#-------------------------------------------------------------------------
#
# Leak
#
#-------------------------------------------------------------------------
class Leakv2(Gramplet):
    """
    Shows uncollected objects.
    """
    def __init__(self, gui, nav_group=0):
        self.show_loops = False  # GUI option
        self.gc_enabled = False  # GUI option
        self.loop_ctr = 0  # a loop identifier
        # make pylint happy
        self.top = self.label = self.scroll = self.list = self.model = None
        self.renderer = self.selection = self.parent = self.junk = None
        self.id_index = self.ref_lst = self.loop_id = self.all = None
        Gramplet.__init__(self, gui, nav_group=0)

    def init(self):
        """ called by Gramplet """
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)

        flags = gc.DEBUG_UNCOLLECTABLE | gc.DEBUG_SAVEALL | gc.DEBUG_STATS
        if hasattr(gc, "DEBUG_OBJECTS"):
            flags = flags | gc.DEBUG_OBJECTS
        gc.set_debug(flags)

    def build_gui(self):
        """
        Build the GUI interface.
        """
        self.top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.top.set_border_width(6)

        bbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        self.label = Gtk.Label(halign=Gtk.Align.START)
        self.label.set_tooltip_text(
            _("While this Gramplet is installed, garbage collections will"
              " print statistics to the STDERR."))
        bbox.pack_start(self.label, False, False, 6)
        find_box = Gtk.Entry()
        find_box.connect('key-press-event', self.find_key_press)
        find_box.set_placeholder_text(_("Find Loop#"))
        find_box.set_tooltip_text(
            _("Find and show only a particular numbered loop."))
        bbox.pack_end(find_box, False, False, 6)
        self.top.pack_start(bbox, False, False, 6)

        self.scroll = Gtk.ScrolledWindow()
        # add a listview to the scrollable
        self.list = Gtk.TreeView()
        self.list.set_headers_visible(True)
        self.list.connect('button-press-event', self._button_press)
        self.scroll.add(self.list)
        # make a model
        self.model = Gtk.ListStore(int, str, str, str)
        self.list.set_model(self.model)

        # set the columns
        self.renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Number'), self.renderer, text=0)
        column.set_resizable(True)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.list.append_column(column)
        column = Gtk.TreeViewColumn(_('Referrer'), self.renderer, text=1)
        column.set_resizable(True)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.list.append_column(column)
        column = Gtk.TreeViewColumn(_('Loop#'), self.renderer, text=2)
        column.set_resizable(True)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.list.append_column(column)
        column = Gtk.TreeViewColumn(_('Uncollected object'), self.renderer,
                                    text=3)
        column.set_resizable(True)
        column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self.list.append_column(column)
        self.selection = self.list.get_selection()
        self.top.pack_start(self.scroll, True, True, 6)

        bbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        loops_check = Gtk.CheckButton(label=_('Only show objects in loops'))
        loops_check.set_tooltip_text(_("Show only those objects that are part"
                                       " of a reference cycle (loop)."))
        loops_check.connect('toggled', self.loops_toggled)
        bbox.pack_start(loops_check, False, False, 6)
        gc_check = Gtk.CheckButton(label=_('Normal Garbage collection'))
        gc_check.set_tooltip_text(_(
            "When checked, this shows the results after a normal gc collect.\n"
            "There should be few if any objects.\n"
            "When unchecked, unreachable objects that require the normal\n"
            "gc collect to clear are shown."))
        gc_check.connect('toggled', self.gc_toggled)
        bbox.pack_start(gc_check, False, False, 6)
        apply_button = Gtk.Button(label=_("Refresh"))
        apply_button.connect('clicked', self.apply_clicked)
        bbox.pack_start(apply_button, False, False, 6)
        self.top.pack_start(bbox, False, False, 6)

        self.top.show_all()

        return self.top

    def main(self):
        """ draw the main display """
        self.label.set_text(_('Press Refresh to see initial results'))
        self.model.clear()
        # self.display()    # We should only run this on demand

    def _button_press(self, obj, event):
        """ deal with clicks on a row """
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            self.referenced_in()
            return True
        elif is_right_click(event):
            self.refers_to()
            return True

    def loops_toggled(self, obj):
        """ deal with changes in Loops checkbox"""
        self.show_loops = obj.get_active()
        self.display()

    def gc_toggled(self, obj):
        """ deal with changes in normal gc checkbox"""
        gc_enabled = obj.get_active()
        if gc_enabled:
            gc.set_debug(gc.DEBUG_UNCOLLECTABLE | gc.DEBUG_STATS)
        else:
            gc.set_debug(gc.DEBUG_UNCOLLECTABLE | gc.DEBUG_SAVEALL |
                         gc.DEBUG_STATS)
        self.display()

    def find_key_press(self, obj, event):
        """deal with entry in find box"""
        if not event.get_state() & get_primary_mask():
            if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_Tab):
                loop_num = obj.get_text()
                obj.set_text('')
                self.list.grab_focus()
                if loop_num.isnumeric():
                    loop_num = int(loop_num)
                    if loop_num >= 0 and loop_num < self.loop_ctr:
                        self.show_found(loop_num)
                        return True
                self.display()
        return False

    def referenced_in(self):
        """ display full list of referrers """
        model, _iter = self.selection.get_selected()
        if _iter is not None:
            count = model.get_value(_iter, 0)
            gc.collect(2)
            referrers = gc.get_referrers(self.junk[count])
            text = ""
            for referrer in referrers:
                match = ""
                try:
                    if referrer is not self.junk:
                        match = "**** "
                        for indx in range(len(self.junk)):
                            if referrer is self.junk[indx]:
                                match = str(indx) + ": "
                                break
                        match += str(referrer) + '\n'
                except ReferenceError:
                    match += 'weakly-referenced object no longer exists %s'\
                        % type(referrer)
                except:
                    print(sys.exc_info())
                text += match
            InfoDialog(_('Referrers of %d') % count, text, parent=self.parent)

    def refers_to(self):
        """ display full list of referents """
        model, _iter = self.selection.get_selected()
        if _iter is not None:
            count = model.get_value(_iter, 0)
            referents = gc.get_referents(self.junk[count])
            text = ""
            for referent in referents:
                match = ""
                try:
                    match = "****: "
                    for indx in range(len(self.junk)):
                        if referent is self.junk[indx]:
                            match = str(indx) + ': '
                            break
                    match += str(referent) + '\n'
                except ReferenceError:
                    match += '%s weakly-referenced object no longer'\
                        ' exists\n' % type(referent)
                except:
                    print(sys.exc_info())
                text += match
            InfoDialog(_('%d refers to') % count, text, parent=self.parent)

    def display(self):
        """ update main display of objects """
        self.parent = self.top.get_toplevel()
        progress = ProgressMeter(
            _('Updating display...'), '', parent=self.parent, can_cancel=True)
        self.model.clear()  # redo the screen completely
        self.junk = []  # contains uncollected objects
        self.id_index = {}  # object id to index table
        self.loop_ctr = 0  # a loop identifier
        # clear old garbage list so we only see new items (important after
        # switch to normal mode).  Cannot replace gc.garbage with empty list,
        # as the underlying structure is what is updated, so clear contents.
        del gc.garbage[:]
        gc.collect(2)
        self.junk = gc.garbage
        self.label.set_text(_('Uncollected Objects: %s') %
                            str(len(self.junk)))
        progress.set_pass(_('Updating display...'), len(self.junk))
        # make up a fast lookup table for objects to ids
        for indx in range(0, len(self.junk)):
            self.id_index[id(self.junk[indx])] = indx

        # find the referers for each object.  We do this by finding the
        # referents (its faster), then updating the referrer list for each
        # object found in the referents.

        # make a list of lists of reference indexes to objects
        self.ref_lst = [[] for i in range(len(self.junk))]

        prev_step = 0
        for indx in range(0, len(self.junk)):
            step = int(indx * 0.11)  # smooth out progress meter
            if step > prev_step:
                prev_step = step
                if progress.step():
                    return
            refs = []
            try:
                for ref in gc.get_referents(self.junk[indx]):
                    try:
                        if ref is self.junk or isinstance(ref, FrameType):
                            continue
                        ref_indx = self.id_index.get(id(ref))
                        if ref_indx is not None:
                            self.ref_lst[ref_indx].append(indx)
                    except:
                        print(sys.exc_info())
            except ReferenceError:
                InfoDialog(_('Reference Error'), "Refresh to correct",
                           parent=self.parent)
            self.ref_lst.append(refs)

        # search for the loops in references

        # indicates that item is part of a loop with #
        self.loop_id = [[] for i in range(len(self.ref_lst))]
        # to record if recursion has explored path before
        self.all = set()
        prev_step = 0
        for item in range(0, len(self.junk)):
            step = int(item * 0.40)  # smooth out progress meter
            if step > prev_step:
                prev_step = step
                if progress.step():
                    return
            if self.loop_id[item]:
                # if we already found this to be part of loop, skip
                continue
            self.recurse(item, item, [item])
            self.all.clear()

        #display the results

        prev_step = 0
        for indx in range(0, len(self.junk)):
            step = int(indx * 0.48)  # smooth out progress meter
            if step > prev_step:
                prev_step = step
                if progress.step():
                    break
            if not self.loop_id[indx] and self.show_loops:
                # if only show loop items and not part of loop
                continue
            if len(self.ref_lst[indx]) > 3:
                ref = ' '.join(map(str, self.ref_lst[indx][0:2])) + "..."
            else:
                ref = ' '.join(map(str, self.ref_lst[indx]))
            if len(self.loop_id[indx]) > 3:
                loop_num = ' '.join(map(str, self.loop_id[indx][0:2])) + "..."
            else:
                loop_num = ' '.join(map(str, self.loop_id[indx]))
            try:
                self.model.append((indx, ref, loop_num, str(self.junk[indx])))
            except DBError:
                self.model.append((indx, ref, loop_num,
                                   'db.DB instance at %s' %
                                   id(self.junk[indx])))
            except ReferenceError:
                self.model.append((
                    indx, ref, loop_num,
                    'weakly-referenced object no longer exists %s'
                    % type(self.junk[indx])))
            except TypeError:
                self.model.append((
                    indx, ref, loop_num,
                    'Object cannot be displayed %s'
                    % type(self.junk[indx])))
            except:
                print(sys.exc_info())
        progress.close()

    def recurse(self, obj, start, current_path):
        """ Recursively look for cyclic references (loops) """
        self.all.add(obj)  # indicate we have been here
        for ref in self.ref_lst[obj]:
            if ref is start:
                # If we've found our way back to the start, this is
                # a reference cycle, so store results
                for item in current_path:
                    self.loop_id[item].append(self.loop_ctr)
                self.loop_ctr += 1
            elif ref not in self.all:
                # if we haven't been here before, try this branch
                self.recurse(ref, start, current_path + [ref])

    def apply_clicked(self, obj):
        """ deal with refresh button"""
        self.display()

    def show_found(self, lookfor):
        """ routine for showing results when doing search """
        self.model.clear()
        for indx in range(0, len(self.junk)):
            if lookfor not in self.loop_id[indx]:
                # show only matching numbers
                continue
            if len(self.ref_lst[indx]) > 3:
                ref = ' '.join(map(str, self.ref_lst[indx][0:2])) + "..."
            else:
                ref = ' '.join(map(str, self.ref_lst[indx]))
            if len(self.loop_id[indx]) > 3:
                loop_num = ' '.join(map(str, self.loop_id[indx][0:2])) + "..."
            else:
                loop_num = ' '.join(map(str, self.loop_id[indx]))
            try:
                self.model.append((indx, ref, loop_num, str(self.junk[indx])))
            except DBError:
                self.model.append((indx, ref, loop_num,
                                   'db.DB instance at %s' %
                                   id(self.junk[indx])))
            except ReferenceError:
                self.model.append((
                    indx, ref, loop_num,
                    'weakly-referenced object no longer exists %s'
                    % type(self.junk[indx])))
            except TypeError:
                self.model.append((
                    indx, ref, loop_num,
                    'Object cannot be displayed %s'
                    % type(self.junk[indx])))
            except:
                print(sys.exc_info())
