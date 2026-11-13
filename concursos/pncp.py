"""Coletor do PNCP para o radar de sinais (ADR-0008 §4).

Licitação ou aviso de contratação direta de uma banca para concurso público
-> Sinal de força 6; contrato -> força 7. Usa só a API de consultas
DOCUMENTADA do PNCP (pncp.gov.br/api/consulta). Ela não busca por texto:
o coletor lê as publicações do dia e filtra aqui (esfera e objeto).

O PNCP limita requisições com rigor (13/10/2026: o endereço foi bloqueado por
algumas horas depois de ~20 consultas de teste em poucos minutos). Por isso:
uma rodada por dia, pausa entre requisições, duas novas tentativas espaçadas
quando a conexão cai (http_get), e para se a falha persistir; a rodada
seguinte continua dali, porque nada é gravado duas vezes.

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
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
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
    Trabalho da 8ª Região'. Acentos pelo dicionário (concursos/acentos.py);
    siglas e o que o dicionário não cobre o curador acerta no painel."""
    from .acentos import acentuar

    pequenas = {"a", "as", "o", "os", "da", "de", "do", "das", "dos", "e", "em", "na", "no", "nas", "nos", "para"}
    palavras = [p.lower() if i and p.lower() in pequenas else p.capitalize()
                for i, p in enumerate(razao.strip().split())]
    return acentuar(re.sub(r"\b(\d+)[aA]\b", r"\1ª", " ".join(palavras)))


class ErroPncp(RuntimeError):
    pass


# Esperas entre tentativas. O PNCP derruba conexões de vez em quando
# ("Connection reset by peer") e responde no pedido seguinte: em 12 e 13/11,
# a mesma consulta falhou no cron e passou minutos depois, à mão. Sem
# repetir, uma queda dessas perdia a noite inteira de coleta.
ESPERAS = (15, 60)


def http_get(caminho: str, params: dict, *, abrir=urllib.request.urlopen,
             dormir=time.sleep, esperas=ESPERAS) -> dict:
    req = urllib.request.Request(f"{API}{caminho}?{urlencode(params)}",
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    for tentativa, espera in enumerate((*esperas, None), start=1):
        try:
            with abrir(req, timeout=60) as resp:
                if resp.status == 204:
                    return {"data": [], "totalPaginas": 0}
                return json.loads(resp.read().decode() or "{}")
        except (urllib.error.URLError, ConnectionError, TimeoutError, json.JSONDecodeError) as exc:
            # 4xx que não seja 429 é recusa de verdade: repetir não muda nada
            definitivo = isinstance(exc, urllib.error.HTTPError) and 400 <= exc.code < 500 and exc.code != 429
            if espera is None or definitivo:
                raise ErroPncp(f"PNCP recusou ou não respondeu ({caminho} {params}) "
                               f"na tentativa {tentativa}: {exc}") from exc
            dormir(espera)


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
    unidade: str = ""          # nome da unidade compradora (ex.: SECRETARIA DE FAZENDA)
    municipio: str = ""
    ibge: str = ""             # código IBGE do município


def _local(u: dict) -> dict:
    return {"unidade": u.get("nomeUnidade") or "", "municipio": u.get("municipioNome") or "",
            "ibge": str(u.get("codigoIbge") or "")}


def _contrato(x: dict) -> Achado:
    o, u = x.get("orgaoEntidade") or {}, x.get("unidadeOrgao") or {}
    cnpj = o.get("cnpj", "")
    return Achado("banca_contratada", cnpj, o.get("razaoSocial", ""), o.get("esferaId", ""),
                  u.get("ufSigla", ""), x.get("objetoContrato") or "",
                  date.fromisoformat((x.get("dataAssinatura") or x["dataPublicacaoPncp"])[:10]),
                  f"{APP}/contratos/{cnpj}/{x.get('anoContrato')}/{x.get('sequencialContrato')}",
                  x.get("nomeRazaoSocialFornecedor") or "", **_local(u))


def _contratacao(x: dict) -> Achado:
    o, u = x.get("orgaoEntidade") or {}, x.get("unidadeOrgao") or {}
    cnpj = o.get("cnpj", "")
    return Achado("licitacao_banca", cnpj, o.get("razaoSocial", ""), o.get("esferaId", ""),
                  u.get("ufSigla", ""), x.get("objetoCompra") or "",
                  date.fromisoformat(x["dataPublicacaoPncp"][:10]),
                  f"{APP}/editais/{cnpj}/{x.get('anoCompra')}/{x.get('sequencialCompra')}", **_local(u))


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
    dias_lidos: int = 0         # pedidos ao PNCP nesta rodada
    dias_do_caderno: int = 0    # já estavam no caderno: nenhum pedido
    dias_pendentes: int = 0     # ficaram para a próxima rodada (limite ou recusa)
    erro: str = ""

    def resumo(self) -> str:
        return (f"{self.lidos} publicação(ões) lida(s); {len(self.sinais)} sinal(is) novo(s), "
                f"{len(self.orgaos_novos)} órgão(s) novo(s), {len(self.chamadas)} chamada(s) no "
                f"portal; {self.ja_vistos} já visto(s), {self.municipais} de concurso municipal; "
                f"dias: {self.dias_lidos} lido(s) do PNCP, {self.dias_do_caderno} do caderno, "
                f"{self.dias_pendentes} pendente(s)"
                + (f"; PAROU: {self.erro}" if self.erro else ""))


def orgao_do_achado(a: Achado, rel: Relatorio | None = None):
    """O Orgao da publicação: pelo CNPJ; senão pela sigla (o resolvedor lê a
    razão social: 'TRIBUNAL REGIONAL DO TRABALHO DA 8A REGIAO' -> TRT8), e aí
    o CNPJ é gravado nele; senão é criado com o nome do PNCP."""
    from .models import Orgao
    from .orgaos import chaves, orgao_da_chave
    from .util import slug_lex

    orgao = Orgao.objects.filter(cnpj=a.cnpj).first() if a.cnpj else None
    if orgao:
        return orgao
    achadas = chaves(a.razao)
    orgao = orgao_da_chave(achadas[0]) if achadas else None
    if orgao:
        orgao.cnpj = a.cnpj
        orgao.save(update_fields=["cnpj"])
        return orgao
    nome = _nome_orgao(a.razao or a.cnpj)
    slug = slug_lex(achadas[0] if achadas else nome)[:70]
    if Orgao.objects.filter(slug=slug).exists():
        slug = f"{slug[:60]}_{a.cnpj[-6:]}"
    orgao = Orgao.objects.create(nome=nome, sigla=achadas[0] if achadas else "", slug=slug,
                                 cnpj=a.cnpj, esfera=ESFERAS[a.esfera], uf=a.uf[:2])
    if rel is not None:
        rel.orgaos_novos.append(nome)
    return orgao


def gravar(a: Achado, rel: Relatorio):
    """Filtra e grava UMA publicação como Sinal. Devolve o Orgao tocado (sinal
    novo) ou None."""
    from .models import Sinal

    if not e_concurso_publico(a.objeto):
        return None
    if a.esfera not in ESFERAS:
        rel.municipais += 1
        return None
    orgao = orgao_do_achado(a, rel)
    resumo = re.sub(r"\s+", " ", a.objeto).strip()
    if a.fornecedor:
        resumo = f"{resumo} Contratada: {a.fornecedor}."
    sinal, novo = Sinal.objects.get_or_create(
        orgao=orgao, tipo=a.tipo_sinal, documento_url=a.url,
        defaults={"data_documento": a.data, "origem": Sinal.Origem.PNCP, "resumo": resumo[:300]})
    if not novo:
        rel.ja_vistos += 1
        return None
    rel.sinais.append(f"{orgao} · {sinal.get_tipo_display()} · {a.url}")
    return orgao


# --- Caderno: o que o PNCP publicou, dia a dia --------------------------------
# Cada dia lido vira um arquivo AAAA-MM-DD.jsonl com as publicações de concurso
# público de TODAS as esferas (as municipais também: a ADR-0012 abre parte
# delas, e a medição precisa vê-las). O arquivo só é gravado quando o dia
# termina de ser lido; a existência dele é o ponto de retomada. Assim uma
# leitura retroativa longa pode ser interrompida pelo limite do PNCP e
# continuar na noite seguinte, sem pedir de novo o que já foi lido.

def caderno_dir() -> Path:
    from django.conf import settings

    return Path(settings.LEXPUBLI_PNCP_CADERNO)


def _arquivo(dia: date) -> Path:
    return caderno_dir() / f"{dia.isoformat()}.jsonl"


def ler_caderno(dia: date) -> list[Achado] | None:
    arquivo = _arquivo(dia)
    if not arquivo.exists():
        return None
    achados = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            d = json.loads(linha)
            d["data"] = date.fromisoformat(d["data"])
            achados.append(Achado(**d))
    return achados


def _gravar_caderno(dia: date, achados: list[Achado]) -> None:
    pasta = caderno_dir()
    pasta.mkdir(parents=True, exist_ok=True)
    temp = pasta / f".{dia.isoformat()}.parcial"
    with temp.open("w", encoding="utf-8") as f:
        for a in achados:
            f.write(json.dumps({**asdict(a), "data": a.data.isoformat()}, ensure_ascii=False) + "\n")
    temp.replace(_arquivo(dia))


def dias_do_caderno() -> list[date]:
    pasta = caderno_dir()
    if not pasta.exists():
        return []
    return sorted(date.fromisoformat(p.stem) for p in pasta.glob("????-??-??.jsonl"))


def coletar(*, dias: int = 1, desde: date | None = None, limite_dias: int | None = None,
            hoje: date | None = None, get=http_get, pausa: float = 3.0) -> Relatorio:
    """Lê do PNCP os dias de `desde` (ou dos últimos `dias`) até ontem — o dia
    de hoje ainda está sendo publicado — e grava os Sinais de concurso público.

    Dia que já está no caderno não é pedido de novo. `limite_dias` limita
    quantos dias vão ao PNCP nesta rodada; os mais recentes vão primeiro, para
    o dia de ontem nunca ficar para trás de uma leitura retroativa."""
    from .models import Orgao
    from .radar import aplicar

    rel, tocados = Relatorio(), set()
    hoje = hoje or date.today()
    inicio = desde or hoje - timedelta(days=dias)
    lista = [hoje - timedelta(days=n) for n in range(1, (hoje - inicio).days + 1)]   # ontem primeiro
    pedidos = 0
    try:
        for dia in lista:
            achados = ler_caderno(dia)
            if achados is None:
                if limite_dias is not None and pedidos >= limite_dias:
                    rel.dias_pendentes += 1
                    continue
                # grava os sinais à medida que lê (uma recusa no meio do dia não
                # perde o que já veio); o caderno do dia só quando o dia acaba
                achados = []
                for a in publicacoes(dia, get=get, pausa=pausa):
                    rel.lidos += 1
                    if e_concurso_publico(a.objeto):
                        achados.append(a)
                        orgao = gravar(a, rel)
                        if orgao:
                            tocados.add(orgao.pk)
                _gravar_caderno(dia, achados)
                pedidos += 1
                rel.dias_lidos += 1
            else:
                rel.dias_do_caderno += 1
                for a in achados:
                    orgao = gravar(a, rel)
                    if orgao:
                        tocados.add(orgao.pk)
    except ErroPncp as exc:
        rel.erro = str(exc)
        rel.dias_pendentes += len(lista) - rel.dias_lidos - rel.dias_do_caderno - rel.dias_pendentes
    for orgao in Orgao.objects.filter(pk__in=tocados):
        chamada = aplicar(orgao)
        if chamada is not None:
            rel.chamadas.append(chamada.title)
    return rel


def por_orgao(cnpj: str, *, hoje: date | None = None, get=http_get, pausa: float = 3.0) -> Relatorio:
    """A busca oficial disparada por uma pista: as contratações e os contratos
    de UM órgão no último ano (o PNCP aceita no máximo 365 dias por consulta)."""
    from .models import Orgao
    from .radar import aplicar

    hoje = hoje or date.today()
    ini, fim = (hoje - timedelta(days=364)).strftime("%Y%m%d"), hoje.strftime("%Y%m%d")
    consultas = [("/contratos", {"cnpjOrgao": cnpj, "tamanhoPagina": 500}, _contrato)] + [
        ("/contratacoes/publicacao", {"cnpj": cnpj, "codigoModalidadeContratacao": m,
                                      "tamanhoPagina": 50}, _contratacao) for m in MODALIDADES]
    rel, tocados = Relatorio(), set()
    try:
        for caminho, extra, normalizar in consultas:
            pagina = 1
            while True:
                corpo = get(caminho, {"dataInicial": ini, "dataFinal": fim, "pagina": pagina, **extra})
                for x in corpo.get("data") or []:
                    rel.lidos += 1
                    orgao = gravar(normalizar(x), rel)
                    if orgao:
                        tocados.add(orgao.pk)
                if pagina >= (corpo.get("totalPaginas") or 0):
                    break
                pagina += 1
                if pausa:
                    time.sleep(pausa)
            if pausa:
                time.sleep(pausa)
    except ErroPncp as exc:
        rel.erro = str(exc)
    for orgao in Orgao.objects.filter(pk__in=tocados):
        chamada = aplicar(orgao)
        if chamada is not None:
            rel.chamadas.append(chamada.title)
    return rel
