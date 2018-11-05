if locals().get('uistate'):  # don't start GUI if in CLI mode, just ignore
    from gi.repository import Gtk, GdkPixbuf
    import os
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
     description =  _("Dynamic graph of relations"),
     version = '1.0.83',
     gramps_target_version = "5.0",
     status = STABLE,
     fname = 'graphview.py',
     authors = ["Gary Burton"],
     authors_email = ["gary.burton@zen.co.uk"],
     viewclass = 'GraphView',
     stock_icon = 'gramps-graph',
)
