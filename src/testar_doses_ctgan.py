"""Compara doses de CTGAN e repetição de positivos; não altera a aplicação/banco.

Executar da raiz com .venv-ctgan/Scripts/python.exe -m src.testar_doses_ctgan.
O snapshot vem do PostgreSQL; --snapshot permite retomar a cópia local identificada.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from scipy.stats import ks_2samp
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
                             confusion_matrix, f1_score, precision_recall_curve,
                             precision_score, recall_score)
from threadpoolctl import threadpool_limits

from .experimento_ctgan import (RAIZ, ajustar_gerador, consultar_base, filtrar_candidatos,
                               gerar_atrasos, hash_base, validar_injecao)
from .preparar_dados import COLUNAS_PREVISAO
from .tratar_dados_ml import CATEGORICAS, NUMERICAS, criar_preprocessador

PASTA = RAIZ / "Modelos/experimento_ctgan/doses_20261111"
SEMENTES = [7, 42, 123]
DOSES = [500, 1000, 2000]
BATCH = 500
EPOCAS_POSITIVOS = 300
FRACAO_FILA = 0.10


def ajustar_condicional(treino, semente, epocas):
    """Ajusta P(X,y) com os reais de treino; mesmo formato do gerador positivo."""
    from ctgan import CTGAN
    if not treino.particao.eq("treino").all() or not treino.origem_dado.eq("real_olist").all():
        raise ValueError("CTGAN condicional exige somente treino real.")
    reais = treino[COLUNAS_PREVISAO].copy().reset_index(drop=True)
    tabela = reais.copy()
    faltantes = {}
    for c in NUMERICAS:
        if reais[c].isna().any():
            flag = "ausente__" + c
            tabela[flag] = reais[c].isna().astype(int)
            faltantes[c] = flag
    estrutura = [c for c in NUMERICAS if c.startswith(("quantidade_", "itens_sem_", "vendedores_sem_"))]
    estrutura += ["uf_origem"] + list(faltantes.values())
    chaves = tabela[estrutura].fillna("AUSENTE").astype(str).agg("|".join, axis=1)
    codigos, _ = pd.factorize(chaves, sort=True)
    tabela["estrutura_pedido"] = [f"E{x:04d}" for x in codigos]
    mapa = tabela[["estrutura_pedido"] + estrutura].drop_duplicates("estrutura_pedido").set_index("estrutura_pedido")
    tabela = tabela.drop(columns=estrutura)
    discretas = [c for c in CATEGORICAS if c in tabela] + ["estrutura_pedido"]
    discretas += ["dia_semana_aprovacao", "mes_aprovacao", "hora_aprovacao", "parcelas_maximas", "prazo_prometido_dias"]
    continuas = [c for c in tabela if c not in discretas]
    for c in discretas:
        tabela[c] = tabela[c].fillna("AUSENTE").astype(str)
    for c in continuas:
        tabela[c] = np.log1p(tabela[c].fillna(reais[c].median() if reais[c].notna().any() else 0))
    constantes = {c: tabela[c].iloc[0] for c in tabela if tabela[c].nunique() == 1}
    tabela = tabela.drop(columns=list(constantes))
    tabela["atrasou"] = treino.atrasou.to_numpy().astype(str)
    torch.manual_seed(semente)
    gerador = CTGAN(epochs=epocas, batch_size=BATCH, pac=10,
                   generator_dim=(128, 128), discriminator_dim=(128, 128),
                   verbose=True, enable_gpu=False)
    gerador.set_random_state(semente)
    gerador.fit(tabela, discrete_columns=[c for c in discretas if c in tabela] + ["atrasou"])
    return {"gerador": gerador, "mapa": mapa, "faltantes": faltantes,
            "continuas": continuas, "constantes": constantes, "epocas": epocas,
            "semente": semente, "reais": reais}


def amostrar_condicional(pacote, treino, quantidade, identificador):
    """Condicionar CTGAN favorece y=1, mas é preciso conferir e rejeitar y!=1."""
    if not 1 <= quantidade <= 10000:
        raise ValueError("Quantidade deve estar entre 1 e 10000.")
    positivos = treino.loc[treino.atrasou.eq(1), COLUNAS_PREVISAO]
    hashes = set(pd.util.hash_pandas_object(treino[COLUNAS_PREVISAO], index=False))
    aceitos = pd.DataFrame(columns=COLUNAS_PREVISAO)
    tentados = positivos_brutos = plausiveis = 0
    for _ in range(100):
        bruto = pacote["gerador"].sample(max(2000, 2 * (quantidade - len(aceitos))),
                                          condition_column="atrasou", condition_value="1")
        tentados += len(bruto)
        # Não transformar um negativo gerado em positivo por atribuição de rótulo.
        bruto = bruto.loc[bruto.atrasou.astype(str).eq("1")].copy()
        positivos_brutos += len(bruto)
        for c, valor in pacote["constantes"].items():
            bruto[c] = valor
        bruto = bruto.join(pacote["mapa"], on="estrutura_pedido", validate="many_to_one")
        for c in pacote["continuas"]:
            bruto[c] = np.expm1(bruto[c].clip(upper=30))
        for c in NUMERICAS:
            bruto[c] = pd.to_numeric(bruto[c], errors="coerce")
        for c in CATEGORICAS:
            bruto[c] = bruto[c].replace("AUSENTE", np.nan)
        for c, flag in pacote["faltantes"].items():
            bruto.loc[bruto[flag].eq(1), c] = np.nan
        novos = filtrar_candidatos(bruto, positivos)
        plausiveis += len(novos)
        novos = novos.loc[~pd.util.hash_pandas_object(novos, index=False).isin(hashes)]
        aceitos = pd.concat([aceitos, novos], ignore_index=True).drop_duplicates()
        if len(aceitos) >= quantidade:
            break
    if len(aceitos) < quantidade:
        raise RuntimeError(f"Amostragem insuficiente: {len(aceitos)} de {quantidade}.")
    saida = aceitos.iloc[:quantidade].copy().reset_index(drop=True)
    saida.insert(0, "order_id", [f"ctgan_{identificador}_{i:05d}" for i in range(quantidade)])
    saida["particao"] = "treino"
    saida["atrasou"] = 1
    saida["origem_dado"] = "sintetico_ctgan"
    saida["rotulo_observado"] = False
    saida["experimento_id"] = identificador
    return saida, {"candidatos_gerados": tentados, "positivos_brutos": positivos_brutos,
                   "plausiveis_antes_duplicatas": plausiveis, "sinteticos_aceitos": len(saida)}


def escolher_limiar(alvo, scores):
    p, r, limites = precision_recall_curve(alvo, scores)
    f1 = 2 * p[:-1] * r[:-1] / np.maximum(p[:-1] + r[:-1], 1e-12)
    return float(limites[np.argmax(f1)])


def metricas(alvo, scores, limiar):
    previstos = scores >= limiar
    tn, fp, fn, tp = confusion_matrix(alvo, previstos, labels=[0, 1]).ravel()
    k = int(len(alvo) * FRACAO_FILA)
    acertos = int(alvo[np.argsort(-scores, kind="stable")[:k]].sum())
    return {"n": len(alvo), "atrasos_reais": int(alvo.sum()), "limiar": limiar,
            "accuracy": accuracy_score(alvo, previstos),
            "balanced_accuracy": balanced_accuracy_score(alvo, previstos),
            "precision": precision_score(alvo, previstos, zero_division=0),
            "recall": recall_score(alvo, previstos, zero_division=0),
            "f1": f1_score(alvo, previstos, zero_division=0),
            "AP": average_precision_score(alvo, scores),
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
            "pedidos_top10": k, "atrasos_top10": acertos,
            "precision_top10": acertos / k, "recall_top10": acertos / int(alvo.sum())}


def qualidade(treino, sinteticos, metodo, semente):
    reais = treino.loc[treino.atrasou.eq(1)]
    linhas = []
    for c in NUMERICAS:
        a, b = reais[c].dropna(), sinteticos[c].dropna()
        linhas.append({"metodo": metodo, "semente": semente, "atributo": c, "tipo": "numerica",
                       "mediana_real": a.median(), "mediana_sintetica": b.median(),
                       "KS": ks_2samp(a, b).statistic if len(a) and len(b) else np.nan,
                       "ausentes_real": reais[c].isna().mean(), "ausentes_sinteticos": sinteticos[c].isna().mean()})
    for c in CATEGORICAS:
        a = reais[c].fillna("AUSENTE").value_counts(normalize=True)
        b = sinteticos[c].fillna("AUSENTE").value_counts(normalize=True)
        a, b = a.align(b, fill_value=0)
        linhas.append({"metodo": metodo, "semente": semente, "atributo": c, "tipo": "categorica",
                       "distancia_variacao_total": float((a-b).abs().sum()/2)})
    pares = [("peso_total_g", "valor_frete"), ("distancia_max_vendedores_km", "prazo_prometido_dias"),
             ("distancia_max_vendedores_km", "valor_frete")]
    for a, b in pares:
        linhas.append({"metodo": metodo, "semente": semente, "atributo": f"{a} x {b}", "tipo": "relacao",
                       "spearman_real": reais[[a, b]].corr(method="spearman").iloc[0, 1],
                       "spearman_sintetico": sinteticos[[a, b]].corr(method="spearman").iloc[0, 1]})
    return linhas


def executar(usar_snapshot=False):
    PASTA.mkdir(parents=True, exist_ok=True)
    base = joblib.load(PASTA / "snapshot_postgresql.joblib") if usar_snapshot else consultar_base()
    if not base.origem_dado.eq("real_olist").all() or not base.order_id.is_unique:
        raise ValueError("Snapshot precisa conter apenas pedidos reais únicos.")
    joblib.dump(base, PASTA / "snapshot_postgresql.joblib")
    partes = {p: base.loc[base.particao.eq(p)].reset_index(drop=True) for p in ["treino", "validacao", "teste"]}
    treino = partes["treino"]
    n_pos = int(treino.atrasou.sum())
    atualizacoes = max(n_pos // BATCH, 1) * EPOCAS_POSITIVOS
    epocas_condicional = math.ceil(atualizacoes / max(len(treino) // BATCH, 1))
    config = {"sementes": SEMENTES, "doses": DOSES, "hash_base": hash_base(base),
              "hash_treino": hash_base(treino), "epocas_positivos": EPOCAS_POSITIVOS,
              "epocas_condicional": epocas_condicional, "batch": BATCH,
              "atualizacoes_positivos": atualizacoes,
              "atualizacoes_condicional": epocas_condicional * max(len(treino)//BATCH, 1),
              "criterio": "F1 medio na validacao; desempate AP; nenhuma selecao por teste",
              "classificador": "LogisticRegression C=1 liblinear max_iter=1500 random_state=42, sem pesos",
              "hash_codigo": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "versoes": {p: version(p) for p in ["pandas", "numpy", "torch", "ctgan", "rdt", "scikit-learn"]}}
    protocolo = PASTA / "protocolo.joblib"
    if protocolo.exists() and joblib.load(protocolo) != config:
        raise ValueError("Protocolo diferente: use outra pasta para não sobrescrever experimentos.")
    joblib.dump(config, protocolo)
    print("PROTOCOLO", json.dumps(config, ensure_ascii=False), flush=True)
    pre = criar_preprocessador()
    X = {"treino": pre.fit_transform(treino[COLUNAS_PREVISAO]).astype(np.float32)}
    X["validacao"] = pre.transform(partes["validacao"][COLUNAS_PREVISAO]).astype(np.float32)
    y = {p: partes[p].atrasou.to_numpy(dtype=int) for p in partes}
    resultados, modelos, diagnostico, geracoes = [], {}, [], []
    torch.set_num_threads(4)

    def avaliar(nome, dose, semente, extras):
        chave = f"{nome}_{dose}_{semente}"
        arq = PASTA / f"classificador_{chave}.joblib"
        if arq.exists():
            pacote = joblib.load(arq)
        else:
            xt, yt = X["treino"], y["treino"]
            if extras is not None:
                xt = np.concatenate([xt, pre.transform(extras[COLUNAS_PREVISAO]).astype(np.float32)])
                yt = np.concatenate([yt, np.ones(len(extras), dtype=int)])
            modelo = LogisticRegression(C=1, max_iter=1500, solver="liblinear", random_state=42).fit(xt, yt)
            scores = modelo.predict_proba(X["validacao"])[:, 1]
            limiar = escolher_limiar(y["validacao"], scores)
            pacote = {"modelo": modelo, "limiar": limiar, "scores_validacao": scores,
                      "metodo": nome, "dose": dose, "semente": semente,
                      "metricas_validacao": metricas(y["validacao"], scores, limiar)}
            joblib.dump(pacote, arq)
        modelos[chave] = pacote
        resultados.append({"metodo": nome, "dose": dose, "semente": semente, **pacote["metricas_validacao"]})
        pd.DataFrame(resultados).to_csv(PASTA / "metricas_validacao.csv", index=False)
        print(chave, "F1=", round(resultados[-1]["f1"], 4), "AP=", round(resultados[-1]["AP"], 4),
              "atrasos_top10=", resultados[-1]["atrasos_top10"], flush=True)

    with threadpool_limits(limits=4), joblib.parallel_backend("threading", n_jobs=4):
        avaliar("Real", 0, 42, None)
        positivos = treino.loc[treino.atrasou.eq(1)].reset_index(drop=True)
        for semente in SEMENTES:
            rng = np.random.default_rng(semente)
            repetidos = positivos.iloc[rng.integers(0, len(positivos), size=max(DOSES))].reset_index(drop=True)
            for dose in DOSES:
                avaliar("Repeticao", dose, semente, repetidos.iloc[:dose])
        for metodo in ["CTGAN_positivos", "CTGAN_condicional"]:
            for semente in SEMENTES:
                cache = PASTA / f"gerador_{metodo}_{semente}.joblib"
                inicio = time.perf_counter()
                if cache.exists():
                    salvo = joblib.load(cache)
                else:
                    print("TREINANDO", metodo, "semente", semente, flush=True)
                    if metodo == "CTGAN_positivos":
                        anterior = RAIZ / "Modelos/experimento_ctgan/ecc4ac30a3df7383/geracao.joblib"
                        if semente == 42 and anterior.exists():
                            antigo = joblib.load(anterior)
                            assert antigo["configuracao"]["hash_treino"] == hash_base(treino)
                            assert antigo["pacote"]["epocas"] == EPOCAS_POSITIVOS
                            pacote = antigo["pacote"]
                            sinteticos = antigo["sinteticos"].sample(frac=1, random_state=semente).iloc[:max(DOSES)].reset_index(drop=True)
                            q = {"cache_anterior": True, "sinteticos_aceitos": len(sinteticos)}
                        else:
                            pacote = ajustar_gerador(treino, EPOCAS_POSITIVOS, semente)
                            sinteticos, q = gerar_atrasos(pacote, max(DOSES), f"doses_positivos_{semente}")
                    else:
                        pacote = ajustar_condicional(treino, semente, epocas_condicional)
                        sinteticos, q = amostrar_condicional(pacote, treino, max(DOSES), f"doses_condicional_{semente}")
                    validar_injecao(base, sinteticos)
                    h_real = set(pd.util.hash_pandas_object(treino[COLUNAS_PREVISAO], index=False))
                    assert not pd.util.hash_pandas_object(sinteticos[COLUNAS_PREVISAO], index=False).isin(h_real).any()
                    salvo = {"pacote": pacote, "sinteticos": sinteticos, "qualidade": q,
                             "segundos": time.perf_counter() - inicio}
                    joblib.dump(salvo, cache)
                sinteticos = salvo["sinteticos"]
                print("GERACAO", metodo, semente, salvo["qualidade"], "segundos", round(salvo["segundos"], 1), flush=True)
                sinteticos.to_csv(PASTA / f"sinteticos_{metodo}_{semente}.csv", index=False)
                diagnostico.extend(qualidade(treino, sinteticos, metodo, semente))
                geracoes.append({"metodo": metodo, "semente": semente, "segundos": salvo["segundos"], **salvo["qualidade"]})
                pd.DataFrame(diagnostico).to_csv(PASTA / "qualidade_sinteticos.csv", index=False)
                pd.DataFrame(geracoes).to_csv(PASTA / "geracoes.csv", index=False)
                for dose in DOSES:
                    avaliar(metodo, dose, semente, sinteticos.iloc[:dose])
    val = pd.DataFrame(resultados)
    resumo = resumir(val)
    resumo.to_csv(PASTA / "resumo_validacao.csv", index=False)
    escolhido = resumo.sort_values(["f1_mean", "AP_mean"], ascending=False).iloc[0]
    selecao = {"metodo": escolhido.metodo, "dose": int(escolhido.dose),
               "criterio": config["criterio"], "f1_medio": float(escolhido.f1_mean)}
    joblib.dump(selecao, PASTA / "selecao_antes_teste.joblib")
    print("SELECAO ANTES DO TESTE", selecao, flush=True)
    # Só após concluir e congelar toda a seleção na validação.
    xteste = pre.transform(partes["teste"][COLUNAS_PREVISAO]).astype(np.float32)
    teste = []
    for chave, pacote in modelos.items():
        scores = pacote["modelo"].predict_proba(xteste)[:, 1]
        pacote["scores_teste"] = scores
        teste.append({"metodo": pacote["metodo"], "dose": pacote["dose"], "semente": pacote["semente"],
                      **metricas(y["teste"], scores, pacote["limiar"])})
    teste = pd.DataFrame(teste)
    teste.to_csv(PASTA / "metricas_teste_descritivo.csv", index=False)
    resumir(teste).to_csv(PASTA / "resumo_teste_descritivo.csv", index=False)
    joblib.dump({"preprocessador": pre, "modelos": modelos, "configuracao": config,
                 "selecao": selecao}, PASTA / "comparacao.joblib")
    print("FINALIZADO", PASTA, flush=True)
    return resumo


def resumir(tabela):
    colunas = ["accuracy", "balanced_accuracy", "precision", "recall", "f1", "AP",
               "atrasos_top10", "precision_top10", "recall_top10", "fp", "fn"]
    resumo = tabela.groupby(["metodo", "dose"])[colunas].agg(["mean", "std", "min", "max"])
    resumo.columns = [f"{a}_{b}" for a, b in resumo.columns]
    resumo["execucoes"] = tabela.groupby(["metodo", "dose"]).size()
    return resumo.reset_index()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="store_true", help="Retomar snapshot PostgreSQL já salvo.")
    args = parser.parse_args()
    executar(args.snapshot)
