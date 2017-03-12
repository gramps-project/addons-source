#
# NetworkChart - is a plugin for GRAMPS that uses graphviz (via
#       pygraphviz) and networkx. NetworkChart uses the dot layout
#       to generate a tight family network graph.  Networkx is used
#       to trim the graph and generate individual to individual
#       highlighted paths.
#
#       Due to the memory allocation method in graphviz the dot
#       layout engine is non-deterministic.  This means that the
#       graphs generated will change slightly from run to run. A
#       small price for an extremely readable network graph that
#       shows connectivity well.
#
#       There is an issue with pygraphviz release version 1.3rc2
#       see - #https://github.com/pygraphviz/pygraphviz/issues/94
#       A temporary fix can be used per the following website
#       see - https://github.com/pygraphviz/pygraphviz/issues/62
#       Add .decode() to line 1332 in agraph.py
#       warnings.warn(b"".join(errors).decode(), RuntimeWarning)
#
#       example path
#       /usr/lib64/python3.4/site-packages/pygraphviz/agraph.py
#
# Copyright (C) 2017 Mark B. <familynetworkchart@gmail.com>
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA 02110-1301  USA
#
# version 0.0.2
"""
Family NetworkChart - Web Report plugin for GRAMPS

Generates a Family Network Chart Using pygraphviz dot layout engine.
Uses networkx python module to calculate paths and trim tree.

"""

#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
from operator import itemgetter
import itertools
import networkx as nx
from networkx import dfs_edges
import os, copy

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale, conv_to_unicode
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#------------------------------------------------------------------------
#
# gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.display.name import displayer as global_name_display
from gramps.gen.datehandler import displayer as global_date_display
from gramps.gen import datehandler
#from gramps.gui.dialog import ErrorDialog
from gramps.gen.lib.person import Person
from gramps.gen.plug.menu import (ColorOption, NumberOption, PersonOption,
                                  EnumeratedListOption, DestinationOption,
                                  PersonListOption, StringOption,
                                  BooleanOption)
from gramps.gen.config import config
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import MenuReportOptions
from gramps.gui.dialog import QuestionDialog2

# TODO
# --- For Future Versions ---
# Respect Family & Event Privacy settings. Already respect Individual
# Non-blocking run in thread

#------------------------------------------------------------------------
#
# NetworkChartReport
#
#------------------------------------------------------------------------
class NetworkChartReport(Report):
    """
    Network Chart Report class
    """
    def __init__(self, database, options, user):
        """
        Create a Family NetworkChart object that produces the
        Family NetworkChart report.

        The arguments are:

        database        - the GRAMPS database instance
        options         - instance of the Options class for this report
        user            - a gen.user.User() instance (UNUSED)

        """
        Report.__init__(self, database, options, user)
        self.map = {}
        self.database = database
        menu = options.menu

        self.font_chart = menu.get_option_by_name('font_chart').get_value()
        self.rank_sep = menu.get_option_by_name('rank_sep').get_value()
        self.top_title = menu.get_option_by_name('top_title').get_value()
        self.b_nobackground = menu.get_option_by_name('b_nobackground').get_value()
        self.b_node_clues = menu.get_option_by_name('b_node_clues').get_value()
        self.graph_splines = menu.get_option_by_name('graph_splines').get_value()
        self.include_urls = menu.get_option_by_name('include_urls').get_value()
        self.url_prefix_suffix = menu.get_option_by_name('url_prefix_suffix').get_value()
        self.rank_dir = menu.get_option_by_name('rank_dir').get_value()

        self.cfill_male = menu.get_option_by_name('cfill_male').get_value()
        self.cfill_male_alpha = menu.get_option_by_name('cfill_male_alpha').get_value()
        self.cedge_male = menu.get_option_by_name('cedge_male').get_value()
        self.cfill_female = menu.get_option_by_name('cfill_female').get_value()
        self.cfill_female_alpha = menu.get_option_by_name('cfill_female_alpha').get_value()
        self.cedge_female = menu.get_option_by_name('cedge_female').get_value()
        self.cnone = menu.get_option_by_name('cnone').get_value()
        self.cfill_none_alpha = menu.get_option_by_name('cfill_none_alpha').get_value()
        self.cline_connector = menu.get_option_by_name('cline_connector').get_value()
        self.cline_marriage = menu.get_option_by_name('cline_marriage').get_value()
        self.cline_highlight = menu.get_option_by_name('cline_highlight').get_value()
        self.cedge_trim = menu.get_option_by_name('cedge_trim').get_value()

        self.b_show_private_records = menu.get_option_by_name('b_show_private_records').get_value()
        self.b_round_bday = menu.get_option_by_name('b_round_bday').get_value()
        self.i_round_year = menu.get_option_by_name('i_round_year').get_value()
        self.b_round_marr = menu.get_option_by_name('b_round_marr').get_value()
        self.i_round_marr = menu.get_option_by_name('i_round_marr').get_value()
        self.b_middle_initials = menu.get_option_by_name('b_middle_initials').get_value()
        self.i_middle_initials = menu.get_option_by_name('i_middle_initials').get_value()

        self.b_trim_children = menu.get_option_by_name('b_trim_children').get_value()
        self.trim_list_children = menu.get_option_by_name('trim_list_children').get_value()
        self.b_trim_parents = menu.get_option_by_name('b_trim_parents').get_value()
        self.trim_list_parents = menu.get_option_by_name('trim_list_parents').get_value()
        self.b_trim_groups = menu.get_option_by_name('b_trim_groups').get_value()
        self.trim_groups_size = menu.get_option_by_name('trim_groups_size').get_value()

        self.path_start_end = menu.get_option_by_name('path_start_end').get_value()
        self.show_highlight = menu.get_option_by_name('show_highlight').get_value()
        self.show_path = menu.get_option_by_name('show_path').get_value()
        self.center_person = menu.get_option_by_name('center_person').get_value()
        self.b_center_person = menu.get_option_by_name('b_center_person').get_value()
        self.center_radius = menu.get_option_by_name('center_radius').get_value()
        self.b_highlight_center = menu.get_option_by_name('b_highlight_center').get_value()

        self.b_confirm_overwrite = menu.get_option_by_name('b_confirm_overwrite').get_value()
        self.file_type = menu.get_option_by_name('file_type').get_value()
        self.b_use_handle = menu.get_option_by_name('b_use_handle').get_value()

        self.dest_path = conv_to_unicode(menu.get_option_by_name('dest_path').get_value(), 'utf8')
        self.dest_file = conv_to_unicode(menu.get_option_by_name('dest_file').get_value(), 'utf8')
        self.destprefix, self.destext = os.path.splitext(os.path.basename(self.dest_file))
        file_ext = str("%s."+self.file_type)
        self.fpath_output = conv_to_unicode(os.path.join(self.dest_path, "",
                                                         file_ext % (self.destprefix)))
        self.cancel = menu.cancel

        self._name_display = copy.deepcopy(global_name_display)
        name_format = menu.get_option_by_name("name_format").get_value()
        if name_format != 0:
            self._name_display.set_default_format(name_format)

        self._datedisplay = copy.deepcopy(global_date_display)
        date_format = menu.get_option_by_name("date_format").get_value()
        if date_format != 0:
            self._datedisplay.set_format(date_format)

    def get_network(self):
        """
        Get person, family, and child data to build network.
        """
        person = []
        edge_marriage = []
        edge_child = []

        try:
            i_round_year = int(float(self.i_round_year))
        except ValueError:
            i_round_year = 9999
        try:
            i_round_marr = int(float(self.i_round_marr))
        except ValueError:
            i_round_marr = 9999
        try:
            i_middle_initials = int(float(self.i_middle_initials))
        except ValueError:
            i_middle_initials = 9999

        for entry in self.database.get_person_cursor():
            handle = entry[0] # individual = entry[1]
            p_person = self.database.get_person_from_handle(handle)
            person_gref = p_person.get_gramps_id()
            p_privacy = p_person.get_privacy()
            if p_person.urls:
                p_url = p_person.urls[0].get_path()
            else:
                p_url = ""

            name = self._name_display.display(p_person)

            bday_index = p_person.birth_ref_index
            dday_index = p_person.death_ref_index

            if bday_index > -1:
                bday_handle = p_person.get_event_ref_list()[bday_index].ref
                h_event = self.database.get_event_from_handle(bday_handle)
                fmt_bdate = self._datedisplay.display_formatted(h_event.get_date_object())
                if len(fmt_bdate.strip()) < 1:
                    fmt_bdate = _('unk')
                if fmt_bdate.strip() == '0000-00-00':
                    fmt_bdate = _('unk')
                if h_event.get_type().is_birth():
                    try:
                        if self.b_round_bday:
                            year = h_event.get_date_object().get_year()
                            if year > i_round_year:
                                bday = _('b.')+str(year)[0:3]+"0's"
                            else:
                                bday = _('b.') + fmt_bdate
                        else:
                            bday = _('b.') + fmt_bdate
                        if self.b_middle_initials:
                            year = h_event.get_date_object().get_year()
                            if year > i_middle_initials:
                                pfns = p_person.get_primary_name().get_first_name()
                                given_names = pfns.split(' ')
                                if len(given_names) > 1:
                                    for i in given_names[1::]:
                                        name = name.replace(i.strip(), i[0]+'.', 1)
                    except NameError:
                        bday = _('b.') + _('unk')
            else:
                bday = _('b.') + _('unk')

            if dday_index > -1:
                dday_handle = p_person.get_event_ref_list()[dday_index].ref
                h_event = self.database.get_event_from_handle(dday_handle)
                fmt_ddate = self._datedisplay.display_formatted(h_event.get_date_object())
                if len(fmt_ddate.strip()) < 1:
                    fmt_ddate = _('unk')
                if fmt_ddate.strip() == '0000-00-00':
                    fmt_ddate = _('unk')
                if h_event.get_type().is_death():
                    try:
                        dday = _('d.') + fmt_ddate
                    except NameError:
                        dday = _('d.') + _('unk')
            else:
                dday = _('d.') + _('unk')

            gender = p_person.get_gender()
            person = person + [[person_gref, name, bday, dday, gender, p_privacy, p_url]]

        for handle, family in self.database.get_family_cursor():
            family_gref = str(family[1])
            f_family = self.database.get_family_from_handle(handle)

            hfather = self.database.get_person_from_handle(
                f_family.get_father_handle())
            if hfather is not None:
                father_gref = str(
                    self.database.get_person_from_handle(
                        f_family.get_father_handle()).get_gramps_id())
            else:
                father_gref = ''

            hmother = self.database.get_person_from_handle(
                f_family.get_mother_handle())
            if hmother is not None:
                mother_gref = str(
                    self.database.get_person_from_handle(
                        f_family.get_mother_handle()).get_gramps_id())
            else:
                mother_gref = ''

            # Get edge_marriage
            h_events = f_family.get_event_list() #get_event_ref_list()
            if len(h_events) > 0:
                for handle in h_events:
                    i_event = self.database.get_event_from_handle(handle)
                    fmt_mdate = self._datedisplay.display_formatted(i_event.get_date_object())
                    if len(fmt_mdate.strip()) < 1:
                        fmt_mdate = _('unk')
                    if fmt_mdate.strip() == '0000-00-00':
                        fmt_mdate = _('unk')
                    if i_event.get_type().is_marriage():
                        try:
                            if self.b_round_marr:
                                year = i_event.get_date_object().get_year()
                                if year > i_round_marr:
                                    marriage_date = _('m.')+str(year)[0:3]+"0's"
                                else:
                                    marriage_date = _('m.') + fmt_mdate
                            else:
                                marriage_date = _('m.') + fmt_mdate
                        except NameError:
                            marriage_date = _('m.') + _('unk')
                        edge_marriage = edge_marriage + [[family_gref,
                                                          father_gref,
                                                          mother_gref,
                                                          marriage_date]]
            else:
                marriage_date = _('m.') + _('unk')
                edge_marriage = edge_marriage + [[family_gref,
                                                  father_gref,
                                                  mother_gref,
                                                  marriage_date]]

            # Get edge_child
            children_refs = f_family.get_child_ref_list()
            for i in children_refs:
                child_gref = str(
                    self.database.get_person_from_handle(
                        i.get_reference_handle()).get_gramps_id())
                if mother_gref != '':
                    edge_child = edge_child + [[family_gref,
                                                mother_gref,
                                                child_gref]]
                elif father_gref != '':
                    edge_child = edge_child + [[family_gref,
                                                father_gref,
                                                child_gref]]

        return(person, edge_marriage, edge_child)

    def write_report(self):
        """
        The routine that actually creates the report.
        """
        trim_list_children = [str(i.strip()) for i in str(self.trim_list_children).split(' ')
                              if len(i) > 0]
        trim_list_parents = [str(i.strip()) for i in str(self.trim_list_parents).split(' ')
                             if len(i) > 0]
        font = self.font_chart
        cfill_male = (self.cfill_male + '{0:x}'.format(int(self.cfill_male_alpha)).upper())
        cfill_female = (self.cfill_female + '{0:x}'.format(int(self.cfill_female_alpha)).upper())
        cedge_male = self.cedge_male + 'DD'
        cedge_female = self.cedge_female + 'DD'
        cnone = (self.cnone + '{0:x}'.format(int(self.cfill_none_alpha)).upper())
        cline_connector = self.cline_connector + 'FF'
        cline_marriage = self.cline_marriage + 'DD'
        cline_highlight = self.cline_highlight + 'DD'
        cedge_trim = self.cedge_trim + 'FF'
        top_title = self.top_title
        rank_dir = self.rank_dir
        include_urls = self.include_urls
        center_person = self.center_person.strip()

        try:
            center_radius = int(self.center_radius)
            if center_radius < 1:
                center_radius = 1
        except ValueError:
            center_radius = 1

        try:
            rank_sep = float(self.rank_sep)
            if rank_sep > 5.0:
                rank_sep = 5.0
            if rank_sep < 0.1:
                rank_sep = 0.1
        except ValueError:
            rank_sep = 0.6

        try:
            trim_groups_size = int(self.trim_groups_size)
            if trim_groups_size < 2:
                trim_groups_size = 2
        except ValueError:
            trim_groups_size = 2

        try:
            url_prefix = self.url_prefix_suffix.split(',')[0]
        except IndexError:
            url_prefix = ""
        try:
            url_suffix = self.url_prefix_suffix.split(',')[1]
        except IndexError:
            url_suffix = ""
        fillnode = not self.b_nobackground

        person, edge_marriage, edge_child = self.get_network()

        person = sorted(person, key=itemgetter(0))
        edge_marriage = sorted(edge_marriage, key=itemgetter(0))
        edge_child = sorted(edge_child, key=itemgetter(0, 2))

        G = nx.DiGraph()
        G.clear()

        for i in edge_marriage:
            if i[1] and i[2]:
                G.add_edge(i[1], i[2])
            elif i[1]:
                G.add_node(i[1])
            elif i[2]:
                G.add_node(i[2])
            else:
                pass

        for i in person:
            if i[4] == Person.MALE:
                node_edge_color = cedge_male
                node_fill_color = cfill_male
                node_edge_thickness = 2.0
                if self.b_node_clues:
                    if self.b_nobackground:
                        node_style = "diagonals"
                    else:
                        node_style = "filled,diagonals"
                else:
                    if self.b_nobackground:
                        node_style = "rounded"
                    else:
                        node_style = "filled"
            elif i[4] == Person.FEMALE:
                node_edge_color = cedge_female
                node_fill_color = cfill_female
                node_edge_thickness = 2.0
                if self.b_node_clues:
                    if self.b_nobackground:
                        node_style = "rounded"
                    else:
                        node_style = "filled"
                else:
                    if self.b_nobackground:
                        node_style = "rounded"
                    else:
                        node_style = "filled"
            else:
                node_edge_color = "#000000FF"
                node_fill_color = cnone
                node_edge_thickness = 0.5
                if self.b_node_clues:
                    if self.b_nobackground:
                        node_style = "rounded,dotted"
                    else:
                        node_style = "filled,rounded,dotted"
                else:
                    if self.b_nobackground:
                        node_style = "rounded"
                    else:
                        node_style = "filled,rounded"

            if i[0] in trim_list_children:
                if self.b_trim_children:
                    node_edge_color = cedge_trim
                    node_style = node_style + ",dashed"
                    node_edge_thickness = 2.0
            if i[0] in trim_list_parents:
                if self.b_trim_parents:
                    node_edge_color = cedge_trim
                    node_style = node_style + ",dashed"
                    node_edge_thickness = 2.0
            try:
                if i[5]:
                    if self.b_show_private_records:
                        lbl = '\\n'.join(i[1:4])
                    else:
                        lbl = '\\n'.join(['Private Record', ' '])
                        i[6] = ''
                else:
                    lbl = '\\n'.join(i[1:4])
                if lbl:
                    if G.has_node(i[0]):
                        G.node[i[0]]['label'] = lbl
                        G.node[i[0]]['color'] = node_edge_color
                        G.node[i[0]]['penwidth'] = node_edge_thickness
                        if include_urls == "include":
                            G.node[i[0]]['URL'] = i[6]
                        elif include_urls == "dynamic":
                            if self.b_use_handle:
                                h_ref = str(self.database.get_person_from_gramps_id(i[0]).get_handle())
                                G.node[i[0]]['URL'] = (url_prefix + h_ref + url_suffix)
                            else:
                                G.node[i[0]]['URL'] = (url_prefix + i[0] + url_suffix)
                        elif include_urls == "static":
                            G.node[i[0]]['URL'] = url_prefix
                        else:
                            G.node[i[0]]['URL'] = ""
                        if fillnode:
                            G.node[i[0]]['fillcolor'] = node_fill_color
                        G.node[i[0]]['style'] = node_style
                    else:
                        if fillnode:
                            G.add_node(i[0], color=node_edge_color,
                                       fillcolor=node_fill_color,
                                       penwidth=node_edge_thickness)
                        else:
                            G.add_node(i[0], color=node_edge_color,
                                       penwidth=node_edge_thickness)
                        G.node[i[0]]['label'] = lbl
                        if include_urls == "include":
                            G.node[i[0]]['URL'] = i[6]
                        elif include_urls == "dynamic":
                            if self.b_use_handle:
                                h_ref = str(self.database.get_person_from_gramps_id(i[0]).get_handle())
                                G.node[i[0]]['URL'] = (url_prefix + h_ref + url_suffix)
                            else:
                                G.node[i[0]]['URL'] = (url_prefix + i[0] + url_suffix)
                        elif include_urls == "static":
                            G.node[i[0]]['URL'] = url_prefix
                        else:
                            G.node[i[0]]['URL'] = ""
                        G.node[i[0]]['style'] = node_style
            except Exception:
                raise

        A = nx.drawing.nx_agraph.to_agraph(G)
        A.node_attr['shape'] = 'Mrecord'
        A.node_attr['width'] = '0.5'
        A.node_attr['height'] = '0.5'

        for i in edge_marriage:
            if i[1] and i[2]:
                A.add_edge([i[1], i[2]], arrowsize=0.0,
                           color=cline_marriage, penwidth=2.0,
                           style='dashed', headlabel=i[3],
                           fontsize=6, fontname=font)
                G.add_edge(i[1], i[2], headlabel=i[3]) # make G and A the same

        for i in edge_child:
            try:
                A.add_edge([i[1], i[2]], arrowsize=0.7,
                           color=cline_connector)
                G.add_edge(i[1], i[2]) # make G and A the same
            except Exception:
                raise

        if self.b_highlight_center:
            A.get_node(center_person).attr['fillcolor'] = '#FFFD6BFF'
            G.node[center_person]['fillcolor'] = '#FFFD6BFF'

        if self.b_trim_groups:
            groups_gen = nx.connected_components(G.to_undirected())
            groups = list(groups_gen)
            main_branch = max(groups, key=len)
            main_branch_len = len(main_branch)
            if trim_groups_size > main_branch_len:
                trim_groups_size = main_branch_len
            for selected_group in groups:
                if len(selected_group) < trim_groups_size:
                    A.remove_nodes_from(selected_group)
                    G.remove_nodes_from(selected_group)

        if self.b_center_person:
            too_far = []
            in_circle = nx.ego_graph(G, center_person, radius=center_radius, center=True,
                                     undirected=True, distance=None)
            for inode in G.nodes():
                if inode not in in_circle:
                    too_far.append(inode)
            if len(too_far) > 0:
                A.remove_nodes_from(too_far)
                G.remove_nodes_from(too_far)

        trim_children = [] # This only works because we used networkx DiGraph type
        if self.b_trim_children:
            for inode in trim_list_children:
                if G.has_node(inode):
                    for edge in dfs_edges(G, inode):
                        if edge[0] not in trim_list_children:
                            trim_children.append(edge[0])
                        if edge[1] not in trim_list_children:
                            trim_children.append(edge[1])
            trim_children = sorted(set(trim_children))[::-1]
            A.remove_nodes_from(trim_children)
            G.remove_nodes_from(trim_children)

        trim_parents = []
        if self.b_trim_parents:
            G_parents = G.reverse()
            for inode in trim_list_parents:
                if G.has_node(inode):
                    for edge in dfs_edges(G_parents, inode):
                        if edge[0] not in trim_list_parents:
                            trim_parents.append(edge[0])
                        if edge[1] not in trim_list_parents:
                            trim_parents.append(edge[1])
            trim_parents = sorted(set(trim_parents))[::-1]
            A.remove_nodes_from(trim_parents)
            G.remove_nodes_from(trim_parents)

        if self.show_highlight == "Direct":
            path_list = [
                str(i.strip()) for i in str(self.path_start_end).split(' ')
                if len(i) > 0]
            if len(path_list) > 1:
                start_path = path_list[0]
                end_path = path_list[1]
                if G.has_node(start_path) and G.has_node(end_path):
                    if nx.has_path(G, start_path, end_path):
                        all_paths = nx.all_simple_paths(G, start_path, end_path)
                        for highlighted_path in all_paths:
                            for i in zip(highlighted_path, highlighted_path[1::]):
                                A.add_edge([i[0], i[1]], arrowsize=0.0, penwidth=5.0,
                                           color=cline_highlight)
                                G.add_edge(i[0], i[1]) # make G and A the same
                    elif nx.has_path(G, end_path, start_path):
                        all_paths = nx.all_simple_paths(G, end_path, start_path)
                        for highlighted_path in all_paths:
                            for i in zip(highlighted_path, highlighted_path[1::]):
                                A.add_edge([i[0], i[1]], arrowsize=0.0, penwidth=5.0,
                                           color=cline_highlight)
                                G.add_edge(i[0], i[1]) # make G and A the same
                    else:
                        pass # NO Path Found Don't highlight anything
        elif self.show_highlight == "Any":
            path_list = [
                str(i.strip()) for i in str(self.path_start_end).split(' ')
                if len(i) > 0]
            if len(path_list) > 1:
                start_path = path_list[0]
                end_path = path_list[1]
                if G.has_node(start_path) and G.has_node(end_path):
                    if nx.has_path(G.to_undirected(), start_path, end_path):
                        all_paths = nx.all_simple_paths(G.to_undirected(),
                                                        start_path,
                                                        end_path)
                        for highlighted_path in all_paths:
                            for i in zip(highlighted_path, highlighted_path[1::]):
                                if G.has_edge(i[0], i[1]):
                                    A.add_edge([i[0], i[1]], arrowsize=0.0,
                                               penwidth=5.0,
                                               color=cline_highlight)
                                    G.add_edge(i[0], i[1]) # make G and A the same
                                elif G.has_edge(i[1], i[0]):
                                    A.add_edge([i[1], i[0]], arrowsize=0.0,
                                               penwidth=5.0,
                                               color=cline_highlight)
                                    G.add_edge(i[1], i[0]) # make G and A the same
                                else:
                                    pass
                    else:
                        pass

        if self.show_path == "Direct":
            path_list = [
                str(i.strip()) for i in str(self.path_start_end).split(' ')
                if len(i) > 0]
            if len(path_list) > 1:
                start_path = path_list[0]
                end_path = path_list[1]
                if G.has_node(start_path) and G.has_node(end_path):
                    if nx.has_path(G, start_path, end_path):
                        all_paths = nx.all_simple_paths(G,
                                                        start_path,
                                                        end_path)
                        short_list = list(set(itertools.chain(*all_paths)))
                        for i in G.nodes():
                            if i not in short_list:
                                G.remove_node(i)
                                A.remove_node(i)
                    elif nx.has_path(G, end_path, start_path):
                        all_paths = nx.all_simple_paths(G,
                                                        end_path,
                                                        start_path)
                        short_list = list(set(itertools.chain(*all_paths)))
                        for i in G.nodes():
                            if i not in short_list:
                                G.remove_node(i)
                                A.remove_node(i)
                    else: # NO PATH FOUND
                        for i in G.nodes():
                            G.remove_node(i)
                            A.remove_node(i)
        elif self.show_path == "Any":
            path_list = [
                str(i.strip()) for i in str(self.path_start_end).split(' ')
                if len(i) > 0]
            if len(path_list) > 1:
                start_path = path_list[0]
                end_path = path_list[1]
                if G.has_node(start_path) and G.has_node(end_path):
                    if nx.has_path(G.to_undirected(), start_path, end_path):
                        all_paths = nx.all_simple_paths(G.to_undirected(),
                                                        start_path,
                                                        end_path)
                        short_list = list(set(itertools.chain(*all_paths)))
                        for i in G.nodes():
                            if i not in short_list:
                                G.remove_node(i)
                                A.remove_node(i)
                    else: # NO PATH FOUND
                        for i in G.nodes():
                            G.remove_node(i)
                            A.remove_node(i)

        A.node_attr.update(fontname=font)
        A.node_attr.update(fontsize=12)
        A.node_attr.update(colorscheme="RGBA")
        if fillnode:
            A.node_attr.update(style="filled")

        A.edge_attr.update(colorscheme="RGBA")
        A.edge_attr.update(fontname=font)
        A.edge_attr.update(fontsize=6)
        A.edge_attr.update(labelfontcolor=cline_marriage)
        A.edge_attr.update(labelfloat=1)

        A.graph_attr.update(bgcolor="transparent")
        A.graph_attr.update(URL=top_title)
        A.graph_attr.update(ranksep=rank_sep)
        A.graph_attr.update(colorscheme="RGBA")
        A.graph_attr.update(fontname=font)
        A.graph_attr.update(fontnames="svg")
        A.graph_attr.update(fontsize=20)
        A.graph_attr.update(label=top_title)
        A.graph_attr.update(labelloc="top")
        A.graph_attr.update(concentrate=False)
        A.graph_attr.update(ratio="compress")
        A.graph_attr.update(splines=self.graph_splines)
        A.graph_attr.update(comment="Gramps via NetworkChart plugin by Mark B.")
        A.graph_attr.update(dpi=72)
        A.graph_attr.update(overlap=0)
        A.graph_attr.update(rankdir=rank_dir)

        if not self.cancel:
            A.draw(self.fpath_output, prog="dot", format=self.file_type)

#------------------------------------------------------------------------
#
# NetworkChartOptions
#
#------------------------------------------------------------------------
class NetworkChartOptions(MenuReportOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, dbase):
        #------- initialize inifile -------
        self.inifile = config.register_manager("NetworkChart")
        self.inifile.load()
        #------- initialize inifile -------
        self._dbase = dbase
        self.center_radius = self.trim_groups_size = self.b_highlight_center = None
        self.cancel = self.b_center_person = self.center_person = self.highlight_center = None
        self.menu = self.path_start_end = self.show_path = self.show_highlight = None
        self.b_trim_parents = self.s_dbname = self.b_trim_groups = self.dest_path = None
        self.trim_list_parents = self.trim_list_children = self.dest_file = self.top_title = None
        self.b_confirm_overwrite = self.b_trim_children = self.file_type = None
        MenuReportOptions.__init__(self, name, dbase)

    def add_user_options(self):
        """
        Generic method to add user options to the menu. Doesn't seem to be called.
        But needed for the options to be saved.
        """

    def parse_user_options(self):
        """
        Load the changed values into the saved options. Used to catch close of dialog.
        """
        for name in self.menu.get_all_option_names():
            option = self.menu.get_option_by_name(name)
            self.options_dict[name] = option.get_value()
        fpath = (str(self.dest_path.get_value()) + os.path.sep + str(self.dest_file.get_value())
                 + '.' + str(self.file_type.get_value()))
        if os.path.isfile(fpath):
            if self.b_confirm_overwrite.get_value():
                q_dia = QuestionDialog2(_("File exists. Overwrite?"),
                                        fpath,
                                        _('Cancel'),
                                        _('Yes'))
                if q_dia.run(): # Cancel
                    self.menu.cancel = True
                else: # Yes Overwrite
                    self.menu.cancel = False
            else: # Just overwrite file
                self.menu.cancel = False
        elif self.dest_file.get_value() == '': # No file name so cancel
            self.menu.cancel = True
        else: # Filename good and not overwriting
            self.menu.cancel = False
        #------- stop inifile -------
        dbname = self.s_dbname.get_value().lower()
        self.inifile.set(dbname + ".trim_list_children", self.trim_list_children.get_value())
        self.inifile.set(dbname + ".trim_list_parents", self.trim_list_parents.get_value())
        self.inifile.set(dbname + ".path_start_end", self.path_start_end.get_value())
        self.inifile.set(dbname + ".b_trim_children", str(int(self.b_trim_children.get_value())))
        self.inifile.set(dbname + ".b_trim_parents", str(int(self.b_trim_parents.get_value())))
        self.inifile.set(dbname + ".b_trim_groups", str(int(self.b_trim_groups.get_value())))
        self.inifile.set(dbname + ".trim_groups_size", self.trim_groups_size.get_value())
        self.inifile.set(dbname + ".show_path", self.show_path.get_value())
        self.inifile.set(dbname + ".show_highlight", self.show_highlight.get_value())
        self.inifile.set(dbname + ".b_center_person", str(int(self.b_center_person.get_value())))
        self.inifile.set(dbname + ".b_highlight_center", str(int(self.b_highlight_center.get_value())))
        self.inifile.set(dbname + ".center_person", self.center_person.get_value())
        self.inifile.set(dbname + ".center_radius", self.center_radius.get_value())

        ini_sections = self.inifile.get_sections()
        for section in ini_sections:
            ini_settings = self.inifile.get_section_settings(section)
            for setting in ini_settings:
                ikey = section + "." + setting
                self.inifile.register(ikey, "")
                self.inifile.set(ikey, self.inifile.get(ikey))

        self.inifile.save()
        #------- stop inifile -------

    def add_menu_options(self, menu):
        """
        Add options to the menu for the network chart.
        """
        category_name = " " + _("Main") + " "

        fmt_list = global_name_display.get_name_format()
        name_format = EnumeratedListOption(_("Name format"), 2)
        name_format.add_item(2, _("Default (Given Surname Suffix)"))
        for entry in fmt_list:
            name_format.add_item(entry[0], entry[1])
        name_format.set_help(_("Select the format to display names"))
        menu.add_option(category_name, "name_format", name_format)

        dt_fmt_list = datehandler.get_date_formats()
        date_format = EnumeratedListOption(_("Date format"), 0)
        for index, entry in enumerate(dt_fmt_list):
            date_format.add_item(index, entry)
        date_format.set_help(_("Select the format to display dates"))
        menu.add_option(category_name, "date_format", date_format)

        graph_splines = EnumeratedListOption(_("Graph Style"), "ortho")
        splines_options = ["ortho", "polyline", "spline"]
        s_graph_splines_names = [_("Orthogonal (right angles in connectors)"),
                                 _("Straight (no right angles in connectors)"),
                                 _("Curved (curved and straight connectors)")]
        graph_splines.add_item(splines_options[0], _("Default (Orthogonal)"))
        for i in range(0, len(splines_options)):
            graph_splines.add_item(splines_options[i],
                                   s_graph_splines_names[i])
        graph_splines.set_help(_("Select the graph line connector format."))
        menu.add_option(category_name, "graph_splines", graph_splines)

        rank_dir = EnumeratedListOption(_("Graph Direction"), "TB")
        rank_dir_options = ["TB", "LR", "BT", "RL"]
        s_rank_dir_names = [_("Top to Bottom"), _("Left to Right"),
                            _("Bottom to Top"), _("Right to Left")]
        rank_dir.add_item(rank_dir_options[0], _("Default (Top to Bottom)"))
        for i in range(0, len(rank_dir_options)):
            rank_dir.add_item(rank_dir_options[i], s_rank_dir_names[i])
        rank_dir.set_help(_("Select the graph direction."))
        menu.add_option(category_name, "rank_dir", rank_dir)

        include_urls = EnumeratedListOption(_("URL Style"), "include")
        urls_options = ["include", "dynamic", "static", "dontinclude"]
        s_urls_names = [_("Include URLs from database."),
                        _("Dynamic URL = Prefix + GrampID + Suffix"),
                        _("Static URL = Prefix"),
                        _("Don't include URLs")]
        include_urls.add_item(urls_options[0], _("Default (include)"))
        for i in range(0, len(urls_options)):
            include_urls.add_item(urls_options[i], s_urls_names[i])
        include_urls.set_help(_("Select URL style."))
        menu.add_option(category_name, "include_urls", include_urls)

        url_prefix_suffix = StringOption(_("URL Prefix,Suffix"), "")
        url_prefix_suffix.set_help(_("Enter the Prefix,Suffix (use comma)\n"
                                     "for dynamically generated URLs.\n"
                                     "URL = Prefix + GrampsID + Suffix."))
        menu.add_option(category_name, "url_prefix_suffix", url_prefix_suffix)

        font_chart = StringOption(_("Enter Font Name"), "White Rabbit")
        font_chart.set_help(_("Enter the primary font style for the chart.\n"
                              "Must already be installed.\nWhite Rabbit can "
                              "be obtained from\n"
                              "https://www.fontsquirrel.com/fonts/white-rabbit"))
        menu.add_option(category_name, "font_chart", font_chart)

        rank_sep = StringOption(_("Spacing (inch)"), "0.5")
        rank_sep.set_help(_('Enter the seperation distance between '
                            '"Generations" in inches (0.1-5.0).'))
        menu.add_option(category_name, "rank_sep", rank_sep)

        self.top_title = StringOption(_("Enter Chart Title"), self._dbase.get_dbname())
        self.top_title.set_help(_("Set the title of the chart."))
        menu.add_option(category_name, "top_title", self.top_title)

        self.dest_path = DestinationOption(_("Folder"), config.get('paths.website-directory'))
        self.dest_path.set_help(_("The destination folder for generated files."))
        self.dest_path.set_directory_entry(True)
        menu.add_option(category_name, "dest_path", self.dest_path)

        s_namebase = _("network")
        fname = self._dbase.get_dbname() + "_" + s_namebase

        self.dest_file = DestinationOption(_("Filename"), fname)
        self.dest_file.set_help(_("The filename for the generated svg network chart."))
        self.dest_file.set_directory_entry(False)
        self.dest_file.set_extension('.svg')
        menu.add_option(category_name, "dest_file", self.dest_file)
        self.dest_file.connect('value-changed', self.cb_initialize)

        b_node_clues = BooleanOption(_("Different node shapes/edges for gender."), False)
        b_node_clues.set_help(_("Node differences for gender."))
        menu.add_option(category_name, "b_node_clues", b_node_clues)

        category_name = " " + _("Color") + " "

        cfill_male = ColorOption(_("Male Background"), "#6495ED")
        cfill_male.set_help(_("RGB-color for male box background."))
        menu.add_option(category_name, "cfill_male", cfill_male)

        cfill_male_alpha = NumberOption(_("Male Background Alpha"), 24, 0, 255, step=1)
        cfill_male_alpha.set_help(_("Alpha for Male box background"
                                    " (transparent=0, solid=255)."))
        menu.add_option(category_name, "cfill_male_alpha", cfill_male_alpha)

        cedge_male = ColorOption(_("Male Box Edge"), "#000000")
        cedge_male.set_help(_("RGB-color for Male box edge."))
        menu.add_option(category_name, "cedge_male", cedge_male)

        cfill_female = ColorOption(_("Female Background"), "#FF69B4")
        cfill_female.set_help(_("RGB-color for Female box background."))
        menu.add_option(category_name, "cfill_female", cfill_female)

        cfill_female_alpha = NumberOption("Female Background Alpha", 24, 0, 255, step=1)
        cfill_female_alpha.set_help(_("Alpha for Female box background "
                                      "(transparent=0, solid=255)."))
        menu.add_option(category_name, "cfill_female_alpha", cfill_female_alpha)

        cedge_female = ColorOption(_("Female Box Edge"), "#000000")
        cedge_female.set_help(_("RGB-color for Female box background."))
        menu.add_option(category_name, "cedge_female", cedge_female)

        cnone = ColorOption(_("Other Background"), "#DCDCDC")
        cnone.set_help(_("RGB-color for other box background."))
        menu.add_option(category_name, "cnone", cnone)

        cfill_none_alpha = NumberOption(_("Other Background Alpha"), 64, 0, 255, step=1)
        cfill_none_alpha.set_help(_("Alpha for Other box background "
                                    "(transparent=0, solid=255)."))
        menu.add_option(category_name, "cfill_none_alpha", cfill_none_alpha)

        cline_connector = ColorOption(_("Family Connector Line"), "#000000")
        cline_connector.set_help(_("RGB-color for family connector line."))
        menu.add_option(category_name, "cline_connector", cline_connector)

        cline_marriage = ColorOption(_("Marriage Connector Line"), "#2E8B57")
        cline_marriage.set_help(_("RGB-color for marriage connector line."))
        menu.add_option(category_name, "cline_marriage", cline_marriage)

        cline_highlight = ColorOption(_("Highlight Connector Line"), "#0000FF")
        cline_highlight.set_help(_("RGB-color for the highlighted path "
                                   "between two individuals.  If the graph."
                                   "inverts, reverse the order to change."))
        menu.add_option(category_name, "cline_highlight", cline_highlight)

        cedge_trim = ColorOption(_("Trim Box Edge"), "#993333")
        cedge_trim.set_help(_("RGB-color for box edge that has been trimmed."))
        menu.add_option(category_name, "cedge_trim", cedge_trim)

        b_nobackground = BooleanOption(_("Remove color background on all nodes."), False)
        b_nobackground.set_help(_("Removes color background for individuals (nodes) on chart."))
        menu.add_option(category_name, "b_nobackground", b_nobackground)

        category_name = " " + _("Privacy") + " "

        i_round_year = StringOption(_("Enter year to start\n"
                                      "replacing birthday\nby decade"), '')
        i_round_year.set_help(_("Birthdays after this year represented by "
                                "decade only.\n"
                                "Invalid entries will be ignored."))
        menu.add_option(category_name, "i_round_year", i_round_year)

        b_round_bday = BooleanOption(_("Round birthday to show only decade after"
                                       " given year (above)."), False)
        b_round_bday.set_help(_("Represent birthday by decade only."))
        menu.add_option(category_name, "b_round_bday", b_round_bday)

        i_round_marr = StringOption(_("Enter year to start\n"
                                      "replacing marriage\ndate by decade"), '')
        i_round_marr.set_help(_("Marriages after this year are represented by"
                                "decade only. Invalid entries will be "
                                "ignored."))
        menu.add_option(category_name, "i_round_marr", i_round_marr)

        b_round_marr = BooleanOption(_("Round marriage to show only decade after"
                                       " given year (above)."), False)
        b_round_marr.set_help(_("Represent marriage by decade only."))
        menu.add_option(category_name, "b_round_marr", b_round_marr)

        i_middle_initials = StringOption("Enter year to start\n"
                                         "replacing middle\n"
                                         "names by initials", '')
        i_middle_initials.set_help(_("Attempts to replace middle names by "
                                     "initials only.  Only works for entries "
                                     "with birth year in the record."))
        menu.add_option(category_name, "i_middle_initials", i_middle_initials)

        b_middle_initials = BooleanOption("Replace middle names with "
                                          "initials after given year (above).",
                                          False)
        b_middle_initials.set_help(_("Replace middle names with initials."))
        menu.add_option(category_name, "b_middle_initials", b_middle_initials)

        b_show_private_records = BooleanOption("Include private records.",
                                               False)
        b_show_private_records.set_help(_("Allow inclusion of private "
                                          "records in chart."))
        menu.add_option(category_name, "b_show_private_records",
                        b_show_private_records)

        category_name = " " + _("Trim") + " "

        self.trim_list_children = PersonListOption(_("Trim descendants"))
        self.trim_list_children.set_help(_("All descendants (children) of selected "
                                           "individuals will not be shown."))
        menu.add_option(category_name, "trim_list_children", self.trim_list_children)

        self.b_trim_children = BooleanOption(_("Enable trimming of descendants."), False)
        self.b_trim_children.set_help(_("You must enter valid person(s) before \n"
                                        "enabling trimming of descendants from tree."))
        menu.add_option(category_name, "b_trim_children", self.b_trim_children)
        self.b_trim_children.connect('value-changed', self.cb_b_trim_children)

        self.trim_list_parents = PersonListOption(_("Trim ancestors"))
        self.trim_list_parents.set_help(_("All ancestors (parents) of selected "
                                          "individuals will not be shown."))
        menu.add_option(category_name, "trim_list_parents", self.trim_list_parents)

        self.b_trim_parents = BooleanOption(_("Enable trimming of ancestors."), False)
        self.b_trim_parents.set_help(_("Enable trimming of ancestors from tree."))
        menu.add_option(category_name, "b_trim_parents", self.b_trim_parents)
        self.b_trim_parents.connect('value-changed', self.cb_b_trim_parents)

        self.b_trim_groups = BooleanOption(_("Enable trim groups."), False)
        self.b_trim_groups.set_help(_("Remove groups less than Min Group Size.  Automatic\n"
                                      "for databases with more than 1500 individuals."))
        menu.add_option(category_name, "b_trim_groups", self.b_trim_groups)
        self.b_trim_groups.connect('value-changed', self.cb_b_trim_groups)

        self.trim_groups_size = StringOption(_("Min Group Size"), "2")
        self.trim_groups_size.set_help(_("Enter the minimum size group to display.\n"
                                         "Value may be 2 or greater."))
        menu.add_option(category_name, "trim_groups_size", self.trim_groups_size)

        category_name = " " + _("Highlight") + " "

        self.path_start_end = PersonListOption(_("Select Start and\nEnd Individuals "
                                                 "in\ndisplayed path(s).\nSelect two"))
        self.path_start_end.set_help(_("Starting and ending person for displayed "
                                       "path(s).\nSelect two people"))
        menu.add_option(category_name, "path_start_end", self.path_start_end)

        self.show_highlight = EnumeratedListOption(_("Highlight path(s)"), "None")
        show_highlight_options = ["None", "Direct", "Any"]
        self.show_highlight.add_item(show_highlight_options[0], _("Default (None)"))
        for i in range(0, len(show_highlight_options)):
            self.show_highlight.add_item(show_highlight_options[i], show_highlight_options[i])
        self.show_highlight.set_help(_("None - Don't highlight paths.\n"
                                       "Direct - Highlight direct descendant/ancestor paths.\n"
                                       "Any - Highlight any path(s) including direct or indirect."))
        menu.add_option(category_name, "show_highlight", self.show_highlight)

        self.show_path = EnumeratedListOption(_("Show only path(s)"), "None")
        show_path_options = ["None", "Direct", "Any"]
        show_path_names = [_("None"), _("Direct"), _("Any")]
        self.show_path.add_item(show_path_options[0], _("Default (none)"))
        for i in range(0, len(show_path_options)):
            self.show_path.add_item(show_path_options[i], show_path_names[i])
        self.show_path.set_help(_("None - Don't show paths only.\n"
                                  "Direct - Show only direct descendant/ancestor paths.\n"
                                  "Any - Show only path(s) direct or indirect."))
        menu.add_option(category_name, "show_path", self.show_path)

        self.center_person = PersonOption(_("Center Person"))
        self.center_person.set_help(_("Select person at center of selection radius in graph."))
        menu.add_option(category_name, "center_person", self.center_person)

        self.center_radius = StringOption(_("Max connections\nfrom center"), "5")
        self.center_radius.set_help(_("Enter the maximum number of connections allowed from\n"
                                      "the center person.  Value may be 1 or greater."))
        menu.add_option(category_name, "center_radius", self.center_radius)

        self.b_center_person = BooleanOption(_("Limit graph to max connections from center."), False)
        self.b_center_person.set_help(_("Display up to max connections from central person."))
        menu.add_option(category_name, "b_center_person", self.b_center_person)

        self.b_highlight_center = BooleanOption(_("Highlight central person in graph."), False)
        self.b_highlight_center.set_help(_("Add yellow color background to central person."))
        menu.add_option(category_name, "b_highlight_center", self.b_highlight_center)

        category_name = " " + _("Config") + " "

        self.s_dbname = StringOption(_("Database"), "")
        menu.add_option(category_name, "s_dbname", self.s_dbname)
        self.s_dbname.set_value(self._dbase.get_dbname())
        self.s_dbname.set_available(False)
        self.s_dbname.connect('value-changed', self.cb_initialize)

        self.file_type = EnumeratedListOption(_("File Type"), "svg")
        file_type_options = ["svg", "pdf"]
        self.file_type.add_item(file_type_options[0], _("Default (svg)"))
        for i in range(0, len(file_type_options)):
            self.file_type.add_item(file_type_options[i], file_type_options[i])
        self.file_type.set_help(_("svg - Scalable Vector Graphics file.\n"
                                  "pdf - Adobe Portable Document Format.\n"))
        menu.add_option(category_name, "file_type", self.file_type)

        b_use_handle = BooleanOption(_("Use database handle instead of GrampID id in URLs."), False)
        b_use_handle.set_help(_("Use database handle instead of the gramps id for URLs.\n"
                                "The handle should never change whereas gramps ids can."))
        menu.add_option(category_name, "b_use_handle", b_use_handle)

        self.b_confirm_overwrite = BooleanOption(_("Confirm overwrite file."), True)
        self.b_confirm_overwrite.set_help(_("Enable/disable confirmation of file overwrite."))
        menu.add_option(category_name, "b_confirm_overwrite", self.b_confirm_overwrite)

    def cb_b_trim_groups(self): # Callback gets called multiple times before displayed
        """
        Callback to force b_trim_groups when database > 1500 people.
        """
        if self._dbase.get_number_of_people() > 1500:
            self.b_trim_groups.set_value(True)
            self.b_trim_groups.set_available(False)
        else:
            self.b_trim_groups.set_available(True)
        return

    def cb_initialize(self): # Initialize Values
        """
        Callback to set file name and other values on initialization.
        """
        current_dbname = self._dbase.get_dbname()
        old_dbname = self.s_dbname.get_value()

        if current_dbname != old_dbname:
            self.s_dbname.set_value(current_dbname)
            s_namebase = _("network")
            fname = current_dbname + "_" + s_namebase
            self.dest_file.set_value(fname)
            s_title = current_dbname[0].upper() + current_dbname[1::]
            self.top_title.set_value(s_title)
            self.b_trim_children.set_value(False)
        elif self.dest_file.get_value() == '':
            s_namebase = _("network")
            fname = current_dbname + "_" + s_namebase
            self.dest_file.set_value(fname)
        old_dbname = self.s_dbname.get_value()
        #------- start inifile -------
        dbname = current_dbname.lower()
        db_sections = self.inifile.get_sections()
        if dbname not in db_sections:
            self.inifile.register(dbname+".s_dbname", "")
            self.inifile.set(dbname+".s_dbname", dbname)

        db_settings = self.inifile.get_section_settings(dbname)
        if "trim_list_children" in db_settings:
            self.trim_list_children.set_value(self.inifile.get(dbname + ".trim_list_children"))
        else:
            self.inifile.register(dbname + ".trim_list_children", "")
            self.inifile.set(dbname + ".trim_list_children", self.trim_list_children.get_value())

        if "trim_list_parents" in db_settings:
            self.trim_list_parents.set_value(self.inifile.get(dbname + ".trim_list_parents"))
        else:
            self.inifile.register(dbname + ".trim_list_parents", "")
            self.inifile.set(dbname + ".trim_list_parents", self.trim_list_parents.get_value())

        if "path_start_end" in db_settings:
            self.path_start_end.set_value(self.inifile.get(dbname + ".path_start_end"))
        else:
            self.inifile.register(dbname + ".path_start_end", "")
            self.inifile.set(dbname + ".path_start_end", self.path_start_end.get_value())

        if "b_trim_children" in db_settings:
            self.b_trim_children.set_value(bool(int(self.inifile.get(dbname + ".b_trim_children"))))
        else:
            self.inifile.register(dbname + ".b_trim_children", "")
            self.inifile.set(dbname + ".b_trim_children", str(int(self.b_trim_children.get_value())))

        if "b_trim_parents" in db_settings:
            self.b_trim_parents.set_value(bool(int(self.inifile.get(dbname + ".b_trim_parents"))))
        else:
            self.inifile.register(dbname + ".b_trim_parents", "")
            self.inifile.set(dbname + ".b_trim_parents", str(int(self.b_trim_parents.get_value())))

        if "b_trim_groups" in db_settings:
            self.b_trim_groups.set_value(bool(int(self.inifile.get(dbname + ".b_trim_groups"))))
        else:
            self.inifile.register(dbname + ".b_trim_groups", "")
            self.inifile.set(dbname + ".b_trim_groups", str(int(self.b_trim_groups.get_value())))

        if "trim_groups_size" in db_settings:
            self.trim_groups_size.set_value(self.inifile.get(dbname + ".trim_groups_size"))
        else:
            self.inifile.register(dbname + ".trim_groups_size", "")
            self.inifile.set(dbname + ".trim_groups_size", self.trim_groups_size.get_value())

        if "show_path" in db_settings:
            self.show_path.set_value(self.inifile.get(dbname + ".show_path"))
        else:
            self.inifile.register(dbname + ".show_path", "")
            self.inifile.set(dbname + ".show_path", self.show_path.get_value())

        if "show_highlight" in db_settings:
            self.show_highlight.set_value(self.inifile.get(dbname + ".show_highlight"))
        else:
            self.inifile.register(dbname + ".show_highlight", "")
            self.inifile.set(dbname + ".show_highlight", self.show_highlight.get_value())

        if "b_center_person" in db_settings:
            self.b_center_person.set_value(bool(int(self.inifile.get(dbname + ".b_center_person"))))
        else:
            self.inifile.register(dbname + ".b_center_person", "")
            self.inifile.set(dbname + ".b_center_person", str(int(self.b_center_person.get_value())))

        if "b_highlight_center" in db_settings:
            self.b_highlight_center.set_value(bool(int(self.inifile.get(dbname + ".b_highlight_center"))))
        else:
            self.inifile.register(dbname + ".b_highlight_center", "")
            self.inifile.set(dbname + ".b_highlight_center", str(int(self.b_highlight_center.get_value())))

        if "center_person" in db_settings:
            self.center_person.set_value(self.inifile.get(dbname + ".center_person"))
        else:
            self.inifile.register(dbname + ".center_person", "")
            self.inifile.set(dbname + ".center_person", self.center_person.get_value())

        if "center_radius" in db_settings:
            self.center_radius.set_value(self.inifile.get(dbname + ".center_radius"))
        else:
            self.inifile.register(dbname + ".center_radius", "")
            self.inifile.set(dbname + ".center_radius", self.center_radius.get_value())

        #------- start inifile -------
        return

    def cb_b_trim_children(self): # Callback gets called multiple times before displayed
        """
        Callback to prevent trim children/descendants on non-existing Gramps IDs.
        """
        current_dbname = self._dbase.get_dbname()
        old_dbname = self.s_dbname.get_value()
        if current_dbname != old_dbname:
            self.b_trim_children.set_value(False)

        if self.b_trim_children.get_value():
            trim_list_children = [str(i.strip()) for i in
                                  str(self.trim_list_children.get_value()).split(' ')
                                  if len(i) > 0]
            if len(trim_list_children) < 1:
                self.b_trim_children.set_value(False)
                return
            for ind in trim_list_children:
                gid = self._dbase.get_person_from_gramps_id(ind)
                if gid is None:
                    self.b_trim_children.set_value(False)
                    return
        return

    def cb_b_trim_parents(self): # Callback gets called multiple times before displayed
        """
        Callback to prevent trim parents/ancestors on non-existing Gramps IDs.
        """
        current_dbname = self._dbase.get_dbname()
        old_dbname = self.s_dbname.get_value()
        if current_dbname != old_dbname:
            self.b_trim_parents.set_value(False)

        if self.b_trim_parents.get_value():
            trim_list_parents = [str(i.strip()) for i in
                                 str(self.trim_list_parents.get_value()).split(' ')
                                 if len(i) > 0]
            if len(trim_list_parents) < 1:
                self.b_trim_parents.set_value(False)
                return
            for ind in trim_list_parents:
                gid = self._dbase.get_person_from_gramps_id(ind)
                if gid is None:
                    self.b_trim_parents.set_value(False)
                    return
        return
