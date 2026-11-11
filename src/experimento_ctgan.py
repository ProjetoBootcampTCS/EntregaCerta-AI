"""Experimento de aumento do treino. Nunca altera pedidos reais ou o modelo da API."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from psycopg import sql
from psycopg.types.json import Jsonb

from .carregar_postgresql import obter_conexao
from .preparar_dados import COLUNAS_PREVISAO
from .tratar_dados_ml import CATEGORICAS, NUMERICAS, limpar_atributos

RAIZ = Path(__file__).resolve().parents[1]
MAX_SINTETICOS = 10_000
VERSAO = "ctgan_aprovacao_v1"
CONSULTA = """
SELECT v.*, p.rotulo_disponivel_em::timestamp AS rotulo_disponivel_em,
       p.atrasou::integer AS atrasou
FROM public.vw_pedidos_inferencia v
JOIN public.pedidos p ON p.order_id = v.order_id
WHERE v.particao IN ('treino', 'validacao', 'teste')
ORDER BY v.order_approved_at, v.order_id
"""


def consultar_base():
    """Lê o snapshot tratado do PostgreSQL, sem fallback silencioso para CSV."""
    os.environ.setdefault("PGCONNECT_TIMEOUT", "5")
    with obter_conexao() as conexao, conexao.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute(CONSULTA)
        base = pd.DataFrame(cursor.fetchall(), columns=[c.name for c in cursor.description])
        cursor.execute("SELECT particao, count(*) FROM public.pedidos GROUP BY particao")
        contagens = dict(cursor.fetchall())
    if base.empty or not base.order_id.is_unique or base.order_id.isna().any():
        raise ValueError("Consulta vazia ou identificadores inválidos/duplicados.")
    if base.groupby("particao").size().to_dict() != contagens:
        raise ValueError("A view perdeu pedidos nas junções. Corrija antes do experimento.")
    if not base.atrasou.isin([0, 1]).all():
        raise ValueError("Alvo deve conter somente 0 e 1 observados.")
    for coluna in ["order_approved_at", "rotulo_disponivel_em"]:
        base[coluna] = pd.to_datetime(base[coluna], errors="raise")
        if base[coluna].isna().any():
            raise ValueError(f"Data ausente: {coluna}")
    cortes = {"treino": pd.Timestamp("2018-01-01"), "validacao": pd.Timestamp("2018-05-01")}
    for parte, limite in cortes.items():
        grupo = base.loc[base.particao.eq(parte)]
        if grupo.empty or not grupo.rotulo_disponivel_em.lt(limite).all():
            raise ValueError(f"Rótulo futuro em {parte}; revisar os cortes do banco.")
    esperado = np.where(base.order_approved_at.lt(cortes["treino"]), "treino",
                        np.where(base.order_approved_at.lt(cortes["validacao"]), "validacao", "teste"))
    if not np.array_equal(base.particao, esperado):
        raise ValueError("Partições do banco não correspondem aos cortes documentados.")
    x, _ = limpar_atributos(base)
    base[COLUNAS_PREVISAO] = x
    base["origem_dado"] = "real_olist"
    base["rotulo_observado"] = True
    return base.reset_index(drop=True)


def hash_base(base):
    colunas = ["order_id", "particao", "order_approved_at", "rotulo_disponivel_em", "atrasou"] + COLUNAS_PREVISAO
    texto = base.sort_values("order_id")[colunas].to_csv(index=False, float_format="%.12g")
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def ajustar_gerador(treino, epocas=300, semente=42):
    """Aprende P(X | atraso) exclusivamente dos atrasos REAIS do treino.

    Contagens relacionadas são uma categoria conjunta para preservar a composição
    dos pedidos. Não são gerados IDs, datas de entrega, dias de atraso ou avaliações.
    """
    import torch
    from ctgan import CTGAN

    if not treino.particao.eq("treino").all() or not treino.origem_dado.eq("real_olist").all():
        raise ValueError("O gerador só pode receber treino real.")
    reais = treino.loc[treino.atrasou.eq(1), COLUNAS_PREVISAO].copy().reset_index(drop=True)
    if len(reais) < 100:
        raise ValueError("Poucos atrasos reais para este experimento (mínimo 100).")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    torch.manual_seed(semente)
    tabela = reais.copy()
    faltantes = {}
    for c in NUMERICAS:
        if reais[c].isna().any():
            flag = "ausente__" + c
            tabela[flag] = reais[c].isna().astype(int)
            faltantes[c] = flag
    # A estrutura conjunta evita inventar mais vendedores/produtos do que itens.
    estrutura = [c for c in NUMERICAS if c.startswith(("quantidade_", "itens_sem_", "vendedores_sem_"))]
    estrutura += ["uf_origem"] + list(faltantes.values())
    chaves = tabela[estrutura].fillna("AUSENTE").astype(str).agg("|".join, axis=1)
    codigos, _ = pd.factorize(chaves, sort=True)
    tabela["estrutura_pedido"] = [f"E{x:04d}" for x in codigos]
    mapa = tabela[["estrutura_pedido"] + estrutura].drop_duplicates("estrutura_pedido").set_index("estrutura_pedido")
    tabela = tabela.drop(columns=estrutura)
    discretas = [c for c in CATEGORICAS if c in tabela] + ["estrutura_pedido"]
    discretas += ["dia_semana_aprovacao", "mes_aprovacao", "hora_aprovacao", "parcelas_maximas", "prazo_prometido_dias"]
    discretas = [c for c in discretas if c in tabela]
    continuas = [c for c in tabela if c not in discretas]
    for c in discretas:
        tabela[c] = tabela[c].fillna("AUSENTE").astype(str)
    # log1p atenua caudas longas; medianas aprendidas só nos atrasos de treino.
    for c in continuas:
        tabela[c] = np.log1p(tabela[c].fillna(reais[c].median() if reais[c].notna().any() else 0))
    constantes = {c: tabela[c].iloc[0] for c in tabela if tabela[c].nunique() == 1}
    tabela = tabela.drop(columns=list(constantes))
    discretas_fit = [c for c in discretas if c in tabela]
    gerador = CTGAN(epochs=epocas, batch_size=500, pac=10,
                   generator_dim=(128, 128), discriminator_dim=(128, 128),
                   verbose=False, enable_gpu=False)
    gerador.set_random_state(semente)
    gerador.fit(tabela, discrete_columns=discretas_fit)
    return {"gerador": gerador, "mapa": mapa, "constantes": constantes,
            "continuas": continuas, "faltantes": faltantes, "reais": reais,
            "epocas": epocas, "semente": semente}


def filtrar_candidatos(candidatos, reais):
    """Rejeita extremos fora do treino e incoerências, sem ajustar pelo teste."""
    bons = pd.Series(True, index=candidatos.index)
    for c in NUMERICAS:
        observado = reais[c].dropna()
        if observado.empty:
            bons &= candidatos[c].isna()
        else:
            bons &= candidatos[c].isna() | candidatos[c].between(observado.min(), observado.max())
    for c in CATEGORICAS:
        bons &= candidatos[c].isna() | candidatos[c].isin(reais[c].dropna().unique())
    media, maxima = candidatos.distancia_media_vendedores_km, candidatos.distancia_max_vendedores_km
    bons &= candidatos.quantidade_vendedores.eq(1) | media.isna() | maxima.isna() | media.le(maxima + 1e-8)
    # Para um único vendedor, as duas distâncias precisam coincidir.
    unico = candidatos.quantidade_vendedores.eq(1) & media.notna() & maxima.notna()
    candidatos = candidatos.copy()
    candidatos.loc[unico, "distancia_media_vendedores_km"] = maxima.loc[unico]
    # Projeção física documentada para esse caso; não ajusta o alvo nem scores.
    # Reaplicar limites após a projeção, sem cancelar rejeições de outras colunas.
    for c in NUMERICAS:
        r = reais[c].dropna()
        if not r.empty:
            bons &= candidatos[c].isna() | candidatos[c].between(r.min(), r.max())
    return candidatos.loc[bons, COLUNAS_PREVISAO].copy()


def gerar_atrasos(pacote, quantidade, experimento_id):
    if not isinstance(quantidade, int) or not 1 <= quantidade <= MAX_SINTETICOS:
        raise ValueError("Quantidade deve ser um inteiro entre 1 e 10.000.")
    reais = pacote["reais"]
    hashes_reais = set(pd.util.hash_pandas_object(reais, index=False))
    aceitos = pd.DataFrame(columns=COLUNAS_PREVISAO)
    tentados = 0
    for _ in range(40):
        bruto = pacote["gerador"].sample(max(1000, quantidade - len(aceitos)))
        tentados += len(bruto)
        for c, valor in pacote["constantes"].items():
            bruto[c] = valor
        bruto = bruto.join(pacote["mapa"], on="estrutura_pedido", validate="many_to_one")
        for c in pacote["continuas"]:
            bruto[c] = np.expm1(bruto[c].clip(upper=30))
        for c in NUMERICAS:
            bruto[c] = pd.to_numeric(bruto[c], errors="coerce")
        for c in CATEGORICAS:
            bruto[c] = bruto[c].replace("AUSENTE", np.nan)
        for c, flag in pacote["faltantes"].items():
            bruto.loc[bruto[flag].eq(1), c] = np.nan
        novos = filtrar_candidatos(bruto, reais)
        novos = novos.loc[~pd.util.hash_pandas_object(novos, index=False).isin(hashes_reais)]
        aceitos = pd.concat([aceitos, novos], ignore_index=True).drop_duplicates()
        if len(aceitos) >= quantidade:
            break
    if len(aceitos) < quantidade:
        raise RuntimeError(f"Só {len(aceitos)} candidatos válidos em {tentados}; nenhuma carga realizada.")
    sinteticos = aceitos.iloc[:quantidade].copy().reset_index(drop=True)
    sinteticos.insert(0, "order_id", [f"ctgan_{experimento_id}_{i:05d}" for i in range(quantidade)])
    sinteticos["particao"] = "treino"
    sinteticos["atrasou"] = 1  # Classe condicionante sintética; não é desfecho observado.
    sinteticos["origem_dado"] = "sintetico_ctgan"
    sinteticos["rotulo_observado"] = False
    sinteticos["experimento_id"] = experimento_id
    return sinteticos, {"candidatos_gerados": tentados, "sinteticos_aceitos": len(sinteticos)}


def validar_injecao(base, sinteticos):
    if not 1 <= len(sinteticos) <= MAX_SINTETICOS:
        raise ValueError("Limite de 10.000 registros sintéticos excedido ou lote vazio.")
    if (not sinteticos.order_id.is_unique or set(base.order_id) & set(sinteticos.order_id)
            or not sinteticos.order_id.str.startswith("ctgan_").all()):
        raise ValueError("IDs sintéticos inválidos ou colidindo com pedidos reais.")
    if not (sinteticos.particao.eq("treino") & sinteticos.atrasou.eq(1)
            & sinteticos.origem_dado.eq("sintetico_ctgan") & sinteticos.rotulo_observado.eq(False)).all():
        raise ValueError("Sintéticos devem ser atraso de treino explicitamente identificado.")
    if sinteticos.experimento_id.nunique() != 1:
        raise ValueError("O lote deve pertencer a um único experimento.")
    if sinteticos[COLUNAS_PREVISAO].duplicated().any():
        raise ValueError("Há linhas sintéticas duplicadas.")
    return True


def persistir_experimento(base, sinteticos, metadados):
    """Grava apenas o schema experimental; repetição não acumula o mesmo lote."""
    validar_injecao(base, sinteticos)
    experimento_id = sinteticos.experimento_id.iloc[0]
    campos = ["order_id"] + COLUNAS_PREVISAO + ["particao", "atrasou", "origem_dado", "rotulo_observado", "experimento_id"]
    lote = sinteticos[campos].astype(object).where(sinteticos[campos].notna(), None)
    checksum = hashlib.sha256(lote.to_csv(index=False).encode()).hexdigest()
    with obter_conexao() as conexao, conexao.cursor() as cursor:
        cursor.execute("CREATE SCHEMA IF NOT EXISTS experimentos_ctgan")
        cursor.execute("""CREATE TABLE IF NOT EXISTS experimentos_ctgan.execucoes (
            experimento_id TEXT PRIMARY KEY, criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            quantidade INTEGER NOT NULL CHECK (quantidade BETWEEN 1 AND 10000),
            checksum TEXT NOT NULL, metadados JSONB NOT NULL)""")
        definicoes = [sql.SQL("order_id TEXT PRIMARY KEY")]
        for c in COLUNAS_PREVISAO:
            tipo = sql.SQL("TEXT" if c in CATEGORICAS else "DOUBLE PRECISION")
            definicoes.append(sql.SQL("{} {}").format(sql.Identifier(c), tipo))
        definicoes.append(sql.SQL("""particao TEXT NOT NULL CHECK (particao = 'treino'),
            atrasou SMALLINT NOT NULL CHECK (atrasou = 1),
            origem_dado TEXT NOT NULL CHECK (origem_dado = 'sintetico_ctgan'),
            rotulo_observado BOOLEAN NOT NULL CHECK (NOT rotulo_observado),
            experimento_id TEXT NOT NULL REFERENCES experimentos_ctgan.execucoes(experimento_id)"""))
        cursor.execute(sql.SQL("CREATE TABLE IF NOT EXISTS experimentos_ctgan.pedidos ({})").format(sql.SQL(", ").join(definicoes)))
        # Registro imutável. Mesma chave com conteúdo diferente exige outro experimento.
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (experimento_id,))
        cursor.execute("SELECT checksum, quantidade FROM experimentos_ctgan.execucoes WHERE experimento_id=%s", (experimento_id,))
        anterior = cursor.fetchone()
        if anterior and anterior != (checksum, len(lote)):
            raise ValueError("Experimento já existe com conteúdo diferente; não será sobrescrito.")
        if not anterior:
            cursor.execute("INSERT INTO experimentos_ctgan.execucoes VALUES (%s, now(), %s, %s, %s)",
                           (experimento_id, len(lote), checksum, Jsonb(metadados)))
            comando = sql.SQL("COPY experimentos_ctgan.pedidos ({}) FROM STDIN").format(sql.SQL(", ").join(map(sql.Identifier, campos)))
            with cursor.copy(comando) as copia:
                for linha in lote.itertuples(index=False, name=None):
                    copia.write_row(linha)
        cursor.execute("SELECT count(*) FROM experimentos_ctgan.pedidos WHERE experimento_id=%s", (experimento_id,))
        if cursor.fetchone()[0] != len(lote):
            raise RuntimeError("Contagem da carga não corresponde ao lote.")
    combinado = pd.concat([base.assign(experimento_id=experimento_id), sinteticos], ignore_index=True)
    caminho = RAIZ / "Dados" / "pedidos_tratados_e_injetados.csv"
    temporario = caminho.with_suffix(".tmp")
    combinado.to_csv(temporario, index=False, encoding="utf-8-sig")
    temporario.replace(caminho)
    conferido = pd.read_csv(caminho)
    if len(conferido) != len(combinado) or conferido.origem_dado.eq("sintetico_ctgan").sum() != len(lote):
        raise RuntimeError("CSV não reconciliou com a carga.")
    return caminho
