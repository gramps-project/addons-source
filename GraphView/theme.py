# -*- coding: utf-8 -*-

import os
from html import escape
from importlib import import_module
from gramps.gen.display.name import displayer
from gramps.gen.utils.db import get_birth_or_fallback, get_death_or_fallback
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen import datehandler
from gramps.gen.lib import EventType, EventRoleType

from gi.repository import Gdk

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

import sys
theme_folder = os.path.join(os.path.dirname(__file__), 'themes')
sys.path.append(os.path.abspath(theme_folder))


class BaseTheme:
    """
    Base theme class.
    """
    def __init__(self, dot_generator, options, functions):
        self.dot_generator = dot_generator
        self.options = options
        self.functions = functions
        self.kind = ''              # 'person', 'family'
        self.index = None           # unique integer
        self.name = 'Base theme'    # theme name
        self.table = (
            '<TABLE '
            'BORDER="0" CELLSPACING="0" CELLPADDING="0" CELLBORDER="0">'
            '%s'
            '</TABLE>')
        self.html = ''              # html table body
        self.tags = None

        self.table_row_fmt = '<TR><TD CELLPADDING="5">%s</TD></TR>'
        self.tag_fmt = self.table_row_fmt
        self.date_fmt = self.table_row_fmt

    def build(self, obj, html=None):
        """
        Build html table.
        Should be implimented in theme and return html string.
        
        This isn't a free-form HTML format here...just a few keywords that
        happen to be similar to keywords commonly seen in HTML.
        For additional information on what is allowed, see:
            https://www.graphviz.org/doc/info/shapes.html#html
        """
        pass

    def get_html(self, obj, html=None):
        """
        Return html table.
        """
        if html is None:
            html = self.html
        return self.table % self.build(obj, html)

    def get_tags_str(self, obj):
        """
        Get formated tags string for person or family.
        """
        tag_table = ''
        if self.options.show_tags:
            self.tags, tag_table = self.functions.get_tags_and_table(obj)
        return self.tag_fmt % tag_table if tag_table else ''


class BasePersonTheme(BaseTheme):
    """
    Base person theme class.
    """
    def __init__(self, dot_generator, options, functions):
        BaseTheme.__init__(self, dot_generator, options, functions)
        self.kind = 'person'
        self.wraped = False         # wrap date place to new line

        self.image_fmt = self.table_row_fmt
        self.name_fmt = self.table_row_fmt

    def get_attr_format(self):
        """
        Choose vertical or horizontal format for attributes cell.
        """
        if self.options.attrs_vertical:
            attrs_fmt = (
                '<TR><TD rowspan="6" CELLPADDING="0" '
                'ALIGN="LEFT" BALIGN="LEFT" VALIGN="TOP">'
                '<TABLE BORDER="0" VALIGN="TOP" FIXEDSIZE="True">%s</TABLE>'
                '</TD></TR>')
        else:
            attrs_fmt = (
                '<TR><TD colspan="2" CELLPADDING="0">'
                '<TABLE BORDER="0" FIXEDSIZE="True">%s</TABLE>'
                '</TD></TR>')
        return attrs_fmt

    def get_image(self, obj):
        """
        Get image for person or family.
        For now is only for person.
        """
        image = ''
        if self.kind=='person' and self.options.show_images:
            image = self.functions.get_person_image(obj, kind='path')
            if not image and self.options.show_avatars:
                image = self.functions.get_avatar(gender=obj.gender)
            image = '<IMG SRC="%s"/>' % image if image is not None else ''
        return image

    def get_name(self, person):
        """
        Get the person's name.
        """
        if self.kind != 'person':
            return ''
        person_name = person.get_primary_name()
        call_name = person_name.get_call_name()
        name = displayer.display_name(person_name)

        if not name:
            # name string should not be empty
            return ' '

        # underline call name
        if call_name and call_name in name:
            name_list = name.split(call_name)
            name = ''
            for item in name_list:
                if name:
                    name += '<U>%s</U>%s' % (escape(call_name), escape(item))
                else:
                    name += escape(item)
        name = ('<FONT POINT-SIZE="%3.1f"><B>%s</B></FONT>'
                % (self.options.bold_size, name))
        return name

    def get_dates(self, person, wraped=None):
        """
        Get birth and death dates.
        """
        if wraped is None:
            wraped = self.wraped
        
        # birth, death is a lists [date, place]
        birth, death = self.functions.get_date_strings(person)

        birth_str = ''
        death_str = ''
        birth_wraped = ''
        death_wraped = ''

        if self.options.show_full_dates or self.options.show_places:
            if birth[0]:
                birth[0] = _('%s %s') % (self.options.bth_sym, birth[0])
                birth_wraped = birth[0]
                birth_str = birth[0]
                if birth[1]:
                    birth_wraped += '<BR/>'
                    birth_str += '  '
            elif birth[1]:
                birth_wraped = _('%s ') % self.options.bth_sym
                birth_str = _('%s ') % self.options.bth_sym
            birth_wraped += birth[1]
            birth_str += birth[1]

            if death[0]:
                death[0] = _('%s %s') % (self.options.dth_sym, death[0])
                death_wraped = death[0]
                death_str = death[0]
                if death[1]:
                    death_wraped += '<BR/>'
                    death_str += '  '
            elif death[1]:
                death_wraped = _('%s ') % self.options.dth_sym
                death_str = _('%s ') % self.options.dth_sym
            death_wraped += death[1]
            death_str += death[1]

        # 2) simple and on one line:
        #       (1890 - 1960)
        else:
            if birth[0] or death[0]:
                # show dots if have no date
                b = birth[0] if birth[0] else '...'
                d = death[0] if death[0] else '...'
                birth_str = _('(%s - %s)') % (b, d)
                if birth[0]:
                    birth_wraped = _('%s %s') % (self.options.bth_sym, birth[0])
                if death[0]:
                    death_wraped = _('%s %s') % (self.options.dth_sym, death[0])

        if wraped:
            return birth_wraped, death_wraped
        else:
            return birth_str, death_str

    def get_image_str(self, person):
        """
        Get formated image string.
        """
        image = self.get_image(person)
        return self.image_fmt % image if image else ''

    def get_name_str(self, person):
        """
        Get formated name string.
        """
        name = self.get_name(person)
        return self.name_fmt % name if name else ''

    def get_dates_str(self, person, separated=False, default=''):
        """
        Get formated date strings.
        """
        birth, death = self.get_dates(person)

        birth = self.date_fmt % (birth) if birth else default
        death = self.date_fmt % (death) if death else default

        if separated:
            return birth, death
        else:
            return birth + death

    def get_attrs_str(self, person):
        """
        Get attributes string.
        """
        if not self.options.show_attrs:
            return ''
        attrs_list = person.get_attribute_list()
        if not attrs_list:
            return ''

        # symbols for eye and hair (font should be installed)
        eye = u"\U0001F441"
        hair = u"\U0001F9B3"
        attr_symbol = {_('eye color') : eye,
                       _('hair color') : hair,
                      }

        colors_dic = {
                      'white' : 'white',
                      'blond' : 'white',
                      'amber' : 'gold',
                      'blue' : 'blue',
                      'grey' : 'grey',
                      'green' : 'green',
                      'brown' : 'saddlebrown',
                      'black' : 'black',
                      'yellow' : 'yellow',
                      'red' : 'red',
                      'auburn' : 'orangered',
                      # russian
                      'белый' : 'white',
                      'седой' : 'ivory',
                      'синий' : 'blue',
                      'голубой' : 'skyblue',
                      'серый' : 'grey',
                      'зеленый' : 'green',
                      'янтарный' : 'gold',
                      'болотный' : 'olive',
                      'оливковый' : 'olive',
                      'карий' : 'saddlebrown',
                      'каштановый' : 'saddlebrown',
                      'русый' : 'lightgoldenrod',
                      'черный' : 'black',
                      'желтый' : 'yellow',
                      'рыжий' : 'orangered',
                      'красный' : 'red',
                     }

        # list of (attr_symbol, color)
        attributes = []

        for at in attrs_list:
            symbol = attr_symbol.get(at.type.type2base().lower())
            if symbol is not None:
                attributes.append((symbol,
                                   colors_dic.get(at.value.lower(), '')))

        attrs = ''
        if self.options.attrs_vertical:
            attr_color = '<TR><TD height="5" BGCOLOR="%s"></TD></TR>'
            for at in attributes:
                attrs += '<TR><TD>%s</TD></TR>' % at[0]
                attrs += attr_color % at[1] if at[1] else ''
        else:
            for at in attributes:
                if not attrs:
                    attrs = '<TR>'
                attrs += '<TD>%s</TD>' % at[0]
            if attrs:
                attrs += '</TR>'

            colors = ''
            attr_color = '<TD height="5" BGCOLOR="%s"></TD>'
            for at in attributes:
                if not colors:
                    colors = '<TR>'
                colors += attr_color % at[1] if at[1] else '<TD></TD>'
            if colors:
                attrs += colors + '</TR>'

        return self.get_attr_format() % attrs if attrs else ''


class BaseFamilyTheme(BaseTheme):
    """
    Base family theme class.
    """
    def __init__(self, dot_generator, options, functions):
        BaseTheme.__init__(self, dot_generator, options, functions)
        self.kind = 'family'

    def get_label(self, family):
        """
        Get lable for family (date and place).
        """
        event_str = ['', '']
        for event_ref in family.get_event_ref_list():
            event = self.dot_generator.database.get_event_from_handle(event_ref.ref)
            if (event.type == EventType.MARRIAGE and
                    (event_ref.get_role() == EventRoleType.FAMILY or
                     event_ref.get_role() == EventRoleType.PRIMARY)):
                event_str = self.functions.get_event_string(event)
                break
        if event_str[0] and event_str[1]:
            event_str = '%s<BR/>%s' % (event_str[0], event_str[1])
        elif event_str[0]:
            event_str = event_str[0]
        elif event_str[1]:
            event_str = event_str[1]
        else:
            event_str = ''

        return event_str

    def get_label_str(self, family):
        """
        Get formated lable string for family (date and place).
        """
        label = self.get_label(family)
        return self.date_fmt % label


class Functions():
    """
    Functions from graphview to get data.
    """
    def __init__(self, graph_widget, options, kind):
        self.dot_generator = options.dot_generator
        self.dbstate = self.dot_generator.dbstate
        self.options = options

        if kind == 'person':
            self.get_person_image = graph_widget.get_person_image
            self.get_avatar = self.dot_generator.avatars.get_avatar

    def get_tags_and_table(self, obj):
        """
        Return html tags table for obj (person or family).
        """
        tag_table = ''
        tags = []

        for tag_handle in obj.get_tag_list():
            tags.append(self.dbstate.db.get_tag_from_handle(tag_handle))

        # prepare html table of tags
        if tags:
            tag_table = ('<TABLE BORDER="0" CELLBORDER="0" '
                         'CELLPADDING="5"><TR>')
            for tag in tags:
                rgba = Gdk.RGBA()
                rgba.parse(tag.get_color())
                value = '#%02x%02x%02x' % (int(rgba.red * 255),
                                           int(rgba.green * 255),
                                           int(rgba.blue * 255))
                tag_table += '<TD BGCOLOR="%s"></TD>' % value
            tag_table += '</TR></TABLE>'

        return tags, tag_table

    def get_date_strings(self, person):
        """
        Returns tuple of birth/christening and death/burying date strings.
        """
        birth_event = get_birth_or_fallback(self.dot_generator.database,
                                            person)
        if birth_event:
            birth = self.get_event_string(birth_event)
        else:
            birth = ['', '']

        death_event = get_death_or_fallback(self.dot_generator.database,
                                            person)
        if death_event:
            death = self.get_event_string(death_event)
        else:
            death = ['', '']

        return (birth, death)

    def get_event_string(self, event):
        """
        Return string for an event label.

        Based on the data availability and preferences, we select one
        of the following for a given event:
            year only
            complete date
            place name
            empty string
        """
        if event:
            place_title = place_displayer.display_event(
                self.dot_generator.database, event,
                fmt=self.options.place_format)
            date_object = event.get_date_object()
            date = ''
            place = ''
            # shall we display full date
            # or do we have a valid year to display only year
            if(self.options.show_full_dates and date_object.get_text() or
               date_object.get_year_valid()):
                if self.options.show_full_dates:
                    date = '%s' % datehandler.get_date(event)
                else:
                    date = '%i' % date_object.get_year()
                # shall we add the place?
                if self.options.show_places and place_title:
                    place = place_title
                return [escape(date), escape(place)]
            else:
                if place_title and self.options.show_places:
                    return ['', escape(place_title)]
        return ['', '']


class Options():
    """
    Options from graphview config and DotSvgGenerator.
    """
    def __init__(self, dot_generator, kind):
        self.config = dot_generator.view._config
        self.dot_generator = dot_generator
        self.kind = kind
        # read data from config
        self.update()

    def update(self):
        """
        Update data.
        """
        self.show_tags = self.config.get('interface.graphview-show-tags')
        self.show_full_dates = self.config.get(
            'interface.graphview-show-full-dates')
        self.show_places = self.config.get('interface.graphview-show-places')
        self.place_format = self.config.get(
            'interface.graphview-place-format') - 1
        self.bold_size = self.dot_generator.bold_size

        if self.kind == 'person':
            self.show_images = self.config.get(
                'interface.graphview-show-images')
            self.show_avatars = self.config.get(
                'interface.graphview-show-avatars')

            attrs_opt = self.config.get('interface.graphview-attrs-direction')
            self.show_attrs = attrs_opt != 0
            self.attrs_vertical = attrs_opt == 1

            self.bth_sym = self.dot_generator.bth
            self.dth_sym = self.dot_generator.dth


class Themes():
    """
    Main themes class.
    """
    def __init__(self, dot_generator, graph_widget):
        self.config = dot_generator.view._config

        self.person_opts = Options(dot_generator, 'person')
        self.family_opts = Options(dot_generator, 'family')
        self.person_funcs = Functions(graph_widget, self.person_opts, 'person')
        self.family_funcs = Functions(graph_widget, self.family_opts, 'family')

        self.list_person = []       # person theme objects list
        self.list_family = []
        self.person_themes = []     # person theme list [(index, name), ...]
        self.family_themes = []

        # current themes
        self.person_theme = None
        self.family_theme = None

        self.person_theme_index = self.config.get(
            'interface.graphview-person-theme')

        for module in os.listdir(theme_folder):
            if module == '__init__.py' or module[-3:] != '.py':
                continue
            try:
                item = import_module(module[:-3]).Theme
                if item.THEME_KIND == 'person':
                    item = item(dot_generator,
                                self.person_opts, self.person_funcs)
                    self.list_person.append(item)
                    self.person_themes.append((item.index, item.name))
                elif item.THEME_KIND == 'family':
                    item = item(dot_generator,
                                self.person_opts, self.person_funcs)
                    self.list_family.append(item)
                else:
                    print('Wrong theme kind "%s" detected in module "%s"'
                          % (item.THEME_KIND, module))
            except:
                print('Found errors in theme module: ', module)

        # sort theme lists by theme name
        self.person_themes.sort(key=lambda tup: tup[1])
        self.family_themes.sort(key=lambda tup: tup[1])

        self.person_theme, self.family_theme = self.get_current()

    def get_current(self):
        """
        Find current themes for person and family in lists by index.
        """
        self.person_theme_index = self.config.get(
            'interface.graphview-person-theme')
        f_index = 0

        p_theme = None
        f_theme = None

        for item in self.list_person:
            if item.index == self.person_theme_index:
                p_theme = item
                break
        # use default person theme if current does not found
        if p_theme is None:
            for item in self.list_person:
                if item.index == 0:
                    p_theme = item
                    break

        for item in self.list_family:
            if item.index == f_index:
                f_theme = item
                break
        # use default family theme if current does not found
        if p_theme is None:
            for item in self.list_family:
                if item.index == 0:
                    f_theme = item
                    break

        return p_theme, f_theme

    def update_options(self):
        """
        Read current options.
        """
        self.person_opts.update()
        self.family_opts.update()
        self.person_theme, self.family_theme = self.get_current()

