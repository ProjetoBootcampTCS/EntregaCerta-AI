"""Validar documentos estruturados e DDL em memória; nenhuma carga de dados/ML."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sqlite3
import sys

from lxml import etree
from entregacerta.contracts import validate_features

ROOT = Path(__file__).resolve().parents[1]
NS = {'b': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
      'di': 'http://www.omg.org/spec/BPMN/20100524/DI',
      'd': 'http://www.omg.org/spec/DD/20100524/DI'}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def validate_bpmn(path):
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    schema = etree.XMLSchema(etree.parse(str(ROOT/'docs/validacao/bpmn-xsd/BPMN20.xsd'), parser))
    tree = etree.parse(str(path), parser)
    schema.assertValid(tree)
    ids = tree.xpath('//@id')
    check(len(ids) == len(set(ids)), 'IDs BPMN duplicados')
    process = tree.find('b:process', NS)
    kinds = {'startEvent','endEvent','serviceTask','userTask','exclusiveGateway','boundaryEvent'}
    nodes = {e.get('id'):e for e in process if etree.QName(e).localname in kinds}
    flows = process.findall('b:sequenceFlow', NS)
    outgoing, incoming = defaultdict(set), defaultdict(set)
    graph = defaultdict(set)
    for flow in flows:
        source, target, fid = flow.get('sourceRef'), flow.get('targetRef'), flow.get('id')
        check(source in nodes and target in nodes, f'Fluxo sem origem/destino válido: {fid}')
        outgoing[source].add(fid)
        incoming[target].add(fid)
        graph[source].add(target)
    for nid, element in nodes.items():
        check({e.text for e in element.findall('b:incoming', NS)} == incoming[nid], f'Incoming inconsistente: {nid}')
        check({e.text for e in element.findall('b:outgoing', NS)} == outgoing[nid], f'Outgoing inconsistente: {nid}')
        kind = etree.QName(element).localname
        if kind == 'boundaryEvent':
            parent = element.get('attachedToRef')
            check(parent in nodes, 'Evento de borda sem atividade')
            graph[parent].add(nid)  # caminho excepcional implícito no BPMN
        elif kind == 'exclusiveGateway' and len(outgoing[nid]) > 1:
            default = element.get('default')
            check(default in outgoing[nid], 'Gateway divergente sem fluxo padrão')
            for flow in flows:
                if flow.get('id') in outgoing[nid] - {default}:
                    check(flow.find('b:conditionExpression', NS) is not None, 'Ramo não padrão sem condição')
    lane_refs = process.xpath('b:laneSet/b:lane/b:flowNodeRef/text()', namespaces=NS)
    check(Counter(lane_refs) == Counter(nodes.keys()), 'Cobertura das raias incorreta')
    starts = {nid for nid,e in nodes.items() if etree.QName(e).localname == 'startEvent'}
    ends = {nid for nid,e in nodes.items() if etree.QName(e).localname == 'endEvent'}
    def reachable(initial, links):
        seen, pending = set(), list(initial)
        while pending:
            item = pending.pop()
            if item not in seen:
                seen.add(item)
                pending.extend(links[item])
        return seen
    check(reachable(starts, graph) == set(nodes), 'Nós inalcançáveis desde o início')
    reverse = defaultdict(set)
    for source, targets in graph.items():
        for target in targets:
            reverse[target].add(source)
    check(reachable(ends, reverse) == set(nodes), 'Existe caminho sem acesso ao fim')
    shapes = tree.xpath('//di:BPMNShape/@bpmnElement', namespaces=NS)
    edge_refs = tree.xpath('//di:BPMNEdge/@bpmnElement', namespaces=NS)
    check(set(nodes) <= set(shapes), 'DI não cobre todos os nós')
    check(set(edge_refs) == {f.get('id') for f in flows}, 'DI não cobre todos os fluxos')
    for edge in tree.xpath('//di:BPMNEdge', namespaces=NS):
        check(len(edge.findall('d:waypoint',NS)) >= 2, 'Fluxo DI sem caminho')
    return {'official_xsd_valid': True, 'flow_nodes': len(nodes), 'sequence_flows': len(flows),
            'lane_count': len(process.xpath('b:laneSet/b:lane', namespaces=NS)),
            'graph_and_di_valid': True}


def validate_sql():
    with sqlite3.connect(':memory:') as connection:
        connection.executescript((ROOT/'docs/schema_planejado.sql').read_text(encoding='utf-8'))
        tables = sorted(row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"))
        check(len(tables) == 11, 'Quantidade inesperada de tabelas')
        check(connection.execute('PRAGMA foreign_keys').fetchone()[0] == 1, 'FKs desabilitadas')
        foreign_keys = sum(len(list(connection.execute(f'PRAGMA foreign_key_list("{table}")'))) for table in tables)
        check(not list(connection.execute('PRAGMA foreign_key_check')), 'Inconsistência no esquema')
        check(connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'Integridade SQL inválida')
        return {'mode':'memory_only_no_data', 'tables':tables, 'foreign_keys':foreign_keys, 'valid':True}


def validate():
    contract = json.loads((ROOT/'config/contrato_problema.json').read_text(encoding='utf-8-sig'))
    features = json.loads((ROOT/'config/atributos.json').read_text(encoding='utf-8-sig'))
    names = validate_features(features)
    check(not contract['model_training_performed'], 'Estado inesperado de treinamento nesta etapa')
    for path in contract['documentation']:
        check((ROOT/path).is_file(), f'Documento ausente: {path}')
    manifest = json.loads((ROOT/'docs/validacao/assets_manifest.json').read_text(encoding='utf-8'))
    for asset in manifest:
        check(hashlib.sha256((ROOT/asset['path']).read_bytes()).hexdigest() == asset['sha256'], f'Asset alterado: {asset["path"]}')
    for name in ('arquitetura.svg','modelo_dados.svg','processo.svg'):
        tree = etree.parse(str(ROOT/'docs/diagramas'/name))
        check(etree.QName(tree.getroot()).localname == 'svg', 'SVG inválido')
    rendered = json.loads((ROOT/'docs/validacao/bpmn_render.json').read_text(encoding='utf-8'))
    check(rendered['import_succeeded'] and not rendered['warnings'], 'BPMN não renderizado sem advertências')
    imports = ['numpy','pandas','sklearn','joblib','fastapi','uvicorn','streamlit','plotly','httpx','dotenv','pydantic','lxml']
    for module in imports:
        importlib.import_module(module)
    return {'validated_at_utc':datetime.now(timezone.utc).isoformat(), 'python':sys.version.split()[0],
            'feature_count':len(names), 'contract_valid':True,
            'bpmn_source':validate_bpmn(ROOT/'docs/diagramas/processo.bpmn'),
            'bpmn_roundtrip':validate_bpmn(ROOT/'docs/validacao/processo_roundtrip.bpmn'),
            'render_report':rendered, 'svg_count':3, 'verified_vendor_assets':len(manifest),
            'sql':validate_sql(), 'package_imports':imports,
            'model_training_performed':False, 'dataset_processing_performed':False, 'ok':True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='docs/validacao/planejamento.json')
    args = parser.parse_args()
    report = validate()
    (ROOT/args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
