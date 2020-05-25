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
This module is required to avoid circular imports which python
can't handle:
https://stackoverflow.com/questions/9252543/importerror-cannot-import-name-x
https://stackoverflow.com/questions/17845366/importerror-cannot-import-name/17845428

It will hold utility/tool type functions
"""
######################################################################


# ---------------------------------------------------------------
# Python imports
# ---------------------------------------------------------------
import logging
from distutils.util import strtobool
from gi.repository import Gdk

# ---------------------------------------------------------------
# Gramps imports
# ---------------------------------------------------------------
from gramps.gui.dialog import ErrorDialog, OkDialog
from gramps.gen.const import GRAMPS_LOCALE as glocale
from dbg_tools import dbg_caller_adesc

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
# Tools/helpers follow
# ---------------------------------------------------------------
def sound_bell():
    """
    Will beep, use on warning or error situation
    Logs so you can tell them apart from system beeps.
    :return: Nothing
    """
    _LOG.debug('[BEEP] sound_bell()')
    Gdk.beep()


def iniget(configobj, what, default=''):
    """
    Will get a value from the INI file
    :param configobj: CONFIG
    :param what:      The name of the INI item
    :param default:   A default value for a string, if passed the
                      object can be of any type.
    :return: The value in the INI file
    """
    try:
        value = configobj.get(what)
    except:  # pylint: disable=bare-except
        value = default
        oops = ('iniget(): ini "%s" doesn\'t exist (returning default' +
                ' of %s).  Registering the key in the ini file!')
        _LOG.warning(oops % (what, default))  # Don't know object type, pylint: disable=logging-not-lazy
        try:
            configobj.register(what, default)
            configobj.save()
        except:  # pylint: disable=bare-except
            _LOG.warning('iniget(): also failed registering it ("%s").',
                         what)
        else:
            _LOG.warning('iniget(): successfully registered "%s".',
                         what)
    return value


def inigeti(configobj, what, default=0):
    """
    Will get an integer value from the INI file
    :param configobj: CONFIG
    :param what:      The name of the INI item
    :param default:   A default value for the integer
    :return: The value in the INI file
    """
    # It is lazy: pylint: disable=logging-not-lazy

    value = iniget(configobj, what, default)
    try:
        numeric = int(value)
        _LOG.info('inigeti(): ini "%s" contained the integer: %d' +
                  ' (default was %s)', what, value, str(default))
    except:  # pylint: disable=bare-except
        numeric = default
        _LOG.warning('inigeti(): ini "%s" contained an invalid' +
                     ' integer of "%s" (returning default of %s)',
                     what, str(value), str(default))
    return numeric


def inigetb(configobj, what, default=False):
    """
    Will get a boolean value from the INI file
    :param configobj: CONFIG
    :param what:      The name of the INI item
    :param default:   A default value if it's a boolean
    :return: The value in the INI file
    """
    # It is lazy: pylint: disable=logging-not-lazy

    value = iniget(configobj, what, default)
    vtype = type(value).__name__
    try:
        if vtype != 'str':
            boolean = bool(value)
        else:
            boolean = bool(strtobool(value))
        _LOG.info('inigetb(): ini "%s" contained the boolean: %s' +
                  ' (orig type "%s", default was %s)',
                  what, str(boolean), vtype, str(default))
    except:  # pylint: disable=bare-except
        boolean = default
        _LOG.warning('inigetb(): ini "%s" contained an invalid' +
                     ' boolean of "%s" (returning default of %s)',
                     what, str(value), str(default))
    return boolean


def dlgerror(title, text):
    """
        Used to display an error of some type that the user probably
        can't do much about (the code location is appended)
    """
    # pylint: disable=logging-not-lazy
    sound_bell()
    text_stack = str(text) + dbg_caller_adesc(1)
    _LOG.error('ERROR DLG TITLE=%s\nTEXT=%s\n' % (title, text_stack))
    ErrorDialog(title, text_stack)   # allow for list etc


def dlginfo(title, text):
    """
        Used to display non-critical information to the user
        (which is based on their input)
    """
    # pylint: disable=logging-not-lazy
    sound_bell()
    _LOG.warning('INFO DLG TITLE=%s\nTEXT=%s\n' % (title, text))
    OkDialog(title, text)


def dlgcritical(title, text):
    """
        Raise an Exception after displaying the error to the user
        (log will contain the full stack trace)
    """
    # pylint: disable=logging-not-lazy
    sound_bell()
    text_stack = str(text) + dbg_caller_adesc(1)
    _LOG.warning('EXCEPTION DLG TITLE [raising exception]: ' +
                 '%s\nTEXT=%s\n' % (title, text_stack))
    ErrorDialog(title, text_stack)
    raise Exception(
        "\n\n" +
        _("DIALOG TITLE") +
        "\n~~~~~~~~~~~~~~~~~~~~~~~~~\n" +
        title + "\n\n" +
        _("DIALOG TEXT") +
        "\n~~~~~~~~~~~~~~~~~~~~~~~~~\n" +
        text
    )
