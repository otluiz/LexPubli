# Contratos de eventos do ecossistema Lex (v1)

Os JSON Schemas desta pasta definem os eventos dos **contratos novos** entre
LexPubli e LexCorpus (ADR-0002). O **dono é o LexPubli**. Os outros projetos
carregam uma **cópia** e validam com ela.

O contrato v2.1 LexCorpus → LexLearn (`concurso.disponivel` /
`concurso.atualizado`) **não** está aqui e não usa este envelope. Ele mora no
LexCorpus (`docs/CONTRATO.md`).

## Eventos

| Evento | Produtor | Exchange | Quando |
|---|---|---|---|
| `contest.discovery.created` | `lexpubli` | `lexpubli.events` | A curadoria aprovou um concurso |
| `document.acquisition.completed` | `lexcorpus` | `lexcorpus.events` | Um concurso (atual ou anterior) foi coletado e entregue ao LexLearn |
| `document.acquisition.awaiting_operator` | `lexcorpus` | `lexcorpus.events` | A política de coleta não resolveu; o caso foi para o operador |
| `document.acquisition.failed` | `lexcorpus` | `lexcorpus.events` | Uma coleta automática falhou |

- **Routing key = `event_type`.** O LexLearn se liga ao `lexcorpus.events`
  com `concurso.#`, então não recebe os `document.*`.
- **As respostas exigem `correlation_id`**, igual ao `event_id` do
  `contest.discovery.created` que as originou. O `contest_id` vai em `data`.
- **As respostas não carregam caminho de storage.** O LexPubli só precisa
  saber *que* há provas (ADR-0002 §3).

## Arquivos

```text
events/v1/
  envelope.schema.json        envelope comum (event_id UUIDv7, occurred_at UTC 'Z', ...)
  common.schema.json          $defs compartilhados (slug, exam_board, relation...)
  <event_type>.schema.json    um por evento; o nome do arquivo é o event_type
  examples/<event_type>.json  exemplo canônico de cada evento
```

O exemplo do `contest.discovery.created` é a mensagem real que passou pelo
RabbitMQ no spike. Os de `document.acquisition.*` são ilustrativos: as
contagens de arquivos não vêm de uma coleta real.

## Versionamento

- `event_version` = `MAJOR.MINOR` do schema de `data`.
  - **MINOR:** mudança compatível, como um campo opcional novo. O
    consumidor antigo continua validando.
  - **MAJOR:** mudança incompatível. Vira uma pasta nova (`v2/`), e as duas
    versões convivem durante a transição.
- **Consumidor primeiro**, como no contrato v2.1:
  1. o dono publica o schema novo;
  2. o consumidor atualiza a cópia e confirma;
  3. só então o produtor passa a emitir a versão nova.

## Como o LexCorpus usa

1. Copiar `events/v1/` inteiro, com os exemplos, para o repositório dele.
   O lugar sugerido é `schema/lexpubli/v1/`.
2. Validar **toda** mensagem recebida (`contest.discovery.created`) e
   **toda** mensagem emitida (`document.acquisition.*`) contra a cópia.
   Mensagem inválida vai para a dead-letter e nunca é processada pela
   metade.
3. Montar o registro de `$ref` pelos `$id`: os schemas se referenciam por
   `$id` (`https://lex/lexpubli/events/v1/...`), não por caminho de arquivo.
   Referência em Python: `concursos/eventos.py`, função `_registro()`.
4. Os testes de `tests/test_contratos.py` mostram o que deve ser recusado:
   produtor errado, `correlation_id` ausente, campo de storage, enum
   desconhecido.
