# -*- coding: utf-8 -*-

from theme import BaseFamilyTheme

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

"""
#############################
#       Marrige date        #
#---------------------------#
#         Tags line         #
#############################
"""

class Theme(BaseFamilyTheme):
    """
    Default family theme.
    """
    THEME_KIND = 'family'

    def __init__(self, dot_generator, options, functions):
        BaseFamilyTheme.__init__(self, dot_generator, options, functions)
        self.index = 0
        self.name = _('Default')
        self.wraped = False
        self.html = ('%(dates)s'
                     '%(tags)s')

    def build(self, family, html):
        """
        Build html table.
        """
        return html % {'dates': self.get_label_str(family),
                       'tags': self.get_tags_str(family)}

