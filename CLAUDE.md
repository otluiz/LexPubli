# CLAUDE.md

Este arquivo orienta o Claude Code (claude.ai/code) ao trabalhar com código neste repositório.

## O que é isto

LexPubli é o radar de concursos públicos e a porta de entrada da suíte Lex: descobre
concursos, passa pela curadoria humana e publica o portal público. É feito em Django +
Wagtail, com PostgreSQL e um RabbitMQ próprio. O LexStudy é um módulo deste projeto, não
uma aplicação separada (ADR-0011).

## Suíte Lex

O LexPubli é um dos três projetos da suíte Lex (com LexCorpus e LexLearn). O mapa
estrutural da suíte (fronteiras, contratos, brokers, storage compartilhado, máquinas)
está em `../ARQUITETURA-DA-SUITE.md`, fora deste repositório. **Leia esse arquivo antes de
qualquer mudança estrutural**: um canal novo entre projetos, um contrato, o broker, um
caminho em `/data`, ou onde algo roda. Se a mudança alterar o que o mapa descreve, ela
precisa de um ADR e de uma revisão do mapa, como manda a §9 dele.

Fronteiras que este projeto não cruza:

- A automação é só com o LexCorpus, pelo broker deste projeto (ADR-0002, ADR-0005).
- Com o LexLearn não há evento nem API, só link. O único ponto de contato é
  `/data/raw/editais/`, com autorização humana (ADR-0003, ADR-0005).
- Os schemas de `contracts/events/v1/` têm uma cópia em `LexCorpus/schema/lexpubli/v1/`.
  Uma mudança aqui tem de ir para lá também. Mudança incompatível vira `v2`.

## Onde está o resto

- `docs/BACKLOG.org`: o estado atual e o que falta.
- `docs/architecture/decisions/`: os ADRs do projeto.
- `README.md`: a arquitetura, a estrutura e como rodar.
