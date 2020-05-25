######################################################################
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020      Dennis Bareis
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
######################################################################
"""
Collection of debugging tools
"""
######################################################################

# ---------------------------------------------------------------
# Python imports
# ---------------------------------------------------------------
import os
import inspect
import logging

# ---------------------------------------------------------------
# Gramps imports
# ---------------------------------------------------------------
from gramps.gui.dialog import OkDialog

# ------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------
_LOG = logging.getLogger("Form Gramplet")


def dbg_dump_ts(treestore):
    """
    This will dump a 'TreeStore' object
    """
    rootiter = treestore.get_iter_first()
    return _dbg_dump_ts_rows(treestore, rootiter, "")


def _dbg_dump_ts_rows(tso, treeiter, indent):
    """
    This will dump a 'TreeStore' object
    """
    txt = ''
    while treeiter is not None:
        txt = txt + indent + str(tso[treeiter][:]) + '\n'
        if tso.iter_has_child(treeiter):
            childiter = tso.iter_children(treeiter)
            txt = txt + _dbg_dump_ts_rows(tso, childiter, indent + "\t")
        treeiter = tso.iter_next(treeiter)
    if txt == '':
        txt = '<<NO ROWS>>\n'

    # Dump some TreeStore properties
    ccount = tso.get_n_columns()
    txt = txt + ('\n# COLUMNS = %s (MORE INFO: ' +
                 'https://developer.gnome.org/pygtk/stable/' +
                 'class-gtktreemodel.html)\n') % ccount
    for col in range(ccount):
        txt = txt + "\t#%d TYPE=%s\n" % (col, tso.get_column_type(col))
    return txt


def dbg_dump_tv(treeview):
    """
    This will dump a 'TreeView' object
    """
    txt = "\nCOLUMNS:\n"
    col = 0
    for treecol in treeview.get_columns():
        col = col + 1
        spacing = treecol.get_spacing()
        visible = treecol.get_visible()
        expand = treecol.get_expand()
        cghead = treecol.get_clickable()
        title = treecol.get_title()
        txt = txt + (("\t#%d - %s [VISIBLE=%s, EXPAND=%s" +
                      ", SPACING=%s, HEADING CLICKABLE=%s\n")
                     % (col, title, expand, visible, spacing, cghead))
        txt = txt + '\n%s' % dbg_dobj(treecol, 'treecol')
    return txt


def dbg_dobj(obj, what=None,
             dunder=False, sunder=False,
             max_string=2000, dump_as_string=True):
    """
        Returns a string representing the object instance's contents
            obj:  The object to be dumped
            what: Description of the Object
          dunder: Are things like "__file__" returned
                  (things that start with double underscore)
          VERSION 2020-05-21c
    """
    typ = type(obj).__name__
    desc = "class '" + typ + "'"
    if what:
        desc = desc + " - " + what
    rsunder = 0
    rdunder = 0
    txt = '%s\n### START OBJECT DUMP [%s] ###\n' % (desc, desc)
    for attr in dir(obj):
        if attr[:1] == "_":
            if attr[1:2] != "_":
                # sunder (2nd byte not underscore)
                if not sunder:
                    rsunder += 1
                    continue        # Remove sunder as requested
            elif attr[2:3] != "_":
                # dunder (3rd byte not underscore)
                if not dunder:
                    rdunder += 1
                    continue        # Remove dunder as requested
        try:
            val = getattr(obj, attr)
        except:  # pylint: disable=bare-except
            val = '<<FAILED DUMPING VALUE>>'
        txt = txt + '.%s = %r' % (attr, val) + '\n'

    # Dump as a string?
    if dump_as_string:
        try:
            as_string = str(obj)
        except:  # pylint: disable=bare-except
            as_string = '<<str failed>>'
            prefix = 'STRING: '
        else:
            length = len(as_string)
            prefix = 'STRING [length ' + str(len(as_string)) + ']'
            prefix = prefix + '\n' + '~~~~~~\n'
            if length > max_string:
                as_string = as_string[:max_string-3] + '...'
        txt = txt + '\n' + prefix + as_string + "\n"

    # Custom dumps?
    if typ == 'TreeStore':
        txt = txt + '\n' + 'TREE STORE CONTENTS' + '\n'
        txt = txt + '~~~~~~~~~~~~~~~~~~~\n'
        txt = txt + dbg_dump_ts(obj)
    elif typ == 'TreeView':
        txt = txt + '\n' + 'TREE VIEW CONTENTS' + '\n'
        txt = txt + '~~~~~~~~~~~~~~~~~~\n'
        txt = txt + dbg_dump_tv(obj)

    if rsunder != 0 or rdunder != 0:
        sdt = ', removed %d x sunder & %d x dunder' % (rsunder, rdunder)
        desc = desc + sdt
    txt = txt + '### END OBJECT DUMP [%s] ###\n' % desc
    return txt


def dbg_get_caller(relative_frame):
    """
        Gets the module, function and line number of the caller
        (or parent of) from the stack

        relative_frame is 0 for direct parent, or 1 for grand parent..
        https://stackoverflow.com/questions/24438976/python-debugging-get-filename-and-line-number-from-which-a-function-is-called
    """

    relative_frame = relative_frame + 1
    total_stack = inspect.stack()
    frameinfo = total_stack[relative_frame][0]

    func_name = frameinfo.f_code.co_name
    filename = os.path.basename(frameinfo.f_code.co_filename)
    line_number = frameinfo.f_lineno                # of the call
    # func_firstlineno    = frameinfo.f_code.co_firstlineno

    # Return Location String
    locn = "%s:%d@%s()" % (filename, line_number, func_name)
    return locn


def dbg_caller_adesc(relative_frame):
    """ add text in a COMMON FORMAT to be displayed (or logged) to the user """
    return("\n\n" + "LOCATION IN CODE" + '\n' +
           '~~~~~~~~~~~~~~~~~~~~~~~~~\n' +
           dbg_get_caller(relative_frame + 1))


# def FormLogDebug(LogMe):
    # Won't work, currently old Python in AIO Windows Installer
    # in Gramps
    # _LOG.debug(LogMe, stacklevel=2)

def dbg_dialog(title, text):
    """
        Used While Debugging the program
    """
    # pylint: disable=logging-not-lazy
    # return
    text_stack = str(text) + dbg_caller_adesc(1)
    _LOG.debug('DEBUG DLG TITLE=%s, TEXT=%s' % (title, text_stack))
    OkDialog(title, text_stack)     # allow for list etc
