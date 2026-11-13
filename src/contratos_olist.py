"""Contratos versionados do experimento de vendedor único (sem alterar o legado)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .preparar_dados import exigir, validar_chave
from .tratar_dados_ml import UFS

VERSAO = "olist_single_seller_v1"
CATEGORICAS = ["customer_state", "seller_state", "categoria_principal"]
CONTAGENS = ["quantidade_itens", "quantidade_produtos", "quantidade_categorias",
             "qtd_avaliacoes_historicas_vendedor"]
HISTORICOS = ["nota_historica_vendedor_media", "qtd_avaliacoes_historicas_vendedor",
              "frequencia_avaliacoes_baixas_vendedor"]
CTGAN_FEATURES = [
    "customer_state", "seller_state", "categoria_principal", "quantidade_itens",
    "quantidade_produtos", "quantidade_categorias", "valor_itens", "valor_frete",
    "peso_total_g", "volume_total_cm3", "distancia_vendedor_cliente_km",
    "prazo_prometido_dias", *HISTORICOS,
]
RAZOES = ["preco_medio_item", "proporcao_frete_valor"]
CLEAN_COLUMNS = ["order_id", "seller_id", "particao", "order_approved_at",
                 *CTGAN_FEATURES, *RAZOES, "atrasou", "origem_dado"]
ML_FEATURES = [
    "customer_state", "seller_state", "distancia_vendedor_cliente_km",
    "categoria_principal", "quantidade_itens", "quantidade_produtos",
    "quantidade_categorias", "peso_total_g", "volume_total_cm3", *HISTORICOS,
    "valor_itens", "preco_medio_item", "valor_frete", "proporcao_frete_valor",
    "prazo_prometido_dias", "mes_aprovacao",
]
ML_TARGET = "atrasou"
ML_METADATA = ["order_id", "seller_id", "particao", "origem_dado"]
ML_DATASET_COLUMNS = ML_METADATA + ML_FEATURES + [ML_TARGET]
NUMERICAS_CTGAN = [c for c in CTGAN_FEATURES if c not in CATEGORICAS]
assert (len(CLEAN_COLUMNS), len(CTGAN_FEATURES), len(ML_FEATURES), len(ML_DATASET_COLUMNS)) == (23, 15, 18, 23)


def adicionar_razoes(base):
    base = base.copy()
    base["preco_medio_item"] = base.valor_itens / base.quantidade_itens
    base["proporcao_frete_valor"] = base.valor_frete / base.valor_itens.where(base.valor_itens.gt(0))
    return base


def mascara_valida(base):
    """Domínio conceitual; nulos só nos históricos sem eventos e razão 0/0."""
    valido = pd.Series(True, index=base.index)
    for c in CATEGORICAS:
        valido &= base[c].notna()
    for c in ["customer_state", "seller_state"]:
        valido &= base[c].isin(UFS)
    for c in NUMERICAS_CTGAN:
        if c in HISTORICOS:
            continue
        valido &= np.isfinite(base[c]) & base[c].ge(0)
    for c in CONTAGENS:
        valido &= np.isfinite(base[c]) & base[c].ge(0) & base[c].eq(np.floor(base[c]))
    valido &= (base.quantidade_categorias.ge(1)
               & base.quantidade_produtos.ge(base.quantidade_categorias)
               & base.quantidade_itens.ge(base.quantidade_produtos))
    n, nota, baixa = [base[c] for c in [HISTORICOS[1], HISTORICOS[0], HISTORICOS[2]]]
    valido &= ((n.eq(0) & nota.isna() & baixa.isna())
               | (n.gt(0) & nota.between(1, 5) & baixa.between(0, 1)))
    valido &= base.distancia_vendedor_cliente_km.le(np.pi * 6371.0088)
    return valido.fillna(False)


def validar_limpo(base, *, sintetico=False):
    exigir(list(base.columns) == CLEAN_COLUMNS, "Contrato A/C: colunas/ordem diferentes das 23 previstas.")
    validar_chave(base, ["order_id"], "Contrato A/C")
    exigir(base.seller_id.notna().all(), "seller_id ausente.")
    exigir(mascara_valida(base).all(), "Atributos fora do domínio do contrato A/C.")
    exigir(base.atrasou.isin([0, 1]).all(), "Alvo sem desfecho/rotulo binário.")
    exigir(base.particao.isin(["treino", "validacao", "teste"]).all(), "Partição inválida.")
    exigir(pd.to_datetime(base.order_approved_at, errors="coerce").notna().all(), "Aprovação inválida.")
    esperado = adicionar_razoes(base)
    for c in RAZOES:
        exigir(np.allclose(base[c], esperado[c], equal_nan=True), f"Razão inconsistente: {c}")
    origem = "sintetico_ctgan" if sintetico else "real"
    exigir(base.origem_dado.eq(origem).all(), "Origem incompatível com o contrato.")
    if sintetico:
        exigir(base.particao.eq("treino").all(), "Sintéticos fora do treino.")
        for c in ["order_id", "seller_id"]:
            exigir(base[c].str.startswith(f"ctgan_{c.split('_')[0]}_").all(), "ID fora do namespace sintético.")
        perfis = base.groupby("seller_id")[["seller_state", *HISTORICOS]].nunique(dropna=False)
        exigir(perfis.le(1).all().all(), "Pseudovendedor reutilizado com perfil incompatível.")
    return True


def validar_ml(base):
    exigir(list(base.columns) == ML_DATASET_COLUMNS, "Contrato D: colunas/ordem inválidas.")
    validar_chave(base, ["order_id"], "Contrato D")
    exigir(base.seller_id.notna().all(), "seller_id ausente no ML.")
    exigir(base.atrasou.isin([0, 1]).all(), "Alvo ML inválido.")
    exigir(base.particao.isin(["treino", "validacao", "teste"]).all(), "Partição inválida.")
    exigir(base.origem_dado.isin(["real", "sintetico_ctgan"]).all(), "Origem desconhecida.")
    exigir((base.origem_dado.eq("real") | base.particao.eq("treino")).all(), "Validação/teste devem ser reais.")
    exigir(mascara_valida(base).all(), "Atributos ML fora do domínio.")
    exigir(base.mes_aprovacao.between(1, 12).all()
           and base.mes_aprovacao.eq(np.floor(base.mes_aprovacao)).all(), "Mês inválido.")
    for c in RAZOES:
        exigir(np.allclose(base[c], adicionar_razoes(base)[c], equal_nan=True), f"Razão ML inconsistente: {c}")


def montar_ml(real, sintetico=None):
    validar_limpo(real)
    partes = [real]
    if sintetico is not None:
        validar_limpo(sintetico, sintetico=True)
        exigir(not set(real.seller_id) & set(sintetico.seller_id), "Colisão de vendedor real/sintético.")
        partes.append(sintetico)
    base = pd.concat(partes, ignore_index=True)
    base["mes_aprovacao"] = pd.to_datetime(base.order_approved_at).dt.month.astype(int)
    base = base[ML_DATASET_COLUMNS].copy()
    validar_ml(base)
    return base
