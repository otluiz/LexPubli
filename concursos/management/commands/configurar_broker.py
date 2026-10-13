"""Configura o broker próprio do LexPubli (ADR-0005 §2a): vhost e usuários.

    python manage.py configurar_broker

Idempotente: pode rodar a cada deploy. Fala com a API de gestão do RabbitMQ
(LEXPUBLI_BROKER_API, ex.: http://rabbitmq:15672/api) com o usuário
administrador, e cria dois usuários de permissão mínima no vhost:

- lexpubli  (o worker): só declara e publica em lexpubli.events;
- lexcorpus (o consumidor do LexCorpus): lê lexpubli.events pela fila dele
  e publica as respostas em lexcorpus.events.

Nenhum dos dois é administrador nem enxerga o painel de gestão.
"""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from django.core.management.base import BaseCommand, CommandError

# Permissões AMQP por usuário: (configure, write, read), regex por nome de
# exchange/fila. A fila do LexCorpus é "lexcorpus.lexpubli.contests" (+ .dlq).
PERMISSOES = {
    "lexpubli": (r"^lexpubli\.events$", r"^lexpubli\.events$", r"^$"),
    "lexcorpus": (
        r"^(lexpubli\.events|lexcorpus\.events|lexcorpus\.lexpubli\..*)$",
        r"^(lexcorpus\.events|lexcorpus\.lexpubli\..*)$",
        r"^(lexpubli\.events|lexcorpus\.lexpubli\..*)$",
    ),
}
SENHAS = {"lexpubli": "BROKER_LEXPUBLI_PASSWORD", "lexcorpus": "BROKER_LEXCORPUS_PASSWORD"}


def chamadas(vhost: str, senhas: dict[str, str]) -> list[tuple[str, str, dict]]:
    """As chamadas PUT à API de gestão, na ordem. Separado para teste."""
    v = urllib.parse.quote(vhost, safe="")
    lista = [("PUT", f"/vhosts/{v}", {})]
    for usuario, (conf, escrita, leitura) in PERMISSOES.items():
        lista.append(("PUT", f"/users/{usuario}", {"password": senhas[usuario], "tags": ""}))
        lista.append(("PUT", f"/permissions/{v}/{usuario}",
                      {"configure": conf, "write": escrita, "read": leitura}))
    return lista


class Command(BaseCommand):
    help = "Cria o vhost e os usuários de permissão mínima no broker do LexPubli."

    def handle(self, *args, **opts):
        api = os.environ.get("LEXPUBLI_BROKER_API", "http://rabbitmq:15672/api").rstrip("/")
        admin = os.environ.get("RABBITMQ_DEFAULT_USER", "")
        admin_senha = os.environ.get("RABBITMQ_DEFAULT_PASS", "")
        vhost = os.environ.get("RABBITMQ_DEFAULT_VHOST", "lexpubli")
        senhas = {u: os.environ.get(var, "") for u, var in SENHAS.items()}
        faltando = [n for n, val in [("RABBITMQ_DEFAULT_USER", admin),
                                     ("RABBITMQ_DEFAULT_PASS", admin_senha)]
                    + [(SENHAS[u], s) for u, s in senhas.items()] if not val]
        if faltando:
            raise CommandError("defina no .env: " + ", ".join(faltando))

        cred = base64.b64encode(f"{admin}:{admin_senha}".encode()).decode()
        for metodo, caminho, corpo in chamadas(vhost, senhas):
            req = urllib.request.Request(
                api + caminho, method=metodo, data=json.dumps(corpo).encode(),
                headers={"Authorization": f"Basic {cred}", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=10):
                    pass
            except urllib.error.HTTPError as exc:
                raise CommandError(f"{metodo} {caminho}: HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                raise CommandError(f"API de gestão inacessível em {api}: {exc.reason}") from exc
        self.stdout.write(f"broker configurado: vhost {vhost}, usuários {', '.join(PERMISSOES)}")
