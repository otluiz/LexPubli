<!-- Arquivo:  docs/architecture/decisions/ADR-0005-fronteira-com-o-lexlearn.md
     Função:   registra que a automação do ecossistema Lex existe só entre
               LexPubli e LexCorpus; o LexPubli toca o LexLearn apenas pela
               pasta /data/raw/editais/, e as decisões do LexLearn são do
               Administrador dele. Revisa o ADR-0004 (§1, §2, §4–6, fases)
               e o ADR-0003 (§4). -->

# ADR-0005: Fronteira com o LexLearn — a automação é só LexPubli ↔ LexCorpus

- Status: **Aceito** em 2026-10-13 pelo dono do produto.
- Data: 2026-10-13
- Autor: Prof. Othon Luiz
- Revisa: ADR-0004 (§1, §2, §4, §5, §6, mudanças de contrato e fases 2–4) e
  ADR-0003 (§4). Os dois receberam nota de REVISÃO.
- Relacionados: ADR-0002 (fronteira LexPubli × LexCorpus); LexCorpus
  ADR-0008 (relação `related`) e `docs/CONTRATO.md` (v2.1); LexLearn
  ADR-0007 (fronteira de ingestão, §6 "navegar sim, executar não"),
  ADR-0011 (uma fila por ambiente) e ADR-0012 (isolamento do LexLearn).

## Contexto

O ADR-0004 fez do concurso-alvo o eixo dos três projetos. No lado do
LexLearn, ele previa:

- o LexLearn assinando `contest.discovery.*` e `document.acquisition.completed`;
- a prioridade do LexPubli (Heat Engine) dizendo **onde gastar GPU**;
- o LexLearn devolvendo `study.target.ready` para o portal.

Ou seja, um concurso aprovado no portal público acabaria disparando, por
eventos, trabalho de geração no LexLearn.

O dono do produto definiu outra fronteira. As razões:

- **O DNA das bancas precisa do fluxo automático.** Ele se alimenta das
  questões que o LexCorpus coleta a partir dos concursos que o LexPubli
  descobre. Esse caminho já existe e funciona: é o contrato v2.1 do
  LexCorpus (`/data/raw/exams/`).
- **A geração de questões é por demanda, de forma controlada.** Ela custa
  GPU e, com usuários pagantes, vira serviço cobrado.
- **O LexLearn é onde a separação entre clientes fica explícita.** Os
  serviços pagos terão interface própria e usarão a geração do LexLearn,
  mas nunca terão acesso ao scrapy do LexCorpus nem aos serviços do
  LexPubli. O que cada serviço pode usar é sempre decisão do Administrador.

## Decisão

### 1. Automação só entre LexPubli e LexCorpus

Eventos, filas e respostas automáticas existem **somente** entre o LexPubli
e o LexCorpus (ADR-0002, ADR-0004 §3, LexCorpus ADR-0007/0008). Nenhum
contrato de evento do LexPubli tem o LexLearn como produtor ou consumidor.

### 2. O LexPubli toca o LexLearn em um único ponto: a pasta de editais

- O LexPubli grava editais em `/data/raw/editais/`, **sob autorização
  humana** e de fonte oficial, como define o ADR-0003.
- O LexPubli **não** publica eventos para o LexLearn, **não** assina nada
  dele e **não** chama a API dele.
- O que o LexLearn faz com um edital, e quando, é decisão do
  **Administrador do LexLearn**. Inclusive disparar a ingestão.
- O `contest_id` no sidecar `edital-1.0` é dado, não ordem: o LexLearn
  pode usá-lo, se e quando o Administrador decidir.

### 2a. O LexPubli também sai do broker do LexLearn

Hoje (ADR-0001, spike) o LexPubli publica no RabbitMQ do LexLearn, e o
LexCorpus usa uma `RABBIT_URL` só, a do LexLearn, para tudo: o v2.1, o
consumo de `lexpubli.events` e as respostas `document.*`. Ou seja, a
automação LexPubli ↔ LexCorpus passa fisicamente pelo broker do LexLearn, e
o LexPubli guarda uma credencial dele. É um segundo ponto de contato, que
esta decisão não permite.

- A automação LexPubli ↔ LexCorpus passa a usar um **broker próprio do
  LexPubli** (o serviço `rabbitmq` do compose do LexPubli já existe).
- O LexCorpus fala com **dois brokers**: o do LexPubli (consome
  `contest.discovery.*`, publica `document.*`) e o do LexLearn (só o v2.1).
  A configuração ganha uma URL separada para o lado LexPubli.
- O LexPubli **não tem credencial** do broker do LexLearn. O overlay
  `docker-compose.lexlearn.yml` deixa de existir.
- O exchange `lexcorpus.events` do broker do LexLearn volta a ter só
  `concurso.*`.

### 3. O v2.1 continua automático

O caminho LexCorpus → LexLearn (`concurso.*`, `/data/raw/exams/`) **não
muda**. Uma coleta que nasceu de um concurso descoberto pelo LexPubli chega
ao LexLearn como qualquer outra: alimenta o acervo e o DNA das bancas.

O LexPubli **influencia indiretamente o que entra no acervo**. Isso é
aceito, porque entrar no acervo não é decisão de geração. Gerar continua
sendo por demanda.

### 4. Geração, prioridade e "estudo pronto" são decisões do Administrador

- **O que gerar, para qual concurso e em que ordem** é decidido pelo
  Administrador do LexLearn, dentro do LexLearn (`tarefas_geracao`).
- O Administrador pode **consultar** o painel do LexPubli e o estado do
  LexCorpus para decidir: link que **navega**, nunca botão que **executa**
  ação no outro sistema (LexLearn ADR-0007 §6).
- A **prioridade** do LexPubli (Heat Engine, curadoria) serve ao portal
  (destaque, ordem) e à **ordem de coleta** do LexCorpus. Não chega ao
  LexLearn.
- Se o portal mostrar um convite para estudar no LexLearn, ele é posto
  **pela curadoria**, à mão, depois que o Administrador do LexLearn
  confirmar que há estudo pronto. Não há `study.target.ready`.

### 5. Revisões nos ADRs anteriores

**ADR-0004:**

| Trecho | Como fica |
|---|---|
| §1, tabela, linha LexLearn | O LexLearn não participa do eixo por eventos. Recebe provas pelo v2.1 e editais pela pasta. O concurso-alvo é eixo **LexPubli ↔ LexCorpus** |
| §2, prioridade | Serve ao portal e à ordem de coleta do LexCorpus, não à GPU |
| §4 (LexLearn assina) | **Revogado** |
| §5 (`study.target.ready`) | **Revogado**. Convite no portal só por curadoria (§4 acima) |
| §6 (métrica) | Passa a ser **tempo até provas disponíveis**: da aprovação do alvo aos `document.acquisition.completed` |
| Mudanças de contrato | Saem as linhas "filas do LexLearn" e `study.target.ready`. Em v1.1 e em `.updated`, o único consumidor a atualizar a cópia primeiro é o LexCorpus; em `related`, é o LexPubli |
| Fases 2–4 | Substituídas pelas fases da §6 abaixo |

**ADR-0003:**

| Trecho | Como fica |
|---|---|
| §4, fase 1 | A rota `POST /exams/ingerir-lote` é acionada pelo **Administrador do LexLearn**, nunca pelo LexPubli |
| §4, fase 2 (`edital.available`) | **Revogada.** Se o LexLearn quiser descobrir editais novos sozinho, faz isso olhando a própria pasta, por decisão dele |

### 6. Fases do concurso-alvo, revistas

- **Fase 1, o alvo e as relacionadas** (LexPubli + LexCorpus): como no
  ADR-0004, sem nada no LexLearn.
- **Fase 2, o portal mostra as provas disponíveis:** o LexPubli consome os
  `document.acquisition.*` do LexCorpus e mostra, na página do concurso,
  quantas provas anteriores e relacionadas já existem.
- **Fase 3, prioridade na coleta:** o Heat Engine ordena as coletas do
  LexCorpus (`contest.discovery.updated` com prioridade), e a métrica "tempo
  até provas disponíveis" vai para o painel.

## Alternativas consideradas

- **Manter o ADR-0004 como estava:** o portal público passaria a mandar na
  GPU e, com clientes pagantes, no serviço deles. Rejeitada.
- **O LexLearn assina os eventos só para informação, sem agir sozinho:**
  ainda abre um caminho do portal público até o LexLearn e cria pressão para
  automatizar depois. O Administrador já pode consultar o painel do
  LexPubli. Rejeitada.
- **Tirar também o v2.1 do automático** (o Administrador aprova cada
  entrada no acervo): mexe num contrato que funciona e trava o DNA, que
  precisa de N. Rejeitada; a fronteira de decisão está na geração, não no
  acervo.

## Consequências

**Positivas.**
- O LexLearn fica isolado do portal público: um LexPubli comprometido não
  dispara geração, não muda prioridade e não fala com a API do LexLearn.
- A fronteira comercial fica limpa: os serviços pagos dependem só do
  LexLearn.
- Menos contratos: sem cópias no LexLearn, sem `study.target.ready`, e a
  Fase 1 só envolve dois projetos.

**Negativas / a monitorar.**
- O LexCorpus passa a manter duas conexões de broker, e o LexPubli um
  broker próprio (mais um serviço a operar).
- O ciclo "concurso anunciado → estudo pronto" passa a ter um passo humano
  no LexLearn. É intencional, mas o tempo desse passo não é medido pelos
  eventos.
- A pasta `/data/raw/editais/` é o único caminho de escrita do LexPubli em
  território do LexLearn, e o LexPubli é o projeto exposto à internet. O
  isolamento físico (disco, VM ou máquina) está em análise no BACKLOG.
