"""Diagnóstico por unidade: python -m src.eda.localizacao; não altera dados."""
from src.experimentos.pipeline_anterior.preparar_dados import PASTA_ORIGINAIS, ler, coordenadas_por_cep


def main():
    vendedores = ler('olist_sellers_dataset.csv', PASTA_ORIGINAIS)
    itens = ler('olist_order_items_dataset.csv', PASTA_ORIGINAIS)
    geo = coordenadas_por_cep(ler('olist_geolocation_dataset.csv', PASTA_ORIGINAIS))
    sem = vendedores.loc[~vendedores.seller_zip_code_prefix.str.zfill(5).isin(geo.geolocation_zip_code_prefix)]
    afetados = itens.loc[itens.seller_id.isin(sem.seller_id)]
    print(f'Vendedores sem coordenadas: {len(sem)}')
    print(f'Itens desses vendedores: {len(afetados)}')
    print(f'Pedidos distintos afetados: {afetados.order_id.nunique()}')


if __name__ == '__main__':
    main()
