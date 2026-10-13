"""Identificadores e slugs compartilhados com o ecossistema Lex."""
from __future__ import annotations

import os
import re
import time
import unicodedata
import uuid

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slug_lex(texto: str) -> str:
    """Rótulo cru -> slug canônico, idêntico ao `lexcorpus.util.slugify`.

    Mesmo algoritmo de propósito: banca e órgão precisam casar entre os
    projetos sem tabela de tradução. 'PC-PE 2024 - Delegado' -> 'pc_pe_2024_delegado'.
    """
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return _SLUG_STRIP.sub("_", sem_acento.lower()).strip("_")


def uuid7() -> uuid.UUID:
    """UUIDv7 (RFC 9562): 48 bits de timestamp em ms + 74 bits aleatórios.

    Ordenável no tempo, como pede a convenção do README. O módulo `uuid`
    só ganha uuid7() no Python 3.14; o ecossistema está no 3.11.
    """
    ms = time.time_ns() // 1_000_000
    aleatorio = int.from_bytes(os.urandom(10), "big")
    rand_a = (aleatorio >> 62) & 0xFFF
    rand_b = aleatorio & ((1 << 62) - 1)
    valor = (ms & ((1 << 48) - 1)) << 80 | 0x7 << 76 | rand_a << 64 | 0b10 << 62 | rand_b
    return uuid.UUID(int=valor)


# Domínios de fonte oficial (ADR-0002, ADR-0007 §1). `.def.br` entra junto:
# as Defensorias vêm com o MP (ADR-0007 §3) e o domínio delas é esse.
SUFIXOS_OFICIAIS = (".gov.br", ".leg.br", ".jus.br", ".mp.br", ".def.br")


def _host(url: str) -> str:
    from urllib.parse import urlsplit

    host = (urlsplit(url or "").hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def dominio_oficial(url: str, sites_de_banca=()) -> bool:
    """A URL é de fonte oficial? Domínio de governo (.gov.br, .leg.br,
    .jus.br, .mp.br, .def.br) ou o site de uma banca cadastrada (e os
    subdomínios dele: cdn.cebraspe.org.br vale por www.cebraspe.org.br).
    Agregador (PCI etc.) nunca: ele é só índice."""
    host = _host(url)
    if not host:
        return False
    if any(host.endswith(s) or host == s[1:] for s in SUFIXOS_OFICIAIS):
        return True
    for site in sites_de_banca:
        base = _host(site)
        if base and (host == base or host.endswith("." + base)):
            return True
    return False
