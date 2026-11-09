# Iniciar a API = .\.venv\Scripts\python.exe -m uvicorn src.api:app --reload --host 127.0.0.1 --port 8000


import logging
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .consultar_postgresql import consultar_pedidos
from .inferencia import (
    carregar_modelos,
    prever_pedidos,
    priorizar_pedidos,
)

app = FastAPI(
    title="EntregaCerta AI",
    description="Priorização de pedidos com risco de atraso.",
    version="0.1.0",
)

PASTA_FRONTEND = Path(__file__).resolve().parents[1] / "frontend"

app.mount(
    "/static",
    StaticFiles(directory=PASTA_FRONTEND),
    name="static",
)


@app.get("/", include_in_schema=False)
def pagina_inicial():
    return FileResponse(PASTA_FRONTEND / "index.html")

@lru_cache(maxsize=1)
def obter_modelos():
    # Evita carregar os mesmos arquivos a cada consulta.
    return carregar_modelos()


@app.get("/api/prioridades")
def consultar_prioridades():
    try:
        # 1. Busca os pedidos reais de validação.
        pedidos = consultar_pedidos("validacao")

        # 2. Executa o tratamento, o modelo e a priorização.
        pacote, modelo = obter_modelos()
        previsoes = prever_pedidos(pedidos, pacote, modelo)
        resultado = priorizar_pedidos(
            previsoes,
            pacote["fracao_fila"],
        )

        # 3. Seleciona a fila e organiza por score.
        fila = resultado.loc[
            resultado["prioridade"].eq(1)
        ].sort_values(
            ["score_atraso", "order_id"],
            ascending=[False, True],
        )

        # 4. Devolve os dados para o frontend.
        return {
            "contexto": "Demonstracao historica — validacao Olist",
            "pedidos_avaliados": len(resultado),
            "pedidos_na_fila": len(fila),
            "fracao_fila": float(pacote["fracao_fila"]),
            "observacao": (
                "O score indica prioridade relativa de risco; "
                "nao representa uma probabilidade calibrada."
            ),
            "fila": fila.to_dict(orient="records"),
        }

    except Exception:
        logging.exception("Falha ao consultar e priorizar pedidos.")
        raise HTTPException(
            status_code=500,
            detail="Nao foi possivel gerar a fila de pedidos.",
        ) from None