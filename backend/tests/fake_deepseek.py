"""Simulated DeepSeek (OpenAI-compatible SSE) + Ollama NDJSON server.

A test helper, not a test: written for the PR #24 review (round 2) and kept
as the wire-level fixture of test_deepseek_wire.py.

Raw sockets so every wire detail is under control: chunked framing, a UTF-8
character split across two TCP writes, keep-alive comment cadence, clean close
without [DONE], TCP RST mid-stream, and server-side detection of the moment the
client really closes the socket.

Scenario = the request's "model" field (DeepSeek path) or Ollama "model".
Shapes follow https://api-docs.deepseek.com/api/create-chat-completion and
https://api-docs.deepseek.com/quick_start/rate_limit (fetched 2026-10-04):
  * streaming requests get ": keep-alive" SSE comments while queued;
  * the LAST chunk carries usage on a choices[0] with empty content and a
    non-null finish_reason (no separate usage-only chunk); with
    include_usage=true every other chunk has "usage": null;
  * finish_reason in {stop,length,content_filter,tool_calls,
    insufficient_system_resource,aborted}; then "data: [DONE]".
"""
from __future__ import annotations

import json
import select
import socket
import socketserver
import struct
import threading
import time

CONN_LOG: list[dict] = []          # one entry per accepted request
_LOCK = threading.Lock()
_SEEN: dict[str, int] = {}         # requests per scenario, for "fail once" scenarios


def _chunk(data: bytes) -> bytes:
    return b"%x\r\n" % len(data) + data + b"\r\n"


def ds_chunk(content=None, *, reasoning=None, finish=None, usage="null-omit",
             role=None, include_usage=True) -> dict:
    delta = {}
    if content is not None:
        delta["content"] = content
    if reasoning is not None:
        delta["reasoning_content"] = reasoning
    if role is not None:
        delta["role"] = role
    obj = {
        "id": "1f633d8bfc032625086f14113c411638",
        "object": "chat.completion.chunk",
        "created": 1718345013,
        "model": "deepseek-flash",
        "system_fingerprint": "fp_a49d71b8a1",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish, "logprobs": None}],
    }
    if usage == "null-omit":
        if include_usage:
            obj["usage"] = None
    else:
        obj["usage"] = usage
    return obj


USAGE = {"completion_tokens": 9, "prompt_tokens": 17, "total_tokens": 26,
         "prompt_tokens_details": {"cached_tokens": 0},
         "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 17}


def data_line(obj, *, ensure_ascii=False) -> bytes:
    return b"data: " + json.dumps(obj, ensure_ascii=ensure_ascii).encode("utf-8") + b"\n\n"


class Handler(socketserver.BaseRequestHandler):
    def setup(self):
        self.sock: socket.socket = self.request
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.conn_id = id(self)
        self.entry = None

    def new_entry(self):
        self.entry = {"t_accept": time.monotonic(), "closed_by_client_at": None,
                      "scenario": None, "path": None, "server_done_at": None,
                      "bytes_sent": 0, "conn_id": self.conn_id, "completed": False}
        with _LOCK:
            CONN_LOG.append(self.entry)

    # ── helpers ──────────────────────────────────────────────────────────
    def client_gone(self) -> bool:
        try:
            r, _, _ = select.select([self.sock], [], [], 0)
            if r:
                peek = self.sock.recv(1, socket.MSG_PEEK)
                if peek == b"":
                    return True
        except OSError:
            return True
        return False

    def send(self, raw: bytes) -> bool:
        if self.client_gone():
            self.mark_closed()
            return False
        try:
            self.sock.sendall(raw)
            self.entry["bytes_sent"] += len(raw)
            return True
        except OSError:
            self.mark_closed()
            return False

    def mark_closed(self):
        if self.entry["closed_by_client_at"] is None:
            self.entry["closed_by_client_at"] = time.monotonic()

    def send_chunk(self, payload: bytes) -> bool:
        return self.send(_chunk(payload))

    def end_chunked(self) -> bool:
        return self.send(b"0\r\n\r\n")

    def headers(self, status=200, ctype="text/event-stream; charset=utf-8", extra=b""):
        reason = {200: b"OK", 400: b"Bad Request", 402: b"Payment Required",
                  429: b"Too Many Requests", 503: b"Service Unavailable",
                  500: b"Internal Server Error"}.get(status, b"X")
        return self.send(b"HTTP/1.1 %d %s\r\nContent-Type: %s\r\nTransfer-Encoding: chunked\r\n"
                         b"Connection: keep-alive\r\n%s\r\n" % (status, reason, ctype.encode(), extra))

    def wait_until_closed(self, max_s: float):
        end = time.monotonic() + max_s
        while time.monotonic() < end:
            if self.client_gone():
                self.mark_closed()
                return
            time.sleep(0.02)

    def keepalive_for(self, seconds: float, every: float = 0.1) -> bool:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if not self.send_chunk(b": keep-alive\n\n"):
                return False
            time.sleep(every)
        return True

    # ── request ──────────────────────────────────────────────────────────
    def handle(self):
        buf = b""
        while True:                      # HTTP/1.1 persistent connection
            while b"\r\n\r\n" not in buf:
                try:
                    d = self.sock.recv(65536)
                except OSError:
                    return
                if not d:
                    return
                buf += d
            head, _, rest = buf.partition(b"\r\n\r\n")
            lines = head.decode("latin-1").split("\r\n")
            method, path, _ = lines[0].split(" ", 2)
            hdrs = {k.strip().lower(): v.strip() for k, v in (l.split(":", 1) for l in lines[1:] if ":" in l)}
            n = int(hdrs.get("content-length", "0"))
            while len(rest) < n:
                d = self.sock.recv(65536)
                if not d:
                    return
                rest += d
            body = json.loads(rest[:n] or b"{}")
            buf = rest[n:]
            self.new_entry()
            self.entry["path"] = path
            self.entry["headers"] = hdrs
            self.entry["body"] = body
            scen = body.get("model", "")
            self.entry["scenario"] = scen
            try:
                if path.endswith("/api/generate"):
                    self.ollama(scen, body)
                else:
                    getattr(self, "s_" + scen.replace("-", "_"))(body)
                self.entry["completed"] = True
            except OSError:
                self.mark_closed()
            finally:
                self.entry["server_done_at"] = time.monotonic()
            if self.entry["closed_by_client_at"] is not None or self.sock.fileno() < 0:
                return
            # after a finished response keep the connection; detect client close
            if self.entry.get("close_after"):
                return

    # ── Ollama NDJSON ────────────────────────────────────────────────────
    def ollama(self, scen, body):
        if scen == "local_down":
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            self.sock.close()
            return
        self.headers(ctype="application/x-ndjson")
        delay = 0.0
        if scen.startswith("local_slow"):
            delay = float(scen.split(":")[1]) if ":" in scen else 3.0
        # emulate prompt eval: silence, while watching for the client leaving
        end = time.monotonic() + delay
        while time.monotonic() < end:
            if self.client_gone():
                self.mark_closed()
                return
            time.sleep(0.02)
        if body.get("stream") is False:
            self.send_chunk(json.dumps({"response": "رد محلي احتياطي.", "done": True,
                                        "prompt_eval_count": 5, "eval_count": 3},
                                       ensure_ascii=False).encode())
            self.end_chunked()
            return
        for t in ["رد ", "محلي ", "احتياطي."]:
            if not self.send_chunk((json.dumps({"response": t, "done": False}, ensure_ascii=False) + "\n").encode()):
                return
            time.sleep(0.05)
        self.send_chunk((json.dumps({"response": "", "done": True, "prompt_eval_count": 5,
                                     "eval_count": 3}) + "\n").encode())
        self.end_chunked()

    # ── DeepSeek scenarios ───────────────────────────────────────────────
    def _content(self, parts, *, finish="stop", usage=USAGE, gap=0.02, ensure_ascii=False):
        self.send_chunk(data_line(ds_chunk("", role="assistant")))
        for p in parts:
            if not self.send_chunk(data_line(ds_chunk(p, role="assistant"), ensure_ascii=ensure_ascii)):
                return False
            time.sleep(gap)
        self.send_chunk(data_line(ds_chunk("", finish=finish, usage=usage)))
        self.send_chunk(b"data: [DONE]\n\n")
        self.end_chunked()
        return True

    def s_normal(self, body):
        self.headers()
        self._content(["مرحبًا", " بك", "، كيف", " أساعدك؟"])

    def s_keepalive_then_content(self, body):
        # queued: keep-alives for 3 s, then the answer
        self.headers()
        if not self.keepalive_for(3.0):
            return
        self._content(["جواب", " بعد", " الانتظار"])

    def s_hold_long(self, body):
        # DeepSeek holding a request: keep-alives for 20 s (it would go to 10 min)
        self.headers()
        if not self.keepalive_for(20.0):
            return
        self._content(["متأخر"])

    def s_silent_hold(self, body):
        # headers, then NOTHING (no keep-alive) for 6 s, then content
        self.headers()
        self.wait_until_closed(6.0)
        if self.entry["closed_by_client_at"]:
            return
        self._content(["صامت ثم جواب"])

    def s_empty_data_lines(self, body):
        self.headers()
        self.send_chunk(b"data:\n\n")
        self.send_chunk(b"data: \n\n")
        self.send_chunk(b"event: message\nid: 7\nretry: 1000\n")
        self.send_chunk(data_line(ds_chunk("أ")))
        self.send_chunk('data:{"choices":[{"delta":{"content":"ب"}}]}\n\n'.encode())   # no space
        self.send_chunk(data_line(ds_chunk("", finish="stop", usage=USAGE)))
        self.send_chunk(b"data: [DONE]\n\n")
        self.end_chunked()

    def s_multiline_data(self, body):
        # SSE spec: one event's data split over two "data:" lines, joined by "\n"
        self.headers()
        self.send_chunk(data_line(ds_chunk("قبل ")))
        js = json.dumps(ds_chunk("وسط "), ensure_ascii=False)
        cut = js.index('"choices"')
        self.send_chunk(b"data: " + js[:cut].encode() + b"\ndata: " + js[cut:].encode() + b"\n\n")
        self.send_chunk(data_line(ds_chunk("بعد")))
        self.send_chunk(data_line(ds_chunk("", finish="stop", usage=USAGE)))
        self.send_chunk(b"data: [DONE]\n\n")
        self.end_chunked()

    def s_utf8_split(self, body):
        # an Arabic char's two UTF-8 bytes in two separate TCP writes/chunks
        self.headers()
        raw = data_line(ds_chunk("سلام عليكم"))
        i = raw.index("سلام".encode()) + 1          # middle of 'س'
        self.send_chunk(raw[:i]); time.sleep(0.05)
        self.send_chunk(raw[i:]); time.sleep(0.05)
        raw2 = data_line(ds_chunk(" ورحمة"))
        self.send_chunk(raw2[:-1]); time.sleep(0.05)   # split right before the final "\n"
        self.send_chunk(raw2[-1:])
        self.send_chunk(data_line(ds_chunk("", finish="stop", usage=USAGE)))
        self.send_chunk(b"data: [DONE]\n\n")
        self.end_chunked()

    def s_invalid_utf8(self, body):
        self.headers()
        self.send_chunk(b'data: {"choices":[{"delta":{"content":"ok\xff\xfe-x"}}]}\n\n')
        self.send_chunk(data_line(ds_chunk("", finish="stop", usage=USAGE)))
        self.send_chunk(b"data: [DONE]\n\n")
        self.end_chunked()

    def s_u2028(self, body):
        # JSON allows raw U+2028/U+2029/U+0085 inside strings (only <U+0020 must be escaped)
        self.headers()
        self._content(["سطر أول", " سطر ثان", " و\u0085نهاية"], ensure_ascii=False)

    def s_crlf(self, body):
        self.headers()
        for t in ["أ", "ب"]:
            self.send_chunk(data_line(ds_chunk(t)).replace(b"\n\n", b"\r\n\r\n"))
        self.send_chunk(b": keep-alive\r\n\r\n")
        self.send_chunk(data_line(ds_chunk("", finish="stop", usage=USAGE)).replace(b"\n\n", b"\r\n\r\n"))
        self.send_chunk(b"data: [DONE]\r\n\r\n")
        self.end_chunked()

    def s_finish_length(self, body):
        self.headers()
        self._content(["جواب مقطوع في"], finish="length")

    def s_finish_insufficient(self, body):
        self.headers()
        self.send_chunk(data_line(ds_chunk("", role="assistant")))
        self.send_chunk(data_line(ds_chunk("", finish="insufficient_system_resource",
                                           usage={"prompt_tokens": 17, "completion_tokens": 0,
                                                  "total_tokens": 17})))
        self.send_chunk(b"data: [DONE]\n\n")
        self.end_chunked()

    def s_finish_insufficient_partial(self, body):
        self.headers()
        self._content(["بداية جواب ثم"], finish="insufficient_system_resource")

    def s_finish_content_filter(self, body):
        self.headers()
        self.send_chunk(data_line(ds_chunk("", role="assistant")))
        self.send_chunk(data_line(ds_chunk("", finish="content_filter", usage=USAGE)))
        self.send_chunk(b"data: [DONE]\n\n")
        self.end_chunked()

    def s_finish_aborted(self, body):
        self.headers()
        self._content(["نصف"], finish="aborted")

    def s_error_200_json(self, body):
        # 200 with a JSON error body instead of SSE
        payload = json.dumps({"error": {"message": "Model Not Exist", "type": "invalid_request_error",
                                        "param": None, "code": "invalid_request_error"}}).encode()
        self.headers(ctype="application/json")
        self.send_chunk(payload)
        self.end_chunked()

    def s_error_midstream(self, body):
        self.headers()
        self.send_chunk(data_line(ds_chunk("جزء")))
        self.send_chunk(data_line({"error": {"message": "Service is too busy", "type": "server_error",
                                             "code": "service_unavailable"}}))
        self.send_chunk(b"data: [DONE]\n\n")
        self.end_chunked()

    def s_error_event_midstream(self, body):
        self.headers()
        self.send_chunk(data_line(ds_chunk("جزء")))
        self.send_chunk(b"event: error\n" + data_line({"error": {"message": "overloaded"}}))
        self.end_chunked()

    def s_reset_midstream(self, body):
        self.headers()
        self.send_chunk(data_line(ds_chunk("جزء ")))
        time.sleep(0.05)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        self.sock.close()

    def s_reset_preflight(self, body):
        self.headers()
        self.send_chunk(b": keep-alive\n\n")
        time.sleep(0.05)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        self.sock.close()

    def s_clean_close_no_done(self, body):
        self.headers()
        self.send_chunk(data_line(ds_chunk("نص ")))
        self.send_chunk(data_line(ds_chunk("بلا نهاية")))
        self.end_chunked()                # well-formed end of body, no finish/usage/[DONE]

    def s_close_no_content(self, body):
        # e.g. DeepSeek's own "not started inference after 10 min" close
        self.headers()
        self.keepalive_for(0.3)
        self.end_chunked()

    def s_eof_no_chunk_end(self, body):
        # FIN without the terminating 0-chunk (truncated body)
        self.headers()
        self.send_chunk(data_line(ds_chunk("نص ")))
        time.sleep(0.05)
        self.sock.shutdown(socket.SHUT_WR)
        time.sleep(0.2)

    def _status(self, status, msg):
        payload = json.dumps({"error": {"message": msg, "type": "x", "param": None, "code": str(status)}}).encode()
        self.send(b"HTTP/1.1 %d X\r\nContent-Type: application/json\r\nContent-Length: %d\r\n"
                  b"Connection: keep-alive\r\n\r\n%s" % (status, len(payload), payload))
        # No lingering here: the client keeps this connection in its pool and
        # its next request must not queue behind a server still waiting.

    def s_http_429(self, body):
        self._status(429, "Rate Limit Reached")

    def _once(self, scen: str) -> bool:
        with _LOCK:
            _SEEN[scen] = _SEEN.get(scen, 0) + 1
            return _SEEN[scen] == 1

    def s_flaky_503(self, body):
        # a blip: the first request is refused, the next one answers
        if self._once("flaky_503"):
            self._status(503, "Server Overloaded")
        else:
            self.s_normal(body)

    def s_flaky_429_retry_after(self, body):
        if self._once("flaky_429_retry_after"):
            payload = b'{"error":{"message":"Rate Limit Reached"}}'
            self.send(b"HTTP/1.1 429 X\r\nContent-Type: application/json\r\nRetry-After: 1\r\n"
                      b"Content-Length: %d\r\nConnection: keep-alive\r\n\r\n%s" % (len(payload), payload))
        else:
            self.s_normal(body)

    def s_no_thinking_field(self, body):
        # an OpenAI-compatible host that rejects DeepSeek's "thinking" field
        if "thinking" in body:
            self._status(400, "Unknown parameter: thinking")
        else:
            self.s_normal(body)

    def s_flaky_reset(self, body):
        # the connection dies before any byte of the answer, once
        if self._once("flaky_reset"):
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            self.sock.close()
        else:
            self.s_normal(body)

    def s_http_503(self, body):
        self._status(503, "Server Overloaded")

    def s_http_402(self, body):
        self._status(402, "Insufficient Balance")

    def s_http_400(self, body):
        self._status(400, "Model Not Exist")

    def s_reasoning_then_content(self, body):
        # thinking mode: reasoning_content for 2 s, then content
        self.headers()
        self.send_chunk(data_line(ds_chunk(None, reasoning="", role="assistant")))
        end = time.monotonic() + 2.0
        while time.monotonic() < end:
            if not self.send_chunk(data_line(ds_chunk(None, reasoning="أفكر "))):
                return
            time.sleep(0.1)
        self._content(["الجواب"])

    def s_reasoning_only_budget(self, body):
        # thinking mode spends the whole max_tokens on reasoning: content never comes
        self.headers()
        for _ in range(10):
            self.send_chunk(data_line(ds_chunk(None, reasoning="أفكر ")))
            time.sleep(0.02)
        self.send_chunk(data_line(ds_chunk("", finish="length", usage=USAGE)))
        self.send_chunk(b"data: [DONE]\n\n")
        self.end_chunked()

    def s_tokens_then_keepalive_hold(self, body):
        # first tokens, then a mid-answer hold with keep-alives for 8 s
        self.headers()
        self.send_chunk(data_line(ds_chunk("بداية ")))
        if not self.keepalive_for(8.0):
            return
        self._content(["تكملة"])

    def s_slow_trickle(self, body):
        # alive but slow: one token every 0.5 s for 6 s
        self.headers()
        self.send_chunk(data_line(ds_chunk("", role="assistant")))
        end = time.monotonic() + 6.0
        while time.monotonic() < end:
            if not self.send_chunk(data_line(ds_chunk("ك"))):
                return
            time.sleep(0.5)
        self._content([])

    def s_openai_usage_chunk(self, body):
        # OpenAI-style separate usage chunk with choices: []
        self.headers()
        self.send_chunk(data_line(ds_chunk("أ", include_usage=False)))
        self.send_chunk(data_line(ds_chunk("", finish="stop", include_usage=False)))
        self.send_chunk(data_line({"id": "x", "object": "chat.completion.chunk", "choices": [],
                                   "usage": {"prompt_tokens": 3, "completion_tokens": 1}}))
        self.send_chunk(b"data: [DONE]\n\n")
        self.end_chunked()


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def start() -> tuple[Server, str]:
    srv = Server(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    host, port = srv.server_address
    return srv, f"http://{host}:{port}"


def last_entry(scenario: str) -> dict | None:
    with _LOCK:
        for e in reversed(CONN_LOG):
            if e["scenario"] == scenario:
                return e
    return None
