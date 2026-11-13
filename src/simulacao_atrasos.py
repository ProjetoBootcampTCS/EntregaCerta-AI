"""Hipóteses configuráveis: não são relações causais estimadas no Olist."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.special import expit

from .contratos_olist import CLEAN_COLUMNS, HISTORICOS, validar_limpo
from .preparar_dados import exigir

FATORES = {
    "distance": "distancia_vendedor_cliente_km", "weight": "peso_total_g",
    "volume": "volume_total_cm3", "price": "valor_itens", "unit_price": "preco_medio_item",
    "freight": "valor_frete", "freight_ratio": "proporcao_frete_valor",
    "promised_days": "prazo_prometido_dias",
}


class SimuladorAtrasos:
    def __init__(self, config):
        self.config = dict(config)

    def fit(self, treino):
        validar_limpo(treino)
        exigir(treino.particao.eq("treino").all(), "Escalas do simulador exigem treino real.")
        exigir(0 < self.config["target_delay_rate"] < 1, "Taxa alvo deve estar entre 0 e 1.")
        exigir(self.config["scenario_strength"] >= 0, "Intensidade deve ser não negativa.")
        permitidos = set(FATORES) | {"seller_rating", "seller_low_review_frequency", "order_complexity"}
        exigir(set(self.config["coefficients"]) <= permitidos, "Coeficiente desconhecido.")
        self.escalas = {}
        for fator, coluna in FATORES.items():
            valores = np.log1p(treino[coluna].dropna())
            centro = float(valores.median()) if len(valores) else 0.
            escala = float(valores.quantile(.9) - valores.quantile(.1)) if len(valores) else 1.
            self.escalas[fator] = (centro, escala if escala > 1e-12 else 1.)
        self.nota_centro = float(treino[HISTORICOS[0]].mean()) if treino[HISTORICOS[0]].notna().any() else 3.
        self.baixa_centro = float(treino[HISTORICOS[2]].mean()) if treino[HISTORICOS[2]].notna().any() else .5
        return self

    def score(self, base):
        coefs = self.config["coefficients"]
        score = np.zeros(len(base), dtype=float)
        for fator, coluna in FATORES.items():
            centro, escala = self.escalas[fator]
            z = (np.log1p(base[coluna]).fillna(centro).to_numpy() - centro) / escala
            score += coefs.get(fator, 0) * z
        n = base[HISTORICOS[1]].to_numpy()
        suavizacao = self.config.get("review_confidence", 10.)
        exigir(suavizacao > 0, "Confiança de reviews deve ser positiva.")
        confianca = n / (n + suavizacao)
        score += coefs.get("seller_rating", 0) * confianca * (base[HISTORICOS[0]].fillna(self.nota_centro).to_numpy() - self.nota_centro)
        score += coefs.get("seller_low_review_frequency", 0) * confianca * (base[HISTORICOS[2]].fillna(self.baixa_centro).to_numpy() - self.baixa_centro)
        complexidade = np.log1p(base[["quantidade_itens", "quantidade_produtos", "quantidade_categorias"]] - 1).mean(axis=1)
        score += coefs.get("order_complexity", 0) * complexidade.to_numpy()
        score += base.categoria_principal.map(self.config.get("category_adjustments", {})).fillna(0).to_numpy()
        exigir(np.isfinite(score).all(), "Score de simulação não finito.")
        return self.config["scenario_strength"] * score

    def simular(self, candidatos):
        exigir(not candidatos.empty, "Lote sintético vazio.")
        exigir((candidatos.origem_dado.eq("sintetico_ctgan") & candidatos.particao.eq("treino")).all(), "Simulação só pode rotular sintéticos de treino.")
        score = self.score(candidatos)
        alvo = self.config["target_delay_rate"]
        inferior, superior = -float(np.max(score)) - 40, -float(np.min(score)) + 40
        for _ in range(100):
            meio = (inferior + superior) / 2
            if expit(meio + score).mean() < alvo:
                inferior = meio
            else:
                superior = meio
        intercepto = (inferior + superior) / 2
        probabilidades = expit(intercepto + score)
        rng = np.random.default_rng(self.config["seed"])
        if self.config.get("exact_count", False):
            rotulos = np.zeros(len(candidatos), dtype=int)
            indices = rng.choice(len(rotulos), size=round(len(rotulos) * alvo), replace=False,
                                 p=probabilidades / probabilidades.sum())
            rotulos[indices] = 1
        else:
            rotulos = rng.binomial(1, probabilidades)
        saida = candidatos.copy()
        saida["atrasou"] = rotulos
        saida = saida[CLEAN_COLUMNS]
        validar_limpo(saida, sintetico=True)
        detalhes = pd.DataFrame({"order_id": saida.order_id, "score_risco": score,
                                 "p_atraso_simulada": probabilidades, "atrasou_simulado": rotulos})
        decis = {}
        for c in ["distancia_vendedor_cliente_km", "peso_total_g", "valor_frete", HISTORICOS[0]]:
            faixas = pd.qcut(saida[c], 10, duplicates="drop")
            grupo = detalhes.assign(faixa=faixas.astype(str)).groupby("faixa", observed=True)
            decis[c] = grupo.agg(p_media=("p_atraso_simulada", "mean"), taxa=("atrasou_simulado", "mean"), n=("order_id", "size")).to_dict("index")
        decis["score_risco"] = detalhes.assign(faixa=pd.qcut(score, 10, duplicates="drop").astype(str)).groupby("faixa").agg(
            p_media=("p_atraso_simulada", "mean"), taxa=("atrasou_simulado", "mean"), n=("order_id", "size")).to_dict("index")
        relatorio = {"config": self.config, "escalas_treino": self.escalas, "intercepto": intercepto,
                     "probabilidade_media": float(probabilidades.mean()), "taxa_obtida": float(rotulos.mean()),
                     "atrasos_simulados": int(rotulos.sum()), "decis": decis,
                     "nota": "Rótulos hipotéticos, não evidência causal. No modo exato, p é peso de sorteio, não probabilidade marginal de inclusão."}
        return saida, detalhes, relatorio
