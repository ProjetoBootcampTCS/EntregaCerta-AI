# Iniciar a API = .\.venv\Scripts\python.exe -m uvicorn src.api:app --reload --host 127.0.0.1 --port 8000

from pydantic import BaseModel, Field, ConfigDict
from .assistente_genai import responder
import logging
from datetime import date, datetime, timezone
from threading import Lock
from typing import Literal
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from .acesso_web import politica_acesso, router as router_acesso
from .loja_web import router as router_loja
from .relatorio_pdf import registrar_analise, gerar_relatorio

from .consultar_postgresql import consultar_pedidos
from .pedidos_web import montar_lote, filtrar_lote
from .inferencia import (
    carregar_modelos,
    prever_pedidos,
    priorizar_pedidos,
)

app = FastAPI(
    title="EntregaCerta AI",
    description="Priorização de pedidos com risco de atraso.",
    version="0.2.0",
    dependencies=[Depends(politica_acesso)],
    docs_url=None, redoc_url=None, openapi_url=None,
)
app.include_router(router_acesso)
app.include_router(router_loja)


@app.exception_handler(RequestValidationError)
async def dados_invalidos(request, erro):
    # Não devolve senhas ou outros campos enviados junto às mensagens de validação.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in erro.errors()
    ]})

PASTA_FRONTEND = Path(__file__).resolve().parents[1] / "frontend"

class AssetsPublicos(StaticFiles):
    async def get_response(self, path, scope):
        # HTML privado, ZIPs de versões e arquivos de dados não são assets públicos.
        if Path(path).suffix.lower() not in {".css", ".js", ".svg", ".png", ".jpg", ".webp", ".woff", ".woff2", ".ico"}:
            raise HTTPException(404, "Arquivo não encontrado.")
        return await super().get_response(path, scope)


@app.middleware("http")
async def cabecalhos_seguranca(request: Request, call_next):
    resposta = await call_next(request)
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Referrer-Policy"] = "same-origin"
    if not request.url.path.startswith("/static/"):
        resposta.headers["Cache-Control"] = "no-store"
    return resposta


app.mount(
    "/static",
    AssetsPublicos(directory=PASTA_FRONTEND),
    name="static",
)


@app.get("/", include_in_schema=False)
def pagina_inicial():
    return FileResponse(PASTA_FRONTEND / "index.html")


@app.get("/cliente", include_in_schema=False)
def pagina_cliente():
    return FileResponse(PASTA_FRONTEND / "cliente.html")


@app.get("/entrar", include_in_schema=False)
def pagina_login():
    return FileResponse(PASTA_FRONTEND / "entrar.html")


@app.get("/dashboard", include_in_schema=False)
def pagina_dashboard():
    return FileResponse(PASTA_FRONTEND / "dashboard.html")


@app.get("/pedidos", include_in_schema=False)
def pagina_pedidos():
    return FileResponse(PASTA_FRONTEND / "pedidos.html")


@lru_cache(maxsize=1)
def obter_modelos():
    # Evita carregar os mesmos arquivos a cada consulta.
    return carregar_modelos()


# Um lote em memória por processo; filtros não consultam nem pontuam novamente.
_trava_lote = Lock()


@lru_cache(maxsize=1)
def obter_lote_pedidos():
    pedidos = consultar_pedidos("validacao")
    pacote, modelo = obter_modelos()
    previsoes = priorizar_pedidos(prever_pedidos(pedidos, pacote, modelo), pacote["fracao_fila"])
    return montar_lote(pedidos, previsoes), datetime.now(timezone.utc).isoformat(), float(pacote["fracao_fila"])


@app.get("/api/pedidos")
def consultar_lista_pedidos(
    pagina: int = Query(1, ge=1),
    tamanho: int = Query(25, ge=25, le=100),
    busca: str = Query("", max_length=100),
    uf: str = Query("", max_length=2),
    categoria: str = Query("", max_length=100),
    prioridade: Literal["todos", "0", "1"] = "todos",
    inicio: date | None = None,
    fim: date | None = None,
    score_min: float = Query(0, ge=0, le=1),
    score_max: float = Query(1, ge=0, le=1),
    ordem: Literal["score-desc", "score-asc", "data-desc", "data-asc", "valor-desc"] = "score-desc",
    atualizar: bool = False,
):
    if tamanho not in (25, 50, 100):
        raise HTTPException(422, "Escolha 25, 50 ou 100 pedidos por página.")
    if score_min > score_max or (inicio and fim and inicio > fim):
        raise HTTPException(422, "O início do intervalo deve ser menor ou igual ao fim.")
    try:
        with _trava_lote:
            if atualizar:
                obter_lote_pedidos.cache_clear()
            lote, consultado_em, fracao = obter_lote_pedidos()
        resposta = filtrar_lote(
            lote, pagina=pagina, tamanho=tamanho, busca=busca, uf=uf.upper(),
            categoria=categoria, prioridade=prioridade, inicio=inicio, fim=fim,
            score_min=score_min, score_max=score_max, ordem=ordem,
        )
        return {**resposta, "consultado_em": consultado_em, "fracao_fila": fracao,
                "contexto": "Demonstração histórica — validação Olist"}
    except Exception:
        logging.exception("Falha ao consultar o catálogo de pedidos.")
        raise HTTPException(503, "Não foi possível consultar os pedidos. Tente atualizar o lote.") from None


@app.get("/api/prioridades")
def consultar_prioridades(request: Request = None):
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
        dados = {
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
        if request is not None:
            dados.update(registrar_analise(dados, request.state.usuario["id"]))
        return dados

    except Exception:
        logging.exception("Falha ao consultar e priorizar pedidos.")
        raise HTTPException(
            status_code=500,
            detail="Nao foi possivel gerar a fila de pedidos.",
        ) from None

class PerguntaAssistente(BaseModel):
    pergunta: str = Field(min_length=1, max_length=1000)


@app.post("/api/assistente")
def conversar_assistente(mensagem: PerguntaAssistente, request: Request):
    pergunta = mensagem.pergunta.strip() 

    if not pergunta:
        raise HTTPException(
            status_code=400,
            detail="Digite uma pergunta."
        )

    if request.state.usuario["perfil"] == "cliente":
        # Orientação da loja; não consulta ML nem envia dados de outros clientes.
        return responder(pergunta, {
            "publico": "cliente",
            "contexto": "Área do cliente — loja demonstrativa EntregaCerta AI",
            "funcionalidades": "Catálogo, carrinho, meus pedidos, prazo prometido e histórico de etapas e prazos.",
            "prazo": "Informado pela equipe; se não definido, não há uma data prometida disponível.",
            "limites": "Sem pagamento ou envio real. Este chat não consulta pedidos individuais nem estima datas ou probabilidades de atraso. Consulte Meus pedidos para os dados registrados.",
        })

    # Reutiliza a consulta e a previsão existentes para o perfil analista.
    dados = consultar_prioridades()

    # Envia somente o resumo necessário para a GenAI.
    contexto = {
        "contexto": dados["contexto"],
        "pedidos_avaliados": dados["pedidos_avaliados"],
        "pedidos_na_fila": dados["pedidos_na_fila"],
        "percentual_configurado_da_fila": (
            100 * dados["fracao_fila"]
        ),
        "observacao": dados["observacao"],
        "regra": (
            "A fila prioriza os pedidos "
            "com maiores scores do modelo."
        )
    }

    return responder(pergunta, contexto)


class PedidoRelatorio(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analise_id: str = Field(pattern=r"^[A-Za-z0-9_-]{32}$")


@app.post("/api/analista/relatorio-pdf")
def baixar_relatorio(dados: PedidoRelatorio, request: Request):
    # A política global exige analista, sessão, origem permitida e CSRF.
    # Só aceita o identificador; números e scores vêm do snapshot privado do servidor.
    try:
        pdf, genai = gerar_relatorio(dados.analise_id, request.state.usuario["id"])
    except HTTPException:
        raise
    except Exception:
        logging.exception("Falha ao montar o relatório PDF.")
        raise HTTPException(503, "Não foi possível gerar o relatório. Tente novamente.") from None
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": 'attachment; filename="entregacerta-relatorio.pdf"',
        "X-Resumo-GenAI": "incluido" if genai else "indisponivel",
    })
