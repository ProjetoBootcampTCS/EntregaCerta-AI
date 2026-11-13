"""Consulta paginada do lote já pontuado, sem alterar a fila do modelo."""

import json
import math

import pandas as pd


# Somente campos da view de inferência; não expõe alvos ou desfechos futuros.
CAMPOS = [
    "order_id", "order_approved_at", "customer_state", "uf_origem",
    "categoria_principal", "quantidade_itens", "quantidade_vendedores",
    "valor_itens", "valor_frete", "valor_pago", "peso_total_g",
    "distancia_media_vendedores_km", "distancia_max_vendedores_km",
    "prazo_prometido_dias", "tipo_pagamento_principal", "parcelas_maximas",
]


def montar_lote(pedidos, previsoes):
    """Une atributos e scores uma única vez, com conferência das chaves."""
    lote = pedidos.reindex(columns=CAMPOS).merge(
        previsoes[["order_id", "score_atraso", "prioridade"]],
        on="order_id", how="outer", validate="one_to_one", indicator=True,
    )
    if lote.empty or not lote["_merge"].eq("both").all():
        raise ValueError("Pedidos e previsões precisam ter as mesmas chaves.")
    if not lote["score_atraso"].between(0, 1).all():
        raise ValueError("Scores inválidos no lote.")
    if not lote["prioridade"].isin([0, 1]).all():
        raise ValueError("Prioridades inválidas no lote.")
    lote = lote.drop(columns="_merge")
    lote["order_approved_at"] = pd.to_datetime(lote["order_approved_at"], errors="coerce")
    for campo in ["customer_state", "uf_origem", "categoria_principal"]:
        lote[campo] = lote[campo].replace("NAO_INFORMADO", None)
    return lote


def filtrar_lote(lote, *, pagina=1, tamanho=25, busca="", uf="", categoria="",
                 prioridade="todos", inicio=None, fim=None, score_min=0,
                 score_max=1, ordem="score-desc"):
    """Filtra todo o lote antes de paginar. Nunca redefine a prioridade."""
    mascara = lote["score_atraso"].between(score_min, score_max)
    if busca.strip():
        mascara &= lote["order_id"].str.contains(busca.strip(), case=False, regex=False)
    if uf:
        mascara &= lote["customer_state"].eq(uf)
    if categoria:
        mascara &= lote["categoria_principal"].eq(categoria)
    if prioridade != "todos":
        mascara &= lote["prioridade"].eq(int(prioridade))
    if inicio:
        mascara &= lote["order_approved_at"].dt.date >= inicio
    if fim:
        mascara &= lote["order_approved_at"].dt.date <= fim
    filtrados = lote.loc[mascara]
    campo, crescente = {
        "score-desc": ("score_atraso", False),
        "score-asc": ("score_atraso", True),
        "data-desc": ("order_approved_at", False),
        "data-asc": ("order_approved_at", True),
        "valor-desc": ("valor_pago", False),
    }[ordem]
    filtrados = filtrados.sort_values([campo, "order_id"], ascending=[crescente, True], na_position="last")
    paginas = max(1, math.ceil(len(filtrados) / tamanho))
    pagina = min(pagina, paginas)
    recorte = filtrados.iloc[(pagina - 1) * tamanho:pagina * tamanho]
    # Pandas converte NaN/NaT em null e datas em ISO, compatíveis com JSON.
    registros = json.loads(recorte.to_json(orient="records", date_format="iso", double_precision=15))
    return {
        "pedidos": registros,
        "total": len(lote),
        "na_fila": int(lote["prioridade"].sum()),
        "filtrados": len(filtrados),
        "filtrados_na_fila": int(filtrados["prioridade"].sum()),
        "pagina": pagina, "paginas": paginas, "tamanho": tamanho,
        "opcoes": {
            "ufs": sorted(lote["customer_state"].dropna().unique().tolist()),
            "categorias": sorted(lote["categoria_principal"].dropna().unique().tolist()),
        },
    }
