"""Merges, engenharia e dataset ML; PLN somente para classes de atraso ausentes."""
from __future__ import annotations
import argparse
import json
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import sys
from importlib import import_module

# Os scripts numerados funcionam também quando executados fora da raiz do projeto.
sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

_dados = import_module("src.2_dados_treino")
ATRIBUTOS, sha256 = _dados.ATRIBUTOS, _dados.sha256
atribuir_particoes = _dados.atribuir_particoes
ATRIBUTOS_CALENDARIO = _dados.ATRIBUTOS_CALENDARIO
DATAS_TRANSPORTADORA = ["order_id", "order_delivered_carrier_date", "order_estimated_delivery_date"]
FERIADOS_DETALHES = "delivered_to_carrier_to_estimative_holiday_dates"
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


COLUNAS = {
    "customers": ["customer_id", "customer_zip_code_prefix", "customer_state"],
    "geolocation": ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"],
    "sellers": ["seller_id", "seller_zip_code_prefix", "seller_state"],
    "order_items": ["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"],
    "order_payments": ["order_id", "payment_sequential", "payment_installments", "payment_value"],
    "order_reviews": ["order_id", "review_score", "review_comment_title", "review_comment_message"],
    "orders": ["order_id", "customer_id", "order_delivered_carrier_date", "order_delivered_customer_date",
               "order_estimated_delivery_date", "order_status", "order_purchase_timestamp", "order_approved_at"],
    "products": ["product_id", "product_category_name", "product_weight_g", "product_length_cm",
                 "product_height_cm", "product_width_cm"],
}


def ler_fontes(pasta):
    return {nome: pd.read_csv(pasta / f"olist_{nome}_dataset.csv", usecols=colunas,
            dtype={c: "string" for c in colunas if c.endswith("_zip_code_prefix")})
            for nome, colunas in COLUNAS.items()}


def soma_completa(s):
    return s.sum(skipna=False) if len(s) else np.nan


def media_completa(s):
    return s.mean(skipna=False)


def textos(s):
    # JSON preserva separação, ordem e textos completos das avaliações.
    valores = s.dropna().tolist()
    return json.dumps(valores, ensure_ascii=False) if valores else pd.NA


def lista_json(s):
    return json.dumps([None if pd.isna(v) else v for v in s.tolist()], ensure_ascii=False)


def estatisticas_vendedores(fontes):
    # Uma venda é um pedido distinto associado ao vendedor, não uma linha de item.
    pares = fontes["order_items"][["order_id", "seller_id"]].drop_duplicates()
    vendas = pares.groupby("seller_id").order_id.nunique().rename("seller_sales_count")
    avaliacoes = pares.merge(fontes["order_reviews"][["order_id", "review_score"]], on="order_id", how="left")
    notas = avaliacoes.groupby("seller_id").agg(seller_review_score_mean=("review_score", "mean"),
                                               seller_reviews_count=("review_score", "count"))
    return vendas.to_frame().join(notas).reset_index()


def construir_merge(fontes):
    p = fontes["order_payments"].groupby("order_id", as_index=False).agg(
        payment_sequential=("payment_sequential", "max"),
        payment_installments=("payment_installments", "max"),
        payment_value=("payment_value", soma_completa))
    r = fontes["order_reviews"].groupby("order_id", as_index=False).agg(
        review_score=("review_score", media_completa),
        review_comment_title=("review_comment_title", textos),
        review_comment_message=("review_comment_message", textos))
    # Um ponto médio por CEP para não multiplicar linhas; sem filtro geográfico.
    geo = fontes["geolocation"].groupby("geolocation_zip_code_prefix", as_index=False).agg(
        geolocation_lat=("geolocation_lat", media_completa), geolocation_lng=("geolocation_lng", media_completa))
    itens = fontes["order_items"]
    unicos = itens.groupby("order_id").seller_id.nunique()
    itens = itens.loc[itens.order_id.isin(unicos[unicos.eq(1)].index)].copy()
    itens = itens.merge(fontes["products"], on="product_id", how="left", validate="many_to_one")
    itens = itens.sort_values(["order_id", "order_item_id"])
    regras = {c: lista_json for c in COLUNAS["products"]}
    regras.update(seller_id="first", price=soma_completa, freight_value=soma_completa)
    itens = itens.groupby("order_id", as_index=False).agg(regras)
    base = fontes["orders"].merge(itens, on="order_id", how="inner", validate="one_to_one")
    base = base.merge(fontes["customers"], on="customer_id", how="left", validate="many_to_one")
    base = base.merge(fontes["sellers"], on="seller_id", how="left", validate="many_to_one")
    for papel in ["customer", "seller"]:
        renomeadas = {c: f"{c}_{papel}" for c in geo}
        base = base.merge(geo.rename(columns=renomeadas), left_on=f"{papel}_zip_code_prefix",
                          right_on=f"geolocation_zip_code_prefix_{papel}", how="left", validate="many_to_one")
    base = base.merge(p, on="order_id", how="left", validate="many_to_one")
    return base.merge(r, on="order_id", how="left", validate="many_to_one")


def distancia_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = [np.radians(s.astype(float)) for s in (lat1, lon1, lat2, lon2)]
    a = np.sin((lat2-lat1)/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin((lon2-lon1)/2)**2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def categoria_predominante(s):
    contagens = s.dropna().value_counts()
    return sorted(contagens[contagens.eq(contagens.max())].index)[0] if len(contagens) else pd.NA


def adicionar_features_calendario(base, pedidos=None):
    """Features disponíveis no despacho, sem consultar a entrega ao cliente.

    Diferença assinada: despacho - estimativa, com frações de 24h.
    Contagens: (dia do despacho, dia estimado], sem contar o dia parcial do
    despacho. Intervalos vencidos/vazios têm zero dias restantes e feriados.
    Datas ausentes/inválidas permanecem ausentes, nunca viram zero.
    """
    import holidays

    resultado = base.copy()
    datas = base if pedidos is None else pedidos
    if pedidos is not None:
        for tabela in (base, pedidos):
            if tabela.order_id.isna().any() or tabela.order_id.duplicated().any():
                raise ValueError("Calendário exige order_id único e presente por linha.")
        if not base.order_id.isin(pedidos.order_id).all():
            raise ValueError("Há pedidos sem correspondência na fonte de datas do calendário.")
        datas = pedidos.set_index("order_id").reindex(base.order_id)
        datas.index = base.index
    despacho = pd.to_datetime(datas.order_delivered_carrier_date, errors="coerce", format="mixed")
    estimativa = pd.to_datetime(datas.order_estimated_delivery_date, errors="coerce", format="mixed")
    resultado[ATRIBUTOS_CALENDARIO[0]] = (despacho - estimativa).dt.total_seconds() / 86400
    resultado["delivered_to_carrier_week_day"] = despacho.dt.dayofweek.map(dict(enumerate(DIAS_SEMANA))).astype("string")
    for coluna in _dados.CONTAGENS_CALENDARIO:
        resultado[coluna] = pd.Series(pd.NA, index=base.index, dtype="Int64")
    resultado[FERIADOS_DETALHES] = pd.Series(pd.NA, index=base.index, dtype="string")

    conhecidas = pd.concat([despacho, estimativa]).dropna()
    if conhecidas.empty:
        return resultado
    # Inclui o ano seguinte para encontrar o próximo dia útil após 31/12.
    anos = range(int(conhecidas.dt.year.min()), int(conhecidas.dt.year.max()) + 2)
    feriados = holidays.country_holidays("BR", years=anos, categories=holidays.PUBLIC,
                                        subdiv=None, observed=False, language="pt_BR", expand=False)
    dias_feriados = np.array(sorted(feriados), dtype="datetime64[D]")
    calendario = np.busdaycalendar(weekmask="1111100", holidays=dias_feriados)
    um_dia = np.timedelta64(1, "D")

    tem_despacho = despacho.notna()
    inicio = despacho.loc[tem_despacho].to_numpy(dtype="datetime64[D]")
    resultado.loc[tem_despacho, "delivered_to_carrier_is_holiday"] = np.isin(inicio, dias_feriados).astype(int)
    proximo = np.busday_offset(inicio + um_dia, 0, roll="forward", busdaycal=calendario)
    resultado.loc[tem_despacho, "delivered_to_carrier_days_until_next_business_day"] = (proximo - inicio).astype(int)

    validas = tem_despacho & estimativa.notna()
    inicio = despacho.loc[validas].to_numpy(dtype="datetime64[D]")
    fim = estimativa.loc[validas].to_numpy(dtype="datetime64[D]")
    # np.busday_count exclui a extremidade final; deslocar ambas conta (início, fim].
    uteis = np.busday_count(inicio + um_dia, np.maximum(inicio, fim) + um_dia, busdaycal=calendario)
    resultado.loc[validas, "delivered_to_carrier_to_estimative_business_days"] = uteis
    esquerda = np.searchsorted(dias_feriados, inicio, side="right")
    direita = np.maximum(esquerda, np.searchsorted(dias_feriados, fim, side="right"))
    resultado.loc[validas, "delivered_to_carrier_to_estimative_holidays"] = direita - esquerda
    # Datas/nomes auditáveis ficam só no engineering; reusa intervalos iguais.
    descricoes = {}
    detalhes = []
    for a, b in zip(esquerda, direita):
        chave = (int(a), int(b))
        if chave not in descricoes:
            descricoes[chave] = json.dumps([
                {"data": str(d), "nome": feriados[d.astype(object)]} for d in dias_feriados[a:b]
            ], ensure_ascii=False)
        detalhes.append(descricoes[chave])
    resultado.loc[validas, FERIADOS_DETALHES] = detalhes
    return resultado


def registro_calendario(base):
    from importlib.metadata import version

    return {
        "biblioteca": "holidays", "versao": version("holidays"), "pais": "BR",
        "categoria": "PUBLIC", "subdivisao": None, "observed": False,
        "semana_util": "segunda a sexta", "datas": "horário local conforme a fonte Olist",
        "diferenca_dias": "(despacho - estimativa).total_seconds() / 86400; negativo = antecipação",
        "intervalo_contagens": "(dia do despacho, dia estimado]; vencido ou vazio = 0",
        "proximo_dia_util": "estritamente após o dia do despacho, mesmo se o despacho ocorreu em dia útil",
        "sem_data_transportadora": int(base.delivered_to_carrier_week_day.isna().sum()),
        "limites": "Calendário PUBLIC do Brasil (inclui Sexta-feira Santa), sem pontos facultativos ou feriados locais; não representa a escala real da transportadora.",
    }


def engenharia(merge, config, estatisticas):
    if merge.order_id.duplicated().any():
        raise ValueError("datasets_merge deve ter uma linha por pedido.")
    base = merge.copy()
    colunas_itens = COLUNAS["products"]
    itens = merge[["order_id"] + colunas_itens].copy()
    for c in colunas_itens:
        itens[c] = itens[c].map(json.loads)
    itens = itens.explode(colunas_itens, ignore_index=True)
    medidas = ["product_length_cm", "product_height_cm", "product_width_cm", "product_weight_g"]
    itens[medidas] = itens[medidas].astype(float)
    itens["volume"] = itens[medidas[:3]].prod(axis=1, min_count=3)
    resumo = itens.groupby("order_id", as_index=False).agg(
        qtd_items=("order_id", "size"), total_volume_cm3=("volume", soma_completa),
        total_weight=("product_weight_g", soma_completa),
        predominant_product_category_name=("product_category_name", categoria_predominante))
    base = base.merge(resumo, on="order_id", validate="one_to_one")
    for papel in ["customer", "seller"]:
        base = base.rename(columns={f"geolocation_lat_{papel}": f"{papel}_lat",
                                    f"geolocation_lng_{papel}": f"{papel}_lng"})
    base["distance_customer_seller"] = distancia_km(base.customer_lat, base.customer_lng, base.seller_lat, base.seller_lng)
    base = base.merge(estatisticas, on="seller_id", how="left", validate="many_to_one")
    base = base.drop(columns=colunas_itens + ["customer_zip_code_prefix", "seller_zip_code_prefix",
                       "geolocation_zip_code_prefix_customer", "geolocation_zip_code_prefix_seller"])
    compra = pd.to_datetime(base.order_purchase_timestamp, errors="coerce")
    for c in ["order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"]:
        base[c + "_in_days"] = (pd.to_datetime(base[c], errors="coerce") - compra).dt.total_seconds() / 86400
    origem = pd.Timestamp(config["origem_dias_compra"]) if config.get("origem_dias_compra") else compra.min()
    base["order_purchase_timestamp_in_days"] = (compra - origem).dt.total_seconds() / 86400
    base["approval_date_in_days"] = (pd.to_datetime(base.order_approved_at, errors="coerce") - compra).dt.total_seconds() / 86400
    base["delay_in_days"] = base.order_delivered_customer_date_in_days - base.order_estimated_delivery_date_in_days
    base["delay_status"] = base.delay_in_days.ge(1).astype("Int64").where(base.delay_in_days.notna())
    base = adicionar_features_calendario(base)
    return base.drop(columns=["order_delivered_carrier_date", "order_delivered_customer_date",
                              "order_estimated_delivery_date", "order_purchase_timestamp"]), str(origem)


def atribuir_transportadoras(base, config):
    quantidade = config.get("quantidade", 2)
    if isinstance(quantidade, bool) or not isinstance(quantidade, int) or quantidade < 1:
        raise ValueError("transportadoras.quantidade deve ser um inteiro positivo.")
    semente = config.get("semente", 42)
    # Sorteio determinístico por ID: independe da ordem das linhas e dos filtros.
    return base.order_id.map(lambda pedido: "transportadora_" + str(
        int.from_bytes(hashlib.sha256(f"{semente}:{pedido}".encode()).digest()[:8], "big") % quantidade + 1))


def confiabilidade_vendedor(base):
    max_vendas = base.seller_sales_count.max()
    vendas = base.seller_sales_count / max_vendas if max_vendas > 0 else base.seller_sales_count * 0
    return (base.seller_review_score_mean * .6 + vendas * 5 * .4).round(2)


def preencher_atrasos_pln(base, modelo):
    comentarios = import_module("src.1_pln").comentarios
    base = base.copy()
    ausentes = base.delay_status.isna()
    if "delay_status_source" not in base:
        base["delay_status_source"] = np.where(base.delay_in_days.notna(), "datas", "manual")
    preenchidos = pd.Series(False, index=base.index)
    textos = comentarios(base.loc[ausentes]) if ausentes.any() else pd.Series(dtype=str)
    textos = textos.loc[textos.ne("")]
    if len(textos):
        preenchidos.loc[textos.index] = modelo.predict(textos).astype(str) == "atrasado"
    base.loc[preenchidos, "delay_status"] = 1
    base.loc[preenchidos, "delay_status_source"] = "pln"
    # A PLN infere a classe, nunca inventa a duração do atraso.
    descartados = ausentes & ~preenchidos
    registro = {"rotulos_ausentes_entrada": int(ausentes.sum()), "preenchidos_pln": int(preenchidos.sum()),
                "descartados_sem_classificacao_atrasado": int(descartados.sum())}
    return base.loc[~descartados].copy(), registro


def configuracao_particoes(config):
    caminho = RAIZ / config.get("configuracao_treino", "src/configuracoes/2_treinamento.json")
    return json.loads(caminho.read_text(encoding="utf-8"))


def atualizar_somente_particoes(config):
    """Adiciona metadados aos CSVs já tratados, sem refazer engenharia ou limpeza."""
    saida = RAIZ / config.get("saida", "Dados")
    treino = configuracao_particoes(config)
    arquivos = [saida / nome for nome in ["datasets_engineering.csv", "dataset_ml.csv"]]
    faltantes = [str(p) for p in arquivos if not p.exists()]
    if faltantes:
        raise FileNotFoundError("CSVs necessários para atualizar partições: " + ", ".join(faltantes))
    tabelas = {}
    resumos = {}
    for p in arquivos:
        d = pd.read_csv(p, low_memory=False)
        tabelas[p], resumos[p.name] = atribuir_particoes(d, treino)
    registro_path = saida / "datasets_preparacao.json"
    registro = json.loads(registro_path.read_text(encoding="utf-8")) if registro_path.exists() else {}
    backup = saida / "experimentos" / ("antes_particoes_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    backup.mkdir(parents=True, exist_ok=False)
    for p in [*arquivos, registro_path]:
        if p.exists():
            shutil.copy2(p, backup / p.name)
    for p, d in tabelas.items():
        d.to_csv(p, index=False)
        r = resumos[p.name]
        print(f"{p.name}: {len(d)} pedidos preservados; {r['por_particao']}")
    registro["particoes"] = resumos
    registro.setdefault("sha256", {}).update({p.name: sha256(p) for p in arquivos})
    registro_path.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumos


def atualizar_somente_calendario(config):
    """Enriquece CSVs tratados por order_id, preservando linhas e demais valores."""
    saida = RAIZ / config.get("saida", "Dados")
    arquivos = [saida / nome for nome in ["datasets_engineering.csv", "dataset_ml.csv"]]
    faltantes = [str(p) for p in arquivos if not p.exists()]
    if faltantes:
        raise FileNotFoundError("CSVs necessários para atualizar calendário: " + ", ".join(faltantes))
    pedidos = pd.read_csv(RAIZ / config["originais"] / "olist_orders_dataset.csv", usecols=DATAS_TRANSPORTADORA)
    tabelas = {}
    for p in arquivos:
        d = adicionar_features_calendario(pd.read_csv(p, low_memory=False), pedidos)
        tabelas[p] = d.drop(columns=FERIADOS_DETALHES) if p.name == "dataset_ml.csv" else d
    registro_path = saida / "datasets_preparacao.json"
    registro = json.loads(registro_path.read_text(encoding="utf-8")) if registro_path.exists() else {}
    backup = saida / "experimentos" / ("antes_preparacao_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    backup.mkdir(parents=True, exist_ok=False)
    for p in [*arquivos, registro_path]:
        if p.exists():
            shutil.copy2(p, backup / p.name)
    # Completa a serialização antes de substituir arquivos já tratados.
    # A troca de cada arquivo é atômica; em caso de bloqueio, o backup permanece.
    for p, d in tabelas.items():
        d.to_csv(backup / (p.name + ".novo"), index=False)
    for p, d in tabelas.items():
        (backup / (p.name + ".novo")).replace(p)
        print(f"{p.name}: calendário atualizado; {len(d)} pedidos preservados.")
    registro["calendario_transportadora"] = registro_calendario(tabelas[arquivos[0]])
    registro["ausencias_engineering"] = tabelas[arquivos[0]].isna().sum().to_dict()
    registro["ausencias_ml"] = tabelas[arquivos[1]].isna().sum().to_dict()
    registro.setdefault("sha256", {}).update({p.name: sha256(p) for p in arquivos})
    registro_path.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Backup: {backup}")
    return tabelas[arquivos[0]], tabelas[arquivos[1]]


def executar(config_path=None, somente_particoes=False, somente_calendario=False):
    config_path = Path(config_path or RAIZ / "src/configuracoes/1_dados.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if somente_particoes:
        return atualizar_somente_particoes(config)
    if somente_calendario:
        return atualizar_somente_calendario(config)
    originais = RAIZ / config["originais"]
    saida = RAIZ / config.get("saida", "Dados")
    saida.mkdir(parents=True, exist_ok=True)
    arquivos = {nome: saida / nome for nome in ["datasets_merge.csv", "datasets_engineering.csv", "dataset_ml.csv"]}
    registro_path = saida / "datasets_preparacao.json"
    registro = json.loads(registro_path.read_text(encoding="utf-8")) if registro_path.exists() else {}
    if arquivos["datasets_engineering.csv"].exists():
        # Reutiliza o tratamento já feito pelo usuário; não remonta a base original.
        base = pd.read_csv(arquivos["datasets_engineering.csv"], low_memory=False)
        merge = pd.read_csv(arquivos["datasets_merge.csv"], low_memory=False) if arquivos["datasets_merge.csv"].exists() else None
        pedidos_calendario = pd.read_csv(originais / "olist_orders_dataset.csv", usecols=DATAS_TRANSPORTADORA)
        base = adicionar_features_calendario(base, pedidos_calendario)
    else:
        fontes = ler_fontes(originais)
        merge = construir_merge(fontes)
        base, origem = engenharia(merge, config, estatisticas_vendedores(fontes))
        registro.update(origem_dias_compra=origem, pedidos_originais=len(fontes["orders"]),
                        pedidos_excluidos_pelo_filtro_vendedor=len(fontes["orders"])-len(merge))
    if base.order_id.isna().any() or base.order_id.duplicated().any():
        raise ValueError("Engineering precisa ter um order_id único e presente por linha.")
    base["transportadora"] = atribuir_transportadoras(base, config.get("transportadoras", {}))
    base["seller_reliability_score"] = confiabilidade_vendedor(base)
    if merge is not None:
        merge["transportadora"] = atribuir_transportadoras(merge, config.get("transportadoras", {}))
    avaliacoes = pd.read_csv(originais / "olist_order_reviews_dataset.csv", usecols=[
        "order_id", "review_comment_title", "review_comment_message", "review_answer_timestamp"])
    relatorio_pln = None
    modelo = None
    if base.delay_status.isna().any():
        treinar_pln = import_module("src.1_pln").treinar_pln
        print("Ajustando a PLN legada para os rótulos ausentes...", flush=True)
        modelo, relatorio_pln = treinar_pln(avaliacoes, config.get("semente_pln", 42))
    base, resumo_pln = preencher_atrasos_pln(base, modelo)
    if "label_available_at" not in base:
        pedidos = pd.read_csv(originais / "olist_orders_dataset.csv", usecols=["order_id", "order_delivered_customer_date"])
        base["label_available_at"] = base.order_id.map(pedidos.set_index("order_id").order_delivered_customer_date)
    datas_reviews = pd.to_datetime(avaliacoes.review_answer_timestamp, errors="coerce").groupby(avaliacoes.order_id).max()
    base.loc[base.delay_status_source.eq("pln"), "label_available_at"] = base.loc[
        base.delay_status_source.eq("pln"), "order_id"].map(datas_reviews).astype(str)
    config_treino = configuracao_particoes(config)
    base, resumo_particoes = atribuir_particoes(base, config_treino)
    metadados = ["order_id", "order_approved_at", "delay_status_source", "label_available_at", "particao"]
    ml = base[metadados + ATRIBUTOS + ["delay_in_days", "delay_status"]].copy()
    
    # Salva a versão anterior antes de substituir qualquer CSV gerado.
    existentes = [p for p in [*arquivos.values(), registro_path] if p.exists()]
    if existentes:
        backup = saida / "experimentos" / ("antes_preparacao_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        backup.mkdir(parents=True, exist_ok=False)
        for p in existentes:
            shutil.copy2(p, backup / p.name)
    if merge is not None:
        merge.to_csv(arquivos["datasets_merge.csv"], index=False)
        
    base.to_csv(arquivos["datasets_engineering.csv"], index=False)
    
    # limpando vazios
    ml = ml[(ml['order_approved_at'].notna()) & (ml['predominant_product_category_name'].notna()) & (ml['seller_reliability_score'].notna()) & (ml['distance_customer_seller'].notna()) & (ml['total_weight'].notna())]
    _, resumo_particoes_ml = atribuir_particoes(ml, config_treino)
    ml.to_csv(arquivos["dataset_ml.csv"], index=False)
    
    registro.update(unidade_dias="segundos decorridos / 86400, com frações preservadas",
        calendario_transportadora=registro_calendario(base),
        filtro="exatamente um vendedor distinto", pedidos_engineering=len(base), pedidos_ml=len(ml),
        transportadoras=config.get("transportadoras", {"quantidade": 5, "semente": 42}),
        seller_reliability_score="round(seller_review_score_mean * 0.6 + seller_sales_count / max_vendas * 5 * 0.4, 2)",
        max_vendas=float(base.seller_sales_count.max()), pln=resumo_pln,
        particoes={"datasets_engineering.csv": resumo_particoes, "dataset_ml.csv": resumo_particoes_ml},
        ausencias_engineering=base.isna().sum().to_dict(), ausencias_ml=ml.isna().sum().to_dict(),
        sha256={nome: sha256(p) for nome, p in arquivos.items() if p.exists()},
        tratamento="PLN preenche somente delay_status ausente como 1; descarta demais classes ausentes. Sem imputação de atributos ou dias.")
    if relatorio_pln is not None:
        registro["avaliacao_pln"] = relatorio_pln
    registro_path.write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Engineering/ML: {len(base)} pedidos; PLN: {resumo_pln}. CTGAN e modelos de atraso não treinados.")
    for p in arquivos.values():
        print(p)
    return merge, base


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    atualizacao = parser.add_mutually_exclusive_group()
    atualizacao.add_argument("--somente-particoes", action="store_true", help="Atualizar apenas partições dos CSVs existentes, preservando seu tratamento.")
    atualizacao.add_argument("--somente-calendario", action="store_true", help="Adicionar/recalcular features de calendário nos CSVs existentes, preservando linhas e tratamento.")
    args = parser.parse_args()
    executar(args.config, args.somente_particoes, args.somente_calendario)
