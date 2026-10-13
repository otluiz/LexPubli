"""Admin: cadastros e a fila de curadoria como snippets do Wagtail."""
import logging

from django.contrib import messages
from wagtail import hooks
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from .models import Banca, Descoberta, Fonte, Orgao, OutboxEvent


class DescobertaViewSet(SnippetViewSet):
    model = Descoberta
    icon = "search"
    menu_label = "Curadoria"
    list_display = ["titulo", "fonte_vigiada", "poder", "carreira_sugerida", "status", "concurso",
                    "detectada_em"]
    list_filter = ["status", "fonte", "fonte_vigiada__conteudo", "fonte_vigiada"]
    search_fields = ["titulo", "fonte_url", "resumo"]
    ordering = ["status", "-detectada_em"]


class OrgaoViewSet(SnippetViewSet):
    model = Orgao
    icon = "group"
    list_display = ["nome", "sigla", "slug", "esfera", "uf"]
    list_filter = ["esfera", "uf"]
    search_fields = ["nome", "sigla"]


class BancaViewSet(SnippetViewSet):
    model = Banca
    icon = "doc-full"
    list_display = ["nome", "slug", "site"]


class FonteViewSet(SnippetViewSet):
    """Fontes de descoberta por Poder (ADR-0007)."""

    model = Fonte
    icon = "site"
    menu_label = "Fontes"
    list_display = ["nome", "poder", "esfera", "onda", "conteudo", "ativa", "avisos_recebidos",
                    "avisos_ignorados"]
    list_filter = ["poder", "esfera", "onda", "conteudo", "tipo", "ativa"]
    search_fields = ["nome", "url"]


class OutboxViewSet(SnippetViewSet):
    """Só leitura na prática: quem escreve aqui é o código, não o operador."""

    model = OutboxEvent
    icon = "mail"
    list_display = ["event_type", "status", "tentativas", "criado_em", "publicado_em"]
    list_filter = ["status", "event_type"]
    inspect_view_enabled = True


class LexPubliGroup(SnippetViewSetGroup):
    menu_label = "LexPubli"
    menu_icon = "folder-open-inverse"
    menu_order = 200
    items = (DescobertaViewSet, FonteViewSet, OrgaoViewSet, BancaViewSet, OutboxViewSet)


register_snippet(LexPubliGroup)


# --- Fonte gravada no painel -> changedetection.io (ADR-0007 §1) -------------
log = logging.getLogger(__name__)
_AVISO = ("Fonte salva, mas o changedetection NÃO foi atualizado ({erro}). Rode "
          "`manage.py sincronizar_changedetection` quando ele voltar.")


def _sincronizar_fonte(request, fonte):
    from .changedetection import ErroChangedetection, configurado, sincronizar_uma

    if not isinstance(fonte, Fonte) or fonte.tipo != Fonte.Tipo.PAGINA:
        return
    try:
        conf = configurado()
        if conf is None:
            return                                   # integração desligada neste ambiente
        rel = sincronizar_uma(fonte, *conf)
    except ErroChangedetection as exc:
        log.warning("sincronização da fonte %s falhou: %s", fonte.pk, exc)
        messages.warning(request, _AVISO.format(erro=exc))
        return
    feito = ("watch criado" if rel.criadas else "watch pausado" if rel.pausadas
             else "watch atualizado" if rel.atualizadas else "watch já estava igual"
             if rel.iguais else "")
    if feito:
        messages.info(request, f"changedetection: {feito}.")


@hooks.register("after_create_snippet")
def fonte_criada(request, instance):
    _sincronizar_fonte(request, instance)


@hooks.register("after_edit_snippet")
def fonte_editada(request, instance):
    _sincronizar_fonte(request, instance)


@hooks.register("after_delete_snippet")
def fontes_apagadas(request, instances):
    """Apagar a Fonte apaga o watch (e o histórico dele). Para só parar de
    vigiar, desative a fonte: o watch é pausado e o histórico fica."""
    from .changedetection import ErroChangedetection, configurado

    uuids = [f.changedetection_uuid for f in instances
             if isinstance(f, Fonte) and f.changedetection_uuid]
    if not uuids:
        return
    try:
        conf = configurado()
        if conf is None:
            return
        for uuid in uuids:
            conf[0].apagar(uuid)
    except ErroChangedetection as exc:
        log.warning("remoção de watch falhou: %s", exc)
        messages.warning(request, _AVISO.format(erro=exc) +
                         " O watch que sobrar aparece como órfão.")
        return
    messages.info(request, f"changedetection: {len(uuids)} watch(es) removido(s).")
