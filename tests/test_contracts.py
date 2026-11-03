"""Testes técnicos isolados. Nenhum registro é usado para avaliar ML."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest
from entregacerta.contracts import validate_features

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('column', ['order_delivered_customer_date','order_status','shipping_limit_date'])
def test_future_or_unavailable_feature_source_is_rejected(column):
    contract = json.loads((ROOT/'config/atributos.json').read_text(encoding='utf-8'))
    tampered = deepcopy(contract)
    tampered['features'][0]['source'] = ['orders.' + column]
    with pytest.raises(ValueError, match='Informação futura'):
        validate_features(tampered)


def test_sql_foreign_keys_reject_orphan_order():
    # Apenas IDs fictícios de teste em memória; não são dados de treinamento.
    with sqlite3.connect(':memory:') as connection:
        connection.executescript((ROOT/'docs/schema_planejado.sql').read_text(encoding='utf-8'))
        with pytest.raises(sqlite3.IntegrityError, match='FOREIGN KEY'):
            connection.execute('INSERT INTO orders(order_id,customer_id) VALUES (?,?)',
                               ('technical-test-order','missing-customer'))
