"""Gerar diagramas documentais editáveis; não processa pedidos nem treina ML."""
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/diagramas"
INK, MUTED, BLUE, TEAL = "#17364d", "#5b7082", "#167baf", "#087f75"


class SVG:
    def __init__(self, width, height, title, subtitle):
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">', '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#66859a"/></marker></defs>', f'<rect width="{width}" height="{height}" fill="#f5f8fb"/>']
        self.text(40, 54, title, 29, INK, True)
        self.text(40, 88, subtitle, 16, MUTED)

    def text(self, x, y, content, size=16, color=INK, bold=False):
        self.parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="Arial, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}">{escape(content)}</text>')

    def edge(self, points, label="", label_pos=None, dashed=False):
        coords = " ".join(f"{x},{y}" for x, y in points)
        self.parts.append(f'<polyline points="{coords}" fill="none" stroke="#66859a" stroke-width="2.2" marker-end="url(#arrow)"'+(' stroke-dasharray="7 5"' if dashed else '')+'/>')
        if label:
            self.text(*label_pos, label, 14, MUTED)

    def box(self, x, y, w, h, title, lines, accent=BLUE):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="white" stroke="#cbd9e4" stroke-width="1.5"/><rect x="{x}" y="{y}" width="{w}" height="7" rx="3" fill="{accent}"/>')
        self.text(x + 16, y + 35, title, 19, accent, True)
        for i, line in enumerate(lines):
            self.text(x + 16, y + 64 + 24 * i, line, 16)

    def save(self, path):
        path.write_text("\n".join(self.parts + ["</svg>"]) + "\n", encoding="utf-8")


def architecture():
    s = SVG(1440, 980, "EntregaCerta AI · Arquitetura", "Projeto da etapa 2 — componentes de negócio serão implementados nas etapas 3 a 7.")
    s.edge([(250, 245), (320, 245)], "originais", (254, 230))
    s.edge([(570, 245), (665, 245)], "tratados", (582, 230))
    s.edge([(915, 245), (1025, 245)], "só treino", (936, 230))
    s.edge([(1150, 315), (1150, 380)])
    s.edge([(1025, 430), (915, 480)], "pipeline salvo", (935, 414))
    s.edge([(790, 315), (790, 435)], "consulta / registro", (802, 367))
    s.edge([(665, 490), (570, 490)], "HTTP", (590, 473))
    s.edge([(320, 500), (250, 500)])
    s.edge([(790, 565), (790, 690)], "opcional", (802, 629), True)
    s.edge([(1025, 750), (915, 750)], "evidências", (930, 733), True)
    s.box(40, 180, 210, 135, "Fonte Olist", ["ZIP original", "CSV reais", "hashes + licença"])
    s.box(320, 180, 250, 135, "Preparação", ["Pandas + SQL", "regras e atributos", "scripts reproduzíveis"])
    s.box(665, 180, 250, 135, "SQLite", ["pedidos e atributos", "desfechos separados", "revisões e relatórios"])
    s.box(1025, 180, 290, 135, "Treinamento offline", ["Scikit-learn", "comparação temporal", "teste reservado"], TEAL)
    s.box(1025, 380, 290, 110, "Artefato versionado", ["pipeline + manifesto", "métricas e limitações"], TEAL)
    s.box(665, 435, 250, 130, "Backend · FastAPI", ["consulta e inferência", "fila e revisão", "controle de evidências"])
    s.box(320, 435, 250, 130, "Interface · Streamlit", ["filtros e gráficos", "previsões e relatórios", "acompanhamento"])
    s.box(40, 435, 210, 130, "Analista", ["revisão humana", "registro de decisão", "apoio operacional"], TEAL)
    s.box(665, 690, 250, 140, "GenAI por API", ["relatório fundamentado", "validação de saída", "falha não bloqueia ML"], TEAL)
    s.box(1025, 690, 290, 140, "Contexto controlado", ["fatos calculados", "documentação do modelo", "chaves só no backend"], TEAL)
    s.parts.append('<rect x="40" y="875" width="1275" height="64" rx="10" fill="#e3edf5"/>')
    s.text(58, 902, "Terraform · etapa 7", 18, INK, True)
    s.text(58, 925, "Provisionamento local previsto: containers, rede e persistência. Sem cluster ou microsserviços de domínio.", 16)
    s.save(OUT / "arquitetura.svg")
    (OUT / "arquitetura.mmd").write_text('''flowchart LR
  A[ZIP Olist e manifesto] --> B[Pandas e preparação SQL]
  B --> C[(SQLite)]
  C --> D[Treinamento temporal offline]
  D --> E[Pipeline e manifesto]
  E --> F[Backend FastAPI]
  C <--> F
  F <--> G[Interface Streamlit]
  G <--> H[Analista]
  F -. contexto controlado .-> I[GenAI por API]
  J[Documentação e fatos calculados] -.-> I
  I -. relatório .-> F
  K[Terraform: containers, rede e persistência na etapa 7]
''', encoding="utf-8")


TABLES = [
    ("customers", 50, 140, ["PK customer_id", "customer_unique_id (linhagem)", "zip_prefix, city, state"]),
    ("orders", 520, 140, ["PK order_id", "FK customer_id", "purchase_at, approved_at", "estimated_delivery_day"]),
    ("order_outcomes", 1030, 140, ["PK/FK order_id", "final_status, delivered_at", "carrier_handoff_at", "is_late, label_observed_at", "eligible, exclusion_reasons_json"]),
    ("products", 50, 460, ["PK product_id", "category", "weight_g", "length_cm, height_cm, width_cm"]),
    ("order_items", 520, 460, ["PK (order_id, item_id)", "FK order_id, product_id, seller_id", "price, freight_value", "shipping_limit_date (não preditor)"]),
    ("sellers", 1030, 460, ["PK seller_id", "zip_prefix, city, state"]),
    ("model_versions", 50, 800, ["PK version", "artifact_sha256", "feature_version, protocol_id", "calibration_status", "metrics_path"]),
    ("predictions", 520, 800, ["PK id", "FK order_id, model_version", "score, score_kind, policy_json", "feature_snapshot_json", "created_at"]),
    ("order_features", 1030, 800, ["PK/FK order_id", "feature_version, as_of", "attributes_json", "quality_flags_json"]),
    ("reviews", 520, 1150, ["PK id", "FK prediction_id", "decision, notes", "reviewed_at"]),
    ("reports", 1030, 1150, ["PK id", "FK prediction_id, review_id?", "mode: llm ou factual_fallback", "evidence_json, content", "created_at"]),
]


def data_model():
    s = SVG(1500, 1480, "EntregaCerta AI · Modelo de dados", "Desenho lógico/DDL da etapa 2 — banco de negócio ainda não criado nem populado.")
    for points, label, pos in [
        ([(390, 250), (520, 250)], "1:N", (440, 235)),
        ([(860, 250), (1030, 250)], "1:0..1", (920, 235)),
        ([(690, 370), (690, 460)], "1:N", (704, 418)),
        ([(390, 570), (520, 570)], "1:N", (440, 555)),
        ([(1030, 570), (860, 570)], "1:N", (925, 555)),
        ([(860, 310), (975, 310), (975, 910), (1030, 910)], "1:0..1", (980, 740)),
        ([(690, 370), (690, 410), (930, 410), (930, 910), (860, 910)], "1:N", (936, 745)),
        ([(390, 910), (520, 910)], "1:N", (440, 895)),
        ([(690, 1030), (690, 1150)], "1:N", (704, 1095)),
        ([(860, 960), (930, 960), (930, 1080), (1200, 1080), (1200, 1150)], "1:N", (1000, 1065)),
        ([(860, 1260), (1030, 1260)], "1:0..N", (920, 1245)),
    ]:
        s.edge(points, label, pos)
    for name, x, y, fields in TABLES:
        s.box(x, y, 340, 230, name, fields, TEAL if name in {"order_outcomes", "order_features"} else BLUE)
    s.text(50, 1430, "PK = chave primária · FK = chave estrangeira · ? = opcional · IDs são para vínculo, não para previsão.", 16, MUTED)
    s.save(OUT / "modelo_dados.svg")
    (OUT / "modelo_dados.mmd").write_text('''erDiagram
  customers ||--o{ orders : possui
  orders ||--|{ order_items : contem
  products ||--o{ order_items : descreve
  sellers ||--o{ order_items : atende
  orders ||--o| order_features : atributos
  orders ||--o| order_outcomes : desfecho
  orders ||--o{ predictions : recebe
  model_versions ||--o{ predictions : calcula
  predictions ||--o{ reviews : revisao
  predictions ||--o{ reports : fundamenta
  reviews |o--o{ reports : referencia_opcional
''', encoding="utf-8")


NS = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL", "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI", "dc": "http://www.omg.org/spec/DD/20100524/DC", "di": "http://www.omg.org/spec/DD/20100524/DI", "xsi": "http://www.w3.org/2001/XMLSchema-instance"}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def el(parent, name, attrs=None, text=None):
    prefix, tag = name.split(":")
    child = ET.SubElement(parent, f"{{{NS[prefix]}}}{tag}", attrs or {})
    if text is not None:
        child.text = text
    return child


NODES = [
    ("startEvent", "Start_Approved", "Pedido aprovado", 80, 210, 36, 36, "App"),
    ("serviceTask", "LoadFacts", "Consultar dados disponíveis na aprovação", 160, 190, 150, 75, "App"),
    ("exclusiveGateway", "DataValid", "Dados necessários válidos?", 360, 202, 50, 50, "App"),
    ("userTask", "DataIssue", "Registrar pendência de dados", 280, 750, 160, 80, "Analyst"),
    ("endEvent", "End_DataIssue", "Aguardando correção", 490, 772, 36, 36, "Analyst"),
    ("serviceTask", "Score", "Calcular escore e registrar versão", 470, 190, 150, 75, "App"),
    ("exclusiveGateway", "InQueue", "Na fila prioritária?", 670, 202, 50, 50, "App"),
    ("serviceTask", "Monitor", "Registrar monitoramento padrão", 790, 190, 150, 75, "App"),
    ("userTask", "Review", "Revisar pedido e evidências", 630, 555, 155, 80, "Analyst"),
    ("userTask", "RegisterDecision", "Registrar decisão de acompanhamento", 835, 555, 155, 80, "Analyst"),
    ("exclusiveGateway", "Merge", "", 1040, 202, 50, 50, "App"),
    ("userTask", "ReportChoice", "Escolher se deseja relatório", 1040, 555, 150, 80, "Analyst"),
    ("exclusiveGateway", "WantReport", "Relatório solicitado?", 1250, 570, 50, 50, "Analyst"),
    ("serviceTask", "GenAI", "Gerar relatório fundamentado por API", 1250, 190, 165, 80, "App"),
    ("boundaryEvent", "GenAIError", "API indisponível", 1305, 252, 36, 36, "App"),
    ("serviceTask", "Factual", "Preparar resumo factual e aviso de indisponibilidade", 1245, 345, 175, 75, "App"),
    ("userTask", "CheckReport", "Conferir e salvar relatório", 1445, 555, 155, 80, "Analyst"),
    ("endEvent", "End_Done", "Caso registrado", 1660, 577, 36, 36, "Analyst"),
]
FLOWS = [
    ("F01", "Start_Approved", "LoadFacts", "", [(116, 228), (160, 228)]),
    ("F02", "LoadFacts", "DataValid", "", [(310, 227), (360, 227)]),
    ("F03", "DataValid", "Score", "Sim", [(410, 227), (470, 227)]),
    ("F04", "DataValid", "DataIssue", "Não", [(385, 252), (385, 680), (360, 680), (360, 750)]),
    ("F05", "DataIssue", "End_DataIssue", "", [(440, 790), (490, 790)]),
    ("F06", "Score", "InQueue", "", [(620, 227), (670, 227)]),
    ("F07", "InQueue", "Monitor", "Não", [(720, 227), (790, 227)]),
    ("F08", "InQueue", "Review", "Sim", [(695, 252), (695, 400), (708, 400), (708, 555)]),
    ("F09", "Monitor", "Merge", "", [(940, 227), (1040, 227)]),
    ("F10", "Review", "RegisterDecision", "", [(785, 595), (835, 595)]),
    ("F11", "RegisterDecision", "Merge", "", [(990, 595), (1015, 595), (1015, 360), (1065, 360), (1065, 252)]),
    ("F12", "Merge", "ReportChoice", "", [(1065, 252), (1065, 480), (1115, 480), (1115, 555)]),
    ("F13", "ReportChoice", "WantReport", "", [(1190, 595), (1250, 595)]),
    ("F14", "WantReport", "GenAI", "Sim", [(1275, 570), (1275, 500), (1195, 500), (1195, 227), (1250, 227)]),
    ("F15", "WantReport", "End_Done", "Não", [(1275, 620), (1275, 690), (1678, 690), (1678, 613)]),
    ("F16", "GenAI", "CheckReport", "", [(1415, 227), (1523, 227), (1523, 555)]),
    ("F17", "GenAIError", "Factual", "", [(1323, 288), (1323, 345)]),
    ("F18", "Factual", "CheckReport", "", [(1420, 383), (1434, 383), (1434, 595), (1445, 595)]),
    ("F19", "CheckReport", "End_Done", "", [(1600, 595), (1660, 595)]),
]


def bpmn():
    root = ET.Element(f"{{{NS['bpmn']}}}definitions", {"id": "Definitions_EntregaCerta", "targetNamespace": "https://entregacerta.local/process", "exporter": "EntregaCerta planning tools", "exporterVersion": "0.2.0"})
    el(root, "bpmn:error", {"id": "Error_GenAIUnavailable", "name": "GenAI indisponível", "errorCode": "GENAI_UNAVAILABLE"})
    process = el(root, "bpmn:process", {"id": "Process_EntregaCerta", "name": "Acompanhar risco de atraso", "isExecutable": "false"})
    el(process, "bpmn:documentation", text="Processo documental do protótipo. A fila apoia revisão humana; indisponibilidade da API não impede inferência nem consulta. Não representa automação de contato com transportadoras.")
    lane_set = el(process, "bpmn:laneSet", {"id": "Lanes"})
    for lane_id, lane_name in [("App", "EntregaCerta AI"), ("Analyst", "Analista de operações")]:
        lane = el(lane_set, "bpmn:lane", {"id": "Lane_" + lane_id, "name": lane_name})
        for node in NODES:
            if node[-1] == lane_id:
                el(lane, "bpmn:flowNodeRef", text=node[1])
    for kind, node_id, name, *_ in NODES:
        attrs = {"id": node_id}
        if name:
            attrs["name"] = name
        if node_id in {"DataValid", "InQueue", "WantReport"}:
            attrs["default"] = {"DataValid": "F04", "InQueue": "F07", "WantReport": "F15"}[node_id]
        if kind == "boundaryEvent":
            attrs.update({"attachedToRef": "GenAI", "cancelActivity": "true"})
        element = el(process, "bpmn:" + kind, attrs)
        for flow_id, source, target, _, _ in FLOWS:
            if target == node_id:
                el(element, "bpmn:incoming", text=flow_id)
            if source == node_id:
                el(element, "bpmn:outgoing", text=flow_id)
        if kind == "boundaryEvent":
            el(element, "bpmn:errorEventDefinition", {"id": "ErrorDefinition_GenAI", "errorRef": "Error_GenAIUnavailable"})
    for flow_id, source, target, name, _ in FLOWS:
        attrs = {"id": flow_id, "sourceRef": source, "targetRef": target}
        if name:
            attrs["name"] = name
        flow = el(process, "bpmn:sequenceFlow", attrs)
        if flow_id in {"F03", "F08", "F14"}:
            condition = {"F03": "dados_validos", "F08": "pedido_prioritario", "F14": "relatorio_solicitado"}[flow_id]
            el(flow, "bpmn:conditionExpression", {f"{{{NS['xsi']}}}type": "bpmn:tFormalExpression"}, condition)
    collab = el(root, "bpmn:collaboration", {"id": "Collaboration_EntregaCerta"})
    el(collab, "bpmn:participant", {"id": "Participant_EntregaCerta", "name": "EntregaCerta AI · acompanhamento de pedidos", "processRef": "Process_EntregaCerta"})
    diagram = el(root, "bpmndi:BPMNDiagram", {"id": "Diagram_EntregaCerta"})
    plane = el(diagram, "bpmndi:BPMNPlane", {"id": "Plane_EntregaCerta", "bpmnElement": "Collaboration_EntregaCerta"})

    def shape(node_id, x, y, w, h, horizontal=False, label=None):
        attrs = {"id": "Shape_" + node_id, "bpmnElement": node_id}
        if horizontal:
            attrs["isHorizontal"] = "true"
        sh = el(plane, "bpmndi:BPMNShape", attrs)
        el(sh, "dc:Bounds", {"x": str(x), "y": str(y), "width": str(w), "height": str(h)})
        if label:
            lab = el(sh, "bpmndi:BPMNLabel")
            el(lab, "dc:Bounds", dict(zip(["x", "y", "width", "height"], map(str, label))))

    shape("Participant_EntregaCerta", 20, 90, 1740, 850, True)
    shape("Lane_App", 50, 90, 1710, 385, True)
    shape("Lane_Analyst", 50, 475, 1710, 465, True)
    for kind, node_id, name, x, y, w, h, _ in NODES:
        label = None
        if kind in {"startEvent", "endEvent", "exclusiveGateway", "boundaryEvent"} and name:
            label = (x - 40, y - 45 if kind == "exclusiveGateway" else y + h + 9, w + 80, 35)
        if kind == "startEvent":
            label = (80, 285, 105, 35)
        shape(node_id, x, y, w, h, label=label)
    label_positions = {"F03": (420, 200), "F04": (393, 480), "F07": (740, 200), "F08": (711, 402), "F14": (1210, 458), "F15": (1400, 670)}
    for flow_id, _, _, _, points in FLOWS:
        edge = el(plane, "bpmndi:BPMNEdge", {"id": "Edge_" + flow_id, "bpmnElement": flow_id})
        for x, y in points:
            el(edge, "di:waypoint", {"x": str(x), "y": str(y)})
        if flow_id in label_positions:
            label = el(edge, "bpmndi:BPMNLabel")
            x, y = label_positions[flow_id]
            el(label, "dc:Bounds", {"x": str(x), "y": str(y), "width": "40", "height": "20"})
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(OUT / "processo.bpmn", encoding="utf-8", xml_declaration=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    architecture()
    data_model()
    bpmn()
    print("Arquitetura, modelo de dados e BPMN documental gerados.")


if __name__ == "__main__":
    main()
