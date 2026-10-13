"""Eventos do LexPubli: envelope v1, validação contra os contratos, outbox e publicação.

Os JSON Schemas em contracts/events/v1/ são a fonte da verdade. Nenhum
evento sai sem passar por eles — inválido fica no outbox como `invalido`,
com o erro registrado, e nunca chega ao broker.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone as dt_timezone
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .util import uuid7

log = logging.getLogger(__name__)

CONTRATOS_DIR = Path(settings.BASE_DIR) / "contracts" / "events" / "v1"
PRODUCER = "lexpubli"


# --- Contratos ---------------------------------------------------------------
@lru_cache(maxsize=1)
def _registro() -> tuple[Registry, dict[str, dict]]:
    """Carrega todos os schemas da pasta; indexa por $id e por event_type."""
    registro = Registry()
    por_tipo: dict[str, dict] = {}
    for arq in sorted(CONTRATOS_DIR.glob("*.schema.json")):
        schema = json.loads(arq.read_text(encoding="utf-8"))
        registro = registro.with_resource(schema["$id"], Resource.from_contents(schema))
        nome = arq.name.removesuffix(".schema.json")
        if "." in nome:  # event_type tem ponto; envelope e common são só peças
            por_tipo[nome] = schema
    return registro, por_tipo


def validar(envelope: dict) -> None:
    """Levanta jsonschema.ValidationError se o envelope violar o contrato do seu tipo."""
    registro, por_tipo = _registro()
    tipo = envelope.get("event_type")
    if tipo not in por_tipo:
        raise ValueError(f"event_type sem contrato em {CONTRATOS_DIR}: {tipo!r}")
    validador = Draft202012Validator(por_tipo[tipo], registry=registro, format_checker=FormatChecker())
    erro = next(iter(sorted(validador.iter_errors(envelope), key=lambda e: e.path)), None)
    if erro is not None:
        raise erro


def montar_envelope(event_type: str, data: dict, *, event_version: str = "1.0",
                    correlation_id: str | None = None) -> dict:
    agora = datetime.now(dt_timezone.utc)
    return {
        "event_id": str(uuid7()),
        "event_type": event_type,
        "event_version": event_version,
        "occurred_at": agora.strftime("%Y-%m-%dT%H:%M:%S.") + f"{agora.microsecond // 1000:03d}Z",
        "producer": PRODUCER,
        "correlation_id": correlation_id,
        "data": data,
    }


# --- Produção dos eventos ----------------------------------------------------
def _ref(obj) -> dict | None:
    return {"slug": obj.slug, "name": str(obj.nome)} if obj is not None else None


def _url_absoluta(pagina) -> str:
    """URL pública: LEXPUBLI_BASE_URL + caminho da página no site.

    Não usa o hostname do Site do Wagtail, que em dev/spike é 'localhost'.
    """
    partes = pagina.get_url_parts()
    caminho = partes[2] if partes else "/"
    return settings.WAGTAILADMIN_BASE_URL.rstrip("/") + caminho


# Campos do concurso que, mudando, geram contest.discovery.updated.
CAMPOS_ATUALIZAVEIS = ["title", "organ", "exam_board", "year", "status", "career", "exam_date",
                       "positions", "registration", "edital_url", "contest_slug"]
TIPOS_ANUNCIO = ("contest.discovery.created", "contest.discovery.updated")


def dados_concurso(c) -> dict:
    """O concurso como está agora ($defs/contest do contrato)."""
    registro = None
    if c.inscricoes_inicio or c.inscricoes_fim:
        registro = {
            "start": c.inscricoes_inicio.isoformat() if c.inscricoes_inicio else None,
            "end": c.inscricoes_fim.isoformat() if c.inscricoes_fim else None,
        }
    return {
        "contest_id": str(c.contest_id),
        "contest_slug": c.contest_slug,
        "title": c.title,
        "organ": {"slug": c.orgao.slug, "name": c.orgao.nome},
        "exam_board": _ref(c.banca),
        "year": c.ano,
        "status": c.status,
        "career": c.carreira or None,
        "exam_date": c.data_prova.isoformat() if c.data_prova else None,
        "positions": [
            {
                "slug": cargo.slug,
                "name": cargo.nome,
                "vacancies": cargo.vagas,
                "salary": float(cargo.salario) if cargo.salario is not None else None,
            }
            for cargo in c.cargos.all()
        ],
        "registration": registro,
        "edital_url": c.edital_url or None,
        "page_url": _url_absoluta(c),
    }


def dados_descoberta_criada(descoberta) -> dict:
    return {**dados_concurso(descoberta.concurso.specific),
            "discovery_id": str(descoberta.id), "source_url": descoberta.fonte_url}


def enfileirar(envelope: dict):
    """Grava o envelope no outbox. Chamar DENTRO da transação da mudança."""
    from .models import OutboxEvent

    status, erro = OutboxEvent.Status.PENDENTE, ""
    try:
        validar(envelope)
    except Exception as exc:  # contrato violado: registra, não publica
        status, erro = OutboxEvent.Status.INVALIDO, str(exc)[:4000]
        log.error("evento %s inválido, retido no outbox: %s", envelope.get("event_type"), erro)
    return OutboxEvent.objects.create(
        event_id=envelope["event_id"], event_type=envelope["event_type"],
        envelope=envelope, status=status, ultimo_erro=erro,
    )


def registrar_descoberta_aprovada(descoberta):
    return enfileirar(montar_envelope("contest.discovery.created", dados_descoberta_criada(descoberta),
                                      event_version="1.1"))


def registrar_atualizacao(concurso):
    """contest.discovery.updated, se o concurso já foi anunciado e algo do
    contrato mudou desde o último anúncio. Chamar na publicação da página.
    Devolve o OutboxEvent, ou None se não havia o que anunciar."""
    from .models import OutboxEvent

    ultimo = (OutboxEvent.objects
              .filter(event_type__in=TIPOS_ANUNCIO,
                      envelope__data__contest_id=str(concurso.contest_id))
              .order_by("-criado_em").first())
    if ultimo is None:
        return None  # nunca anunciado: quem anuncia é a aprovação de uma descoberta
    antes, agora = ultimo.envelope["data"], dados_concurso(concurso)
    mudou = [campo for campo in CAMPOS_ATUALIZAVEIS if antes.get(campo) != agora.get(campo)]
    if not mudou:
        return None
    dados = {**agora, "source_url": concurso.fonte_url, "changed": mudou}
    return enfileirar(montar_envelope("contest.discovery.updated", dados))


# --- Publicação --------------------------------------------------------------
class Publicador:
    """Publica no exchange topic `lexpubli.events`, com confirmação do broker.

    routing key = event_type; message_id = event_id (idempotência do lado
    consumidor); mensagens persistentes.
    """

    def __init__(self, url: str, exchange: str):
        import pika

        self._pika = pika
        self.exchange = exchange
        self.conexao = pika.BlockingConnection(pika.URLParameters(url))
        self.canal = self.conexao.channel()
        self.canal.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
        self.canal.confirm_delivery()

    def publicar(self, envelope: dict) -> None:
        self.canal.basic_publish(
            exchange=self.exchange,
            routing_key=envelope["event_type"],
            body=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
            properties=self._pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                message_id=envelope["event_id"],
                type=envelope["event_type"],
                app_id=PRODUCER,
            ),
            mandatory=False,
        )

    def fechar(self) -> None:
        if self.conexao.is_open:
            self.conexao.close()


def publicar_pendentes(publicador, limite: int = 100) -> int:
    """Publica os pendentes em ordem de criação. Devolve quantos saíram.

    Para no primeiro erro de broker (a ordem importa para o consumidor); o
    evento fica pendente e entra na próxima passada.
    """
    from .models import OutboxEvent

    publicados = 0
    for ev in OutboxEvent.objects.filter(status=OutboxEvent.Status.PENDENTE)[:limite]:
        try:
            validar(ev.envelope)
        except Exception as exc:
            ev.status, ev.ultimo_erro = OutboxEvent.Status.INVALIDO, str(exc)[:4000]
            ev.save(update_fields=["status", "ultimo_erro"])
            continue
        try:
            publicador.publicar(ev.envelope)
        except Exception as exc:
            ev.tentativas += 1
            ev.ultimo_erro = f"{type(exc).__name__}: {exc}"[:4000]
            ev.save(update_fields=["tentativas", "ultimo_erro"])
            log.warning("falha ao publicar %s (tentativa %d): %s", ev.event_id, ev.tentativas, exc)
            raise
        ev.status, ev.publicado_em, ev.ultimo_erro = OutboxEvent.Status.PUBLICADO, timezone.now(), ""
        ev.tentativas += 1
        ev.save(update_fields=["status", "publicado_em", "ultimo_erro", "tentativas"])
        publicados += 1
    return publicados
