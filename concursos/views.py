"""Webhook de descoberta e páginas utilitárias (robots.txt)."""
from __future__ import annotations

import hashlib
import hmac
import json
import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Descoberta

_RE_URL = re.compile(r"https?://[^\s<>\"']+")
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

    titulo = str(corpo.get("title") or corpo.get("watch_title") or "").strip()
    mensagem = str(corpo.get("message") or corpo.get("diff") or "").strip()
    url = str(corpo.get("watch_url") or "").strip()
    if not url:
        achadas = _RE_URL.findall(mensagem) or _RE_URL.findall(titulo)
        url = achadas[0] if achadas else ""
    if not url.startswith(("http://", "https://")):
        return JsonResponse({"erro": "nenhuma URL de origem no aviso"}, status=400)

    chave = hashlib.sha256(f"{url}\n{mensagem}".encode()).hexdigest()
    try:
        with transaction.atomic():
            descoberta = Descoberta.objects.create(
                titulo=(titulo or f"Mudança em {url}")[:300],
                fonte="changedetection",
                fonte_url=url[:500],
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
