"""Coletor do PNCP para o radar de sinais (ADR-0008 §4).

Licitação ou aviso de contratação direta de uma banca para concurso público
-> Sinal de força 6; contrato -> força 7. Usa só a API de consultas
DOCUMENTADA do PNCP (pncp.gov.br/api/consulta). Ela não busca por texto:
o coletor lê as publicações do dia e filtra aqui (esfera e objeto).

O PNCP limita requisições com rigor (13/10/2026: o endereço foi bloqueado por
algumas horas depois de ~20 consultas de teste em poucos minutos). Por isso:
uma rodada por dia, pausa entre requisições, e para na primeira recusa; a
rodada seguinte continua dali, porque nada é gravado duas vezes.

- contratos: /v1/contratos, todas as modalidades, 500 por página;
- contratações: /v1/contratacoes/publicacao, só dispensa (8; é como Cebraspe,
  FGV e Cesgranrio costumam ser contratadas) e concorrência eletrônica (4).
  Pregão fica de fora pelo volume: se virar contrato, aparece no contrato.

Escopo: federal, estadual e distrital. Os municipais são só contados (onda C).
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, timedelta
from urllib.parse import urlencode

API = "https://pncp.gov.br/api/consulta/v1"
APP = "https://pncp.gov.br/app"
UA = "LexPubli/0.1 (radar de concursos; dados abertos do PNCP)"
MODALIDADES = {8: "Dispensa", 4: "Concorrência eletrônica"}
ESFERAS = {"F": "federal", "E": "estadual", "D": "distrital"}

# o objeto precisa ser a REALIZAÇÃO de concurso para provimento de cargos
RE_CONCURSO = re.compile(r"concurso\s+p[uú]blico", re.I)
RE_REALIZACAO = re.compile(
    r"provimento|cargos?\b|organiza[cç][aã]o|realiza[cç][aã]o|planejamento|execu[cç][aã]o|"
    r"banca|elabora[cç][aã]o (?:e aplica[cç][aã]o )?de provas", re.I)
RE_FORA = re.compile(
    r"arquitet|urban[ií]stic|projeto (?:de|executivo)|pr[eê]mi|fotogr|liter[aá]ri|"
    r"concurso de (?:reda[cç][aã]o|desenho|beleza|fantasia|quadrilha)|julgamento de propostas", re.I)


def e_concurso_publico(objeto: str) -> bool:
    return bool(RE_CONCURSO.search(objeto) and RE_REALIZACAO.search(objeto)
                and not RE_FORA.search(objeto))


def _nome_orgao(razao: str) -> str:
    """'TRIBUNAL REGIONAL DO TRABALHO DA 8A REGIAO' -> 'Tribunal Regional do
    Trabalho da 8ª Regiao'. Acentos e siglas o curador acerta no painel."""
    pequenas = {"da", "de", "do", "das", "dos", "e", "em", "para"}
    palavras = [p.lower() if i and p.lower() in pequenas else p.capitalize()
                for i, p in enumerate(razao.strip().split())]
    return re.sub(r"\b(\d+)[aA]\b", r"\1ª", " ".join(palavras))


class ErroPncp(RuntimeError):
    pass


def http_get(caminho: str, params: dict, *, abrir=urllib.request.urlopen) -> dict:
    req = urllib.request.Request(f"{API}{caminho}?{urlencode(params)}",
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with abrir(req, timeout=60) as resp:
            if resp.status == 204:
                return {"data": [], "totalPaginas": 0}
            return json.loads(resp.read().decode() or "{}")
    except (urllib.error.URLError, ConnectionError, TimeoutError, json.JSONDecodeError) as exc:
        raise ErroPncp(f"PNCP recusou ou não respondeu ({caminho} {params}): {exc}") from exc


@dataclass
class Achado:
    """Uma publicação do PNCP já normalizada (contrato ou contratação)."""
    tipo_sinal: str
    cnpj: str
    razao: str
    esfera: str
    uf: str
    objeto: str
    data: date
    url: str
    fornecedor: str = ""


def _contrato(x: dict) -> Achado:
    o, u = x.get("orgaoEntidade") or {}, x.get("unidadeOrgao") or {}
    cnpj = o.get("cnpj", "")
    return Achado("banca_contratada", cnpj, o.get("razaoSocial", ""), o.get("esferaId", ""),
                  u.get("ufSigla", ""), x.get("objetoContrato") or "",
                  date.fromisoformat((x.get("dataAssinatura") or x["dataPublicacaoPncp"])[:10]),
                  f"{APP}/contratos/{cnpj}/{x.get('anoContrato')}/{x.get('sequencialContrato')}",
                  x.get("nomeRazaoSocialFornecedor") or "")


def _contratacao(x: dict) -> Achado:
    o, u = x.get("orgaoEntidade") or {}, x.get("unidadeOrgao") or {}
    cnpj = o.get("cnpj", "")
    return Achado("licitacao_banca", cnpj, o.get("razaoSocial", ""), o.get("esferaId", ""),
                  u.get("ufSigla", ""), x.get("objetoCompra") or "",
                  date.fromisoformat(x["dataPublicacaoPncp"][:10]),
                  f"{APP}/editais/{cnpj}/{x.get('anoCompra')}/{x.get('sequencialCompra')}")


def publicacoes(dia: date, *, get=http_get, pausa: float = 3.0):
    """Gera os Achados do dia, página a página. ErroPncp interrompe."""
    d = dia.strftime("%Y%m%d")
    consultas = [("/contratos", {"tamanhoPagina": 500}, _contrato)] + [
        ("/contratacoes/publicacao", {"codigoModalidadeContratacao": m, "tamanhoPagina": 50},
         _contratacao) for m in MODALIDADES]
    for caminho, extra, normalizar in consultas:
        pagina = 1
        while True:
            corpo = get(caminho, {"dataInicial": d, "dataFinal": d, "pagina": pagina, **extra})
            for x in corpo.get("data") or []:
                yield normalizar(x)
            if pagina >= (corpo.get("totalPaginas") or 0):
                break
            pagina += 1
            if pausa:
                time.sleep(pausa)
        if pausa:
            time.sleep(pausa)


@dataclass
class Relatorio:
    sinais: list[str] = field(default_factory=list)
    orgaos_novos: list[str] = field(default_factory=list)
    chamadas: list[str] = field(default_factory=list)
    lidos: int = 0
    ja_vistos: int = 0
    municipais: int = 0
    erro: str = ""

    def resumo(self) -> str:
        return (f"{self.lidos} publicação(ões) lida(s); {len(self.sinais)} sinal(is) novo(s), "
                f"{len(self.orgaos_novos)} órgão(s) novo(s), {len(self.chamadas)} chamada(s) no "
                f"portal; {self.ja_vistos} já visto(s), {self.municipais} de concurso municipal"
                + (f"; PAROU: {self.erro}" if self.erro else ""))


def coletar(*, dias: int = 1, hoje: date | None = None, get=http_get, pausa: float = 3.0) -> Relatorio:
    """Lê os últimos `dias` (ontem e para trás; o dia de hoje ainda está
    sendo publicado) e grava os Sinais de concurso público."""
    from .models import Orgao, Sinal
    from .radar import aplicar
    from .util import slug_lex

    rel, tocados = Relatorio(), set()
    hoje = hoje or date.today()
    try:
        for n in range(dias, 0, -1):
            for a in publicacoes(hoje - timedelta(days=n), get=get, pausa=pausa):
                rel.lidos += 1
                if not e_concurso_publico(a.objeto):
                    continue
                if a.esfera not in ESFERAS:
                    rel.municipais += 1
                    continue
                orgao = Orgao.objects.filter(cnpj=a.cnpj).first() if a.cnpj else None
                if orgao is None:
                    nome = _nome_orgao(a.razao or a.cnpj)
                    slug = slug_lex(nome)[:70]
                    if Orgao.objects.filter(slug=slug).exists():
                        slug = f"{slug[:60]}_{a.cnpj[-6:]}"
                    orgao = Orgao.objects.create(nome=nome, slug=slug, cnpj=a.cnpj,
                                                 esfera=ESFERAS[a.esfera], uf=a.uf[:2])
                    rel.orgaos_novos.append(nome)
                resumo = re.sub(r"\s+", " ", a.objeto).strip()
                if a.fornecedor:
                    resumo = f"{resumo} Contratada: {a.fornecedor}."
                sinal, novo = Sinal.objects.get_or_create(
                    orgao=orgao, tipo=a.tipo_sinal, documento_url=a.url,
                    defaults={"data_documento": a.data, "origem": Sinal.Origem.PNCP,
                              "resumo": resumo[:300]})
                if not novo:
                    rel.ja_vistos += 1
                    continue
                rel.sinais.append(f"{orgao} · {sinal.get_tipo_display()} · {a.url}")
                tocados.add(orgao.pk)
    except ErroPncp as exc:
        rel.erro = str(exc)
    for orgao in Orgao.objects.filter(pk__in=tocados):
        chamada = aplicar(orgao)
        if chamada is not None:
            rel.chamadas.append(chamada.title)
    return rel
