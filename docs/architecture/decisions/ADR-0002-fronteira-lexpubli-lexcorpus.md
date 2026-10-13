<!-- Arquivo:  docs/architecture/decisions/ADR-0002-fronteira-lexpubli-lexcorpus.md
     Função:   registra a fronteira entre LexPubli e LexCorpus, a automação da
               coleta depois da aprovação humana e o uso de agregadores (PCI)
               como índice. Espelho no LexCorpus: ADR-0007. -->

# ADR-0002: Fronteira LexPubli × LexCorpus e automação pós-curadoria

- Status: **Aceito** em 2026-10-12 pelo dono do produto, junto com o espelho
  no LexCorpus (ADR-0007), que revisa uma regra do ADR-0006 de lá.
- Data: 2026-10-12
- Autores: Prof. Othon Luiz, Claude (Anthropic)
- Relacionados: ADR-0001 (LexPubli, plataforma); ADR-0001 e ADR-0006 do
  LexCorpus (agregador como índice; buscador, catálogo e orquestrador).

## Contexto

Com o ADR-0001 aceito, o LexPubli publica `contest.discovery.created` quando
a curadoria aprova uma descoberta. **Ninguém consome esse evento ainda.** O
LexCorpus funciona por lotes (watchlist, scheduler, comandos manuais) e não
tem consumidor de fila.

Três perguntas pedem resposta:

1. **Quem avisa o LexCorpus**, e até onde a coleta pode ser automática
   depois da aprovação humana?
2. **Onde passa a fronteira.** Os dois projetos "descobrem" coisas e é fácil
   duplicar: o LexCorpus já tem buscador, catálogo e orquestrador (ADR-0006).
3. **Agregadores como o PCI Concursos.** Podemos usá-los, e como, sem ferir
   direitos autorais?

Um fato de domínio orienta a resposta. Quando um concurso é descoberto,
**a prova dele ainda não existe**. O que serve ao estudante nesse momento
são as **provas anteriores** do mesmo órgão, cargo e banca, que é o que o
buscador do LexCorpus encontra. A prova do certame atual vem depois, quando
for aplicada, pelo ciclo do watchlist e do StateStore.

## Decisão

### 1. A fronteira: concurso × documento

| | LexPubli | LexCorpus |
|---|---|---|
| Descobre | **concursos**: notícia, edital, cronograma, vagas | **documentos**: provas e gabaritos, atuais e anteriores |
| Decide | se o concurso é real e relevante (curadoria) | o que coletar, de onde, com qual spider e quando |
| Publica | páginas públicas e eventos `contest.*` | arquivos no storage e eventos `concurso.*` e `document.acquisition.*` |
| Nunca faz | escolher spider, baixar PDF, rodar o buscador de bancas anteriores | publicar para o público, julgar a relevância de um concurso |

- **O LexPubli avisa e o LexCorpus decide.** A integração é só por eventos,
  sem código ou banco compartilhado.
- O `document.acquisition.requested` previsto no README do LexPubli **sai do
  fluxo normal**: o `contest.discovery.created` já é o aviso. Ele fica
  reservado para um pedido explícito da curadoria ("buscar provas anteriores
  deste concurso agora"), se um dia for necessário.
- O buscador, o catálogo, o orquestrador, o watchlist e os spiders **ficam no
  LexCorpus**. O LexPubli não os reimplementa.

### 2. Automação pós-curadoria, com duas portas de aprovação

```text
LexPubli ─ PORTA 1: curador aprova o concurso ─▶ contest.discovery.created
                                                        │
LexCorpus: consumidor (novo, processo de longa duração) ◀┘
  1. idempotência: event_id já visto? ignora
  2. catálogo: upsert em "vigentes" (chave contest_slug; guarda contest_id)
       exam_board = null ─▶ status aguardando_banca
  3. CONCURSO ATUAL ─▶ banca na lista de validadas e alvo resolvido?
       sim ─▶ watchlist automático (cron conforme a fase)
       não ─▶ fila do operador
  4. PROVAS ANTERIORES ─▶ buscador(órgão, cargo) ─▶ candidatas
       PORTA 2 (política): banca validada E confirmada no catálogo do órgão
                           E score ≥ limiar E dentro do limite de certames
       passa ─▶ orquestrador ─▶ coleta automática
       não passa ─▶ fila do operador (o "update-busca" de hoje)
  5. responde: document.acquisition.* ─▶ LexPubli
```

- **Porta 1 (humana, no LexPubli):** só concurso aprovado gera evento. Isso
  já está implementado.
- **Porta 2 (política, no LexCorpus):** o operador deixa de aprovar caso a
  caso e passa a **definir a política**, que resolve os casos de rotina:
  - **Bancas validadas:** a lista é configuração versionada no LexCorpus.
    Uma banca só entra depois de um crawl real conferido pelo operador.
    Hoje seriam Cebraspe, FGV, FCC e Cesgranrio.
  - **Limiares do buscador:** exigir `confirmado_por_catálogo_do_órgão` e
    um score mínimo.
  - **Limite de volume:** no máximo N certames anteriores por concurso
    (sugestão inicial: 3), para não varrer o histórico inteiro de um órgão
    de uma vez.
- **Continua manual, sempre:**
  - banca sem spider (gerar e validar o esqueleto);
  - candidatas abaixo do limiar;
  - ativar spider novo;
  - qualquer coisa fora da política.

> Isso **revisa o ADR-0006 do LexCorpus**, que dizia "a promoção é sempre
> decisão do operador". A nova regra é: **o operador decide a política, e a
> política decide os casos de rotina.** O espelho deste ADR no LexCorpus
> (ADR-0007) registra a mudança do lado de lá.

### 3. O contrato de resposta: `document.acquisition.*`

O LexCorpus responde no exchange que já tem, `lexcorpus.events`, usando o
**envelope v1 do LexPubli** (`event_id`, `event_type`, `event_version`,
`occurred_at`, `producer`, `correlation_id`, `data`).

- `correlation_id` = `event_id` do `contest.discovery.created` que originou
  a resposta.
- Separação dos consumidores: o LexLearn se liga ao `lexcorpus.events` com
  `concurso.#` (`lexlearn.lexcorpus.ingest`). Os eventos `document.*` não
  chegam a ele, e o contrato v2.1 LexCorpus → LexLearn **não muda**.

| Evento | Quando | `data` (resumo) |
|---|---|---|
| `document.acquisition.completed` | um concurso (atual ou anterior) foi coletado e publicado ao LexLearn | `contest_id`, `relation` (`current`/`previous`), `exam_board`, `lexcorpus_contest` (slug da pasta), `year`, `files` (contagem por papel) |
| `document.acquisition.awaiting_operator` | a política não resolveu: precisa de humano | `contest_id`, `relation`, `reason` (`no_spider`, `below_threshold`, `unresolved_target`, `volume_limit`), candidatas resumidas |
| `document.acquisition.failed` | tentativa automática falhou | `contest_id`, `relation`, `reason` (`fetch_error`, `blocked`, `invalid_source`), `retryable` |

- **Sem caminhos de storage na resposta.** O LexPubli não lê o storage. Ele
  só precisa saber *que* existem provas, para mostrar "provas anteriores
  disponíveis" e o link para estudar no LexLearn. Mínimo privilégio.
- Os schemas ficam em `contracts/events/v1/` no LexPubli, que é o dono do
  envelope. O LexCorpus carrega uma cópia e valida com ela, seguindo a
  regra "consumidor primeiro" do contrato v2.1.

### 4. Agregadores (PCI) como índice; fonte oficial como verdade

É a regra do ADR-0001 do LexCorpus, agora estendida ao LexPubli.

- O LexPubli **pode** usar agregadores para **descobrir**. O PCI Concursos
  permite as listagens e as notícias no robots.txt e publica um sitemap de
  notícias (`smap_noticias.xml`, ~1.000 URLs com `lastmod`, conferido em
  12/10/2026).
- **Nada é publicado com base só no agregador.** Para uma descoberta ser
  aprovada, o concurso precisa ter `fonte_url` em **fonte oficial** (banca,
  órgão ou diário oficial). O link do agregador fica só como origem da
  descoberta, para auditoria.
- **Não copiar o texto do agregador.** O LexPubli publica fatos conferidos
  na fonte oficial, com o próprio texto.
- O LexCorpus **continua** baixando documentos só das fontes oficiais. Os
  PDFs do PCI seguem fora de alcance: `Disallow: /*.pdf` e Turnstile.
- **Boas maneiras de coleta, nos dois projetos:**
  - respeitar o robots.txt;
  - não contornar captcha nem Turnstile;
  - limitar a frequência das requisições;
  - User-Agent identificável.

  A exceção da FCC no LexCorpus (`ROBOTSTXT_OBEY=False`) deve ser revista
  à luz desta regra.

**Direitos autorais.** Estes são critérios de engenharia, não parecer
jurídico.

| Conteúdo | Situação | Uso |
|---|---|---|
| Fatos (órgão, banca, vagas, salário, datas) | Fatos não são protegidos | Livre, conferido na fonte oficial e com link |
| Editais | Atos oficiais (Lei 9.610/98, art. 8º, IV) | Livre |
| Texto e organização de agregadores | Criação do agregador, protegida | Só como índice; não copiar |
| Provas e questões | Zona cinzenta: não são claramente "atos oficiais", e as bancas costumam reivindicar direitos | Coletar da fonte oficial, como já se faz. **Republicar questões na íntegra para usuários (LexLearn) exige parecer jurídico antes da monetização** |

Conferir que uma informação é verdadeira **não** altera a titularidade do
texto. O que importa é o que se copia e o que se republica.

## Alternativas consideradas

- **O LexPubli pede a aquisição** (`document.acquisition.requested` com
  spider e parâmetros): coloca no LexPubli um conhecimento que é do LexCorpus
  (spiders, slugs das bancas). Rejeitada; foi a proposta da primeira análise.
- **Automação total sem a porta 2:** o buscador tem falsos positivos
  (banca citada na página de busca ≠ banca que examinou o órgão), e spider
  não validado baixa lixo para o acervo do LexLearn. Rejeitada.
- **Continuar manual no LexCorpus:** o evento já existe; ignorá-lo mantém o
  gargalo humano em casos de rotina. Rejeitada.
- **Mover o buscador para o LexPubli:** ele existe para encontrar
  *documentos* de certames anteriores, o que é trabalho do LexCorpus.
  Rejeitada.

## Consequências

**Positivas.** Concurso aprovado no LexPubli vira coleta de provas
anteriores sem trabalho manual nos casos de rotina. O operador do LexCorpus
cuida só das exceções. Cada projeto continua dono do próprio conhecimento.
O LexPubli consegue mostrar ao público que já há provas para estudar.

**Negativas / riscos.**
- (a) O LexCorpus passa a ter um **processo de longa duração** (o
  consumidor), além do scheduler em lote. É mais um serviço no compose dele.
- (b) Os limiares da porta 2 precisam de calibração. No começo, é melhor
  pecar por mandar demais à fila do operador.
- (c) Dois exchanges e um envelope compartilhado exigem disciplina de
  versionamento, com a regra "consumidor primeiro".
- (d) A questão autoral das provas fica em aberto até haver parecer jurídico.

## Implementação

**LexPubli**
- [ ] Schemas `document.acquisition.{completed,awaiting_operator,failed}`
      em `contracts/events/v1/`
- [ ] Consumidor das respostas: registra o estado da aquisição por
      concurso; a página mostra "provas anteriores disponíveis"
- [ ] Regra de aprovação: `fonte_url` oficial obrigatória (lista de
      domínios de agregadores recusados como fonte)
- [ ] Discovery: sitemap de notícias do PCI como índice → descoberta
      pendente, com checagem da fonte oficial pela curadoria

**LexCorpus** (ADR-0007 de lá)
- [ ] `consumidor.py`: fila `lexcorpus.lexpubli.contests` ligada a
      `lexpubli.events` com `contest.discovery.*`, idempotência pelo
      `event_id` (no StateStore) e dead-letter
- [ ] Catálogo: upsert por `contest_slug`, guardando o `contest_id`
- [ ] Política da porta 2 em configuração versionada (bancas validadas,
      limiares, limite de volume)
- [ ] Watchlist automático em arquivo separado do manual (o manual
      continua versionado e soberano)
- [ ] Emitir `document.acquisition.*` no envelope v1, validado contra a
      cópia dos schemas
- [ ] Revisar o `ROBOTSTXT_OBEY=False` da FCC

**Ecossistema**
- [ ] Parecer jurídico sobre a republicação de questões (LexLearn)
