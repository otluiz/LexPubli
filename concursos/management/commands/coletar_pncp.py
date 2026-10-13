"""Coleta do PNCP para o radar de sinais (ADR-0008 §4). Uma vez por dia.

    python manage.py coletar_pncp            # ontem
    python manage.py coletar_pncp --dias 3   # os 3 últimos dias

Licitação/dispensa para banca de concurso -> Sinal 6; contrato -> Sinal 7.
Força >= 4 publica a chamada sozinha (opção b). Para na primeira recusa do
PNCP; rodar de novo continua, sem duplicar.
"""
from django.core.management.base import BaseCommand

from concursos.pncp import coletar


class Command(BaseCommand):
    help = "Lê as contratações do PNCP e grava os sinais de concurso (radar)."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=1, help="quantos dias para trás (padrão: ontem)")

    def handle(self, *args, dias, **opts):
        rel = coletar(dias=dias)
        for item in rel.sinais:
            self.stdout.write(f"  sinal: {item}")
        for item in rel.orgaos_novos:
            self.stdout.write(f"  órgão novo (revisar nome e sigla): {item}")
        for item in rel.chamadas:
            self.stdout.write(f"  chamada no portal: {item}")
        estilo = self.style.WARNING if rel.erro else self.style.SUCCESS
        self.stdout.write(estilo(rel.resumo()))
