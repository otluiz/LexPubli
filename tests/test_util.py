import time

from concursos.util import slug_lex, uuid7


def test_slug_identico_ao_lexcorpus():
    assert slug_lex("PC-PE 2024 - Delegado") == "pc_pe_2024_delegado"
    assert slug_lex("SEFAZ-AL") == "sefaz_al"
    assert slug_lex("Administração Tributária") == "administracao_tributaria"
    assert slug_lex("") == ""


def test_uuid7_versao_variante_e_ordem():
    a = uuid7()
    time.sleep(0.002)
    b = uuid7()
    assert a.version == 7 and b.version == 7
    assert a.variant == "specified in RFC 4122"
    assert a < b  # ordenável pelo tempo
