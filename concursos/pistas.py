"""Pistas dos sites de concursos (ADR-0008 §3).

Uma menção num site de concursos não é sinal e não pontua. Ela só dispara a
busca pela documentação oficial do órgão citado:
- a checagem imediata das Fontes oficiais dele no changedetection;
- a consulta ao PNCP daquele órgão (quando o CNPJ dele é conhecido).
Achou documento oficial: a pista é confirmada. Em 30 dias sem documento, ela
expira sozinha, sem ir para a fila de ninguém.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, timedelta

from django.utils import timezone

log = logging.getLogger(__name__)
RE_CONCURSO = re.compile(r"concurso|edital", re.I)
RE_URL = re.compile(r"https?://[^\s<>\"')]+")
PRAZO_DIAS = 30
PNCP_INTERVALO_DIAS = 7            # um órgão é consultado no PNCP no máximo 1x por semana


def registrar(fonte, mensagem: str) -> int:
    """Uma Pista por (linha que cita concurso, órgão citado). Devolve quantas
    pistas novas. Guarda só o título (a linha) e o link."""
    from .models import Pista
    from .orgaos import chaves, orgao_da_chave

    novas = 0
    for linha in mensagem.splitlines():
        linha = re.sub(r"^\s*\((?:added|changed|removed)\)\s*", "", linha).strip()
        if len(linha) < 12 or not RE_CONCURSO.search(linha) or linha.startswith("watch_uuid"):
            continue
        link = (RE_URL.findall(linha) or [""])[0]
        titulo = RE_URL.sub("", linha).strip(" -|·")[:300]
        for chave in chaves(titulo) or [""]:
            dedup = hashlib.sha256(f"{fonte.pk}|{chave}|{titulo}".encode()).hexdigest()
            _, criada = Pista.objects.get_or_create(chave_dedup=dedup, defaults={
                "fonte": fonte, "titulo": titulo, "link": link, "chave_orgao": chave,
                "orgao": orgao_da_chave(chave, criar=True) if chave else None,
                "status": Pista.Status.A_BUSCAR if chave else Pista.Status.SEM_ORGAO})
            novas += criada
    return novas


def _confirmar(pista) -> bool:
    """Há documento oficial do órgão no último ano? Liga o mais forte."""
    from .radar import forca

    desde = (pista.detectada_em.date() if pista.detectada_em else date.today()) - timedelta(days=365)
    sinais = list(pista.orgao.sinais.filter(data_documento__gte=desde)) if pista.orgao else []
    if not sinais:
        return False
    pista.sinal = max(sinais, key=lambda s: (forca(s.tipo), s.data_documento))
    pista.status = pista.Status.CONFIRMADA
    return True


def processar(*, hoje: date | None = None, cliente_cd=None, pncp_por_orgao=None) -> dict:
    """Busca oficial das pistas novas; reavalia e expira as que aguardam."""
    from .models import Pista
    from .orgaos import fontes_da_chave

    agora = timezone.now()
    hoje = hoje or agora.date()
    if pncp_por_orgao is None:
        from .pncp import por_orgao as pncp_por_orgao
    if cliente_cd is None:
        from .changedetection import configurado

        conf = configurado()
        cliente_cd = conf[0] if conf else None
    resumo = {"buscadas": 0, "confirmadas": 0, "expiradas": 0, "checagens": 0, "pncp": 0, "erros": []}
    pncp_feito: set[int] = set()
    for pista in Pista.objects.filter(status=Pista.Status.A_BUSCAR).select_related("orgao"):
        orgao = pista.orgao
        if cliente_cd is not None:
            for fonte in fontes_da_chave(pista.chave_orgao):
                if fonte.ativa and fonte.changedetection_uuid:
                    try:
                        cliente_cd.checar_agora(fonte.changedetection_uuid)
                        resumo["checagens"] += 1
                    except Exception as exc:          # changedetection fora: segue com o PNCP
                        resumo["erros"].append(f"changedetection: {exc}")
        recente = Pista.objects.filter(orgao=orgao, buscada_em__gte=agora - timedelta(
            days=PNCP_INTERVALO_DIAS)).exclude(pk=pista.pk).exists()
        if orgao and orgao.cnpj and orgao.pk not in pncp_feito and not recente:
            rel = pncp_por_orgao(orgao.cnpj, hoje=hoje)
            pncp_feito.add(orgao.pk)
            resumo["pncp"] += 1
            if rel.erro:
                resumo["erros"].append(rel.erro)
        pista.buscada_em = agora
        pista.status = Pista.Status.AGUARDANDO
        _confirmar(pista)
        pista.save()
        resumo["buscadas"] += 1
        resumo["confirmadas"] += pista.status == Pista.Status.CONFIRMADA
    for pista in Pista.objects.filter(status=Pista.Status.AGUARDANDO).select_related("orgao"):
        if _confirmar(pista):
            pista.save()
            resumo["confirmadas"] += 1
        elif pista.detectada_em < agora - timedelta(days=PRAZO_DIAS):
            pista.status = Pista.Status.EXPIRADA
            pista.save(update_fields=["status"])
            resumo["expiradas"] += 1
    return resumo
