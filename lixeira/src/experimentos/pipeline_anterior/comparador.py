"""Laboratório configurável: python -m src.ml.experimentos --config ..."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time
from importlib.metadata import version

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

from src.experimentos.pipeline_anterior.preparar_dados import RAIZ, COLUNAS_PREVISAO, ler
from src.experimentos.pipeline_anterior.avaliacoes import ATRIBUTOS_NOTAS, adicionar_avaliacoes
from src.experimentos.pipeline_anterior.tratar_dados_ml import (CATEGORICAS, selecionar_coorte, separar_por_tempo,
    corrigir_distancias, limpar_atributos, localizar_entrada, sha256)
from src.ml.modelos import CATALOGO, criar_modelos
from src.ml.metricas import avaliar, escolher_limiar
from src.experimentos.pipeline_anterior import geracao as sinteticos

PARTICOES = ("treino", "validacao", "teste")


def caminho(valor):
    p = Path(valor)
    return p if p.is_absolute() else RAIZ / p


def salvar_json(destino, valor):
    destino.write_text(json.dumps(valor, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def validar_config(config):
    for campo in ["modelos", "cenarios"]:
        itens = config.get(campo, [])
        nomes = [x["nome"] for x in itens]
        if not nomes or len(set(nomes)) != len(nomes) or any(not re.fullmatch(r"[a-zA-Z0-9_-]+", n) for n in nomes):
            raise ValueError(f"{campo}: nomes únicos e somente letras, números, _ e -.")
    for m in config["modelos"]:
        if m["tipo"] not in CATALOGO:
            raise ValueError(f"Modelo desconhecido: {m['tipo']}; opções: {list(CATALOGO)}")
        criar_modelos(m, config.get("semente", 42))
    for c in config["cenarios"]:
        for p in PARTICOES:
            spec = c[p]
            if spec["modo"] not in ("real", "sintetico", "misto"):
                raise ValueError(f"Modo inválido: {c['nome']}/{p}")
            for k in ("n_reais", "n_sinteticos"):
                v = spec.get(k)
                if v is not None and (type(v) is not int or v < 0):
                    raise ValueError(f"{k} deve ser inteiro não negativo ou null.")
            if spec["modo"] != "real" and not spec.get("n_sinteticos"):
                raise ValueError("Modo sintético/misto exige n_sinteticos positivo.")
            if spec["modo"] == "real" and spec.get("n_sinteticos", 0):
                raise ValueError("Modo real não aceita n_sinteticos.")
            if spec["modo"] != "sintetico" and spec.get("n_reais") == 0:
                raise ValueError("Modo real/misto exige pedidos reais.")
    if config.get("limiar", "f1_validacao") != "f1_validacao":
        if not isinstance(config["limiar"], (int, float)) or not 0 <= config["limiar"] <= 1:
            raise ValueError("limiar deve ser f1_validacao ou número entre 0 e 1.")
    if any(not 0 < f <= 1 for f in config.get("fracoes_fila", [0.1])):
        raise ValueError("Frações da fila precisam estar em (0, 1].")


def selecionar_reais(dados, n, semente):
    if n is None:
        return dados.copy().reset_index(drop=True)
    if n > len(dados):
        raise ValueError(f"Solicitados {n} reais, disponíveis {len(dados)}.")
    # Sem reposição: preserva a identidade dos pedidos e a distribuição natural.
    return dados.sample(n=n, random_state=semente).sort_values("order_id").reset_index(drop=True)


def montar_particao(reais, gerados, spec, semente):
    partes = []
    if spec["modo"] != "sintetico":
        partes.append(selecionar_reais(reais, spec.get("n_reais"), semente))
    if spec["modo"] != "real":
        n = spec["n_sinteticos"]
        if len(gerados) < n:
            raise ValueError("Pool sintético insuficiente.")
        partes.append(gerados.iloc[:n].copy())
    resultado = pd.concat(partes, ignore_index=True).sort_values("order_id").reset_index(drop=True)
    if resultado.empty or resultado.order_id.duplicated().any():
        raise ValueError("Partição vazia ou IDs repetidos.")
    return resultado


def assinaturas(dados, atributos):
    """Normaliza tipos para reconhecer, por exemplo, contagem 1 e 1.0 iguais."""
    tabela = dados[atributos + ["atrasou", "dias_atraso"]].copy()
    for c in tabela:
        if c in CATEGORICAS:
            tabela[c] = tabela[c].fillna("NAO_INFORMADO").astype(str)
        else:
            tabela[c] = tabela[c].astype(float)
    return pd.util.hash_pandas_object(tabela, index=False)


def preprocessador(atributos):
    return ColumnTransformer([
        ("num", Pipeline([("imputar", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
                          ("escala", StandardScaler())]), [c for c in atributos if c not in CATEGORICAS]),
        ("cat", Pipeline([("imputar", SimpleImputer(strategy="constant", fill_value="NAO_INFORMADO")),
                          ("codificar", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), CATEGORICAS)
    ], remainder="drop")


def preparar(config, pasta, destino):
    entrada = localizar_entrada(caminho(config["entrada"]) if config.get("entrada") else None)
    originais = caminho(config.get("originais", "Dados/Brazilian Logistic"))
    fontes = [entrada] + sorted(originais.glob("*.csv"))
    hashes = {str(p): sha256(p) for p in fontes}
    log = []
    bruto = pd.read_csv(entrada, dtype={"customer_zip_code_prefix": "string"})
    base = selecionar_coorte(bruto, log)
    base = corrigir_distancias(base, originais, log)
    limpos, _ = limpar_atributos(base)
    base[COLUNAS_PREVISAO] = limpos
    cortes = config.get("cortes", {"validacao": "2018-01-01", "teste": "2018-05-01"})
    base, descartes = separar_por_tempo(base, pd.Timestamp(cortes["validacao"]), pd.Timestamp(cortes["teste"]))
    reviews = ler("olist_order_reviews_dataset.csv", originais)
    base = adicionar_avaliacoes(base, reviews, ler("olist_order_items_dataset.csv", originais),
                                ler("olist_orders_dataset.csv", originais))
    base["origem_dado"] = "real_olist"
    base["rotulo_observado"] = True
    atributos = COLUNAS_PREVISAO + (ATRIBUTOS_NOTAS if config.get("usar_notas_historicas", True) else [])
    reais = {p: selecionar_reais(base.loc[base.particao.eq(p)], config.get("limite_reais_por_particao", {}).get(p),
                               config.get("semente", 42)) for p in PARTICOES}
    for p, d in reais.items():
        if set(d.atrasou.unique()) != {0, 1}:
            raise ValueError(f"{p}: são necessárias ambas as classes; aumente a amostra.")
    destino.mkdir(parents=True, exist_ok=False)
    for p, d in reais.items():
        d.to_csv(destino / f"reais_{p}.csv", index=False)
    # Comentários preservados separadamente, sem multiplicar pedidos nos CSVs de treino.
    reviews.loc[reviews.order_id.isin(base.order_id)].to_csv(destino / "avaliacoes_clientes_eda.csv", index=False)
    maximos = {p: max(c[p].get("n_sinteticos", 0) or 0 for c in config["cenarios"]) for p in PARTICOES}
    pools = {p: pd.DataFrame() for p in PARTICOES}
    if any(maximos.values()):
        print("Ajustando CTGAN exclusivamente no treino real...", flush=True)
        pacote = sinteticos.ajustar(reais["treino"], config.get("ctgan", {}), config.get("semente", 42), atributos)
        joblib.dump(pacote, pasta / "gerador_ctgan.joblib", compress=3)
        hashes_vistos = set(assinaturas(reais["treino"], atributos))
        for i, p in enumerate(PARTICOES):
            n = maximos[p]
            if n:
                partes, total = [], 0
                for tentativa in range(20):
                    lote = sinteticos.amostrar(pacote, n - total, p, config.get("semente", 42) + 1000 * (i + 1) + tentativa)
                    chaves = assinaturas(lote, atributos)
                    aceita = ~chaves.isin(hashes_vistos) & ~chaves.duplicated()
                    partes.append(lote.loc[aceita])
                    hashes_vistos.update(chaves.loc[aceita])
                    total += int(aceita.sum())
                    if total == n:
                        break
                if total != n:
                    raise ValueError("CTGAN não gerou amostras distintas suficientes após 20 tentativas.")
                pools[p] = pd.concat(partes, ignore_index=True)
                pools[p].to_csv(destino / f"sinteticos_{p}.csv", index=False)
    resumo = []
    for c in config["cenarios"]:
        out = destino / c["nome"]
        out.mkdir()
        ids = set()
        for p in PARTICOES:
            d = montar_particao(reais[p], pools[p], c[p], config.get("semente", 42))
            if ids.intersection(d.order_id):
                raise ValueError("Mesmo pedido em mais de uma partição.")
            ids.update(d.order_id)
            d.to_csv(out / f"{p}.csv", index=False)
            resumo.append({"cenario": c["nome"], "particao": p, "modo": c[p]["modo"], "pedidos": len(d),
                           "reais": int(d.origem_dado.eq("real_olist").sum()), "sinteticos": int(d.origem_dado.eq("sintetico_ctgan").sum()),
                           "taxa_atraso": d.atrasou.mean(), "dias_atraso_media": d.dias_atraso.mean()})
    pd.DataFrame(resumo).to_csv(destino / "resumo_particoes.csv", index=False)
    if any(sha256(Path(p)) != h for p, h in hashes.items()):
        raise ValueError("Fonte alterada durante a preparação.")
    salvar_json(pasta / "preparacao.json", {"atributos": atributos, "fontes_sha256": hashes,
                "pasta_dados": str(destino.relative_to(RAIZ)) if destino.is_relative_to(RAIZ) else str(destino),
                "descartes_temporais": descartes, "log": log,
                "csv_sha256": {str(p.relative_to(destino)): sha256(p) for p in destino.rglob("*.csv")}})


def treinar(config, pasta):
    preparo = json.loads((pasta / "preparacao.json").read_text(encoding="utf-8"))
    destino = caminho(preparo["pasta_dados"])
    for p, h in preparo["csv_sha256"].items():
        if sha256(destino / p) != h:
            raise ValueError(f"CSV alterado depois da preparação: {p}")
    atributos = preparo["atributos"]
    out = pasta / "resultados"
    out.mkdir()  # Falha explicitamente se já treinado; não substitui uma rodada.
    metricas, selecionados = [], []
    teste_real = pd.read_csv(destino / "reais_teste.csv", low_memory=False)
    for c in config["cenarios"]:
        dados = {p: pd.read_csv(destino / c["nome"] / f"{p}.csv", low_memory=False) for p in PARTICOES}
        for p in ("treino", "validacao"):
            if set(dados[p].atrasou.unique()) != {0, 1}:
                raise ValueError(f"{c['nome']}/{p} sem ambas as classes; aumente amostras.")
        # Categorias como object/np.nan, compatíveis com sklearn e pandas 2/3.
        for d in [*dados.values(), teste_real]:
            d[CATEGORICAS] = d[CATEGORICAS].astype(object).where(d[CATEGORICAS].notna(), np.nan)
        for m in config["modelos"]:
            print(f"Treinando {c['nome']} / {m['nome']}...", flush=True)
            inicio = time.perf_counter()
            cls, reg = criar_modelos(m, config.get("semente", 42))
            classificador = Pipeline([("preprocessador", preprocessador(atributos)), ("modelo", cls)])
            regressor = Pipeline([("preprocessador", preprocessador(atributos)), ("modelo", reg)])
            with threadpool_limits(limits=config.get("threads", 2)):
                classificador.fit(dados["treino"][atributos], dados["treino"].atrasou)
                regressor.fit(dados["treino"][atributos], dados["treino"].dias_atraso)
            positivo = list(classificador.classes_).index(1)
            scores_val = classificador.predict_proba(dados["validacao"][atributos])[:, positivo]
            limiar = config.get("limiar", "f1_validacao")
            if limiar == "f1_validacao":
                limiar = escolher_limiar(dados["validacao"].atrasou, scores_val)
            duracao = time.perf_counter() - inicio
            local = out / c["nome"] / m["nome"]
            local.mkdir(parents=True)
            joblib.dump({"classificador": classificador, "regressor": regressor, "limiar": limiar,
                         "atributos": atributos, "config_modelo": m}, local / "modelo.joblib", compress=3)
            for p, d in [*dados.items(), ("teste_real_referencia", teste_real)]:
                with threadpool_limits(limits=config.get("threads", 2)):
                    scores = classificador.predict_proba(d[atributos])[:, positivo]
                    dias = np.maximum(0, regressor.predict(d[atributos]))
                prev = d[["order_id", "origem_dado", "atrasou", "dias_atraso"]].copy()
                prev["score_atraso"] = scores
                prev["previsao_atrasou"] = (scores >= limiar).astype(int)
                prev["previsao_dias_atraso"] = dias
                prev["erro_dias"] = dias - d.dias_atraso
                prev["limiar"] = limiar
                prev.to_csv(local / f"previsoes_{p}.csv", index=False)
                for segmento in ["todos", "real_olist", "sintetico_ctgan"]:
                    mascara = np.ones(len(d), dtype=bool) if segmento == "todos" else d.origem_dado.eq(segmento).to_numpy()
                    if not mascara.any():
                        continue
                    met = avaliar(d.atrasou.to_numpy()[mascara], scores[mascara], d.dias_atraso.to_numpy()[mascara], dias[mascara],
                                  limiar, config.get("fracoes_fila", [0.1]))
                    met.update(cenario=c["nome"], modelo=m["nome"], particao=p, segmento=segmento,
                               segundos_treino=duracao,
                               avaliacao_sintetica=bool(d.loc[mascara, "origem_dado"].eq("sintetico_ctgan").any()),
                               limiar_ajustado_com_sinteticos=bool(dados["validacao"].origem_dado.eq("sintetico_ctgan").any()))
                    metricas.append(met)
            pd.DataFrame(metricas).to_csv(out / "metricas.csv", index=False)
        val = pd.DataFrame(metricas)
        val = val.loc[val.cenario.eq(c["nome"]) & val.particao.eq("validacao") & val.segmento.eq("todos")]
        selecionados.append({"cenario": c["nome"],
            "melhor_classificador_f1": val.sort_values(["f1", "average_precision", "modelo"], ascending=[False, False, True]).iloc[0].modelo,
            "melhor_regressor_mae": val.sort_values(["mae_dias", "modelo"]).iloc[0].modelo,
            "criterio": "somente validacao configurada"})
    pd.DataFrame(selecionados).to_csv(out / "selecionados_validacao.csv", index=False)
    cols = ["cenario", "modelo", "particao", "segmento", "tn", "fp", "fn", "tp"]
    pd.DataFrame(metricas)[cols].to_csv(out / "matrizes_confusao.csv", index=False)


def executar(config, pasta, etapa="tudo", destino=None):
    validar_config(config)
    destino = destino or RAIZ / "Dados/comparacao_modelos" / pasta.name
    if etapa != "treinar":
        if destino.exists():
            raise FileExistsError(f"Pasta de dados já existe: {destino}; escolha outro nome de execução.")
        pasta.mkdir(parents=True, exist_ok=False)
        salvar_json(pasta / "config.json", config)
        manifesto = {"status": "iniciada", "inicio_utc": datetime.now(timezone.utc).isoformat(),
                     "python": sys.version, "versoes": {m: version(m) for m in ["pandas", "numpy", "scikit-learn", "joblib"]},
                     "codigo_sha256": {str(p.relative_to(RAIZ)): sha256(p) for pasta_codigo in [RAIZ / "src/ml", RAIZ / "src/dados", RAIZ / "src/ctgan"] for p in pasta_codigo.glob("*.py")},
                     "limite_interpretacao": "Sintéticos são diagnóstico do gerador, não evidência independente; teste real é exportado separadamente."}
        if any(c[p]["modo"] != "real" for c in config["cenarios"] for p in PARTICOES):
            manifesto["versoes"].update({m: version(m) for m in ["ctgan", "torch", "rdt"]})
    else:
        if json.loads((pasta / "config.json").read_text(encoding="utf-8")) != config:
            raise ValueError("Configuração diverge da preparação; crie outra execução.")
        manifesto = json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))
    salvar_json(pasta / "manifesto.json", manifesto)
    try:
        if etapa != "treinar":
            preparar(config, pasta, destino)
        if etapa != "preparar":
            treinar(config, pasta)
        manifesto["status"] = "preparada" if etapa == "preparar" else "concluida"
    except Exception as erro:
        manifesto.update(status="falhou", erro=str(erro))
        raise
    finally:
        manifesto["fim_utc"] = datetime.now(timezone.utc).isoformat()
        salvar_json(pasta / "manifesto.json", manifesto)
    return pasta


def executar_configuracao(config_path=None, nome=None, etapa="tudo"):
    config_path = caminho(config_path or "src/configuracoes/treinamento.json")
    nome = nome or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", nome):
        raise ValueError("Nome da execução: use somente letras, números, _ e -.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    pasta = RAIZ / "Modelos/comparacao_modelos" / nome
    executar(config, pasta, etapa)
    (pasta.parent / "ultima_execucao.txt").write_text(nome, encoding="utf-8")
    print("CSVs:", RAIZ / "Dados/comparacao_modelos" / nome)
    print("Modelos e métricas:", pasta)
    return pasta


def mostrar_resultados(nome=None):
    raiz_resultados = RAIZ / "Modelos/comparacao_modelos"
    if nome is None:
        nome = (raiz_resultados / "ultima_execucao.txt").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", nome):
        raise ValueError("Nome de execução inválido.")
    pasta = raiz_resultados / nome
    manifesto = json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))
    if manifesto["status"] != "concluida":
        raise ValueError(f"Execução {nome}: {manifesto['status']}; conclua o treinamento antes de avaliar.")
    metricas = pd.read_csv(pasta / "resultados/metricas.csv")
    resumo = metricas.loc[metricas.particao.eq("teste_real_referencia") & metricas.segmento.eq("todos")]
    print("Execução:", nome, "— desempenho no teste real comum")
    print(resumo[["cenario", "modelo", "f1", "precision", "recall", "accuracy", "mae_dias", "rmse_dias"]].to_string(index=False))
    print("Seleção feita na validação:")
    print(pd.read_csv(pasta / "resultados/selecionados_validacao.csv").to_string(index=False))
    print("Métricas completas:", pasta / "resultados/metricas.csv")
    return resumo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=RAIZ / "src/configuracoes/treinamento.json")
    parser.add_argument("--nome", help="Nome da execução; obrigatório para retomar com --etapa treinar.")
    parser.add_argument("--etapa", choices=["preparar", "treinar", "tudo"], default="tudo")
    args = parser.parse_args()
    if args.etapa == "treinar" and args.nome is None:
        parser.error("--etapa treinar exige --nome da preparação anterior")
    executar_configuracao(args.config, args.nome, args.etapa)


if __name__ == "__main__":
    main()
