"""Sincronização Fonte -> changedetection.io (ADR-0007 §1).

O cadastro Fonte é a fonte da verdade; o changedetection só executa. Para cada
fonte do tipo `pagina`:

- ativa, sem watch (ou com o watch apagado na UI) -> cria;
- ativa, com watch diferente do cadastro -> atualiza (URL, título, intervalo,
  notificação, despausa);
- inativa, com watch -> PAUSA (o histórico da página fica lá).

Os watches criados aqui levam a etiqueta `lexpubli`. Um watch com a etiqueta
que nenhuma Fonte reconhece é ÓRFÃO: só é apagado com `remover_orfaos`. Os
watches criados à mão na UI (sem a etiqueta) nunca são tocados.

Cliente só com a biblioteca padrão (urllib): a API é JSON simples.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import quote, urlencode

ETIQUETA = "lexpubli"
CORPO_NOTIFICACAO = "{{watch_url}}\nwatch_uuid: {{watch_uuid}}\n---\n{{diff}}\n---\n"
TIMEOUT_S = 20


class ErroChangedetection(RuntimeError):
    pass


class Cliente:
    """API v1 do changedetection.io (header x-api-key)."""

    def __init__(self, base: str, chave: str, *, abrir=urllib.request.urlopen):
        if not chave:
            raise ErroChangedetection("LEXPUBLI_CHANGEDETECTION_API_KEY vazia "
                                      "(UI do changedetection: Settings > API)")
        self.base, self.chave, self.abrir = base.rstrip("/") + "/api/v1", chave, abrir

    def _pedir(self, metodo: str, caminho: str, corpo=None, consulta: dict | None = None):
        url = self.base + caminho + (f"?{urlencode(consulta)}" if consulta else "")
        dados = json.dumps(corpo).encode() if corpo is not None else None
        req = urllib.request.Request(url, data=dados, method=metodo, headers={
            "x-api-key": self.chave, "Content-Type": "application/json"})
        try:
            with self.abrir(req, timeout=TIMEOUT_S) as resp:
                texto = resp.read().decode() or "null"
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            detalhe = exc.read().decode(errors="replace")[:300]
            raise ErroChangedetection(f"{metodo} {caminho}: HTTP {exc.code} {detalhe}") from exc
        except urllib.error.URLError as exc:
            raise ErroChangedetection(f"changedetection fora do ar ({self.base}): {exc.reason}") from exc
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            return texto                      # o PUT responde "OK" em texto

    def etiqueta(self, titulo: str, *, criar: bool = True) -> str | None:
        """UUID da etiqueta, criada se ainda não existir (e `criar`)."""
        for uuid, tag in (self._pedir("GET", "/tags") or {}).items():
            if (tag.get("title") or "").lower() == titulo.lower():
                return uuid
        if not criar:
            return None
        criada = self._pedir("POST", "/tag", {"title": titulo})
        return criada["uuid"]

    def watches(self, etiqueta: str) -> dict[str, dict]:
        return self._pedir("GET", "/watch", consulta={"tag": etiqueta}) or {}

    def watch(self, uuid: str) -> dict | None:
        return self._pedir("GET", f"/watch/{quote(uuid)}")

    def criar(self, campos: dict) -> str:
        return self._pedir("POST", "/watch", campos)["uuid"]

    def atualizar(self, uuid: str, campos: dict) -> None:
        self._pedir("PUT", f"/watch/{quote(uuid)}", campos)

    def apagar(self, uuid: str) -> None:
        self._pedir("DELETE", f"/watch/{quote(uuid)}")


def notificacao(webhook_interno: str, token: str) -> str:
    """URL Apprise do webhook (json://... com o header do token)."""
    if not token:
        raise ErroChangedetection("LEXPUBLI_WEBHOOK_TOKEN vazio: o webhook está desligado, "
                                  "e watch sem notificação não gera descoberta")
    return f"{webhook_interno}?+X-Lexpubli-Token={token}"


def campos_do_watch(fonte, etiqueta_uuid: str, url_notificacao: str) -> dict:
    return {
        "url": fonte.url,
        "title": f"[LexPubli] {fonte.nome}",
        "tags": [etiqueta_uuid],
        "time_between_check": {"hours": int(fonte.intervalo_horas)},
        "time_between_check_use_default": False,
        "notification_urls": [url_notificacao],
        "notification_format": "text",       # a curadoria quer texto, não HTML colorido
        # o webhook liga a Descoberta à Fonte pelo uuid (a URL fica de reserva)
        "notification_title": f"[LexPubli] {fonte.nome}",
        "notification_body": CORPO_NOTIFICACAO,
        "fetch_backend": "html_requests",    # conferida sem JS (ADR-0007 §3)
        "paused": not fonte.ativa,
    }


def _difere(remoto: dict, desejado: dict) -> list[str]:
    diferentes = []
    for campo, valor in desejado.items():
        atual = remoto.get(campo)
        if campo == "time_between_check":
            atual = {"hours": (atual or {}).get("hours")} if isinstance(atual, dict) else atual
        if campo == "tags":
            atual = [t for t in (atual or []) if t in valor] if isinstance(atual, list) else atual
        if atual != valor:
            diferentes.append(campo)
    return diferentes


@dataclass
class Relatorio:
    criadas: list[str] = field(default_factory=list)
    atualizadas: list[str] = field(default_factory=list)
    pausadas: list[str] = field(default_factory=list)
    iguais: list[str] = field(default_factory=list)
    orfaos: list[str] = field(default_factory=list)
    removidos: list[str] = field(default_factory=list)

    def resumo(self) -> str:
        return (f"{len(self.criadas)} criada(s), {len(self.atualizadas)} atualizada(s), "
                f"{len(self.pausadas)} pausada(s), {len(self.iguais)} sem mudança, "
                f"{len(self.orfaos)} órfão(s), {len(self.removidos)} removido(s)")


def _aplicar(fonte, cliente: Cliente, desejado: dict, remotos: dict, rel: Relatorio,
             simular: bool) -> str | None:
    """Leva UMA fonte ao estado do cadastro. Devolve o uuid do watch dela
    (None se não há watch)."""
    remoto = cliente.watch(fonte.changedetection_uuid) if fonte.changedetection_uuid else None
    if remoto is None:
        # sem watch (ou apagado na UI): adota um com a mesma URL e a etiqueta,
        # se houver (ex.: o uuid se perdeu numa restauração do banco)
        achado = next((u for u, w in remotos.items() if w.get("url") == fonte.url), None)
        if achado:
            remoto = dict(cliente.watch(achado) or {}, uuid=achado)
            if not simular:
                fonte.changedetection_uuid = achado
                fonte.save(update_fields=["changedetection_uuid"])
    if remoto is None:
        if not fonte.ativa:
            return None                        # inativa e sem watch: nada a fazer
        rel.criadas.append(fonte.nome)
        if not simular:
            fonte.changedetection_uuid = cliente.criar(desejado)
            fonte.save(update_fields=["changedetection_uuid"])
        return fonte.changedetection_uuid or None
    uuid = fonte.changedetection_uuid or remoto.get("uuid")
    mudou = _difere(remoto, desejado)
    if not mudou:
        rel.iguais.append(fonte.nome)
        return uuid
    (rel.pausadas if not fonte.ativa and not remoto.get("paused") else rel.atualizadas
     ).append(f"{fonte.nome} ({', '.join(mudou)})")
    if not simular:
        cliente.atualizar(uuid, desejado)
    return uuid


def sincronizar(fontes, cliente: Cliente, url_notificacao: str, *,
                simular: bool = False, remover_orfaos: bool = False) -> Relatorio:
    """Aplica o cadastro no changedetection. `fontes` = Fonte do tipo pagina.
    Em `simular`, só lê e relata; nada é escrito, nem lá nem aqui."""
    rel = Relatorio()
    etiqueta = cliente.etiqueta(ETIQUETA, criar=not simular) or "(a criar)"
    remotos = cliente.watches(ETIQUETA)
    conhecidos = set()
    for fonte in fontes:
        conhecidos.add(_aplicar(fonte, cliente, campos_do_watch(fonte, etiqueta, url_notificacao),
                                remotos, rel, simular))
    for uuid, w in remotos.items():
        if uuid not in conhecidos:
            rel.orfaos.append(f"{w.get('title') or w.get('url')} [{uuid}]")
            if remover_orfaos and not simular:
                cliente.apagar(uuid)
                rel.removidos.append(uuid)
    return rel


def sincronizar_uma(fonte, cliente: Cliente, url_notificacao: str) -> Relatorio:
    """A fonte que o curador acabou de gravar no painel. Não olha órfãos:
    isso é da sincronização completa."""
    rel = Relatorio()
    if fonte.tipo != fonte.Tipo.PAGINA:
        return rel
    etiqueta = cliente.etiqueta(ETIQUETA)
    _aplicar(fonte, cliente, campos_do_watch(fonte, etiqueta, url_notificacao),
             cliente.watches(ETIQUETA), rel, simular=False)
    return rel


def configurado() -> tuple[Cliente, str] | None:
    """Cliente e URL do webhook, ou None se a integração não está configurada
    (sem chave da API ou sem token do webhook): aí o painel não sincroniza."""
    from django.conf import settings

    if not (settings.LEXPUBLI_CHANGEDETECTION_API_KEY and settings.LEXPUBLI_WEBHOOK_TOKEN):
        return None
    return (Cliente(settings.LEXPUBLI_CHANGEDETECTION_URL, settings.LEXPUBLI_CHANGEDETECTION_API_KEY),
            notificacao(settings.LEXPUBLI_WEBHOOK_INTERNO, settings.LEXPUBLI_WEBHOOK_TOKEN))
