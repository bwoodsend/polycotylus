import os
from http.server import BaseHTTPRequestHandler
from http import HTTPStatus
import socketserver
import webbrowser
import threading
from contextlib import contextmanager


class Handler(BaseHTTPRequestHandler):
    content: dict

    def do_HEAD(self):
        if self.path in self.content:
            self.send_response(HTTPStatus.OK)
        else:
            self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_GET(self):
        self.do_HEAD()
        self.wfile.write(self.content[self.path]())

    def log_message(self, *args, **kwargs):
        pass


@contextmanager
def miniserver(content: dict):
    handler = type("Handler", (Handler,), {"content": content})

    httpd = socketserver.TCPServer(("", 0), handler)
    host, port = httpd.socket.getsockname()
    host = "localhost" if os.name == "nt" else host
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield "http://{}:{}".format(host, port)

    httpd.shutdown()
