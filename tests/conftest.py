"""Temporários dos testes ficam dentro do projeto, inclusive em sandbox Windows."""
import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TEST_TEMP = (PROJECT / '.local/pytest-temp').resolve()
if not TEST_TEMP.is_relative_to(PROJECT):
    raise RuntimeError('Temporários devem permanecer dentro do projeto')
TEST_TEMP.mkdir(parents=True, exist_ok=True)
os.environ['PYTEST_DEBUG_TEMPROOT'] = str(TEST_TEMP)
