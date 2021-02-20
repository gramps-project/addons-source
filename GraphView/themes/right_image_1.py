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
#   |     Name (bold font)      #
# A |---------------------------#
# t |   Birth date   |          #
# t |   Birth place  |  Image   #
# r |----------------|          #
# s |   Death date   |          #
#   |   Death place  |          #
#   |---------------------------#
#   |         Tags line         #
#-------------------------------#
#           Attrs               #   < - attributes can be vertical or horizontal
#################################
"""


class Theme(BasePersonTheme):
    """
    Person theme with image on right side.
    """
    THEME_KIND = 'person'

    def __init__(self, dot_generator, options, functions):
        BasePersonTheme.__init__(self, dot_generator, options, functions)
        self.index = 1
        self.name = _('Image on right side')
        self.wraped=True
        self.html = (
            '%(name)s'
            '<TR>'
            '%(birth)s'
            '%(img)s'
            '</TR>'
            '<TR>%(death)s</TR>'
            '%(tags)s'
            )

        self.name_fmt = '<TR><TD colspan="2" CELLPADDING="5">%s</TD></TR>'
        self.date_fmt = '<TD ALIGN="LEFT" BALIGN="LEFT" CELLPADDING="5">%s</TD>'
        self.image_fmt = '<TD rowspan="2" CELLPADDING="5">%s</TD>'
        self.tag_fmt = '<TR><TD colspan="2" CELLPADDING="5">%s</TD></TR>'

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
        # birth and death cells should be present in table.
        # if no data - as empty cell without CELLPADDING
        birth, death = self.get_dates_str(person, separated=True,
                                          default='<TD></TD>')

        return html % {'img': self.get_image_str(person),
                       'name': self.get_name_str(person),
                       'birth': birth,
                       'death': death,
                       'tags': self.get_tags_str(person),
                       'attrs' : self.get_attrs_str(person)}

