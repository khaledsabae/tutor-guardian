"""SSE stream worker cancellation (audit H6).

The worker thread used to keep reading the whole answer after the parent
disconnected. `_pump_stream` must stop at the next chunk once cancelled and
CLOSE the generator, so the provider's HTTP connection is released.
"""
import threading

from app.routers.assistant import _STREAM_EXECUTOR, _pump_stream


class _FakeStream:
    def __init__(self, n=100, on_yield=None):
        self.n, self.on_yield = n, on_yield
        self.closed = False
        self.yielded = 0

    def __iter__(self):
        return self._gen()

    def _gen(self):
        try:
            for i in range(self.n):
                self.yielded += 1
                if self.on_yield:
                    self.on_yield(i)
                yield f"tok{i}"
        finally:
            self.closed = True


def test_cancel_stops_the_worker_and_closes_the_stream():
    cancel = threading.Event()
    fake = _FakeStream(on_yield=lambda i: cancel.set() if i == 2 else None)
    events = []
    _pump_stream(lambda: iter(fake), lambda k, v: events.append((k, v)), cancel)
    assert fake.closed, "generator not closed — the provider connection leaks"
    assert fake.yielded == 3          # stopped at the next chunk, not the 100th
    assert ("done", None) not in events
    assert not any(k == "error" for k, _ in events)


def test_completed_stream_reports_done():
    events = []
    fake = _FakeStream(n=3)
    _pump_stream(lambda: iter(fake), lambda k, v: events.append((k, v)), threading.Event())
    assert [k for k, _ in events] == ["chunk", "chunk", "chunk", "done"]
    assert fake.closed


def test_deadline_turns_into_an_error_not_a_hang():
    events = []
    fake = _FakeStream(n=10)
    _pump_stream(lambda: iter(fake), lambda k, v: events.append((k, v)),
                 threading.Event(), deadline_s=-1)
    assert events and events[-1][0] == "error"
    assert fake.closed


def test_provider_error_is_surfaced():
    def boom():
        raise ConnectionError("upstream down")

    events = []
    _pump_stream(boom, lambda k, v: events.append((k, v)), threading.Event())
    assert events[0][0] == "error" and isinstance(events[0][1], ConnectionError)


def test_streams_run_on_their_own_bounded_pool():
    assert _STREAM_EXECUTOR._max_workers >= 1
    assert _STREAM_EXECUTOR._thread_name_prefix == "llm-stream"
