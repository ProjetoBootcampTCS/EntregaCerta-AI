"""Compatibilidade para abrir os Joblib históricos sem regravá-los.

Alguns artefatos guardam a classe src.simulacao_logistica.cenario.Cenario.
O código de pesquisa está agora em experimentos/simulacao_logistica.
Este arquivo não é um comando de inicialização.
"""
import sys
from experimentos.simulacao_logistica import cenario

sys.modules[__name__ + '.cenario'] = cenario
