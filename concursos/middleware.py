"""Cabeçalhos de segurança do site público.

A CSP vale só para as páginas públicas: o admin do Wagtail usa scripts e
estilos inline e tem a sua própria proteção (login + CSRF). O site público
não executa JavaScript algum — JSON-LD (`application/ld+json`) é dado, não
script executado, então `script-src 'none'` não o bloqueia.
"""
from django.conf import settings

CSP_PUBLICA = "; ".join([
    "default-src 'self'",
    "script-src 'none'",
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


class CabecalhosSegurancaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.prefixos_isentos = ("/" + settings.LEXPUBLI_ADMIN_PATH, "/documents/")

    def __call__(self, request):
        resposta = self.get_response(request)
        if not request.path.startswith(self.prefixos_isentos):
            resposta.headers.setdefault("Content-Security-Policy", CSP_PUBLICA)
        resposta.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        resposta.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return resposta
