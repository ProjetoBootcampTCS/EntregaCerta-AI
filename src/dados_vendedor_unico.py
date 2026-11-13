"""Adapta as rotinas existentes: filtro bruto, geografia e histórico as-of."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .contratos_olist import (CATEGORICAS, CLEAN_COLUMNS, CTGAN_FEATURES, HISTORICOS,
                             adicionar_razoes, validar_limpo)
from .preparar_dados import (adicionar_tempos_e_alvos, coordenadas_por_cep, exigir,
                            hash_arquivos, ler, resumir_itens, validar_chave)
from .tratar_dados_ml import limpar_atributos, selecionar_coorte, separar_por_tempo


def mapear_vendedor_unico(itens):
    validar_chave(itens, ["order_id", "order_item_id"], "Itens brutos")
    ids = itens[["order_id", "seller_id"]].copy()
    ids["seller_id"] = ids.seller_id.replace(r"^\s*$", np.nan, regex=True)
    contagem = ids.groupby("order_id").seller_id.nunique()
    incompletos = ids.loc[ids.seller_id.isna(), "order_id"]
    aceitos = contagem.index[contagem.eq(1)].difference(incompletos)
    mapa = ids.loc[ids.order_id.isin(aceitos)].drop_duplicates()
    validar_chave(mapa, ["order_id"], "Mapa de vendedor único")
    return mapa, contagem


def preparar_fontes(pasta, corte_validacao, corte_teste, legado=None):
    """Atribui splits com as regras existentes, ainda antes do enriquecimento."""
    pasta = Path(pasta)
    fontes = {nome: ler(f"olist_{nome}_dataset.csv", pasta) for nome in
              ["orders", "order_items", "order_reviews", "sellers", "customers", "products"]}
    pedidos, itens = fontes["orders"].copy(), fontes["order_items"]
    validar_chave(pedidos, ["order_id"], "Pedidos brutos")
    for c in pedidos.columns:
        if c.endswith(("_date", "_at", "_timestamp")):
            pedidos[c] = pd.to_datetime(pedidos[c], errors="coerce")
    fontes["orders"] = pedidos.copy()
    mapa, contagem = mapear_vendedor_unico(itens)
    fontes["mapa"] = mapa
    pedidos["quantidade_itens"] = pedidos.order_id.map(itens.groupby("order_id").size()).fillna(0)
    pedidos["n_sellers_bruto"] = pedidos.order_id.map(contagem).fillna(0).astype(int)
    pedidos = adicionar_tempos_e_alvos(pedidos, comparar_timestamp=True)
    pedidos["grupo_sellers"] = np.select([pedidos.n_sellers_bruto.eq(0), pedidos.n_sellers_bruto.eq(1)],
                                         ["0", "1"], default=">=2")
    grupos = []
    for grupo, df in pedidos.groupby("grupo_sellers"):
        grupos.append({"sellers": grupo, "pedidos": len(df), "proporcao": len(df) / len(pedidos),
                       "atrasos": int(df.atrasou.eq(1).sum()), "no_prazo": int(df.atrasou.eq(0).sum()),
                       "sem_rotulo": int(df.atrasou.isna().sum())})
    registro = []
    coorte = selecionar_coorte(pedidos, registro, comparar_timestamp=True)
    coorte, purgas = separar_por_tempo(coorte, pd.Timestamp(corte_validacao), pd.Timestamp(corte_teste))
    splits = []
    for parte, df in coorte.groupby("particao", sort=False):
        mantidos = df.order_id.isin(mapa.order_id)
        for status, grupo in [("antes", df), ("mantidos", df.loc[mantidos]), ("excluidos", df.loc[~mantidos])]:
            splits.append({"particao": parte, "status": status, "pedidos": len(grupo),
                           "proporcao_split_original": len(grupo) / len(df),
                           "atrasos": int(grupo.atrasou.sum()), "no_prazo": int(grupo.atrasou.eq(0).sum()),
                           "prevalencia": float(grupo.atrasou.mean()) if len(grupo) else None})
    auditoria = {"pedidos_brutos": len(pedidos), "pedidos_duplicados": int(pedidos.order_id.duplicated().sum()),
                 "sellers_brutos": grupos, "splits": splits, "coorte": registro, "purga": purgas,
                 "hashes_fontes": hash_arquivos(pasta),
                 "rotulos_diferentes_do_calendario": int((pedidos.atrasou.eq(1)
                    & pedidos.order_delivered_customer_date.dt.normalize().eq(pedidos.order_estimated_delivery_date.dt.normalize())).sum()),
                 "multi_itens_single_seller_bruto": int((pedidos.order_id.isin(mapa.order_id) & pedidos.quantidade_itens.gt(1)).sum())}
    # O legado serve só para conferir: não é fonte de IDs, rótulos ou imputações.
    if legado is not None and Path(legado).exists():
        anterior = pd.read_csv(legado)
        validar_chave(anterior, ["order_id"], "ML legado")
        comum = coorte.merge(anterior, on="order_id", suffixes=("", "_antigo"), validate="one_to_one")
        exigir(comum.particao.eq(comum.particao_antigo).all(), "Split legado divergente dos cortes configurados.")
        auditoria["legado"] = {"colunas": list(anterior.columns), "pedidos_comuns": len(comum),
            "rotulos_diferentes": int(comum.atrasou.ne(comum.atrasou_antigo).sum()),
            "contagem_sellers_divergente": int(comum.n_sellers_bruto.ne(comum.quantidade_vendedores).sum())
                if "quantidade_vendedores" in comum else None}
        if "uf_origem" in comum:
            conferir = comum.loc[comum.order_id.isin(mapa.order_id)].merge(mapa, on="order_id", validate="one_to_one")
            conferir = conferir.merge(fontes["sellers"][["seller_id", "seller_state"]], on="seller_id", validate="many_to_one")
            auditoria["legado"]["uf_origem_divergente_cadastro"] = int(
                (conferir.uf_origem.notna() & conferir.seller_state.notna() & conferir.uf_origem.ne(conferir.seller_state)).sum())
        if {"distancia_media_vendedores_km", "distancia_max_vendedores_km"} <= set(comum):
            unico = comum.loc[comum.order_id.isin(mapa.order_id)]
            auditoria["legado"]["distancias_media_max_divergentes_single_seller"] = int((~np.isclose(
                unico.distancia_media_vendedores_km, unico.distancia_max_vendedores_km, atol=.001, rtol=0, equal_nan=True)).sum())
    filtrado = coorte.merge(mapa, on="order_id", how="inner", validate="one_to_one")
    fontes["filtrado"] = filtrado
    return fontes, auditoria


def historicos_asof(alvos, pedidos, mapa, reviews):
    """Review é proxy da experiência do pedido; disponibilidade = resposta.

    Eventos de qualquer split são permitidos apenas quando estritamente passados.
    Identidades com pedidos/notas conflitantes são excluídas, não multiplicadas.
    """
    eventos = reviews[["review_id", "order_id", "review_score", "review_answer_timestamp", "review_creation_date"]].copy()
    inicial = len(eventos)
    eventos["review_score"] = pd.to_numeric(eventos.review_score, errors="coerce")
    for c in ["review_answer_timestamp", "review_creation_date"]:
        eventos[c] = pd.to_datetime(eventos[c], errors="coerce")
    identidade = eventos.groupby("review_id")[["order_id", "review_score"]].nunique()
    ambiguos = identidade.index[identidade.gt(1).any(axis=1)]
    eventos = eventos.loc[eventos.review_id.notna() & ~eventos.review_id.isin(ambiguos)]
    eventos = eventos.merge(mapa, on="order_id", how="inner", validate="many_to_one")
    eventos = eventos.merge(pedidos[["order_id", "order_approved_at"]], on="order_id", validate="many_to_one")
    validos = (eventos.review_score.between(1, 5) & eventos.review_score.eq(np.floor(eventos.review_score))
               & eventos.review_answer_timestamp.notna() & eventos.review_creation_date.notna()
               & eventos.review_answer_timestamp.ge(eventos.review_creation_date)
               & eventos.review_answer_timestamp.gt(eventos.order_approved_at))
    invalidos = int((~validos).sum())
    eventos = eventos.loc[validos].sort_values(["review_answer_timestamp", "review_id", "order_id"])
    duplicados = int(eventos.duplicated("review_id").sum())
    eventos = eventos.drop_duplicates("review_id")
    saida = alvos.copy().reset_index(drop=True)
    saida[HISTORICOS[0]], saida[HISTORICOS[1]], saida[HISTORICOS[2]] = np.nan, 0, np.nan
    por_seller = {seller: grupo for seller, grupo in eventos.groupby("seller_id", sort=False)}
    for seller, grupo in saida.groupby("seller_id", sort=False):
        ev = por_seller.get(seller)
        if ev is None:
            continue
        datas = ev.review_answer_timestamp.to_numpy(dtype="datetime64[ns]")
        n = np.searchsorted(datas, pd.to_datetime(grupo.order_approved_at).to_numpy(dtype="datetime64[ns]"), side="left")
        notas = np.r_[0., ev.review_score.cumsum().to_numpy()]
        baixas = np.r_[0., ev.review_score.le(3).cumsum().to_numpy()]
        # Um evento próprio passou pelo filtro resposta > aprovação: nunca pode
        # preceder a aprovação desse mesmo pedido, mesmo em fontes malformadas.
        saida.loc[grupo.index, HISTORICOS[1]] = n
        saida.loc[grupo.index, HISTORICOS[0]] = np.divide(notas[n], n, out=np.full(len(n), np.nan), where=n > 0)
        saida.loc[grupo.index, HISTORICOS[2]] = np.divide(baixas[n], n, out=np.full(len(n), np.nan), where=n > 0)
    relatorio = {"reviews_brutas": inicial, "identidades_ambiguas_excluidas": len(ambiguos),
                 "datas_ou_notas_invalidas": invalidos, "duplicatas_removidas": duplicados,
                 "eventos_validos_unicos": len(eventos), "pedidos_sem_historico": int(saida[HISTORICOS[1]].eq(0).sum()),
                 "politica": "answer_timestamp < aprovacao; resposta > aprovacao de origem; sem reviews sintéticas; identidade review_id; conflitos excluidos"}
    return saida, relatorio


def enriquecer(fontes, pasta):
    base = fontes["filtrado"].copy()
    # Filtro ocorre antes de qualquer agregação de produtos/geografia/histórico.
    itens = fontes["order_items"].loc[fontes["order_items"].order_id.isin(base.order_id)]
    produtos = fontes["products"].copy()
    produtos["product_category_name"] = produtos.product_category_name.fillna("nao_informado")
    for nome, chave in [("customers", "customer_id"), ("sellers", "seller_id"), ("products", "product_id")]:
        validar_chave(fontes[nome], [chave], nome)
    exigir(itens.product_id.isin(produtos.product_id).all(), "Produto sem cadastro; revisar a fonte.")
    geo = ler("olist_geolocation_dataset.csv", Path(pasta))
    plausivel = geo.geolocation_lat.between(-34, 6) & geo.geolocation_lng.between(-74, -28)
    coords = coordenadas_por_cep(geo.loc[plausivel])
    clientes, vendedores = fontes["customers"].copy(), fontes["sellers"].copy()
    for df, c in [(clientes, "customer_zip_code_prefix"), (vendedores, "seller_zip_code_prefix")]:
        df[c] = df[c].str.zfill(5)
    base = base.merge(clientes, on="customer_id", how="left", validate="many_to_one")
    base = base.merge(coords.rename(columns={"geolocation_zip_code_prefix": "customer_zip_code_prefix",
                                            "latitude": "customer_latitude", "longitude": "customer_longitude"}),
                      on="customer_zip_code_prefix", how="left", validate="many_to_one")
    resumo = resumir_itens(itens, produtos, vendedores, coords, base)
    base = base.drop(columns="quantidade_itens").merge(resumo, on="order_id", validate="one_to_one")
    base = base.merge(vendedores[["seller_id", "seller_state"]], on="seller_id", how="left", validate="many_to_one")
    divergencia = base.uf_origem.notna() & base.seller_state.notna() & base.uf_origem.ne(base.seller_state)
    exigir(not divergencia.any(), "UF agregada diverge do cadastro do seller.")
    exigir(base.quantidade_vendedores.eq(1).all(), "Agregação misturou sellers.")
    exigir(np.allclose(base.distancia_media_vendedores_km, base.distancia_max_vendedores_km, equal_nan=True), "Distâncias divergentes para seller único.")
    base["distancia_vendedor_cliente_km"] = base.distancia_max_vendedores_km
    colunas_base = [c for c in CTGAN_FEATURES if c not in HISTORICOS]
    x, invalidos = limpar_atributos(base, colunas=colunas_base, categoricas=CATEGORICAS)
    faltantes = x.isna().sum().astype(int).to_dict()
    treino = base.particao.eq("treino")
    exigir(treino.any(), "Treino vazio após filtro.")
    imputacao = {}
    for c in colunas_base:
        conhecidos = x.loc[treino, c].dropna()
        exigir(len(conhecidos) > 0, f"Sem suporte de treino para imputar {c}.")
        valor = conhecidos.mode().iloc[0] if c in CATEGORICAS else conhecidos.median()
        imputacao[c] = valor
        x[c] = x[c].fillna(valor)
    base[colunas_base] = x
    base, hist = historicos_asof(base, fontes["orders"], fontes["mapa"], fontes["order_reviews"])
    base = adicionar_razoes(base)
    base["origem_dado"] = "real"
    for c in ["quantidade_itens", "quantidade_produtos", "quantidade_categorias", HISTORICOS[1]]:
        base[c] = base[c].astype(int)
    base = base[CLEAN_COLUMNS].reset_index(drop=True)
    validar_limpo(base)
    return base, {"ausencias_antes_imputacao": faltantes, "invalidos": invalidos,
                  "imputacao_treino": imputacao, "historico": hist,
                  "geo": {"coordenadas_fora_retangulo": int((~plausivel).sum()), "ufs_divergentes": int(divergencia.sum())},
                  "politica_categoria": "nao_informado conta como categoria distinta; empate alfabético",
                  "politica_ausencias": "Mediana/moda do treino; históricos sem reviews permanecem nulos; valor zero mantém razão nula."}
