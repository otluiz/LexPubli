import pytest
from django.core.management import call_command


@pytest.fixture
def exemplo(db):
    """Portal com o Sefaz-AL 2026 publicado e uma descoberta pendente."""
    call_command("carregar_exemplo", stdout=open("/dev/null", "w"))
    from concursos.models import ConcursoPage, Descoberta

    return {
        "concurso": ConcursoPage.objects.get(contest_slug="sefaz_al_2026"),
        "descoberta": Descoberta.objects.get(chave_dedup="exemplo-sefaz-al-2026"),
    }


class PublicadorFalso:
    def __init__(self, falhar=False):
        self.enviados, self.falhar = [], falhar

    def publicar(self, envelope):
        if self.falhar:
            raise ConnectionError("broker fora do ar")
        self.enviados.append(envelope)


@pytest.fixture
def publicador():
    return PublicadorFalso()


@pytest.fixture(autouse=True)
def _caderno_pncp_isolado(settings, tmp_path):
    """Cada teste com o seu caderno do PNCP: o caderno é ponto de retomada,
    e um dia gravado por um teste pularia o PNCP no seguinte."""
    settings.LEXPUBLI_PNCP_CADERNO = tmp_path / "pncp_caderno"
