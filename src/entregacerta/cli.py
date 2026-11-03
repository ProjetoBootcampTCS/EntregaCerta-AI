"""Diagnóstico do ambiente; não disponibiliza previsões fictícias."""
import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys

from . import __version__
from .settings import load_settings

DEPENDENCIES = ["numpy", "pandas", "scikit-learn", "fastapi", "uvicorn", "streamlit", "plotly", "httpx", "python-dotenv", "pydantic", "pytest", "lxml"]


def tool_probe(name, args):
    executable = shutil.which(name)
    if not executable:
        return {"executable_found": False, "returncode": None, "output": "Não encontrado no PATH"}
    try:
        completed = subprocess.run([executable, *args], capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace")
        return {"executable_found": True, "returncode": completed.returncode, "output": (completed.stdout + completed.stderr).strip()[:2500]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"executable_found": True, "returncode": None, "output": type(exc).__name__}


def doctor(root=None, probe_tools=True):
    settings = load_settings(root)
    versions = {}
    for dependency in DEPENDENCIES:
        try:
            versions[dependency] = metadata.version(dependency)
        except metadata.PackageNotFoundError:
            versions[dependency] = None
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "project": "EntregaCerta AI", "version": __version__,
        "python": platform.python_version(), "platform": platform.system(),
        "independent_venv": sys.prefix != sys.base_prefix,
        "system_site_packages_disabled": "include-system-site-packages = false" in (Path(sys.prefix) / "pyvenv.cfg").read_text(encoding="utf-8").lower() if (Path(sys.prefix) / "pyvenv.cfg").is_file() else False,
        "python_312": sys.version_info[:2] == (3, 12),
        "dependencies": versions,
        "dataset_archive_configured": settings.dataset_zip is not None,
        "dataset_archive_exists": settings.dataset_zip.is_file() if settings.dataset_zip else False,
        "llm_key_present": bool(settings.llm_api_key),
        "llm_integration_tested": False,
        "business_application_available": False,
        "model_available": False,
    }
    if probe_tools:
        report["tools"] = {
            "git": tool_probe("git", ["--version"]),
            "docker_client": tool_probe("docker", ["--version"]),
            "docker_engine": tool_probe("docker", ["version", "--format", "{{json .}}"]),
            "terraform": tool_probe("terraform", ["version", "-json"]),
        }
    report["python_environment_ok"] = report["independent_venv"] and report["system_site_packages_disabled"] and report["python_312"] and all(versions.values())
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ferramentas do EntregaCerta AI — etapa 2")
    sub = parser.add_subparsers(dest="command", required=True)
    diag = sub.add_parser("doctor", help="Conferir Python, pacotes e ferramentas sem expor segredos")
    diag.add_argument("--output", type=Path)
    diag.add_argument("--skip-tools", action="store_true")
    sub.add_parser("contract", help="Exibir o contrato do problema")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        report = doctor(probe_tools=not args.skip_tools)
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        print(payload)
        return 0 if report["python_environment_ok"] else 1
    print((Path.cwd() / "config/contrato_problema.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
