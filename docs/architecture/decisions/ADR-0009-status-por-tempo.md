<!-- Arquivo:  docs/architecture/decisions/ADR-0009-status-por-tempo.md
     Função:   registra a decisão sobre as transições automáticas de status
               do concurso governadas por data (inscrições encerradas, prova
               realizada) e, sobretudo, se essas transições emitem
               contest.discovery.updated ao LexCorpus. -->

# ADR-0009: Transições de status por tempo e emissão de eventos

- Status: **Proposto** em 2026-11-02 por Prof. Othon Luiz. Aguarda decisão
  do dono do produto sobre a emissão de eventos (§ Decisão, opções) e
  alinhamento com o LexCorpus.
- Data: 2026-11-02
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0004 (concurso-alvo; `status` em CAMPOS_ATUALIZAVEIS e
  `contest.discovery.updated`), ADR-0002 e ADR-0005 (fronteiras),
  ADR-0007/0008 (ciclo e sinais). Plano de implementação:
  docs/planos/automacao-status-por-data.md.

## Contexto

Observado em 02/11/2026: um concurso (Sefaz-AL 2026) aparecia em "Inscrições
abertas" na home com a data de inscrição (`inscricoes_fim = 21/10/2026`) já
vencida. A home agrupa concursos pelo campo `status`; o concurso continuava
`edital_aberto` porque **nada rebaixa o status quando a data vence**. Não há
automação nem signal de tempo. O frontend reflete fielmente o banco — o
problema é de domínio.

Duas transições do ciclo (ADR-0004) têm uma data que as comprova
objetivamente:

| De                      | Para                    | Gatilho                 |
|-------------------------|-------------------------|-------------------------|
| `edital_aberto`         | `inscricoes_encerradas` | `inscricoes_fim < hoje` |
| `inscricoes_encerradas` | `prova_realizada`       | `data_prova < hoje`     |

As demais (`prova_realizada → resultado → encerrado`) dependem de fato
externo que nenhuma data prova; ficam com curadoria/sinal.

O ponto de arquitetura: `status` está em `CAMPOS_ATUALIZAVEIS` (eventos.py) e
`contest.discovery.updated` é emitido no `page_published` (signals.py). Hoje
esse evento sai quando a **curadoria publica à mão** (ADR-0004, Fase 1). Se
uma automação por cron passar a mover o status e publicar, ela vira um
**emissor automático de eventos entre projetos** — comportamento novo, que o
LexCorpus receberá sem intervenção humana.

## Decisão (a tomar)

**D1 — As transições por tempo existem e são automatizadas.** Um comando
idempotente e conservador (`atualizar_status_por_data`, ver plano) avança
apenas as duas transições acima, só com data preenchida e vencida, nunca
retrocede, com `--simular` e log. Agendado 1x/dia no gpu01.
*(Esta parte é consensual; o plano detalha o como.)*

**D2 — A transição automática emite `contest.discovery.updated`?**
PENDENTE. Opções:

- **(a) Emitir** — a automação publica via revisão; o evento sai; o LexCorpus
  sabe que as inscrições encerraram / a prova foi realizada. Consistente com o
  Wagtail. Exige: registrar aqui que o cron também emite `.updated`, e alinhar
  com o LexCorpus (ele passa a receber updates não-humanos). A favor: o
  ecossistema deve reagir ao ciclo do concurso; encerramento de inscrições
  pode afetar a priorização de coleta.

- **(b) Não emitir** — a automação altera o status sem publicar evento
  (transição interna ao LexPubli). Exige resolver a divergência entre a
  página publicada e a última revisão do Wagtail de forma explícita. A favor:
  transição por mero decurso de tempo não é "novidade de conteúdo" que
  justifique notificar outro projeto.

Recomendação para discussão: **(a)**, por alinhamento ao espírito do ADR-0004
(o ecossistema reage ao ciclo), desde que registrada e alinhada. Decisão do
dono do produto.

## Consequências

- Com (a): o contrato de eventos ganha um produtor não-humano; o LexCorpus
  deve estar ciente de que `.updated` pode chegar de um cron. Nenhuma mudança
  de schema (o `status` já é campo do contrato).
- Com (b): o LexCorpus não é notificado da virada de fase por tempo; o
  LexPubli precisa de cuidado para não deixar revisão e página divergentes.
- Em ambos: a home passa a refletir a fase real sem depender de curadoria
  manual a cada data vencida. O dado atual do Sefaz-AL 2026 é corrigido à mão
  no painel, independente desta decisão.

## Salvaguarda de exibição (opcional, não-bloqueante)

Enquanto a automação não roda, a view da home pode deixar de listar em
"Inscrições abertas" um concurso com `inscricoes_fim` vencida, mesmo
`edital_aberto` — filtro de exibição, sem tocar status nem fronteira.
