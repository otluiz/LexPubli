"""Admin: cadastros e a fila de curadoria como snippets do Wagtail."""
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from .models import Banca, Descoberta, Orgao, OutboxEvent


class DescobertaViewSet(SnippetViewSet):
    model = Descoberta
    icon = "search"
    menu_label = "Curadoria"
    list_display = ["titulo", "fonte", "status", "concurso", "detectada_em"]
    list_filter = ["status", "fonte"]
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
    items = (DescobertaViewSet, OrgaoViewSet, BancaViewSet, OutboxViewSet)


register_snippet(LexPubliGroup)
