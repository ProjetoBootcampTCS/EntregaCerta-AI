from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import re, unicodedata

def remover_acentos_mantendo_simbolos(texto): return unicodedata.normalize("NFC", re.sub(r"[\u0300-\u036f]", "", unicodedata.normalize("NFD", texto))) if isinstance(texto, str) else texto


RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)
print(Path.cwd())
csv_path = Path("./Dados/Brazilian Logistic") / "olist_order_reviews_dataset.csv"
df = pd.read_csv(csv_path, usecols=["review_comment_title", "review_comment_message"])

# Remove linhas apenas quando título e mensagem estão ambos nulos.
df = df.dropna(subset=["review_comment_title", "review_comment_message"], how="all").copy()
df["comentario"] = df[["review_comment_title", "review_comment_message"]].fillna("").agg(" ".join, axis=1).str.lower().str.strip()
df["comentario"] = df["comentario"].apply(remover_acentos_mantendo_simbolos)
df = df[df["comentario"].str.len() > 0]

parametros_atraso = [
    "nao chegou",
    "nao recebi",
    "ainda nao recebi",
    "nao foi entregue",
    "nao entregaram",
    "chegou atrasado",
    "chegou com atraso",
    "entrega atrasada",
    "entrega demorou",
    "atraso na entrega",
    "demora na entrega",
    "passou do prazo"
]

parametros_no_prazo = [
    "chegou no prazo",
    "entregue no prazo",
    "entrega no prazo",
    "dentro do prazo",
    "chegou antes do prazo",
    "entregue antes do prazo",
    "nao passou do prazo"
]

tem_atraso = df["comentario"].apply(lambda texto: any(frase in texto for frase in parametros_atraso))
tem_no_prazo = df["comentario"].apply(lambda texto: any(frase in texto for frase in parametros_no_prazo))

df["classificacao"] = np.select([tem_atraso, tem_no_prazo], ["atrasado", "no prazo"], default="nao consta")
df = df[df["classificacao"] != "nao consta"].copy()

X = df["comentario"]
y = df["classificacao"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=RANDOM_STATE, stratify=y)

modelo = Pipeline([
    ("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2, max_features=30000, sublinear_tf=True)),
    ("classificador", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)),
])

modelo.fit(X_train, y_train)
y_pred = modelo.predict(X_test)

print(f"Acurácia: {accuracy_score(y_test, y_pred):.3f}")
print("\nRelatório de classificação:")
print(classification_report(y_test, y_pred, zero_division=0))
print("Matriz de confusão:")
print(confusion_matrix(y_test, y_pred, labels=["atrasado", "no prazo"]))

novos_comentarios = [
    "nao recebi meu pedido e ja passou do prazo",
    "o produto chegou no prazo",
    "produto muito bom",
]

previsoes = modelo.predict(novos_comentarios)

for comentario, classificacao in zip(novos_comentarios, previsoes):
    print(f"Comentário: {comentario}")
    print(f"Classificação: {classificacao}")
    print("-" * 50)