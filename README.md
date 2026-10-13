# LexPubli

**Radar de concursos públicos e porta de entrada do ecossistema Lex.**

O LexPubli busca na Internet informações sobre concursos públicos (previstos,
autorizados, editais, retificações, cronogramas e resultados), transforma
fontes dispersas em dados estruturados, prioriza o que importa e **publica**
tudo em páginas abertas ao público. Quem chega pelo LexPubli encontra o
caminho para estudar no LexLearn.

> **LexPubli descobre concursos e publica. LexCorpus adquire os documentos. LexLearn transforma documentos em conhecimento.**

> 🚧 **Status:** plataforma decidida (ADR-0001 *Aceito*: Wagtail) e spike
> concluído com um concurso real (Sefaz-AL 2026). Próxima etapa: o MVP.

## O ecossistema Lex

```text
          INTERNET (bancas, órgãos, diários oficiais)
                          │
                          ▼
     ┌──────────────── LEXPUBLI ────────────────┐
     │ Discovery ─▶ Curadoria ─▶ Portal público │──▶ PÚBLICO
     │ (fontes)     (humano)      (SEO, páginas)│    (páginas, feeds)
     └──────┬────────────▲────────────────┬─────┘
            │ contest.   │ document.      │ editais em /data/raw/editais/
            │ discovery.*│ acquisition.*  │ (só com autorização humana)
            ▼            │                │
       ┌─────────── LEXCORPUS ──────┐     │   broker próprio do LexPubli
       │ catálogo, busca de bancas  │     │   (ÚNICA automação: LexPubli ↔ LexCorpus)
       │ anteriores, spiders        │     │
       └────────────┬───────────────┘     │
                    │ concurso.disponivel │
                    │ (contrato v2.1)     │
                    ▼                     ▼
                LEXLEARN ── DNA das bancas (automático); geração de
                            questões por demanda, decidida pelo Administrador
```

| Projeto | Responsabilidade |
| --- | --- |
| **LexPubli** | Descobrir **concursos**, priorizar com curadoria humana, publicar |
| **LexCorpus** | Descobrir e adquirir **documentos** (provas, gabaritos, inclusive de certames anteriores) |
| **LexLearn** | Processar documentos e oferecer aprendizagem personalizada |

A automação é **só entre LexPubli e LexCorpus**, por eventos versionados no
**RabbitMQ próprio do LexPubli** ([ADR-0005](docs/architecture/decisions/ADR-0005-fronteira-com-o-lexlearn.md)).
Nenhum projeto lê o banco ou importa o código de outro. O LexPubli **avisa**,
e o LexCorpus **decide** o que coletar. O LexPubli toca o LexLearn em um
único ponto, a pasta `/data/raw/editais/`, sob autorização humana; o que o
LexLearn gera, e quando, é decisão do Administrador dele.

## Arquitetura

Plataforma: **[Wagtail](https://github.com/wagtail/wagtail)** (CMS em Python
sobre Django, BSD-3) com PostgreSQL. A escolha e as alternativas avaliadas
(WordPress, Ghost, Payload, Directus, FastAPI) estão no
[ADR-0001](docs/architecture/decisions/ADR-0001-plataforma-e-arquitetura.md).

Um projeto só, uma imagem Docker, dois processos:

| Processo | O que faz |
| --- | --- |
| `web` (gunicorn) | Portal público com renderização no servidor, JSON-LD schema.org, sitemap e robots, mais o **painel** do Wagtail (editorial e curadoria) |
| `worker` | `publicar_eventos`: lê o *outbox* e publica no exchange `lexpubli.events` |

Fluxo de uma descoberta:

```text
changedetection.io ──webhook──▶ Descoberta (pendente)
                                     │ curadoria no painel: aprova e liga a um concurso
                                     ▼
                     OutboxEvent (mesma transação)
                                     │ worker publicar_eventos
                                     ▼
                RabbitMQ: lexpubli.events / contest.discovery.created
```

- **Só o que foi aprovado vira evento.** O ecossistema recebe informação
  curada, não o ruído bruto das fontes.
- **Transactional outbox.** O evento nasce na mesma transação da aprovação.
  Se o broker estiver fora do ar, nada se perde: o evento espera e sai na
  próxima passada do worker.
- **Contratos validados antes de sair.** Um evento que viole o JSON Schema
  fica retido no outbox como `invalido` e nunca chega ao broker.

## Estrutura

```text
lexpubli/            settings (tudo por variável de ambiente), urls, wsgi
concursos/
  models.py          Orgao, Banca, ConcursoPage, Cargo, Descoberta, OutboxEvent
  eventos.py         envelope v1, validação, outbox, Publicador (pika)
  views.py           webhook do changedetection.io, robots.txt
  middleware.py      CSP e cabeçalhos de segurança do site público
  wagtail_hooks.py   painel: Curadoria, Órgãos, Bancas, Eventos (outbox)
  templatetags/      JSON-LD (JobPosting) e formatação em R$
  templates/         páginas públicas
  management/commands/
    carregar_exemplo.py   Sefaz-AL 2026 (dados reais da Cebraspe)
    publicar_eventos.py   worker do outbox
contracts/events/v1/ JSON Schemas: envelope + um schema por event_type
tests/               pytest (domínio, contratos, webhook, portal)
docs/                BACKLOG.org e ADRs (docs/architecture/decisions/)
```

## Rodando

### Desenvolvimento rápido (venv + SQLite, sem Docker)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py carregar_exemplo
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

- Portal: <http://localhost:8000/>. O concurso de exemplo fica em `/sefaz-al-2026/`.
- Painel: <http://localhost:8000/painel/> (fora de `/admin/` de propósito).

### Stack completa (Docker)

```bash
cp .env.example .env          # preencha LEXPUBLI_SECRET_KEY, POSTGRES_PASSWORD, ...

# portal, worker, banco e o broker próprio (o broker-init cria os usuários);
# --profile discovery acrescenta o changedetection.io
docker compose --profile discovery up -d --build

docker compose exec web python manage.py migrate
docker compose exec web python manage.py carregar_exemplo
docker compose exec web python manage.py createsuperuser
```

Portas (só em `127.0.0.1`): portal `8190`, changedetection.io `5000`,
gestão do RabbitMQ `15673` (usuário administrador do `.env`).

O LexCorpus entra na rede `lexpubli-broker` e usa o usuário `lexcorpus`
(`amqp://lexcorpus:<BROKER_LEXCORPUS_PASSWORD>@lexpubli-rabbitmq:5672/lexpubli`).
Permissões mínimas: ver `concursos/management/commands/configurar_broker.py`. Expor o portal na Internet é uma decisão
de produção, registrada no backlog.

### Ligando o changedetection.io

1. Na UI (<http://127.0.0.1:5000>), adicione a página a monitorar, por
   exemplo `https://www.cebraspe.org.br/concursos/SEFAZ_AL_26`.
2. Em *Notifications*, use a URL Apprise:
   `json://web:8000/webhooks/changedetection/?+X-Lexpubli-Token=<LEXPUBLI_WEBHOOK_TOKEN>`
3. Cada mudança detectada vira uma **Descoberta pendente** em *LexPubli → Curadoria*.

### Testes

```bash
.venv/bin/pytest
```

## Configuração

Tudo vem do ambiente. O [`.env.example`](.env.example) é o modelo comentado.
As principais variáveis:

| Variável | Para quê |
| --- | --- |
| `LEXPUBLI_SECRET_KEY` | Obrigatória com `LEXPUBLI_DEBUG=0` |
| `DATABASE_URL` | Montada pelo compose. Sem ela, usa SQLite local |
| `LEXPUBLI_BASE_URL` | URL pública: links nos eventos e no sitemap |
| `LEXPUBLI_ADMIN_PATH` | Caminho do painel (padrão `painel/`) |
| `LEXPUBLI_HTTPS` | `1` atrás de HTTPS: HSTS, cookies seguros, redirect |
| `RABBITMQ_DEFAULT_USER` / `_PASS` | Administrador do broker próprio (gestão e broker-init) |
| `BROKER_LEXPUBLI_PASSWORD` | Usuário `lexpubli` do worker; o compose monta a `LEXPUBLI_RABBITMQ_URL` |
| `BROKER_LEXCORPUS_PASSWORD` | Usuário `lexcorpus`, passado ao LexCorpus |
| `LEXPUBLI_WEBHOOK_TOKEN` | Token do webhook. Vazio = webhook desligado |

## Contratos e convenções

- Eventos em inglês, `lowercase.dot.case`; campos em `snake_case`.
- Envelope v1: `event_id` (UUIDv7), `event_type`, `event_version`
  (`MAJOR.MINOR`), `occurred_at` (ISO 8601 UTC, sufixo `Z`), `producer`,
  `correlation_id`, `data`. Schema em [`contracts/events/v1/`](contracts/events/v1/).
- Exchange `lexpubli.events` (topic); routing key = `event_type`;
  `message_id` = `event_id`, para idempotência no consumidor.
- Slugs de banca e órgão com o **mesmo algoritmo do LexCorpus**
  (`lexcorpus.util.slugify`), para casar sem tabela de tradução.
- Mudança incompatível de contrato = novo `MAJOR`, implantado com o
  consumidor primeiro.
- Este envelope vale para os contratos novos. O contrato LexCorpus → LexLearn
  (v2.1: `concurso.disponivel` / `concurso.atualizado`) continua como está.

| Evento | Status |
| --- | --- |
| `contest.discovery.created` | ✅ v1.0, emitido pelo LexPubli na aprovação da curadoria |
| `document.acquisition.completed` | ✅ v1.0 (schema), emitido pelo LexCorpus (ADR-0002) |
| `document.acquisition.awaiting_operator` | ✅ v1.0 (schema), emitido pelo LexCorpus |
| `document.acquisition.failed` | ✅ v1.0 (schema), emitido pelo LexCorpus |
| `contest.discovery.updated` | previsto |
| `contest.priority.changed` | previsto (Heat Engine) |

Detalhes, versionamento e o guia para o LexCorpus: [`contracts/README.md`](contracts/README.md).

## Roteiro

- **Spike (concluído em 12/10/2026):** Wagtail e arquitetura validados. Resultados no ADR-0001.
- **MVP (próximo):** modelos completos, primeiras fontes, deduplicação, Heat Score por
  regras com decisão humana preservada, API pública e feeds, consumo pelo
  LexCorpus.
- **Depois:** mais fontes, alertas e newsletter, aprendizado a partir das
  decisões da curadoria.

O estado detalhado de cada item está em [`docs/BACKLOG.org`](docs/BACKLOG.org).

## Projetos relacionados

- **LexCorpus**: coleta e armazenamento de provas, editais e gabaritos.
- **LexLearn**: transformação dos documentos em conhecimento e experiências
  de aprendizagem.

## Licença

A definir.
