r"""Consolida os CSVs reais da Olist, sem alterar os arquivos originais.

Execucao na raiz: .\.venv\Scripts\python.exe src/preparar_dados.py
O CSV inclui campos retrospectivos para EDA. Para uma futura previsao na
aprovacao, usar somente COLUNAS_PREVISAO, apos validar suas disponibilidades.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


RAIZ = Path(__file__).resolve().parents[1]
PASTA_ORIGINAIS = RAIZ / "Dados" / "Brazilian Logistic"
SAIDA = RAIZ / "Dados" / "pedidos_consolidados.csv"
RELATORIO = RAIZ / "Docs" / "validacao_dados.txt"

# Lista explicita: datas reais, status final, rotulos, IDs e flags de
# elegibilidade NUNCA devem entrar automaticamente em X no treinamento.
COLUNAS_PREVISAO = [
    "customer_state", "uf_origem", "categoria_principal",
    "quantidade_itens", "quantidade_produtos", "quantidade_vendedores",
    "quantidade_categorias", "quantidade_ufs_origem",
    "valor_itens", "valor_frete", "peso_total_g", "volume_total_cm3",
    "itens_sem_peso", "itens_sem_dimensoes", "itens_sem_categoria",
    "distancia_media_vendedores_km", "distancia_max_vendedores_km",
    "vendedores_sem_distancia", "vendedores_sem_uf",
    "valor_pago", "quantidade_pagamentos", "quantidade_formas_pagamento",
    "parcelas_maximas", "tipo_pagamento_principal",
    "prazo_prometido_dias", "tempo_aprovacao_horas",
    "dia_semana_aprovacao", "mes_aprovacao", "hora_aprovacao",
]


def exigir(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise ValueError(mensagem)


def validar_chave(df: pd.DataFrame, colunas: list[str], nome: str) -> None:
    exigir(df[colunas].notna().all().all(), f"{nome}: chave ausente.")
    exigir(not df.duplicated(colunas).any(), f"{nome}: chave duplicada {colunas}.")


def ler(nome: str, pasta: Path) -> pd.DataFrame:
    # CEPs sao identificadores: preservar zeros iniciais.
    return pd.read_csv(pasta / nome, dtype={
        "customer_zip_code_prefix": "string",
        "seller_zip_code_prefix": "string",
        "geolocation_zip_code_prefix": "string",
    })


def hash_arquivos(pasta: Path) -> dict[str, str]:
    resultado = {}
    for arquivo in sorted(pasta.glob("*.csv")):
        digest = hashlib.sha256()
        with arquivo.open("rb") as entrada:
            for bloco in iter(lambda: entrada.read(1024 * 1024), b""):
                digest.update(bloco)
        resultado[arquivo.name] = digest.hexdigest()
    return resultado


def coordenadas_por_cep(geo: pd.DataFrame) -> pd.DataFrame:
    geo = geo.copy()
    geo["geolocation_zip_code_prefix"] = geo["geolocation_zip_code_prefix"].str.zfill(5)
    validas = (geo["geolocation_lat"].between(-90, 90)
               & geo["geolocation_lng"].between(-180, 180))
    # Mediana reduz o efeito de coordenadas atipicas dentro do mesmo prefixo.
    return geo.loc[validas].groupby("geolocation_zip_code_prefix", as_index=False).agg(
        latitude=("geolocation_lat", "median"),
        longitude=("geolocation_lng", "median"),
    )


def distancia_km(lat1, lon1, lat2, lon2):
    """Haversine: distancia em linha geodesica, nao percurso rodoviario."""
    lat1, lon1, lat2, lon2 = [np.radians(x.astype(float)) for x in (lat1, lon1, lat2, lon2)]
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def categoria_predominante(itens: pd.DataFrame) -> pd.DataFrame:
    contagens = (itens.groupby(["order_id", "product_category_name"])
                 .size().rename("itens_categoria").reset_index())
    # Empate: ordem alfabetica. Nao descartar itens da tabela original.
    return (contagens.sort_values(["order_id", "itens_categoria", "product_category_name"],
                                  ascending=[True, False, True])
            .drop_duplicates("order_id")[["order_id", "product_category_name"]]
            .rename(columns={"product_category_name": "categoria_principal"}))


def resumir_itens(itens, produtos, vendedores, geo, pedidos):
    detalhes = itens.merge(produtos, on="product_id", how="left", validate="many_to_one")
    peso = detalhes["product_weight_g"]
    detalhes["peso_valido"] = peso.where(peso > 0)
    dimensoes = ["product_length_cm", "product_height_cm", "product_width_cm"]
    medidas_validas = detalhes[dimensoes].gt(0).all(axis=1)
    detalhes["volume_valido"] = detalhes[dimensoes].prod(axis=1, min_count=3).where(medidas_validas)
    detalhes["sem_peso"] = detalhes["peso_valido"].isna().astype(int)
    detalhes["sem_dimensoes"] = detalhes["volume_valido"].isna().astype(int)
    detalhes["sem_categoria"] = detalhes["product_category_name"].isna().astype(int)
    resumo = detalhes.groupby("order_id", as_index=False).agg(
        quantidade_itens=("order_item_id", "size"),
        quantidade_produtos=("product_id", "nunique"),
        quantidade_vendedores=("seller_id", "nunique"),
        quantidade_categorias=("product_category_name", "nunique"),
        valor_itens=("price", "sum"), valor_frete=("freight_value", "sum"),
        peso_total_g=("peso_valido", "sum"), volume_total_cm3=("volume_valido", "sum"),
        itens_sem_peso=("sem_peso", "sum"), itens_sem_dimensoes=("sem_dimensoes", "sum"),
        itens_sem_categoria=("sem_categoria", "sum"),
    )
    # Uma soma parcial nao representa o peso/volume total do pedido.
    resumo.loc[resumo["itens_sem_peso"] > 0, "peso_total_g"] = np.nan
    resumo.loc[resumo["itens_sem_dimensoes"] > 0, "volume_total_cm3"] = np.nan
    resumo = resumo.merge(categoria_predominante(detalhes), on="order_id", how="left", validate="one_to_one")

    # Cada vendedor aparece uma vez por pedido para nao ponderar a distancia
    # acidentalmente pela quantidade de itens vendidos.
    # AVALIAR SE REALMENTE É NECESSÁRIO
    origens = itens[["order_id", "seller_id"]].drop_duplicates()
    origens = origens.merge(vendedores, on="seller_id", how="left", validate="many_to_one")
    origens = origens.merge(geo.rename(columns={"geolocation_zip_code_prefix": "seller_zip_code_prefix",
                            "latitude": "seller_latitude", "longitude": "seller_longitude"}),
        on="seller_zip_code_prefix", how="left", validate="many_to_one")
    origens = origens.merge(pedidos[["order_id", "customer_latitude", "customer_longitude"]],
                            on="order_id", how="left", validate="many_to_one")
    origens["distancia_km"] = distancia_km(
        origens["customer_latitude"], origens["customer_longitude"],
        origens["seller_latitude"], origens["seller_longitude"])
    origens["sem_distancia"] = origens["distancia_km"].isna().astype(int)
    origens["sem_uf"] = origens["seller_state"].isna().astype(int)
    rotas = origens.groupby("order_id", as_index=False).agg(
        quantidade_ufs_origem=("seller_state", "nunique"),
        uf_origem=("seller_state", "first"),
        vendedores_sem_uf=("sem_uf", "sum"),
        distancia_media_vendedores_km=("distancia_km", "mean"), # É REALMENTE NECESSÁRIO?
        distancia_max_vendedores_km=("distancia_km", "max"),
        vendedores_sem_distancia=("sem_distancia", "sum"),
        vendedores_ids=("seller_id", lambda s: "|".join(sorted(s))),
    )
    rotas.loc[rotas["quantidade_ufs_origem"] > 1, "uf_origem"] = "MULTIPLAS"
    rotas.loc[rotas["vendedores_sem_uf"] > 0, "uf_origem"] = pd.NA
    return resumo.merge(rotas, on="order_id", how="left", validate="one_to_one")


def resumir_pagamentos(pagamentos: pd.DataFrame) -> pd.DataFrame:
    resumo = pagamentos.groupby("order_id", as_index=False).agg(
        valor_pago=("payment_value", "sum"),
        quantidade_pagamentos=("payment_sequential", "size"),
        quantidade_formas_pagamento=("payment_type", "nunique"),
        parcelas_maximas=("payment_installments", "max"),
    )
    por_tipo = pagamentos.groupby(["order_id", "payment_type"], as_index=False)["payment_value"].sum()
    principal = (por_tipo.sort_values(["order_id", "payment_value", "payment_type"],
                                      ascending=[True, False, True])
                 .drop_duplicates("order_id")[["order_id", "payment_type"]]
                 .rename(columns={"payment_type": "tipo_pagamento_principal"}))
    return resumo.merge(principal, on="order_id", how="left", validate="one_to_one")


def adicionar_tempos_e_alvos(base: pd.DataFrame, *, comparar_timestamp=False) -> pd.DataFrame:
    base = base.copy()
    compra = base["order_purchase_timestamp"]
    aprovacao = base["order_approved_at"]
    despacho = base["order_delivered_carrier_date"]
    entrega = base["order_delivered_customer_date"]
    promessa = base["order_estimated_delivery_date"]
    base["prazo_prometido_dias"] = (promessa.dt.normalize() - aprovacao.dt.normalize()).dt.days.astype("Int64")
    base["tempo_aprovacao_horas"] = (aprovacao - compra).dt.total_seconds() / 3600
    base["dia_semana_aprovacao"] = aprovacao.dt.day_of_week.astype("Int64")
    base["mes_aprovacao"] = aprovacao.dt.month.astype("Int64")
    base["hora_aprovacao"] = aprovacao.dt.hour.astype("Int64")

    # Campos exclusivamente retrospectivos, fora de COLUNAS_PREVISAO.
    observado = (base["order_status"].eq("delivered") & entrega.notna()
                 & promessa.notna() & compra.notna() & entrega.ge(compra))
    diferenca = (entrega.dt.normalize() - promessa.dt.normalize()).dt.days
    base["diferenca_entrega_prazo_dias"] = diferenca.where(observado).astype("Int64")
    base["dias_atraso"] = diferenca.clip(lower=0).where(observado).astype("Int64")
    # O contrato novo compara timestamps; o padrão preserva os notebooks legados.
    atraso = entrega.gt(promessa) if comparar_timestamp else diferenca.gt(0)
    base["atrasou"] = atraso.where(observado).astype("Int64")
    base["rotulo_disponivel"] = observado.astype(int)
    cronologia = (compra.notna() & aprovacao.notna() & promessa.notna()
                  & aprovacao.ge(compra)
                  & promessa.dt.normalize().ge(aprovacao.dt.normalize()))
    base["elegivel_modelagem"] = (observado & cronologia & entrega.ge(aprovacao)).astype(int)
    base["entrega_anterior_aprovacao"] = (entrega.notna() & aprovacao.notna() & entrega.lt(aprovacao)).astype(int)
    base["prazo_anterior_aprovacao"] = (promessa.notna() & aprovacao.notna()
                                          & promessa.dt.normalize().lt(aprovacao.dt.normalize())).astype(int)
    for nome, inicio, fim in [
        ("tempo_ate_despacho_dias", aprovacao, despacho),
        ("tempo_transporte_dias", despacho, entrega),
        ("tempo_entrega_dias", aprovacao, entrega),
    ]:
        duracao = (fim - inicio).dt.total_seconds() / 86400
        base[nome] = duracao.where(duracao.ge(0))
    return base


def validar_resultado(base, pedidos, itens, pagamentos):
    validar_chave(base, ["order_id"], "Base consolidada")
    exigir(len(base) == len(pedidos), "A quantidade de pedidos mudou.")
    exigir(set(base["order_id"]) == set(pedidos["order_id"]), "Pedidos perdidos ou adicionados.")
    for coluna, original in [("valor_itens", itens["price"]), ("valor_frete", itens["freight_value"]),
                             ("valor_pago", pagamentos["payment_value"])]:
        exigir(np.isclose(base[coluna].sum(), original.sum(), atol=0.005, rtol=0),
               f"Total monetario alterado: {coluna}.")
    exigir(base["quantidade_itens"].sum() == len(itens), "Itens perdidos ou multiplicados.")
    exigir(base["quantidade_pagamentos"].sum() == len(pagamentos), "Pagamentos perdidos ou multiplicados.")
    exigir(base.loc[base["rotulo_disponivel"].eq(0), ["atrasou", "dias_atraso"]].isna().all().all(),
           "Um pedido sem desfecho recebeu rotulo.")
    exigir(base.loc[base["atrasou"].eq(0), "dias_atraso"].eq(0).all(), "Atraso incoerente.")
    exigir(base.loc[base["atrasou"].eq(1), "dias_atraso"].gt(0).all(), "Atraso incoerente.")
    exigir(set(COLUNAS_PREVISAO).issubset(base.columns), "Faltam entradas previstas.")


def construir_dataset(pasta: Path = PASTA_ORIGINAIS):
    fontes = hash_arquivos(pasta)
    exigir(len(fontes) == 9, "Esperados os nove CSVs originais da Olist na pasta de entrada.")
    pedidos = ler("olist_orders_dataset.csv", pasta)
    itens = ler("olist_order_items_dataset.csv", pasta)
    pagamentos = ler("olist_order_payments_dataset.csv", pasta)
    produtos = ler("olist_products_dataset.csv", pasta)
    clientes = ler("olist_customers_dataset.csv", pasta)
    vendedores = ler("olist_sellers_dataset.csv", pasta)
    geo = ler("olist_geolocation_dataset.csv", pasta)
    for tabela, colunas, nome in [
        (pedidos, ["order_id"], "Pedidos"), (itens, ["order_id", "order_item_id"], "Itens"),
        (pagamentos, ["order_id", "payment_sequential"], "Pagamentos"),
        (produtos, ["product_id"], "Produtos"), (clientes, ["customer_id"], "Clientes"),
        (vendedores, ["seller_id"], "Vendedores"),
    ]:
        validar_chave(tabela, colunas, nome)
    for tabela, nome in [(itens, "Itens"), (pagamentos, "Pagamentos")]:
        exigir(tabela["order_id"].isin(pedidos["order_id"]).all(), f"{nome}: pedido sem correspondencia.")
    # Impedir somas parciais de valores monetarios ausentes.
    exigir(itens[["price", "freight_value"]].notna().all().all(), "Valores de itens/frete ausentes.")
    exigir(pagamentos["payment_value"].notna().all(), "Valores de pagamento ausentes.")
    datas = [c for c in pedidos if c.endswith("_date") or c.endswith("_timestamp") or c == "order_approved_at"]
    for coluna in datas:
        pedidos[coluna] = pd.to_datetime(pedidos[coluna], errors="raise")
    for tabela, coluna in [(clientes, "customer_zip_code_prefix"), (vendedores, "seller_zip_code_prefix")]:
        tabela[coluna] = tabela[coluna].str.zfill(5)
    coords = coordenadas_por_cep(geo)
    base = pedidos.merge(clientes, on="customer_id", how="left", validate="many_to_one")
    base = base.merge(coords.rename(columns={"geolocation_zip_code_prefix": "customer_zip_code_prefix",
                                            "latitude": "customer_latitude", "longitude": "customer_longitude"}),
                      on="customer_zip_code_prefix", how="left", validate="many_to_one")
    resumo = resumir_itens(itens, produtos, vendedores, coords, base)
    base = base.merge(resumo, on="order_id", how="left", validate="one_to_one")
    base = base.merge(resumir_pagamentos(pagamentos), on="order_id", how="left", validate="one_to_one")
    base = adicionar_tempos_e_alvos(base)
    for coluna in base:
        if coluna.startswith(("quantidade_", "itens_sem_", "vendedores_sem_")) or coluna == "parcelas_maximas":
            base[coluna] = base[coluna].astype("Int64")
    for coluna in ["customer_latitude", "customer_longitude"]:
        base[coluna] = base[coluna].round(6)
    for coluna in ["distancia_media_vendedores_km", "distancia_max_vendedores_km"]:
        base[coluna] = base[coluna].round(3)
    validar_resultado(base, pedidos, itens, pagamentos)
    exigir(fontes == hash_arquivos(pasta), "Os originais mudaram durante a execucao.")
    resumo_execucao = [
        "VALIDACAO DO DATASET CONSOLIDADO - Olist / EntregaCerta AI",
        "Fonte: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "Licenca documentada: CC BY-NC-SA 4.0. Registros reais anonimizados (2016-2018).",
        f"Pandas {pd.__version__}; NumPy {np.__version__}",
        f"Pedidos originais: {len(pedidos)}",
        f"Linhas consolidadas: {len(base)}; colunas: {len(base.columns)}",
        f"Pedidos duplicados: {base['order_id'].duplicated().sum()}",
        f"Sem itens: {base['quantidade_itens'].isna().sum()}",
        f"Sem pagamento: {base['quantidade_pagamentos'].isna().sum()}",
        f"Com varios vendedores: {base['quantidade_vendedores'].gt(1).sum()}",
        f"Pedidos com peso total desconhecido: {base['peso_total_g'].isna().sum()}",
        f"Pedidos sem nenhuma distancia disponivel: {base['distancia_max_vendedores_km'].isna().sum()}",
        f"Pedidos com ao menos um vendedor sem distancia: {base['vendedores_sem_distancia'].gt(0).sum()}",
        f"Pedidos com distancia apenas parcialmente disponivel: {(base['vendedores_sem_distancia'].gt(0) & base['vendedores_sem_distancia'].lt(base['quantidade_vendedores'])).sum()}",
        f"Com entrega anterior a aprovacao: {base['entrega_anterior_aprovacao'].sum()}",
        f"Com promessa anterior ao dia da aprovacao: {base['prazo_anterior_aprovacao'].sum()}",
        f"Rotulos observados: {base['rotulo_disponivel'].sum()}",
        f"Sem rotulo: {base['atrasou'].isna().sum()}",
        f"Atrasados observados: {base['atrasou'].eq(1).sum()}",
        f"Elegiveis inicialmente para modelagem: {base['elegivel_modelagem'].sum()}",
        "Chaves, quantidade de pedidos/itens/pagamentos e totais monetarios: OK.",
        "Hashes dos nove originais conferidos antes/depois: OK.",
        "Avaliacoes e traducao de categorias preservadas, mas nao usadas na consolidacao.",
        "Nao houve treinamento, imputacao de datas/rotulos, carga SQL ou avaliacao de modelo.",
        "",
        "Entradas candidatas na aprovacao (disponibilidade historica ainda e uma hipotese):",
        ", ".join(COLUNAS_PREVISAO),
        "",
        "SHA-256 DOS ORIGINAIS:",
        *[f"{nome}: {digest}" for nome, digest in fontes.items()],
    ]
    return base, "\n".join(resumo_execucao) + "\n"


def main():
    base, relatorio = construir_dataset()
    temporario = SAIDA.with_suffix(".csv.tmp")
    base.to_csv(temporario, index=False, encoding="utf-8", date_format="%Y-%m-%d %H:%M:%S")
    reaberto = pd.read_csv(temporario, dtype={"customer_zip_code_prefix": "string"})
    exigir(len(reaberto) == len(base), "Falha na reabertura do CSV.")
    validar_chave(reaberto, ["order_id"], "CSV reaberto")
    exigir(reaberto["atrasou"].isna().equals(base["atrasou"].isna()), "Rotulos alterados na gravacao.")
    temporario.replace(SAIDA)
    RELATORIO.write_text(relatorio + "Reabertura do CSV e preservacao de rotulos ausentes: OK.\n", encoding="utf-8")
    print(relatorio.split("Entradas candidatas")[0])
    print("CSV criado:", SAIDA)
    print("Registro de validacao:", RELATORIO)


if __name__ == "__main__":
    main()
