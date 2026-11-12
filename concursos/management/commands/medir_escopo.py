"""Mede o que a ADR-0012 deixaria entrar, lendo o caderno do PNCP.

    python manage.py medir_escopo                    # tudo o que está no caderno
    python manage.py medir_escopo --desde 2026-09-01
    python manage.py medir_escopo --listar fiscal_controle

Não pede nada ao PNCP e não grava nada: só lê os arquivos que o
coletar_pncp guardou. Conta as publicações de concurso público por trilha e
por esfera, e mostra quantas entrariam hoje (federal, estadual, distrital)
e quantas a ADR-0012 acrescentaria (municipais de alguma trilha).
"""
from collections import Counter
from datetime import date

from django.core.management.base import BaseCommand

from concursos.pncp import ESFERAS, dias_do_caderno, ler_caderno
from concursos.trilhas import TRILHAS, trilhas


class Command(BaseCommand):
    help = "Conta, no caderno do PNCP, o que entraria no radar por trilha de carreira (ADR-0012)."

    def add_arguments(self, parser):
        parser.add_argument("--desde", type=date.fromisoformat, help="AAAA-MM-DD")
        parser.add_argument("--listar", choices=list(TRILHAS), help="lista as publicações da trilha")

    def handle(self, *args, desde=None, listar=None, **opts):
        dias = [d for d in dias_do_caderno() if not desde or d >= desde]
        if not dias:
            self.stdout.write(self.style.WARNING("Caderno vazio: rode coletar_pncp primeiro."))
            return
        total, por_esfera, por_trilha, novos = 0, Counter(), Counter(), Counter()
        listagem = []
        for dia in dias:
            for a in ler_caderno(dia):
                total += 1
                esfera = "municipal" if a.esfera not in ESFERAS else ESFERAS[a.esfera]
                por_esfera[esfera] += 1
                for t in trilhas(a.razao, a.unidade, a.objeto):
                    por_trilha[(t, esfera)] += 1
                    if esfera == "municipal":
                        novos[t] += 1
                    if t == listar:
                        listagem.append(a)

        self.stdout.write(f"Caderno: {len(dias)} dia(s), de {dias[0]:%d/%m/%Y} a {dias[-1]:%d/%m/%Y}; "
                          f"{total} publicação(ões) de concurso público.")
        self.stdout.write("\nPor esfera:")
        for esfera, n in por_esfera.most_common():
            self.stdout.write(f"  {esfera:<10} {n:>6}")
        self.stdout.write("\nPor trilha (esfera):")
        for t, nome in TRILHAS.items():
            partes = ", ".join(f"{e} {n}" for (tt, e), n in sorted(por_trilha.items()) if tt == t)
            self.stdout.write(f"  {nome:<36} {partes or '0'}")
        hoje = sum(n for e, n in por_esfera.items() if e != "municipal")
        acrescimo = novos["fiscal_controle"] + novos["juridica"]   # um concurso pode estar nas duas
        self.stdout.write(f"\nEntram hoje: {hoje}. A ADR-0012 acrescentaria até {acrescimo} municipal(is) "
                          f"(fiscal e controle {novos['fiscal_controle']}, jurídica {novos['juridica']}) "
                          f"em {len(dias)} dia(s) (~{acrescimo / len(dias) * 30:.0f} por mês para a curadoria).")
        self.stdout.write("A Rede Federal já entra quando contrata banca; a que faz o concurso com "
                          "comissão própria não passa pelo PNCP (ADR-0012 D2: fontes da onda E).")
        for a in listagem:
            local = f"{a.municipio}-{a.uf}" if a.municipio else a.uf
            self.stdout.write(f"\n  {a.data:%d/%m/%Y} · {a.razao} · {local}"
                              + (f" · {a.unidade}" if a.unidade else "")
                              + (f"\n    banca: {a.fornecedor}" if a.fornecedor else "")
                              + f"\n    {a.objeto[:160]}\n    {a.url}")
