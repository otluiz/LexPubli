<!-- Arquivo:  docs/architecture/decisions/ADR-0004-concurso-alvo.md
     Função:   registra o "concurso-alvo" como eixo comum do ecossistema Lex:
               o concurso anunciado pelo LexPubli orienta a coleta de provas
               relacionadas (LexCorpus) e a preparação do estudo (LexLearn). -->

# ADR-0004: Concurso-alvo como eixo do ecossistema

- Status: **Aceito** em 2026-10-13 pelo dono do produto. Afeta os três
  projetos. Espelhos: LexCorpus ADR-0008 e LexLearn ADR-0012.
- **REVISÃO (2026-10-13, ADR-0005):** a automação é só LexPubli ↔ LexCorpus.
  Ficam **revogados** o §4 (o LexLearn assina os eventos) e o §5
  (`study.target.ready`). O §1 (linha LexLearn), o §2 (prioridade), o §6
  (métrica), a tabela de mudanças de contrato e as fases 2–4 foram revistos
  no ADR-0005 §5–6. O LexLearn recebe provas pelo v2.1 e editais pela pasta;
  o que gerar é decisão do Administrador dele.
- Data: 2026-10-13
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0002 (fronteira LexPubli × LexCorpus), ADR-0003
  (editais), LexCorpus ADR-0006/0007 (buscador, política de coleta),
  LexLearn README do pipeline DNA e BACKLOG (perfil de banca, Fase 6).

## Contexto

**O modelo de negócio, nas palavras do dono do produto:** quando um concurso
está por vir (ex.: Sefaz-AL 2026), consultar provas relacionadas (Sefaz-CE e
outras), pedir ao LexCorpus que procure mais, e o LexLearn saber disso e
preparar a infraestrutura para gerar questões no estilo daquela banca e
daquele concurso.

O que já existe:

- **A prática manual.** O `watchlist.yaml` do LexCorpus tem o bloco "Carreira
  fiscal (26/09)": Sefaz-AL 2019, Sefaz-DF 2019 e Sefaz-CE 2021, todos da
  Cebraspe, coletados porque a Sefaz-AL 2026 abriu. É exatamente "concurso
  por vir → provas relacionadas", feito à mão.
- **A necessidade medida no LexLearn.** Cada linha de `banca_profiles`
  declara o que não mede, e uma das entradas é *"generalização (N=1 concurso
  por banca)"*. O perfil da Cebraspe se apoia em ~50 questões. Mais provas da
  mesma banca e da mesma carreira é o que falta ao DNA.
- **O passo em aberto no LexLearn.** "Ligar a geração ao perfil" (Fase 6, na
  GPU). Hoje o `quiz_generator.py` "não sabe nada de banca".
- **As peças de integração** (ADR-0002, ADR-0003):
  - o LexPubli anuncia o concurso aprovado (`contest.discovery.created`,
    com o `contest_id`);
  - o LexCorpus coleta o próprio concurso (`current`) e certames anteriores
    do mesmo órgão (`previous`), e responde com `document.acquisition.*`;
  - o LexPubli grava os editais (com o conteúdo programático) em
    `/data/raw/editais/`, com o `contest_id` no sidecar.

**O que falta:** um **eixo comum**. Hoje cada projeto sabe uma parte do
concurso, e nada diz ao LexLearn **para qual concurso** cada prova e cada
edital servem, nem **até quando** ele precisa estar pronto.

## Decisão

### 1. O concurso-alvo

O **concurso-alvo** é um concurso anunciado e aprovado no LexPubli, para o
qual o ecossistema prepara estudo dirigido. A chave dele em todos os
projetos é o **`contest_id`** do LexPubli.

| Projeto | Papel no concurso-alvo |
|---|---|
| **LexPubli** | Diz **qual é o alvo**: banca, órgão, cargo, **carreira**, **data da prova**, prioridade. Publica o edital (ADR-0003) |
| **LexCorpus** | Diz **quais documentos servem** ao alvo: o próprio, os anteriores do órgão e os **relacionados** (mesma banca, mesma carreira) |
| **LexLearn** | Decide **como preparar**: DNA das provas vinculadas, perfil da banca com recorte do alvo, geração no estilo da banca e nas disciplinas do edital |

A fronteira do ADR-0002 continua: cada projeto decide dentro do próprio
domínio, e a integração é só por eventos.

### 2. LexPubli: carreira e data da prova

- **Carreira**, escolhida pelo curador na aprovação, a partir de uma **lista
  fixa e curta**:

  | slug | exemplos |
  |---|---|
  | `fiscal` | Sefaz, Receita, auditor fiscal |
  | `controle` | TCU, TCEs, CGU |
  | `tribunais` | TJs, TRFs, TRTs, TREs (área administrativa e judiciária) |
  | `juridica` | procuradorias, defensorias, MP, magistratura |
  | `policial` | PF, PRF, PCs, PMs |
  | `legislativa` | câmaras, assembleias, Senado |
  | `bancaria` | BB, Caixa, BNB, BNDES, Bacen |
  | `administrativa` | órgãos executivos em geral, analistas e técnicos |
  | `estatais` | Petrobras, Transpetro e similares |
  | `saude` | SUS, hospitais, agências de saúde |
  | `educacao` | professores, institutos federais |

  É uma lista **da curadoria**, não uma taxonomia acadêmica. A taxonomia
  rica do LexLearn (`aprendizado/taxonomy/`) continua dele. Valor novo na
  lista = MINOR no contrato, implantado com o consumidor primeiro.
- **Data da prova** (`exam_date`): quase sempre sai depois do edital. Ela
  define **até quando** o alvo precisa estar pronto.
- **Prioridade:** vem do Heat Engine (vagas, salário, prazo) e das decisões
  da curadoria. É ela que diz ao LexLearn **onde gastar GPU primeiro**.

### 3. LexCorpus: a relação `related`

Além de `current` (o próprio concurso) e `previous` (o mesmo órgão), o
LexCorpus passa a buscar **`related`: a mesma banca e a mesma carreira, em
outros órgãos**. É a relação que alimenta o DNA da banca, e é a que o dono
do produto faz hoje à mão.

- **Fonte 1, o acervo** (barato e certo): concursos já coletados com a mesma
  banca e a mesma carreira. A resposta `completed` sai **na hora**. Para isso
  o catálogo do LexCorpus ganha o campo `carreira`:
  - preenchido sozinho nos concursos que chegam por evento (vem do alvo);
  - marcado uma vez pelo operador no acervo já existente (ex.: `sefaz_ce_21`,
    `sefaz_al_19_auditor` e `seec_auditor_19` → `fiscal`).
- **Fonte 2, a descoberta** (depois): inventários das bancas e o buscador
  ("provas {banca} {carreira}"), sob a mesma política do ADR-0007 do
  LexCorpus: banca validada, confirmação, limite.
- **Política** (`politica_coleta.yaml`):
  - **mesma banca obrigatória**, porque o DNA é por banca;
  - no máximo **N relacionados por alvo** (sugestão inicial: 5), os mais
    recentes primeiro;
  - outras bancas da mesma carreira ficam **desligadas** no início.
- **A ligação é o ponto central.** Um mesmo concurso do acervo serve a
  vários alvos (o `sefaz_ce_21` serve à Sefaz-AL 2026 e a qualquer futuro
  alvo fiscal da Cebraspe). Isso já é suportado: a ligação no StateStore é
  por `(banca, concurso, contest_id)`.

### 4. LexLearn: o alvo como unidade de preparação

O LexLearn passa a **assinar**, com filas próprias:

| Evento | Exchange | Para quê |
|---|---|---|
| `contest.discovery.created` / `.updated` | `lexpubli.events` | Criar e atualizar o concurso-alvo: banca, cargo, carreira, data da prova, prioridade |
| `document.acquisition.completed` | `lexcorpus.events` | Vincular alvo ↔ `lexcorpus_contest` (as provas que ele já recebe pelo v2.1) |

- O **edital** chega pelo ADR-0003 e é ligado ao alvo pelo `contest_id` do
  sidecar.
- Isso **ajusta o ADR-0002**, que dizia que os `document.*` "não chegam ao
  LexLearn". Continua verdade por padrão: o LexLearn só os recebe porque
  **optou** por uma fila própria. O contrato v2.1 (`concurso.*`,
  `/data/raw/exams`, slugs) **não muda**. As provas continuam chegando como
  hoje; a novidade é saber **para qual alvo** cada uma serve.
- **O que o LexLearn faz com o alvo é decisão dele**, a registrar em ADR
  próprio. A expectativa do negócio:
  1. DNA das provas vinculadas, pelo pipeline determinístico que já existe;
  2. perfil da banca com o **recorte do alvo** (as provas vinculadas),
     elevando o N do perfil e declarando o recorte, como o perfil já exige;
  3. geração no estilo da banca (Fase 6), nas **disciplinas do edital**;
  4. fila de preparação ordenada por **data da prova** e **prioridade**.

### 5. LexLearn → LexPubli: o alvo está pronto

O LexLearn publica **`study.target.ready`** quando há estudo dirigido
disponível para o alvo (simulado, trilha, flashcards: ele decide o quê).

- O **dono do schema é o LexLearn**, e o LexPubli consome.
- Na página do concurso, o LexPubli mostra: *"Simulado Sefaz-AL 2026, estilo
  Cebraspe → estude no LexLearn"*.

Fecha-se o ciclo do negócio: o público chega pelo LexPubli e encontra o
estudo pronto no LexLearn.

### 6. A métrica do negócio

**Tempo até pronto:** dias entre a aprovação do alvo no LexPubli e o
`study.target.ready`, comparado com os dias até a prova. Cada etapa tem o
seu marco nos eventos (`contest.discovery.created`, os `completed`, o
`study.target.ready`) e pode ser medida sem instrumentação nova.

## Mudanças de contrato

| Mudança | Versão | Implantação |
|---|---|---|
| `contest.discovery.created` ganha `career` e `exam_date` (opcionais) | v1.1 | **Consumidor primeiro.** Os schemas v1 usam `additionalProperties: false`, então um consumidor com a cópia antiga **recusaria** os campos novos. Ordem: LexCorpus e LexLearn atualizam a cópia, depois o LexPubli emite |
| `contest.discovery.updated` (nova): mudança de status, data da prova, carreira ou prioridade | v1.0 | Consumidores assinam antes de o LexPubli emitir |
| `relation: related` em `document.acquisition.*` | v1.1 | LexPubli e LexLearn aceitam `related` antes de o LexCorpus emitir |
| Filas do LexLearn em `lexpubli.events` e `lexcorpus.events` | — | Do lado do LexLearn; não muda nenhum produtor |
| `study.target.ready` (nova) | v1.0, dono LexLearn | O LexPubli consome |

> Lição registrada: em contratos com `additionalProperties: false`, **até um
> campo opcional novo** quebra o consumidor que ainda tem a cópia antiga. A
> regra "consumidor primeiro" vale para toda mudança, MINOR inclusive.

## Alternativas consideradas

- **O LexLearn decide sozinho o que é relacionado** (por similaridade, com
  embeddings): ele não sabe o que *existe* para coletar, e saber isso é
  trabalho do LexCorpus. Pode **sugerir** depois (ex.: disciplinas em comum
  medidas no DNA), como evolução.
- **O LexPubli escolhe as provas relacionadas:** coloca no LexPubli um
  conhecimento que é do LexCorpus (o acervo, os spiders). Viola o ADR-0002.
- **Carreira inferida automaticamente** do cargo ou do órgão: erros de
  classificação viram coleta errada em escala. A curadoria já aprova o
  concurso, e escolher a carreira custa um campo. Inferência pode vir depois,
  como **sugestão** para o curador.
- **Relacionados de qualquer banca da mesma carreira:** ajuda o conteúdo,
  mas dilui o DNA, que é por banca. Fica desligado, como opção de política.

## Consequências

**Positivas.**
- O modelo de negócio vira fluxo: anúncio → provas relacionadas → preparação
  → estudo pronto, com uma chave só (`contest_id`).
- O LexLearn ganha o que o perfil de banca declara não ter (N > 1) e o que a
  geração precisa (banca, disciplinas, prazo).
- A GPU, o recurso caro, passa a seguir a prioridade do negócio.
- A prática manual da "carreira fiscal" vira política versionada.

**Negativas / riscos.**
- (a) O LexLearn assume trabalho novo: um consumidor, o modelo de alvo e a
  Fase 6. É a etapa mais longa e define o ritmo do ciclo.
- (b) A lista de carreiras precisa de disciplina de curadoria.
- (c) Mais eventos e versões em circulação. Por isso a lição registrada nas
  mudanças de contrato.
- (d) A questão autoral da republicação de questões (ADR-0002 §4) fica mais
  urgente: o produto passa a depender de provas reais como base da geração.

## Implantação, em fases

**Fase 1: o alvo e as relacionadas** (LexPubli + LexCorpus)
- [ ] LexPubli: `carreira` e `data da prova` no `ConcursoPage` e na curadoria
- [ ] Contratos v1.1 (`career`, `exam_date`, `related`) e
      `contest.discovery.updated` v1.0; cópias atualizadas **antes** da emissão
- [ ] LexCorpus: campo `carreira` no catálogo; marcação do acervo existente
- [ ] LexCorpus: relação `related` a partir do acervo, com política de limite
- [ ] Validação: a Sefaz-AL 2026 deve receber, sem coleta nova, os
      `completed` do acervo fiscal da Cebraspe já existente

**Fase 2: o LexLearn conhece o alvo**
- [ ] ADR do LexLearn: modelo de concurso-alvo, filas próprias, vínculos
- [ ] Consumidor do alvo e dos `completed`; vínculo com os editais (ADR-0003)
- [ ] Perfil da banca com o recorte do alvo

**Fase 3: estudo pronto**
- [ ] LexLearn: geração ligada ao perfil (Fase 6) e às disciplinas do edital
- [ ] `study.target.ready` (schema do LexLearn) e CTA na página do LexPubli

**Fase 4: prioridade**
- [ ] Heat Engine → `contest.priority.changed` → fila de preparação do
      LexLearn ordenada por prazo e prioridade
- [ ] Métrica "tempo até pronto" no painel
