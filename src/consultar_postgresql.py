import pandas as pd

from .carregar_postgresql import obter_conexao


def consultar_pedidos(particao="validacao"):
    """Busca no banco os pedidos da divisão escolhida."""

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


if __name__ == "__main__":
    from .inferencia import (
        carregar_modelos,
        prever_pedidos,
        priorizar_pedidos,
    )

    pedidos = consultar_pedidos()
    pacote, modelo = carregar_modelos()

    previsoes = prever_pedidos(pedidos, pacote, modelo)
    resultado = priorizar_pedidos(previsoes, pacote["fracao_fila"])

    print("Consulta e previsao pelo PostgreSQL executadas!")
    print("Pedidos avaliados:", len(resultado))
    print("Pedidos na fila:", int(resultado["prioridade"].sum()))