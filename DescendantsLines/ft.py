#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007-2010 ats-familytree@offog.org
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
Print Descendants Lines
"""
#-------------------------------------------------------------------------
#
# python modules
#
#-------------------------------------------------------------------------
import cairo
import gtk
import gzip
import xml.dom.minidom
import getopt
import sys
#-------------------------------------------------------------------------
#
# variables
#
#-------------------------------------------------------------------------
S_DOWN = 20
S_UP = 10
S_VPAD = 10
FL_PAD = 20
OL_PAD = 10
O_DOWN = 30
C_PAD = 10
F_PAD = 20
C_UP = 15
SP_PAD = 10
MIN_C_WIDTH = 40
TEXT_PAD = 2
TEXT_LINE_PAD = 2

ctx = None
font_name = 'sans-serif'
base_font_size = 12


def draw_text(text, x, y):
    (total_w, total_h) = size_text(text)
    for (size, color, line) in text:
        ctx.select_font_face(font_name)
        ctx.set_font_size(base_font_size * size)
        (ascent, _, height, _, _) = ctx.font_extents()
        (
            lx,
            _,
            width,
            _,
            _,
            _,
            ) = ctx.text_extents(line)
        ctx.move_to(x - lx + TEXT_PAD + (total_w - width + lx) / 2, y
                     + ascent + TEXT_PAD)
        ctx.set_source_rgb(*color)
        ctx.show_text(line)
        y += height + TEXT_LINE_PAD


def size_text(text):
    text_width = 0
    text_height = 0
    first = True
    for (size, color, line) in text:
        if first:
            first = False
        else:
            text_height += TEXT_LINE_PAD
        ctx.select_font_face(font_name)
        ctx.set_font_size(base_font_size * size)
        (_, _, height, _, _) = ctx.font_extents()
        (
            lx,
            _,
            width,
            _,
            _,
            _,
            ) = ctx.text_extents(line)
        text_width = max(text_width, width - lx)
        text_height += height
    text_width += 2 * TEXT_PAD
    text_height += 2 * TEXT_PAD
    return (text_width, text_height)


mem_depth = 0


class Memorised:

    def get(self, name):
        try:
            getattr(self, '_memorised')
        except:
            self._memorised = {}

        global mem_depth
        mem_depth += 1
        if name in self._memorised:
            cached = '*'
            v = self._memorised[name]
        else:
            cached = ' '
            v = getattr(self, name)()
            self._memorised[name] = v

        mem_depth -= 1
        return v


class Person(Memorised):

    def __init__(self, text):
        self.text = text

        self.families = []
        self.from_family = None
        self.prevsib = None
        self.nextsib = None

        self.generation = None

    def __str__(self):
        return '[' + self.text + ']'

    def add_family(self, fam):
        if self.families != []:
            self.families[-1].nextfam = fam
            fam.prevfam = self.families[-1]
        self.families.append(fam)

    def draw(self):
        set_bg_style(ctx)
        ctx.rectangle(self.get('x'), self.get('y'), self.get('w'),
                      self.get('h'))
        ctx.fill()

        draw_text(self.text, self.get('tx'), self.get('y'))

        for f in self.families:
            f.draw()

    def x(self):
        if self.from_family is None:
            return 0
        else:
            return self.from_family.get('cx') + self.get('o')

    def tx(self):
        return (self.get('x') + self.get('go')) - self.get('tw') / 2

    def y(self):
        if self.from_family is None:
            return 0
        else:
            return self.from_family.get('cy')

    def tw(self):
        return size_text(self.text)[0]

    def th(self):
        return size_text(self.text)[1]

    def glh(self):
        return reduce(lambda a, b: a + b, [f.get('glh') for f in
                      self.families], 0)

    def o(self):
        if self.prevsib is None:
            return 0
        else:
            return self.prevsib.get('o') + self.prevsib.get('w') + C_PAD

    def ch(self):
        ch = reduce(max, [f.get('ch') for f in self.families], 0)
        if ch != 0:
            ch += O_DOWN + C_UP
        return ch

    def w(self):
        w = self.get('go') + self.get('tw') / 2
        w = max(w, MIN_C_WIDTH)
        if self.families != []:
            ff = self.families[0]
            to_sp = self.get('go') + ff.get('flw')
            w = max(w, to_sp + ff.spouse.get('tw') / 2)
            w = max(w, (to_sp - FL_PAD + ff.get('cw')) - ff.get('oloc'))
        return w

    def h(self):
        return self.get('th') + self.get('glh') + self.get('ch')

    def go(self):
        go = self.get('tw') / 2
        if self.families != []:
            lf = self.families[-1]
            if lf.children != []:
                go = max(go, lf.get('oloc') - (lf.get('flw') - FL_PAD))
        return go

    def to(self):
        return self.get('go') - self.get('tw') / 2

    def glx(self):
        return self.get('x') + self.get('go')


class Family(Memorised):

    def __init__(self, main, spouse):
        self.main = main
        self.spouse = spouse

        self.children = []
        self.prevfam = None
        self.nextfam = None

        main.add_family(self)

        self.generation = None

    def __str__(self):
        return '(:' + str(self.main) + '+' + str(self.spouse) + ':)'

    def add_child(self, child):
        if self.children != []:
            self.children[-1].nextsib = child
            child.prevsib = self.children[-1]
        self.children.append(child)
        child.from_family = self

    def draw(self):
        (px, py) = (self.main.get('x'), self.main.get('y'))

        set_line_style(ctx)
        ctx.new_path()
        ctx.move_to(self.get('glx'), self.get('gly'))
        ctx.rel_line_to(0, self.get('glh'))
        ctx.rel_line_to(self.get('flw'), 0)
        ctx.rel_line_to(0, -S_UP)
        ctx.stroke()

        draw_text(self.spouse.text, self.get('spx'), self.get('spy'))

        if self.children != []:
            set_line_style(ctx)
            ctx.new_path()
            ctx.move_to(self.get('olx'), self.get('oly'))
            ctx.rel_line_to(0, self.get('olh'))
            ctx.stroke()

            ctx.new_path()
            ctx.move_to(self.children[0].get('glx'), self.get('cly'))
            ctx.line_to(self.children[-1].get('glx'), self.get('cly'))
            ctx.stroke()

            for c in self.children:
                set_line_style(ctx)
                ctx.new_path()
                ctx.move_to(c.get('glx'), self.get('cly'))
                ctx.rel_line_to(0, C_UP)
                ctx.stroke()

                c.draw()

    def glx(self):
        return self.main.get('glx')

    def gly(self):
        if self.prevfam is None:
            return self.main.get('y') + self.main.get('th')
        else:
            return self.prevfam.get('gly') + self.prevfam.get('glh')

    def spx(self):
        return (self.get('glx') + self.get('flw'))\
             - self.spouse.get('tw') / 2

    def spy(self):
        return ((self.get('gly') + self.get('glh')) - S_UP)\
             - self.spouse.get('th')

    def olx(self):
        return (self.get('glx') + self.get('flw')) - FL_PAD

    def oly(self):
        return self.get('gly') + self.get('glh')

    def cx(self):
        return ((self.main.get('x') + self.main.get('go')
                 + self.get('flw')) - FL_PAD) - self.get('oloc')

    def cly(self):
        return self.get('oly') + self.get('olh')

    def cy(self):
        return self.get('cly') + C_UP

    def glh(self):
        if self.prevfam is None:
            return S_DOWN
        else:
            return S_VPAD + self.spouse.get('th') + S_UP

    def flw(self):
        flw = 2 * FL_PAD
        flw = max(flw, self.main.get('tw') / 2 + self.spouse.get('tw')
                   / 2 + SP_PAD)
        if self.nextfam is not None:
            flw = max(flw, self.nextfam.get('flw')
                       + self.nextfam.spouse.get('tw') + OL_PAD)
            flw = max(flw, self.nextfam.get('flw')
                       - self.nextfam.get('oloc')
                       + self.nextfam.get('cw') + F_PAD
                       + self.get('oloc'))
        return flw

    def olh(self):
        if self.nextfam is None:
            return O_DOWN
        else:
            return self.nextfam.get('olh') + self.nextfam.get('glh')

    def cw(self):
        if self.children == []:
            return 0
        else:
            return self.children[-1].get('o')\
                 + self.children[-1].get('w')

    def ch(self):
        return reduce(max, [c.get('h') for c in self.children], 1)

    def oloc(self):
        if self.children == []:
            return 0
        else:
            return reduce(lambda a, b: a + b, [c.get('o') + c.get('go')
                          for c in self.children]) / len(self.children)


def load_gramps(fn, start):
    f = gzip.open(fn, 'r')
    x = xml.dom.minidom.parse(f)
    f.close()

    def get_text(nodes):
        if nodes == []:
            return None
        for cn in nodes[0].childNodes:
            if cn.nodeType == nodes[0].TEXT_NODE:
                return cn.data
        return None


    class InPerson:

        def __init__(self):
            self.gender = None
            self.first = None
            self.prefix = None
            self.last = None
            self.birth = None
            self.death = None

        def text(self, expected_last=None):
            first_size = 1.0
            last_size = 0.95
            life_size = 0.90

            if self.gender == 'M':
                col = (0, 0, 0.5)
            elif self.gender == 'F':
                col = (0.5, 0, 0)
            else:
                col = (0, 0.5, 0)
            last_col = (0, 0, 0)
            life_col = (0.2, 0.2, 0.2)

            last = self.last
            if last == expected_last:
                last = None
            if last is not None:
                if self.prefix is not None:
                    last = self.prefix + ' ' + last
                last = last.upper()
            if self.first is None and last is None:
                s = []
            elif self.first is None:
                s = [(first_size, col, '?'), (last_size, last_col,
                     last)]
            elif last is None:
                s = [(first_size, col, self.first)]
            else:
                s = [(first_size, col, self.first), (last_size,
                     last_col, last)]

            if self.birth is not None:
                s.append((life_size, life_col, 'b. ' + self.birth))
            if self.death is not None:
                s.append((life_size, life_col, 'd. ' + self.death))

            return s


    handletoid = {}
    eventtoid = {}
    tpeople = {}
    people = x.getElementsByTagName('people')[0]
    for p in people.getElementsByTagName('person'):
        id = p.getAttribute('id')
        handle = p.getAttribute('handle')
        handletoid[handle] = id
        name = p.getElementsByTagName('name')[0]
        po = InPerson()
        po.gender = get_text(p.getElementsByTagName('gender'))
        po.first = get_text(name.getElementsByTagName('first'))
        po.last = get_text(name.getElementsByTagName('last'))
        ls = name.getElementsByTagName('last')
        if ls != []:
            po.prefix = ls[0].getAttribute('prefix')
        for er in p.getElementsByTagName('eventref'):
            eventtoid[er.getAttribute('hlink')] = id
        tpeople[id] = po

    events = x.getElementsByTagName('events')[0]
    for ev in events.getElementsByTagName('event'):
        pid = eventtoid.get(ev.getAttribute('handle'))
        if pid is None:
            continue
        po = tpeople[pid]
        etype = get_text(ev.getElementsByTagName('type'))
        dvs = ev.getElementsByTagName('dateval')
        if len(dvs) == 0:
            print 'Undated event: ' + ev.getAttribute('handle')
            continue
        date = ev.getElementsByTagName('dateval')[0].getAttribute('val')
        if etype == 'Birth':
            po.birth = date
        elif etype == 'Death':
            po.death = date
        else:
            print 'Unknown event type: ' + etype


    class InFamily:

        def __init__(self):
            self.a = None
            self.b = None
            self.children = []

        def spouse(self, s):
            if s == self.a:
                return self.b
            else:
                return self.a


    parents = {}
    tfamilies = {}
    families = x.getElementsByTagName('families')[0]
    for f in families.getElementsByTagName('family'):
        id = f.getAttribute('id')
        fo = InFamily()
        for p in f.getElementsByTagName('father'):
            fo.a = handletoid[p.getAttribute('hlink')]
            parents.setdefault(fo.a, []).append(id)
        for p in f.getElementsByTagName('mother'):
            fo.b = handletoid[p.getAttribute('hlink')]
            parents.setdefault(fo.b, []).append(id)
        for p in f.getElementsByTagName('childref'):
            fo.children.append(handletoid[p.getAttribute('hlink')])
        tfamilies[id] = fo

    def do_person(pid, expected_last=None):
        po = tpeople[pid]
        p = Person(po.text(expected_last))
        if pid in parents:
            for fid in parents[pid]:
                fo = tfamilies[fid]
                if fo.spouse(pid):
                    spo = tpeople[fo.spouse(pid)]
                    fm = Family(p, Person(spo.text()))
                    last = po.last
                    if spo.gender == 'M':
                        last = spo.last
                    for cpid in fo.children:
                        cpo = tpeople[cpid]
                        fm.add_child(do_person(cpid, last))
                else:
                    pass
        return p

    return do_person(start)


def set_bg_style(ctx):
    ctx.set_source_rgb(1.0, 1.0, 1.0)


def set_line_style(ctx):
    ctx.set_source_rgb(0.3, 0.3, 0.3)


def draw_tree(head):
    ctx.select_font_face(font_name)
    ctx.set_font_size(base_font_size)
    ctx.set_line_width(2)
    ctx.set_line_cap(cairo.LINE_CAP_SQUARE)
    ctx.set_line_join(cairo.LINE_JOIN_MITER)
    set_line_style(ctx)
    head.draw()


def draw_gtk(p):
    win = gtk.Window()
    win.set_title('Family tree')
    win.connect('destroy', lambda widget: gtk.main_quit())

    sw = gtk.ScrolledWindow()
    win.add(sw)

    da = gtk.DrawingArea()

    def draw(widget, event):
        global ctx
        ctx = da.window.cairo_create()
        draw_tree(p)

        w = int(p.get('w') + 1)
        h = int(p.get('h') + 1)
        da.set_size_request(w, h)
        w = min(w, 1200)

        sw.set_size_request(w, h + 60)

    da.connect('expose_event', draw)
    sw.add_with_viewport(da)

    win.show_all()
    gtk.main()


class PNGWriter:

    def start(
        self,
        fn,
        w,
        h,
        ):
        self.fn = fn
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(w
                 + 1), int(h + 1))
        return self.surface

    def finish(self):
        self.surface.write_to_png(self.fn)


class PSWriter:

    def start(
        self,
        fn,
        w,
        h,
        ):
        return cairo.PSSurface(fn, w, h)

    def finish(self):
        pass


def draw_file(p, fn, writer):
    global ctx

    surface = writer.start(fn, 10, 10)
    ctx = cairo.Context(surface)
    draw_tree(p)
    (w, h) = (p.get('w'), p.get('h'))

    surface = writer.start(fn, w, h)
    ctx = cairo.Context(surface)
    draw_tree(p)
    ctx.show_page()
    writer.finish()


def usage():
    print """Usage: familytree [OPTION]...
Generate graphical family trees from GRAMPS databases.

-i INPUT                     Use INPUT as input "data.gramps" file
-o OUTPUT                    Write output to OUTPUT in Postscript or PNG
                             format depending on the filename (default:
                             use GTK to display the output)
-h HEAD                      Use person with ID of HEAD as the top of
                             the tree (default: I0000)
-f FONT                      Select font to use
-s SIZE                      Select base font size to use
--help                       Display this help and exit

Report bugs to <ats-familytree@offog.org>."""


def main(args):
    global font_name, base_font_size

    input_fn = 'data.gramps'
    output_fn = None
    head = 'I0000'

    try:
        (opts, args) = getopt.getopt(args, 'i:o:h:f:s:', ['help'])
    except getopt.GetoptError, s:
        print s
        usage()
        sys.exit(1)

    for (o, a) in opts:
        if o == '--help':
            usage()
            sys.exit(0)
        elif o == '-i':
            input_fn = a
        elif o == '-o':
            output_fn = a
        elif o == '-h':
            head = a
        elif o == '-f':
            font_name = a
        elif o == '-s':
            base_font_size = float(a)

    p = load_gramps(input_fn, head)
    if output_fn is None:
        draw_gtk(p)
    elif output_fn.lower().endswith('.png'):
        draw_file(p, output_fn, PNGWriter())
    elif output_fn.lower().endswith('.ps'):
        draw_file(p, output_fn, PSWriter())
    else:
        print 'Unknown output format'
        sys.exit(1)


if __name__ == '__main__':
    main(sys.argv[1:])
