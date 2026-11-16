"""Lê o CSV revisado sem limpar, imputar, excluir linhas ou recalcular features."""
import numpy as np
import pandas as pd
from src.dados.esquema import RAIZ, ATRIBUTOS, CATEGORICAS, PROIBIDAS, ALVO_CLASSE, ALVO_DIAS


def exigir_revisao(config):
    if config.get("dados_validados") is not True:
        raise ValueError("Treinamento bloqueado: revise e trate dataset_ml.csv; depois defina dados_validados=true em treinamento.json.")


def atributos_configurados(config):
    atributos = config.get("atributos", ATRIBUTOS)
    if not atributos or len(set(atributos)) != len(atributos):
        raise ValueError("A lista atributos precisa ser não vazia e sem repetições.")
    proibidas = set(atributos) & PROIBIDAS
    if proibidas:
        raise ValueError(f"Colunas de identificação/desfecho não podem entrar em X: {sorted(proibidas)}")
    if set(atributos) - set(ATRIBUTOS):
        raise ValueError(f"Atributos fora do contrato: {sorted(set(atributos) - set(ATRIBUTOS))}")
    return list(atributos)


def validar_tabela(base, atributos):
    necessarias = ["order_id", ALVO_CLASSE, ALVO_DIAS, *atributos]
    faltam = set(necessarias) - set(base)
    if faltam:
        raise ValueError(f"Colunas ausentes: {sorted(faltam)}")
    if base.empty or base.order_id.isna().any() or base.order_id.duplicated().any():
        raise ValueError("O CSV precisa ter uma linha por pedido, com order_id único e presente.")
    ausencias = base[[c for c in necessarias if c != ALVO_DIAS]].isna().sum()
    if ausencias.any():
        raise ValueError(f"Campos ausentes para seu tratamento (nenhuma imputação feita): {ausencias[ausencias.gt(0)].to_dict()}")
    for c in [*atributos, ALVO_CLASSE, ALVO_DIAS]:
        if c not in CATEGORICAS:
            valores = pd.to_numeric(base[c], errors="raise")
            verificar = valores.dropna() if c == ALVO_DIAS else valores
            if not np.isfinite(verificar.to_numpy(float)).all():
                raise ValueError(f"Valores não finitos em {c}; revise o CSV.")
            base[c] = valores
    conhecidos = base[ALVO_DIAS].notna()
    fontes = base.get("delay_status_source", pd.Series("datas", index=base.index))
    if ((~conhecidos) & ~(fontes.isin(["pln", "ctgan"]) & base[ALVO_CLASSE].eq(1))).any():
        raise ValueError("Dias ausentes só são aceitos para atrasos inferidos pela PLN ou CTGAN, com fonte registrada.")
    if not base[ALVO_CLASSE].isin([0, 1]).all() or not base.loc[conhecidos, ALVO_CLASSE].eq(base.loc[conhecidos, ALVO_DIAS].ge(1).astype(int)).all():
        raise ValueError("delay_status deve ser exatamente delay_in_days >= 1.")
    return base


def carregar(config):
    exigir_revisao(config)
    atributos = atributos_configurados(config)
    entrada = RAIZ / config.get("entrada", "Dados/dataset_ml.csv")
    base = validar_tabela(pd.read_csv(entrada, low_memory=False, dtype={"order_id": "string"}), atributos)
    datas = pd.to_datetime(base["order_approved_at"], errors="raise")
    if datas.isna().any():
        raise ValueError("order_approved_at ausente; revise antes da divisão temporal.")
    cortes = config["cortes"]
    val, teste = pd.Timestamp(cortes["validacao"]), pd.Timestamp(cortes["teste"])
    if val >= teste:
        raise ValueError("Corte de validação deve ser anterior ao de teste.")
    if "particao" not in base:
        base["particao"] = np.where(datas.lt(val), "treino", np.where(datas.lt(teste), "validacao", "teste"))
    if not base.particao.isin(["treino", "validacao", "teste"]).all():
        raise ValueError("Partições aceitas: treino, validacao e teste.")
    # Se o usuário fornece partições, elas também precisam respeitar os cortes.
    esperado = np.where(datas.lt(val), "treino", np.where(datas.lt(teste), "validacao", "teste"))
    if not np.array_equal(base.particao, esperado):
        raise ValueError("As partições fornecidas discordam dos cortes temporais configurados.")
    if config.get("verificar_disponibilidade_rotulo", True):
        # Reconstrução da data do desfecho só para checagem, nunca atributo de X.
        if "label_available_at" in base:
            entrega = pd.to_datetime(base.label_available_at, errors="raise")
        else:
            entrega = datas + pd.to_timedelta(base.order_delivered_customer_date_in_days - base.approval_date_in_days, unit="D")
        if entrega.isna().any():
            raise ValueError("label_available_at ausente; revise a disponibilidade dos rótulos.")
        futuros = ((base.particao.eq("treino") & entrega.ge(val)) | (base.particao.eq("validacao") & entrega.ge(teste)))
        if futuros.any():
            raise ValueError(f"{int(futuros.sum())} rótulos ficam disponíveis após o corte seguinte. Revise a coorte/cortes; nenhuma linha foi descartada automaticamente.")
    if "seller_reliability_score" in atributos and config.get("review_score_origem") != "media_global_vendedor":
        raise ValueError("Para este CSV, declare review_score_origem=media_global_vendedor.")
    base["origem_dado"] = "real_olist"
    base["rotulo_observado"] = base.get("delay_status_source", pd.Series("datas", index=base.index)).eq("datas")
    return base, atributos, {"cortes": cortes, "linhas_descartadas": 0,
        "review_score_origem": config.get("review_score_origem"),
        "verificar_disponibilidade_rotulo": config.get("verificar_disponibilidade_rotulo", True)}
