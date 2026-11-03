# Fontes dos componentes de diagramação

- Schemas BPMN 2.0: OMG, [BPMN20.xsd](https://www.omg.org/spec/BPMN/20100501/BPMN20.xsd) e dependências `BPMNDI.xsd`, `DC.xsd`, `DI.xsd`, `Semantic.xsd`, preservados em `../validacao/bpmn-xsd/`. Arquivos originais mantidos.
- Modelador local: [bpmn-js](https://github.com/bpmn-io/bpmn-js), versão 18.16.0, pacote oficial [npm](https://registry.npmjs.org/bpmn-js/-/bpmn-js-18.16.0.tgz). Assets distribuídos em `vendor/bpmn-js/`, licença e README originais preservados. A marca/link bpmn.io permanece no visualizador conforme licença.
- SVGs de arquitetura/modelo relacional e fonte BPMN: criados no projeto com `scripts/build_diagrams.py`; não são figuras de desempenho do modelo.

URLs, versões e SHA-256 individuais estão em `../validacao/assets_manifest.json`. `scripts/acquire_planning_assets.py` baixa somente a lista prevista e extrai os caminhos explicitamente permitidos. Nenhum dado de pedidos ou credencial é enviado às fontes acima.
