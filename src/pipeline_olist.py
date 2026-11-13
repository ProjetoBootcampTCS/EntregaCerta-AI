"""CLI incremental do contrato Olist vendedor único. Caminhos relativos à raiz."""
from __future__ import annotations

import argparse
import json
import math
import re
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from .contratos_olist import CLEAN_COLUMNS, CTGAN_FEATURES, ML_DATASET_COLUMNS, ML_FEATURES, VERSAO, montar_ml
from .dados_vendedor_unico import enriquecer, preparar_fontes
from .ml_vendedor_unico import avaliar_comparacao, treinar_comparacao
from .preparar_dados import RAIZ, exigir, hash_arquivos
from .simulacao_atrasos import SimuladorAtrasos
from .sintese_olist import ajustar_ctgan, gerar_pedidos, hash_tabela, qualidade_sintetica, treino_real
from .tratar_dados_ml import sha256

ETAPAS = ["audit", "clean-single-seller", "enrich", "ctgan-train", "ctgan-generate", "simulate", "ml-prepare", "ml-train", "evaluate"]


def json_seguro(obj):
    if isinstance(obj, dict):
        return {str(k): json_seguro(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_seguro(v) for v in obj]
    if isinstance(obj, (np.integer, np.floating)):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, Path):
        return str(obj)
    return obj


def salvar_json(caminho, valor):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(json_seguro(valor), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def carregar_config(caminho):
    config = json.loads(Path(caminho).read_text(encoding="utf-8"))
    exigir(bool(re.fullmatch(r"[A-Za-z0-9_-]+", config["run_id"])), "run_id inválido.")
    return config


def relatorio_filtro(auditoria):
    linhas = ["# Filtro de exatamente um vendedor", "", f"Pedidos brutos: {auditoria['pedidos_brutos']}; duplicados: {auditoria['pedidos_duplicados']}.", "",
              "| Sellers | Pedidos | % bruto | No prazo | Atrasados | Sem rótulo |", "|---|---:|---:|---:|---:|---:|"]
    for g in auditoria["sellers_brutos"]:
        linhas.append(f"| {g['sellers']} | {g['pedidos']} | {100*g['proporcao']:.4f}% | {g['no_prazo']} | {g['atrasos']} | {g['sem_rotulo']} |")
    linhas += ["", "| Split | Situação | Pedidos | % split original | No prazo | Atrasados | Prevalência |", "|---|---|---:|---:|---:|---:|---:|"]
    for g in auditoria["splits"]:
        taxa = f"{100*g['prevalencia']:.4f}%" if g["prevalencia"] is not None else "n/a"
        linhas.append(f"| {g['particao']} | {g['status']} | {g['pedidos']} | {100*g['proporcao_split_original']:.4f}% | {g['no_prazo']} | {g['atrasos']} | {taxa} |")
    linhas += ["", f"Pedidos multi-item com um seller na fonte: {auditoria['multi_itens_single_seller_bruto']}.",
               f"Entregas no mesmo dia cuja definição difere do legado: {auditoria['rotulos_diferentes_do_calendario']}.",
               "Rótulo deste relatório: entrega ao cliente > promessa, comparando timestamps; nenhum rótulo simulado.",
               "Cortes temporais preservados, com purga por disponibilidade do rótulo. Ver auditoria.json para exclusões sequenciais, hashes e comparação com legado.",
               "A base é retrospectiva de entregues; a purga pode reduzir representação de entregas demoradas."]
    return "\n".join(linhas) + "\n"


def preparar_execucao(config):
    pasta = RAIZ / config["paths"]["artifacts_dir"] / config["run_id"]
    for nome in ["datasets", "staging", "ctgan", "models", "reports", "eda"]:
        (pasta / nome).mkdir(parents=True, exist_ok=True)
    manifesto = pasta / "manifesto.json"
    fontes = hash_arquivos(RAIZ / config["paths"]["raw_dir"])
    exigir(len(fontes) >= 7, "Fontes Olist ausentes; nenhuma fonte será fabricada.")
    if manifesto.exists():
        anterior = json.loads(manifesto.read_text(encoding="utf-8"))
        exigir(anterior["config"] == config, "Config alterada: escolha outro run_id para preservar a execução.")
        exigir(anterior["hashes_fontes"] == fontes, "Fontes alteradas: escolha outro run_id.")
    else:
        salvar_json(manifesto, {"contrato": VERSAO, "config": config, "hashes_fontes": fontes,
            "hashes_codigo": {p.name: sha256(p) for p in (RAIZ / "src").glob("*.py")},
            "versoes": {p: version(p) for p in ["numpy", "pandas", "scikit-learn", "joblib", "pyarrow"]}})
    return pasta


def executar_etapa(config, etapa, pasta):
    dados, reports = pasta / "datasets", pasta / "reports"
    a = dados / "pedidos_ml_limpo_enriquecido.parquet"
    c = dados / "pedidos_sinteticos.parquet"
    d = dados / "pedidos_ml_filtrado.parquet"
    raw = RAIZ / config["paths"]["raw_dir"]
    if etapa in ["audit", "clean-single-seller", "enrich"]:
        fontes, auditoria = preparar_fontes(raw, config["split"]["validation"], config["split"]["test"],
                                           RAIZ / config["paths"]["legacy_ml"])
        salvar_json(reports / "auditoria.json", auditoria)
        (reports / "filtro_um_vendedor.md").write_text(relatorio_filtro(auditoria), encoding="utf-8")
        if etapa != "audit":
            fontes["filtrado"].to_parquet(pasta / "staging" / "pedidos_um_vendedor.parquet", index=False)
        if etapa == "enrich":
            base, tratamento = enriquecer(fontes, raw)
            base.to_parquet(a, index=False)
            salvar_json(reports / "tratamento_historico.json", tratamento)
            exigir(auditoria["hashes_fontes"] == hash_arquivos(raw), "Fontes mudaram durante enriquecimento.")
            print(f"A: {base.shape}; splits {base.particao.value_counts().to_dict()}", flush=True)
    elif etapa == "ctgan-train":
        exigir(not (reports / "avaliacao_final.json").exists(), "Execução já avaliada: use outro run_id para treinar novamente.")
        treino = treino_real(pd.read_parquet(a))
        pacote, b = ajustar_ctgan(treino, config["ctgan"])
        joblib.dump(pacote, pasta / "ctgan" / "gerador.joblib", compress=3)
        b.to_parquet(dados / "ctgan_treino_features.parquet", index=False)
        salvar_json(reports / "ctgan_fit.json", {k: v for k, v in pacote.items() if k not in ["modelo", "treino"]})
    elif etapa == "ctgan-generate":
        pacote = joblib.load(pasta / "ctgan" / "gerador.joblib")
        exigir(hash_tabela(treino_real(pd.read_parquet(a))) == pacote["hash_treino"], "A não corresponde ao treino do gerador.")
        try:
            candidatos, relatorio = gerar_pedidos(pacote, config["synthetic"]["num_samples"], config["run_id"], config["synthetic"])
        except RuntimeError as erro:
            if hasattr(erro, "relatorio"):
                salvar_json(reports / "falha_amostragem.json", erro.relatorio)
            raise
        candidatos.to_parquet(pasta / "staging" / "candidatos_sinteticos.parquet", index=False)
        salvar_json(reports / "geracao.json", relatorio)
        salvar_json(reports / "qualidade_sintetica.json", qualidade_sintetica(pacote["treino"], candidatos, config["synthetic"]["seed"]))
    elif etapa == "simulate":
        treino = treino_real(pd.read_parquet(a))
        candidatos = pd.read_parquet(pasta / "staging" / "candidatos_sinteticos.parquet")
        simulador = SimuladorAtrasos(config["simulation"]).fit(treino)
        sinteticos, detalhes, relatorio = simulador.simular(candidatos)
        sinteticos.to_parquet(c, index=False)
        detalhes.to_parquet(reports / "probabilidades_simuladas.parquet", index=False)
        salvar_json(reports / "simulacao.json", relatorio)
        joblib.dump(simulador, pasta / "ctgan" / "simulador.joblib")
    elif etapa == "ml-prepare":
        montar_ml(pd.read_parquet(a), pd.read_parquet(c)).to_parquet(d, index=False)
        salvar_json(reports / "contratos.json", {"A": CLEAN_COLUMNS, "B": CTGAN_FEATURES, "C": CLEAN_COLUMNS,
                                                 "D": ML_DATASET_COLUMNS, "X": ML_FEATURES})
    elif etapa == "ml-train":
        exigir(not (reports / "avaliacao_final.json").exists(), "Execução já avaliada: use outro run_id para treinar novamente.")
        pacote = treinar_comparacao(pd.read_parquet(d), config["ml"])
        joblib.dump(pacote, pasta / "models" / "comparacao.joblib", compress=3)
        pacote["validacao"].to_csv(reports / "metricas_validacao.csv", index=False)
        for nome in ["baseline_real", pacote["selecionado_aumentado"]]:
            joblib.dump(pacote["modelos"][nome], pasta / "models" / f"{nome}.joblib", compress=3)
        salvar_json(reports / "selecao.json", {"aumentado": pacote["selecionado_aumentado"], "metrica": "average_precision",
                                               "limiar": "F1 na validação real", "hash_dataset_ml": pacote["hash_dataset_ml"]})
    elif etapa == "evaluate":
        pacote = joblib.load(pasta / "models" / "comparacao.joblib")
        base = pd.read_parquet(d)
        # Reexecução só relê o resultado final, evitando retunar com o teste.
        registro = reports / "avaliacao_final.json"
        if registro.exists():
            anterior = json.loads(registro.read_text(encoding="utf-8"))
            exigir(anterior["hash_modelos"] == sha256(pasta / "models" / "comparacao.joblib")
                   and anterior["hash_dataset"] == hash_tabela(base), "Avaliação final já existe para outro modelo/dataset.")
            print(pd.read_csv(reports / "metricas_teste.csv").to_string(index=False), flush=True)
        else:
            tabela = avaliar_comparacao(base, pacote)
            tabela.to_csv(reports / "metricas_teste.csv", index=False)
            delta = float(tabela.average_precision.iloc[1] - tabela.average_precision.iloc[0])
            salvar_json(registro, {"hash_modelos": sha256(pasta / "models" / "comparacao.joblib"),
                                   "hash_dataset": hash_tabela(base), "delta_average_precision": delta,
                                   "resultado": "melhora" if delta > 0 else "piora" if delta < 0 else "empate",
                                   "ressalva": "Uma comparação temporal. Rótulos sintéticos hipotéticos não provam causalidade nem ganho em produção."})
            print(tabela.to_string(index=False), flush=True)
    elif etapa == "eda":
        executar_eda(pd.read_parquet(a), pd.read_parquet(c) if c.exists() else None, pasta / "eda")
    else:
        raise ValueError(f"Etapa desconhecida: {etapa}")


def executar_eda(real, sintetico, saida):
    """Leitura apenas dos contratos já limpos; não refaz transformações."""
    from .sintese_olist import estratos

    partes = [real] + ([sintetico] if sintetico is not None else [])
    base = pd.concat(partes, ignore_index=True)
    base.assign(itens=estratos(base)).groupby(["origem_dado", "particao", "itens"]).agg(
        pedidos=("order_id", "size"), atrasos=("atrasou", "sum"), taxa=("atrasou", "mean")).to_csv(saida / "itens.csv")
    for coluna in ["distancia_vendedor_cliente_km", "peso_total_g", "valor_frete", "nota_historica_vendedor_media"]:
        base.assign(faixa=pd.qcut(base[coluna], 10, duplicates="drop")).groupby(
            ["origem_dado", "particao", "faixa"], observed=True).agg(
            pedidos=("order_id", "size"), taxa=("atrasou", "mean")).to_csv(saida / f"faixas_{coluna}.csv")
    (saida / "LEIA-ME.txt").write_text("EDA descritiva posterior; sintéticos têm rótulos hipotéticos. Reviews são proxy da experiência do pedido. Não usar o teste para retunar cenários.\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=RAIZ / "config" / "olist_ctgan.json")
    parser.add_argument("--step", choices=[*ETAPAS, "all", "eda"], required=True)
    args = parser.parse_args()
    config = carregar_config(args.config)
    pasta = preparar_execucao(config)
    etapas = ETAPAS if args.step == "all" else [args.step]
    with threadpool_limits(limits=config["ctgan"].get("threads", 4)):
        for etapa in etapas:
            print(f"[{etapa}] {config['run_id']}", flush=True)
            executar_etapa(config, etapa, pasta)
            registro = pasta / "reports" / "etapas.json"
            historico = json.loads(registro.read_text(encoding="utf-8")) if registro.exists() else {}
            historico[etapa] = {"concluida": True, "hashes_codigo": {
                p.name: sha256(p) for p in (RAIZ / "src").glob("*.py")}}
            salvar_json(registro, historico)
            print(f"[{etapa}] concluído", flush=True)
    print(f"Artefatos: {pasta}", flush=True)


if __name__ == "__main__":
    main()
