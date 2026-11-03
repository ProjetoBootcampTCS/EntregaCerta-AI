"""Obter schemas oficiais e renderizador BPMN fixado, sem baixar dados de treinamento."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = "18.16.0"


def fetch(url, limit=30 * 1024 * 1024):
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Recurso excede limite de aquisição")
    return data


def main():
    manifest = []
    schemas = ROOT / "docs/validacao/bpmn-xsd"
    schemas.mkdir(parents=True, exist_ok=True)
    for name in ["BPMN20.xsd", "BPMNDI.xsd", "DC.xsd", "DI.xsd", "Semantic.xsd"]:
        url = "https://www.omg.org/spec/BPMN/20100501/" + name
        path = schemas / name
        if not path.exists():
            path.write_bytes(fetch(url))
        manifest.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "url": url, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    url = f"https://registry.npmjs.org/bpmn-js/-/bpmn-js-{VERSION}.tgz"
    cache = ROOT / ".local" / f"bpmn-js-{VERSION}.tgz"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        cache.write_bytes(fetch(url))
    vendor = ROOT / "docs/diagramas/vendor/bpmn-js"
    vendor.mkdir(parents=True, exist_ok=True)
    with tarfile.open(cache, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            rel = Path(member.name).relative_to("package")
            text = rel.as_posix()
            keep = text in {"LICENSE", "README.md", "dist/bpmn-modeler.production.min.js"} or (text.startswith("dist/assets/") and rel.suffix in {".css", ".woff", ".woff2", ".ttf", ".eot", ".svg"})
            if not keep:
                continue
            target = (vendor / rel).resolve()
            if not target.is_relative_to(vendor.resolve()):
                raise ValueError("Caminho de pacote inesperado")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
            manifest.append({"path": str(target.relative_to(ROOT)).replace("\\", "/"), "url": url, "version": VERSION, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    (ROOT / "docs/validacao/assets_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"assets": len(manifest), "bpmn_js_version": VERSION}))


if __name__ == "__main__":
    main()
