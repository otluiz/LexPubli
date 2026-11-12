"""Devolve os acentos que o PNCP tira dos nomes de órgãos.

A razão social chega em maiúsculas e sem acento ("SECRETARIA DE ESTADO DA
ADMINISTRACAO E DA PREVIDENCIA"). O `_nome_orgao` acerta as maiúsculas; aqui
se acertam os acentos, palavra por palavra:

1. dicionário explícito (concursos/dados/acentos.json), para o que não segue
   regra: "saude" -> "saúde", "policia" -> "polícia";
2. terminações regulares do português, que não têm forma sem acento em nome
   de órgão: -cao/-coes, -sao/-soes depois de "s" ou "i", -encia/-ancia, -erio.

Palavra em maiúsculas (sigla: SEAP, TJPE) não é tocada. Palavra que já tem
acento também não: o que o curador corrigiu fica como está.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent / "dados" / "acentos.json"

TERMINACOES = [
    (re.compile(r"cao$"), "ção"), (re.compile(r"coes$"), "ções"),
    (re.compile(r"(?<=[si])sao$"), "são"), (re.compile(r"(?<=[si])soes$"), "sões"),
    (re.compile(r"encia$"), "ência"), (re.compile(r"encias$"), "ências"),
    (re.compile(r"ancia$"), "ância"), (re.compile(r"ancias$"), "âncias"),
    (re.compile(r"erio$"), "ério"), (re.compile(r"erios$"), "érios"),
]


@lru_cache(maxsize=1)
def dicionario() -> dict[str, str]:
    return json.loads(ARQUIVO.read_text(encoding="utf-8"))["palavras"]


def _palavra(m: re.Match) -> str:
    original = m.group(0)
    if not original.isascii() or (len(original) > 1 and original.isupper()):
        return original
    base = original.lower()
    nova = dicionario().get(base)
    if nova is None and len(base) > 4:
        for padrao, troca in TERMINACOES:
            if padrao.search(base):
                nova = padrao.sub(troca, base)
                break
    if nova is None:
        return original
    return nova[0].upper() + nova[1:] if original[0].isupper() else nova


def acentuar(nome: str) -> str:
    """'Secretaria de Estado da Administracao' -> 'Secretaria de Estado da Administração'."""
    return re.sub(r"[A-Za-z]+", _palavra, nome or "")
