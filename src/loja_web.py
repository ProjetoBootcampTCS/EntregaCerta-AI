"""Loja demonstrativa: catálogo real Olist, pedidos novos isolados dos dados de ML."""
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.types.json import Jsonb

from .acesso_web import conexao_web

router = APIRouter()
RAIZ = Path(__file__).resolve().parents[1]
UFS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
CATEGORIAS = {
    "beleza_saude": "Beleza e saúde", "esporte_lazer": "Esporte e lazer",
    "utilidades_domesticas": "Utilidades domésticas", "informatica_acessorios": "Informática",
    "moveis_decoracao": "Casa e decoração", "livros_interesse_geral": "Livros",
}


@lru_cache(maxsize=1)
def catalogo():
    pasta = RAIZ / "Dados/Brazilian Logistic"
    try:
        produtos = pd.read_csv(pasta / "olist_products_dataset.csv", usecols=["product_id", "product_category_name", "product_weight_g"])
        itens = pd.read_csv(pasta / "olist_order_items_dataset.csv", usecols=["product_id", "price"])
    except (OSError, ValueError):
        raise HTTPException(503, "Catálogo indisponível. Confira os arquivos originais da Olist.") from None
    resumo = itens.loc[itens.price.gt(0)].groupby("product_id").agg(preco=("price", "median"), registros=("price", "size")).reset_index()
    base = produtos.merge(resumo, on="product_id", validate="one_to_one")
    resultado = []
    for categoria, nome in CATEGORIAS.items():
        grupo = base.loc[base.product_category_name.eq(categoria)].sort_values(["registros", "product_id"], ascending=[False, True])
        if grupo.empty:
            continue
        p = grupo.iloc[0]
        centavos = int((Decimal(str(p.preco))*100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        resultado.append({"id": p.product_id, "nome": f"Item de {nome.lower()}", "categoria": nome,
                          "categoria_codigo": categoria, "preco_centavos": centavos,
                          "peso_g": None if pd.isna(p.product_weight_g) else float(p.product_weight_g)})
    return resultado


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    produto_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    quantidade: int = Field(ge=1, le=10, strict=True)


class NovoPedido(BaseModel):
    model_config = ConfigDict(extra="forbid")
    itens: list[Item] = Field(min_length=1, max_length=6)
    uf: str = Field(min_length=2, max_length=2)
    chave_requisicao: UUID

    @field_validator("uf")
    @classmethod
    def uf_valida(cls, valor):
        if valor.upper() not in UFS:
            raise ValueError("Selecione uma UF válida.")
        return valor.upper()


def apresentar(pedido, interno=False):
    resultado = {k: pedido[k] for k in ["id", "itens", "uf", "total_centavos", "status", "origem", "criado_em",
                                       "prazo_prometido", "prazo_original", "atualizado_em", "versao"]}
    if interno:
        resultado.update(eventos=pedido["eventos"], responsavel_id=pedido["responsavel_id"],
                         responsavel=pedido.get("responsavel"), cliente=pedido.get("cliente"))
    else:
        # O cliente acompanha seu pedido sem receber notas internas ou dados da equipe.
        eventos = []
        for evento in pedido["eventos"]:
            publico = {k: evento[k] for k in ("em", "status") if k in evento}
            mudancas = [m for m in evento.get("alteracoes", []) if m["campo"] == "prazo_prometido"]
            if mudancas:
                publico["alteracoes"] = mudancas
            if "status" in publico or mudancas:
                eventos.append(publico)
        resultado["eventos"] = eventos
    return resultado


@router.get("/api/loja/catalogo")
def consultar_catalogo():
    return {"produtos": catalogo(), "demonstracao": True,
            "observacao": "Produtos anonimizados e preços medianos históricos da Olist (2016–2018). Não há oferta comercial, pagamento ou envio real."}


@router.post("/api/cliente/pedidos", status_code=201)
def criar_pedido(dados: NovoPedido, request: Request):
    produtos = {p["id"]: p for p in catalogo()}
    if len({p.produto_id for p in dados.itens}) != len(dados.itens):
        raise HTTPException(422, "Agrupe as quantidades de cada produto no carrinho.")
    itens = []
    for item in dados.itens:
        produto = produtos.get(item.produto_id)
        if not produto:
            raise HTTPException(422, "Um produto não está disponível no catálogo.")
        itens.append({"produto_id": produto["id"], "nome": produto["nome"], "quantidade": item.quantidade,
                      "preco_unitario_centavos": produto["preco_centavos"]})
    total = sum(p["quantidade"] * p["preco_unitario_centavos"] for p in itens)
    assinatura = hashlib.sha256(json.dumps({"itens": sorted([i.model_dump() for i in dados.itens], key=lambda x: x["produto_id"]),
                                            "uf": dados.uf}, sort_keys=True).encode()).hexdigest()
    evento = {"status": "recebido", "em": datetime.now(timezone.utc).isoformat(), "tipo": "criacao",
              "autor": {"id": str(request.state.usuario["id"]), "nome": request.state.usuario["nome"]}}
    usuario = request.state.usuario["id"]
    with conexao_web() as conn:
        pedido = conn.execute("""INSERT INTO pedidos_demo(id,cliente_id,chave_requisicao,assinatura,itens,uf,total_centavos,eventos)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(cliente_id,chave_requisicao) DO NOTHING RETURNING *""",
            (uuid4(), usuario, dados.chave_requisicao, assinatura, Jsonb(itens), dados.uf, total, Jsonb([evento]))).fetchone()
        if not pedido:
            pedido = conn.execute("SELECT * FROM pedidos_demo WHERE cliente_id=%s AND chave_requisicao=%s", (usuario, dados.chave_requisicao)).fetchone()
            if pedido["assinatura"] != assinatura:
                raise HTTPException(409, "Esta confirmação já foi usada para outro carrinho. Atualize a página.")
    return apresentar(pedido)


@router.get("/api/cliente/pedidos")
def meus_pedidos(request: Request):
    with conexao_web() as conn:
        pedidos = conn.execute("SELECT * FROM pedidos_demo WHERE cliente_id=%s ORDER BY criado_em DESC LIMIT 100",
                               (request.state.usuario["id"],)).fetchall()
    return {"pedidos": [apresentar(p) for p in pedidos]}


@router.get("/api/cliente/pedidos/{pedido_id}")
def meu_pedido(pedido_id: UUID, request: Request):
    with conexao_web() as conn:
        pedido = conn.execute("SELECT * FROM pedidos_demo WHERE id=%s AND cliente_id=%s",
                              (pedido_id, request.state.usuario["id"])).fetchone()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado.")
    return apresentar(pedido)


@router.get("/api/analista/pedidos-loja")
def pedidos_da_loja():
    with conexao_web() as conn:
        pedidos = conn.execute("""SELECT p.*,u.nome AS cliente,r.nome AS responsavel FROM pedidos_demo p
            JOIN usuarios u ON u.id=p.cliente_id LEFT JOIN usuarios r ON r.id=p.responsavel_id
            ORDER BY p.criado_em DESC LIMIT 100""").fetchall()
    return {"pedidos": [apresentar(p, interno=True) for p in pedidos]}


@router.get("/api/analista/responsaveis")
def responsaveis():
    with conexao_web() as conn:
        usuarios = conn.execute("SELECT id,nome FROM usuarios WHERE ativo AND perfil='analista' ORDER BY nome,id").fetchall()
    return {"responsaveis": usuarios}


class Atualizacao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    versao: int = Field(ge=1, strict=True)
    status: Literal["recebido", "em_preparacao", "despachado", "entregue"] | None = None
    prazo_prometido: date | None = None
    responsavel_id: UUID | None = None
    motivo: str = Field(default="", max_length=500)


@router.patch("/api/analista/pedidos-loja/{pedido_id}")
def atualizar_pedido(pedido_id: UUID, dados: Atualizacao, request: Request):
    proximo = {"recebido": "em_preparacao", "em_preparacao": "despachado", "despachado": "entregue"}
    with conexao_web() as conn:
        pedido = conn.execute("SELECT * FROM pedidos_demo WHERE id=%s FOR UPDATE", (pedido_id,)).fetchone()
        if not pedido:
            raise HTTPException(404, "Pedido não encontrado.")
        if pedido["versao"] != dados.versao:
            raise HTTPException(409, "Outro analista atualizou este pedido. Consulte a lista novamente antes de salvar.")
        alteracoes = []
        campos = dados.model_fields_set
        if "status" in campos and dados.status != pedido["status"]:
            if proximo.get(pedido["status"]) != dados.status or dados.status is None:
                raise HTTPException(409, "Só é possível avançar para a próxima etapa do pedido.")
            alteracoes.append({"campo": "status", "anterior": pedido["status"], "novo": dados.status})
            pedido["status"] = dados.status
        if "prazo_prometido" in campos:
            prazo = dados.prazo_prometido
            if prazo is None or prazo < pedido["criado_em"].astimezone(ZoneInfo("America/Sao_Paulo")).date():
                raise HTTPException(422, "Informe uma data de entrega igual ou posterior à criação do pedido.")
            if prazo != pedido["prazo_prometido"]:
                if pedido["prazo_prometido"] and not dados.motivo.strip():
                    raise HTTPException(422, "Explique o motivo da alteração do prazo prometido.")
                alteracoes.append({"campo": "prazo_prometido", "anterior": str(pedido["prazo_prometido"]) if pedido["prazo_prometido"] else None,
                                   "novo": prazo.isoformat()})
                pedido["prazo_original"] = pedido["prazo_original"] or prazo
                pedido["prazo_prometido"] = prazo
        if "responsavel_id" in campos and dados.responsavel_id != pedido["responsavel_id"]:
            novo = None
            if dados.responsavel_id:
                novo = conn.execute("SELECT id,nome FROM usuarios WHERE id=%s AND ativo AND perfil='analista'", (dados.responsavel_id,)).fetchone()
                if not novo:
                    raise HTTPException(422, "Selecione um analista ativo como responsável.")
            anterior = conn.execute("SELECT nome FROM usuarios WHERE id=%s", (pedido["responsavel_id"],)).fetchone()
            alteracoes.append({"campo": "responsavel", "anterior": anterior["nome"] if anterior else None,
                               "novo": novo["nome"] if novo else None,
                               "anterior_id": str(pedido["responsavel_id"]) if pedido["responsavel_id"] else None,
                               "novo_id": str(dados.responsavel_id) if dados.responsavel_id else None})
            pedido["responsavel_id"] = dados.responsavel_id
        if alteracoes:
            agora = datetime.now(timezone.utc)
            evento = {"tipo": "alteracao", "em": agora.isoformat(), "alteracoes": alteracoes,
                      "autor": {"id": str(request.state.usuario["id"]), "nome": request.state.usuario["nome"]},
                      "motivo": dados.motivo.strip()}
            if any(m["campo"] == "status" for m in alteracoes):
                evento["status"] = pedido["status"]
            conn.execute("""UPDATE pedidos_demo SET status=%s,prazo_prometido=%s,prazo_original=%s,
                responsavel_id=%s,eventos=%s,atualizado_em=%s,versao=versao+1 WHERE id=%s""",
                (pedido["status"], pedido["prazo_prometido"], pedido["prazo_original"], pedido["responsavel_id"],
                 Jsonb(pedido["eventos"] + [evento]), agora, pedido_id))
        pedido = conn.execute("""SELECT p.*,u.nome AS cliente,r.nome AS responsavel FROM pedidos_demo p
            JOIN usuarios u ON u.id=p.cliente_id LEFT JOIN usuarios r ON r.id=p.responsavel_id WHERE p.id=%s""", (pedido_id,)).fetchone()
    return apresentar(pedido, interno=True)
