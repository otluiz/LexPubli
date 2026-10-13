"""Worker do outbox: publica os eventos pendentes no RabbitMQ.

    python manage.py publicar_eventos              # uma passada e sai
    python manage.py publicar_eventos --loop 5     # verifica a cada 5 s

Broker fora do ar não derruba o worker no modo --loop: o evento continua
pendente e a conexão é refeita com backoff (até 60 s).
"""
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from concursos.eventos import Publicador, publicar_pendentes


class Command(BaseCommand):
    help = "Publica no RabbitMQ os eventos pendentes do outbox."

    def add_arguments(self, parser):
        parser.add_argument("--loop", type=float, default=0, help="Intervalo em segundos (0 = uma passada).")
        parser.add_argument("--limite", type=int, default=100, help="Máximo de eventos por passada.")

    def handle(self, *args, loop, limite, **opts):
        url = settings.LEXPUBLI_RABBITMQ_URL
        if not url:
            raise CommandError("LEXPUBLI_RABBITMQ_URL vazia: sem broker, nada a publicar.")
        if not loop:
            pub = Publicador(url, settings.LEXPUBLI_EXCHANGE)
            try:
                n = publicar_pendentes(pub, limite)
            finally:
                pub.fechar()
            self.stdout.write(f"{n} evento(s) publicado(s)")
            return

        espera, pub = loop, None
        while True:
            try:
                if pub is None:
                    pub = Publicador(url, settings.LEXPUBLI_EXCHANGE)
                    self.stdout.write(f"conectado ao broker, exchange {settings.LEXPUBLI_EXCHANGE}")
                n = publicar_pendentes(pub, limite)
                if n:
                    self.stdout.write(f"{n} evento(s) publicado(s)")
                espera = loop
            except Exception as exc:
                self.stderr.write(f"broker indisponível ({type(exc).__name__}: {exc}); nova tentativa em {espera:.0f}s")
                if pub is not None:
                    try:
                        pub.fechar()
                    except Exception:
                        pass
                    pub = None
                time.sleep(espera)
                espera = min(espera * 2, 60)
                continue
            time.sleep(loop)
