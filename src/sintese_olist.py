"""CTGAN de 15 atributos, rejeição de candidatos e rastreabilidade separada."""
from __future__ import annotations

import hashlib
import os
import re
from importlib.metadata import version

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.compose import ColumnTransformer
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .contratos_olist import (CATEGORICAS, CONTAGENS, CTGAN_FEATURES, HISTORICOS,
                             NUMERICAS_CTGAN, VERSAO, adicionar_razoes, mascara_valida, validar_limpo)
from .preparar_dados import exigir


def hash_tabela(base):
    return hashlib.sha256(base.to_csv(index=False, float_format="%.12g").encode()).hexdigest()


def treino_real(base):
    validar_limpo(base)
    resultado = base.loc[base.particao.eq("treino")].copy().reset_index(drop=True)
    exigir(not resultado.empty, "Treino real vazio.")
    return resultado


def codificar_treino(treino):
    validar_limpo(treino)
    exigir(treino.particao.eq("treino").all(), "CTGAN aceita somente treino real.")
    exigir(len(treino) >= 10, "CTGAN exige ao menos dez pedidos de treino real.")
    tabela = treino[CTGAN_FEATURES].copy()
    # Somente representação técnica interna: count=0 restaura nulos na saída.
    tabela[HISTORICOS[0]] = tabela[HISTORICOS[0]].fillna(0.)
    tabela[HISTORICOS[2]] = tabela[HISTORICOS[2]].fillna(-1.)
    logs = [c for c in NUMERICAS_CTGAN if c not in HISTORICOS[:1] + HISTORICOS[2:]
            and c not in CONTAGENS[:3]]
    for c in logs:
        tabela[c] = np.log1p(tabela[c])
    discretas = CATEGORICAS + CONTAGENS[:3]
    for c in discretas:
        tabela[c] = tabela[c].astype(str)
    exigir(list(tabela) == CTGAN_FEATURES, "Schema de fit CTGAN diferente de B.")
    return tabela, logs, discretas


def ajustar_ctgan(treino, config):
    import torch
    from ctgan import CTGAN

    tabela, logs, discretas = codificar_treino(treino)
    seed = config["seed"]
    exigir(config["epochs"] > 0, "Épocas devem ser positivas.")
    exigir(config["batch_size"] % 10 == 0 and config["batch_size"] >= 10, "Lote CTGAN deve ser múltiplo de 10.")
    torch.set_num_threads(min(config.get("threads", 4), os.cpu_count() or 1))
    torch.manual_seed(seed)
    np.random.seed(seed)
    modelo = CTGAN(epochs=config["epochs"], batch_size=config["batch_size"], pac=10,
                   generator_dim=tuple(config.get("hidden_dims", [128, 128])),
                   discriminator_dim=tuple(config.get("hidden_dims", [128, 128])),
                   enable_gpu=False, verbose=config.get("verbose", False))
    modelo.set_random_state(seed)
    modelo.fit(tabela, discrete_columns=discretas)
    return {"modelo": modelo, "logs": logs, "discretas": discretas, "treino": treino,
            "config": dict(config), "versao_contrato": VERSAO,
            "hash_treino": hash_tabela(treino), "colunas_fit": list(tabela),
            "versoes": {p: version(p) for p in ["ctgan", "rdt", "torch", "pandas", "numpy", "scikit-learn"]}}, tabela


def decodificar_candidatos(bruto, pacote):
    exigir(list(bruto) == CTGAN_FEATURES, "Gerador retornou schema diferente de B.")
    base = bruto.copy()
    for c in NUMERICAS_CTGAN:
        base[c] = pd.to_numeric(base[c], errors="coerce")
    with np.errstate(over="ignore", invalid="ignore"):
        for c in pacote["logs"]:
            base[c] = np.expm1(base[c])
    # Contagem contínua de reviews: arredondamento, sem clipping de negativos.
    base[HISTORICOS[1]] = base[HISTORICOS[1]].round()
    base.loc[base[HISTORICOS[1]].eq(0), [HISTORICOS[0], HISTORICOS[2]]] = np.nan
    return base


def filtrar_candidatos(base, treino):
    valido = mascara_valida(base)
    for c in NUMERICAS_CTGAN:
        observado = treino[c].dropna()
        if len(observado):
            valido &= base[c].isna() | base[c].between(observado.min(), observado.max())
        else:
            valido &= base[c].isna()
    for c in CATEGORICAS:
        valido &= base[c].isin(treino[c].unique())
    return base.loc[valido].copy()


def estratos(base):
    return base.quantidade_itens.clip(upper=3).astype(int)


def quotas_estratos(treino, quantidade):
    pesos = estratos(treino).value_counts(normalize=True).reindex([1, 2, 3], fill_value=0).sort_index()
    alvos = pesos * quantidade
    quotas = np.floor(alvos).astype(int)
    for k in (alvos - quotas).sort_values(ascending=False, kind="stable").index[:quantidade - quotas.sum()]:
        quotas.loc[k] += 1
    return quotas.to_dict()


def fingerprints(base):
    tabela = base[CTGAN_FEATURES].copy()
    # Neutraliza ruído de ida/volta log1p/expm1 ao procurar cópias.
    tabela[NUMERICAS_CTGAN] = tabela[NUMERICAS_CTGAN].astype(float).round(8)
    return pd.util.hash_pandas_object(tabela, index=False)


def atribuir_metadados(base, treino, run_id, seed):
    exigir(bool(re.fullmatch(r"[A-Za-z0-9_-]+", run_id)), "run_id deve conter apenas letras, números, _ ou -.")
    base = adicionar_razoes(base.reset_index(drop=True))
    rng = np.random.default_rng(seed)
    base["order_id"] = [f"ctgan_order_{run_id}_{i:07d}" for i in range(len(base))]
    base["seller_id"] = [f"ctgan_seller_{run_id}_individual_{i:07d}" for i in range(len(base))]
    # Reutilizar perfil somente se todos os atributos observáveis coincidirem.
    # Caso contínuo usual: não existe correspondência exata, portanto ID exclusivo.
    colunas_perfil = ["seller_state", *HISTORICOS]
    perfis = treino[colunas_perfil].drop_duplicates().fillna("SEM_HISTORICO")
    catalogo = {tuple(row): i for i, row in enumerate(perfis.itertuples(index=False, name=None))}
    encontrados = 0
    for i, row in enumerate(base[colunas_perfil].fillna("SEM_HISTORICO").itertuples(index=False, name=None)):
        perfil = catalogo.get(tuple(row))
        if perfil is not None:
            base.loc[i, "seller_id"] = f"ctgan_seller_{run_id}_perfil_{perfil:07d}"
            encontrados += 1
    base["order_approved_at"] = rng.choice(treino.order_approved_at.to_numpy(), size=len(base))
    base["particao"], base["origem_dado"] = "treino", "sintetico_ctgan"
    exigir(not set(base.order_id) & set(treino.order_id), "ID sintético colide com real.")
    exigir(not set(base.seller_id) & set(treino.seller_id), "Seller sintético colide com real.")
    return base, {"perfis_compativeis": encontrados, "seller_exclusivo_por_pedido": len(base) - encontrados,
                  "politica": "Perfil de treino somente em correspondência exata UF/históricos; fallback exclusivo não representa recorrência ou série real de reviews; datas amostradas do treino."}


def gerar_pedidos(pacote, quantidade, run_id, config):
    exigir(isinstance(quantidade, int) and quantidade > 0, "Quantidade sintética deve ser inteiro positivo.")
    treino = pacote["treino"]
    validar_limpo(treino)
    exigir(treino.particao.eq("treino").all(), "Fonte da síntese deve ser treino real.")
    exigir(pacote["hash_treino"] == hash_tabela(treino), "Treino do pacote CTGAN alterado.")
    pacote["modelo"].set_random_state(config["seed"])
    quotas = quotas_estratos(treino, quantidade)
    aceitos = treino.iloc[:0][CTGAN_FEATURES].copy()
    conhecidos = set(fingerprints(treino))
    tentados = invalidos = copias = excedentes = 0
    for tentativa in range(config["max_resample_attempts"]):
        n = max(config.get("min_batch", 1000), (quantidade - len(aceitos)) * config.get("oversample_factor", 3))
        bruto = pacote["modelo"].sample(n)
        tentados += len(bruto)
        candidatos = filtrar_candidatos(decodificar_candidatos(bruto, pacote), treino)
        invalidos += len(bruto) - len(candidatos)
        antes = len(candidatos)
        candidatos = candidatos.loc[~fingerprints(candidatos).isin(conhecidos)].drop_duplicates()
        copias += antes - len(candidatos)
        selecionados = []
        for k, quota in quotas.items():
            faltam = quota - int(estratos(aceitos).eq(k).sum())
            grupo = candidatos.loc[estratos(candidatos).eq(k)]
            selecionados.append(grupo.head(max(0, faltam)))
            excedentes += max(0, len(grupo) - max(0, faltam))
        novos = pd.concat(selecionados, ignore_index=True)
        conhecidos.update(fingerprints(novos))
        aceitos = pd.concat([aceitos, novos], ignore_index=True)
        if len(aceitos) == quantidade:
            break
    relatorio = {"candidatos": tentados, "invalidos": invalidos, "copias_ou_duplicatas": copias,
                 "excedentes_estratos": excedentes, "aceitos": len(aceitos), "quotas": quotas,
                 "taxa_rejeicao_dominio": invalidos / tentados, "taxa_retencao": len(aceitos) / tentados,
                 "tentativas": tentativa + 1, "seed": config["seed"]}
    if len(aceitos) < quantidade:
        erro = RuntimeError(f"Amostragem insuficiente: {len(aceitos)}/{quantidade}; {relatorio}")
        erro.relatorio = relatorio
        raise erro
    for c in CONTAGENS:
        aceitos[c] = aceitos[c].astype(int)
    base, perfis = atribuir_metadados(aceitos, treino, run_id, config["seed"])
    relatorio["sellers"] = perfis
    return base, relatorio


def qualidade_sintetica(treino, sinteticos, seed=42):
    numericos = {}
    for c in NUMERICAS_CTGAN:
        r, s = treino[c].dropna(), sinteticos[c].dropna()
        numericos[c] = {"ks": float(ks_2samp(r, s).statistic) if len(r) and len(s) else None,
                        "quantis_real": r.quantile([0, .1, .5, .9, 1]).to_dict(),
                        "quantis_sintetico": s.quantile([0, .1, .5, .9, 1]).to_dict()}
    categoricos = {}
    for c in CATEGORICAS:
        r, s = treino[c].value_counts(normalize=True), sinteticos[c].value_counts(normalize=True)
        idx = r.index.union(s.index)
        categoricos[c] = {"variacao_total": float((r.reindex(idx, fill_value=0) - s.reindex(idx, fill_value=0)).abs().sum() / 2),
                          "real": r.to_dict(), "sintetico": s.to_dict()}
    # Diagnóstico aproximado de cópias próximas, com referência limitada e seed.
    ref = treino.sample(min(5000, len(treino)), random_state=seed)
    pre = ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(keep_empty_features=True), StandardScaler()), NUMERICAS_CTGAN),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAS),
    ])
    xr = pre.fit_transform(ref[CTGAN_FEATURES])
    xs = pre.transform(sinteticos[CTGAN_FEATURES])
    distancias = NearestNeighbors(n_neighbors=1).fit(xr).kneighbors(xs)[0][:, 0]
    condicionais = {}
    for nome, df in [("real", treino), ("sintetico", sinteticos)]:
        grupo = df.assign(estrato=estratos(df))
        condicionais[nome] = {
            "estratos": estratos(df).value_counts(normalize=True).sort_index().to_dict(),
            "medianas_por_estrato": grupo.groupby("estrato")[["peso_total_g", "volume_total_cm3", "valor_itens"]].median().to_dict(),
            "medianas_por_categoria": grupo.groupby("categoria_principal")[["peso_total_g", "volume_total_cm3", "valor_itens"]].median().to_dict(),
            "categorias_por_estrato": pd.crosstab(grupo.estrato, grupo.categoria_principal, normalize="index").to_dict(),
            "correlacoes": df[NUMERICAS_CTGAN].corr().to_dict(),
            "contingencia_uf": pd.crosstab(df.seller_state, df.customer_state, normalize=True).to_dict(),
            "media_por_mes": df.assign(mes=pd.to_datetime(df.order_approved_at).dt.month).groupby("mes")[NUMERICAS_CTGAN].mean().to_dict(),
        }
    return {"numericos": numericos, "categoricos": categoricos, "condicionais": condicionais,
            "copias_exatas_treino": int(fingerprints(sinteticos).isin(set(fingerprints(treino))).sum()),
            "duplicatas_sinteticas": int(sinteticos[CTGAN_FEATURES].duplicated().sum()),
            "distancia_vizinho_mais_proximo": pd.Series(distancias).quantile([0, .1, .5, .9, 1]).to_dict(),
            "referencias_vizinhos": len(ref), "nota": "Diagnóstico aproximado, não prova ausência de memorização. Datas independentes podem enfraquecer dependências de calendário."}
