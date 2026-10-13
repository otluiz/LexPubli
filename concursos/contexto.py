"""Variáveis de todas as páginas do portal."""
from django.conf import settings


def ecossistema(request):
    return {"LEXLEARN_URL": settings.LEXPUBLI_LEXLEARN_URL}
