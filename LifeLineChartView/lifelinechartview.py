#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020 Christian Schulze
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

"""
See https://github.com/CWSchulze/life_line_chart
"""

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk
import cairo
from gramps.gen.const import GRAMPS_LOCALE as glocale
from copy import deepcopy

#-------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------nechart
from gramps.gui.views.navigationview import NavigationView
from gramps.gui.views.bookmarks import PersonBookmarks
from gramps.gui.utils import SystemFonts

# widget
import lifelinechart

# backend
from life_line_chart import BaseGraph

# the print settings to remember between print sessions
PRINT_SETTINGS = None
_ = glocale.translation.sgettext


class LifeLineChartView(lifelinechart.LifeLineChartGrampsGUI, NavigationView):
    """
    The Gramplet code that realizes the LifeLineChartWidget.
    """
    # settings in the config file, Needs to be preset only for values with wrong data format
    CONFIGSETTINGS = (
        ('interface.lifelineview-generations', 4),
        ('interface.lifelineview-background', lifelinechart.BACKGROUND_GRAD_GEN),
        ('interface.lifelineview-showid', False),
        ('interface.lifelineview-relative_line_thickness', BaseGraph._default_formatting['relative_line_thickness']*100),
        ('interface.lifelineview-font_size_description', BaseGraph._default_formatting['font_size_description']*100),
        ('interface.lifelineview-birth_label_rotation', str(BaseGraph._default_formatting['birth_label_rotation'])),
        ('interface.lifelineview-death_label_rotation', str(BaseGraph._default_formatting['death_label_rotation'])),
        ('interface.lifelineview-birth_label_letter_x_offset', str(BaseGraph._default_formatting['birth_label_letter_x_offset'])),
        ('interface.lifelineview-birth_label_letter_y_offset', str(BaseGraph._default_formatting['birth_label_letter_y_offset'])),
        ('interface.lifelineview-death_label_letter_x_offset', str(BaseGraph._default_formatting['death_label_letter_x_offset'])),
        ('interface.lifelineview-death_label_letter_y_offset', str(BaseGraph._default_formatting['death_label_letter_y_offset'])),
        ('interface.lifelineview-individual_foto_relative_size', BaseGraph._default_formatting['individual_foto_relative_size']*100),
        )

    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        self.dbstate = dbstate
        self.uistate = uistate

        self.formatting = deepcopy(BaseGraph._default_formatting)
        self.positioning = deepcopy(BaseGraph._default_positioning)
        self.allfonts = [x for x in enumerate(
            SystemFonts().get_system_fonts())]

        self.gui_config = {
            'generations': {
                'description': BaseGraph._positioning_description['generations']['short_description'],
                'tooltip': BaseGraph._positioning_description['generations']['long_description'],
                'additional_arg': {'range': (1, 100)},
                'data_container': 'positioning',
                'widget': 'spinner',
                'additional_setter_arg': {}
            },
            # 'compression_steps': {
            #     'description' : 'compression_steps',
            #     'additional_arg' : {'range':(-1,500)},
            #     'data_container':'positioning',
            #     'widget' : 'spinner',
            #     'additional_setter_arg'  : {}
            # },
            'warp_shape': {
                'description': BaseGraph._formatting_description['warp_shape']['short_description'],
                'tooltip': BaseGraph._formatting_description['warp_shape']['long_description'],
                'additional_arg': {'opts': [a for a in enumerate(BaseGraph._available_warp_shapes)], 'valueactive': True},
                'additional_setter_arg': {'index_to_name': lambda x: BaseGraph._available_warp_shapes[x]},
                'data_container': 'formatting',
                'widget': 'combobox',
            },
            'flip_to_optimize': {
                'description': BaseGraph._positioning_description['flip_to_optimize']['short_description'],
                'tooltip': BaseGraph._positioning_description['flip_to_optimize']['long_description'],
                'additional_arg': {},
                'widget': 'checkbox',
                'data_container': 'positioning',
                'additional_setter_arg': {}
            },
            'compress': {
                'description': BaseGraph._positioning_description['compress']['short_description'],
                'tooltip': BaseGraph._positioning_description['compress']['long_description'],
                'additional_arg': {},
                'widget': 'checkbox',
                'data_container': 'positioning',
                'additional_setter_arg': {}
            },
            'fade_individual_color': {
                'description': BaseGraph._formatting_description['fade_individual_color']['short_description'],
                'tooltip': BaseGraph._formatting_description['fade_individual_color']['long_description'],
                'additional_arg': {},
                'widget': 'checkbox',
                'data_container': 'formatting',
                'additional_setter_arg': {}
            },
            'birth_label_active': {
                'description': BaseGraph._formatting_description['birth_label_active']['short_description'],
                'tooltip': BaseGraph._formatting_description['birth_label_active']['long_description'],
                'additional_arg': {},
                'widget': 'checkbox',
                'data_container': 'formatting',
                'additional_setter_arg': {}
            },
            'birth_label_along_path': {
                'description': BaseGraph._formatting_description['birth_label_along_path']['short_description'],
                'tooltip': BaseGraph._formatting_description['birth_label_along_path']['long_description'],
                'additional_arg': {},
                'widget': 'checkbox',
                'data_container': 'formatting',
                'additional_setter_arg': {}
            },
            'marriage_label_active': {
                'description': BaseGraph._formatting_description['marriage_label_active']['short_description'],
                'tooltip': BaseGraph._formatting_description['marriage_label_active']['long_description'],
                'additional_arg': {},
                'widget': 'checkbox',
                'data_container': 'formatting',
                'additional_setter_arg': {}
            },
            'death_label_active': {
                'description': BaseGraph._formatting_description['death_label_active']['short_description'],
                'tooltip': BaseGraph._formatting_description['death_label_active']['long_description'],
                'additional_arg': {},
                'widget': 'checkbox',
                'data_container': 'formatting',
                'additional_setter_arg': {}
            },
            'vertical_step_size': {
                'description': BaseGraph._formatting_description['vertical_step_size']['short_description'],
                'tooltip': BaseGraph._formatting_description['vertical_step_size']['long_description'],
                'additional_arg': {'range': (1, 100)},
                'data_container': 'formatting',
                'widget': 'slider',
                'additional_setter_arg': {}
            },
            'relative_line_thickness': {
                'description': BaseGraph._formatting_description['relative_line_thickness']['short_description'],
                'tooltip': BaseGraph._formatting_description['relative_line_thickness']['long_description'],
                'additional_arg': {'range': (1, 100)},
                'data_container': 'formatting',
                'widget': 'slider',
                'additional_setter_arg': {
                    'value_decode': lambda x: x/100.,
                    'value_encode': lambda x: int(x*100)
                },
            },
            'total_height': {
                'description': BaseGraph._formatting_description['total_height']['short_description'],
                'tooltip': BaseGraph._formatting_description['total_height']['long_description'],
                'additional_arg': {'range': (500, 5000)},
                'data_container': 'formatting',
                'widget': 'slider',
                'additional_setter_arg': {}
            },
            'fathers_have_the_same_color': {
                'description': BaseGraph._positioning_description['fathers_have_the_same_color']['short_description'],
                'tooltip': BaseGraph._positioning_description['fathers_have_the_same_color']['long_description'],
                'additional_arg': {},
                'widget': 'checkbox',
                'data_container': 'positioning',
                'additional_setter_arg': {}
            },
            'font_name': {
                'description': BaseGraph._formatting_description['font_name']['short_description'],
                'tooltip': BaseGraph._formatting_description['font_name']['long_description'],
                'additional_arg': {'opts': self.allfonts, 'valueactive': True},
                'additional_setter_arg': {'index_to_name': lambda x: self.allfonts[x][1]},
                'data_container': 'formatting',
                'widget': 'combobox',
            },
            'family_shape': {
                'description': BaseGraph._formatting_description['family_shape']['short_description'],
                'tooltip': BaseGraph._formatting_description['family_shape']['long_description'],
                'additional_arg': {'opts': [a for a in enumerate(list(BaseGraph._formatting_description['family_shape']['choices'].values()))], 'valueactive': True},
                'additional_setter_arg': {'index_to_name': lambda x: list(BaseGraph._formatting_description['family_shape']['choices'].keys())[x]},
                'data_container': 'formatting',
                'widget': 'combobox',
            },
            'font_size_description': {
                'description': BaseGraph._formatting_description['font_size_description']['short_description'],
                'tooltip': BaseGraph._formatting_description['font_size_description']['long_description'],
                'additional_arg': {'range': (1, 200)},
                'data_container': 'formatting',
                'widget': 'slider',
                'additional_setter_arg': {
                    'value_decode': lambda x: x/100.,
                    'value_encode': lambda x: int(x*100)
                },
            },
            'birth_label_rotation': {
                'description': BaseGraph._formatting_description['birth_label_rotation']['short_description'],
                'tooltip': BaseGraph._formatting_description['birth_label_rotation']['long_description'],
                'additional_arg': {'col_attach' : 1},
                'additional_setter_arg': {
                    'value_decode': lambda x: float(x),
                    'value_encode': lambda x: str(x)
                },
                'data_container': 'formatting',
                'widget': 'lineedit',
            },
            'birth_label_letter_x_offset': {
                'description': BaseGraph._formatting_description['birth_label_letter_x_offset']['short_description'],
                'tooltip': BaseGraph._formatting_description['birth_label_letter_x_offset']['long_description'],
                'additional_arg': {'col_attach' : 1},
                'additional_setter_arg': {
                    'value_decode': lambda x: float(x),
                    'value_encode': lambda x: str(x)
                },
                'data_container': 'formatting',
                'widget': 'lineedit',
            },
            'birth_label_letter_y_offset': {
                'description': BaseGraph._formatting_description['birth_label_letter_y_offset']['short_description'],
                'tooltip': BaseGraph._formatting_description['birth_label_letter_y_offset']['long_description'],
                'additional_arg': {'col_attach' : 1},
                'additional_setter_arg': {
                    'value_decode': lambda x: float(x),
                    'value_encode': lambda x: str(x)
                },
                'data_container': 'formatting',
                'widget': 'lineedit',
            },
            'birth_label_anchor': {
                'description': BaseGraph._formatting_description['birth_label_anchor']['short_description'],
                'tooltip': BaseGraph._formatting_description['birth_label_anchor']['long_description'],
                'additional_arg': {'opts': [a for a in enumerate(list(BaseGraph._formatting_description['birth_label_anchor']['choices'].values()))], 'valueactive': True},
                'additional_setter_arg': {'index_to_name': lambda x: list(BaseGraph._formatting_description['birth_label_anchor']['choices'].keys())[x]},
                'data_container': 'formatting',
                'widget': 'combobox',
            },
            'birth_label_wrapping_active': {
                'description': BaseGraph._formatting_description['birth_label_wrapping_active']['short_description'],
                'tooltip': BaseGraph._formatting_description['birth_label_wrapping_active']['long_description'],
                'additional_arg': {},
                'widget': 'checkbox',
                'data_container': 'formatting',
                'additional_setter_arg': {}
            },
            'death_label_rotation': {
                'description': BaseGraph._formatting_description['death_label_rotation']['short_description'],
                'tooltip': BaseGraph._formatting_description['death_label_rotation']['long_description'],
                'additional_arg': {'col_attach' : 1},
                'additional_setter_arg': {
                    'value_decode': lambda x: float(x),
                    'value_encode': lambda x: str(x)
                },
                'data_container': 'formatting',
                'widget': 'lineedit',
            },
            'death_label_letter_x_offset': {
                'description': BaseGraph._formatting_description['death_label_letter_x_offset']['short_description'],
                'tooltip': BaseGraph._formatting_description['death_label_letter_x_offset']['long_description'],
                'additional_arg': {'col_attach' : 1},
                'additional_setter_arg': {
                    'value_decode': lambda x: float(x),
                    'value_encode': lambda x: str(x)
                },
                'data_container': 'formatting',
                'widget': 'lineedit',
            },
            'death_label_letter_y_offset': {
                'description': BaseGraph._formatting_description['death_label_letter_y_offset']['short_description'],
                'tooltip': BaseGraph._formatting_description['death_label_letter_y_offset']['long_description'],
                'additional_arg': {'col_attach' : 1},
                'additional_setter_arg': {
                    'value_decode': lambda x: float(x),
                    'value_encode': lambda x: str(x)
                },
                'data_container': 'formatting',
                'widget': 'lineedit',
            },
            'death_label_anchor': {
                'description': BaseGraph._formatting_description['death_label_anchor']['short_description'],
                'tooltip': BaseGraph._formatting_description['death_label_anchor']['long_description'],
                'additional_arg': {'opts': [a for a in enumerate(list(BaseGraph._formatting_description['death_label_anchor']['choices'].values()))], 'valueactive': True},
                'additional_setter_arg': {'index_to_name': lambda x: list(BaseGraph._formatting_description['death_label_anchor']['choices'].keys())[x]},
                'data_container': 'formatting',
                'widget': 'combobox',
            },
            'death_label_wrapping_active': {
                'description': BaseGraph._formatting_description['death_label_wrapping_active']['short_description'],
                'tooltip': BaseGraph._formatting_description['death_label_wrapping_active']['long_description'],
                'additional_arg': {},
                'widget': 'checkbox',
                'data_container': 'formatting',
                'additional_setter_arg': {}
            },
            'individual_foto_active': {
                'description': BaseGraph._formatting_description['individual_foto_active']['short_description'],
                'tooltip': BaseGraph._formatting_description['individual_foto_active']['long_description'],
                'additional_arg': {},
                'widget': 'checkbox',
                'data_container': 'formatting',
                'additional_setter_arg': {}
            },
            'individual_foto_relative_size': {
                'description': BaseGraph._formatting_description['individual_foto_relative_size']['short_description'],
                'tooltip': BaseGraph._formatting_description['individual_foto_relative_size']['long_description'],
                'additional_arg': {'range': (1, 500)},
                'data_container': 'formatting',
                'widget': 'slider',
                'additional_setter_arg': {
                    'value_decode': lambda x: x/100.,
                    'value_encode': lambda x: int(x*100)
                },
            },
        }
        for item_name, item_data in self.gui_config.items():
            if item_data['data_container'] == 'positioning':
                item_data['tab_name'] = BaseGraph._positioning_description[item_name]['tab'] if 'tab' in BaseGraph._positioning_description[item_name] else 'General Layout'
            if item_data['data_container'] == 'formatting':
                item_data['tab_name'] = BaseGraph._formatting_description[item_name]['tab'] if 'tab' in BaseGraph._formatting_description[item_name] else 'General Layout'
        NavigationView.__init__(self, _('Life Line Chart'),
                                pdata, dbstate, uistate,
                                PersonBookmarks, nav_group)
        lifelinechart.LifeLineChartGrampsGUI.__init__(
            self, self.on_childmenu_changed)
        # set needed values
        scg = self._config.get
        for key, value in self.formatting.items():
            gramps_key = 'interface.lifelineview-'+key
            if self._config.is_set('interface.lifelineview-'+key):
                if key in self.gui_config and 'value_encode' in self.gui_config[key]['additional_setter_arg']:
                    value_encode = self.gui_config[key]['additional_setter_arg']['value_encode']
                    value_decode = self.gui_config[key]['additional_setter_arg']['value_decode']
                else:
                    def value_encode(x): return x
                    def value_decode(x): return x
                self.formatting[key] = value_decode(
                    self._config.get(gramps_key))
        for key, value in self.positioning.items():
            if self._config.is_set('interface.lifelineview-'+key):
                self.positioning[key] = self._config.get(
                    'interface.lifelineview-'+key)


        self.fonttype = scg('interface.lifelineview-font_name')

        self.showid = scg('interface.lifelineview-showid')
        self.generic_filter = None
        self.alpha_filter = 0.2
        self.scrolledwindow = None

        dbstate.connect('active-changed', self.active_changed)
        dbstate.connect('database-changed', self.change_db)

        self.additional_uis.append(self.additional_ui)

        self.uistate.connect('font-changed', self.font_changed)

    def font_changed(self):
        self.format_helper.reload_symbols()
        self.update()

    def navigation_type(self):
        return 'Person'

    def get_handle_from_gramps_id(self, gid):
        """
        returns the handle of the specified object
        """
        obj = self.dbstate.db.get_person_from_gramps_id(gid)
        if obj:
            return obj.get_handle()
        else:
            return None

    def build_widget(self):
        chart = lifelinechart.LifeLineChartWidget(self.dbstate, self.uistate,
                                                  self.on_popup)
        chart.formatting = self.formatting
        chart.positioning = self.positioning
        self.axis_widget = lifelinechart.LifeLineChartAxis(self.dbstate, self.uistate, chart)
        self.set_lifeline(chart)
        chart.set_axis_widget(self.axis_widget)


        self.scrolledwindow = Gtk.ScrolledWindow()
        self.scrolledwindow.set_shadow_type(Gtk.ShadowType.IN)
        self.hadjustment = self.scrolledwindow.get_hadjustment()
        self.vadjustment = self.scrolledwindow.get_vadjustment()
        self.lifeline.show_all()
        #self.scrolledwindow.add(self.lifeline)
        chart.scrolledwindow = self.scrolledwindow


        self.vbox = Gtk.Box(homogeneous=False, spacing=4,
                            orientation=Gtk.Orientation.VERTICAL)
        self.vbox.set_border_width(4)
        self.toolbar = Gtk.Box(homogeneous=False, spacing=4,
                               orientation=Gtk.Orientation.HORIZONTAL)
        self.vbox.pack_start(self.toolbar, False, False, 0)

        # add zoom-in button
        self.zoom_in_btn = Gtk.Button.new_from_icon_name('zoom-in',
                                                         Gtk.IconSize.MENU)
        self.zoom_in_btn.set_tooltip_text(_('Zoom in'))
        self.toolbar.pack_start(self.zoom_in_btn, False, False, 1)
        self.zoom_in_btn.connect("clicked", self.lifeline.zoom_in)

        # add zoom-out button
        self.zoom_out_btn = Gtk.Button.new_from_icon_name('zoom-out',
                                                          Gtk.IconSize.MENU)
        self.zoom_out_btn.set_tooltip_text(_('Zoom out'))
        self.toolbar.pack_start(self.zoom_out_btn, False, False, 1)
        self.zoom_out_btn.connect("clicked", self.lifeline.zoom_out)

        # add original zoom button
        self.orig_zoom_btn = Gtk.Button.new_from_icon_name('zoom-original',
                                                           Gtk.IconSize.MENU)
        self.orig_zoom_btn.set_tooltip_text(_('Zoom to original'))
        self.toolbar.pack_start(self.orig_zoom_btn, False, False, 1)
        self.orig_zoom_btn.connect("clicked", self.lifeline.set_original_zoom)

        # add best fit button
        self.fit_btn = Gtk.Button.new_from_icon_name('zoom-fit-best',
                                                     Gtk.IconSize.MENU)
        self.fit_btn.set_tooltip_text(_('Zoom to best fit'))
        self.toolbar.pack_start(self.fit_btn, False, False, 1)
        self.fit_btn.connect("clicked", self.lifeline.fit_to_page)

        # add view-refresh button
        self.view_refresh_btn = Gtk.Button.new_from_icon_name('view-refresh',
                                                         Gtk.IconSize.MENU)
        self.view_refresh_btn.set_tooltip_text(_('Rebuild Data Cache'))
        self.toolbar.pack_start(self.view_refresh_btn, False, False, 1)
        self.view_refresh_btn.connect("clicked", self.lifeline.rebuild_instance_cache)

        #self.vbox.pack_start(self.scrolledwindow, True, True, 0)

        self.hbox_split_view = Gtk.Box(homogeneous=False, spacing=0,
                               orientation=Gtk.Orientation.HORIZONTAL)
        self.hbox_split_view.pack_start(self.lifeline, True, True, 0)
        self.hbox_split_view.pack_start(self.axis_widget, False, False, 0)
        self.vbox.pack_start(self.hbox_split_view, True, True, 0)


        gen_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        return self.vbox # self.scrolledwindow

    def get_stock(self):
        """
        The category stock icon
        """
        return 'gramps-pedigree'

    def get_viewtype_stock(self):
        """Type of view in category
        """
        return 'gramps-lifelinechart'

    additional_ui = [  # Defines the UI string for UIManager
        '''
      <placeholder id="CommonGo">
      <section>
        <item>
          <attribute name="action">win.Back</attribute>
          <attribute name="label" translatable="yes">_Back</attribute>
        </item>
        <item>
          <attribute name="action">win.Forward</attribute>
          <attribute name="label" translatable="yes">_Forward</attribute>
        </item>
      </section>
      <section>
        <item>
          <attribute name="action">win.HomePerson</attribute>
          <attribute name="label" translatable="yes">_Home</attribute>
        </item>
      </section>
      </placeholder>
''',
        '''
      <section id='CommonEdit' groups='RW'>
        <item>
          <attribute name="action">win.PrintView</attribute>
          <attribute name="label" translatable="yes">Print...</attribute>
        </item>
      </section>
''',
        '''
      <section id="AddEditBook">
        <item>
          <attribute name="action">win.AddBook</attribute>
          <attribute name="label" translatable="yes">_Add Bookmark</attribute>
        </item>
        <item>
          <attribute name="action">win.EditBook</attribute>
          <attribute name="label" translatable="no">%s...</attribute>
        </item>
      </section>
''' % _('Organize Bookmarks'),  # Following are the Toolbar items
        '''
    <placeholder id='CommonNavigation'>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">go-previous</property>
        <property name="action-name">win.Back</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Go to the previous object in the history</property>
        <property name="label" translatable="yes">_Back</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">go-next</property>
        <property name="action-name">win.Forward</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Go to the next object in the history</property>
        <property name="label" translatable="yes">_Forward</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">go-home</property>
        <property name="action-name">win.HomePerson</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Go to the default person</property>
        <property name="label" translatable="yes">_Home</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    </placeholder>
''',
        '''
    <placeholder id='BarCommonEdit'>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">document-save</property>
        <property name="action-name">win.SaveView</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Save the Life Line Chart View</property>
        <property name="label" translatable="yes">Save...</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    </placeholder>
    ''']

    def define_actions(self):
        """
        Required define_actions function for PageView. Builds the action
        group information required.
        """
        NavigationView.define_actions(self)

        self._add_action('SaveView', self.saveview, "<PRIMARY><SHIFT>S")
        self._add_action('PRIMARY-J', self.jump, '<PRIMARY>J')

    def build_tree(self):
        """
        Generic method called by PageView to construct the view.
        Here the tree builds when active person changes or db changes or on
        callbacks like person_rebuild, so build will be double sometimes.
        However, change in generic filter also triggers build_tree ! So we
        need to reset.
        """
        self.update()

    def active_changed(self, handle):
        """
        Method called when active person changes.
        """
        #pass
        #dummy_handle = handle
        # Reset everything but rotation angle (leave it as is)
        self.update()

    def _connect_db_signals(self):
        """
        Connect database signals.
        """
        self._add_db_signal('person-add', self.person_rebuild)
        self._add_db_signal('person-update', self.person_rebuild)
        self._add_db_signal('person-delete', self.person_rebuild)
        self._add_db_signal('person-rebuild', self.person_rebuild_bm)
        self._add_db_signal('family-update', self.person_rebuild)
        self._add_db_signal('family-add', self.person_rebuild)
        self._add_db_signal('family-delete', self.person_rebuild)
        self._add_db_signal('family-rebuild', self.person_rebuild)

    def change_db(self, db):
        """
        We selected a new database
        """
        self._change_db(db)
        if self.active:
            self.bookmarks.redraw()
        self.update()

    def update(self):
        """
        Redraw the lifeline chart
        """
        run_profiler = False
        if run_profiler:
            import cProfile
            cProfile.runctx('self.main()', globals(), locals())
        else:
            self.main()

    def goto_handle(self, handle):
        """
        Draw the lifeline chart for the active person
        """
        self.change_active(handle)
        self.main()

    def get_active(self, obj):
        """overrule get_active, to support call as in Gramplets
        """
        dummy_obj = obj
        return NavigationView.get_active(self)

    def person_rebuild(self, *args):
        """
        Redraw the lifeline chart for the person
        """
        dummy_args = args
        self.update()

    def person_rebuild_bm(self, *args):
        """Large change to person database"""
        dummy_args = args
        self.person_rebuild()
        if self.active:
            self.bookmarks.redraw()

    def saveview(self, *obj):
        """
        Save the view that is currently shown
        """

        chooser = Gtk.FileChooserDialog(
            title=_("Export View as SVG"),
            transient_for=self.uistate.window,
            action=Gtk.FileChooserAction.SAVE)
        chooser.add_buttons(_('_Cancel'), Gtk.ResponseType.CANCEL,
                            _('_Save'), Gtk.ResponseType.OK)
        chooser.set_do_overwrite_confirmation(True)

        filtering = Gtk.FileFilter()
        filtering.add_pattern("*.svg")
        chooser.set_filter(filtering)
        #default_dir = '.'#self._config.get('paths.recent-export-dir')
        #chooser.set_current_folder(default_dir)

        import os
        while True:
            value = chooser.run()
            fn = chooser.get_filename()
            if value == Gtk.ResponseType.OK:
                if fn and os.path.splitext(fn)[1].lower() in ['', '.svg']:
                    chooser.destroy()
                    break
            else:
                chooser.destroy()
                return
        # config.set('paths.recent-export-dir', os.path.split(fn)[0])
        base, extension = os.path.splitext(fn)
        if extension == '':
            fn = base + '.svg'
        self.lifeline.life_line_chart_ancestor_graph.paint_and_save(
            self.lifeline.rootpersonh, fn)

    def on_childmenu_changed(self, obj, person_handle):
        """Callback for the pulldown menu selection, changing to the person
           attached with menu item."""
        dummy_obj = obj
        self.change_active(person_handle)
        return True

    def can_configure(self):
        """
        See :class:`~gui.views.pageview.PageView
        :return: bool
        """
        return True

    def _get_configure_page_funcs(self):
        """
        Return a list of functions that create gtk elements to use in the
        notebook pages of the Configure dialog

        :return: list of functions
        """
        return [
            lambda configdialog, tab_name='General Layout': self.config_panel(configdialog, tab_name),
            lambda configdialog, tab_name='Label Configuration': self.config_panel(configdialog, tab_name)
            ]

    def config_panel(self, configdialog, tab_name):
        """
        Function that builds the widget in the configuration dialog
        """
        nrentry = 10
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)


        def my_non_weird_add_checkbox(grid, label, index, constant, start=1, stop=9,
                                      config=None, callback=None, extra_callback=None, tooltip=''):
            cb = configdialog.add_checkbox(
                grid, label, index, constant, start, stop, config, extra_callback, tooltip)
            self._config.connect(constant,
                                 callback)
            return cb

        function_mapping = {
            'spinner': configdialog.add_spinner,
            'slider': configdialog.add_slider,
            'combobox': configdialog.add_combo,
            'checkbox': my_non_weird_add_checkbox,
            'lineedit': configdialog.add_entry,
        }

        for index, (entry_name, settings) in enumerate(self.gui_config.items()):
            if settings['tab_name'] != tab_name:
                continue
            item = function_mapping[settings['widget']](
                grid, _(settings['description']),
                index,
                'interface.lifelineview-' + entry_name,
                callback=lambda *args, entry_name=entry_name, settings=settings:
                getattr(self, 'cb_update_' + settings['widget'])(
                    *args, entry_name, settings['data_container'], **settings['additional_setter_arg']),
                **settings['additional_arg']
            )
            item.set_tooltip_text(_(settings['tooltip']))

        # add reset button
        reset_button = configdialog.add_button(grid, 'Reset all settings', index + 1, None, lambda a,b=configdialog:self.reset_settings(a,b))
        return _(tab_name), grid

    def reset_settings(self, obj, widget):
        for key, value in self.formatting.items():
            gramps_key = 'interface.lifelineview-'+key
            if self._config.is_set('interface.lifelineview-'+key):
                if key in self.gui_config and 'value_encode' in self.gui_config[key]['additional_setter_arg']:
                    value_encode = self.gui_config[key]['additional_setter_arg']['value_encode']
                    value_decode = self.gui_config[key]['additional_setter_arg']['value_decode']
                else:
                    def value_encode(x): return x
                    def value_decode(x): return x
                self.formatting[key] = BaseGraph._default_formatting[key]
                self._config.set(gramps_key, value_encode(self.formatting[key]))
        for key, value in self.positioning.items():
            gramps_key = 'interface.lifelineview-'+key
            if self._config.is_set('interface.lifelineview-'+key):
                if key in self.gui_config and 'value_encode' in self.gui_config[key]['additional_setter_arg']:
                    value_encode = self.gui_config[key]['additional_setter_arg']['value_encode']
                    value_decode = self.gui_config[key]['additional_setter_arg']['value_decode']
                else:
                    def value_encode(x): return x
                    def value_decode(x): return x
                self.positioning[key] = BaseGraph._default_positioning[key]
                self._config.set(gramps_key, value_encode(self.positioning[key]))

        widget.close()
        self.update()
        self.configure()
        pass

    def config_connect(self):
        """
        Overwriten from  :class:`~gui.views.pageview.PageView method
        This method will be called after the ini file is initialized,
        use it to monitor changes in the ini file
        """
        pass

    def cb_update_spinner(self, obj, constant, value_name, container):
        value = obj.get_value_as_int()
        container = getattr(self, container)
        if container[value_name] != value:
            container[value_name] = value
            self._config.set(constant, container[value_name])
            self.update()

    def cb_update_slider(self, obj, constant, value_name, container, value_decode=lambda x: x, value_encode=lambda x: x):
        value = value_decode(obj.get_value())
        container = getattr(self, container)
        if container[value_name] != value:
            container[value_name] = value
            self._config.set(constant, value_encode(container[value_name]))
            self.update()

    def cb_update_lineedit(self, obj, constant, value_name, container, value_decode=lambda x: x, value_encode=lambda x: x):
        try:
            value = value_decode(obj.get_text())
            container = getattr(self, container)
            if container[value_name] != value:
                container[value_name] = value
                self._config.set(constant, value_encode(container[value_name]))
                self.update()
        except:
            pass

    def cb_update_checkbox(self, client, cnxn_id, entry, data, value_name, container):
        #self, obj, constant, value_name):
        value = (entry == 'True')
        container = getattr(self, container)
        if container[value_name] != value:
            container[value_name] = value
            #self._config.set(cnxn_id, container[value_name]) # is done by connection... self explaining stuff, why this is handled differently
            self.update()

    def cb_update_combobox(self, obj, constant, value_name, container, index_to_name):
        entry = obj.get_active()
        container = getattr(self, container)
        value = index_to_name(entry)
        if container[value_name] != value:
            container[value_name] = value
            self._config.set(constant, container[value_name])
            self.update()

    def cb_update_background(self, obj, constant):
        """
        Change the background
        """
        entry = obj.get_active()
        Gtk.TreePath.new_from_string('%d' % entry)
        val = int(obj.get_model().get_value(
            obj.get_model().get_iter_from_string('%d' % entry), 0))
        self._config.set(constant, val)
        self.background = val
        self.update()

    def cb_update_showid(self, client, cnxn_id, entry, data):
        """
        Called when the configuration menu changes the showid setting.
        """
        self.showid = (entry == 'True')
        self.update()

    def get_default_gramplets(self):
        """
        Define the default gramplets for the sidebar and bottombar.
        """
        return (("Person Filter",),
                ())


# fix the fact that the config is static
for key, value in list(BaseGraph._default_formatting.items()) + list(BaseGraph._default_positioning.items()):
    def config_has_key(name):
        for a, b in LifeLineChartView.CONFIGSETTINGS:
            if a == name:
                return True
        return False
    gramps_key = 'interface.lifelineview-' + key
    if not config_has_key(gramps_key):
        LifeLineChartView.CONFIGSETTINGS = LifeLineChartView.CONFIGSETTINGS + \
            ((gramps_key, value),)
