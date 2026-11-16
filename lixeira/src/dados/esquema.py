"""Contrato explícito dos novos CSVs; nenhuma regra de limpeza automática."""
import hashlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ALVO_CLASSE = "delay_status"
ALVO_DIAS = "delay_in_days"
CATEGORICAS = ["order_status", "customer_state", "seller_state", "predominant_product_category_name", "transportadora"]
ATRIBUTOS = [
    "order_status", "price", "freight_value", "customer_state", "seller_state",
    "qtd_items", "total_volume_cm3", "total_weight", "predominant_product_category_name",
    "distance_customer_seller", "seller_reliability_score", "transportadora", "approval_date_in_days",
]
PROIBIDAS = {
    "order_id", "customer_id", "seller_id", "order_approved_at", "label_available_at", "delay_status_source",
    "order_delivered_carrier_date_in_days", "order_delivered_customer_date_in_days",
    "review_comment_title", "review_comment_message", "review_score_order", "review_score",
    "delay_status", "delay_in_days", "particao", "origem_dado", "rotulo_observado",
}


def sha256(caminho):
    digest = hashlib.sha256()
    with Path(caminho).open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()
