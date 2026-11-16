"""CTGAN conjunta de atributos e alvos, ajustada exclusivamente no treino real."""
import numpy as np
import pandas as pd
from src.experimentos.pipeline_anterior.preparar_dados import COLUNAS_PREVISAO
from src.experimentos.pipeline_anterior.tratar_dados_ml import CATEGORICAS, NUMERICAS, limpar_atributos


def ajustar(treino, config, semente, atributos=None):
    if not treino.particao.eq("treino").all() or not treino.origem_dado.eq("real_olist").all():
        raise ValueError("CTGAN aceita exclusivamente treino real.")
    from ctgan import CTGAN
    import torch
    torch.set_num_threads(config.get("threads", 2))
    torch.manual_seed(semente)
    atributos = list(atributos or COLUNAS_PREVISAO)
    numericas = [c for c in atributos if c not in CATEGORICAS]
    tabela = treino[atributos + ["atrasou", "dias_atraso"]].copy()
    discretas = CATEGORICAS + ["atrasou"]
    continuas = numericas + ["dias_atraso"]
    medianas = tabela[continuas].median().fillna(0)
    flags = {}
    for c in numericas:
        if tabela[c].isna().any():
            flag = "faltante__" + c
            tabela[flag] = tabela[c].isna().astype(str)
            flags[c] = flag
            discretas.append(flag)
    for c in discretas:
        tabela[c] = tabela[c].fillna("NAO_INFORMADO").astype(str)
    tabela[continuas] = np.log1p(tabela[continuas].fillna(medianas).clip(lower=0))
    constantes = {c: tabela[c].iloc[0] for c in tabela if tabela[c].nunique() == 1}
    tabela = tabela.drop(columns=list(constantes))
    parametros = {"epochs": 100, "batch_size": 500, "pac": 10,
                  "generator_dim": (128, 128), "discriminator_dim": (128, 128),
                  "verbose": True, "enable_gpu": False}
    parametros.update(config.get("parametros", {}))
    gerador = CTGAN(**parametros)
    gerador.set_random_state(semente)
    gerador.fit(tabela, discrete_columns=[c for c in discretas if c in tabela])
    return {"gerador": gerador, "constantes": constantes, "continuas": continuas, "atributos": atributos,
            "flags": flags, "maximos": treino[continuas].max().fillna(0)}


def amostrar(pacote, quantidade, particao, semente):
    pacote["gerador"].set_random_state(semente)
    dados = pacote["gerador"].sample(quantidade)
    for c, valor in pacote["constantes"].items():
        dados[c] = valor
    for c in pacote["continuas"]:
        dados[c] = np.expm1(pd.to_numeric(dados[c], errors="coerce").clip(0, np.log1p(pacote["maximos"][c])))
    inteiras = [c for c in NUMERICAS if c.startswith(("quantidade_", "itens_sem_", "vendedores_sem_"))]
    inteiras += ["dia_semana_aprovacao", "mes_aprovacao", "hora_aprovacao", "parcelas_maximas", "prazo_prometido_dias"]
    dados[inteiras] = dados[inteiras].round()
    for c in ["quantidade_itens", "quantidade_produtos", "quantidade_vendedores", "quantidade_ufs_origem", "quantidade_pagamentos", "parcelas_maximas"]:
        dados[c] = dados[c].clip(lower=1)
    for c in ["quantidade_produtos", "quantidade_vendedores", "quantidade_categorias", "itens_sem_peso", "itens_sem_dimensoes", "itens_sem_categoria"]:
        dados[c] = np.minimum(dados[c], dados.quantidade_itens)
    for c in ["quantidade_ufs_origem", "vendedores_sem_uf", "vendedores_sem_distancia"]:
        dados[c] = np.minimum(dados[c], dados.quantidade_vendedores)
    dados["quantidade_formas_pagamento"] = dados.quantidade_formas_pagamento.clip(lower=1)
    dados["quantidade_formas_pagamento"] = np.minimum(dados.quantidade_formas_pagamento, dados.quantidade_pagamentos)
    dados["distancia_max_vendedores_km"] = np.maximum(dados.distancia_media_vendedores_km, dados.distancia_max_vendedores_km)
    dados["mes_aprovacao"] = dados.mes_aprovacao.clip(1, 12)
    for c in ["hist_nota_vendedor_media", "hist_nota_vendedor_min"]:
        if c in dados:
            dados[c] = dados[c].clip(1, 5)
    if "hist_nota_vendedor_min" in dados:
        dados["hist_nota_vendedor_min"] = np.minimum(dados.hist_nota_vendedor_min, dados.hist_nota_vendedor_media)
    for c in ["hist_notas_baixas_fracao", "hist_vendedores_sem_nota_fracao"]:
        if c in dados:
            dados[c] = dados[c].clip(0, 1)
    dados["atrasou"] = pd.to_numeric(dados.atrasou, errors="raise").astype(int)
    dados["dias_atraso"] = np.where(dados.atrasou.eq(1), dados.dias_atraso.round().clip(lower=1), 0)
    for c, flag in pacote["flags"].items():
        dados.loc[dados[flag].eq("True"), c] = np.nan
    limpos, _ = limpar_atributos(dados)
    dados[COLUNAS_PREVISAO] = limpos
    dados = dados[pacote["atributos"] + ["atrasou", "dias_atraso"]].copy()
    dados["order_id"] = [f"SYN-{particao}-{semente}-{i:08d}" for i in range(len(dados))]
    dados["particao"] = particao
    dados["origem_dado"] = "sintetico_ctgan"
    dados["rotulo_observado"] = False
    return dados
