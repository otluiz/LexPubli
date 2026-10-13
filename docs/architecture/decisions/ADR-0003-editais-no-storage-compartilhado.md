<!-- Arquivo:  docs/architecture/decisions/ADR-0003-editais-no-storage-compartilhado.md
     Função:   registra que o LexPubli passa a gravar editais em
               /data/raw/editais/, só com autorização humana e só de fonte
               oficial, no formato que o LexLearn já lê. -->

# ADR-0003: Editais no storage compartilhado (`/data/raw/editais/`)

- Status: **Aceito** em 2026-10-13 pelo dono do produto, inclusive a chave
  `{concurso}` = `contest_slug` + `contest_id` (§2). A nota no ADR-0007 do
  LexLearn (fronteira de ingestão) foi registrada em 13/10/2026.
- **REVISÃO (2026-10-13, ADR-0005):** no §4, a fase 1 é acionada pelo
  Administrador do LexLearn, nunca pelo LexPubli; a fase 2
  (`edital.available`) foi revogada. A pasta é o único ponto de contato do
  LexPubli com o LexLearn.
- Data: 2026-10-12
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0002 (fonte oficial; agregador só como índice);
  LexLearn ADR-0005 (taxonomia de diretórios) e ADR-0007 (fronteira de
  ingestão); LexCorpus `docs/CONTRATO.md` §2 (quem escreve em `exams/`).

## Contexto

O edital traz o **conteúdo programático**: é ele que diz ao LexLearn
**quais disciplinas** preparar para um concurso. Com a banca (DNA, no
LexLearn) e as provas relacionadas (LexCorpus), o edital completa o que é
preciso para gerar estudo dirigido a um concurso.

O que já existe, apurado em 12/10/2026 no repositório do LexLearn:

- **A pasta existe:** `data/raw/editais/{banca}/{concurso}/`, mesma convenção
  de `exams/` (anotada no `.gitkeep`). Hoje há 4 editais da Transpetro 2026
  (Cesgranrio) em `cesgranrio/transpetro_psp_*_2026_N/`, cada um com sidecar
  `.meta.json`.
- **O formato do sidecar existe**, criado à mão: `schema_version`,
  `arquivo`, `papel: "edital_abertura"`, `banca`, `concurso`, `orgao`,
  `checksum_sha256`, `vigente`, `indexar`, `origem.fonte_url`,
  `publicacao_dou`.
- **A ingestão funciona, mas é manual:** o arquivo é colocado na pasta, e a
  ingestão roda por `POST /exams/ingerir-lote` com `subdir: "editais"`. O
  `exams_ingest.py` lê do sidecar:
  - o `papel`: se começar com `edital` (ou for `extrato_dou`), o documento
    vira `document_type = 'edital'`, e o dado declarado vence o
    classificador;
  - o `checksum_sha256`;
  - o sidecar inteiro, que vai para `analysis_metadata`.
- **Não há evento de fila para editais.**
- **Não há dono definido.** O ADR-0007 do LexLearn diz que as provas entram
  só pelo LexCorpus e que o usuário sobe só leis. Os editais ficaram de fora.
- **A origem dos atuais é um agregador.** Os 4 editais da Transpetro foram
  baixados à mão do PCI (marca d'água `pcimarkpci`). O próprio sidecar
  registra isso, e conflita com a regra da fonte oficial (ADR-0002 §4).
- **O backlog do LexLearn já registrou dois problemas:**
  - *item 13:* editais têm versões (retificação, consolidação), e a data do
    cabeçalho não serve de chave. Medido: o extrato do DOU diverge da
    íntegra em 2 de 4 editais;
  - *a chave `(banca, concurso)`* é o que pareia o edital com as provas do
    mesmo concurso.

## Decisão

### 1. Quem escreve: o LexPubli, e só com autorização humana

- O **LexPubli é o único escritor automatizado** de `/data/raw/editais/`.
  - O LexCorpus continua escrevendo **só** em `exams/` (CONTRATO §2).
  - O LexLearn continua dono da pasta e é o consumidor.
  - O legado manual (os 4 editais da Transpetro) fica como está.
- **Nada é gravado sem autorização humana.** O LexPubli *encontra* o
  edital, e o curador, no painel:
  - confere que é a **fonte oficial** e o **concurso certo**;
  - diz qual é a **versão** (abertura, retificação, consolidado);
  - **autoriza**.

  Só então o arquivo é gravado. Quem autorizou e quando vão no sidecar.
- **Fonte oficial obrigatória** (ADR-0002 §4): site da banca, do órgão ou
  diário oficial. Agregadores servem para *descobrir* o edital, nunca como
  origem do arquivo gravado.
- **O LexPubli nunca apaga nem sobrescreve.** Uma versão nova é um arquivo
  novo; uma versão superada vira `vigente: false`, como o preliminar no
  contrato v2.1. Remoção física é decisão de um administrador do LexLearn.

> Complementa o ADR-0007 do LexLearn (§4, "quem alimenta o quê"):
> **editais entram exclusivamente pelo LexPubli, com autorização humana**.
> A nota correspondente deve ser registrada no LexLearn (ver Implantação).

### 2. Onde e como gravar

```text
/data/raw/editais/{banca}/{concurso}/
    {nome original}.pdf
    {nome original}.pdf.meta.json
```

- **Pasta plana por concurso, nome original preservado, basename sem
  barra.** É a mesma regra do `exams/` (CONTRATO §2), contra path traversal.
- **Ordem de escrita:** os dois arquivos são gravados como `.tmp` e
  renomeados (escrita atômica). **O sidecar é renomeado primeiro e o PDF por
  último.** A varredura do LexLearn lista PDFs, então um PDF nunca fica
  visível sem o sidecar ao lado. Sem sidecar, o LexLearn cairia no
  classificador por texto.
- **`{banca}`** usa o slug canônico, o mesmo do LexCorpus (ex.: `cebraspe`).
- **`{concurso}`** usa o `contest_slug` do LexPubli (ex.: `sefaz_al_2026`), e
  o sidecar leva o `contest_id`. Esta escolha **muda o pareamento no
  LexLearn**:
  - O slug das *provas* é do LexCorpus e muitas vezes é outro (ex.:
    `sefaz_al_26`, o identificador da Cebraspe).
  - O edital chega **antes** das provas, quando o LexCorpus pode nem ter
    resolvido o alvo.
  - Por isso o pareamento edital ↔ provas passa a ser pelo **`contest_id`**,
    a chave comum do ecossistema. O LexLearn recebe a ligação
    `contest_id` ↔ `lexcorpus_contest` pelo `document.acquisition.completed`
    (ADR-0004, concurso-alvo).
  - A alternativa (gravar com o slug do LexCorpus) deixaria o LexPubli
    dependente de uma resolução que pode nunca acontecer (`awaiting_operator`).

### 3. O sidecar do edital (v1)

Compatível com o que o LexLearn já lê: `papel` começa com `edital` e
`checksum_sha256` está presente. O resto vai inteiro para
`analysis_metadata`. O schema fica em
`contracts/storage/edital.sidecar.schema.json` no LexPubli, que é quem
produz. O LexLearn carrega uma cópia, seguindo a regra "consumidor primeiro".

```json
{
  "schema_version": "edital-1.0",
  "arquivo": "edital_1_abertura.pdf",
  "papel": "edital_abertura",
  "banca": "cebraspe",
  "concurso": "sefaz_al_2026",
  "orgao": "sefaz_al",
  "checksum_sha256": "…",
  "tamanho_bytes": 812345,
  "vigente": true,
  "indexar": true,
  "edital_numero": "1",
  "publicado_em": "2026-08-25",
  "retifica": null,
  "substituido_por": null,
  "origem": {
    "fonte_url": "https://cdn.cebraspe.org.br/concursos/sefaz_al_26/arquivos/….pdf",
    "publicacao_dou": null,
    "coletado_em": "2026-10-12T21:00:00Z",
    "autorizado_por": "curador@…",
    "autorizado_em": "2026-10-12T21:05:00Z",
    "produtor": "lexpubli"
  },
  "lexpubli": { "contest_id": "01a132f0-…", "contest_slug": "sefaz_al_2026" }
}
```

- **`papel`:**
  - `edital_abertura`;
  - `edital_retificacao`, que complementa: o anterior **continua** vigente,
    e `retifica` aponta para ele;
  - `edital_consolidado` ("atualizado conforme retificações"), que
    **substitui** a abertura anterior: o anterior fica `vigente: false`, com
    `substituido_por`;
  - `extrato_dou`.

  Documentos sem conteúdo de estudo (listas de isenção, convocações) não
  entram.
- **`publicado_em`** é a data **da fonte** (página da banca ou DOU), não a do
  cabeçalho do PDF. Isso responde ao item 13 do LexLearn: a data impressa
  diverge, e quem decide a versão é o curador, com a fonte à vista.
- **`indexar`:** `true` só na íntegra que deve virar texto de busca; o
  extrato do DOU fica `false`. A convenção é a que o LexLearn já usa.

### 4. O aviso ao LexLearn, em duas fases

> **REVISADO pelo ADR-0005:** o LexPubli não avisa o LexLearn. Quem aciona a
> ingestão é o Administrador do LexLearn; a fase 2 abaixo está revogada.

- **Fase 1 (sem evento):** o LexLearn ingere pela rota que já existe
  (`POST /exams/ingerir-lote`, `subdir: "editais"`). Nada muda no LexLearn
  além de aceitar o sidecar v1.
- **Fase 2 (com evento):** o LexPubli publica `edital.available` em
  `lexpubli.events` (envelope v1, padrão Claim Check):
  - `contest_id`, `banca`, `concurso`, a lista de arquivos com `papel`,
    `checksum_sha256` e `vigente`, e o `storage_uri` da pasta;
  - nenhum binário.

  O LexLearn assina com fila própria quando tiver o consumidor, e implanta
  primeiro (consumidor primeiro).

### 5. Mínimo privilégio no container

O worker do LexPubli que grava monta **só** `/data/raw/editais` (leitura e
escrita), não `/data` inteiro. Ele não enxerga `exams/`, `laws/` nem
`processed/`. O portal (`web`) não monta storage nenhum.

## Alternativas consideradas

- **O LexCorpus coleta os editais** (ele já raspa os sites das bancas):
  - mistura documento de *prova* com documento de *concurso*;
  - o LexCorpus não tem curadoria humana, e editais exigem decidir versão e
    relevância;
  - os spiders das bancas hoje descartam editais de propósito, para não
    poluir o acervo de provas.

  Rejeitada. Pode ser revista se a curadoria virar gargalo.
- **Gravar sem autorização, com revisão depois:** o edital vira estudo
  dirigido. Um edital errado (concurso trocado, versão superada) gera
  material errado em escala. Rejeitada, por pedido explícito do dono do
  produto.
- **`{concurso}` = slug do LexCorpus:** pareamento direto com as provas, mas
  dependente de uma resolução que pode não existir quando o edital sai.
  Rejeitada em favor do `contest_id` (§2).

## Consequências

**Positivas.**
- Editais de fonte oficial, versionados e autorizados chegam ao LexLearn no
  formato que ele já lê.
- O ecossistema ganha a peça que faltava para o estudo dirigido: as
  disciplinas do edital.
- A fronteira de ingestão do LexLearn fica completa: provas pelo LexCorpus,
  editais pelo LexPubli, leis pelo usuário.

**Negativas / riscos.**
- (a) A curadoria de editais é trabalho humano a mais. É o preço da regra,
  e o Heat Engine ajuda a decidir o que olhar primeiro.
- (b) O pareamento por `contest_id` exige que o LexLearn implemente a
  ligação do ADR-0004.
- (c) O LexPubli passa a ter escrita num volume compartilhado. A mitigação
  é o §5 (monta só `editais/`) e a regra de nunca apagar nem sobrescrever.

## Implantação (consumidor primeiro)

**LexLearn**
- [x] Nota no ADR-0007 (§4): editais entram só pelo LexPubli, com
      autorização humana (13/10/2026)
- [ ] Aceitar o sidecar `edital-1.0` (cópia do schema; `papel` com os novos
      valores, todos começando com `edital`)
- [ ] Conferir os 4 PDFs da Transpetro duplicados na raiz de `editais/`
      (raiz = caixa de entrada) contra os organizados em `cesgranrio/`

**LexPubli**
- [ ] Schema `contracts/storage/edital.sidecar.schema.json` (v1) e exemplo
- [ ] Modelo `Edital` ligado a `ConcursoPage`, com fonte, versão, papel e
      estado (`encontrado`, `autorizado`, `gravado`, `recusado`)
- [ ] Painel: fila de editais encontrados; autorizar e recusar; a fonte
      oficial é obrigatória para autorizar
- [ ] Gravação atômica (sidecar antes do PDF), sem apagar nem sobrescrever,
      com volume montado só em `/data/raw/editais`
- [ ] Fase 2: evento `edital.available`, depois que o LexLearn tiver o
      consumidor
