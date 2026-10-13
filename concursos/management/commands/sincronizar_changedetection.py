"""Aplica o cadastro Fonte no changedetection.io (ADR-0007 §1).

    python manage.py sincronizar_changedetection --simular   # só relata
    python manage.py sincronizar_changedetection
    python manage.py sincronizar_changedetection --remover-orfaos

Idempotente: rodar de novo sem mudança no cadastro não altera nada.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from concursos.changedetection import Cliente, ErroChangedetection, notificacao, sincronizar
from concursos.models import Fonte


class Command(BaseCommand):
    help = "Cria, atualiza e pausa os watches do changedetection.io a partir das Fontes."

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true", help="só lê e relata")
        parser.add_argument("--remover-orfaos", action="store_true",
                            help="apaga watches com a etiqueta lexpubli que nenhuma Fonte reconhece")

    def handle(self, *args, simular, remover_orfaos, **opts):
        try:
            cliente = Cliente(settings.LEXPUBLI_CHANGEDETECTION_URL,
                              settings.LEXPUBLI_CHANGEDETECTION_API_KEY)
            url = notificacao(settings.LEXPUBLI_WEBHOOK_INTERNO, settings.LEXPUBLI_WEBHOOK_TOKEN)
            rel = sincronizar(Fonte.objects.filter(tipo=Fonte.Tipo.PAGINA).order_by("pk"),
                              cliente, url, simular=simular, remover_orfaos=remover_orfaos)
        except ErroChangedetection as exc:
            raise CommandError(str(exc)) from exc
        for titulo, itens in (("criadas", rel.criadas), ("atualizadas", rel.atualizadas),
                              ("pausadas", rel.pausadas), ("órfãos", rel.orfaos)):
            for item in itens:
                self.stdout.write(f"  {titulo[:-1] if titulo != 'órfãos' else 'órfão'}: {item}")
        prefixo = "SIMULAÇÃO — " if simular else ""
        self.stdout.write(self.style.SUCCESS(prefixo + rel.resumo()))
