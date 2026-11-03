"""Configuração explícita e sem exposição de credenciais."""
from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    database_path: Path
    dataset_zip: Path | None
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    frontend_port: int = 8502
    llm_api_key: str = field(default="", repr=False)
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 30.0


def load_settings(root: Path | None = None, environ: dict | None = None) -> Settings:
    root = (root or Path.cwd()).resolve()
    env = {**dotenv_values(root / ".env"), **(os.environ if environ is None else environ)}

    def value(name, default=""):
        return env.get("ENTREGACERTA_" + name) or default

    def local_path(raw):
        path = Path(raw).expanduser()
        return (root / path).resolve() if not path.is_absolute() else path.resolve()

    api_port = int(value("API_PORT", "8000"))
    frontend_port = int(value("FRONTEND_PORT", "8502"))
    timeout = float(value("LLM_TIMEOUT_SECONDS", "30"))
    if not (1 <= api_port <= 65535 and 1 <= frontend_port <= 65535):
        raise ValueError("Portas devem estar entre 1 e 65535")
    if api_port == frontend_port:
        raise ValueError("Backend e frontend precisam de portas diferentes")
    if timeout <= 0 or timeout > 120:
        raise ValueError("Timeout de GenAI deve ser maior que zero e no máximo 120 segundos")
    archive = value("DATASET_ZIP")
    return Settings(
        project_root=root, data_dir=local_path(value("DATA_DIR", "data")),
        database_path=local_path(value("DB_PATH", "data/entregacerta.sqlite3")),
        dataset_zip=local_path(archive) if archive else None,
        api_host=value("API_HOST", "127.0.0.1"), api_port=api_port,
        frontend_port=frontend_port, llm_api_key=value("LLM_API_KEY"),
        llm_base_url=value("LLM_BASE_URL"), llm_model=value("LLM_MODEL"),
        llm_timeout_seconds=timeout,
    )
