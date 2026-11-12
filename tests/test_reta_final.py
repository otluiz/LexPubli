"""Reta final: inscrições encerradas e prova com data (decisão de 12/11).

Quem já se inscreveu e tem data de prova está estudando agora: é o público
principal do LexLearn. O portal põe esses concursos em primeiro lugar, com a
contagem até a prova.
"""
import re

from tests.test_portal import _datas


def test_inscricoes_encerradas_com_prova_futura_e_reta_final(client, exemplo):
    c = exemplo["concurso"]
    _datas(c, inicio=-40, fim=-5, prova=32)
    assert c.situacao_classe == "prova-marcada"
    assert c.situacao.startswith("Prova em ")
    assert c.contagem_prova == "faltam 32 dias para a prova"
    home = client.get("/").content.decode()
    assert "Reta final: prova marcada" in home and "faltam 32 dias para a prova" in home
    pagina = client.get("/sefaz-al-2026/").content.decode()
    assert "Faltam 32 dias para a prova. Hora de treinar." in pagina


def test_reta_final_vem_antes_dos_outros_grupos(client, exemplo):
    _datas(exemplo["concurso"], inicio=-40, fim=-5, prova=10)
    home = client.get("/").content.decode()
    grupos = re.findall(r'<section class="grupo grupo-([\w-]+)">', home)
    assert grupos[0] == "reta-final"


def test_sem_data_de_prova_nao_e_reta_final(exemplo):
    c = exemplo["concurso"]
    _datas(c, inicio=-40, fim=-5)
    assert c.situacao_classe == "encerrado"
    _datas(c, inicio=-40, fim=-5, prova=0)
    assert c.contagem_prova == "a prova é hoje" and c.situacao_classe == "prova-marcada"
    _datas(c, inicio=-40, fim=-5, prova=1)
    assert c.contagem_prova == "a prova é amanhã"


def test_status_encerrado_sem_datas_de_inscricao_tambem_conta(exemplo):
    c = exemplo["concurso"]
    _datas(c, prova=20)
    c.status = "inscricoes_encerradas"
    c.save_revision().publish()
    assert c.situacao_classe == "prova-marcada"


def test_reta_final_ordena_pela_prova_mais_proxima(client, exemplo):
    from concursos.models import ConcursoPage, ConcursosIndexPage

    _datas(exemplo["concurso"], inicio=-40, fim=-5, prova=50)
    outro = ConcursoPage(title="TJPE 2026 — Analista", slug="tjpe-2026", orgao=exemplo["concurso"].orgao,
                         ano=2026, status="edital_aberto", fonte_url="https://www.tjpe.jus.br/x",
                         contest_slug="tjpe_2026")
    ConcursosIndexPage.objects.get().add_child(instance=outro)
    _datas(outro, inicio=-40, fim=-5, prova=9)
    home = client.get("/").content.decode()
    assert home.index("tjpe-2026") < home.index("sefaz-al-2026")


def test_painel_avisa_concurso_encerrado_sem_data_de_prova(exemplo):
    from concursos.wagtail_hooks import concursos_sem_data_de_prova

    c = exemplo["concurso"]
    _datas(c, inicio=-40, fim=-5)
    assert [x.pk for x in concursos_sem_data_de_prova()] == [c.pk]
    _datas(c, inicio=-40, fim=-5, prova=20)
    assert concursos_sem_data_de_prova() == []


def test_painel_aparece_no_admin(client, exemplo, django_user_model):
    _datas(exemplo["concurso"], inicio=-40, fim=-5)
    client.force_login(django_user_model.objects.create_superuser("adm", "a@x.br", "s"))
    from django.conf import settings

    html = client.get("/" + settings.LEXPUBLI_ADMIN_PATH).content.decode()
    assert "Inscrições encerradas sem data de prova (1)" in html
