"""Catálogo extensível: cada família tem classificador e regressor de dias."""
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import (RandomForestClassifier, RandomForestRegressor,
    ExtraTreesClassifier, ExtraTreesRegressor,
    HistGradientBoostingClassifier, HistGradientBoostingRegressor)
from sklearn.neural_network import MLPClassifier, MLPRegressor

CATALOGO = {
    "dummy": (DummyClassifier, DummyRegressor, {"strategy": "prior"}, {"strategy": "mean"}),
    "linear": (LogisticRegression, Ridge, {"max_iter": 1000}, {}),
    "arvore": (DecisionTreeClassifier, DecisionTreeRegressor, {"max_depth": 8}, {"max_depth": 8}),
    "random_forest": (RandomForestClassifier, RandomForestRegressor,
                      {"n_estimators": 150, "min_samples_leaf": 5, "n_jobs": 2},
                      {"n_estimators": 150, "min_samples_leaf": 5, "n_jobs": 2}),
    "extra_trees": (ExtraTreesClassifier, ExtraTreesRegressor,
                    {"n_estimators": 150, "min_samples_leaf": 5, "n_jobs": 2},
                    {"n_estimators": 150, "min_samples_leaf": 5, "n_jobs": 2}),
    "hist_gradient_boosting": (HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                               {"max_iter": 150}, {"max_iter": 150}),
    "mlp": (MLPClassifier, MLPRegressor,
            {"hidden_layer_sizes": (128, 64), "max_iter": 150},
            {"hidden_layer_sizes": (128, 64), "max_iter": 150}),
}


def criar_modelos(config, semente):
    cls, reg, pc, pr = CATALOGO[config["tipo"]]
    modelos = []
    for construtor, padrao, chave in [(cls, pc, "classificacao"), (reg, pr, "regressao")]:
        parametros = dict(padrao)
        if "random_state" in construtor().get_params():
            parametros["random_state"] = semente
        parametros.update(config.get(chave, {}))
        modelos.append(construtor(**parametros))
    return tuple(modelos)


if __name__ == "__main__":
    print("Auxiliar do treino. Modelos disponíveis:", ", ".join(CATALOGO))
