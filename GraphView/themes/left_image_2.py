# -*- coding: utf-8 -*-

from right_image_1 import Theme as RightImageTheme

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

"""
#################################
#   |     Name (bold font)      #
# A |---------------------------#
# t |         |  Birth date     #
# t |  Image  |  Birth place    #
# t |         |---------------- #
# r |         |  Death date     #
# s |         |  Death place    #
#   |---------------------------#
#   |         Tags line         #
#-------------------------------#
#           Attrs               #   < - attributes can be vertical or horizontal
#################################
"""


class Theme(RightImageTheme):
    """
    Person theme with image on left side.
    Use RightImageTheme as base.
    """
    THEME_KIND = 'person'

    def __init__(self, dot_generator, options, functions):
        RightImageTheme.__init__(self, dot_generator, options, functions)
        self.index = 2
        self.name = _('Image on left side')
        self.html = (
            '%(name)s'
            '<TR>'
            '%(img)s'
            '%(birth)s'
            '</TR>'
            '<TR>%(death)s</TR>'
            '%(tags)s'
            )

