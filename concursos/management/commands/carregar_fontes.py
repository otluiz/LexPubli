"""Carrega as fontes de descoberta de uma onda (ADR-0007 §3).

Os dados ficam versionados em concursos/dados/fontes_onda_<x>.json, com o
resultado da conferência de cada fonte (texto sem JS, robots.txt). Idempotente
pela URL: uma fonte que já existe NÃO é alterada, porque depois de carregada
ela é do curador (ativar, desativar, mudar prioridade). Use --atualizar para
sobrescrever com o arquivo.
"""
import datetime as dt
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from concursos.models import Fonte

DADOS = Path(__file__).resolve().parents[2] / "dados"
CAMPOS = ("nome", "poder", "esfera", "onda", "tipo", "carreira_sugerida", "prioridade",
          "intervalo_horas", "ativa", "motivo_inativa")


class Command(BaseCommand):
    help = "Carrega as fontes de uma onda (A, B, C) a partir de concursos/dados/."

    def add_arguments(self, parser):
        parser.add_argument("onda", choices=["A", "B", "C", "a", "b", "c"])
        parser.add_argument("--atualizar", action="store_true",
                            help="sobrescreve as fontes que já existem (perde ajustes do curador)")

    @transaction.atomic
    def handle(self, *args, onda, atualizar, **opts):
        arquivo = DADOS / f"fontes_onda_{onda.lower()}.json"
        if not arquivo.exists():
            raise CommandError(f"{arquivo} não existe")
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        criadas = atualizadas = mantidas = 0
        for item in dados["fontes"]:
            valores = {c: item[c] for c in CAMPOS if c in item}
            if item.get("conferida_em"):
                valores["conferida_em"] = dt.date.fromisoformat(item["conferida_em"])
            fonte = Fonte.objects.filter(url=item["url"]).first()
            if fonte and not atualizar:
                mantidas += 1
                continue
            fonte = fonte or Fonte(url=item["url"])
            novo = fonte.pk is None
            for campo, valor in valores.items():
                setattr(fonte, campo, valor)
            try:
                fonte.full_clean()
            except ValidationError as exc:
                raise CommandError(f"{item['nome']}: {exc.message_dict}") from exc
            fonte.save()
            criadas, atualizadas = criadas + novo, atualizadas + (not novo)
        ativas = Fonte.objects.filter(onda=onda.upper(), ativa=True).count()
        self.stdout.write(self.style.SUCCESS(
            f"onda {onda.upper()}: {criadas} criada(s), {atualizadas} atualizada(s), "
            f"{mantidas} mantida(s); {ativas} ativa(s)"))
