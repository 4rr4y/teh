"""What the fake API servers share: reading a request, answering in either API format, and serving on a port.

Each fake is a small script that the test suites start (tests/e2e/lib.py: Suite.serve); it imports this from its own
folder."""
import http.server
import json


def read_json(handler):
    """Return the request's body, parsed as JSON."""
    return json.loads(handler.rfile.read(int(handler.headers["content-length"])))

def send_json(handler, reply, code=200, headers=None):
    """Answer with reply as JSON, with this status code and any extra headers."""
    body = json.dumps(reply).encode() if not isinstance(reply, bytes) else reply
    handler.send_response(code)
    handler.send_header("content-length", len(body))
    for name, value in (headers or {}).items():
        handler.send_header(name, value)
    handler.end_headers()
    handler.wfile.write(body)

def openai_reply(message, usage=None, finish_reason="stop"):
    """Return an OpenAI-format reply with this message (default usage: 10 tokens in, 1 out)."""
    return {"model": "fake", "choices": [{"finish_reason": finish_reason, "message": message}],
            "usage": usage or {"prompt_tokens": 10, "completion_tokens": 1}}

def text(content):
    """Return an OpenAI-format assistant message with this text."""
    return {"role": "assistant", "content": content}

def tool_call(command, call_id="c1", name="shell"):
    """Return an OpenAI-format assistant message that calls the shell tool with this command."""
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps({"command": command})}}]}

class Handler(http.server.BaseHTTPRequestHandler):
    """A request handler that doesn't log each request to stderr."""
    def log_message(self, *args):
        """Log nothing."""

def serve(port, handler):
    """Serve on localhost at this port until stopped."""
    http.server.HTTPServer(("127.0.0.1", int(port)), handler).serve_forever()
