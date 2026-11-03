"""Prévia local dos diagramas; não serve a aplicação, dados ou arquivo .env."""
import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = ROOT / "docs/diagramas"


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/__export_bpmn" or self.headers.get("X-EntregaCerta-Preview") != "planning-local":
            self.send_error(403)
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self.send_error(415)
            return
        size = int(self.headers.get("Content-Length", "0"))
        if size <= 0 or size > 2 * 1024 * 1024:
            self.send_error(413)
            return
        try:
            data = json.loads(self.rfile.read(size))
            svg = data["svg"]
            xml = data["xml"]
            if ET.fromstring(svg).tag != "{http://www.w3.org/2000/svg}svg":
                raise ValueError("SVG inválido")
            if ET.fromstring(xml).tag != "{http://www.omg.org/spec/BPMN/20100524/MODEL}definitions":
                raise ValueError("BPMN inválido")
            (DIAGRAMS / "processo.svg").write_text(svg, encoding="utf-8")
            validation = ROOT / "docs/validacao"
            validation.mkdir(exist_ok=True)
            (validation / "processo_roundtrip.bpmn").write_text(xml, encoding="utf-8")
            report = {"rendered_at_utc": datetime.now(timezone.utc).isoformat(), "renderer": "bpmn-js 18.16.0", "import_succeeded": True, "warnings": data["warnings"], "svg_exported": True, "xml_roundtrip_exported": True}
            (validation / "bpmn_render.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except (ValueError, KeyError, ET.ParseError):
            self.send_error(400)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"saved":true}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    handler = partial(Handler, directory=str(DIAGRAMS))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Prévia de documentação: http://127.0.0.1:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
