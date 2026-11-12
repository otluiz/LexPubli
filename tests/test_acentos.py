"""Acentos nos nomes de órgãos que chegam do PNCP sem acento."""
import io

import pytest
from django.core.management import call_command

from concursos.acentos import acentuar
from concursos.pncp import _nome_orgao


@pytest.mark.parametrize("razao, nome", [
    ("SECRETARIA DE ESTADO DA ADMINISTRACAO E DA PREVIDENCIA - SEAP",
     "Secretaria de Estado da Administração e da Previdência - Seap"),
    ("CONSELHO REGIONAL DE MEDICINA VETERINARIA DO ESTADO DE MATO GROSSO DO SUL",
     "Conselho Regional de Medicina Veterinária do Estado de Mato Grosso do Sul"),
    ("TRIBUNAL REGIONAL DO TRABALHO DA 8A REGIAO", "Tribunal Regional do Trabalho da 8ª Região"),
    ("MINISTERIO DA SAUDE", "Ministério da Saúde"),
    ("DEFENSORIA PUBLICA DO ESTADO DO PIAUI", "Defensoria Pública do Estado do Piauí"),
    ("FUNDACAO DE AMPARO A PESQUISA", "Fundação de Amparo a Pesquisa"),
    ("PREFEITURA MUNICIPAL DE SAO JOSE DOS CAMPOS", "Prefeitura Municipal de São José dos Campos"),
])
def test_nome_do_pncp_sai_acentuado(razao, nome):
    assert _nome_orgao(razao) == nome


def test_sigla_e_palavra_ja_acentuada_ficam_como_estao():
    assert acentuar("SEAP") == "SEAP"
    assert acentuar("Secretária") == "Secretária"           # o curador decidiu
    assert acentuar("Secretaria da Fazenda") == "Secretaria da Fazenda"
    assert acentuar("Casa da Moeda") == "Casa da Moeda"      # "-sao" só depois de s/i: "casa" não
    assert acentuar("Divisao e Comissao") == "Divisão e Comissão"


def test_comando_mostra_sem_gravar_e_grava_com_aplicar(exemplo):
    from concursos.models import Orgao

    orgao = exemplo["concurso"].orgao
    orgao.nome, orgao.sigla = "Secretaria da Fazenda Publica", ""
    orgao.save()
    pagina = exemplo["concurso"]
    pagina.title = "Secretaria da Fazenda Publica 2026: concurso autorizado"
    pagina.save_revision().publish()

    saida = io.StringIO()
    call_command("acentuar_orgaos", stdout=saida)
    assert "-> Secretaria da Fazenda Pública" in saida.getvalue()
    assert Orgao.objects.get(pk=orgao.pk).nome == "Secretaria da Fazenda Publica"

    call_command("acentuar_orgaos", "--aplicar", stdout=io.StringIO())
    assert Orgao.objects.get(pk=orgao.pk).nome == "Secretaria da Fazenda Pública"
    pagina.refresh_from_db()
    assert pagina.title == "Secretaria da Fazenda Pública 2026: concurso autorizado"
    assert pagina.slug == "sefaz-al-2026"                      # URL não muda

    segunda = io.StringIO()
    call_command("acentuar_orgaos", "--aplicar", stdout=segunda)
    assert "0 órgão(s)" in segunda.getvalue()
