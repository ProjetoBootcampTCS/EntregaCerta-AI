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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

from src.dados.esquema import RAIZ, ATRIBUTOS, CATEGORICAS, sha256
from src.ml.dados_treino import carregar, exigir_revisao, atributos_configurados
from src.ml.modelos import CATALOGO, criar_modelos
from src.ml.metricas import avaliar, escolher_limiar
from src.ctgan import geracao as sinteticos

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
    arquivos_modelos = [f"{c['nome']}__{m['nome']}" for c in config["cenarios"] for m in config["modelos"]]
    if len(set(arquivos_modelos)) != len(arquivos_modelos):
        raise ValueError("Os nomes de cenários/modelos geram arquivos iguais; ajuste os nomes.")
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
    tabela = dados[atributos + ["delay_status", "delay_in_days"]].copy()
    for c in tabela:
        if c in CATEGORICAS:
            tabela[c] = tabela[c].fillna("NAO_INFORMADO").astype(str)
        else:
            tabela[c] = tabela[c].astype(float)
    return pd.util.hash_pandas_object(tabela, index=False)


def preprocessador(atributos):
    # Apenas representação técnica; nenhum preenchimento ou filtro de valores.
    categorias = [c for c in atributos if c in CATEGORICAS]
    return ColumnTransformer([
        ("num", StandardScaler(), [c for c in atributos if c not in CATEGORICAS]),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorias),
    ], remainder="drop")


def preparar(config, pasta, destino):
    entrada = caminho(config.get("entrada", "Dados/dataset_ml.csv"))
    hashes = {str(entrada): sha256(entrada)}
    base, atributos, separacao = carregar(config)
    reais = {p: selecionar_reais(base.loc[base.particao.eq(p)], config.get("limite_reais_por_particao", {}).get(p),
                               config.get("semente", 42)) for p in PARTICOES}
    for p, d in reais.items():
        if set(d.delay_status.unique()) != {0, 1}:
            raise ValueError(f"{p}: são necessárias ambas as classes; revise a partição/amostra.")
    destino.mkdir(parents=True, exist_ok=False)
    for p, d in reais.items():
        d.to_csv(destino / f"reais_{p}.csv", index=False)
    maximos = {p: max(c[p].get("n_sinteticos", 0) or 0 for c in config["cenarios"]) for p in PARTICOES}
    pools = {p: pd.DataFrame() for p in PARTICOES}
    if any(maximos.values()):
        print("Ajustando CTGAN exclusivamente no treino real...", flush=True)
        pacote = sinteticos.ajustar(reais["treino"], {**config.get("ctgan", {}), "dados_validados": config["dados_validados"]}, config.get("semente", 42), atributos)
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
                           "taxa_atraso": d.delay_status.mean(), "delay_in_days_media": d.delay_in_days.mean()})
    pd.DataFrame(resumo).to_csv(destino / "resumo_particoes.csv", index=False)
    if any(sha256(Path(p)) != h for p, h in hashes.items()):
        raise ValueError("Fonte alterada durante a preparação.")
    salvar_json(pasta / "preparacao.json", {"atributos": atributos, "fontes_sha256": hashes,
                "pasta_dados": str(destino.relative_to(RAIZ)) if destino.is_relative_to(RAIZ) else str(destino),
                "separacao": separacao,
                "csv_sha256": {str(p.relative_to(destino)): sha256(p) for p in destino.rglob("*.csv")}})


def arquivo_resultados(config, nome):
    return caminho(config.get("saida_resultados", "Dados/resultados_modelos")) / f"{nome}.csv"


def marcar_selecionados(metricas):
    metricas = metricas.copy()
    metricas["melhor_classificador_validacao"] = False
    metricas["melhor_regressor_validacao"] = False
    for cenario in metricas.cenario.unique():
        mascara = metricas.cenario.eq(cenario)
        val = metricas.loc[mascara & metricas.particao.eq("validacao") & metricas.segmento.eq("todos")]
        if val.empty:
            continue
        cls = val.sort_values(["f1", "average_precision", "modelo"], ascending=[False, False, True]).iloc[0].modelo
        metricas.loc[mascara & metricas.modelo.eq(cls), "melhor_classificador_validacao"] = True
        reg = val.dropna(subset=["mae_dias"]).sort_values(["mae_dias", "modelo"])
        if len(reg):
            metricas.loc[mascara & metricas.modelo.eq(reg.iloc[0].modelo), "melhor_regressor_validacao"] = True
    return metricas


def treinar(config, pasta):
    exigir_revisao(config)
    preparo = json.loads((pasta / "preparacao.json").read_text(encoding="utf-8"))
    destino = caminho(preparo["pasta_dados"])
    for p, h in preparo["csv_sha256"].items():
        if sha256(destino / p) != h:
            raise ValueError(f"CSV alterado depois da preparação: {p}")
    atributos = preparo["atributos"]
    resultado = arquivo_resultados(config, pasta.name)
    previsoes = pasta / "previsoes.csv"
    if resultado.exists() or previsoes.exists():
        raise FileExistsError("Execução já possui resultados; escolha outro nome.")
    metricas = []
    teste_real = pd.read_csv(destino / "reais_teste.csv", low_memory=False)
    for c in config["cenarios"]:
        dados = {p: pd.read_csv(destino / c["nome"] / f"{p}.csv", low_memory=False) for p in PARTICOES}
        for p in ("treino", "validacao"):
            if set(dados[p].delay_status.unique()) != {0, 1}:
                raise ValueError(f"{c['nome']}/{p} sem ambas as classes; aumente amostras.")
        # Categorias como object/np.nan, compatíveis com sklearn e pandas 2/3.
        for d in [*dados.values(), teste_real]:
            categorias = [c for c in atributos if c in CATEGORICAS]
            d[categorias] = d[categorias].astype(object)
        for m in config["modelos"]:
            print(f"Treinando {c['nome']} / {m['nome']}...", flush=True)
            inicio = time.perf_counter()
            cls, reg = criar_modelos(m, config.get("semente", 42))
            classificador = Pipeline([("preprocessador", preprocessador(atributos)), ("modelo", cls)])
            regressor = Pipeline([("preprocessador", preprocessador(atributos)), ("modelo", reg)])
            with threadpool_limits(limits=config.get("threads", 2)):
                classificador.fit(dados["treino"][atributos], dados["treino"].delay_status)
                dias_conhecidos = dados["treino"].delay_in_days.notna()
                if dias_conhecidos.any():
                    regressor.fit(dados["treino"].loc[dias_conhecidos, atributos], dados["treino"].loc[dias_conhecidos, "delay_in_days"])
                else:
                    regressor = None
            positivo = list(classificador.classes_).index(1)
            scores_val = classificador.predict_proba(dados["validacao"][atributos])[:, positivo]
            limiar = config.get("limiar", "f1_validacao")
            if limiar == "f1_validacao":
                limiar = escolher_limiar(dados["validacao"].delay_status, scores_val)
            duracao = time.perf_counter() - inicio
            joblib.dump({"classificador": classificador, "regressor": regressor, "limiar": limiar,
                         "atributos": atributos, "config_modelo": m, "review_score_origem": config.get("review_score_origem"), "alvo_classe": "delay_status", "alvo_dias": "delay_in_days"}, pasta / f"{c['nome']}__{m['nome']}.joblib", compress=3)
            for p, d in [*dados.items(), ("teste_real_referencia", teste_real)]:
                with threadpool_limits(limits=config.get("threads", 2)):
                    scores = classificador.predict_proba(d[atributos])[:, positivo]
                    dias = regressor.predict(d[atributos]) if regressor is not None else np.full(len(d), np.nan)
                prev = d[["order_id", "origem_dado", "delay_status", "delay_in_days"]].copy()
                prev["delay_status_source"] = d.get("delay_status_source", "nao_registrado")
                prev["cenario"], prev["modelo"], prev["particao"] = c["nome"], m["nome"], p
                prev["score_atraso"] = scores
                prev["previsao_delay_status"] = (scores >= limiar).astype(int)
                prev["previsao_delay_in_days"] = dias
                prev["erro_dias"] = dias - d.delay_in_days
                prev["limiar"] = limiar
                prev.to_csv(previsoes, index=False, mode="a", header=not previsoes.exists())
                for segmento in ["todos", "real_olist", "sintetico_ctgan"]:
                    mascara = np.ones(len(d), dtype=bool) if segmento == "todos" else d.origem_dado.eq(segmento).to_numpy()
                    if not mascara.any():
                        continue
                    met = avaliar(d.delay_status.to_numpy()[mascara], scores[mascara], d.delay_in_days.to_numpy()[mascara], dias[mascara],
                                  limiar, config.get("fracoes_fila", [0.1]))
                    met.update(cenario=c["nome"], modelo=m["nome"], particao=p, segmento=segmento,
                               execucao=pasta.name, segundos_treino=duracao,
                               entrada_dados=config.get("entrada", "Dados/dataset_ml.csv"),
                               pedidos_treino_regressao=int(dias_conhecidos.sum()),
                               rotulos_pln=int(d.get("delay_status_source", pd.Series("", index=d.index)).loc[mascara].eq("pln").sum()),
                               review_score_origem=config.get("review_score_origem"),
                               interpretacao="retrospectiva: status do pedido e avaliações globais do vendedor",
                               avaliacao_sintetica=bool(d.loc[mascara, "origem_dado"].eq("sintetico_ctgan").any()),
                               limiar_ajustado_com_sinteticos=bool(dados["validacao"].origem_dado.eq("sintetico_ctgan").any()))
                    metricas.append(met)
    resultado.parent.mkdir(parents=True, exist_ok=True)
    # Somente a rodada completa é publicada como CSV de desempenho.
    with resultado.open("x", encoding="utf-8", newline="") as arquivo:
        marcar_selecionados(pd.DataFrame(metricas)).to_csv(arquivo, index=False)
    salvar_json(pasta / "resultado.json", {"csv": str(resultado)})


def executar(config, pasta, etapa="tudo", destino=None):
    exigir_revisao(config)
    atributos_configurados(config)
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
    if etapa == "tudo" and (pasta / "preparacao.json").is_file():
        etapa = "treinar"
    executar(config, pasta, etapa)
    (pasta.parent / "ultima_execucao.txt").write_text(nome, encoding="utf-8")
    print("CSVs:", RAIZ / "Dados/comparacao_modelos" / nome)
    print("Modelos:", pasta)
    if etapa != "preparar":
        print("Métricas:", arquivo_resultados(config, nome))
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
    referencia = pasta / "resultado.json"
    csv = Path(json.loads(referencia.read_text(encoding="utf-8"))["csv"]) if referencia.exists() else arquivo_resultados({}, nome)
    metricas = pd.read_csv(csv)
    if "versao_dados" in metricas:
        print("Dados da execução:", ", ".join(metricas.versao_dados.dropna().unique()))
    resumo = metricas.loc[metricas.particao.eq("teste_real_referencia") & metricas.segmento.eq("todos")]
    print("Execução:", nome, "— desempenho no teste real comum")
    print(resumo[["cenario", "modelo", "f1", "precision", "recall", "accuracy", "mae_dias", "rmse_dias"]].to_string(index=False))
    print("Seleção feita na validação:")
    selecionados = metricas.loc[metricas.particao.eq("validacao") & metricas.segmento.eq("todos") & (
        metricas.melhor_classificador_validacao | metricas.melhor_regressor_validacao)]
    print(selecionados[["cenario", "modelo", "melhor_classificador_validacao", "melhor_regressor_validacao"]].to_string(index=False))
    print("Métricas completas:", csv)
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
