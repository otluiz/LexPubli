"""Webhook de descoberta e páginas utilitárias (robots.txt)."""
from __future__ import annotations

import hashlib
import hmac
import json
import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.utils.html import strip_tags
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Descoberta, Fonte

_RE_URL = re.compile(r"https?://[^\s<>\"']+")
# Fonte de notícias (ADR-0007 §3a): só vira descoberta o que fala de concurso.
RE_CONCURSO = re.compile(
    r"concurso|edital|banca organizadora|comiss[aã]o (?:do|de|organizadora)|provimento de cargos"
    r"|cargos? efetivos?|nomea[cç][aãõ]", re.I)
_RE_WATCH_UUID = re.compile(r"^watch_uuid:\s*([0-9a-f-]{36})\s*$", re.M)
LIMITE_CORPO = 256 * 1024  # um diff de página não passa disso; acima é abuso


def _token_ok(request) -> bool:
    esperado = settings.LEXPUBLI_WEBHOOK_TOKEN
    if not esperado:
        return False
    recebido = request.headers.get("X-Lexpubli-Token") or request.GET.get("token", "")
    return hmac.compare_digest(recebido.encode(), esperado.encode())


@csrf_exempt  # chamada máquina-a-máquina; autenticada pelo token compartilhado
@require_POST
def webhook_changedetection(request):
    """Recebe a notificação do changedetection.io e cria uma Descoberta pendente.

    Aceita o JSON do Apprise (`json://`: title, message, type) e também um
    corpo com `watch_url` explícito. Reentrega do mesmo aviso não duplica
    (chave_dedup).
    """
    if not _token_ok(request):
        return JsonResponse({"erro": "não autorizado"}, status=403)
    if len(request.body) > LIMITE_CORPO:
        return JsonResponse({"erro": "corpo grande demais"}, status=413)
    try:
        corpo = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"erro": "JSON inválido"}, status=400)
    if not isinstance(corpo, dict):
        return JsonResponse({"erro": "esperado um objeto JSON"}, status=400)

    # O formato padrão do changedetection é 'htmlcolor': a curadoria quer o texto.
    titulo = strip_tags(str(corpo.get("title") or corpo.get("watch_title") or "")).strip()
    mensagem = strip_tags(str(corpo.get("message") or corpo.get("diff") or "")).strip()
    url = str(corpo.get("watch_url") or "").strip()
    if not url:
        achadas = _RE_URL.findall(mensagem) or _RE_URL.findall(titulo)
        url = achadas[0] if achadas else ""
    if not url.startswith(("http://", "https://")):
        return JsonResponse({"erro": "nenhuma URL de origem no aviso"}, status=400)

    # o corpo que a sincronização configura traz o uuid do watch (ADR-0007);
    # aviso de watch criado à mão não traz, e aí vale a URL
    achado = _RE_WATCH_UUID.search(mensagem)
    watch_uuid = achado.group(1) if achado else str(corpo.get("watch_uuid") or "")
    mensagem = _RE_WATCH_UUID.sub("", mensagem).strip()
    fonte_vigiada = Fonte.do_aviso(url, watch_uuid)
    if fonte_vigiada and fonte_vigiada.tipo == Fonte.Tipo.PISTA:
        # site de concursos: não vira Descoberta, só dispara a busca oficial
        from .pistas import registrar

        criadas = registrar(fonte_vigiada, mensagem)
        Fonte.objects.filter(pk=fonte_vigiada.pk).update(avisos_recebidos=F("avisos_recebidos") + 1)
        return JsonResponse({"pistas": criadas}, status=200)
    if fonte_vigiada:
        ignorar = (fonte_vigiada.conteudo == Fonte.Conteudo.NOTICIAS
                   and not RE_CONCURSO.search(  # o nome e a URL da própria fonte não contam
                       f"{titulo}\n{mensagem}".replace(fonte_vigiada.nome, "")
                       .replace(fonte_vigiada.url, "").replace(url, "")))
        Fonte.objects.filter(pk=fonte_vigiada.pk).update(
            avisos_recebidos=F("avisos_recebidos") + 1,
            avisos_ignorados=F("avisos_ignorados") + int(ignorar))
        if ignorar:
            return JsonResponse({"ignorada": True, "motivo": "notícia sem menção a concurso"},
                                status=200)

    chave = hashlib.sha256(f"{url}\n{mensagem}".encode()).hexdigest()
    try:
        with transaction.atomic():
            descoberta = Descoberta.objects.create(
                titulo=(titulo or f"Mudança em {url}")[:300],
                fonte="changedetection",
                fonte_url=url[:500],
                fonte_vigiada=fonte_vigiada,
                resumo=mensagem[:20000],
                payload=corpo,
                chave_dedup=chave,
            )
    except IntegrityError:
        existente = Descoberta.objects.get(chave_dedup=chave)
        return JsonResponse({"id": str(existente.id), "duplicada": True}, status=200)
    return JsonResponse({"id": str(descoberta.id), "duplicada": False}, status=201)


@require_GET
def robots_txt(request):
    linhas = [
        "User-agent: *",
        f"Disallow: /{settings.LEXPUBLI_ADMIN_PATH}",
        "Disallow: /webhooks/",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(linhas) + "\n", content_type="text/plain")
