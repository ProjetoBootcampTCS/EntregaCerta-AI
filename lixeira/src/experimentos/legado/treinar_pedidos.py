"""Treina HistGradientBoosting para atraso (classificação e regressão).

Na raiz do projeto: python treinar_pedidos.py
Ou: python treinar_pedidos.py caminho/pedidos_ml.csv --saida resultados_hgb
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
    mean_absolute_error, mean_squared_error, precision_score, r2_score,
    recall_score, PrecisionRecallDisplay)
from sklearn.model_selection import StratifiedKFold, KFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


def preparar(df):
    df = df.copy()
    dt = pd.to_datetime(df["order_approved_at"], errors="coerce")
    df["ano_aprovacao"], df["mes_aprovacao"] = dt.dt.year, dt.dt.month
    df["dia_semana_aprovacao"], df["hora_aprovacao"] = dt.dt.day_of_week, dt.dt.hour
    return df.drop(columns=[c for c in ("order_id", "customer_unique_id", "particao",
        "rotulo_disponivel_em", "order_approved_at", "atrasou", "dias_atraso") if c in df])


def criar_pipeline(X, modelo):
    numericas = X.select_dtypes(include=np.number).columns
    categoricas = X.select_dtypes(exclude=np.number).columns
    pre = ColumnTransformer([
        ("num", SimpleImputer(strategy="median", add_indicator=True), numericas),
        ("cat", Pipeline([("imputar", SimpleImputer(strategy="most_frequent")),
                          ("codificar", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), categoricas),
    ])
    return Pipeline([("pre", pre), ("modelo", modelo)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", type=Path, default=Path("Dados/pedidos_ml.csv"))
    parser.add_argument("--saida", type=Path, default=Path("Modelos/legado_hgb"))
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)

    print(f"Lendo dados: {args.csv}", flush=True)
    df = pd.read_csv(args.csv)
    treino, validacao, teste = (df[df.particao == p].copy() for p in ("treino", "validacao", "teste"))
    print(f"Partições: treino={len(treino):,}, validação={len(validacao):,}, teste={len(teste):,}".replace(",", "."), flush=True)
    X = preparar(treino)
    X_val, X_test = preparar(validacao), preparar(teste)
    X_final = pd.concat([X, X_val], ignore_index=True)
    resultados = []

    # Classificação: estratifica os folds e reporta o efeito dos falsos positivos/negativos.
    y = treino.atrasou.astype(int)
    clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=50, l2_regularization=5.0, class_weight="balanced", random_state=42)
    print(f"Validação cruzada de classificação ({args.folds} folds)...", flush=True)
    cv = cross_validate(criar_pipeline(X, clf), X, y,
        cv=StratifiedKFold(args.folds, shuffle=True, random_state=42),
        scoring={"accuracy":"accuracy", "f1_macro":"f1_macro", "f1_weighted":"f1_weighted"})
    for m in ("accuracy", "f1_macro", "f1_weighted"):
        resultados.append({"tarefa":"classificacao", "origem":"cv", "metrica":m,
                           "media":cv[f"test_{m}"].mean(), "desvio":cv[f"test_{m}"].std(ddof=1)})
    class_model = criar_pipeline(X_final, clf).fit(X_final, pd.concat([y, validacao.atrasou.astype(int)], ignore_index=True))
    print("Avaliando classificação no teste...", flush=True)
    y_test = teste.atrasou.astype(int)
    pred = class_model.predict(X_test)
    for m, value in {"accuracy":accuracy_score(y_test, pred),
        "precision_pos":precision_score(y_test, pred, zero_division=0),
        "recall_pos":recall_score(y_test, pred, zero_division=0),
        "f1_macro":f1_score(y_test, pred, average="macro", zero_division=0),
        "f1_weighted":f1_score(y_test, pred, average="weighted", zero_division=0)}.items():
        resultados.append({"tarefa":"classificacao", "origem":"teste", "metrica":m, "valor":value})
    cm = confusion_matrix(y_test, pred, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(5, 4)); ax.imshow(cm, cmap="Blues")
    ax.set(xticks=[0,1], yticks=[0,1], xticklabels=["No prazo", "Atrasou"],
           yticklabels=["No prazo", "Atrasou"], xlabel="Previsto", ylabel="Real", title="Matriz de confusão — teste")
    for (i,j), n in np.ndenumerate(cm): ax.text(j, i, str(n), ha="center", va="center")
    fig.tight_layout(); fig.savefig(args.saida / "classificacao_erros.png", dpi=150); plt.close(fig)
    if len(class_model.classes_) == 2:
        pos = list(class_model.classes_).index(1)
        PrecisionRecallDisplay.from_predictions(y_test, class_model.predict_proba(X_test)[:, pos])
        plt.title("Precision-Recall — teste"); plt.tight_layout(); plt.savefig(args.saida / "precision_recall.png", dpi=150); plt.close()

    # Regressão: métricas na escala de dias e diagnóstico dos resíduos no conjunto de teste.
    yr = treino.dias_atraso.astype(float)
    reg = HistGradientBoostingRegressor(max_iter=120, learning_rate=0.08, max_leaf_nodes=31, l2_regularization=1.0, random_state=42)
    print(f"Validação cruzada de regressão ({args.folds} folds)...", flush=True)
    cv = cross_validate(criar_pipeline(X, reg), X, yr,
        cv=KFold(args.folds, shuffle=True, random_state=42),
        scoring={"mae":"neg_mean_absolute_error", "mse":"neg_mean_squared_error", "r2":"r2"})
    for m in ("mae", "mse", "r2"):
        scores = -cv[f"test_{m}"] if m in ("mae", "mse") else cv[f"test_{m}"]
        resultados.append({"tarefa":"regressao", "origem":"cv", "metrica":m,
                           "media":scores.mean(), "desvio":scores.std(ddof=1)})
    reg_model = criar_pipeline(X_final, reg).fit(X_final, pd.concat([yr, validacao.dias_atraso.astype(float)], ignore_index=True))
    print("Avaliando regressão no teste e gerando gráficos...", flush=True)
    y_real = teste.dias_atraso.astype(float).to_numpy()
    y_pred = reg_model.predict(X_test)
    mse = mean_squared_error(y_real, y_pred)
    for m, value in {"mae":mean_absolute_error(y_real, y_pred), "mse":mse,
                     "rmse":np.sqrt(mse), "r2":r2_score(y_real, y_pred)}.items():
        resultados.append({"tarefa":"regressao", "origem":"teste", "metrica":m, "valor":value})
    residuo = y_real - y_pred
    fig, ax = plt.subplots(1, 3, figsize=(14, 4))
    ax[0].scatter(y_real, y_pred, alpha=.25); lim=max(y_real.max(), y_pred.max()); ax[0].plot([0,lim],[0,lim],"r--"); ax[0].set(title="Real × previsto", xlabel="Real (dias)", ylabel="Previsto (dias)")
    ax[1].scatter(y_pred, residuo, alpha=.25); ax[1].axhline(0,color="r",ls="--"); ax[1].set(title="Resíduos × previsto", xlabel="Previsto (dias)", ylabel="Resíduo (dias)")
    ax[2].hist(residuo, bins=35); ax[2].axvline(0,color="r",ls="--"); ax[2].set(title="Distribuição dos resíduos", xlabel="Resíduo (dias)", ylabel="Contagem")
    fig.tight_layout(); fig.savefig(args.saida / "regressao_erros.png", dpi=150); plt.close(fig)

    pd.DataFrame(resultados).to_csv(args.saida / "metricas.csv", index=False)
    print(pd.DataFrame(resultados).to_string(index=False))
    print(f"\nGráficos e métricas salvos em: {args.saida.resolve()}")


if __name__ == "__main__":
    main()
