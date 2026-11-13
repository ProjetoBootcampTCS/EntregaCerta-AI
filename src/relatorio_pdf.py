"""Relatório do dashboard: indicadores calculados, gráficos vetoriais e resumo assistido.

Recebe somente resultados já calculados. Não importa nem executa treinamento/inferência.
Snapshots privados ficam por 30 minutos na memória do único processo da API local.
"""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import logging
import math
from pathlib import Path
import re
import secrets
from statistics import mean, median
from threading import Lock
from time import monotonic
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from matplotlib import get_data_path
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.graphics.shapes import Drawing, Rect, String, Line

from .assistente_genai import responder

DURACAO = 30 * 60
MAX_ANALISES = 16
_analises = OrderedDict()
_trava = Lock()
VERDE = colors.HexColor('#19271f')
LIMA = colors.HexColor('#d4ff3f')
SUAVE = colors.HexColor('#edf3df')
CINZA = colors.HexColor('#586550')
BORDA = colors.HexColor('#d5ddcc')
FONTE = Path(get_data_path()) / 'fonts/ttf'
for nome, arquivo in [('EC','DejaVuSans.ttf'),('EC-Bold','DejaVuSans-Bold.ttf')]:
    if nome not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(nome, str(FONTE / arquivo)))


def indicadores(dados):
    """Agrega a fila inteira; busca e paginação do navegador não mudam o relatório."""
    total, quantidade = dados['pedidos_avaliados'], dados['pedidos_na_fila']
    fracao = float(dados['fracao_fila'])
    scores = [float(p['score_atraso']) for p in dados['fila']]
    if (not isinstance(total, int) or total < 0 or not isinstance(quantidade, int)
            or quantidade != len(scores) or not 0 <= quantidade <= total
            or not math.isfinite(fracao) or not 0 <= fracao <= 1
            or int(total * fracao) != quantidade
            or any(not math.isfinite(s) or not 0 <= s <= 1 for s in scores)):
        raise ValueError('Resultados inconsistentes para o relatório.')
    faixas = [0] * 10
    for score in scores:
        faixas[min(int(score * 10), 9)] += 1
    return {
        'contexto': str(dados['contexto']), 'pedidos_avaliados': total,
        'pedidos_na_fila': quantidade, 'fora_da_fila': total - quantidade,
        'fracao_configurada': fracao,
        'fracao_efetiva': quantidade / total if total else 0,
        'maior_score': max(scores) if scores else None,
        'score_medio': mean(scores) if scores else None,
        'score_mediano': median(scores) if scores else None,
        'histograma_fila': faixas,
        'observacao': 'Score de risco relativo, não uma probabilidade calibrada. Estar na fila não confirma atraso.',
    }


def registrar_analise(dados, usuario_id):
    fatos = indicadores(dados)
    identificador = secrets.token_urlsafe(24)
    agora = datetime.now(timezone.utc).isoformat()
    with _trava:
        for chave in list(_analises):
            if _analises[chave]['expira'] <= monotonic():
                del _analises[chave]
        while len(_analises) >= MAX_ANALISES:
            _analises.popitem(last=False)
        _analises[identificador] = {
            'dono': str(usuario_id), 'expira': monotonic() + DURACAO,
            'fatos': fatos, 'analisado_em': agora, 'trava': Lock(), 'pdf': None,
        }
    return {'analise_id': identificador, 'analisado_em': agora}


def resumo_completo(resposta):
    """Recusa respostas vazias ou aparentemente interrompidas; não valida veracidade."""
    if (not isinstance(resposta, dict) or resposta.get('disponivel') is not True
            or resposta.get('motivo_termino') != 'STOP'):
        return False
    texto = resposta.get('resposta')
    return isinstance(texto, str) and len(texto.strip()) >= 40 and bool(
        re.search(r'[.!?][\s"\u201d\u2019)*_]*$', texto)
    )


def gerar_relatorio(analise_id, usuario_id):
    with _trava:
        registro = _analises.get(analise_id)
        if not registro or registro['dono'] != str(usuario_id):
            raise HTTPException(404, 'Análise não encontrada para esta conta. Gere uma nova análise no dashboard.')
        if registro['expira'] <= monotonic():
            del _analises[analise_id]
            raise HTTPException(410, 'A análise expirou. Atualize a fila no dashboard e gere o relatório novamente.')
    if not registro['trava'].acquire(blocking=False):
        raise HTTPException(409, 'Este relatório já está sendo gerado. Aguarde a conclusão.')
    try:
        if registro['pdf'] is not None:
            return registro['pdf'], registro['genai']
        fatos = deepcopy(registro['fatos'])
        prompt = (
            'Escreva um resumo operacional de até 150 palavras para o relatório do analista. '
            'Use exclusivamente os fatos recebidos. Explique o tamanho da fila e o papel da revisão humana. '
            'Não invente causas, datas de entrega, ganhos, acurácia, precision ou recall. '
            'Score não é probabilidade. Não estime indicadores ausentes, como o menor score. '
            'Não apresente os pedidos priorizados como atrasos confirmados. '
            'Escreva em texto simples, sem tabelas, código ou emojis.'
        )
        # As faixas continuam no gráfico, mas não permitem deduzir um mínimo exato.
        # A LLM recebe somente os indicadores necessários para redigir o resumo.
        contexto_resumo = {chave: fatos[chave] for chave in (
            'contexto', 'pedidos_avaliados', 'pedidos_na_fila', 'fora_da_fila',
            'fracao_configurada', 'maior_score', 'score_medio', 'score_mediano', 'observacao',
        )}
        try:
            resposta = responder(prompt, contexto_resumo, para_relatorio=True)
            genai = resumo_completo(resposta)
        except Exception:
            logging.warning('Resumo generativo indisponível durante a geração do PDF.')
            genai = False
        if genai:
            texto = resposta['resposta'].strip()
        else:
            texto = (
                'O resumo da GenAI não ficou disponível ou chegou incompleto nesta geração. Os indicadores e gráficos '
                'foram calculados pelo sistema a partir da análise registrada. '
                'A fila orienta a revisão humana e não confirma quais pedidos atrasaram. '
                'Para tentar um novo resumo, atualize a análise no dashboard e gere outro relatório.'
            )
        registro['pdf'] = montar_pdf(fatos, texto, genai, analise_id, registro['analisado_em'])
        registro['genai'] = bool(genai)
        return registro['pdf'], registro['genai']
    finally:
        registro['trava'].release()


def numero(valor):
    return f'{valor:,}'.replace(',', '.')


def decimal(valor, casas=4):
    return 'Não disponível' if valor is None else f'{valor:.{casas}f}'.replace('.', ',')


def grafico_fila(fatos):
    d = Drawing(490, 125)
    total = fatos['pedidos_avaliados']
    for y, rotulo, n, cor in [(79,'Na fila',fatos['pedidos_na_fila'],VERDE),(30,'Fora da fila',fatos['fora_da_fila'],colors.HexColor('#a7b98e'))]:
        d.add(String(0,y+8,rotulo,fontName='EC',fontSize=9,fillColor=VERDE))
        d.add(Rect(90,y,285,25,fillColor=SUAVE,strokeColor=None))
        largura = 285 * n / total if total else 0
        if largura:
            d.add(Rect(90,y,largura,25,fillColor=cor,strokeColor=None))
        percentual = n / total * 100 if total else 0
        d.add(String(390,y+8,f'{numero(n)} ({decimal(percentual,1)}%)',fontName='EC',fontSize=9,fillColor=VERDE))
    d.add(String(90,6,'Comprimento proporcional ao total de pedidos avaliados.',fontName='EC',fontSize=8,fillColor=CINZA))
    return d


def grafico_scores(fatos):
    d = Drawing(490, 192)
    faixas = fatos['histograma_fila']
    if not sum(faixas):
        d.add(String(30,85,'Não há pedidos na fila para apresentar a distribuição.',fontName='EC',fontSize=10,fillColor=CINZA))
        return d
    pico = max(faixas)
    teto = max(4, math.ceil(pico / 4) * 4)
    for i in range(5):
        y = 35 + i * 32
        d.add(Line(46,y,474,y,strokeColor=BORDA,strokeWidth=.5))
        d.add(String(37,y-3,numero(int(teto*i/4)),textAnchor='end',fontName='EC',fontSize=8,fillColor=CINZA))
    for i,n in enumerate(faixas):
        x = 50 + i*42
        altura = n/teto*128
        if n:
            d.add(Rect(x,35,30,altura,fillColor=VERDE,strokeColor=None))
        d.add(String(x+15,40+altura,numero(n),textAnchor='middle',fontName='EC',fontSize=8,fillColor=VERDE))
        d.add(String(x+15,20,f'{i/10:.1f}'.replace('.',','),textAnchor='middle',fontName='EC',fontSize=8,fillColor=CINZA))
    d.add(String(46,180,'Quantidade de pedidos na fila',fontName='EC',fontSize=8,fillColor=CINZA))
    d.add(String(46,3,'Início da faixa de score (largura 0,1); última faixa inclui 1,0.',fontName='EC',fontSize=8,fillColor=CINZA))
    return d


def texto_seguro(texto):
    # Saída da LLM é texto não confiável, nunca comandos ou marcação ReportLab.
    texto = str(texto).replace('—','-').replace('–','-').replace('\u2011','-')
    glifos = pdfmetrics.getFont('EC').face.charToGlyph
    texto = ''.join(c for c in texto if c in '\n\t' or (ord(c)>=32 and ord(c) in glifos))
    return escape(texto)


def montar_pdf(fatos, resumo, genai, analise_id, analisado_em):
    saida = BytesIO()
    largura, altura = A4
    estilos = {
        'titulo': ParagraphStyle('titulo',fontName='EC-Bold',fontSize=23,leading=29,textColor=VERDE,spaceAfter=12),
        'subtitulo': ParagraphStyle('subtitulo',fontName='EC-Bold',fontSize=13,leading=18,textColor=VERDE,spaceBefore=14,spaceAfter=8),
        'corpo': ParagraphStyle('corpo',fontName='EC',fontSize=10,leading=16,textColor=VERDE,spaceAfter=10),
        'nota': ParagraphStyle('nota',fontName='EC',fontSize=8,leading=12,textColor=CINZA,spaceAfter=7),
        'metrica': ParagraphStyle('metrica',fontName='EC-Bold',fontSize=19,leading=25,textColor=VERDE),
        'metrica_vazia': ParagraphStyle('metrica_vazia',fontName='EC-Bold',fontSize=12,leading=25,textColor=VERDE),
    }
    def paragrafo(texto,tipo='corpo'):
        return Paragraph(texto_seguro(texto),estilos[tipo])
    def hora(iso):
        return datetime.fromisoformat(iso).astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M:%S')
    gerado_em = datetime.now(timezone.utc).isoformat()
    def pagina(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(VERDE);canvas.rect(0,altura-55,largura,55,stroke=0,fill=1)
        canvas.setFillColor(LIMA);canvas.roundRect(40,altura-39,23,23,5,stroke=0,fill=1)
        canvas.setStrokeColor(VERDE);canvas.setLineWidth(1.3)
        desenho=canvas.beginPath();desenho.moveTo(45,altura-24);desenho.lineTo(51.5,altura-20);desenho.lineTo(58,altura-24);desenho.lineTo(51.5,altura-28);desenho.close()
        canvas.drawPath(desenho);canvas.line(45,altura-24,45,altura-33);canvas.line(45,altura-33,51.5,altura-37);canvas.line(51.5,altura-37,58,altura-33);canvas.line(58,altura-33,58,altura-24);canvas.line(51.5,altura-28,51.5,altura-37)
        canvas.setFont('EC-Bold',13);canvas.setFillColor(colors.white);canvas.drawString(73,altura-32,'entregacerta AI')
        canvas.setFont('EC',8);canvas.setFillColor(LIMA);canvas.drawRightString(largura-40,altura-31,'RELATÓRIO DO ANALISTA')
        canvas.setStrokeColor(BORDA);canvas.line(40,43,largura-40,43)
        canvas.setFont('EC',7);canvas.setFillColor(CINZA)
        canvas.drawString(40,29,'Olist | demonstração histórica | revisão humana')
        canvas.drawRightString(largura-40,29,f'Página {doc.page}')
        canvas.restoreState()
    doc = SimpleDocTemplate(saida,pagesize=A4,rightMargin=40,leftMargin=40,topMargin=76,bottomMargin=60,
                            title='EntregaCerta AI - Relatório de priorização',author='Equipe EntregaCerta AI')
    blocos = [paragrafo('Uma visão da fila.\nUm ponto de partida para agir.','titulo'),
              paragrafo('Resultados da análise histórica de validação. O relatório considera a fila completa; busca, ordenação e paginação da tela não alteram estes indicadores.','nota'),
              paragrafo('Análise: '+hora(analisado_em)+' | PDF: '+hora(gerado_em)+' (Brasília)','nota')]
    itens = [('Pedidos avaliados',numero(fatos['pedidos_avaliados'])),('Pedidos na fila',numero(fatos['pedidos_na_fila'])),
             ('Capacidade configurada',decimal(100*fatos['fracao_configurada'],1)+'%'),('Maior score da fila',decimal(fatos['maior_score'])),
             ('Score médio da fila',decimal(fatos['score_medio'])),('Score mediano da fila',decimal(fatos['score_mediano']))]
    celulas = [[paragrafo(nome,'nota'),paragrafo(valor,'metrica_vazia' if valor=='Não disponível' else 'metrica')] for nome,valor in itens]
    grade = Table([celulas[:3],celulas[3:]],colWidths=[(largura-80)/3]*3)
    grade.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),SUAVE),('BOX',(0,0),(-1,-1),.6,BORDA),
                              ('INNERGRID',(0,0),(-1,-1),.6,BORDA),('VALIGN',(0,0),(-1,-1),'TOP'),
                              ('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),8),
                              ('TOPPADDING',(0,0),(-1,-1),11),('BOTTOMPADDING',(0,0),(-1,-1),9)]))
    blocos.extend([Spacer(1,9),grade,paragrafo('01 / Quanto do lote foi priorizado?','subtitulo'),grafico_fila(fatos),
                   paragrafo('02 / Como os scores se distribuem na fila?','subtitulo'),grafico_scores(fatos),
                   paragrafo('Os gráficos descrevem a seleção para revisão. Não medem acurácia, atraso observado ou eficácia de intervenções. O score não é uma probabilidade calibrada.','nota'),PageBreak(),
                   paragrafo('Leitura assistida.\nDecisão humana.','titulo'),
                   paragrafo('Resumo gerado pela GenAI' if genai else 'Resumo automático de contingência - GenAI indisponível','subtitulo')])
    # Preserva o resumo inteiro. O ReportLab cria outra página se necessário.
    texto = ' '.join(str(resumo).split())
    blocos.append(paragrafo(texto))
    blocos.extend([paragrafo('O que estes resultados permitem afirmar','subtitulo'),
                   paragrafo(f"Foram avaliados {numero(fatos['pedidos_avaliados'])} pedidos, dos quais {numero(fatos['pedidos_na_fila'])} entraram na fila ({decimal(100*fatos['fracao_efetiva'],2)}% do lote). Essa proporção é a cobertura operacional da fila, não a taxa de atraso."),
                   paragrafo('Como utilizar','subtitulo'),
                   paragrafo('Use a fila para organizar a revisão. Antes de agir, confira o prazo e os dados do pedido nas fontes operacionais. Registre as decisões humanas e acompanhe seus resultados; esta análise histórica não comprova redução de atrasos.'),
                   paragrafo('Limites e origem dos dados','subtitulo'),
                   paragrafo('Fonte: registros reais e anonimizados da base pública Olist (2016-2018), na partição de validação do projeto. Os pedidos fictícios da loja e do rastreio demonstrativo não compõem este relatório.','nota'),
                   paragrafo('A classificação usa o modelo já carregado pela aplicação. Não houve treinamento ou nova inferência durante a exportação. Faltam rótulos observados neste resumo para calcular precision, recall, F1 ou acurácia; por isso essas métricas não são apresentadas.','nota'),
                   paragrafo('A GenAI recebe somente indicadores agregados, sem identificadores de pedidos, nomes ou e-mails. O texto gerado pode conter erros e deve ser revisado. Os números e os gráficos são calculados pelo código, independentemente da resposta da IA.','nota'),
                   paragrafo('Identificação da análise: '+analise_id,'nota')])
    doc.build(blocos,onFirstPage=pagina,onLaterPages=pagina)
    return saida.getvalue()
