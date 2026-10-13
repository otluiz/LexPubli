"""Busca oficial das pistas dos sites de concursos (ADR-0008 §3). 1x/dia,
depois do coletar_pncp.

    python manage.py processar_pistas
"""
from django.core.management.base import BaseCommand

from concursos.pistas import processar


class Command(BaseCommand):
    help = "Dispara a busca oficial das pistas e confirma ou expira as que aguardam."

    def handle(self, *args, **opts):
        r = processar()
        for erro in r["erros"]:
            self.stdout.write(self.style.WARNING(f"  {erro}"))
        self.stdout.write(self.style.SUCCESS(
            f"{r['buscadas']} pista(s) buscada(s): {r['checagens']} checagem(ns) de fonte oficial, "
            f"{r['pncp']} consulta(s) ao PNCP; {r['confirmadas']} confirmada(s), "
            f"{r['expiradas']} expirada(s)"))
