"""Métricas de classificação e dias de atraso; um CSV por execução."""
import math
import argparse
import json
import re
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix,
    mean_absolute_error, mean_squared_error, r2_score)

RAIZ = Path(__file__).resolve().parents[1]


def escolher_limiar(y, scores):
    """Maximiza F1 da classe atrasado (1); empate favorece o maior limiar."""
    if len(np.unique(y)) < 2:
        raise ValueError("Validação precisa das duas classes para escolher limiar por F1.")
    y, scores = np.asarray(y, dtype=int), np.asarray(scores, dtype=float)
    ordem = np.argsort(-scores, kind="stable")
    ordenados = scores[ordem]
    finais = np.r_[np.flatnonzero(np.diff(ordenados)), len(y) - 1]
    tp = np.r_[0, np.cumsum(y[ordem])[finais]]
    fp = np.r_[0, finais + 1] - tp
    fn = y.sum() - tp
    limiares = np.r_[np.nextafter(ordenados[0], np.inf), ordenados[finais]]
    f1 = 2 * tp / np.maximum(2 * tp + fp + fn, 1)
    return float(limiares[np.flatnonzero(np.isclose(f1, f1.max()))[0]])


def avaliar(y, scores, dias, previstos, limiar, fracoes=None):
    """F1/precision/recall referem-se ao atraso (1); dias ausentes não viram zero.

    ``fracoes`` é aceito apenas para compatibilidade com chamadas antigas.
    """
    y, scores, dias, previstos = map(np.asarray, (y, scores, dias, previstos))
    conhecidos = np.isfinite(dias)
    regressao = conhecidos & np.isfinite(previstos)
    d, pr = dias[regressao], previstos[regressao]
    atrasados = regressao & (y == 1)
    pred = scores >= limiar
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    resultado = {
        "pedidos": len(y), "limiar": limiar,
        "accuracy": accuracy_score(y, pred), "precision": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred, zero_division=0),
        "f1": f1_score(y, pred, pos_label=1, average="binary", zero_division=0),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        "pedidos_dias_conhecidos": int(conhecidos.sum()), "pedidos_dias_ausentes": int((~conhecidos).sum()),
        "pedidos_avaliados_regressao": int(regressao.sum()),
        "mae_dias": mean_absolute_error(d, pr) if len(d) else np.nan,
        "rmse_dias": math.sqrt(mean_squared_error(d, pr)) if len(d) else np.nan,
        "r2_dias": r2_score(d, pr) if len(d) > 1 and np.var(d) > 0 else np.nan,
        "mae_dias_atrasados": mean_absolute_error(dias[atrasados], previstos[atrasados]) if atrasados.any() else np.nan,
    }
    return resultado


def caminho(valor):
    p = Path(valor)
    return p if p.is_absolute() else RAIZ / p

def arquivo_resultados(config, nome):
    return caminho(config.get("saida_resultados", "Dados/resultados_modelos")) / f"{nome}.csv"

def metricas_f1(metricas):
    """Calcula F1 binário pela matriz; não renomeia valores macro/micro antigos."""
    metricas = metricas.drop(columns=["f1_macro", "f1_micro"], errors="ignore").copy()
    denominador = (2 * metricas.tp + metricas.fp + metricas.fn).replace(0, np.nan)
    metricas["f1"] = (2 * metricas.tp / denominador).fillna(0)
    return metricas


def marcar_selecionados(metricas):
    metricas = metricas_f1(metricas)
    metricas["melhor_classificador_validacao"] = False
    metricas["melhor_regressor_validacao"] = False
    for cenario in metricas.cenario.unique():
        mascara = metricas.cenario.eq(cenario)
        val = metricas.loc[mascara & metricas.particao.eq("validacao") & metricas.segmento.eq("todos")]
        if val.empty:
            continue
        cls = val.sort_values(["f1", "precision", "modelo"], ascending=[False, False, True]).iloc[0].modelo
        metricas.loc[mascara & metricas.modelo.eq(cls), "melhor_classificador_validacao"] = True
        reg = val.dropna(subset=["mae_dias"]).sort_values(["mae_dias", "modelo"])
        if len(reg):
            metricas.loc[mascara & metricas.modelo.eq(reg.iloc[0].modelo), "melhor_regressor_validacao"] = True
    return metricas

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
    metricas = metricas_f1(pd.read_csv(csv))
    if "versao_dados" in metricas:
        print("Dados da execução:", ", ".join(metricas.versao_dados.dropna().unique()))
    resumo = metricas.loc[metricas.particao.eq("teste_real_referencia") & metricas.segmento.eq("todos")]
    print("Execução:", nome, "— desempenho no teste real comum")
    colunas = [c for c in ["cenario", "modelo", "f1", "precision", "recall", "accuracy", "mae_dias", "rmse_dias"] if c in resumo]
    print(resumo[colunas].to_string(index=False))
    print("Seleção registrada na validação:")
    selecionados = metricas.loc[metricas.particao.eq("validacao") & metricas.segmento.eq("todos") & (
        metricas.melhor_classificador_validacao | metricas.melhor_regressor_validacao)]
    print(selecionados[["cenario", "modelo", "melhor_classificador_validacao", "melhor_regressor_validacao"]].to_string(index=False))
    print("Métricas completas:", csv)
    kfold = pasta / "kfold_resumo.csv"
    if kfold.exists():
        print("K-fold no treino real (média e desvio-padrão; limiar fixo):")
        resumo_kfold = pd.read_csv(kfold)
        if "f1_media" not in resumo_kfold:
            folds = metricas_f1(pd.read_csv(pasta / "kfold_metricas.csv"))
            f1 = folds.groupby("modelo").f1.agg(f1_media="mean", f1_desvio="std")
            resumo_kfold = resumo_kfold.merge(f1, on="modelo", validate="one_to_one")
        print(resumo_kfold[["modelo", "f1_media", "f1_desvio",
                            "mae_dias_media", "mae_dias_desvio"]].to_string(index=False))
        print("Métricas K-fold:", kfold)
    return resumo


def main():
    parser = argparse.ArgumentParser(description="Consultar o CSV de desempenho de uma execução concluída.")
    parser.add_argument("--nome", help="Nome da execução; omitido usa a última execução.")
    args = parser.parse_args()
    mostrar_resultados(args.nome)


if __name__ == "__main__":
    main()
