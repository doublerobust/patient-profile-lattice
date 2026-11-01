"""Small HTTP regression for the addresses used to open the demo."""
import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
import unittest

from app import Engine, make_handler


class AddressChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = make_handler(Engine(Path(__file__).parent / 'data'))
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, host, origin=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        headers = {'Host': host}
        if origin is not None:
            headers['Origin'] = origin
        try:
            conn.request('GET', '/', headers=headers)
            response = conn.getresponse()
            return response.status, response.getheader('Content-Type'), response.read()
        finally:
            conn.close()

    def test_supported_addresses_serve_the_viewer(self):
        for host in (f'127.0.0.1:{self.port}', f'localhost:{self.port}',
                     f'[::1]:{self.port}', 'yues-mac-studio.tail8e98a8.ts.net:9143'):
            with self.subTest(host=host):
                status, _, body = self.request(host, 'https://' + host)
                self.assertEqual(status, 200)
                self.assertIn(b'<html', body.lower())

    def test_foreign_host_returns_readable_working_link(self):
        status, mime, body = self.request(f'foreign.example:{self.port}')
        self.assertEqual(status, 403)
        self.assertIn('text/html', mime or '')
        self.assertIn(f'http://127.0.0.1:{self.port}/'.encode(), body)

    def test_foreign_origin_stays_refused(self):
        for host in (f'localhost:{self.port}', 'yues-mac-studio.tail8e98a8.ts.net:9143'):
            with self.subTest(host=host):
                self.assertEqual(self.request(host, 'https://foreign.example')[0], 403)


if __name__ == '__main__':
    unittest.main(verbosity=2)
