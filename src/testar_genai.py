import json

import httpx

from .assistente_genai import responder

# Consulta os resultados reais da aplicação.
resposta_api = httpx.get(
    "http://127.0.0.1:8000/api/prioridades",
    timeout=60
)
resposta_api.raise_for_status()
dados = resposta_api.json()

contexto = {
    "contexto": dados["contexto"],
    "pedidos_avaliados": dados["pedidos_avaliados"],
    "pedidos_na_fila": dados["pedidos_na_fila"],
    "percentual_configurado_da_fila": 100 * dados["fracao_fila"],
    "observacao": dados["observacao"],
    "regra": "A fila prioriza os pedidos com maiores scores do modelo."
}

pergunta = (
    "Resuma a fila e explique como o analista deve interpretar "
    "essa priorização e suas limitações."
)

resultado = responder(pergunta, contexto)

print("CONTEXTO:")
print(json.dumps(contexto, ensure_ascii=False, indent=2))

print("\nGENAI DISPONÍVEL:", resultado["disponivel"])
print(resultado["resposta"])