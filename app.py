"""Local-only review server. No external write operations exist."""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from connectors import ROOT, Samples, Freshdesk, SafeError, load_env, read_data, scrub
from domain import Ticket
from engine import analyze
import local_review
import dialogflow_knowledge
import pilot_review
import chat_service
from chat_model import ModelUnavailable


def make_handler(mode, reader):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log ticket content, URLs, request bodies, or credentials.

        def send(self, value, status=200, kind="application/json"):
            if kind == "application/json":
                value = json.dumps(scrub(scrub(value, os.environ.get("FRESHDESK_API_KEY", "")), os.environ.get("OPENAI_API_KEY", ""))).encode()
            self.send_response(status)
            for k, v in {"Content-Type": kind, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                         "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"}.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(value)

        def local_request(self):
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            origin = self.headers.get("Origin")
            return self.headers.get("Host") in allowed and (not origin or origin in {"http://" + h for h in allowed})

        def result(self, ticket):
            return {"ticket": ticket.to_dict(), "review": analyze(ticket, read_data("knowledge.json"), read_data("coverage.json"), read_data('source_catalog.json'))}

        def do_GET(self):
            if not self.local_request():
                return self.send({"error": "Local origin required"}, 403)
            path = urlsplit(self.path)
            try:
                if path.path == '/api/dialogflow-import':
                    return self.send(dialogflow_knowledge.listing(local_review.read('dialogflow_import.json',{'summary':{},'items':[]})))
                if path.path == "/api/chat/status":
                    return self.send(chat_service.settings())
                if path.path == "/api/status":
                    return self.send({"mode": mode, "engine": "Rules + approved-source templates", "read_only": True})
                if path.path == "/api/tickets":
                    return self.send(reader.list_tickets())
                if path.path == '/api/pilot-review':
                    return self.send(pilot_review.listing())
                if path.path == '/api/history-review':
                    return self.send(local_review.listing())
                if path.path == '/api/draft-comparisons':
                    return self.send({'items':local_review.read('comparisons.json',[])})
                if path.path == "/api/review":
                    ticket_id = parse_qs(path.query).get("id", [""])[0]
                    return self.send(self.result(reader.get_ticket(ticket_id)))
                if path.path == "/api/references":
                    return self.send({"knowledge": read_data("knowledge.json"), "coverage": read_data("coverage.json"), "source_catalog":read_data('source_catalog.json')})
                files = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8"), "/chat": ("chat.html", "text/html; charset=utf-8"), "/dialogflow": ("dialogflow.html", "text/html; charset=utf-8"), "/dialogflow.js": ("dialogflow.js", "text/javascript; charset=utf-8"), "/chat.js": ("chat.js", "text/javascript; charset=utf-8"), "/chat.css": ("chat.css", "text/css; charset=utf-8")}
                if path.path in files:
                    file, kind = files[path.path]
                    return self.send((ROOT / "static" / file).read_bytes(), kind=kind)
                self.send({"error": "Not found"}, 404)
            except SafeError as exc:
                self.send({"error": str(exc)}, 400)
            except Exception:
                self.send({"error": "Review failed. Check local data structure and retry."}, 500)

        def do_POST(self):
            if not self.local_request():
                return self.send({"error": "Local origin required"}, 403)
            if self.path == '/api/chat':
                try:
                    if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.send({'error':'JSON content required'},415)
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=12000:raise ValueError('Chat request is too large.')
                    return self.send(chat_service.chat(json.loads(self.rfile.read(size))))
                except ValueError as exc:return self.send({'error':str(exc)},400)
                except ModelUnavailable as exc:return self.send({'error':str(exc),'response_kind':exc.code,'trace':exc.trace,'model_attempted':exc.attempted},503)
                except Exception:return self.send({'error':'Chat unavailable. Retry or start a new chat.'},500)
            if self.path in ('/api/history-review','/api/pilot-review'):
                try:
                    if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                        return self.send({'error':'JSON content required'},415)
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=65000:raise ValueError('Invalid review size')
                    data=scrub(json.loads(self.rfile.read(size)),os.environ.get('FRESHDESK_API_KEY',''))
                    return self.send(pilot_review.save(data) if self.path=='/api/pilot-review' else local_review.save(data))
                except (ValueError,TypeError):
                    return self.send({'error':'Review could not be saved. Check text and decision, or reload if another tab changed it.'},400)
                except OSError:
                    return self.send({'error':'Local review storage unavailable'},500)
            if mode != "sample" or self.path != "/api/preview":
                return self.send({"error": "Write operations are unavailable"}, 405)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 100_000:
                    return self.send({"error": "Sample preview must be under 100 KB"}, 413)
                data = scrub(json.loads(self.rfile.read(size)), os.environ.get("FRESHDESK_API_KEY", ""))
                data["source"] = "sample"
                return self.send(self.result(Ticket.from_dict(data)))
            except Exception:
                return self.send({"error": "Invalid ticket JSON. Check the common ticket format."}, 400)

        def do_PUT(self):
            self.send({"error": "Write operations are unavailable"}, 405)
        do_PATCH = do_DELETE = do_PUT
    return Handler


def main():
    load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["sample", "freshdesk"], default=os.environ.get("SUPPORT_MODE", "sample"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.mode not in ("sample", "freshdesk"):
        raise SystemExit("Invalid SUPPORT_MODE; choose sample or freshdesk")
    try:
        reader = Samples() if args.mode == "sample" else Freshdesk()
    except SafeError as exc:
        raise SystemExit(str(exc)) from None
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.mode, reader))
    print(f"omniQ support sandbox: http://127.0.0.1:{args.port} ({args.mode}, advisory only)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
