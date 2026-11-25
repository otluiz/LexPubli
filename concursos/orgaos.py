"""Resolvedor de órgão: de um texto livre a uma chave canônica (ADR-0008).

"TRT-8", "TRT da 8ª Região" e "TRIBUNAL REGIONAL DO TRABALHO DA 8A REGIAO"
viram a mesma chave, TRT8. A chave é a sigla do Orgao (normalizada) e o
prefixo do nome das Fontes das ondas A e B ("TRT8 — Concursos").

Serve a dois caminhos que precisam concordar:
- as pistas dos sites de concursos (que órgão o texto cita?);
- o coletor do PNCP (este CNPJ é de um órgão que já conhecemos?).
"""
from __future__ import annotations

import re
import unicodedata

UFS = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "goias": "GO", "maranhao": "MA",
    "mato grosso do sul": "MS", "mato grosso": "MT", "minas gerais": "MG", "para": "PA",
    "paraiba": "PB", "parana": "PR", "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ",
    "rio grande do norte": "RN", "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR",
    "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE", "tocantins": "TO",
}
ESTADO = {  # nome por extenso, para o nome do Orgao
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
    "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MS": "Mato Grosso do Sul", "MT": "Mato Grosso", "MG": "Minas Gerais", "PA": "Pará",
    "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins",
}
_UF = "|".join(sorted(UFS.values()))
_ESTADO = "|".join(sorted(UFS, key=len, reverse=True))      # "mato grosso do sul" antes de "mato grosso"

# órgãos federais únicos: chave -> (padrão no texto sem acento e em minúsculas, nome, esfera)
FEDERAIS = {
    "STF": (r"\bstf\b|supremo tribunal federal", "Supremo Tribunal Federal"),
    "STJ": (r"\bstj\b|superior tribunal de justica", "Superior Tribunal de Justiça"),
    "TST": (r"\btst\b|tribunal superior do trabalho", "Tribunal Superior do Trabalho"),
    "TSE": (r"\btse\b|tribunal superior eleitoral", "Tribunal Superior Eleitoral"),
    "STM": (r"\bstm\b|superior tribunal militar", "Superior Tribunal Militar"),
    "CNJ": (r"\bcnj\b|conselho nacional de justica", "Conselho Nacional de Justiça"),
    "CNMP": (r"\bcnmp\b|conselho nacional do ministerio publico", "Conselho Nacional do Ministério Público"),
    "CSJT": (r"\bcsjt\b|conselho superior da justica do trabalho", "Conselho Superior da Justiça do Trabalho"),
    "CJF": (r"\bcjf\b|conselho da justica federal", "Conselho da Justiça Federal"),
    "TCU": (r"\btcu\b|tribunal de contas da uniao", "Tribunal de Contas da União"),
    "MPF": (r"\bmpf\b|ministerio publico federal", "Ministério Público Federal"),
    "MPT": (r"\bmpt\b|ministerio publico do trabalho", "Ministério Público do Trabalho"),
    "MPM": (r"\bmpm\b|ministerio publico militar", "Ministério Público Militar"),
    "MPU": (r"\bmpu\b|ministerio publico da uniao", "Ministério Público da União"),
    "MPDFT": (r"\bmpdft\b|ministerio publico do distrito federal", "Ministério Público do DF e Territórios"),
    "TJDFT": (r"\btjdft\b|tribunal de justica do distrito federal", "Tribunal de Justiça do DF e Territórios"),
    "AGU": (r"\bagu\b|advocacia-geral da uniao|advocacia geral da uniao", "Advocacia-Geral da União"),
    "DPU": (r"\bdpu\b|defensoria publica da uniao", "Defensoria Pública da União"),
    "CAMARA": (r"camara dos deputados", "Câmara dos Deputados"),
    "SENADO": (r"senado federal", "Senado Federal"),
    # executivo federal: os concursos grandes que os sites de concursos mais citam
    # (medido nas pistas sem órgão do gpu01, 25/11/2026)
    "RFB": (r"\brfb\b|receita federal", "Receita Federal do Brasil"),
    "PGFN": (r"\bpgfn\b|procuradoria[- ]geral da fazenda nacional", "Procuradoria-Geral da Fazenda Nacional"),
    "STN": (r"\bstn\b|tesouro nacional", "Secretaria do Tesouro Nacional"),
    "PF": (r"\bpf\b|policia federal", "Polícia Federal"),
    "PRF": (r"\bprf\b|policia rodoviaria federal", "Polícia Rodoviária Federal"),
    "CGU": (r"\bcgu\b|controladoria[- ]geral da uniao", "Controladoria-Geral da União"),
    "BACEN": (r"\bbacen\b|\bbcb\b|banco central", "Banco Central do Brasil"),
    "INSS": (r"\binss\b|instituto nacional do seguro social", "Instituto Nacional do Seguro Social"),
    "IBGE": (r"\bibge\b|instituto brasileiro de geografia", "Instituto Brasileiro de Geografia e Estatística"),
    "CVM": (r"\bcvm\b|comissao de valores mobiliarios", "Comissão de Valores Mobiliários"),
    "SUSEP": (r"\bsusep\b|superintendencia de seguros privados", "Superintendência de Seguros Privados"),
    "PREVIC": (r"\bprevic\b|superintendencia nacional de previdencia complementar",
               "Superintendência Nacional de Previdência Complementar"),
    "MTE": (r"\bmte\b|ministerio do trabalho|auditor[- ]fiscal do trabalho|\baft\b",
            "Ministério do Trabalho e Emprego"),
    "MGI": (r"\bmgi\b|ministerio da gestao|\bcp?nu\b|concurso nacional unificado",
            "Ministério da Gestão e da Inovação em Serviços Públicos"),
    "EBSERH": (r"\bebserh\b", "Empresa Brasileira de Serviços Hospitalares"),
    "BNDES": (r"\bbndes\b", "Banco Nacional de Desenvolvimento Econômico e Social"),
    "BB": (r"\bbb\b|banco do brasil", "Banco do Brasil"),
    "CAIXA": (r"\bcef\b|caixa economica federal", "Caixa Econômica Federal"),
}

# Órgãos sem CNPJ próprio no PNCP: compram pelo CNPJ do ministério e aparecem
# lá como UNIDADE compradora (a Receita é "MINISTERIO DA FAZENDA" / "SECRETARIA
# ESPECIAL DA RECEITA FEDERAL"). CNPJs conferidos na API do PNCP em 25/11/2026.
FAZENDA, MJSP = "00394460000141", "00394494000136"
CNPJ_DO_MINISTERIO = {"RFB": FAZENDA, "PGFN": FAZENDA, "STN": FAZENDA, "PF": MJSP, "PRF": MJSP}

# famílias numeradas ou por UF: (padrão com um grupo, construtor da chave)
FAMILIAS = [
    (r"\btrt[\s\-–/]*(\d{1,2})\b|tribunal regional do trabalho da (\d{1,2})\s*(?:a|ª|o)?\s*regiao",
     lambda g: f"TRT{int(g)}"),
    (r"\btrf[\s\-–/]*(\d)\b|tribunal regional federal da (\d)\s*(?:a|ª|o)?\s*regiao",
     lambda g: f"TRF{int(g)}"),
    (rf"\btre[\s\-–/]*({_UF.lower()})\b|tribunal regional eleitoral d[aeo]s? ({_ESTADO})",
     lambda g: f"TRE-{UFS.get(g, g.upper())}"),
    (rf"\btj[\s\-–/]*({_UF.lower()})\b|tribunal de justica d[aeo]s?(?: estado d[aeo]s?)? ({_ESTADO})",
     lambda g: f"TJ{UFS.get(g, g.upper())}"),
    (rf"\bmp[\s\-–/]*({_UF.lower()})\b|ministerio publico d[aeo]s?(?: estado d[aeo]s?)? ({_ESTADO})",
     lambda g: f"MP{UFS.get(g, g.upper())}"),
]


def _plano(texto: str) -> str:
    sem = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sem if not unicodedata.combining(c)).lower()


def normalizar_sigla(sigla: str) -> str:
    """'TRT-8' -> 'TRT8', 'TRE/SP' -> 'TRE-SP', 'TJ-SP' -> 'TJSP'."""
    achadas = chaves(sigla)
    return achadas[0] if achadas else re.sub(r"[^A-Z0-9]", "", _plano(sigla).upper())


def chaves(texto: str) -> list[str]:
    """As chaves dos órgãos citados no texto, na ordem em que aparecem."""
    plano = _plano(texto)
    achados: list[tuple[int, str]] = []
    for padrao, montar in FAMILIAS:
        for m in re.finditer(padrao, plano):
            grupo = next(g for g in m.groups() if g)
            if montar(grupo).startswith(("TJDF", "MPDF")):
                continue                      # o DF tem os seus (TJDFT, MPDFT)
            achados.append((m.start(), montar(grupo)))
    for chave, (padrao, _) in FEDERAIS.items():
        m = re.search(padrao, plano)
        if m:
            achados.append((m.start(), chave))
    vistos, saida = set(), []
    for _, chave in sorted(achados):
        if chave not in vistos:
            vistos.add(chave)
            saida.append(chave)
    return saida


def nome_e_esfera(chave: str) -> tuple[str, str]:
    """Nome por extenso e esfera de uma chave, para criar o Orgao."""
    if chave in FEDERAIS:
        return FEDERAIS[chave][1], "federal"
    m = re.fullmatch(r"(TRT|TRF)(\d+)", chave)
    if m:
        tipo = "do Trabalho" if m.group(1) == "TRT" else "Federal"
        return f"Tribunal Regional {tipo} da {m.group(2)}ª Região", "federal"
    m = re.fullmatch(r"TRE-([A-Z]{2})", chave)
    if m:
        return f"Tribunal Regional Eleitoral — {ESTADO[m.group(1)]}", "federal"
    m = re.fullmatch(r"(TJ|MP)([A-Z]{2})", chave)
    if m:
        orgao = "Tribunal de Justiça" if m.group(1) == "TJ" else "Ministério Público"
        return f"{orgao} — {ESTADO[m.group(2)]}", "estadual"
    return chave, "federal"


def orgao_da_chave(chave: str, *, criar: bool = False):
    """O Orgao cuja sigla normalizada é a chave; criado se `criar`."""
    from .models import Orgao

    for o in Orgao.objects.exclude(sigla=""):
        if normalizar_sigla(o.sigla) == chave:
            return o
    if not criar:
        return None
    nome, esfera = nome_e_esfera(chave)
    uf = chave[-2:] if re.fullmatch(r"(TRE-|TJ|MP)[A-Z]{2}", chave) else ""
    return Orgao.objects.create(nome=nome, sigla=chave, esfera=esfera, uf=uf)


def cnpj_para_pncp(orgao) -> str:
    """O CNPJ com que o PNCP publica as compras do órgão: o dele ou, se ele
    compra pelo ministério (CNPJ_DO_MINISTERIO), o do ministério."""
    if orgao.cnpj:
        return orgao.cnpj
    return CNPJ_DO_MINISTERIO.get(normalizar_sigla(orgao.sigla), "") if orgao.sigla else ""


def fontes_da_chave(chave: str):
    """As Fontes oficiais do órgão: o nome começa pela chave ("TRT8 — ...")."""
    from .models import Fonte

    return [f for f in Fonte.objects.exclude(tipo=Fonte.Tipo.PISTA)
            if normalizar_sigla(f.nome.split(" — ")[0]) == chave]
