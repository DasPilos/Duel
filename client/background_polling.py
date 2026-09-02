import queue
import threading
import time


class BackgroundPoller:
    """Run a polling function away from the Pygame/UI thread."""

    def __init__(self, fetch, interval=2.0):
        self.fetch = fetch
        self.interval = float(interval)
        self.results = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="client-poller", daemon=True)

    def start(self):
        if not self.thread.is_alive():
            self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            try:
                result = self.fetch()
                try:
                    self.results.get_nowait()
                except queue.Empty:
                    pass
                self.results.put_nowait((result, None))
            except Exception as error:
                try:
                    self.results.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self.results.put_nowait((None, error))
                except queue.Full:
                    pass
            self.stop_event.wait(self.interval)

    def poll(self):
        try:
            return self.results.get_nowait()
        except queue.Empty:
            return None, None

    def stop(self):
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
