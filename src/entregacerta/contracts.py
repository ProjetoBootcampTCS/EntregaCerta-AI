"""Verificações do contrato planejado; não calculam atributos nem predições."""


def validate_features(contract: dict) -> list[str]:
    forbidden = set(contract['forbidden_source_columns'])
    lineage = set(contract['lineage_only'])
    names = [feature['name'] for feature in contract['features']]
    if len(names) != len(set(names)):
        raise ValueError('Nomes de atributos duplicados')
    if set(names) & (forbidden | lineage):
        raise ValueError('Alvo ou identificador incluído como atributo bruto')
    for feature in contract['features']:
        if feature['type'] not in {'numeric', 'categorical'}:
            raise ValueError('Tipo de atributo não suportado')
        if not feature.get('source') or not feature.get('rule'):
            raise ValueError('Atributo sem fonte/regra')
        sources = {name.split('.')[-1] for name in feature['source']}
        if sources & forbidden:
            raise ValueError('Informação futura ou indisponível na fonte do atributo')
    return names
