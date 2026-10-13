<!-- Arquivo:  docs/architecture/decisions/ADR-0007-fontes-por-poder.md
     Função:   registra as fontes oficiais de descoberta de concursos do
               LexPubli, organizadas por Poder: Executivo, Legislativo,
               Judiciário e Ministério Público. -->

# ADR-0007: Fontes de descoberta por Poder

- Status: **Aceito** em 2026-10-13 pelo dono do produto.
- **REVISÃO (2026-10-13, dono do produto):** notícias oficiais sobre a
  iminência de um concurso também são fonte (§3a). O LexPubli fala de
  concursos, e avisar antes do edital é argumento de marketing e de venda.
- Data: 2026-10-13
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0001 (changedetection.io como gatilho), ADR-0002 (fonte
  oficial obrigatória; agregador só como índice), ADR-0003 (editais),
  ADR-0004 (carreiras); LexCorpus ADR-0009 (varredura por carreira).

## Contexto

Hoje o LexPubli descobre concursos por um caminho só: o changedetection.io
vigiando páginas escolhidas à mão (a API da Cebraspe, no spike). É pouco
para ser a porta de entrada do ecossistema. O dono do produto pediu (13/10)
que as fontes cubram o Estado, organizadas por Poder:

- **Executivo:** os ministérios e as demandas do Poder Executivo;
- **Legislativo;**
- **Judiciário;**
- **Ministério Público.**

O que foi verificado (13/10):

- **Executivo federal.** As autorizações de concurso saem no **DOU** como
  portarias do Ministério da Gestão e da Inovação (MGI). Exemplos: a
  Portaria MGI nº 5.759/2023, com 520 vagas em quatro ministérios, e as
  três portarias de junho/2025, com cerca de 2.000 vagas. Os editais e
  extratos também saem no DOU. A Imprensa Nacional oferece o DOU completo
  em **XML e PDF pelo INLABS**, gratuito desde 2020, com os últimos 4 meses
  na ferramenta e o histórico em dados abertos.
- **Legislativo.** Câmara e Senado têm APIs de dados abertos, mas elas cobrem
  parlamentares, proposições e votações, **não concursos**. Os concursos
  ficam nas páginas de Transparência/RH de cada casa.
- **Judiciário.** O DJEN do CNJ (`comunica.pje.jus.br`) publica
  comunicações processuais. Não é uma fonte comprovada de concursos. Cada
  tribunal publica os seus concursos na própria página.
- **Ministério Público.** O CNMP não mantém uma lista consolidada. Cada ramo
  (MPU, MPF, MPT, MPM, MPDFT) e cada MP estadual publica a sua.

Ou seja, **só o Executivo federal tem uma fonte estruturada**, o DOU.
Legislativo, Judiciário e MP são centenas de páginas oficiais, uma por
órgão.

## Decisão

### 1. As fontes viram cadastro, organizadas por Poder

O LexPubli ganha o cadastro **Fonte**, um snippet no painel:

| Campo | Para quê |
|---|---|
| `poder` | executivo, legislativo, judiciario, ministerio_publico |
| `esfera` | federal, estadual, municipal (a mesma do `Orgao`) |
| `orgao` | o órgão a que a fonte se refere, quando é de um órgão só |
| `tipo` | `dou` (coletor próprio) ou `pagina` (vigiada pelo changedetection) |
| `url` | a página oficial |
| `carreira_sugerida` | ex.: tribunais para um TRT, controle para um TCE |
| `prioridade`, `ativa` | o que vigiar primeiro, e com que frequência |

- **Só fonte oficial** (ADR-0002): domínio `.gov.br`, `.leg.br`, `.jus.br`,
  `.mp.br` ou o site da banca contratada. Agregadores continuam só como
  índice, e o cadastro recusa outros domínios.
- As fontes `pagina` são **sincronizadas com o changedetection.io** pela API
  dele. O cadastro no LexPubli é a fonte da verdade; o changedetection só
  executa. Tudo o que muda vira **Descoberta pendente**, como hoje.
- A `carreira_sugerida` aparece para o curador como **sugestão**. Quem grava
  a carreira do concurso continua sendo o curador (ADR-0004).

### 2. Executivo federal: um coletor do DOU

O worker ganha `coletar_dou`, rodado uma vez por dia:

- baixa pelo INLABS as Seções 1 e 3 do dia, em XML, só os atos;
- filtra por termos versionados: "autoriza a realização de concurso
  público", "concurso público", "edital de abertura", "extrato de edital";
- cada ato que casa vira uma **Descoberta pendente**, com o texto, o órgão
  publicador, a seção e o link oficial do ato no `in.gov.br`;
- **status sugerido pelo tipo de ato:** portaria de autorização →
  `autorizado`; edital de abertura → `edital_aberto`.

O XML do DOU é **dado público de leitura**. O LexPubli não republica o
DOU: guarda só o trecho do ato para a curadoria e o link oficial.

### 3. Legislativo, Judiciário e MP: páginas oficiais, em ondas

Cada órgão entra como uma `Fonte` do tipo `pagina`. A cobertura cresce em
ondas, porque são centenas de páginas e cada uma precisa ser conferida
(muitas são renderizadas por JS, como a da Cebraspe):

| Onda | Executivo | Legislativo | Judiciário | Ministério Público |
|---|---|---|---|---|
| **A, federal** | DOU (coletor) + página de concursos autorizados do MGI | Câmara, Senado, TCU | CNJ, STF, STJ, TST, TSE, STM, CJF, CSJT | CNMP, MPU (MPF, MPT, MPM, MPDFT) |
| **B, regional** | — | — | 6 TRFs, 24 TRTs, 27 TREs, 27 TJs | 26 MPs estaduais |
| **C, estadual** | Diários oficiais estaduais e Sefaz | Assembleias e TCEs | (TJMs) | — |

- **Onda A primeiro**, com cerca de 25 fontes e o DOU.
- Cada fonte nova é **conferida antes de ser ativada**: a página tem texto
  legível sem JS? Se não tiver, há uma API ou um feed? O `robots.txt`
  permite? Fonte que não passa fica cadastrada como inativa, com o motivo.
- As **Defensorias** (DPU e DPEs) e a **Advocacia Pública** (AGU,
  procuradorias) entram junto com o MP na onda em que couberem: são
  carreiras jurídicas, e o curador já as classifica como `juridica`.

### 3a. Notícias oficiais: o concurso antes do edital

A comissão formada, a banca contratada, a autorização publicada: tudo isso
sai nas **notícias** do órgão antes do edital. Avisar primeiro é o que
diferencia o portal, e é material de marketing.

- A `Fonte` ganha o campo `conteudo`: `concursos` (a página oficial de
  concursos) ou `noticias` (a listagem de notícias do órgão, de preferência
  a busca ou a etiqueta "concurso" do próprio site).
- A página de notícias publica de tudo. Por isso, **só nas fontes de
  notícias**, o webhook só cria Descoberta quando a mudança cita concurso,
  edital, banca organizadora, comissão do concurso, provimento ou nomeação.
  O resto é ignorado e **contado** na Fonte (avisos recebidos e ignorados),
  para medir o ruído de cada uma.
- Até duas fontes por órgão: a de concursos e a de notícias.
- O que vira Descoberta continua passando pelo curador (§4). Uma notícia de
  iminência vira, se ele aprovar, um concurso com status **Previsto**.

### 4. O que não muda

- **A curadoria humana continua sendo a porta:** nenhuma fonte publica
  concurso sozinha. Só a aprovação gera `contest.discovery.created`.
- O LexPubli descobre **concursos**; quem busca **provas** é o LexCorpus
  (ADR-0002).
- Respeito a `robots.txt`, sem contornar Turnstile ou captcha, e intervalos
  de vigilância educados (no mínimo 1 hora por página; o DOU 1 vez por dia).

### 5. A ponte com a varredura do LexCorpus

As frentes do LexPubli e a varredura do LexCorpus (ADR-0009 de lá) se
completam sem se misturar:

- o **Judiciário** do LexPubli anuncia concursos de **tribunais**, e a
  varredura do LexCorpus já terá provas de **tribunais** no acervo;
- o **Executivo** (Sefaz, Receita) faz o mesmo com a carreira **fiscal**.

A ligação continua sendo o ADR-0008 do LexCorpus: mesma banca e mesma
carreira, resposta na hora.

## Alternativas consideradas

- **Agregadores (PCI, blogs de concursos) como fonte principal:** cobrem
  tudo, mas não são fonte oficial e erram datas e números. Continuam só
  como índice (ADR-0002).
- **DJEN do CNJ para o Judiciário:** é para comunicações processuais, não
  para concursos. Não foi encontrada evidência de que os editais de concurso
  passem por ele. Pode ser reavaliado.
- **Raspar os 27 diários oficiais estaduais logo de início:** cada um tem um
  formato, e o custo de manutenção é alto. Fica para a onda C, depois de
  medir o que as ondas A e B já cobrem.
- **Fontes cadastradas só no changedetection.io:** perde poder, esfera,
  carreira e prioridade, e o cadastro fica fora do domínio do LexPubli.

## Consequências

**Positivas.**
- A descoberta cobre os quatro Poderes de forma organizada e auditável: cada
  descoberta diz de que fonte veio.
- O Executivo federal ganha a fonte mais cedo do ciclo: a **autorização**
  sai meses antes do edital. Isso dá tempo para o LexCorpus preparar o
  acervo.
- A carreira sugerida pela fonte reduz o trabalho do curador.

**Negativas / a monitorar.**
- **Volume de curadoria:** o DOU e dezenas de páginas geram muitas
  descobertas, algumas repetidas. A curadoria em lote e a fusão de
  duplicatas, que já estão no backlog, viram pré-requisito da onda B.
- **Manutenção de páginas:** sites de órgãos mudam sem aviso. O painel
  precisa mostrar as fontes que pararam de responder.
- **Recursos:** cada página vigiada custa ao changedetection. A onda B
  (cerca de 110 páginas) deve ser medida antes, na VM do ADR-0006.
- **INLABS:** as condições de acesso (cadastro, limites) precisam ser
  confirmadas antes da implementação.

## Implantação

1. Modelo `Fonte` + painel + validação de domínio oficial + testes.
2. Sincronização `Fonte` → changedetection.io (API), com o webhook atual.
3. Confirmar o acesso ao INLABS (cadastro, formato do XML) e escrever o
   `coletar_dou` com os termos versionados e testes com atos reais.
4. Onda A: conferir e ativar as cerca de 25 fontes federais.
5. Medir a onda A (descobertas por semana, duplicatas, fontes quebradas)
   antes de abrir a onda B.
