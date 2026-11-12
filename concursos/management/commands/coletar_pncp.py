"""Coleta do PNCP para o radar de sinais (ADR-0008 §4). Uma vez por dia.

    python manage.py coletar_pncp            # ontem
    python manage.py coletar_pncp --dias 3   # os 3 últimos dias
    python manage.py coletar_pncp --desde 2026-01-01 --limite-dias 15
                                             # leitura retroativa, 15 dias por noite

Cada dia lido fica no caderno (LEXPUBLI_PNCP_CADERNO); dia que já está lá não
é pedido de novo. A leitura retroativa avança sozinha a cada rodada até
alcançar a data de --desde; o dia de ontem vem sempre primeiro.

Licitação/dispensa para banca de concurso -> Sinal 6; contrato -> Sinal 7.
Força >= 4 publica a chamada sozinha (opção b). Para na primeira recusa do
PNCP; rodar de novo continua, sem duplicar.
"""
import datetime as dt

from django.core.management.base import BaseCommand

from concursos.pncp import coletar


class Command(BaseCommand):
    help = "Lê as contratações do PNCP e grava os sinais de concurso (radar)."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=1, help="quantos dias para trás (padrão: ontem)")
        parser.add_argument("--desde", type=dt.date.fromisoformat,
                            help="AAAA-MM-DD: lê de ontem até esta data (substitui --dias)")
        parser.add_argument("--limite-dias", type=int,
                            help="no máximo N dias pedidos ao PNCP nesta rodada (os do caderno não contam)")

    def handle(self, *args, dias, desde=None, limite_dias=None, **opts):
        rel = coletar(dias=dias, desde=desde, limite_dias=limite_dias)
        for item in rel.sinais:
            self.stdout.write(f"  sinal: {item}")
        for item in rel.orgaos_novos:
            self.stdout.write(f"  órgão novo (revisar nome e sigla): {item}")
        for item in rel.chamadas:
            self.stdout.write(f"  chamada no portal: {item}")
        estilo = self.style.WARNING if rel.erro else self.style.SUCCESS
        self.stdout.write(estilo(rel.resumo()))
