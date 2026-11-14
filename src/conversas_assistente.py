"""Memória curta por sessão e contexto; feedback separado dos dados de ML."""
from collections import OrderedDict
from dataclasses import dataclass, field
from hashlib import sha256
import os
from threading import Lock
from time import monotonic
from uuid import uuid4

from fastapi import HTTPException

from .acesso_web import conexao_web

TTL = 30 * 60
MAX_CONVERSAS = 100
MAX_PERGUNTAS = 20
PARES_MEMORIA = 6


@dataclass
class Conversa:
    dono: str
    pedido: dict | None
    acesso: float = field(default_factory=monotonic)
    historico: list = field(default_factory=list)
    requisicoes: dict = field(default_factory=dict)
    trava: Lock = field(default_factory=Lock)


_conversas = OrderedDict()
_trava = Lock()


def dono_sessao(usuario):
    # CSRF é diferente em cada login. Não guardamos o token em texto claro.
    return sha256(f'{usuario["id"]}:{usuario["perfil"]}:{usuario["csrf"]}'.encode()).hexdigest()


def criar(usuario, pedido=None):
    with _trava:
        agora = monotonic()
        for chave, conversa in list(_conversas.items()):
            if agora - conversa.acesso > TTL and not conversa.trava.locked():
                del _conversas[chave]
        if len(_conversas) >= MAX_CONVERSAS:
            raise HTTPException(503, "O assistente está ocupado. Tente novamente em instantes.")
        identificador = str(uuid4())
        _conversas[identificador] = Conversa(dono_sessao(usuario), pedido)
        return identificador


def obter(identificador, usuario):
    with _trava:
        conversa = _conversas.get(str(identificador))
        if conversa is None or conversa.dono != dono_sessao(usuario):
            raise HTTPException(404, "Conversa indisponível. Inicie uma nova conversa.")
        if monotonic() - conversa.acesso > TTL and not conversa.trava.locked():
            del _conversas[str(identificador)]
            raise HTTPException(410, "A conversa expirou. Inicie uma nova conversa.")
        conversa.acesso = monotonic()
        return conversa


def apagar(identificador, usuario):
    obter(identificador, usuario)
    with _trava:
        _conversas.pop(str(identificador), None)


def conversar(identificador, usuario, requisicao, pergunta, contexto, gerar):
    conversa = obter(identificador, usuario)
    if not conversa.trava.acquire(blocking=False):
        raise HTTPException(409, "Aguarde a resposta anterior antes de enviar outra pergunta.")
    try:
        chave = str(requisicao)
        anterior = conversa.requisicoes.get(chave)
        if anterior and anterior["pergunta"] != pergunta:
            raise HTTPException(409, "Esta tentativa pertence a outra pergunta.")
        if anterior and anterior.get("resultado"):
            return anterior["resultado"]
        if anterior is None:
            if len(conversa.requisicoes) >= MAX_PERGUNTAS:
                raise HTTPException(409, "Limite desta conversa atingido. Inicie uma nova conversa.")
            conversa.requisicoes[chave] = {"pergunta": pergunta}
        resultado = gerar(pergunta, contexto, historico=list(conversa.historico))
        # Texto truncado não entra na memória nem recebe avaliação.
        if resultado.get("disponivel") and resultado.get("motivo_termino") not in (None, "STOP"):
            resultado = {"disponivel": False, "resposta": "A IA não concluiu a resposta. Tente novamente."}
        resultado = {**resultado, "conversa_id": str(identificador)}
        if resultado.get("disponivel"):
            resultado["resposta_id"] = str(uuid4())
            conversa.requisicoes[chave].update(resultado=resultado, modelo=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"))
            conversa.historico.extend([
                {"papel": "user", "texto": pergunta},
                {"papel": "model", "texto": resultado["resposta"]},
            ])
            conversa.historico = conversa.historico[-PARES_MEMORIA * 2:]
        return resultado
    finally:
        conversa.acesso = monotonic()
        conversa.trava.release()


def avaliar(usuario, conversa_id, resposta_id, avaliacao, categoria):
    conversa = obter(conversa_id, usuario)
    with conversa.trava:
        registro = next((r.copy() for r in conversa.requisicoes.values()
                         if r.get("resultado", {}).get("resposta_id") == str(resposta_id)), None)
    if registro is None:
        raise HTTPException(404, "Resposta indisponível para avaliação.")
    if avaliacao == 1:
        categoria = None
    elif not categoria:
        raise HTTPException(422, "Selecione o motivo da avaliação.")
    with conexao_web() as conn:
        conn.execute("""
            INSERT INTO assistente_feedback
                (resposta_id, usuario_id, avaliacao, categoria, pergunta, resposta, contexto, modelo)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (resposta_id) DO UPDATE SET
                avaliacao=EXCLUDED.avaliacao, categoria=EXCLUDED.categoria, atualizado_em=now()
            WHERE assistente_feedback.usuario_id=EXCLUDED.usuario_id
        """, (str(resposta_id), usuario["id"], avaliacao, categoria, registro["pergunta"],
              registro["resultado"]["resposta"], (conversa.pedido or {}).get("tipo", "geral"), registro["modelo"]))
    return {"salvo": True, "avaliacao": avaliacao, "categoria": categoria}


def contexto_loja(usuario, pedido_id):
    """Autorização em cada turno; somente campos operacionais seguem para a IA."""
    with conexao_web() as conn:
        pedido = conn.execute("""
            SELECT status, uf, prazo_prometido, prazo_original, eventos, responsavel_id
            FROM pedidos_demo WHERE id=%s AND (%s='analista' OR cliente_id=%s)
        """, (pedido_id, usuario["perfil"], usuario["id"])).fetchone()
    if pedido is None:
        raise HTTPException(404, "Pedido não encontrado.")
    eventos = []
    for evento in pedido["eventos"][-15:]:
        publico = {k: evento[k] for k in ("em", "status") if k in evento}
        publico["alteracoes"] = [{k: a.get(k) for k in ("campo", "anterior", "novo")}
                                for a in evento.get("alteracoes", []) if a.get("campo") == "prazo_prometido"]
        eventos.append(publico)
    return {
        "publico": usuario["perfil"],
        "contexto": "Pedido selecionado na loja demonstrativa — sem pagamento ou envio real",
        "pedido": {"status": pedido["status"], "uf": pedido["uf"],
                   "prazo_prometido": str(pedido["prazo_prometido"]) if pedido["prazo_prometido"] else None,
                   "prazo_original": str(pedido["prazo_original"]) if pedido["prazo_original"] else None,
                   "responsavel_atribuido": pedido["responsavel_id"] is not None,
                   "historico_recente": eventos},
        "limites": "Este pedido demonstrativo não tem previsão individual de ML. Prazo nulo significa não definido. Nomes e justificativas internas não são enviados.",
    }
