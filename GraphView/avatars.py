# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020-      Ivan Komaritsyn
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

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import os

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from gramps.gen.lib import Person

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


class Avatars():
    """
    Avatar support for GraphView.
    """
    def __init__(self, config):
        """
        config param - gramps.gen.config.
        """
        self.config = config

        # set avatars path '<...<GraphView_addon_path>/avatars>'
        self.path, _filename = os.path.split(__file__)
        self.path = os.path.join(self.path, 'avatars')

        # define styles dictionary
        # dic item: (id: name, directory)
        self.styles = {0: (_('Custom'), None),
                       1: (_('Dark (default)'), 'dark'),
                       2: (_('Light'), 'light'),
                       3: (_('Cartoon'), 'cartoon'),
                      }

        self.style = 1
        self.custom = False
        self.update_current_style()

    def update_current_style(self):
        """
        Update and check current style.
        """
        self.style = self.config.get('interface.graphview-avatars-style')
        if self.styles.get(self.style) is None:
            self.style = 1

        # set custom style mark
        self.custom = self.style == 0

    def get_avatar(self, gender):
        """
        Return person gender avatar or None.
        """
        if self.custom:
            avatar = ''
            if gender == Person.MALE:
                avatar = self.config.get('interface.graphview-avatars-male')
            elif gender == Person.FEMALE:
                avatar = self.config.get('interface.graphview-avatars-female')
            if avatar:
                return avatar
            else:
                return None

        style = self.styles.get(self.style)[1]  # get style directory

        if gender == Person.MALE:
            return os.path.join(self.path, style, 'person_male.png')
        if gender == Person.FEMALE:
            return os.path.join(self.path, style, 'person_female.png')

    def get_styles_list(self):
        """
        List of styles.
        List item: (id, name)
        """
        styles_list = []
        for key, item in self.styles.items():
            styles_list.append((key, item[0]))
        return styles_list

