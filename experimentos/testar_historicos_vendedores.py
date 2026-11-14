"""Audita rótulos e testa históricos pontuais de vendedores, sem alterar a API.

Execute na raiz: python -m experimentos.testar_historicos_vendedores --snapshot
Sem --snapshot, consulta novamente o PostgreSQL em modo somente leitura.
Os resultados ficam em Modelos/experimento_historicos; teste não é avaliado.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, confusion_matrix,
                             f1_score, precision_recall_curve, precision_score, recall_score)
from threadpoolctl import threadpool_limits

from .experimento_ctgan import consultar_base, hash_base
from src.preparar_dados import RAIZ, COLUNAS_PREVISAO, PASTA_ORIGINAIS
from src.tratar_dados_ml import (CATEGORICAS, NUMERICAS, corrigir_distancias,
                             criar_preprocessador, limpar_atributos,
                             selecionar_coorte, separar_por_tempo, sha256)

PASTA = RAIZ / "Modelos/experimento_historicos"
CORTE_VALIDACAO = pd.Timestamp("2018-01-01")
CORTE_TESTE = pd.Timestamp("2018-05-01")
COLUNAS_HISTORICO = [
    "hist_observados_media", "hist_observados_min",
    "hist_taxa_atraso_media", "hist_taxa_atraso_max",
    "hist_taxa_atraso_90d_media", "hist_taxa_atraso_90d_max",
    "hist_sem_desfecho_fracao", "hist_postagem_dias_media", "hist_postagem_dias_max",
    "hist_entrega_dias_media", "hist_entrega_dias_max",
    "hist_pedidos_30d_media", "hist_pedidos_30d_max", "hist_folga_promessa_dias",
]


def disponibilidade_revisada(base):
    """Mesmo alvo observado; positivo conhecível após encerrar o dia prometido.

    Restrito à coorte retrospectiva de entregues. Pressupõe promessa estável e
    monitoramento pontual da ausência de entrega, sem latência de atualização.
    Não generaliza a pedidos cancelados ou ainda sem desfecho no arquivo.
    """
    fim_prazo = base.order_estimated_delivery_date.dt.normalize() + pd.Timedelta(days=1)
    return base.order_delivered_customer_date.where(base.atrasou.eq(0), fim_prazo)


def acumulados_anteriores(eventos, consultas, data, valores, janela_dias=None):
    """Soma eventos estritamente anteriores a cada consulta (mesmo seller_id).

    searchsorted('left') exclui eventos no mesmo instante da aprovação.
    Janela, quando usada, é [aprovação - dias, aprovação).
    """
    saida = pd.DataFrame(0.0, index=consultas.index, columns=valores)
    ultimo = pd.Series(pd.NaT, index=consultas.index, dtype="datetime64[ns]")
    grupos = {k: g.sort_values(data) for k, g in eventos.groupby("seller_id")}
    for vendedor, consulta in consultas.groupby("seller_id"):
        grupo = grupos.get(vendedor)
        if grupo is None or grupo.empty:
            continue
        tempos = grupo[data].to_numpy(dtype="datetime64[ns]")
        agora = consulta.order_approved_at.to_numpy(dtype="datetime64[ns]")
        direita = np.searchsorted(tempos, agora, side="left")
        somas = np.vstack([np.zeros(len(valores)), grupo[valores].to_numpy(float).cumsum(axis=0)])
        total = somas[direita]
        if janela_dias is not None:
            esquerda = np.searchsorted(tempos, agora - np.timedelta64(janela_dias, "D"), side="left")
            total = total - somas[esquerda]
        saida.loc[consulta.index] = total
        tem = direita > 0
        ultimo.loc[consulta.index[tem]] = tempos[direita[tem] - 1]
    return saida, ultimo


def preparar_eventos(pedidos, itens):
    """Eventos observados; status final só restringe desfechos de entregues.

    Volume de aprovações inclui também pedidos não entregues. Uma associação
    pedido-vendedor conta uma vez, independentemente da quantidade de itens.
    Postagem/entrega são do pedido inteiro: não medem culpa de um vendedor.
    """
    p = pedidos.copy()
    datas = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
             "order_delivered_customer_date", "order_estimated_delivery_date"]
    for c in datas:
        p[c] = pd.to_datetime(p[c], errors="coerce")
    if not p.order_id.is_unique:
        raise ValueError("Pedidos originais duplicados.")
    pares = itens[["order_id", "seller_id"]].drop_duplicates()
    if pares.isna().any().any():
        raise ValueError("Associação com chave ausente.")
    aprovados = p.order_approved_at.notna() & p.order_approved_at.ge(p.order_purchase_timestamp)
    p = p.loc[aprovados].copy()
    entrega = p.order_delivered_customer_date
    promessa = p.order_estimated_delivery_date
    validos = (p.order_status.eq("delivered") & entrega.ge(p.order_approved_at)
               & promessa.dt.normalize().ge(p.order_approved_at.dt.normalize()))
    desfechos = p.loc[validos].copy()
    desfechos["atrasos"] = (entrega.loc[validos].dt.normalize() > promessa.loc[validos].dt.normalize()).astype(int)
    desfechos["observados"] = 1
    desfechos["dias_entrega"] = (desfechos.order_delivered_customer_date - desfechos.order_approved_at).dt.total_seconds() / 86400
    # Conservador: os históricos de atraso só são atualizados na entrega real.
    eventos = desfechos.merge(pares, on="order_id", validate="one_to_many")
    embarques = p.loc[p.order_delivered_carrier_date.ge(p.order_approved_at)].copy()
    embarques["postagens"] = 1
    embarques["dias_postagem"] = (embarques.order_delivered_carrier_date - embarques.order_approved_at).dt.total_seconds() / 86400
    embarques = embarques.merge(pares, on="order_id", validate="one_to_many")
    aprovacoes = p[["order_id", "order_approved_at"]].merge(pares, on="order_id", validate="one_to_many")
    aprovacoes["pedidos"] = 1
    return pares, desfechos, eventos, embarques, aprovacoes


def criar_historicos(pedidos, itens, consultas):
    """Reproduz atualização cronológica de históricos, sem refazer o modelo.

    Desfechos de validação já conhecidos podem atualizar o histórico de pedidos
    posteriores. Isso simula um serviço online, não uma previsão em lote em 01/01.
    """
    pares, global_real, eventos, embarques, aprovacoes = preparar_eventos(pedidos, itens)
    q = consultas[["order_id", "order_approved_at", "prazo_prometido_dias"]].merge(
        pares, on="order_id", how="left", validate="one_to_many")
    if q.seller_id.isna().any():
        raise ValueError("Pedido consultado sem vendedor na fonte original.")
    q = q.reset_index(drop=True)
    g = global_real[["order_delivered_customer_date", "observados", "atrasos"]].assign(seller_id="GLOBAL")
    qglobal = q.assign(seller_id="GLOBAL")
    glob, _ = acumulados_anteriores(g, qglobal, "order_delivered_customer_date", ["observados", "atrasos"])
    prior = glob.atrasos / glob.observados.replace(0, np.nan)
    cumul, t1 = acumulados_anteriores(eventos, q, "order_delivered_customer_date", ["observados", "atrasos", "dias_entrega"])
    recente, _ = acumulados_anteriores(eventos, q, "order_delivered_customer_date", ["observados", "atrasos"], 90)
    envio, t2 = acumulados_anteriores(embarques, q, "order_delivered_carrier_date", ["postagens", "dias_postagem"])
    volume, t3 = acumulados_anteriores(aprovacoes, q, "order_approved_at", ["pedidos"], 30)
    q["observados"] = cumul.observados
    # Força 20 fixada antes do experimento. Prior global usa só entregas passadas.
    q["taxa_atraso"] = (cumul.atrasos + 20 * prior) / (cumul.observados + 20)
    q["taxa_atraso_90d"] = (recente.atrasos + 20 * prior) / (recente.observados + 20)
    q["sem_desfecho"] = cumul.observados.eq(0).astype(float)
    q["postagem_dias"] = envio.dias_postagem / envio.postagens.replace(0, np.nan)
    q["entrega_dias"] = cumul.dias_entrega / cumul.observados.replace(0, np.nan)
    q["pedidos_30d"] = volume.pedidos
    ultimo = pd.concat([t1, t2, t3], axis=1).max(axis=1)
    if not (ultimo.isna() | ultimo.lt(q.order_approved_at)).all():
        raise AssertionError("Evento futuro ou simultâneo entrou no histórico.")
    q["ultimo_evento"] = ultimo
    h = q.groupby("order_id", sort=False).agg(
        hist_observados_media=("observados", "mean"), hist_observados_min=("observados", "min"),
        hist_taxa_atraso_media=("taxa_atraso", "mean"), hist_taxa_atraso_max=("taxa_atraso", "max"),
        hist_taxa_atraso_90d_media=("taxa_atraso_90d", "mean"), hist_taxa_atraso_90d_max=("taxa_atraso_90d", "max"),
        hist_sem_desfecho_fracao=("sem_desfecho", "mean"),
        hist_postagem_dias_media=("postagem_dias", "mean"), hist_postagem_dias_max=("postagem_dias", "max"),
        hist_entrega_dias_media=("entrega_dias", "mean"), hist_entrega_dias_max=("entrega_dias", "max"),
        hist_pedidos_30d_media=("pedidos_30d", "mean"), hist_pedidos_30d_max=("pedidos_30d", "max"),
        ultimo_evento_historico=("ultimo_evento", "max"), vendedores=("seller_id", "size"),
    ).reset_index()
    h = consultas[["order_id", "prazo_prometido_dias"]].merge(h, on="order_id", validate="one_to_one")
    h["hist_folga_promessa_dias"] = h.prazo_prometido_dias - h.hist_entrega_dias_max
    return h.drop(columns="prazo_prometido_dias"), q


def preparar_experimento(snapshot):
    caminho = RAIZ / "Dados/pedidos_consolidados_teste.csv"
    bruto = pd.read_csv(caminho, dtype={"customer_zip_code_prefix": "string"})
    log = []
    coorte = selecionar_coorte(bruto, log)
    original, _ = separar_por_tempo(coorte)
    original = original.set_index("order_id")
    sql = snapshot.set_index("order_id")
    assert set(original.index) == set(sql.index)
    assert original.atrasou.reindex(sql.index).eq(sql.atrasou).all()
    assert original.particao.reindex(sql.index).eq(sql.particao).all()
    coorte["rotulo_disponivel_em_original"] = coorte.rotulo_disponivel_em
    coorte["rotulo_disponivel_em"] = disponibilidade_revisada(coorte)
    revisada, _ = separar_por_tempo(coorte)
    revisada["recuperado"] = ~revisada.order_id.isin(sql.index)
    assert revisada.loc[revisada.recuperado, "atrasou"].eq(1).all()
    # A comparação atual usa desenvolvimento; não mede novamente o teste.
    revisada = revisada.loc[revisada.particao.ne("teste")].copy()
    revisada = corrigir_distancias(revisada, PASTA_ORIGINAIS, log)
    x, _ = limpar_atributos(revisada)
    revisada[COLUNAS_PREVISAO] = x
    revisada = revisada.set_index("order_id")
    comuns = revisada.index.intersection(sql.index)
    assert np.allclose(revisada.loc[comuns, NUMERICAS], sql.loc[comuns, NUMERICAS], equal_nan=True, atol=1e-7)
    for c in CATEGORICAS:
        assert revisada.loc[comuns, c].fillna("NA").eq(sql.loc[comuns, c].fillna("NA")).all()
    # Preservar exatamente os atributos do baseline PostgreSQL nos pedidos comuns.
    revisada.loc[comuns, COLUNAS_PREVISAO] = sql.loc[comuns, COLUNAS_PREVISAO]
    revisada = revisada.reset_index().sort_values(["order_approved_at", "order_id"]).reset_index(drop=True)
    auditoria = []
    for nome, tabela in [("original", snapshot), ("revisada", revisada)]:
        for parte in ["treino", "validacao"]:
            grupo = tabela.loc[tabela.particao.eq(parte)]
            auditoria.append({"coorte": nome, "particao": parte, "pedidos": len(grupo),
                              "atrasos": int(grupo.atrasou.sum()), "proporcao_atrasos": grupo.atrasou.mean()})
    pd.DataFrame(auditoria).to_csv(PASTA / "auditoria_rotulos.csv", index=False)
    recuperados = revisada.loc[revisada.recuperado, ["order_id", "particao", "order_approved_at", "atrasou",
        "order_estimated_delivery_date", "order_delivered_customer_date", "rotulo_disponivel_em_original", "rotulo_disponivel_em"]]
    recuperados.to_csv(PASTA / "pedidos_recuperados.csv", index=False)
    (PASTA / "auditoria.txt").write_text("\n".join(log), encoding="utf-8")
    return revisada


def escolher_limiar(y, scores):
    p, r, t = precision_recall_curve(y, scores)
    f = 2 * p[:-1] * r[:-1] / np.maximum(p[:-1] + r[:-1], 1e-12)
    return float(t[np.argmax(f)])


def metricas(y, s, limiar):
    previsto = s >= limiar
    tn, fp, fn, tp = confusion_matrix(y, previsto, labels=[0, 1]).ravel()
    k = int(len(y) * .10)
    top = np.argsort(-s, kind="stable")[:k]
    acertos = int(y[top].sum())
    return {"pedidos": len(y), "atrasos": int(y.sum()), "limiar": limiar,
            "accuracy": accuracy_score(y, previsto), "precision": precision_score(y, previsto, zero_division=0),
            "recall": recall_score(y, previsto, zero_division=0), "f1": f1_score(y, previsto, zero_division=0),
            "AP": average_precision_score(y, s), "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
            "fila10": k, "atrasos_top10": acertos, "precision_top10": acertos/k, "recall_top10": acertos/y.sum()}


def executar(usar_snapshot=False, saida=None):
    global PASTA
    fonte = PASTA / "snapshot_postgresql.joblib"
    if saida is not None:
        PASTA = Path(saida).resolve()
    PASTA.mkdir(parents=True, exist_ok=True)
    snapshot = joblib.load(fonte) if usar_snapshot else consultar_base()
    assert snapshot.origem_dado.eq("real_olist").all() and snapshot.order_id.is_unique
    protocolo = {
        "hash_snapshot": hash_base(snapshot), "hash_codigo": sha256(Path(__file__)),
        "hash_fontes": {p.name: sha256(p) for p in [RAIZ / "Dados/pedidos_consolidados_teste.csv",
                          *[PASTA_ORIGINAIS / f"olist_{s}_dataset.csv" for s in ["orders", "order_items", "geolocation", "sellers"]]]},
        "cortes": [str(CORTE_VALIDACAO), str(CORTE_TESTE)],
        "historicos": COLUNAS_HISTORICO, "prior_forca": 20, "semente": 42,
        "criterio": "AP e atrasos na fila fixa de 10% na mesma validacao original; F1 auxiliar com limiar de validacao",
        "comparacao": "2 coortes de treino x 2 conjuntos de atributos x 2 algoritmos; sem busca de hiperparametros",
        "teste": "nao avaliado; historicamente ja consultado em outros experimentos",
        "atualizacao": "eventos observados estritamente antes de cada aprovacao, inclusive dentro da validacao",
        "versoes": {p: version(p) for p in ["pandas", "numpy", "scikit-learn", "joblib"]},
    }
    if (PASTA / "protocolo.joblib").exists() and joblib.load(PASTA / "protocolo.joblib") != protocolo:
        raise ValueError("Protocolo alterado: usar uma nova pasta de resultados.")
    joblib.dump(snapshot, PASTA / "snapshot_postgresql.joblib")
    joblib.dump(protocolo, PASTA / "protocolo.joblib")
    base = preparar_experimento(snapshot)
    print("AUDITORIA", pd.read_csv(PASTA / "auditoria_rotulos.csv").to_string(index=False), flush=True)
    pedidos = pd.read_csv(PASTA_ORIGINAIS / "olist_orders_dataset.csv")
    itens = pd.read_csv(PASTA_ORIGINAIS / "olist_order_items_dataset.csv", usecols=["order_id", "seller_id"])
    historicos, pares = criar_historicos(pedidos, itens, base)
    base = base.merge(historicos, on="order_id", validate="one_to_one")
    assert np.allclose(base.quantidade_vendedores, base.vendedores)
    colunas_exportadas = ["order_id", "particao", "recuperado", "order_approved_at", "rotulo_disponivel_em", "atrasou"] + COLUNAS_PREVISAO + COLUNAS_HISTORICO
    base[colunas_exportadas].to_csv(PASTA / "pedidos_com_historicos.csv", index=False)
    historicos.to_csv(PASTA / "historicos_por_pedido.csv", index=False)
    joblib.dump(base, PASTA / "base_experimento.joblib", compress=3)
    pares.to_csv(PASTA / "auditoria_eventos_vendedores.csv", index=False)
    val = base.loc[base.particao.eq("validacao") & ~base.recuperado].copy()
    ampliada = base.loc[base.particao.eq("validacao")].copy()
    resultados, mensal, modelos = [], [], {}
    for coorte in ["original", "revisada"]:
        treino = base.loc[base.particao.eq("treino") & (~base.recuperado if coorte == "original" else True)]
        for atributos in ["atuais", "com_historicos"]:
            extras = COLUNAS_HISTORICO if atributos == "com_historicos" else []
            colunas = COLUNAS_PREVISAO + extras
            pre = criar_preprocessador()
            # Mesmo tratamento do projeto; acrescenta históricos ao bloco numérico.
            pre.transformers[0] = (pre.transformers[0][0], pre.transformers[0][1], NUMERICAS + extras)
            xt = pre.fit_transform(treino[colunas]).astype(np.float32)
            xv = pre.transform(val[colunas]).astype(np.float32)
            xa = pre.transform(ampliada[colunas]).astype(np.float32)
            y = treino.atrasou.to_numpy(int)
            for algoritmo in ["Logistica", "HGB"]:
                chave = f"{coorte}_{atributos}_{algoritmo}"
                print("TREINANDO", chave, xt.shape, flush=True)
                if algoritmo == "Logistica":
                    modelo = LogisticRegression(C=1, max_iter=1500, solver="liblinear", random_state=42)
                else:
                    modelo = HistGradientBoostingClassifier(max_iter=200, learning_rate=.07, max_leaf_nodes=15,
                        max_depth=5, min_samples_leaf=40, l2_regularization=1, early_stopping=False, random_state=42)
                with threadpool_limits(limits=4):
                    modelo.fit(xt, y)
                    s = modelo.predict_proba(xv)[:, 1]
                    sa = modelo.predict_proba(xa)[:, 1]
                limiar = escolher_limiar(val.atrasou.to_numpy(int), s)
                meta = {"coorte_treino": coorte, "atributos": atributos, "algoritmo": algoritmo, "n_treino": len(treino), "n_features": xt.shape[1]}
                for nome, tabela, scores in [("comum", val, s), ("ampliada", ampliada, sa)]:
                    resultados.append({**meta, "validacao": nome, **metricas(tabela.atrasou.to_numpy(int), scores, limiar)})
                for mes, indices in val.reset_index(drop=True).groupby(val.order_approved_at.dt.strftime("%Y-%m").to_numpy()).groups.items():
                    mensal.append({**meta, "mes": mes, **metricas(val.atrasou.to_numpy(int)[indices], s[indices], limiar)})
                pacote = {"preprocessador": copy.deepcopy(pre), "modelo": modelo, "colunas": colunas, "limiar": limiar,
                          "ids_validacao": val.order_id.to_numpy(), "scores_validacao": s, "scores_ampliada": sa}
                modelos[chave] = pacote
                joblib.dump(pacote, PASTA / f"modelo_{chave}.joblib", compress=3)
                pd.DataFrame(resultados).to_csv(PASTA / "metricas_validacao.csv", index=False)
                pd.DataFrame(mensal).to_csv(PASTA / "metricas_mensais.csv", index=False)
                print(chave, "AP", round(resultados[-2]["AP"], 4), "F1", round(resultados[-2]["f1"], 4),
                      "atrasos_top10", resultados[-2]["atrasos_top10"], flush=True)
    joblib.dump({"modelos": modelos, "protocolo": protocolo}, PASTA / "comparacao.joblib", compress=3)
    print("CONCLUIDO", PASTA, flush=True)
    return pd.DataFrame(resultados)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="store_true", help="Usar cópia local identificada do PostgreSQL.")
    parser.add_argument("--saida", type=Path, help="Nova pasta de resultados para o código reorganizado.")
    args = parser.parse_args()
    executar(args.snapshot, args.saida)
