from gi import Repository
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.plug._pluginreg import register, VIEW, STABLE #, END, START
_ = glocale.translation.gettext

# Attempting to import goocanvas gives an error dialog if goocanvas is not
# available so test first and log just a warning to the console instead.
try:
    config.get('interface.ignore-goocanvas')
except:
    config.register('interface.ignore-goocanvas', False)

GOOCANVAS = False
REPOSITORY = Repository.get_default()
if REPOSITORY.enumerate_versions("GooCanvas"):
    try:
        # current goocanvas support GTK3
        import gi
        gi.require_version('GooCanvas', '2.0')
        from gi.repository import GooCanvas as goocanvas
        GOOCANVAS = True
    except:
        pass

if not GOOCANVAS:
    from gramps.gen.config import config
    if not config.get('interface.ignore-goocanvas'):
        from gramps.gen.constfunc import has_display
        if has_display():
            from gramps.gui.dialog import MessageHideDialog
            from gramps.gen.const import URL_WIKISTRING
            TITLE = _("goocanvas module not loaded.")
            MESSAGE = _("Graphview functionality will not be available.\n"
                        "You must install goocanvas."
                       )
            if uistate:
                MessageHideDialog(TITLE, MESSAGE,
                                  'interface.ignore-goocanvas',
                                  parent=uistate.window)
            else:
                MessageHideDialog(TITLE, MESSAGE,
                                  'interface.ignore-goocanvas')
else:
    # Load the view only if goocanvas library is present.
    register(VIEW,
         id    = 'graphview',
         name  = _("Graph View"),
         category = ("Ancestry", _("Charts")),
         description =  _("Dynamic graph of relations"),
         version = '1.0.70',
         gramps_target_version = "5.0",
         status = STABLE,
         fname = 'graphview.py',
         authors = ["Gary Burton"],
         authors_email = ["gary.burton@zen.co.uk"],
         viewclass = 'GraphView',
      )
