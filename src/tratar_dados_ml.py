"""Prepara dados reais para ML; nao treina classificadores nem regressores."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from .preparar_dados import RAIZ, COLUNAS_PREVISAO, exigir, validar_chave, ler, coordenadas_por_cep, distancia_km
except ImportError:
    from preparar_dados import RAIZ, COLUNAS_PREVISAO, exigir, validar_chave, ler, coordenadas_por_cep, distancia_km


CATEGORICAS = ["customer_state", "uf_origem", "categoria_principal", "tipo_pagamento_principal"]
NUMERICAS = [c for c in COLUNAS_PREVISAO if c not in CATEGORICAS]
DATAS = ["order_purchase_timestamp", "order_approved_at", "order_delivered_customer_date", "order_estimated_delivery_date"]
CORTE_VALIDACAO = pd.Timestamp("2018-01-01")
CORTE_TESTE = pd.Timestamp("2018-05-01")
UFS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())


def sha256(caminho):
    digest = hashlib.sha256()
    with Path(caminho).open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def localizar_entrada(entrada=None):
    if entrada is not None:
        caminho = Path(entrada).resolve()
        exigir(caminho.is_file(), f"CSV nao encontrado: {caminho}")
        return caminho
    for nome in ["pedidos_consolidados.csv", "pedidos_consolidados_teste.csv"]:
        caminho = RAIZ / "Dados" / nome
        if caminho.is_file():
            return caminho
    raise FileNotFoundError("Gere ou informe um CSV consolidado com --entrada.")


def corrigir_distancias(base, pasta_originais, registro):
    """Recalcula distancias apenas de coordenadas reais geograficamente plausiveis."""
    geo = ler("olist_geolocation_dataset.csv", pasta_originais)
    # Retangulo conservador, incluindo ilhas oceanicas. Nao e uma malha
    # territorial e nao valida a exatidao municipal de cada coordenada.
    plausiveis = geo["geolocation_lat"].between(-34, 6) & geo["geolocation_lng"].between(-74, -28)
    registro.append(f"Coordenadas originais fora do retangulo conservador: {(~plausiveis).sum()}")
    coords = coordenadas_por_cep(geo.loc[plausiveis])
    vendedores = ler("olist_sellers_dataset.csv", pasta_originais)
    vendedores["seller_zip_code_prefix"] = vendedores["seller_zip_code_prefix"].str.zfill(5)
    validar_chave(vendedores, ["seller_id"], "Vendedores")
    itens = ler("olist_order_items_dataset.csv", pasta_originais)
    origens = itens[["order_id", "seller_id"]].drop_duplicates()
    origens = origens.merge(vendedores[["seller_id", "seller_zip_code_prefix"]],
                            on="seller_id", how="left", validate="many_to_one")
    origens = origens.merge(coords.rename(columns={"geolocation_zip_code_prefix": "seller_zip_code_prefix",
                                                  "latitude": "lat_vendedor", "longitude": "lon_vendedor"}),
                            on="seller_zip_code_prefix", how="left", validate="many_to_one")
    destinos = base[["order_id", "customer_zip_code_prefix"]].copy()
    destinos["customer_zip_code_prefix"] = destinos["customer_zip_code_prefix"].str.zfill(5)
    destinos = destinos.merge(coords.rename(columns={"geolocation_zip_code_prefix": "customer_zip_code_prefix",
                                                     "latitude": "lat_cliente", "longitude": "lon_cliente"}),
                              on="customer_zip_code_prefix", how="left", validate="many_to_one")
    origens = origens.merge(destinos[["order_id", "lat_cliente", "lon_cliente"]],
                            on="order_id", how="inner", validate="many_to_one")
    origens["distancia"] = distancia_km(origens["lat_cliente"], origens["lon_cliente"],
                                         origens["lat_vendedor"], origens["lon_vendedor"])
    origens["sem_distancia"] = origens["distancia"].isna().astype(int)
    resumo = origens.groupby("order_id", as_index=False).agg(
        distancia_media_vendedores_km=("distancia", "mean"),
        distancia_max_vendedores_km=("distancia", "max"),
        vendedores_sem_distancia=("sem_distancia", "sum"))
    colunas = ["distancia_media_vendedores_km", "distancia_max_vendedores_km", "vendedores_sem_distancia"]
    anterior = base.set_index("order_id")["distancia_max_vendedores_km"]
    base = base.drop(columns=colunas).merge(resumo, on="order_id", how="left", validate="one_to_one")
    novo = base.set_index("order_id")["distancia_max_vendedores_km"]
    iguais = np.isclose(anterior, novo.reindex(anterior.index), atol=0.001, equal_nan=True, rtol=0)
    registro.append(f"Pedidos com distancia maxima alterada/indefinida apos revisao geografica: {(~iguais).sum()}")
    return base


def limpar_atributos(base):
    """Regras de dominio fixas, sem aprender estatisticas de validacao/teste."""
    x = base[COLUNAS_PREVISAO].copy()
    alteracoes = {}
    for coluna in NUMERICAS:
        original = x[coluna]
        valores = pd.to_numeric(original, errors="coerce").astype(float)
        validos = np.isfinite(valores) & valores.ge(0)
        if coluna in {"peso_total_g", "volume_total_cm3", "quantidade_itens", "quantidade_produtos",
                      "quantidade_vendedores", "quantidade_pagamentos", "quantidade_formas_pagamento"}:
            validos &= valores.gt(0)
        if coluna.startswith(("quantidade_", "itens_sem_", "vendedores_sem_")) or coluna in {
            "parcelas_maximas", "dia_semana_aprovacao", "mes_aprovacao", "hora_aprovacao"}:
            validos &= valores.eq(np.floor(valores))
        if coluna == "dia_semana_aprovacao": validos &= valores.le(6)
        if coluna == "mes_aprovacao": validos &= valores.between(1, 12)
        if coluna == "hora_aprovacao": validos &= valores.le(23)
        if coluna.startswith("distancia_"): validos &= valores.le(np.pi * 6371.0088)
        alteracoes[coluna] = int((original.notna() & ~validos).sum())
        x[coluna] = valores.where(validos)
    for coluna in CATEGORICAS:
        valores = x[coluna].astype("string").str.strip()
        valores = valores.mask(valores.str.lower().isin(["", "nan", "none", "null"]))
        if coluna in {"customer_state", "uf_origem"}:
            valores = valores.str.upper()
            permitidos = UFS | ({"MULTIPLAS"} if coluna == "uf_origem" else set())
            valores = valores.where(valores.isin(permitidos))
        else:
            valores = valores.str.lower()
        alteracoes[coluna] = int((x[coluna].notna() & valores.isna()).sum())
        x[coluna] = valores.astype(object).where(valores.notna(), np.nan)
    return x, alteracoes


def selecionar_coorte(base, registro):
    base = base.copy()
    n = len(base)
    base = base.drop_duplicates()
    registro.append(f"Duplicatas identicas removidas: {n-len(base)}")
    exigir(not base["order_id"].dropna().duplicated().any(), "Mesmo order_id com linhas conflitantes; revisar a origem.")
    for coluna in DATAS:
        original = base[coluna]
        base[coluna] = pd.to_datetime(original, errors="coerce")
        registro.append(f"Datas invalidas convertidas em ausentes em {coluna}: {(original.notna() & base[coluna].isna()).sum()}")
    compra, aprovacao, entrega, promessa = [base[c] for c in DATAS]
    regras = [
        ("identificador ausente", base["order_id"].notna()),
        ("sem status delivered", base["order_status"].eq("delivered")),
        ("datas essenciais ausentes/invalidas", base[DATAS].notna().all(axis=1)),
        ("aprovacao anterior a compra", aprovacao.ge(compra)),
        ("entrega anterior a aprovacao", entrega.ge(aprovacao)),
        ("promessa anterior ao dia da aprovacao", promessa.dt.normalize().ge(aprovacao.dt.normalize())),
        ("sem itens", base["quantidade_itens"].gt(0)),
    ]
    aceitos = pd.Series(True, index=base.index)
    for motivo, regra in regras:
        excluidos = aceitos & ~regra.fillna(False)
        registro.append(f"Exclusao sequencial - {motivo}: {excluidos.sum()}")
        aceitos &= regra.fillna(False)
    base = base.loc[aceitos].copy()
    diferenca = (base["order_delivered_customer_date"].dt.normalize()
                 - base["order_estimated_delivery_date"].dt.normalize()).dt.days
    exigir(base["atrasou"].eq(diferenca.gt(0).astype(int)).all(), "Rotulos existentes discordam das datas reais.")
    exigir(base["dias_atraso"].eq(diferenca.clip(lower=0)).all(), "Dias de atraso discordam das datas reais.")
    base["atrasou"] = base["atrasou"].astype("int8")
    base["dias_atraso"] = base["dias_atraso"].astype("int32")
    base["rotulo_disponivel_em"] = base["order_delivered_customer_date"]
    registro.append(f"Coorte basica antes da separacao temporal: {len(base)}")
    return base.sort_values(["order_approved_at", "order_id"]).reset_index(drop=True)


def separar_por_tempo(base, corte_validacao=CORTE_VALIDACAO, corte_teste=CORTE_TESTE):
    exigir(corte_validacao < corte_teste, "Cortes temporais fora de ordem.")
    datas = base["order_approved_at"]
    particao = pd.Series("teste", index=base.index)
    particao.loc[datas.lt(corte_teste)] = "validacao"
    particao.loc[datas.lt(corte_validacao)] = "treino"
    futuro_treino = particao.eq("treino") & base["rotulo_disponivel_em"].ge(corte_validacao)
    futuro_validacao = particao.eq("validacao") & base["rotulo_disponivel_em"].ge(corte_teste)
    descartes = {"rotulo_futuro_treino": int(futuro_treino.sum()),
                 "rotulo_futuro_validacao": int(futuro_validacao.sum())}
    resultado = base.loc[~(futuro_treino | futuro_validacao)].copy()
    resultado["particao"] = particao.loc[resultado.index]
    return resultado, descartes


def criar_preprocessador():
    return ColumnTransformer([
        ("numericas", Pipeline([
            ("imputador", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("escala", StandardScaler()),
        ]), NUMERICAS),
        ("categoricas", Pipeline([
            ("imputador", SimpleImputer(strategy="constant", fill_value="NAO_INFORMADO", keep_empty_features=True)),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float32)),
        ]), CATEGORICAS),
    ], remainder="drop")


def preparar(entrada=None, corte_validacao=CORTE_VALIDACAO, corte_teste=CORTE_TESTE):
    entrada = localizar_entrada(entrada)
    originais = RAIZ / "Dados" / "Brazilian Logistic"
    fontes = [entrada, *[originais / nome for nome in ["olist_geolocation_dataset.csv", "olist_sellers_dataset.csv", "olist_order_items_dataset.csv"]]]
    hashes = {str(p.relative_to(RAIZ)) if p.is_relative_to(RAIZ) else str(p): sha256(p) for p in fontes}
    registro = ["TRATAMENTO PARA TESTES DE ML - EntregaCerta AI", f"Entrada: {entrada}",
                f"Python {sys.version.split()[0]}; Pandas {pd.__version__}; NumPy {np.__version__}; Scikit-learn {sklearn.__version__}; Joblib {joblib.__version__}"]
    base = pd.read_csv(entrada, dtype={"customer_zip_code_prefix": "string"})
    registro.append(f"Pedidos na entrada: {len(base)}")
    base = selecionar_coorte(base, registro)
    base = corrigir_distancias(base, originais, registro)
    x, invalidos = limpar_atributos(base)
    # Substituir colunas permite a conversao explicita para float no Pandas 3.
    base[COLUNAS_PREVISAO] = x
    registro += [f"Valores invalidos tornados ausentes em {c}: {n}" for c,n in invalidos.items() if n]
    registro += [f"Ausencias antes de imputar {c}: {int(n)}" for c,n in x.isna().sum().items() if n]
    base, descartes = separar_por_tempo(base, corte_validacao, corte_teste)
    # Reconstituir object/np.nan nas categorias apos a atribuicao ao DataFrame.
    x, _ = limpar_atributos(base)
    mascara_treino = base["particao"].eq("treino")
    exigir(mascara_treino.any(), "Treino vazio.")
    preprocessador = criar_preprocessador()
    preprocessador.fit(x.loc[mascara_treino])
    numerico = preprocessador.named_transformers_["numericas"].named_steps["imputador"]
    categorico = preprocessador.named_transformers_["categoricas"].named_steps["imputador"]
    # CSV legivel: preservar unidades, imputando com os mesmos valores do treino.
    preenchido = x.copy()
    for coluna, valor in zip(NUMERICAS, numerico.statistics_):
        preenchido[coluna] = preenchido[coluna].fillna(valor)
    preenchido[CATEGORICAS] = categorico.transform(x[CATEGORICAS])
    for indice in numerico.indicator_.features_:
        coluna = NUMERICAS[indice]
        preenchido[f"faltante_{coluna}"] = x[coluna].isna().astype("int8")
    meta = base[["order_id", "customer_unique_id", "order_approved_at", "rotulo_disponivel_em", "particao", "atrasou", "dias_atraso"]]
    csv = pd.concat([meta, preenchido], axis=1).reset_index(drop=True)
    exigir(not csv.isna().any().any(), "O CSV de ML ainda tem valores ausentes.")
    artefato = {"preprocessador": preprocessador, "colunas_entrada": list(COLUNAS_PREVISAO),
                "nomes_atributos": list(preprocessador.get_feature_names_out()),
                "X": {}, "y": {}, "y_dias_atraso": {}, "metadados": {},
                "cortes": {"validacao": str(corte_validacao), "teste": str(corte_teste)}, "hashes_entrada": hashes}
    registro += [f"Corte da validacao: {corte_validacao}", f"Corte do teste: {corte_teste}",
                  *[f"Exclusao temporal - {nome}: {n}" for nome,n in descartes.items()]]
    for nome in ["treino", "validacao", "teste"]:
        mascara = base["particao"].eq(nome)
        exigir(mascara.any(), f"Particao vazia: {nome}")
        matriz = preprocessador.transform(x.loc[mascara]).astype(np.float32)
        exigir(np.isfinite(matriz).all(), f"Matriz com NaN/infinito: {nome}")
        alvo = base.loc[mascara, "atrasou"].to_numpy(dtype=np.int8)
        exigir(set(alvo) == {0,1}, f"Particao sem ambas as classes: {nome}")
        artefato["X"][nome] = matriz
        artefato["y"][nome] = alvo
        artefato["y_dias_atraso"][nome] = base.loc[mascara, "dias_atraso"].to_numpy(dtype=np.int32)
        artefato["metadados"][nome] = meta.loc[mascara].reset_index(drop=True)
        registro.append(f"{nome}: {len(alvo)} pedidos; atrasados observados: {alvo.sum()} ({alvo.mean():.2%}); matriz {matriz.shape}")
        registro.append(f"{nome}: aprovacoes de {base.loc[mascara,'order_approved_at'].min()} a {base.loc[mascara,'order_approved_at'].max()}")
    ids_treino = set(artefato["metadados"]["treino"]["customer_unique_id"])
    for nome in ["validacao", "teste"]:
        conhecidos = artefato["metadados"][nome]["customer_unique_id"].isin(ids_treino).sum()
        registro.append(f"Pedidos de {nome} cujo cliente tambem aparece no treino: {conhecidos} (IDs fora das entradas)")
    for p, (_,hash_anterior) in zip(fontes, hashes.items()):
        exigir(sha256(p) == hash_anterior, f"Arquivo de entrada alterado: {p}")
    registro += [f"Total de pedidos no CSV preparado: {len(csv)}", f"Entradas originais: {len(COLUNAS_PREVISAO)}; atributos transformados: {len(artefato['nomes_atributos'])}",
                 "Imputacao, escala e categorias ajustadas SOMENTE no treino.",
                 "CSV: valores numericos nas unidades originais, ausencias imputadas e indicadores faltante_*; categorias ainda legiveis.",
                 "Joblib: matrizes codificadas e padronizadas prontas para estimadores, alvos e preprocessador reutilizavel.",
                 "Nao houve balanceamento artificial, remocao de valores extremos validos, treinamento preditivo ou metricas de modelo.",
                 "Limites: coorte retrospectiva de entregues; purga temporal pode alterar a representatividade de entregas demoradas.",
                 "Pontos dentro do retangulo geografico ainda podem estar incorretos; distancias por CEP sao aproximacoes.",
                 "A disponibilidade historica de cadastros, pagamentos e promessa na aprovacao permanece uma hipotese.",
                 "Teste final reservado; nao usar para escolher modelos, limiares ou tratamentos.",
                 "Referencias: https://scikit-learn.org/stable/common_pitfalls.html",
                 "https://scikit-learn.org/stable/modules/generated/sklearn.impute.SimpleImputer.html",
                 "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.OneHotEncoder.html",
                 "IBGE (limites usados para retangulo conservador, incluindo ilhas): https://anuario.ibge.gov.br/images/aeb/2024/s1/2_pdf/s1t1101.pdf",
                 "HASHES DOS ARQUIVOS DE ENTRADA:", *[f"{nome}: {digest}" for nome,digest in hashes.items()]]
    return csv, artefato, "\n".join(registro) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path)
    args = parser.parse_args()
    csv, artefato, registro = preparar(args.entrada)
    saida = RAIZ / "Dados" / "pedidos_ml.csv"
    pacote = RAIZ / "Modelos" / "dados_ml.joblib"
    saida.parent.mkdir(exist_ok=True)
    pacote.parent.mkdir(exist_ok=True)
    csv.to_csv(saida.with_suffix(".csv.tmp"), index=False, encoding="utf-8", date_format="%Y-%m-%d %H:%M:%S")
    joblib.dump(artefato, pacote.with_suffix(".joblib.tmp"), compress=3)
    conferir = joblib.load(pacote.with_suffix(".joblib.tmp"))
    exigir(conferir["X"]["treino"].shape == artefato["X"]["treino"].shape, "Falha ao reabrir pacote.")
    saida.with_suffix(".csv.tmp").replace(saida)
    pacote.with_suffix(".joblib.tmp").replace(pacote)
    registro += f"SHA-256 do CSV preparado: {sha256(saida)}\nSHA-256 do pacote: {sha256(pacote)}\n"
    (RAIZ / "Docs" / "tratamento_ml.txt").write_text(registro, encoding="utf-8")
    print(registro)


if __name__ == "__main__":
    main()
