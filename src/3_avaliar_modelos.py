"""Métricas de classificação, duração do atraso e capacidade de atendimento."""
import math
import argparse
import json
import re
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, average_precision_score, roc_auc_score, brier_score_loss,
    mean_absolute_error, mean_squared_error, r2_score, precision_recall_curve)

RAIZ = Path(__file__).resolve().parents[1]


def escolher_limiar(y, scores):
    """Ajustado na validação; empate favorece o maior limiar."""
    if len(np.unique(y)) < 2:
        raise ValueError("Validação precisa das duas classes para escolher limiar por F1.")
    precision, recall, limiares = precision_recall_curve(y, scores)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-15)
    return float(limiares[np.flatnonzero(np.isclose(f1, f1.max()))[-1]])


def avaliar(y, scores, dias, previstos, limiar, fracoes):
    y, scores, dias, previstos = map(np.asarray, (y, scores, dias, previstos))
    conhecidos = np.isfinite(dias)
    regressao = conhecidos & np.isfinite(previstos)
    d, pr = dias[regressao], previstos[regressao]
    atrasados = regressao & (y == 1)
    dias_positivos = np.where(conhecidos, np.maximum(dias, 0), np.nan)
    pred = scores >= limiar
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    ambos = len(np.unique(y)) == 2
    resultado = {
        "pedidos": len(y), "taxa_atraso": float(y.mean()), "limiar": limiar,
        "accuracy": accuracy_score(y, pred), "precision": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred, zero_division=0), "f1": f1_score(y, pred, zero_division=0),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        "average_precision": average_precision_score(y, scores) if ambos else np.nan,
        "roc_auc": roc_auc_score(y, scores) if ambos else np.nan,
        "brier": brier_score_loss(y, scores),
        "pedidos_dias_conhecidos": int(conhecidos.sum()), "pedidos_dias_ausentes": int((~conhecidos).sum()),
        "pedidos_avaliados_regressao": int(regressao.sum()),
        "mae_dias": mean_absolute_error(d, pr) if len(d) else np.nan,
        "rmse_dias": math.sqrt(mean_squared_error(d, pr)) if len(d) else np.nan,
        "r2_dias": r2_score(d, pr) if len(d) > 1 and np.var(d) > 0 else np.nan,
        "mae_dias_atrasados": mean_absolute_error(dias[atrasados], previstos[atrasados]) if atrasados.any() else np.nan,
        "vies_dias": float(np.mean(pr - d)) if len(d) else np.nan,
        "acerto_tolerancia_1_dia": float(np.mean(np.abs(pr - d) <= 1)) if len(d) else np.nan,
        "dias_atraso_total": float(np.nansum(dias_positivos)) if conhecidos.any() else np.nan,
        "saldo_dias_total": float(np.nansum(dias)) if conhecidos.any() else np.nan,
    }
    for fracao in fracoes:
        k = max(1, math.ceil(len(y) * fracao))
        fila = np.argsort(-scores, kind="stable")[:k]
        prefixo = f"fila_{fracao:g}"
        resultado.update({
            prefixo + "_pedidos": k,
            prefixo + "_atrasos_encontrados": int(y[fila].sum()),
            prefixo + "_precision": float(y[fila].mean()),
            prefixo + "_recall": float(y[fila].sum() / y.sum()) if y.sum() else np.nan,
            prefixo + "_dias_ausentes": int((~conhecidos[fila]).sum()),
            prefixo + "_dias_capturados": float(np.nansum(dias_positivos[fila])) if conhecidos[fila].any() else np.nan,
            prefixo + "_fracao_dias": float(np.nansum(dias_positivos[fila]) / np.nansum(dias_positivos)) if np.nansum(dias_positivos) else np.nan,
        })
    return resultado


def caminho(valor):
    p = Path(valor)
    return p if p.is_absolute() else RAIZ / p

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
    parser = argparse.ArgumentParser(description="Consultar o CSV de desempenho de uma execução concluída.")
    parser.add_argument("--nome", help="Nome da execução; omitido usa a última execução.")
    args = parser.parse_args()
    mostrar_resultados(args.nome)


if __name__ == "__main__":
    main()
