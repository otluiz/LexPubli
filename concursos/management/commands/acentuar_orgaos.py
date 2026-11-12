"""Acentua os nomes de órgãos que vieram do PNCP antes do dicionário.

Sem --aplicar, só mostra o que mudaria. Com --aplicar, grava o nome do órgão
e o título das páginas de concurso que repetem esse nome, publicando uma
revisão nova (o que pode gerar contest.discovery.updated, como qualquer
publicação).

Idempotente: palavra que já tem acento não é tocada, então rodar duas vezes
não muda nada na segunda, e o que o curador corrigiu à mão fica como está.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from concursos.acentos import acentuar
from concursos.models import ConcursoPage, Orgao


class Command(BaseCommand):
    help = "Acentua nomes de órgãos (e títulos de concurso) pelo dicionário de acentos."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="grava; sem isto só mostra")

    @transaction.atomic
    def handle(self, *args, aplicar, **opts):
        orgaos = paginas = 0
        for orgao in Orgao.objects.order_by("nome"):
            novo = acentuar(orgao.nome)
            if novo == orgao.nome:
                continue
            orgaos += 1
            self.stdout.write(f"órgão  {orgao.nome}\n    -> {novo}")
            for pagina in ConcursoPage.objects.filter(orgao=orgao):
                if orgao.nome not in pagina.title:
                    continue
                titulo = pagina.title.replace(orgao.nome, novo)
                paginas += 1
                self.stdout.write(f"página {pagina.title}\n    -> {titulo}")
                if aplicar:
                    pagina.title = titulo
                    revisao = pagina.save_revision()
                    if pagina.live:
                        revisao.publish()
            if aplicar:
                orgao.nome = novo
                orgao.save(update_fields=["nome"])
        verbo = "acentuado(s)" if aplicar else "a acentuar (rode com --aplicar para gravar)"
        self.stdout.write(self.style.SUCCESS(f"{orgaos} órgão(s) e {paginas} página(s) {verbo}"))
