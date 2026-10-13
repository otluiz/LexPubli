<!-- Arquivo:  docs/architecture/decisions/ADR-0001-plataforma-e-arquitetura.md
     Função:   registra a escolha da plataforma e da arquitetura do LexPubli
               (portal público de concursos e porta de entrada do ecossistema
               Lex). -->

# ADR-0001: Plataforma e arquitetura do LexPubli

- Status: **Proposto**. Aceitação condicionada ao spike descrito em "Validação".
- Data: 2026-10-12
- Autores: Prof. Othon Luiz, Claude (Anthropic)

## Contexto

O LexPubli é a **porta de entrada** do ecossistema Lex. Ele busca na
Internet informações sobre concursos (previstos, autorizados, editais,
retificações, cronogramas, resultados), prioriza essas descobertas (Heat
Engine, com decisão humana preservada) e as **publica em páginas próprias**
para o público, levando o visitante ao LexLearn.

O ecossistema já tem uma stack consolidada, e o LexPubli precisa conviver
com ela:

| Projeto | Stack |
|---|---|
| LexLearn | Python 3.11, FastAPI, PostgreSQL + pgvector, RabbitMQ (dono do broker), workers, React + Vite + Tailwind, Docker Compose |
| LexCorpus | Python, Scrapy, PyYAML, SQLite (StateStore), pika → RabbitMQ, Docker Compose |
| Convenções | contratos versionados em JSON Schema, Claim Check, ADRs em `docs/architecture/decisions/`, BACKLOG em org-mode |

O que a plataforma do LexPubli precisa entregar:

1. **Páginas públicas com bom SEO**: renderizadas no servidor, sitemap,
   schema.org e URLs estáveis. O tráfego orgânico é o funil do ecossistema.
2. **Modelo de dados estruturado**: Concurso, Órgão, Banca, Cargo,
   Cronograma e Fonte, com relações, e não apenas "posts com campos".
3. **Painel de curadoria**: aprovar descobertas, fundir duplicatas e
   fixar ou ocultar prioridades.
4. **Editorial humano**: notícias, guias, revisão e agendamento de
   publicação.
5. **Integração por eventos**: publicar e consumir no RabbitMQ existente,
   usando os mesmos padrões de contrato do LexCorpus.
6. **Superfície de ataque pequena**: é um site público, exposto a
   tráfego anônimo.
7. **Não partir do zero**: usar um projeto open source maduro, mantido e
   compatível com a nossa arquitetura.

Ficou fora deste ADR: a fronteira com o LexCorpus, que é o ADR-0002. Em
resumo, o LexPubli descobre **concursos** e o LexCorpus descobre e adquire
**documentos**. O buscador, o catálogo, o orquestrador e os spiders
continuam no LexCorpus.

## Opções consideradas

### A. WordPress (puro, ou como vitrine de um núcleo Python)

- Prós: o CMS mais difundido; SEO maduro (Rank Math, Yoast); editorial
  e feeds prontos; muita gente sabe operar.
- Contras:
  - **Segurança.** O relatório anual da Patchstack registrou 11.334 novas
    vulnerabilidades no ecossistema WordPress em 2025, 42% a mais que em
    2024. Cerca de 91% estão em plugins, e uma parcela relevante não tinha
    correção na data da divulgação. O núcleo do WordPress é razoavelmente
    seguro; o risco está nos plugins, que são exatamente o que daria o
    "ganho rápido". As atualizações constantes ajudam, mas viram uma
    obrigação operacional permanente.
  - PHP e MySQL ficam fora da stack. O domínio (deduplicação, Heat Engine,
    eventos) teria de ficar em PHP, ou exigiria um núcleo Python mais uma
    camada de sincronização com o WP, ou seja, dois runtimes e duas fontes
    de verdade a manter coerentes.
  - Custom post types com ACF não modelam bem relações (concurso ↔ cargos
    ↔ cronograma).

### B. Ghost (Node.js, MIT)

- Prós: excelente para publicação e newsletter (envio de e-mail e
  assinantes nativos); Admin e Content API; histórico de segurança melhor
  que o do WordPress.
- Contras: o modelo de dados é fixo (posts, páginas, tags), e concursos
  estruturados não cabem; em produção exige MySQL 8, segundo SGBD no
  ecossistema; Node fora da stack. Funcionaria só como vitrine, com o
  mesmo problema de sincronização da opção A.

### C. Payload CMS (TypeScript + Next.js, MIT, PostgreSQL)

- Prós: CMS headless moderno, modelagem por código, PostgreSQL, licença MIT
  e comunidade grande; a partir da v3 roda dentro do Next.js (front e admin
  num só app).
- Contras: TypeScript como segunda linguagem de back-end; o domínio
  (Heat Engine, consumidores RabbitMQ) ficaria em Node ou exigiria um
  núcleo Python à parte, de novo com dois runtimes.

### D. Directus + front estático (Astro)

- Prós: introspecta um PostgreSQL existente. O núcleo Python seria dono do
  schema (Alembic), e o Directus ofereceria painel e API REST/GraphQL sem
  código.
- Contras: **a licença não é open source.** É a Monospace Sustainable Core
  License (fonte disponível), gratuita abaixo de US$ 5 milhões de receita e
  50 funcionários. Isso é um risco para um produto que pretende crescer.
  Node fora da stack; mais uma peça para operar.

### E. FastAPI + SQLAdmin + templates (Jinja2/HTMX) ou Astro

- Prós: alinhamento total com o LexLearn (FastAPI, SQLAlchemy, pydantic).
- Contras: o SQLAdmin cobre o CRUD, mas não o editorial (rascunho,
  revisão, agendamento, rich text, imagens, histórico), nem SEO, sitemap,
  redirecionamentos e busca. Seria quase partir do zero na metade
  "portal" do produto.

### F. Wagtail (Python + Django, BSD-3-Clause, PostgreSQL)

- Prós:
  - **Python e PostgreSQL**, a mesma linguagem e o mesmo SGBD do
    ecossistema. Os modelos de domínio são modelos Django: Concurso, Órgão,
    Banca e Cargo como *snippets*/modelos, e a página do concurso como
    *Page*, com relações de verdade.
  - **Não partimos do zero.** É um CMS maduro (cerca de 20 mil estrelas,
    lançamentos de funcionalidades a cada três meses, BSD-3), com editorial
    completo (rascunho, moderação, agendamento, revisões, StreamField),
    imagens, busca nativa no PostgreSQL, sitemap, redirecionamentos e
    multi-site.
  - **SEO por renderização no servidor**, sem front separado. Se um dia
    quisermos um front desacoplado (Astro/Next.js), o Wagtail tem uma
    Content API headless e a troca não toca o domínio.
  - **Curadoria no próprio admin** (ViewSets, filtros, ações em lote):
    painel do Heat Engine sem front-end próprio.
  - **Superfície de ataque menor**: poucos pacotes, auditáveis e na nossa
    linguagem. Os avisos de segurança do Django e do Wagtail são
    publicados e corrigidos com processo definido.
  - Os workers (descoberta, Heat Engine, consumidor e publicador
    RabbitMQ) são comandos do próprio projeto, que importam os mesmos
    modelos. Usam pika, como o LexCorpus, e o mesmo padrão de contrato.
- Contras:
  - O framework é Django, não FastAPI como no LexLearn. É a mesma
    linguagem, pydantic continua disponível para os contratos e a
    integração entre projetos é por eventos, então a diferença fica
    contida no LexPubli. Mesmo assim é um segundo framework web no
    ecossistema.
  - Newsletter não é nativa. Fica fora do MVP; quando entrar, usar um
    serviço dedicado (ex.: listmonk, self-hosted e com PostgreSQL) ou a
    integração com Mailchimp.

### Peças de apoio (para qualquer opção)

- **changedetection.io** (Python, Apache-2.0, cerca de 32 mil estrelas):
  monitora páginas (portais de bancas, órgãos, diários) e avisa por
  webhook quando mudam. Candidato a gatilho do Discovery: avisa que a
  página do órgão X mudou, e o worker do LexPubli extrai e normaliza.
  Evita escrever o agendador e o diff de páginas. A avaliar no spike.
- **Scrapy**, para fontes que exigem navegação. Já é a ferramenta do
  LexCorpus, então o conhecimento é reaproveitado (o código não é
  compartilhado, conforme o ADR-0002).

## Decisão (proposta)

Adotar o **Wagtail** como plataforma do LexPubli, num único projeto
Django/Wagtail com PostgreSQL, que abriga:

```text
lexpubli/  (Wagtail + Django · PostgreSQL · Docker Compose)
 ├─ domínio      Concurso, Órgão, Banca, Cargo, Cronograma, Fonte (modelos)
 ├─ portal       páginas públicas (SSR), editorial, SEO, sitemap, feeds
 ├─ curadoria    admin Wagtail: fila de descobertas, deduplicação, prioridades
 ├─ workers      comandos: discovery, heat engine, consumer/publisher RabbitMQ
 └─ api          API pública (JSON) para terceiros e para o ecossistema
          │
          ├── eventos (lexpubli.events, envelope v1) ──▶ LexCorpus
          └── links/CTA ("estude para este concurso") ──▶ LexLearn
```

Regras que acompanham a decisão:

1. O PostgreSQL do LexPubli é **só do LexPubli**. Nenhum outro projeto o
   lê; a integração é por eventos e pela API.
2. O RabbitMQ é o broker existente do LexLearn (rede externa, como faz o
   LexCorpus). O LexPubli publica em `lexpubli.events`.
3. Contratos em JSON Schema versionados em `contracts/`, envelope
   `event_id`, `event_type`, `event_version`, `occurred_at`, `producer`,
   `correlation_id`, `data` (ver README).
4. Dependências de terceiros (pacotes Wagtail/Django) entram por decisão
   explícita. A lista é revisada a cada release, para não repetir o
   problema dos plugins do WordPress.

## Validação (spike antes de aceitar)

Spike de até duas semanas. O ADR passa a **Aceito** se todos os itens
abaixo funcionarem; se não, volta-se às opções (fallback preferido: E,
FastAPI + SQLAdmin + Astro).

- [ ] Modelar Concurso, Órgão, Banca e Cargo e publicar a página de um
      concurso real (ex.: Sefaz-AL 2026) com schema.org e sitemap.
- [ ] Curadoria no admin: listar descobertas pendentes, aprovar e fundir
      duplicatas.
- [ ] Worker publica `contest.discovery.created` no RabbitMQ do LexLearn,
      validado contra o JSON Schema.
- [ ] changedetection.io dispara o webhook para uma fonte real, e o
      worker registra a descoberta.
- [ ] `docker compose up` sobe tudo (portal, worker, postgres) e se liga
      à rede do LexLearn.
- [ ] Checklist de hardening: `manage.py check --deploy` limpo, admin fora
      da URL padrão, CSP e cabeçalhos de segurança.

## Consequências

**Positivas.** Uma linguagem e um SGBD em todo o ecossistema; o domínio
fica junto do portal, sem camada de sincronização; o editorial, o SEO e a
curadoria vêm prontos de um projeto maduro com licença permissiva; a
superfície de ataque é menor e auditável; o front pode ser desacoplado no
futuro sem tocar o domínio.

**Negativas / riscos.** (a) Django é um segundo framework web no
ecossistema; mitigado por tudo ser Python e pela integração exclusiva por
eventos. (b) Os temas e o front do portal são escritos por nós (templates
Django), já que não há um mercado de temas como o do WordPress. (c)
Newsletter e alertas precisam de um serviço externo quando saírem do MVP.

## Referências

- Patchstack, *State of WordPress Security* 2025: <https://patchstack.com/?p=25568>
- Wagtail (BSD-3-Clause): <https://github.com/wagtail/wagtail>
- Directus, licença MSCL: <https://github.com/directus/directus>
- Payload CMS: <https://docs.railway.com/guides/payload-cms>
- Ghost 6: <https://dasroot.net/posts/2026/02/building-newsletter-substack-alternatives-ghost-buttondown/>
- changedetection.io: <https://pagecrawl.io/blog/open-source-website-change-detection-tools>
- SQLAdmin: <https://pypi.org/project/sqladmin/0.16.0>
