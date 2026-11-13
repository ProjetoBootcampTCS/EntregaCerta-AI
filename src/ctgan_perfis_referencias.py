"""CTGAN aprende somente população artificial definida por JSON, nunca Olist.

CLI: python -m src.ctgan_perfis_referencias --step all
O contrato de 15 atributos não inclui perfil nem alvo. Uma CTGAN por perfil.
"""
from __future__ import annotations

import argparse
import json
import re
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

from .contratos_olist import (CATEGORICAS, CLEAN_COLUMNS, CONTAGENS, CTGAN_FEATURES,
    HISTORICOS, ML_DATASET_COLUMNS, ML_FEATURES, NUMERICAS_CTGAN, adicionar_razoes,
    mascara_valida, validar_limpo, validar_ml)
from .ml_vendedor_unico import criar_preprocessador, escolher_limiar, metricas
from .pipeline_olist import salvar_json
from .preparar_dados import RAIZ, exigir
from .sintese_olist import decodificar_candidatos, fingerprints, hash_tabela
from .tratar_dados_ml import sha256


def validar_config(c):
    exigir(bool(re.fullmatch(r"[A-Za-z0-9_-]+", c['run_id'])), 'run_id inválido')
    exigir(c['num_samples'] > 0 and c['seed_population_per_profile'] >= 100, 'Populações insuficientes')
    exigir(c['date_start'] == '2016-01-01' and c['date_end_exclusive'] == '2019-01-01', 'Datas devem cobrir 2016-2018')
    exigir({p['name'] for p in c['profiles']} == {'baixo', 'medio', 'alto'} and len(c['profiles']) == 3, 'Exigir três perfis únicos')
    exigir(np.isclose(sum(p['share'] for p in c['profiles']), 1), 'Participações devem somar um')
    probabilidades = {p['name']: p['delay_probability'] for p in c['profiles']}
    exigir(0 < probabilidades['baixo'] < probabilidades['medio'] < probabilidades['alto'] < 1, 'Probabilidades fora de ordem')
    for p in c['profiles']:
        exigir(p['share'] > 0, 'Perfil sem participação')
        for key, tamanho in [('route_weights', len(c['routes'])), ('review_score_probabilities', 5), ('item_probabilities', 4)]:
            exigir(len(p[key]) == tamanho and min(p[key]) >= 0 and np.isclose(sum(p[key]), 1), f'Pesos inválidos: {key}')
        for minimo, maximo in p['ranges'].values():
            exigir(0 < minimo < maximo, 'Faixas devem ser positivas e crescentes')
        exigir(0 <= p['no_history_probability'] <= 1 and 1 <= p['review_count'][0] <= p['review_count'][1], 'Histórico inválido')
    exigir(c['ctgan']['epochs'] > 0 and c['ctgan']['batch_size'] >= 10 and c['ctgan']['batch_size'] % 10 == 0, 'Config CTGAN inválida')
    exigir(0 < c['ml']['holdout_fraction'] < .5, 'Holdout inválido')


def populacao_artificial(c, perfil, seed):
    """Sem I/O: nenhuma consulta a Olist, modelos anteriores ou estatísticas reais."""
    rng = np.random.default_rng(seed)
    n = c['seed_population_per_profile']
    rotas = rng.choice(len(c['routes']), n, p=perfil['route_weights'])
    itens = rng.choice(np.arange(1, 5), n, p=perfil['item_probabilities'])
    produtos = np.array([rng.integers(1, k + 1) for k in itens])
    categorias = np.array([rng.integers(1, k + 1) for k in produtos])
    r = perfil['ranges']
    loguniforme = lambda key: np.exp(rng.uniform(*np.log(r[key]), n))
    valor = loguniforme('unit_price') * itens
    count = rng.integers(perfil['review_count'][0], perfil['review_count'][1] + 1, n)
    count[rng.random(n) < perfil['no_history_probability']] = 0
    contagens = np.array([rng.multinomial(int(k), perfil['review_score_probabilities']) for k in count])
    nota = np.divide(contagens @ np.arange(1, 6), count, out=np.full(n, np.nan), where=count > 0)
    baixa = np.divide(contagens[:, :3].sum(axis=1), count, out=np.full(n, np.nan), where=count > 0)
    base = pd.DataFrame({
        'customer_state': [c['routes'][k]['customer_state'] for k in rotas],
        'seller_state': [c['routes'][k]['seller_state'] for k in rotas],
        'categoria_principal': rng.choice(c['categories'], n),
        'quantidade_itens': itens, 'quantidade_produtos': produtos, 'quantidade_categorias': categorias,
        'valor_itens': valor, 'valor_frete': valor * rng.uniform(*r['freight_ratio'], n),
        'peso_total_g': loguniforme('unit_weight_g') * itens,
        'volume_total_cm3': loguniforme('unit_volume_cm3') * itens,
        'distancia_vendedor_cliente_km': [rng.uniform(*c['routes'][k]['distance_km']) for k in rotas],
        'prazo_prometido_dias': rng.uniform(*r['prazo_prometido_dias'], n),
        HISTORICOS[0]: nota, HISTORICOS[1]: count, HISTORICOS[2]: baixa,
    })[CTGAN_FEATURES]
    exigir(mascara_valida(base).all(), 'População artificial inválida')
    return base


def ajustar_perfil(base, c, seed):
    import torch
    from ctgan import CTGAN
    exigir(list(base) == CTGAN_FEATURES and mascara_valida(base).all(), 'CTGAN requer 15 atributos válidos')
    tabela = base.copy()
    tabela[HISTORICOS[0]] = tabela[HISTORICOS[0]].fillna(0.)
    tabela[HISTORICOS[2]] = tabela[HISTORICOS[2]].fillna(-1.)
    logs = [x for x in NUMERICAS_CTGAN if x not in [HISTORICOS[0], HISTORICOS[2], *CONTAGENS[:3]]]
    for x in logs:
        tabela[x] = np.log1p(tabela[x])
    discretas = CATEGORICAS + CONTAGENS[:3]
    for x in discretas:
        tabela[x] = tabela[x].astype(str)
    torch.set_num_threads(c['ctgan']['threads'])
    torch.manual_seed(seed)
    exigir(not c['ctgan']['enable_gpu'] or torch.cuda.is_available(), 'GPU solicitada, mas CUDA indisponível')
    modelo = CTGAN(epochs=c['ctgan']['epochs'], batch_size=c['ctgan']['batch_size'], pac=10,
        generator_dim=(128, 128), discriminator_dim=(128, 128),
        enable_gpu=c['ctgan']['enable_gpu'], verbose=c['ctgan']['verbose'])
    modelo.set_random_state(seed)
    modelo.fit(tabela, discrete_columns=discretas)
    return {'modelo': modelo, 'logs': logs, 'source': 'json_rules_only', 'hash_seed': hash_tabela(base)}, tabela


def validar_candidatos(base, c, perfil):
    valido = mascara_valida(base) & base.categoria_principal.isin(c['categories'])
    r = perfil['ranges']
    for coluna, regra in [('valor_itens', 'unit_price'), ('peso_total_g', 'unit_weight_g'), ('volume_total_cm3', 'unit_volume_cm3')]:
        valido &= (base[coluna] / base.quantidade_itens).between(*r[regra])
    valido &= (base.valor_frete / base.valor_itens).between(*r['freight_ratio'])
    valido &= base.prazo_prometido_dias.between(*r['prazo_prometido_dias']) & base.quantidade_itens.between(1, 4)
    valido &= base[HISTORICOS[1]].eq(0) | base[HISTORICOS[1]].between(*perfil['review_count'])
    # Consistência mínima entre média e fração de notas <=3.
    valido &= base[HISTORICOS[1]].eq(0) | (base[HISTORICOS[0]].ge(4 - 3 * base[HISTORICOS[2]]) & base[HISTORICOS[0]].le(5 - 2 * base[HISTORICOS[2]]))
    rota_valida = pd.Series(False, index=base.index)
    for rota in c['routes']:
        rota_valida |= (base.seller_state.eq(rota['seller_state']) & base.customer_state.eq(rota['customer_state']) & base.distancia_vendedor_cliente_km.between(*rota['distance_km']))
    return base.loc[valido & rota_valida].copy()


def amostrar_perfil(pacote, inicial, c, perfil, n, seed):
    exigir(pacote['source'] == 'json_rules_only' and pacote['hash_seed'] == hash_tabela(inicial), 'Gerador não pertence à população artificial')
    pacote['modelo'].set_random_state(seed)
    aceitos = inicial.iloc[:0].copy()
    hashes = set(fingerprints(inicial))
    tentados = invalidos = duplicados = excedentes = 0
    for _ in range(c['max_resample_attempts']):
        # Aprender só a eficiência da rejeição sintética, nunca afrouxar regras.
        eficiencia = max((tentados - invalidos - duplicados) / tentados, .005) if tentados else .2
        lote = min(100000, max(2000, int(np.ceil(1.2 * (n - len(aceitos)) / eficiencia))))
        bruto = pacote['modelo'].sample(lote)
        tentados += len(bruto)
        novos = validar_candidatos(decodificar_candidatos(bruto, pacote), c, perfil)
        invalidos += len(bruto) - len(novos)
        tamanho = len(novos)
        novos = novos.loc[~fingerprints(novos).isin(hashes)].drop_duplicates()
        duplicados += tamanho - len(novos)
        excedentes += max(0, len(novos) - (n - len(aceitos)))
        novos = novos.head(n - len(aceitos))
        hashes.update(fingerprints(novos))
        aceitos = pd.concat([aceitos, novos], ignore_index=True)
        if len(aceitos) == n:
            break
    relatorio = {'candidatos': tentados, 'invalidos': invalidos, 'duplicados': duplicados,
                 'excedentes': excedentes, 'aceitos': len(aceitos), 'taxa_rejeicao': invalidos / tentados}
    if len(aceitos) != n:
        erro = ValueError(f'Perfil {perfil["name"]}: só {len(aceitos)}/{n} amostras válidas; não exportar lote incompleto')
        erro.relatorio = relatorio
        raise erro
    aceitos[CONTAGENS] = aceitos[CONTAGENS].astype(int)
    return aceitos, relatorio


def finalizar(amostras, perfis, c):
    rng = np.random.default_rng(c['seed'] + 2)
    base = adicionar_razoes(amostras.reset_index(drop=True))
    n = len(base)
    for coluna, prefixo in [('order_id', 'order'), ('seller_id', 'seller')]:
        base[coluna] = [f'ctgan_{prefixo}_{c["run_id"]}_{i:07d}' for i in range(n)]
    inicio, fim = pd.Timestamp(c['date_start']), pd.Timestamp(c['date_end_exclusive'])
    base['order_approved_at'] = inicio + pd.to_timedelta(rng.integers(0, int((fim - inicio).total_seconds()), n), unit='s')
    probs = {p['name']: p['delay_probability'] for p in c['profiles']}
    prob = pd.Series(perfis).map(probs).to_numpy()
    base['atrasou'] = rng.binomial(1, prob)
    base['origem_dado'], base['particao'] = 'sintetico_ctgan', 'treino'
    base = base[CLEAN_COLUMNS]
    validar_limpo(base, sintetico=True)
    detalhes = pd.DataFrame({'order_id': base.order_id, 'perfil': perfis, 'p_atraso_simulada': prob, 'atrasou': base.atrasou})
    return base, detalhes


def montar_ml_sintetico(base):
    validar_limpo(base, sintetico=True)
    df = base.copy()
    df['mes_aprovacao'] = pd.to_datetime(df.order_approved_at).dt.month
    df = df[ML_DATASET_COLUMNS]
    validar_ml(df)
    return df


def treinar_somente_sinteticos(df, c):
    validar_ml(df)
    exigir(df.origem_dado.eq('sintetico_ctgan').all() and df.particao.eq('treino').all(), 'Preditor aceita SOMENTE sintéticos')
    treino, holdout = train_test_split(df, test_size=c['ml']['holdout_fraction'], random_state=c['ml']['seed'], stratify=df.atrasou)
    pre = criar_preprocessador()
    modelo = Pipeline([('preprocessador', pre), ('modelo', LogisticRegression(C=c['ml']['C'], solver='liblinear', max_iter=1500, random_state=c['ml']['seed']))])
    modelo.fit(treino[ML_FEATURES], treino.atrasou)
    scores = modelo.predict_proba(holdout[ML_FEATURES])[:, 1]
    limiar = escolher_limiar(holdout.atrasou, scores)
    metricas_holdout = metricas(holdout.atrasou, scores, limiar)
    metricas_holdout['atrasos_sinteticos'] = metricas_holdout.pop('atrasos_reais')
    # Sem refit após selecionar limiar: preservar calibração do modelo avaliado.
    return {'pipeline': modelo, 'features': ML_FEATURES, 'limiar': limiar, 'source': 'synthetic_only',
        'hash_dataset': hash_tabela(df), 'train_ids': treino.order_id.tolist(), 'holdout_ids': holdout.order_id.tolist(),
        'holdout_metrics': metricas_holdout}


def avaliar_real(real, modelo):
    validar_limpo(real)
    exigir(modelo['source'] == 'synthetic_only', 'Modelo não é exclusivamente sintético')
    # Nenhum fit ou seleção aqui. Olist é aberto somente após salvar o preditor.
    df = real.copy()
    df['mes_aprovacao'] = pd.to_datetime(df.order_approved_at).dt.month
    scores = modelo['pipeline'].predict_proba(df[ML_FEATURES])[:, 1]
    previsoes = df[['order_id', 'particao', 'atrasou']].copy()
    previsoes['score_atraso'] = scores
    linhas = [{'grupo': 'todos_reais', **metricas(df.atrasou, scores, modelo['limiar'])}]
    for parte in ['treino', 'validacao', 'teste']:
        m = df.particao.eq(parte)
        if m.any():
            linhas.append({'grupo': f'particao_original_{parte}', **metricas(df.loc[m, 'atrasou'], scores[m], modelo['limiar'])})
    return pd.DataFrame(linhas), previsoes


def executar(c, etapa):
    validar_config(c)
    pasta = RAIZ / c['artifacts_dir'] / c['run_id']
    pasta.mkdir(parents=True, exist_ok=True)
    manifesto = pasta / 'manifesto.json'
    if manifesto.exists():
        exigir(json.loads(manifesto.read_text(encoding='utf-8'))['config'] == c, 'Config mudou; use outro run_id')
    else:
        salvar_json(manifesto, {'config': c, 'source': 'json_rules_only', 'codigo_sha256': sha256(__file__),
            'versoes': {p: version(p) for p in ['ctgan', 'rdt', 'torch', 'pandas', 'numpy', 'scikit-learn']}})
    etapas = ['seed', 'ctgan-train', 'generate', 'ml-train', 'evaluate'] if etapa == 'all' else [etapa]
    for step in etapas:
        print(f'[{step}] {c["run_id"]}', flush=True)
        if step != 'evaluate':
            exigir(not (pasta / 'metricas_reais.csv').exists(), 'Execução já avaliada; novo experimento exige outro run_id')
        if step == 'seed':
            for i, perfil in enumerate(c['profiles']):
                populacao_artificial(c, perfil, c['seed'] + i).to_parquet(pasta / f'seed_{perfil["name"]}.parquet', index=False)
        elif step == 'ctgan-train':
            for i, perfil in enumerate(c['profiles']):
                nome = perfil['name']
                inicial = pd.read_parquet(pasta / f'seed_{nome}.parquet')
                pd.testing.assert_frame_equal(inicial, populacao_artificial(c, perfil, c['seed'] + i))
                pacote, b = ajustar_perfil(inicial, c, c['seed'] + i)
                joblib.dump(pacote, pasta / f'ctgan_{nome}.joblib', compress=3)
                b.to_parquet(pasta / f'ctgan_features_{nome}.parquet', index=False)
        elif step == 'generate':
            partes, perfis, relatorios = [], [], {}
            quotas = np.array([p['share'] * c['num_samples'] for p in c['profiles']])
            inteiros = np.floor(quotas).astype(int)
            for i in np.argsort(-(quotas - inteiros), kind='stable')[:c['num_samples'] - sum(inteiros)]:
                inteiros[i] += 1
            for i, (perfil, n) in enumerate(zip(c['profiles'], inteiros)):
                nome = perfil['name']
                try:
                    base, relatorios[nome] = amostrar_perfil(joblib.load(pasta / f'ctgan_{nome}.joblib'), pd.read_parquet(pasta / f'seed_{nome}.parquet'), c, perfil, int(n), c['seed'] + i + 10)
                except ValueError as erro:
                    if hasattr(erro, 'relatorio'):
                        salvar_json(pasta / f'falha_amostragem_{nome}.json', erro.relatorio)
                    raise
                partes.append(base)
                perfis.extend([nome] * n)
            base, detalhes = finalizar(pd.concat(partes, ignore_index=True), perfis, c)
            base.to_parquet(pasta / 'pedidos_sinteticos.parquet', index=False)
            base.to_csv(pasta / 'pedidos_sinteticos.csv', index=False)
            detalhes.to_parquet(pasta / 'perfis_probabilidades.parquet', index=False)
            relatorios['resumo'] = detalhes.groupby('perfil').agg(n=('atrasou', 'size'), atrasos=('atrasou', 'sum'), taxa=('atrasou', 'mean'), probabilidade=('p_atraso_simulada', 'mean')).to_dict('index')
            salvar_json(pasta / 'geracao.json', relatorios)
        elif step == 'ml-train':
            df = montar_ml_sintetico(pd.read_parquet(pasta / 'pedidos_sinteticos.parquet'))
            df.to_parquet(pasta / 'pedidos_ml_filtrado.parquet', index=False)
            pacote = treinar_somente_sinteticos(df, c)
            joblib.dump(pacote, pasta / 'preditor_sintetico.joblib', compress=3)
            salvar_json(pasta / 'validacao_sintetica.json', pacote['holdout_metrics'])
        elif step == 'evaluate':
            exigir(not (pasta / 'metricas_reais.csv').exists(), 'Avaliação já realizada; consulte o CSV salvo')
            modelo = joblib.load(pasta / 'preditor_sintetico.joblib')
            real_path = RAIZ / c['evaluation_real']
            tabela, previsoes = avaliar_real(pd.read_parquet(real_path), modelo)
            tabela.to_csv(pasta / 'metricas_reais.csv', index=False)
            previsoes.to_parquet(pasta / 'previsoes_olist.parquet', index=False)
            salvar_json(pasta / 'avaliacao.json', {'fonte_real': str(real_path), 'hash_real': sha256(real_path),
                'hash_modelo': sha256(pasta / 'preditor_sintetico.joblib'), 'observacao': 'Base real enriquecida pelo fluxo existente. Sem fit/ajuste nos reais neste experimento; teste já consultado em experimentos anteriores.'})
            print(tabela.to_string(index=False), flush=True)
        else:
            raise ValueError(step)
        print(f'[{step}] concluído', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=RAIZ / 'config/ctgan_perfis_referencias.json')
    parser.add_argument('--step', choices=['all', 'seed', 'ctgan-train', 'generate', 'ml-train', 'evaluate'], required=True)
    args = parser.parse_args()
    c = json.loads(args.config.read_text(encoding='utf-8'))
    with threadpool_limits(limits=c['ctgan']['threads']):
        executar(c, args.step)


if __name__ == '__main__':
    main()
