"""Interactive tree tool."""

from gramps.gui.display import display_url
from gramps.gui.plug import tool
from topola_server import TopolaServer

# Port to start the HTTP server.
HTTP_PORT = 8156

class Topola(tool.Tool):
    """Gramps tool that opens an interactive tree in the browser.

    Starts a HTTP server that serves the data in GEDCOM format, then opens
    Topola Genealogy Viewer at https://pewu.github.io/topola-viewer pointing
    to the local server to get data. The online viewer does not send any data
    to a remote server. All data is only kept in the browser.
    """

    server = None

    def __init__(self, dbstate, user, options_class, name, callback=None):
        tool.Tool.__init__(self, dbstate, options_class, name)
        if not dbstate.db:
            return

        # Initialize the server if running for the first time.
        if not Topola.server:
            Topola.server = TopolaServer(HTTP_PORT)
            Topola.server.start()

        Topola.server.set_database(dbstate.db)
        display_url(
            'https://pewu.github.io/topola-viewer/#/view' +
            '?utm_source=gramps&handleCors=false&standalone=false' +
            '&url=http://127.0.0.1:{}/'.format(HTTP_PORT))

class TopolaOptions(tool.ToolOptions):
    """Empty options class."""
