<!-- Arquivo:  docs/architecture/decisions/ADR-0015-lexstudy-vitrine-antes-do-edital.md
     Função:   define o LexStudy como ferramenta de captação na janela entre o
               sinal do radar e o edital: o edital anterior verticalizado, com
               incidência, na página do concurso, e as chamadas para o
               LexLearn. Diz o que fica no LexPubli, o que fica no LexLearn e
               de que decisões isso depende.
     Não confundir com a ADR-0015_LL (qualidade de questão gerada), do LexLearn. -->

# ADR-0015: LexStudy como vitrine antes do edital

- Status: **Proposto**
- Data: 2026-11-27
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0005 (fronteira com o LexLearn), ADR-0008 (radar de
  sinais), ADR-0010 (dados do acervo no portal, em estudo), ADR-0011
  (LexStudy é módulo do LexPubli; **revisa a D3 e a D4**), ADR-0014 (último concurso
  na página; **depende da D2**), ADR-0012_LL (isolamento do LexLearn),
  ADR-0013_LL (itinerário de estudos; **§5, o plano antes do edital**)

## Contexto

O radar (ADR-0008) encontra o concurso **antes do edital**: autorização,
licitação da banca, comissão formada. Nessa janela o candidato quer saber duas
coisas: se vale estudar (salário e vagas) e **o que estudar**. A primeira
pergunta é respondida pelo bloco "Último concurso" (ADR-0014). A segunda ainda
não tem resposta.

O dono do produto propôs (27/11) usar o LexStudy como **ferramenta de
marketing** nessa janela. A ideia é verticalizar o **edital do concurso
anterior**, que o LexCorpus coleta, mostrar o que estudar, e espalhar chamadas
para o candidato experimentar o gerador de questões do LexLearn. Assim o
candidato **consome o produto antes de o edital sair**, que é quando nenhum
concorrente tem o que oferecer além de notícia.

A maior parte das peças já está decidida ou proposta, em ADRs separados:

| Peça | Onde está | Situação |
|---|---|---|
| Achar o concurso antes do edital | ADR-0008 | aceito |
| Trazer o edital do certame anterior | ADR-0014 D2 (pedido ao LexCorpus) | proposto, falta o aceite do LexCorpus |
| Verticalizar o edital (PDF → JSON canônico) | ADR-0011 D3, PoC A | aceito, no backlog |
| Só publicar o verticalizado com incidência | ADR-0011 D4 | aceito |
| Plano de estudos a partir do edital anterior | ADR-0013_LL §5 | proposto, decisão do Administrador |
| Mostrar no portal o que vem do acervo | ADR-0010 | em estudo |

Este ADR junta essas peças num objetivo só e resolve o que nenhuma delas
resolve sozinha: **o que aparece no portal, o que fica no LexLearn e como as
duas partes se ligam sem cruzar a fronteira do ADR-0005.**

## Decisões

### D1: O que é o produto antecipado

Na página de um concurso **previsto** (sem edital), o módulo LexStudy mostra:

1. o **edital anterior verticalizado**: disciplinas e tópicos do conteúdo
   programático, com o quadro de provas (questões e peso por disciplina);
2. a **incidência** de cada tópico nas provas anteriores da banca, com link
   para as provas (ADR-0011 D4);
3. um **esqueleto de roteiro**: os tópicos em ordem de prioridade (peso no
   edital × incidência), **sem calendário e sem personalização**;
4. as **chamadas para o LexLearn**, em cada bloco: "monte seu plano",
   "resolva questões deste tópico no estilo da banca".

O objetivo é **captação**: trazer o candidato para o LexLearn meses antes do
edital, e não substituir o LexLearn.

### D2: O que fica em cada projeto

| Parte | Projeto | Por quê |
|---|---|---|
| Verticalizado do edital anterior, incidência agregada e esqueleto do roteiro | **LexPubli** (LexStudy) | é conteúdo público de captação e precisa de SEO |
| Plano personalizado (horas por semana, data da prova, "estudar hoje", replanejamento) | **LexLearn** (ADR-0013_LL) | é produto, precisa de usuário autenticado e do DNA |
| Gerador de questões | **LexLearn** | é a função-fim dele (ADR-0012_LL) |

- As chamadas são **link de saída** com o `contest_slug` na URL, como o botão
  "Começar a estudar". O ADR-0005 já permite isso, e **nenhum canal novo**
  LexPubli ↔ LexLearn é aberto.
- O LexPubli **não guarda** o progresso nem o plano do candidato. Assim não
  nasce a identidade compartilhada que o ADR-0011 D1 evitou.

### D3: Revisão do ADR-0011 D3

O ADR-0011 D3 deixou o planejamento fora com o argumento de que "planejador de
estudo sem acervo é casa sem terreno". Quando o LexCorpus coletou o certame
anterior, **o terreno existe**: há edital e há provas.

A revisão é estreita:

- **Entra no LexPubli** só o **esqueleto público** do roteiro (D1, item 3),
  derivado do verticalizado e da incidência.
- **A PoC B continua fora do LexPubli.** Ela previa planejamento, ciclos e
  calendário. O plano personalizado mora no LexLearn, onde o ADR-0013_LL já o
  descreve.

### D4: "Experimentar o gerador" sem abrir a geração

O LexLearn não gera nada por ordem de fora: geração é decisão do Administrador
(ADR-0012_LL). Há duas formas de deixar o candidato experimentar:

- **(a) Amostras pré-geradas.** Para cada concurso-alvo que entra na vitrine,
  o Administrador decide gerar um lote pequeno de questões por disciplina.
  Elas ficam no LexLearn, abertas sem cadastro ou com cadastro leve, e a
  chamada do portal leva até elas.
  - Cabe nas regras de hoje.
  - O custo de GPU é fixo por concurso, e não cresce com o tráfego.
  - O Administrador revisa o lote antes de abrir (ADR-0015_LL, qualidade de
    questão gerada).
- **(b) Geração pelo próprio visitante.** Cada visitante pede questões e a
  GPU gera na hora.
  - Revoga parte do ADR-0012_LL, decisão que é do Administrador do LexLearn.
  - O custo de GPU cresce com o tráfego do portal.
  - É uma superfície de abuso exposta à internet.

**Proposta: (a).** A (b) só entra com um ADR do lado do LexLearn.

As amostras ficam **no LexLearn**, e não na página do LexPubli. Mostrar a
questão no portal seria conteúdo do LexLearn cruzando para o lado exposto
(ADR-0010). Também esbarraria no parecer jurídico sobre republicação, que
continua pendente no backlog.

### D5: Regras, para não vender o edital antigo como o novo

As mesmas regras do ADR-0014 D4, aplicadas ao conteúdo:

1. **Sempre o ano.** "Baseado no edital de 2022". O nome nunca é só "Edital
   verticalizado".
2. **Sempre o aviso e o documento.** "O novo edital pode mudar disciplinas e
   pesos", e o link do edital anterior oficial.
3. **Mesmo órgão e mesmo cargo.** Se o cargo mudou, o bloco diz isso, ou não
   aparece.
4. **Sem edital anterior oficial, não há vitrine.** Nada de edital de outro
   órgão "parecido", nem de agregador.
5. **Quando o edital novo sai**, a vitrine é refeita e mostra **o que mudou**:
   disciplinas que entraram, que saíram e que mudaram de peso. Esse é o
   segundo gancho de captação, e o mesmo do ADR-0013_LL §5 ("o estudante vê o
   que mudou").

### D6: Dependências e ordem

A vitrine só vai ao ar quando estas quatro estiverem prontas:

1. **Edital anterior**: aceite do ADR-0014 D2, revisado em 27/11, pelo
   LexCorpus. O LexCorpus informa o link oficial (`previous_edital_url`, no
   `document.acquisition.completed` v1.1) e o curador confere e grava o PDF
   pelo ADR-0003. Sem esse aceite, o curador acha o edital à mão, como no
   próprio ADR-0014.
2. **Verticalização**: PoC A do backlog (ADR-0011 D3).
3. **Incidência no portal**: a incidência sai do DNA das bancas, que é do
   LexLearn. Exibi-la no LexPubli depende da via do **ADR-0010**
   (B-triangulada: o LexLearn empurra um resumo ao LexCorpus e o portal lê o
   LexCorpus). **É o gargalo deste ADR**, e o ADR-0010 deve subir de
   prioridade se este for aceito.
4. **Destino das chamadas**: aceite do ADR-0013_LL (§5 em diante) e das
   amostras da D4 pelo Administrador do LexLearn. As amostras abertas da D8
   precisam de uma rota pública no LexLearn, e o ADR-0007_LL registra que a
   autenticação e a checagem de papel **ainda não estão implementadas**. Ou
   a autenticação vem antes, ou a rota pública fica limitada às amostras e é
   decidida à parte pelo Administrador.

A peça 3 **não bloqueia a janela pré-edital**: a D7 abre essa exceção. As
peças 1, 2 e 4 continuam obrigatórias.

As decisões D7 a D9 respondem às perguntas que a primeira versão deste ADR
deixou em aberto. Foram tomadas pelo dono do produto em 27/11/2026.

### D7: Antes do edital, a vitrine pode ir ao ar sem incidência

**Revisa o ADR-0011 D4**, só para a janela pré-edital.

- Enquanto o concurso estiver previsto, a vitrine vai ao ar com o **edital
  anterior verticalizado, o esqueleto do roteiro e as chamadas**, mesmo sem
  incidência. As regras da D5 valem inteiras: o ano, o aviso e o link oficial.
- **Por quê:** antes do edital, o verticalizado do edital **anterior** não é
  commodity, porque o concorrente costuma verticalizar o edital novo, depois
  que ele sai. Esperar o ADR-0010 seria perder a janela que dá sentido a
  este ADR.
- Sem incidência, o esqueleto do roteiro ordena os tópicos **só pelo peso no
  edital**. A página diz isso.
- A incidência entra na vitrine assim que o ADR-0010 permitir exibi-la.
- **Quando o edital novo sai, volta a valer o ADR-0011 D4:** o verticalizado
  do edital novo só é publicado com incidência.

### D8: Algumas amostras abertas, e depois conta no LexLearn

- Em cada disciplina, **algumas questões de amostra ficam abertas, sem
  cadastro**, no LexLearn (D4 a).
- **Para continuar**, o candidato cria uma conta no LexLearn. É o `/cadastro`
  dos protótipos do Lovable (`quantumlearn-page`), que já leva a ele.
- O lead nasce **no LexLearn**. O LexPubli continua sem guardar identidade
  nem progresso do candidato (D2), e a captura de interesse por concurso
  (SPEC-0002) segue como está.
- Quantas questões ficam abertas, e a passagem da conta gratuita para a
  assinatura, são decisões comerciais do LexLearn, fora deste ADR.

### D9: Começa só pelos concursos de prioridade alta do radar

- Entram na vitrine os concursos previstos que têm **prioridade alta no
  radar** (ADR-0008) **e** edital anterior oficial (D5.4).
- **Por quê:** cada concurso custa curadoria, para conferir o edital
  anterior, e um lote de amostras geradas. Começar pelos que mais atraem
  testa a vitrine com custo controlado.
- Ampliar para mais concursos é decisão a tomar **depois de medir** os
  resultados (cliques nas chamadas, contas criadas a partir da vitrine).

## Consequências

**Positivas.**
- O portal passa a entregar valor **antes** do edital, quando a concorrência
  só tem notícia.
- O candidato chega ao LexLearn com concurso e cargo definidos, que é o
  onboarding do ADR-0013_LL.
- Liga peças já decididas sem abrir canal novo entre LexPubli e LexLearn.

**Negativas / a monitorar.**
- Depende de quatro decisões em três projetos (D6), duas delas fora do
  LexPubli. Isso dá muito alinhamento para uma pessoa só.
- O LexPubli acumula mais uma responsabilidade, e o risco de
  aplicação-canivete do ADR-0011 cresce. As condições de reavaliação de lá
  continuam valendo.
- Se o edital novo mudar muito, o candidato pode se sentir enganado. As
  regras da D5 seguram isso e não podem sair da página.

## Alternativas consideradas

- **Esperar o edital.** Sem risco de prometer o que o edital novo não traz,
  mas perde a janela em que a vitrine é diferencial. Rejeitada.
- **LexStudy como aplicação separada, dona do roteiro.** Recusada pelo
  ADR-0011 D1 pelo custo de identidade e de operação, e nada mudou desde
  então.
- **Roteiro personalizado inteiro no LexPubli.** Duplicaria o ADR-0013_LL e
  obrigaria o portal a guardar o plano do candidato. Rejeitada pela D2.
- **Questões de amostra na própria página do LexPubli.** Seria conteúdo do
  LexLearn no lado exposto, e depende do parecer jurídico. Rejeitada pela D4.

## Decisão

As perguntas do dono do produto estão respondidas (D7 a D9, 27/11/2026). O
ADR continua **Proposto** até o alinhamento da D6.1 com o LexCorpus e da D6.4
com o Administrador do LexLearn. Depois do aceite: registrar no backlog as
peças da D6 e revisar a §1.1 do `ARQUITETURA-DA-SUITE.md`.
