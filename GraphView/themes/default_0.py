# -*- coding: utf-8 -*-

from theme import BasePersonTheme

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

"""
#################################
#   |        ---------          #
# A |        | Image |          #
# t |        |       |          #
# r |        ---------          #
# r |---------------------------#
# s |     Name (bold font)      #
#   |---------------------------#
#   |   Birth and death dates   #   < - dates have short and long formats
#   |---------------------------#
#   |   Tags line               #
#-------------------------------#
#           Attrs               #   < - attributes can be vertical or horizontal
#################################

      Long date format                Short date format
#############################   #############################
#   Birth date and place    #   #      (birth - death)      #
#   Death date and place    #   #############################
#############################
"""

class Theme(BasePersonTheme):
    """
    Default person theme.
    """
    THEME_KIND = 'person'

    def __init__(self, dot_generator, options, functions):
        BasePersonTheme.__init__(self, dot_generator, options, functions)
        self.index = 0
        self.name = _('Default')
        self.wraped = False
        # will be changed in "self.get_html" method (add attrs cell)
        self.html = ('%(img)s'
                     '%(name)s'
                     '%(dates)s'
                     '%(tags)s')

        self.full_date_fmt = ('<TR><TD ALIGN="LEFT" BALIGN="LEFT" '
                              'CELLPADDING="5">%s</TD></TR>')

    def get_dates_str(self, person):
        """
        Get formated dates string.
        """
        if (self.options.show_full_dates or self.options.show_places
                or self.wraped):
            # change format to wrap birth and death dates
            self.date_fmt = self.full_date_fmt
        else:
            self.date_fmt = self.table_row_fmt

        # call original BasePersonTheme.get_dates_str
        return super().get_dates_str(person)

    def get_html(self, person):
        """
        Insert attributes cell to table.
        """
        if self.options.attrs_vertical:
            html = '%(attrs)s' + self.html
        else:
            html = self.html + '%(attrs)s'

        # call original "BaseTheme.get_html" with changed html
        return super().get_html(person, html)

    def build(self, person, html):
        """
        Build html table.
        """
        return html % {'img': self.get_image_str(person),
                       'name': self.get_name_str(person),
                       'dates': self.get_dates_str(person),
                       'tags': self.get_tags_str(person),
                       'attrs' : self.get_attrs_str(person)
                      }

