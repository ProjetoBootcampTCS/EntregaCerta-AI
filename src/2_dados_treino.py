"""Contrato explícito dos novos CSVs; nenhuma regra de limpeza automática."""
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ALVO_CLASSE = "delay_status"
ALVO_DIAS = "delay_in_days"
CATEGORICAS = ["order_status", "customer_state", "seller_state", "predominant_product_category_name",
               "transportadora", "delivered_to_carrier_week_day"]
ATRIBUTOS_CALENDARIO = [
    "delivered_to_carrier_minus_estimative_in_days", "delivered_to_carrier_week_day",
    "delivered_to_carrier_is_holiday", "delivered_to_carrier_to_estimative_holidays",
    "delivered_to_carrier_to_estimative_business_days", "delivered_to_carrier_days_until_next_business_day",
]
CONTAGENS_CALENDARIO = ATRIBUTOS_CALENDARIO[2:]
ATRIBUTOS = [
    "order_status", "price", "freight_value", "customer_state", "seller_state",
    "qtd_items", "total_volume_cm3", "total_weight", "predominant_product_category_name",
    "distance_customer_seller", "seller_reliability_score", "transportadora", "approval_date_in_days",
] + ATRIBUTOS_CALENDARIO
PROIBIDAS = {
    "order_id", "customer_id", "seller_id", "order_approved_at", "label_available_at", "delay_status_source",
    "order_delivered_carrier_date_in_days", "order_delivered_customer_date_in_days",
    "review_comment_title", "review_comment_message", "review_score_order", "review_score",
    "delay_status", "delay_in_days", "particao", "elegivel_particao", "origem_dado", "rotulo_observado",
}


def sha256(caminho):
    digest = hashlib.sha256()
    with Path(caminho).open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()

def exigir_revisao(config):
    if config.get("dados_validados") is not True:
        raise ValueError("Treinamento bloqueado: revise e trate dataset_ml.csv; depois defina dados_validados=true em configuracoes/2_treinamento.json.")


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


def atribuir_particoes(base, config):
    """Separa pela data de aprovação, sem excluir pedidos ou consultar o rótulo."""
    base = base.drop(columns="elegivel_particao", errors="ignore").copy()
    datas = pd.to_datetime(base["order_approved_at"], errors="raise")
    cortes = config["cortes"]
    val, teste = pd.Timestamp(cortes["validacao"]), pd.Timestamp(cortes["teste"])
    if pd.isna(val) or pd.isna(teste) or val >= teste:
        raise ValueError("Corte de validação deve ser anterior ao de teste.")
    base["particao"] = pd.Series(np.where(datas.lt(val), "treino",
        np.where(datas.lt(teste), "validacao", "teste")), index=base.index, dtype="string").where(datas.notna())
    resumo = {"metodo": "data_aprovacao", "cortes": cortes, "pedidos_csv": len(base),
        "aprovacoes_ausentes": int(datas.isna().sum()),
        "por_particao": {p: int(base.particao.eq(p).sum()) for p in ["treino", "validacao", "teste"]}}
    return base, resumo


def carregar(config):
    exigir_revisao(config)
    atributos = atributos_configurados(config)
    entrada = RAIZ / config.get("entrada", "Dados/dataset_ml.csv")
    base = pd.read_csv(entrada, low_memory=False, dtype={"order_id": "string"})
    linhas_entrada = len(base)
    descartados = 0
    # Elegibilidade explícita para previsão após o despacho; o CSV é preservado.
    if config.get("excluir_sem_data_transportadora", False) and set(atributos) & set(ATRIBUTOS_CALENDARIO):
        coluna = "delivered_to_carrier_week_day"
        if coluna not in base:
            raise ValueError("Features de calendário ausentes; execute 1_preparar_dados.py --somente-calendario.")
        elegiveis = base[coluna].notna()
        descartados = int((~elegiveis).sum())
        base = base.loc[elegiveis].copy()
    base = validar_tabela(base, atributos)
    base, resumo = atribuir_particoes(base, config)
    if base.particao.isna().any():
        raise ValueError("order_approved_at ausente; necessário para atribuir a partição.")
    if "seller_reliability_score" in atributos and config.get("review_score_origem") != "media_global_vendedor":
        raise ValueError("Para este CSV, declare review_score_origem=media_global_vendedor.")
    base["origem_dado"] = "real_olist"
    base["rotulo_observado"] = base.get("delay_status_source", pd.Series("datas", index=base.index)).eq("datas")
    return base, atributos, {**resumo, "pedidos_csv": linhas_entrada,
        "pedidos_elegiveis": len(base), "linhas_descartadas": descartados,
        "excluidos_sem_data_transportadora": descartados,
        "review_score_origem": config.get("review_score_origem")}


if __name__ == "__main__":
    print("Auxiliar chamado automaticamente por 1_preparar_dados.py e 2_treinar_modelos.py.")
