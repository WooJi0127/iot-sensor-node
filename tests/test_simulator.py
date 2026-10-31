import csv
import http.client
import inspect
import io
import json
import queue
import random
import socket
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

from simulator import sensor_sim as sim


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class StateFixture:
    def setUp(self):
        with sim._LOCK:
            sim.LATEST.clear()
            sim.HISTORY.clear()
            sim._SUBSCRIBERS.clear()

    def publish(self, reading):
        self.assertTrue(callable(getattr(sim, '_publish', None)), 'sampling must expose the real bounded publication path')
        sim._publish(reading)


class SimulatorTests(StateFixture, unittest.TestCase):
    def test_seed_and_time_reproduce_frames(self):
        self.assertIn('rng', inspect.signature(sim._gen_reading).parameters)
        a, b = random.Random(17), random.Random(17)
        frames_a = [sim._gen_reading(sim.NODES[0], t, a) for t in (1, 2, 3)]
        time.sleep(0.002)
        frames_b = [sim._gen_reading(sim.NODES[0], t, b) for t in (1, 2, 3)]
        self.assertEqual(frames_a, frames_b)
        self.assertEqual([r['ts'] for r in frames_a], [1000, 2000, 3000])
        self.assertIs(type(frames_a[0]['anomaly']), bool)

    def test_slow_subscriber_keeps_recent_frames_without_blocking_sampling(self):
        self.assertTrue(callable(getattr(sim, '_subscribe', None)))
        slow = sim._subscribe()
        fast = sim._subscribe()
        started = time.monotonic()
        for i in range(1000):
            self.publish(sim._gen_reading(sim.NODES[0], i))
            fast.get_nowait()
        self.assertLess(time.monotonic() - started, 3)
        self.assertGreater(slow.maxsize, 0)
        self.assertLessEqual(slow.qsize(), slow.maxsize)
        events = [json.loads(slow.get_nowait().split('data: ', 1)[1]) for _ in range(slow.qsize())]
        self.assertEqual(events[-1]['ts'], 999000)

    def test_history_capacity_and_snapshots_are_independent(self):
        for i in range(sim.HISTORY_LEN + 3):
            self.publish(sim._gen_reading(sim.NODES[0], i))
        snapshot = sim._history_snapshot()
        self.assertEqual(len(snapshot), sim.HISTORY_LEN)
        self.assertEqual(snapshot[0]['ts'], 3000)
        snapshot[0]['temp'] = -999
        self.assertNotEqual(sim._history_snapshot()[0]['temp'], -999)


class HttpTests(StateFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        class SmallSendBufferServer(ThreadingHTTPServer):
            def get_request(server):
                connection, address = super().get_request()
                connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2048)
                return connection, address
        self.server = SmallSendBufferServer(('127.0.0.1', 0), sim.Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(3)

    def get(self, path):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        conn.request('GET', path)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        self.assertEqual(response.status, 200)
        return data

    def test_history_json_and_csv_share_contract(self):
        reading = sim._gen_reading(sim.NODES[0], 123)
        self.publish(reading)
        self.assertEqual(json.loads(self.get('/history')), [reading])
        row = list(csv.DictReader(io.StringIO(self.get('/history.csv').decode('utf-8'))))[0]
        self.assertEqual(list(row), ['id', 'name', 'ts', 'temp', 'hum', 'lux', 'anomaly'])
        self.assertEqual(row['name'], reading['name'])
        self.assertEqual(int(row['ts']), 123000)
        self.assertEqual(float(row['temp']), reading['temp'])
        self.assertEqual(row['anomaly'], str(reading['anomaly']).lower())
        self.assertIn(b'canvas', self.get('/'))
        self.assertEqual(json.loads(self.get('/latest')), [reading])

    def test_stream_delivers_two_events_and_disconnect_cleans_up(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        conn.request('GET', '/stream')
        response = conn.getresponse()
        try:
            self.assertIsNone(response.getheader('Content-Length'), 'SSE cannot declare a zero-length body')
            self.assertTrue(wait_until(lambda: len(sim._SUBSCRIBERS) == 1))
            for t in (12, 13):
                self.publish(sim._gen_reading(sim.NODES[0], t))
                while True:
                    line = response.readline()
                    self.assertTrue(line, 'stream closed before an event')
                    if line.startswith(b'data: '):
                        event = json.loads(line[6:])
                        if isinstance(event, dict):
                            break  # initial SSE snapshot is an array, live events are objects
                self.assertEqual(event['ts'], t * 1000)
        finally:
            if conn.sock:
                conn.sock.shutdown(socket.SHUT_RDWR)
            response.close()
            conn.close()
        self.assertTrue(wait_until(lambda: not sim._SUBSCRIBERS), 'disconnected subscriber leaked')

    def test_slow_http_stream_does_not_block_fast_stream_or_latest(self):
        connections, responses = [], []
        observed = threading.Event()
        errors = []
        try:
            for _ in range(2):
                conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
                conn.request('GET', '/stream')
                connections.append(conn)
                responses.append(conn.getresponse())
            self.assertTrue(wait_until(lambda: len(sim._SUBSCRIBERS) == 2))
            # First client never reads the body; second keeps consuming.
            def consume():
                try:
                    while True:
                        line = responses[1].readline()
                        if not line:
                            return
                        if line.startswith(b'data: '):
                            data = json.loads(line[6:])
                            if isinstance(data, dict) and data['ts'] == 2999000:
                                observed.set()
                                return
                except OSError as exc:
                    errors.append(exc)
            reader = threading.Thread(target=consume, daemon=True)
            reader.start()
            started = time.monotonic()
            for t in range(3000):
                self.publish(sim._gen_reading(sim.NODES[0], t))
            self.assertLess(time.monotonic() - started, 3, 'slow HTTP writer blocked sampling')
            self.assertTrue(observed.wait(3), errors)
            self.assertEqual(json.loads(self.get('/latest'))[0]['ts'], 2999000)
            with sim._LOCK:
                self.assertTrue(all(q.qsize() <= q.maxsize for q in sim._SUBSCRIBERS))
        finally:
            for conn in connections:
                if conn.sock:
                    conn.sock.shutdown(socket.SHUT_RDWR)
            for response in responses:
                response.close()
            for conn in connections:
                conn.close()
        self.assertTrue(wait_until(lambda: not sim._SUBSCRIBERS))


if __name__ == '__main__':
    unittest.main()
