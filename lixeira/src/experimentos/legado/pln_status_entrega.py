"""PLN original reutilizável: TF-IDF + regressão logística, sem treino ao importar."""
import json
import re
import unicodedata
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

RANDOM_STATE = 42
parametros_atraso = [
    "nao chegou", "nao recebi", "ainda nao recebi", "nao foi entregue", "nao entregaram",
    "chegou atrasado", "chegou com atraso", "entrega atrasada", "entrega demorou",
    "atraso na entrega", "demora na entrega", "passou do prazo",
]
parametros_no_prazo = [
    "chegou no prazo", "entregue no prazo", "entrega no prazo", "dentro do prazo",
    "chegou antes do prazo", "entregue antes do prazo", "nao passou do prazo",
]


def remover_acentos_mantendo_simbolos(texto):
    return unicodedata.normalize("NFC", re.sub(r"[\u0300-\u036f]", "", unicodedata.normalize("NFD", texto)))


def texto_celula(valor):
    if pd.isna(valor):
        return ""
    valor = str(valor)
    if valor.startswith("["):
        try:
            lista = json.loads(valor)
            if isinstance(lista, list):
                return " ".join(str(v) for v in lista if v is not None)
        except json.JSONDecodeError:
            pass
    return valor


def comentarios(base):
    textos = base[["review_comment_title", "review_comment_message"]].apply(
        lambda coluna: coluna.map(texto_celula)).agg(" ".join, axis=1)
    return textos.str.lower().str.strip().map(remover_acentos_mantendo_simbolos)


def rotular_texto(texto):
    # Evita que a expressão positiva seja encontrada dentro da sua negação.
    sem_negacao = texto.replace("nao passou do prazo", "")
    if any(frase in sem_negacao for frase in parametros_atraso):
        return "atrasado"
    if any(frase in texto for frase in parametros_no_prazo):
        return "no prazo"
    return "nao consta"


def treinar_pln(avaliacoes, semente=RANDOM_STATE):
    x = comentarios(avaliacoes)
    y = x.map(rotular_texto)
    selecionadas = y.ne("nao consta")
    x, y = x[selecionadas], y[selecionadas]
    if y.nunique() != 2 or y.value_counts().min() < 2:
        raise ValueError("PLN precisa de exemplos das duas classes com as expressões do legado.")
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=.2, random_state=semente, stratify=y)
    modelo = Pipeline([
        ("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2,
                                  max_features=30000, sublinear_tf=True)),
        ("classificador", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=semente)),
    ])
    modelo.fit(x_train, y_train)
    previsto = modelo.predict(x_test)
    return modelo, {
        "origem_rotulos": "expressoes_do_legado; avaliação de pseudorrótulos, não de entregas observadas",
        "exemplos_treino": len(x_train), "exemplos_teste": len(x_test),
        "accuracy": accuracy_score(y_test, previsto),
        "relatorio": classification_report(y_test, previsto, output_dict=True, zero_division=0),
        "matriz_confusao": confusion_matrix(y_test, previsto, labels=["atrasado", "no prazo"]).tolist(),
    }


if __name__ == "__main__":
    from src.dados.esquema import RAIZ
    _, relatorio = treinar_pln(pd.read_csv(RAIZ / "Dados/Brazilian Logistic/olist_order_reviews_dataset.csv"))
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
