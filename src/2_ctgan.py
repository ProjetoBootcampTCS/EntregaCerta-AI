"""CTGAN sobre dataset_ml revisado, com ausência de dias explicitamente codificada."""
import numpy as np
import pandas as pd
import sys
from pathlib import Path
from importlib import import_module

# Os scripts numerados funcionam também quando executados fora da raiz do projeto.
sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

_dados = import_module("src.2_dados_treino")
CATEGORICAS, ALVO_CLASSE, ALVO_DIAS = _dados.CATEGORICAS, _dados.ALVO_CLASSE, _dados.ALVO_DIAS
CONTAGENS_CALENDARIO = _dados.CONTAGENS_CALENDARIO
validar_tabela, exigir_revisao = _dados.validar_tabela, _dados.exigir_revisao



def ajustar(treino, config, semente, atributos):
    if not treino.particao.eq("treino").all() or not treino.origem_dado.eq("real_olist").all():
        raise ValueError("CTGAN aceita exclusivamente treino real.")
    exigir_revisao(config)
    validar_tabela(treino.copy(), atributos)
    from ctgan import CTGAN
    import torch
    torch.set_num_threads(config.get("threads", 2))
    torch.manual_seed(semente)
    tabela = treino[atributos + [ALVO_DIAS]].copy()
    discretas = [c for c in atributos if c in CATEGORICAS or c in CONTAGENS_CALENDARIO
                 or c in config.get("colunas_discretas", ["qtd_items", "payment_sequential", "payment_installments"])]
    if tabela[ALVO_DIAS].isna().any():
        tabela["__dias_ausentes"] = tabela[ALVO_DIAS].isna().astype(int)
        discretas.append("__dias_ausentes")
        # Sentinela técnica da representação; restaurada como NaN após geração.
        tabela[ALVO_DIAS] = tabela[ALVO_DIAS].fillna(0)
    for c in discretas:
        tabela[c] = tabela[c].astype(str)
    constantes = {c: tabela[c].iloc[0] for c in tabela if tabela[c].nunique() == 1}
    tabela = tabela.drop(columns=list(constantes))
    if tabela.empty:
        raise ValueError("Nenhuma coluna variável para treinar a CTGAN.")
    parametros = {"epochs": 100, "batch_size": 500, "pac": 10, "generator_dim": (128, 128),
                  "discriminator_dim": (128, 128), "verbose": True, "enable_gpu": False}
    parametros.update(config.get("parametros", {}))
    gerador = CTGAN(**parametros)
    gerador.set_random_state(semente)
    gerador.fit(tabela, discrete_columns=[c for c in discretas if c in tabela])
    return {"gerador": gerador, "constantes": constantes, "atributos": atributos,
            "protocolo": "engineering_revisado_sem_imputacao", "colunas_discretas": discretas}


def amostrar(pacote, quantidade, particao, semente):
    pacote["gerador"].set_random_state(semente)
    dados = pacote["gerador"].sample(quantidade)
    for c, valor in pacote["constantes"].items():
        dados[c] = valor
    for c in pacote["atributos"] + [ALVO_DIAS]:
        if c not in CATEGORICAS:
            dados[c] = pd.to_numeric(dados[c], errors="raise")
    # Derivar a classe garante a mesma definição usada nos pedidos reais.
    dados[ALVO_CLASSE] = dados[ALVO_DIAS].ge(1).astype(int)
    if "__dias_ausentes" in dados:
        ausentes = pd.to_numeric(dados.pop("__dias_ausentes"), errors="raise").eq(1)
        dados.loc[ausentes, ALVO_DIAS] = np.nan
        dados.loc[ausentes, ALVO_CLASSE] = 1
    dados["delay_status_source"] = "ctgan"
    dados["order_id"] = [f"SYN-{particao}-{semente}-{i:08d}" for i in range(len(dados))]
    dados["particao"] = particao
    dados["origem_dado"] = "sintetico_ctgan"
    dados["rotulo_observado"] = False
    validar_tabela(dados, pacote["atributos"])
    return dados


if __name__ == "__main__":
    print("Auxiliar do treino: execute 2_treinar_modelos.py; para gerar apenas dados, use --etapa preparar.")
