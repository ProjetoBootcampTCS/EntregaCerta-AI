"""Carga e consulta PostgreSQL. Administração: python main.py --help."""
from __future__ import annotations

import csv
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql


RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO_CSV = RAIZ / "Dados" / "pedidos_ml.csv"
ARQUIVO_AVALIACOES = RAIZ / "Dados" / "Brazilian Logistic" / "olist_order_reviews_dataset.csv"
COLUNAS_AVALIACOES = (
    "review_id",
    "order_id",
    "review_score",
    "review_comment_title",
    "review_comment_message",
    "review_creation_date",
    "review_answer_timestamp",
)

# Cada coluna do CSV aparece exatamente uma vez nestes grupos. As colunas
# derivadas e flags de ausência também são mantidas, sem recalcular seus valores.
COLUNAS_POR_TABELA: dict[str, tuple[str, ...]] = {
    "pedidos": (
        "order_id",
        "customer_unique_id",
        "order_approved_at",
        "rotulo_disponivel_em",
        "particao",
        "atrasou",
        "dias_atraso",
    ),
    "clientes": ("customer_state",),
    "logistica": (
        "uf_origem",
        "categoria_principal",
        "quantidade_itens",
        "quantidade_produtos",
        "quantidade_vendedores",
        "quantidade_categorias",
        "quantidade_ufs_origem",
        "valor_itens",
        "valor_frete",
        "peso_total_g",
        "volume_total_cm3",
        "itens_sem_peso",
        "itens_sem_dimensoes",
        "itens_sem_categoria",
        "distancia_media_vendedores_km",
        "distancia_max_vendedores_km",
        "vendedores_sem_distancia",
        "vendedores_sem_uf",
        "prazo_prometido_dias",
        "tempo_aprovacao_horas",
        "dia_semana_aprovacao",
        "mes_aprovacao",
        "hora_aprovacao",
    ),
    "pagamentos": (
        "valor_pago",
        "quantidade_pagamentos",
        "quantidade_formas_pagamento",
        "parcelas_maximas",
        "tipo_pagamento_principal",
    ),
    "qualidade_dados": (
        "faltante_peso_total_g",
        "faltante_volume_total_cm3",
        "faltante_distancia_media_vendedores_km",
        "faltante_distancia_max_vendedores_km",
        "faltante_valor_pago",
        "faltante_quantidade_pagamentos",
        "faltante_quantidade_formas_pagamento",
        "faltante_parcelas_maximas",
    ),
}


def obter_conexao() -> psycopg.Connection:
    """Usa ENTREGACERTA_DATABASE_URL ou as variáveis POSTGRES_* do compose."""
    load_dotenv(RAIZ / ".env")
    url = os.getenv("ENTREGACERTA_DATABASE_URL", "").strip()
    if url:
        return psycopg.connect(url)

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.getenv("POSTGRES_DB", "meu_banco"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def validar_cabecalho(cabecalho: list[str] | None, esperado: list[str], arquivo: Path) -> None:
    if cabecalho is None:
        raise ValueError(f"O CSV está vazio: {arquivo}")
    if len(cabecalho) != len(set(cabecalho)):
        raise ValueError("O CSV contém nomes de coluna repetidos.")
    if set(cabecalho) != set(esperado) or len(cabecalho) != len(esperado):
        faltando = sorted(set(esperado) - set(cabecalho))
        extras = sorted(set(cabecalho) - set(esperado))
        raise ValueError(f"Cabeçalho inesperado; colunas ausentes={faltando}, extras={extras}.")


def criar_tabelas(cursor: psycopg.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pedidos (
            pedido_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_id TEXT NOT NULL UNIQUE,
            customer_unique_id TEXT,
            order_approved_at TEXT,
            rotulo_disponivel_em TEXT,
            particao TEXT,
            atrasou TEXT,
            dias_atraso TEXT
        )
        """
    )
    for tabela in ("clientes", "logistica", "pagamentos", "qualidade_dados"):
        definicoes = [sql.SQL("pedido_id BIGINT PRIMARY KEY REFERENCES pedidos(pedido_id)")]
        definicoes.extend(sql.SQL("{} TEXT").format(sql.Identifier(coluna)) for coluna in COLUNAS_POR_TABELA[tabela])
        cursor.execute(
            sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
                sql.Identifier(tabela), sql.SQL(", ").join(definicoes)
            )
        )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS avaliacoes (
            avaliacao_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            review_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            review_score TEXT,
            review_comment_title TEXT,
            review_comment_message TEXT,
            review_creation_date TEXT,
            review_answer_timestamp TEXT
        )
        """
    )


def carregar() -> tuple[int, int]:
    for arquivo_csv in (ARQUIVO_CSV, ARQUIVO_AVALIACOES):
        if not arquivo_csv.is_file():
            raise FileNotFoundError(f"CSV não encontrado: {arquivo_csv}")

    total = 0
    total_avaliacoes = 0
    with ARQUIVO_CSV.open("r", encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        validar_cabecalho(
            leitor.fieldnames,
            [coluna for colunas in COLUNAS_POR_TABELA.values() for coluna in colunas],
            ARQUIVO_CSV,
        )

        with obter_conexao() as conexao:
            with conexao.cursor() as cursor:
                criar_tabelas(cursor)
                cursor.execute("TRUNCATE TABLE avaliacoes RESTART IDENTITY")
                cursor.execute(
                    "TRUNCATE TABLE qualidade_dados, pagamentos, logistica, clientes, pedidos RESTART IDENTITY"
                )

                sql_pedido = sql.SQL("INSERT INTO pedidos ({}) VALUES ({}) RETURNING pedido_id").format(
                    sql.SQL(", ").join(map(sql.Identifier, COLUNAS_POR_TABELA["pedidos"])),
                    sql.SQL(", ").join(sql.Placeholder() for _ in COLUNAS_POR_TABELA["pedidos"]),
                )

                comandos_dependentes = {
                    tabela: sql.SQL("INSERT INTO {} (pedido_id, {}) VALUES ({})").format(
                        sql.Identifier(tabela),
                        sql.SQL(", ").join(map(sql.Identifier, colunas)),
                        sql.SQL(", ").join(
                            [sql.Placeholder()] + [sql.Placeholder() for _ in colunas]
                        ),
                    )
                    for tabela, colunas in COLUNAS_POR_TABELA.items()
                    if tabela != "pedidos"
                }

                for linha in leitor:
                    if None in linha:
                        raise ValueError(f"Linha CSV com campos excedentes após o registro {total + 1}.")
                    if any(linha[coluna] is None for coluna in leitor.fieldnames or []):
                        raise ValueError(f"Linha CSV incompleta no registro {total + 1}; carga cancelada.")

                    valores_pedido = tuple(linha[coluna] for coluna in COLUNAS_POR_TABELA["pedidos"])
                    cursor.execute(sql_pedido, valores_pedido)
                    pedido_id = cursor.fetchone()[0]

                    for tabela, comando in comandos_dependentes.items():
                        valores = tuple(linha[coluna] for coluna in COLUNAS_POR_TABELA[tabela])
                        cursor.execute(comando, (pedido_id, *valores))

                    total += 1

                # review_id não é chave única no arquivo da Olist: o identificador
                # técnico da tabela garante que todas as linhas repetidas sejam mantidas.
                comando_avaliacao = sql.SQL("INSERT INTO avaliacoes ({}) VALUES ({})").format(
                    sql.SQL(", ").join(map(sql.Identifier, COLUNAS_AVALIACOES)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in COLUNAS_AVALIACOES),
                )
                with ARQUIVO_AVALIACOES.open("r", encoding="utf-8-sig", newline="") as arquivo_avaliacoes:
                    leitor_avaliacoes = csv.DictReader(arquivo_avaliacoes)
                    validar_cabecalho(leitor_avaliacoes.fieldnames, list(COLUNAS_AVALIACOES), ARQUIVO_AVALIACOES)
                    lote: list[tuple[str, ...]] = []
                    for numero, linha in enumerate(leitor_avaliacoes, start=1):
                        if None in linha or any(linha[coluna] is None for coluna in COLUNAS_AVALIACOES):
                            raise ValueError(f"Linha CSV de avaliações incompleta ou excedente: {numero}.")
                        lote.append(tuple(linha[coluna] for coluna in COLUNAS_AVALIACOES))
                        total_avaliacoes += 1
                        if len(lote) == 1_000:
                            cursor.executemany(comando_avaliacao, lote)
                            lote.clear()
                    if lote:
                        cursor.executemany(comando_avaliacao, lote)

    return total, total_avaliacoes



def consultar_pedidos(particao="validacao"):
    """Busca no banco os pedidos da divisão escolhida."""

    import pandas as pd

    with obter_conexao() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute("""
                SELECT *
                FROM public.vw_pedidos_inferencia
                WHERE particao = %s
                ORDER BY order_approved_at, order_id
            """, (particao,))

            colunas = [coluna.name for coluna in cursor.description]
            pedidos = pd.DataFrame(cursor.fetchall(), columns=colunas)

    if pedidos.empty:
        raise ValueError("Nenhum pedido encontrado para essa divisão.")

    if not pedidos["order_id"].is_unique:
        raise ValueError("A consulta retornou pedidos duplicados.")

    return pedidos

