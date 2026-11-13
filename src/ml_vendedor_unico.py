"""Seleção na validação real, avaliação final isolada e inferência com 18 campos."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                             f1_score, precision_recall_curve, precision_score, recall_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .contratos_olist import (CATEGORICAS, CTGAN_FEATURES, HISTORICOS, ML_FEATURES,
                             adicionar_razoes, mascara_valida, validar_ml)
from .dados_vendedor_unico import historicos_asof
from .preparar_dados import exigir
from .sintese_olist import hash_tabela
from .tratar_dados_ml import limpar_atributos


def criar_preprocessador():
    return ColumnTransformer([
        ("numericas", Pipeline([
            ("imputador", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("escala", StandardScaler()),
        ]), [c for c in ML_FEATURES if c not in CATEGORICAS]),
        ("categoricas", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAS),
    ], remainder="drop")


def escolher_limiar(alvo, scores):
    # Mesmo critério F1 usado em testar_doses_ctgan, somente na validação real.
    p, r, limites = precision_recall_curve(alvo, scores)
    f1 = np.divide(2 * p[:-1] * r[:-1], p[:-1] + r[:-1], out=np.zeros(len(limites)), where=p[:-1] + r[:-1] > 0)
    return float(limites[np.argmax(f1)]) if len(limites) else .5


def metricas(alvo, scores, limiar):
    pred = scores >= limiar
    tn, fp, fn, tp = confusion_matrix(alvo, pred, labels=[0, 1]).ravel()
    return {"n": len(alvo), "atrasos_reais": int(np.sum(alvo)), "prevalencia": float(np.mean(alvo)),
            "average_precision": float(average_precision_score(alvo, scores)),
            "roc_auc": float(roc_auc_score(alvo, scores)) if len(np.unique(alvo)) == 2 else None,
            "precision": float(precision_score(alvo, pred, zero_division=0)),
            "recall": float(recall_score(alvo, pred, zero_division=0)), "f1": float(f1_score(alvo, pred, zero_division=0)),
            "brier": float(brier_score_loss(alvo, scores)), "limiar": limiar,
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}


def treinar_comparacao(base, config):
    validar_ml(base)
    real = base.loc[base.origem_dado.eq("real") & base.particao.eq("treino")]
    sint = base.loc[base.origem_dado.eq("sintetico_ctgan")]
    val = base.loc[base.particao.eq("validacao")]
    exigir(len(real) > 0 and len(val) > 0 and len(sint) > 0, "Comparação exige treino real, sintéticos e validação real.")
    exigir(real.atrasou.nunique() == 2 and val.atrasou.nunique() == 2, "Treino/validação precisam conter as duas classes.")
    # Compartilhar um transformador ajustado exclusivamente no treino real
    # permite comparar o efeito dos exemplos artificiais com a mesma escala.
    pre = criar_preprocessador().fit(real[ML_FEATURES])
    xr, xs, xv = [pre.transform(df[ML_FEATURES]) for df in [real, sint, val]]
    rng = np.random.default_rng(config["seed"])
    ordem = rng.permutation(len(sint))
    candidatos = [("baseline_real", 0, 0., 0.)]
    vistos = set()
    for proporcao in config["synthetic_to_real_ratios"]:
        exigir(proporcao > 0, "Proporção sintética deve ser positiva.")
        n = min(round(len(real) * proporcao), len(sint))
        exigir(n > 0, "Dose sintética arredondou para zero.")
        for peso in config["synthetic_weights"]:
            exigir(peso > 0, "Peso sintético deve ser positivo.")
            if (n, peso) not in vistos:
                candidatos.append((f"real_mais_ctgan_n{n}_peso{peso:g}", n, peso, proporcao))
                vistos.add((n, peso))
    modelos, resultados = {}, []
    for nome, n, peso, pedido in candidatos:
        ids = ordem[:n]
        x = np.concatenate([xr, xs[ids]]) if n else xr
        y = np.r_[real.atrasou.to_numpy(), sint.atrasou.to_numpy()[ids]] if n else real.atrasou.to_numpy()
        pesos = np.r_[np.ones(len(real)), np.full(n, peso)]
        clf = LogisticRegression(C=config.get("C", 1.), solver="liblinear", max_iter=1500, random_state=config["seed"])
        clf.fit(x, y, sample_weight=pesos)
        scores = clf.predict_proba(xv)[:, 1]
        limiar = escolher_limiar(val.atrasou, scores)
        modelos[nome] = {"pipeline": Pipeline([("preprocessador", pre), ("modelo", clf)]),
                         "limiar": limiar, "features": list(ML_FEATURES), "seed": config["seed"],
                         "n_real": len(real), "n_sintetico": n, "peso_sintetico": peso}
        resultados.append({"experimento": nome, "n_sintetico": n, "proporcao_solicitada": pedido,
                            "proporcao_efetiva": n / len(real), "peso": peso,
                            **metricas(val.atrasou, scores, limiar)})
    tabela = pd.DataFrame(resultados)
    aumentados = tabela.loc[tabela.n_sintetico.gt(0)]
    escolhido = aumentados.sort_values(["average_precision", "n_sintetico", "peso"], ascending=[False, True, True]).iloc[0].experimento
    return {"modelos": modelos, "selecionado_aumentado": escolhido, "validacao": tabela,
            "config": config, "hash_dataset_ml": hash_tabela(base),
            "hash_validacao": hash_tabela(val), "features": list(ML_FEATURES)}


def avaliar_comparacao(base, pacote):
    validar_ml(base)
    exigir(hash_tabela(base) == pacote["hash_dataset_ml"], "Dataset mudou após seleção; não avaliar outro teste.")
    teste = base.loc[base.particao.eq("teste")]
    exigir(len(teste) > 0 and teste.origem_dado.eq("real").all(), "Teste deve ser real e não vazio.")
    resultados = []
    for nome in ["baseline_real", pacote["selecionado_aumentado"]]:
        modelo = pacote["modelos"][nome]
        scores = modelo["pipeline"].predict_proba(teste[ML_FEATURES])[:, 1]
        resultados.append({"experimento": nome, **metricas(teste.atrasou, scores, modelo["limiar"])})
    return pd.DataFrame(resultados)


def prever_pedido_enriquecido(pedidos, pacote_modelo):
    """Entrada pré-entrega: atributos + aprovação; históricos já calculados as-of.

    Não exige rótulo/status final/data de entrega. Para construir o histórico de
    um pedido novo usar `preparar_features_inferencia` com os eventos disponíveis.
    """
    exigir(pacote_modelo["features"] == ML_FEATURES, "Modelo com contrato incompatível.")
    base = adicionar_razoes(pedidos)
    base["mes_aprovacao"] = pd.to_datetime(base.order_approved_at, errors="raise").dt.month
    exigir(base.mes_aprovacao.notna().all(), "Data de aprovação necessária na inferência.")
    exigir(mascara_valida(base).all(), "Atributos inválidos na inferência; aplicar a limpeza e histórico as-of.")
    scores = pacote_modelo["pipeline"].predict_proba(base[ML_FEATURES])[:, 1]
    return pd.DataFrame({"order_id": base.order_id, "score_atraso": scores,
                         "previsao_atraso": (scores >= pacote_modelo["limiar"]).astype(int)})


def preparar_features_inferencia(pedidos, pedidos_historicos, mapa_historico, reviews, imputacao):
    """Pedidos já agregados de um seller: mesmos campos geográficos/produtos de A.

    Reaplica estatísticas salvas da limpeza e a função as-of compartilhada.
    `pedidos_historicos` contém apenas order_id/aprovação, sem exigir entrega.
    """
    base = pedidos.drop(columns=HISTORICOS, errors="ignore").copy()
    atributos = [c for c in CTGAN_FEATURES if c not in HISTORICOS]
    limpos, _ = limpar_atributos(base, colunas=atributos, categoricas=CATEGORICAS)
    base[atributos] = limpos
    for c, valor in imputacao.items():
        base[c] = base[c].fillna(valor)
    base, _ = historicos_asof(base, pedidos_historicos, mapa_historico, reviews)
    base = adicionar_razoes(base)
    base["mes_aprovacao"] = pd.to_datetime(base.order_approved_at).dt.month
    return base
