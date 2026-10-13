"""Sinais do app: a publicação de um concurso já anunciado vira
contest.discovery.updated (ADR-0004, Fase 1)."""
from django.db import transaction
from django.dispatch import receiver
from wagtail.signals import page_published

from .eventos import registrar_atualizacao


@receiver(page_published)
def concurso_publicado(sender, instance, **kwargs):
    from .models import ConcursoPage

    if isinstance(instance.specific, ConcursoPage):
        with transaction.atomic():
            registrar_atualizacao(instance.specific)
