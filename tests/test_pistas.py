"""Pistas dos sites de concursos (ADR-0008 §3): disparam a busca oficial."""
import json
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from concursos import pistas, pncp
from concursos.models import Descoberta, Fonte, Orgao, Pista, Sinal
from tests.test_pncp import PncpFalso, contrato

RSS = ("(added) Concurso TRT 8: comissão formada; edital previsto para 2027 https://blog.x.com.br/trt8\n"
       "(added) Concurso TJ-SP e MP-RS: o que se sabe https://blog.x.com.br/tjsp\n"
       "(added) Dicas de redação para provas discursivas\n"
       "(added) Concurso Prefeitura de Itu: edital publicado\n")


@pytest.fixture
def gran(db):
    return Fonte.objects.create(nome="Gran — blog", tipo=Fonte.Tipo.PISTA, esfera="federal",
                                url="https://blog.grancursosonline.com.br/feed/",
                                changedetection_uuid="aaaaaaaa-1111-4222-8333-444444444444")


def test_registrar_uma_pista_por_orgao_citado(gran):
    assert pistas.registrar(gran, RSS) == 4
    por_chave = {p.chave_orgao: p for p in Pista.objects.all()}
    assert set(por_chave) == {"TRT8", "TJSP", "MPRS", ""}
    assert por_chave["TRT8"].link == "https://blog.x.com.br/trt8"
    assert por_chave["TRT8"].orgao.sigla == "TRT8" and por_chave["TRT8"].status == "a_buscar"
    assert por_chave[""].status == "sem_orgao"                  # Prefeitura de Itu: fica só registrada
    assert "redação" not in " ".join(p.titulo for p in Pista.objects.all())
    assert pistas.registrar(gran, RSS) == 0                     # reentrega não duplica


def test_webhook_de_pista_nao_vira_descoberta(client, gran, settings):
    settings.LEXPUBLI_WEBHOOK_TOKEN = "segredo"
    corpo = {"title": "[LexPubli] Gran — blog",
             "message": "https://blog.grancursosonline.com.br/feed/\n"
                        "watch_uuid: aaaaaaaa-1111-4222-8333-444444444444\n---\n" + RSS}
    r = client.post("/webhooks/changedetection/", data=json.dumps(corpo),
                    content_type="application/json", HTTP_X_LEXPUBLI_TOKEN="segredo")
    assert r.status_code == 200 and r.json()["pistas"] == 4
    assert not Descoberta.objects.exists()


class CdFalso:
    def __init__(self):
        self.checados = []

    def checar_agora(self, uuid):
        self.checados.append(uuid)


def test_busca_oficial_checa_as_fontes_e_consulta_o_pncp(gran, exemplo):
    trt8_oficial = Fonte.objects.create(nome="TRT8 — Concursos", poder="judiciario", esfera="federal",
                                        url="https://www.trt8.jus.br/concursos", ativa=True,
                                        conferida_em="2026-10-13", changedetection_uuid="u-trt8")
    pistas.registrar(gran, RSS)
    trt8 = Orgao.objects.get(sigla="TRT8")
    trt8.cnpj = "02390435000115"
    trt8.save()
    consultas = []

    def pncp_falso(cnpj, hoje):
        consultas.append(cnpj)
        return pncp.por_orgao(cnpj, hoje=hoje, get=PncpFalso(contratos=[contrato()]), pausa=0)

    cd = CdFalso()
    r = pistas.processar(hoje=date(2026, 10, 13), cliente_cd=cd, pncp_por_orgao=pncp_falso)
    assert cd.checados == ["u-trt8"] and consultas == ["02390435000115"]
    p = Pista.objects.get(chave_orgao="TRT8")
    assert p.status == "confirmada" and p.sinal.tipo == "banca_contratada"
    assert Pista.objects.get(chave_orgao="TJSP").status == "aguardando"    # sem CNPJ, sem documento
    assert r["confirmadas"] == 1 and trt8_oficial.ativa


def test_pncp_acha_o_orgao_da_pista_pela_sigla_e_grava_o_cnpj(gran, exemplo):
    pistas.registrar(gran, RSS)
    pncp.coletar(hoje=date(2026, 10, 13), get=PncpFalso(contratos=[contrato()]), pausa=0)
    trt8 = Orgao.objects.get(sigla="TRT8")
    assert trt8.cnpj == "02390435000115" and Orgao.objects.filter(cnpj="02390435000115").count() == 1
    assert trt8.sinais.count() == 1
    # a pista aguardando é confirmada na reavaliação, sem nova consulta
    Pista.objects.filter(chave_orgao="TRT8").update(status="aguardando")
    pistas.processar(hoje=date(2026, 10, 13), cliente_cd=CdFalso(), pncp_por_orgao=lambda *a, **k: None)
    assert Pista.objects.get(chave_orgao="TRT8").status == "confirmada"


def test_pista_sem_documento_expira_em_30_dias(gran):
    pistas.registrar(gran, RSS)
    Pista.objects.exclude(chave_orgao="").update(status="aguardando",
                                                 detectada_em=timezone.now() - timedelta(days=31))
    r = pistas.processar(hoje=date(2026, 10, 13), cliente_cd=CdFalso(), pncp_por_orgao=lambda *a, **k: None)
    assert r["expiradas"] == 3 and Pista.objects.filter(status="expirada").count() == 3


def test_pncp_do_mesmo_orgao_no_maximo_uma_vez_por_semana(gran):
    pistas.registrar(gran, RSS)
    Orgao.objects.filter(sigla="TRT8").update(cnpj="02390435000115")
    outra = Pista.objects.get(chave_orgao="TRT8")
    outra.pk, outra.chave_dedup, outra.status, outra.buscada_em = None, "x", "aguardando", timezone.now()
    outra.save()
    consultas = []
    pistas.processar(hoje=date(2026, 10, 13), cliente_cd=None,
                     pncp_por_orgao=lambda cnpj, hoje: consultas.append(cnpj))
    assert consultas == []


def test_site_de_concursos_nao_conta_como_fonte_oficial(client, exemplo, gran):
    gran.ativa, gran.conferida_em = True, "2026-10-13"
    gran.save()
    assert "fontes oficiais acompanhadas" in client.get("/").content.decode()
    assert "<strong>0</strong><span>fontes oficiais" in client.get("/").content.decode()


def test_carregar_pistas(db):
    call_command("carregar_fontes", "P", stdout=StringIO())
    p = Fonte.objects.filter(tipo="pista")
    assert p.count() == 4 and p.filter(ativa=True).count() == 3
