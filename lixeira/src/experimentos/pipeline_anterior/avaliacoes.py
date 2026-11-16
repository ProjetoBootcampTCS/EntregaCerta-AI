"""Notas do pedido para EDA; reputação passada dos vendedores para previsão."""
import numpy as np
import pandas as pd

ATRIBUTOS_NOTAS = ["hist_nota_vendedor_media", "hist_nota_vendedor_min",
                  "hist_avaliacoes_vendedor_media", "hist_notas_baixas_fracao",
                  "hist_vendedores_sem_nota_fracao"]


def adicionar_avaliacoes(base, reviews, itens, pedidos):
    pares = itens[["order_id", "seller_id"]].drop_duplicates()
    eventos = reviews.copy()
    eventos["disponivel_em"] = pd.to_datetime(eventos.review_answer_timestamp, errors="coerce")
    eventos = eventos.merge(pedidos[["order_id", "order_approved_at"]], on="order_id", validate="many_to_one")
    aprovacao = pd.to_datetime(eventos.order_approved_at, errors="coerce")
    eventos = eventos.loc[eventos.review_score.between(1, 5) & eventos.disponivel_em.gt(aprovacao)]
    # Uma avaliação por pedido; a primeira resposta válida evita contar revisões repetidas.
    eventos = eventos.sort_values(["disponivel_em", "review_id"]).drop_duplicates("order_id")
    retrospectivo = eventos[["order_id", "review_score", "disponivel_em"]].rename(columns={
        "review_score": "nota_proprio_pedido_eda", "disponivel_em": "nota_proprio_pedido_em_eda"})
    eventos = eventos.merge(pares, on="order_id", validate="one_to_many")
    consultas = base[["order_id", "order_approved_at"]].merge(pares, on="order_id", how="left", validate="one_to_many")
    if consultas.seller_id.isna().any():
        raise ValueError("Pedido sem vendedor para consultar reputação.")
    consultas["nota"] = 3.0
    consultas["n"] = 0.0
    consultas["baixas"] = 0.0
    consultas["ultima_nota_em"] = pd.NaT
    grupos = {k: g.sort_values("disponivel_em") for k, g in eventos.groupby("seller_id")}
    for vendedor, q in consultas.groupby("seller_id"):
        g = grupos.get(vendedor)
        if g is None:
            continue
        t = g.disponivel_em.to_numpy(dtype="datetime64[ns]")
        pos = np.searchsorted(t, pd.to_datetime(q.order_approved_at).to_numpy(dtype="datetime64[ns]"), side="left")
        notas = np.r_[0.0, g.review_score.cumsum().to_numpy()]
        baixas = np.r_[0.0, g.review_score.le(2).cumsum().to_numpy()]
        consultas.loc[q.index, "nota"] = (notas[pos] + 6) / (pos + 2)
        consultas.loc[q.index, "n"] = pos
        consultas.loc[q.index, "baixas"] = baixas[pos] / np.maximum(pos, 1)
        consultas.loc[q.index[pos > 0], "ultima_nota_em"] = t[pos[pos > 0] - 1]
    consultas["sem_nota"] = consultas.n.eq(0).astype(float)
    hist = consultas.groupby("order_id", as_index=False).agg(
        hist_nota_vendedor_media=("nota", "mean"), hist_nota_vendedor_min=("nota", "min"),
        hist_avaliacoes_vendedor_media=("n", "mean"), hist_notas_baixas_fracao=("baixas", "mean"),
        hist_vendedores_sem_nota_fracao=("sem_nota", "mean"),
        ultima_nota_historica_em=("ultima_nota_em", "max"))
    saida = base.merge(hist, on="order_id", validate="one_to_one").merge(
        retrospectivo, on="order_id", how="left", validate="one_to_one")
    if not (saida.ultima_nota_historica_em.isna() | saida.ultima_nota_historica_em.lt(pd.to_datetime(saida.order_approved_at))).all():
        raise AssertionError("Avaliação futura entrou no histórico.")
    return saida
