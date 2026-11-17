"""Etapa 2: CTGAN, cenários, treino automatizado e CSV único de avaliação."""
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
from sklearn.decomposition import PCA
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

from importlib import import_module

# Os scripts numerados funcionam também quando executados fora da raiz do projeto.
sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

_dados = import_module("src.2_dados_treino")
ATRIBUTOS, CATEGORICAS, sha256 = _dados.ATRIBUTOS, _dados.CATEGORICAS, _dados.sha256
carregar, exigir_revisao, atributos_configurados = _dados.carregar, _dados.exigir_revisao, _dados.atributos_configurados
_modelos = import_module("src.2_catalogo_modelos")
CATALOGO, criar_modelos = _modelos.CATALOGO, _modelos.criar_modelos
_metricas = import_module("src.3_avaliar_modelos")
avaliar, escolher_limiar = _metricas.avaliar, _metricas.escolher_limiar
arquivo_resultados, marcar_selecionados = _metricas.arquivo_resultados, _metricas.marcar_selecionados
sinteticos = import_module("src.2_ctgan")


PARTICOES = ("treino", "validacao", "teste")


def caminho(valor):
    p = Path(valor)
    return p if p.is_absolute() else RAIZ / p


def salvar_json(destino, valor):
    destino.write_text(json.dumps(valor, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def validar_config(config):
    pca = config.get("pca", {})
    if pca.get("ativado", False):
        variancia = pca.get("variancia", .95)
        if type(variancia) not in (int, float) or not 0 < variancia < 1:
            raise ValueError("pca.variancia deve estar entre 0 e 1, exclusivamente.")
    kfold = config.get("kfold", {})
    if kfold.get("ativado", False):
        if type(kfold.get("n_splits", 5)) is not int or kfold.get("n_splits", 5) < 2:
            raise ValueError("kfold.n_splits deve ser um inteiro >= 2.")
        limiar_cv = kfold.get("limiar", .5)
        if type(limiar_cv) not in (int, float) or not 0 <= limiar_cv <= 1:
            raise ValueError("kfold.limiar deve estar entre 0 e 1.")
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


def pipeline_modelo(atributos, modelo, config):
    etapas = [("preprocessador", preprocessador(atributos))]
    if config.get("pca", {}).get("ativado", False):
        etapas.append(("pca", PCA(n_components=config["pca"].get("variancia", .95), svd_solver="full")))
    return Pipeline([*etapas, ("modelo", modelo)])


def informacoes_pca(classificador, regressor):
    resultado = {"pca_ativado": "pca" in classificador.named_steps}
    for nome, modelo in [("classificacao", classificador), ("regressao", regressor)]:
        pca = modelo.named_steps.get("pca") if modelo is not None else None
        resultado[f"pca_componentes_{nome}"] = int(pca.n_components_) if pca is not None else None
        resultado[f"pca_variancia_{nome}"] = float(pca.explained_variance_ratio_.sum()) if pca is not None else None
    return resultado


def validar_cruzado(config, pasta, reais, atributos):
    """Diagnóstico dos modelos em folds reais; nunca usa validação, teste ou CTGAN.

    O limiar é fixo (padrão 0.5), sem otimização sobre o fold avaliado.
    Encoder, scaler e PCA novos são ajustados apenas nos dados de cada treino.
    """
    if not reais.particao.eq("treino").all() or not reais.origem_dado.eq("real_olist").all():
        raise ValueError("K-fold aceita exclusivamente a partição de treino real.")
    reais = _dados.validar_tabela(reais.copy(), atributos)
    categorias = [c for c in atributos if c in CATEGORICAS]
    reais[categorias] = reais[categorias].astype(object)
    opcoes = config["kfold"]
    n = opcoes.get("n_splits", 5)
    if set(reais.delay_status.unique()) != {0, 1} or reais.delay_status.value_counts().min() < n:
        raise ValueError(f"K-fold exige pelo menos {n} pedidos de cada classe no treino real.")
    semente = config.get("semente", 42)
    folds = list(StratifiedKFold(n_splits=n, shuffle=True, random_state=semente).split(reais, reais.delay_status))
    atribuicoes = reais[["order_id"]].copy()
    atribuicoes["fold_validacao"] = 0
    for fold, (_, iv) in enumerate(folds, 1):
        atribuicoes.iloc[iv, atribuicoes.columns.get_loc("fold_validacao")] = fold
    atribuicoes.to_csv(pasta / "kfold_particoes.csv", index=False)
    metricas = []
    limiar = opcoes.get("limiar", .5)
    print(f"K-fold: {n} folds estratificados exclusivamente no treino real; limiar fixo {limiar}.", flush=True)
    for m in config["modelos"]:
        for fold, (it, iv) in enumerate(folds, 1):
            inicio = time.perf_counter()
            t, v = reais.iloc[it], reais.iloc[iv]
            cls, reg = criar_modelos(m, semente)
            classificador = pipeline_modelo(atributos, cls, config)
            regressor = pipeline_modelo(atributos, reg, config)
            conhecidos = t.delay_in_days.notna()
            with threadpool_limits(limits=config.get("threads", 2)):
                classificador.fit(t[atributos], t.delay_status)
                scores = classificador.predict_proba(v[atributos])[:, list(classificador.classes_).index(1)]
                if conhecidos.any():
                    regressor.fit(t.loc[conhecidos, atributos], t.loc[conhecidos, "delay_in_days"])
                    dias = regressor.predict(v[atributos])
                else:
                    regressor = None
                    dias = np.full(len(v), np.nan)
            met = avaliar(v.delay_status, scores, v.delay_in_days, dias, limiar)
            met.update(modelo=m["nome"], fold=fold, pedidos_treino=len(t),
                       pedidos_treino_regressao=int(conhecidos.sum()),
                       segundos=time.perf_counter() - inicio, **informacoes_pca(classificador, regressor))
            metricas.append(met)
            print(f"  {m['nome']} fold {fold}/{n}: F1={met['f1']:.4f}; MAE={met['mae_dias']:.4f} dias", flush=True)
    metricas = pd.DataFrame(metricas)
    metricas.to_csv(pasta / "kfold_metricas.csv", index=False)
    medidas = ["f1", "precision", "recall", "accuracy", "mae_dias", "rmse_dias"]
    resumo = metricas.groupby("modelo")[medidas].agg(["mean", "std"])
    resumo.columns = [f"{metrica}_{'media' if estatistica == 'mean' else 'desvio'}" for metrica, estatistica in resumo.columns]
    resumo = resumo.reset_index()
    resumo.to_csv(pasta / "kfold_resumo.csv", index=False)
    print("K-fold no treino real (média e desvio-padrão):", flush=True)
    print(resumo[["modelo", "f1_media", "f1_desvio", "mae_dias_media", "mae_dias_desvio"]].to_string(index=False), flush=True)
    return metricas, resumo


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
    if config.get("kfold", {}).get("ativado", False):
        validar_cruzado(config, pasta, pd.read_csv(destino / "reais_treino.csv", low_memory=False), atributos)
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
            classificador = pipeline_modelo(atributos, cls, config)
            regressor = pipeline_modelo(atributos, reg, config)
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
                                  limiar)
                    met.update(cenario=c["nome"], modelo=m["nome"], particao=p, segmento=segmento,
                               execucao=pasta.name, segundos_treino=duracao,
                               criterio_selecao="f1_validacao",
                               entrada_dados=config.get("entrada", "Dados/dataset_ml.csv"),
                               pedidos_treino_regressao=int(dias_conhecidos.sum()),
                               rotulos_pln=int(d.get("delay_status_source", pd.Series("", index=d.index)).loc[mascara].eq("pln").sum()),
                               review_score_origem=config.get("review_score_origem"),
                               interpretacao="retrospectiva: status do pedido e avaliações globais do vendedor",
                               avaliacao_sintetica=bool(d.loc[mascara, "origem_dado"].eq("sintetico_ctgan").any()),
                               limiar_ajustado_com_sinteticos=bool(dados["validacao"].origem_dado.eq("sintetico_ctgan").any()))
                    met.update(informacoes_pca(classificador, regressor))
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
                     "codigo_sha256": {str(p.relative_to(RAIZ)): sha256(p) for p in (RAIZ / "src").glob("[123]_*.py")},
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
    config_path = caminho(config_path or "src/configuracoes/2_treinamento.json")
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



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=RAIZ / "src/configuracoes/2_treinamento.json")
    parser.add_argument("--nome", help="Nome da execução; obrigatório para retomar com --etapa treinar.")
    parser.add_argument("--etapa", choices=["preparar", "treinar", "tudo"], default="tudo")
    args = parser.parse_args()
    if args.etapa == "treinar" and args.nome is None:
        parser.error("--etapa treinar exige --nome da preparação anterior")
    executar_configuracao(args.config, args.nome, args.etapa)


if __name__ == "__main__":
    main()
