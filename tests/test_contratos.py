"""Contratos v1: os exemplos canônicos valem, e o que fere a fronteira é recusado.

Os exemplos em contracts/events/v1/examples/ são a referência para quem
implementa o outro lado (o consumidor do LexCorpus valida a mesma coisa).
"""
import copy
import json

import pytest
from jsonschema import ValidationError

from concursos.eventos import CONTRATOS_DIR, _registro, validar

EXEMPLOS = CONTRATOS_DIR / "examples"
TIPOS_AQUISICAO = [
    "document.acquisition.completed",
    "document.acquisition.awaiting_operator",
    "document.acquisition.failed",
]


def exemplo(tipo: str) -> dict:
    return json.loads((EXEMPLOS / f"{tipo}.json").read_text(encoding="utf-8"))


def test_tipos_registrados_sao_so_eventos():
    _, por_tipo = _registro()
    assert set(por_tipo) == {"contest.discovery.created", *TIPOS_AQUISICAO}


def test_todo_tipo_tem_exemplo_valido():
    _, por_tipo = _registro()
    for tipo in por_tipo:
        validar(exemplo(tipo))
    assert {p.stem for p in EXEMPLOS.glob("*.json")} == set(por_tipo)


# --- O que a fronteira proíbe (ADR-0002) -------------------------------------
@pytest.mark.parametrize("tipo", TIPOS_AQUISICAO)
def test_resposta_exige_correlation_id(tipo):
    env = exemplo(tipo)
    env["correlation_id"] = None
    with pytest.raises(ValidationError):
        validar(env)


@pytest.mark.parametrize("tipo", TIPOS_AQUISICAO)
def test_resposta_so_pode_vir_do_lexcorpus(tipo):
    env = exemplo(tipo)
    env["producer"] = "lexpubli"
    with pytest.raises(ValidationError):
        validar(env)


def test_descoberta_so_pode_vir_do_lexpubli():
    env = exemplo("contest.discovery.created")
    validar(env)
    env["producer"] = "lexcorpus"
    with pytest.raises(ValidationError, match="lexpubli"):
        validar(env)


@pytest.mark.parametrize("campo", ["pasta_uri", "storage_uri", "arquivos"])
def test_completed_nao_carrega_storage(campo):
    env = exemplo("document.acquisition.completed")
    env["data"][campo] = "file:///data/raw/exams/cebraspe/sefaz_al_19_auditor/"
    with pytest.raises(ValidationError):
        validar(env)


# --- Campos ------------------------------------------------------------------
def mutar(tipo, caminho, valor):
    env = copy.deepcopy(exemplo(tipo))
    alvo = env
    for chave in caminho[:-1]:
        alvo = alvo[chave]
    if valor is KeyError:
        del alvo[caminho[-1]]
    else:
        alvo[caminho[-1]] = valor
    return env


@pytest.mark.parametrize("tipo,caminho,valor", [
    ("document.acquisition.completed", ["data", "relation"], "futuro"),
    ("document.acquisition.completed", ["data", "files", "prova"], -1),
    ("document.acquisition.completed", ["data", "files", "gabarito_definitivo"], KeyError),
    ("document.acquisition.completed", ["data", "lexcorpus_contest"], "Sefaz AL 19"),
    ("document.acquisition.completed", ["data", "exam_board", "slug"], "CEBRASPE"),
    ("document.acquisition.completed", ["data", "contest_id"], "não-é-uuid"),
    ("document.acquisition.awaiting_operator", ["data", "reason"], "preguica"),
    ("document.acquisition.awaiting_operator", ["data", "candidates"],
     [{"exam_board_slug": "fcc", "year": 2013}] * 11),
    ("document.acquisition.failed", ["data", "retryable"], KeyError),
    ("document.acquisition.failed", ["data", "reason"], "captcha_resolvido"),
    ("document.acquisition.failed", ["event_version"], "2.0"),
])
def test_campos_invalidos_sao_recusados(tipo, caminho, valor):
    with pytest.raises(ValidationError):
        validar(mutar(tipo, caminho, valor))


@pytest.mark.parametrize("tipo,caminho,valor", [
    ("document.acquisition.completed", ["data", "year"], None),
    ("document.acquisition.completed", ["data", "exam_board"], {"slug": "cebraspe"}),
    ("document.acquisition.completed", ["data", "positions"], KeyError),
    ("document.acquisition.completed", ["data", "source_url"], KeyError),
    ("document.acquisition.awaiting_operator", ["data", "candidates"], KeyError),
    ("document.acquisition.failed", ["data", "lexcorpus_contest"], None),
    ("document.acquisition.failed", ["event_version"], "1.3"),
])
def test_opcionais_e_minor_compativel_sao_aceitos(tipo, caminho, valor):
    validar(mutar(tipo, caminho, valor))
