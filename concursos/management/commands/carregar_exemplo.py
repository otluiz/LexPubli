"""Carrega o concurso de exemplo do spike: Sefaz-AL 2026 (Cebraspe).

Dados conferidos na API oficial da Cebraspe em 12/10/2026
(apis.cebraspe.org.br/cebraspe/eventos/sefaz_al_26). Idempotente: rodar de
novo não duplica nada.
"""
import datetime as dt
from decimal import Decimal
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.models import Page, Site

from concursos.models import (Banca, Cargo, Carreira, ConcursoPage, ConcursosIndexPage, Descoberta,
                              Orgao, StatusConcurso)

FONTE = "https://www.cebraspe.org.br/concursos/SEFAZ_AL_26"
EDITAL = ("https://cdn.cebraspe.org.br/concursos/sefaz_al_26/arquivos/"
          "F317460224E42B1C2CF8434E69696571F3F5EDBE2EA2FFE3B2AC27139650B343.pdf")


class Command(BaseCommand):
    help = "Cria o índice do portal e o concurso Sefaz-AL 2026 (dados reais da Cebraspe)."

    @transaction.atomic
    def handle(self, *args, **opts):
        indice = self._indice()
        self._sincronizar_site(indice)
        orgao, _ = Orgao.objects.get_or_create(
            slug="sefaz_al",
            defaults={"nome": "Secretaria de Estado da Fazenda de Alagoas", "sigla": "SEFAZ-AL",
                      "esfera": Orgao.Esfera.ESTADUAL, "uf": "AL"},
        )
        banca, _ = Banca.objects.get_or_create(
            slug="cebraspe", defaults={"nome": "Cebraspe", "site": "https://www.cebraspe.org.br"},
        )
        concurso = ConcursoPage.objects.filter(contest_slug="sefaz_al_2026").first()
        if concurso is None:
            concurso = ConcursoPage(
                title="Sefaz-AL 2026 — Auditor Fiscal",
                slug="sefaz-al-2026",
                search_description="Concurso Sefaz-AL 2026: 40 vagas de Auditor Fiscal (AFTE), "
                                   "remuneração de R$ 25.270,68, banca Cebraspe.",
                orgao=orgao, banca=banca, ano=2026, status=StatusConcurso.EDITAL_ABERTO,
                carreira=Carreira.FISCAL,
                inscricoes_inicio=dt.date(2026, 9, 17), inscricoes_fim=dt.date(2026, 10, 21),
                edital_url=EDITAL, fonte_url=FONTE,
                resumo="<p>Inscrições até 21/10/2026, às 18h (horário de Brasília), "
                       "no site da Cebraspe.</p>",
            )
            concurso.cargos.add(Cargo(
                nome="Auditor Fiscal da Administração Tributária Estadual (AFTE)",
                vagas=40, salario=Decimal("25270.68"), escolaridade="Superior",
            ))
            indice.add_child(instance=concurso)
            concurso.save_revision().publish()
            self.stdout.write(self.style.SUCCESS(f"concurso criado: {concurso.url}"))
        else:
            self.stdout.write("concurso já existia")

        _, criada = Descoberta.objects.get_or_create(
            chave_dedup="exemplo-sefaz-al-2026",
            defaults={"titulo": "Sefaz-AL 2026: edital aberto (Cebraspe)", "fonte": "manual",
                      "fonte_url": FONTE, "resumo": "Edital nº 1 publicado em 25/08/2026."},
        )
        if criada:
            self.stdout.write(self.style.SUCCESS("descoberta pendente criada para a curadoria"))

    def _sincronizar_site(self, indice):
        """Hostname/porta do Site = LEXPUBLI_BASE_URL (o sitemap usa o Site)."""
        base = urlsplit(settings.WAGTAILADMIN_BASE_URL)
        porta = base.port or (443 if base.scheme == "https" else 80)
        Site.objects.filter(root_page=indice).update(hostname=base.hostname, port=porta)

    def _indice(self) -> ConcursosIndexPage:
        indice = ConcursosIndexPage.objects.first()
        if indice:
            return indice
        raiz = Page.get_first_root_node()
        indice = ConcursosIndexPage(title="Concursos públicos", slug="concursos",
                                    introducao="<p>Concursos abertos e previstos, com dados das fontes oficiais.</p>")
        raiz.add_child(instance=indice)
        indice.save_revision().publish()
        site = Site.objects.filter(is_default_site=True).first()
        antiga = site.root_page if site else None
        if site:
            site.root_page = indice
            site.save()
        else:
            Site.objects.create(hostname="localhost", port=80, root_page=indice, is_default_site=True)
        # A página "Welcome" que o Wagtail cria na instalação não serve ao portal.
        if antiga and antiga.specific_class is Page and antiga.depth == 2:
            antiga.delete()
        return indice
