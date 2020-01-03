"""Interactive tree tool."""

from tempfile import mkstemp
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

from gramps.plugins.export.exportgedcom import GedcomWriter
from gramps.gui.user import User
from gramps.gui.display import display_url
from gramps.gui.plug import tool

# Port to start the HTTP server.
HTTP_PORT = 8156

class TopolaServer(Thread):
    """Server serving the Gramps database in GEDCOM format.

    This class is used as a singleton.
    """
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.path = None

    def set_path(self, path):
        """Sets a new path of the GEDCOM to be served."""
        self.path = path

    def run(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                """Serves the GEDCOM file."""
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                content = open(server.path, 'rb').read()
                self.wfile.write(content)

        server_address = ('127.0.0.1', HTTP_PORT)
        httpd = HTTPServer(server_address, Handler)
        httpd.serve_forever()

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

        if not Topola.server:
            Topola.server = TopolaServer()
            Topola.server.start()

        temp_file = mkstemp()[1]
        ged_writer = GedcomWriter(dbstate.db, User())
        ged_writer.write_gedcom_file(temp_file)
        Topola.server.set_path(temp_file)
        display_url(
            'https://pewu.github.io/topola-viewer/#/view' +
            '?utm_source=gramps&handleCors=false&standalone=false' +
            '&url=http://127.0.0.1:{}/'.format(HTTP_PORT))

class TopolaOptions(tool.ToolOptions):
    """Empty options class."""
