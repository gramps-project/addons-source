# -*- coding: utf-8 -*-

from default_0 import Theme as DefaultTheme

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

"""
#################################
#   |        ---------          #
#   |        | Image |          #
# A |        |       |          #
# t |        ---------          #
# t |---------------------------#
# r |     Name (bold font)      #
# s |---------------------------#
#   |   Birth date              #
#   |   Birth place             #
#   |---------------------------#
#   |   Death date              #
#   |   Death place             #
#   |---------------------------#
#   |        Tags line          #
#   |---------------------------#
#   |          Attrs            #   < - attributes can be vertical or horizontal
#################################
"""


class Theme(DefaultTheme):
    """
    Use person DefaultTheme as base, but apply wrap for dates.
    """
    THEME_KIND = 'person'

    def __init__(self, dot_generator, options, functions):
        DefaultTheme.__init__(self, dot_generator, options, functions)
        self.index = 3
        self.name = _('Normal')
        self.wraped = True

