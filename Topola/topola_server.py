"""HTTP server serving data for the Topola application."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from http.server import BaseHTTPRequestHandler, HTTPServer
from os.path import splitext
from tempfile import mkstemp
from threading import Thread, Lock

from gramps.gui.user import User
from gramps.plugins.export.exportgedcom import GedcomWriter

class TopolaServer(Thread):
    """Server serving the Gramps database in GEDCOM format.

    This class is used as a singleton.
    """

    def __init__(self, port):
        Thread.__init__(self)
        self.port = port
        self.daemon = True
        self.executor = ThreadPoolExecutor()
        self.lock = Lock()

    def _load_data(self, database):
      """Takes a snapshot of the database as a GEDCOM file."""

      # Export GEDCOM to a temporary file.
      exported_file = mkstemp()[1]
      ged_writer = GedcomWriter(database, User())
      ged_writer.write_gedcom_file(exported_file)

      # Postprocess the exported file replacing referenced files with links
      # back to Gramps that will read these files.
      content = open(exported_file, 'r').readlines()
      gedcom_path = mkstemp()[1]
      # Store all served files in a map from requested URL path to path on
      # disk.
      file_map = {'/': gedcom_path}
      gedcom_file = open(gedcom_path, 'w')
      for line in content:
        if line.startswith('1 FILE'):
          file_name = line[6:].strip()
          # Don't replace web links.
          if file_name.startswith('http://') or file_name.startswith('https://'):
            continue
          # Use hash instead of file path to avoid encoding problems.
          hash = md5(file_name.encode()).hexdigest()
          # Preserve file extension.
          extension = splitext(file_name)[1]
          remote_name = '/file/{}{}'.format(hash, extension)
          file_map[remote_name] = file_name
          line = '1 FILE http://127.0.0.1:8156{}\n'.format(remote_name)
        gedcom_file.write(line)
      return file_map

    def set_database(self, database):
      """Asynchronously takes a snapshot of the database.

      Stores a future that resolves to a file map that includes the GEDCOM file
      and files referenced from the GEDCOM file.
      """

      with self.lock:
        self.dataFuture = self.executor.submit(TopolaServer._load_data, self, database)

    def run(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                """Serves the GEDCOM file and referenced files."""
                # Take the file map in a thread-safe way, possibly blocking
                # until the GEDCOM file is ready.
                with server.lock:
                  file_map = server.dataFuture.result()

                # Return 404 if a file is not known.
                if not self.path in file_map:
                  self.send_response(404)
                  return

                # Respond with the file contents.
                self.send_response(200)
                # self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Origin', 'https://pewu.github.io')
                self.end_headers()
                content = open(file_map[self.path], 'rb').read()
                self.wfile.write(content)

        # Bind to the local address only.
        server_address = ('127.0.0.1', self.port)
        httpd = HTTPServer(server_address, Handler)
        httpd.serve_forever()
