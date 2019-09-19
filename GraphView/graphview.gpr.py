import os
from gramps.gen.utils.file import search_for
try:
    import gi
    gi.require_version('GooCanvas', '2.0')
    from gi.repository import GooCanvas
    _GOO = True
except (ImportError, ValueError):
    _GOO = False
if os.sys.platform == "win32":
    _DOT = search_for("dot.exe")
else:
    _DOT = search_for("dot")

if not (_GOO and _DOT):
    from gramps.gen.config import config
    inifile = config.register_manager("graphviewwarn")
    inifile.load()
    sects = inifile.get_sections()

if(_GOO and _DOT or locals().get('build_script') or
   'graphviewwarn' not in sects):
    if locals().get('uistate'):  # don't start GUI if in CLI mode, just ignore
        from gi.repository import Gtk, GdkPixbuf
        from gramps.gen.const import USER_PLUGINS
        fname = os.path.join(USER_PLUGINS, 'GraphView',
                            'gramps-graph.svg')
        factory = Gtk.IconFactory()
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(fname)
        iconset = Gtk.IconSet.new_from_pixbuf(pixbuf)
        factory.add('gramps-graph', iconset)
        factory.add_default()

    register(VIEW,
        id    = 'graphview',
        name  = _("Graph View"),
        category = ("Ancestry", _("Charts")),
        description =  _("Dynamic and interactive graph of relations"),
        version = '1.0.94',
        gramps_target_version = "5.0",
        status = STABLE,
        fname = 'graphview.py',
        authors = ["Gary Burton"],
        authors_email = ["gary.burton@zen.co.uk"],
        viewclass = 'GraphView',
        stock_icon = 'gramps-graph',
    )

from gramps.gen.config import logging
if not _GOO:
    warn_msg = _("Graphview Warning:  Goocanvas 2 "
                 "(https://wiki.gnome.org/action/show/Projects/GooCanvas)"
                 " is required for this view to work")
    logging.log(logging.WARNING, warn_msg)
if not _DOT:
    warn_msg = _("Graphview Warning:  GraphViz "
                 "(http://www.graphviz.org) is "
                 "required for this view to work")
    logging.log(logging.WARNING, warn_msg)
# don't start GUI if in CLI mode, just ignore
if not (_GOO and _DOT) and locals().get('uistate'):
    from gramps.gui.dialog import QuestionDialog2
    if 'graphviewwarn' not in sects:
        yes_no = QuestionDialog2(
            _("Graphview Failed to Load"),
            _("\n\nGraphview is missing python modules or programs.\n"
              "%smust be installed.\n\n"
              "For now, it may be possible to install the files manually."
              " See\n<a href=\"https://gramps-project.org/wiki/index.php?"
              "title=Graph_View\" "
              "title=\"https://gramps-project.org/wiki/index.php?"
              "title=Graph_View\">https://gramps-project.org/wiki/index.php?"
              "title=Graph_View</a> \n\n"
              "To dismiss all future Graphview warnings click Dismiss.") %
            ('' if _DOT else "GraphViz (<a href=\"http://www.graphviz.org\" "
             "title=\"http://www.graphviz.org\">"
             "http://www.graphviz.org</a>)\n") +
            ('' if _GOO else "Goocanvas 2 (<a "
             "href=\"https://wiki.gnome.org/action/show/Projects/GooCanvas\" "
             "title=\"https://wiki.gnome.org/action/show/Projects/GooCanvas\">"
             "https://wiki.gnome.org/action/show/Projects/GooCanvas</a>)\n"),
            _(" Dismiss "),
            _("Continue"), parent=uistate.window)
        prompt = yes_no.run()
        if prompt is True:
            inifile.register('graphviewwarn.MissingModules', "")
            inifile.set('graphviewwarn.MissingModules', "True")
            inifile.save()
