"""Trilhas de carreira (ADR-0012): o radar recorta por carreira, não por esfera.

Uma publicação do PNCP pertence a uma trilha pelo órgão (razão social e
unidade compradora) ou pelo objeto do contrato. O objeto quase nunca cita o
cargo ("concurso público para provimento de cargos"), então o órgão pesa
mais. Tudo em texto sem acento e minúsculo (orgaos._plano).
"""
from __future__ import annotations

import re

from .orgaos import _plano

# Rede Federal de EPCT: os IFs, os dois CEFETs, a UTFPR e o Colégio Pedro II
RE_REDE_FEDERAL = re.compile(
    r"instituto federal|centro federal de educacao tecnologica|\bcefet\b|colegio pedro ii|"
    r"universidade tecnologica federal")
# só para medir, por enquanto (ADR-0012 D1: universidades depois)
RE_UNIVERSIDADE_FEDERAL = re.compile(r"universidade federal|fundacao universidade")

# Fiscal e controle: fazenda, receita, tributação; tribunais de contas e controladorias
RE_FISCAL_ORGAO = re.compile(
    r"fazenda|financas|receita|tributa|arrecadacao|tribunal de contas|controladoria|"
    r"auditoria geral|controle interno")
RE_FISCAL_OBJETO = re.compile(
    r"auditor|fiscal de (tributos|rendas|receita)|fiscal (municipal|tributario|de tributos)|"
    r"tributari|fazendari|controle externo|controle interno|\biss\b|\bissqn\b|\bitbi\b|\biptu\b")

# Jurídica: procuradorias (procurador do município, do estado, advocacia pública)
RE_JURIDICA_ORGAO = re.compile(r"procuradoria|advocacia geral|advocacia-geral")
RE_JURIDICA_OBJETO = re.compile(r"procurador|advogado publico|advogado municipal")

TRILHAS = {
    "rede_federal": "Rede Federal de EPCT",
    "fiscal_controle": "Fiscal e controle",
    "juridica": "Jurídica (procuradorias)",
    "universidade_federal": "Universidade federal (só medição)",
}


def trilhas(razao: str, unidade: str = "", objeto: str = "") -> list[str]:
    """As trilhas da publicação, em ordem fixa; [] se nenhuma."""
    orgao, obj = _plano(f"{razao} {unidade}"), _plano(objeto)
    saida = []
    if RE_REDE_FEDERAL.search(orgao):
        saida.append("rede_federal")
    elif RE_UNIVERSIDADE_FEDERAL.search(orgao):
        saida.append("universidade_federal")
    if RE_FISCAL_ORGAO.search(orgao) or RE_FISCAL_OBJETO.search(obj):
        saida.append("fiscal_controle")
    if RE_JURIDICA_ORGAO.search(orgao) or RE_JURIDICA_OBJETO.search(obj):
        saida.append("juridica")
    return saida
