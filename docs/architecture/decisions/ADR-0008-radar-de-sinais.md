<!-- Arquivo:  docs/architecture/decisions/ADR-0008-radar-de-sinais.md
     Função:   registra o radar de sinais de concurso futuro: os sinais
               oficiais (orçamento, autorização, comissão, licitação e
               contratação da banca), a pontuação e a janela de tempo até o
               edital, o papel dos sites de concursos (só gatilho de busca) e
               a chamada no portal. -->

# ADR-0008: Radar de sinais de concurso futuro

- Status: **Aceito** em 2026-10-13 pelo dono do produto, com a opção (b) do
  §5: o radar publica sozinho a partir da autorização (força 4). Revisto no
  mesmo dia com as regras de tempo do dono do produto.
- Data: 2026-10-13
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0002 (fonte oficial obrigatória; agregador só como
  índice), ADR-0004 (concurso-alvo; status Previsto e Autorizado), ADR-0007
  (fontes por Poder; §3a, notícias oficiais).

## Contexto

O dono do produto observou (13/10):

- **A previsão orçamentária** de um órgão pode antecipar um concurso.
- **Os sites de concursos e os cursinhos** começam a "vender" um concurso
  muito antes do edital, com assinaturas antecipadas, apoiados em algum
  movimento do órgão. São um bom sinal, mas **especulam muito**.
- O LexPubli deve buscar a **documentação oficial**, dar uma **pontuação** e
  **decidir por conta própria**, sem herdar a especulação de ninguém.
- **O tempo importa**, e a experiência do mercado dá as janelas:
  - um concurso é lançado, em média, **2 meses** depois da autorização; uma
    autorização que não vira edital em 2 a 3 meses já está atrasada;
  - autorização dada **perto do fim do ano** costuma virar edital só
    **depois do Carnaval**: 3 a 5 meses depois;
  - a **contratação da banca** antecede o edital em **3 a 4 meses**, nunca
    de imediato;
  - antes da contratação houve a **licitação** (ou o aviso de contratação
    direta), que já é um forte indício.

Hoje o LexPubli só conhece **concursos** (ConcursoPage), alimentados por
Descobertas de fontes oficiais (ADR-0007). Um concurso futuro não tem edital,
banca nem vagas: o que existe são **sinais**, de força e prazo diferentes.

## Decisão

### 1. O sinal oficial vira cadastro, com força e janela

O LexPubli ganha o cadastro **Sinal**: órgão, tipo, data do documento, o que
diz e a **URL do documento oficial** (domínio oficial obrigatório, a mesma
regra do ADR-0002). Sem documento oficial, não há Sinal.

Cada tipo tem uma **força** e uma **janela típica até o edital**, contada da
data do documento:

| Força | Tipo de sinal (documento oficial) | Janela típica até o edital |
|---|---|---|
| 1 | **Pedido de autorização** feito pelo órgão | sem janela: pode não sair |
| 2 | **Previsão orçamentária**: provimento no PLOA (Anexo V, na União) ou na LDO/LOA estadual | no exercício seguinte |
| 3 | **Orçamento aprovado** com provimento (LOA) | no exercício |
| 4 | **Autorização** do concurso (na União, portaria do MGI no DOU) | **2 a 3 meses**; se a autorização sai de outubro a dezembro, **3 a 5 meses** (depois do Carnaval) |
| 5 | **Comissão do concurso** designada | reforça a autorização; usa a janela dela |
| 6 | **Licitação ou aviso de contratação direta** da banca (PNCP; diário) | contratação a seguir, e o edital **3 a 4 meses** depois dela |
| 7 | **Banca contratada**: contrato ou extrato publicado (PNCP; diário) | **3 a 4 meses** |
| 8 | **Edital publicado** | vira concurso com edital, o fluxo de hoje |

As janelas ficam num **arquivo versionado**, e não no código, porque vão ser
calibradas com o que medirmos (item 6).

### 2. Pontuação e previsão, calculadas e explicáveis

Para cada órgão com sinais, o radar calcula:

- **a pontuação:** a força do sinal oficial mais forte;
- **a previsão do edital:** a janela desse sinal, com a regra do fim do ano;
- **o prazo:** "no prazo" enquanto a janela não venceu; **"atrasado"** quando
  venceu sem edital. Atrasado **rebaixa** a chamada no portal (a página diz
  que o prazo usual passou), mas não apaga o sinal: concurso atrasado ainda
  acontece.

Nada aqui é modelo opaco: o assinante vê qual documento sustenta a nota e
qual janela vale.

### 3. Sites de concursos: só disparam a busca

Eles especulam muito. Por isso:

- uma menção num site de concursos ou cursinho **não é sinal e não pontua**;
- ela só **dispara a busca** pela documentação oficial daquele órgão
  (notícias do órgão, PNCP, DOU e diários). Achou documento: nasce um Sinal
  oficial, com a força do documento. Não achou: a pista morre sozinha, sem ir
  para a fila de ninguém;
- os sites entram pelo feed RSS quando houver, ou pela listagem de notícias,
  com respeito ao `robots.txt` e sem contornar Turnstile ou captcha;
- deles guardam-se só o título, o link e a data, para auditoria. O texto
  não é copiado nem republicado.

### 4. Sinais com fonte estruturada, coletados direto

- **Licitação e contratação da banca (forças 6 e 7):** o PNCP tem API pública
  de contratações. A busca é pelo objeto ("concurso público", "processo
  seletivo") e pelos CNPJs das bancas validadas. Muitas bancas são
  contratadas por dispensa (instituição de ensino e pesquisa), e o aviso de
  contratação direta também sai no PNCP antes do contrato. **É a primeira
  coleta a fazer.**
- **Autorização (força 4):** as portarias do MGI no DOU (o `coletar_dou` do
  ADR-0007, que espera a conta no INLABS).
- **Previsão orçamentária (força 2):** o Anexo V do PLOA e da LOA da União,
  uma vez por ano, comparado com o ano anterior.
- **Comissão designada (força 5):** as notícias oficiais (ADR-0007 §3a) e os
  diários.

Para avaliar depois: projetos de lei que **criam cargos** (dados abertos da
Câmara e do Senado), **vacância** (Painel Estatístico de Pessoal), acórdãos
do TCU sobre **terceirizados**, LDO e LOA **estaduais** (onda C).

### 5. A chamada no portal

- Um órgão com sinal oficial vira uma **chamada**: a página do concurso com
  status **Previsto** (ou **Autorizado**, da força 4 em diante), com a
  pontuação, a **previsão do edital**, a **linha do tempo dos sinais** e o
  link de cada documento oficial.
- A página diz o que é oficial ("comissão designada em 02/10, portaria nº
  …") e nunca atribui um boato a um site concorrente. O argumento de venda é
  **o LexPubli confere**.
- Toda chamada leva a chamada ao LexLearn ("comece antes do edital").
- **Quem publica (decidido no aceite, opção b):** o radar calcula a
  pontuação e a previsão sozinho e **publica sozinho a chamada a partir da
  força 4** (autorização), sempre com o documento oficial. O curador revisa
  depois e pode despublicar. Abaixo da força 4, a chamada só sai pelo
  curador. É a exceção à regra do ADR-0007 §4, e vale só para a chamada de
  concurso Previsto ou Autorizado: o `contest.discovery.created` continua
  saindo só da aprovação do curador (§7).

### 6. Medir e calibrar

O radar registra, para cada concurso que chega a edital, a data do primeiro
sinal de cada tipo. Com isso as janelas do item 1 deixam de ser experiência
de mercado e passam a ser medidas, por esfera e por Poder.

### 7. O que não muda

- O `contest.discovery.created` para o LexCorpus continua saindo só na
  aprovação de um **concurso** (ADR-0002, ADR-0004). O sinal não é evento
  do contrato. Começar a varredura do LexCorpus a partir de um sinal forte é
  decisão de outro ADR, com o consumidor primeiro.
- O LexPubli não fala com o LexLearn (ADR-0005); a chamada é só um link.

## Alternativas consideradas

- **Publicar o que os sites de concursos publicam, com a fonte citada:** é o
  que o mercado já faz, e repete o erro dele quando a especulação não se
  confirma. Rejeitada: o diferencial é conferir.
- **Ignorar os sites de concursos:** perde-se a pista mais rápida. Rejeitada:
  eles disparam a busca, sem pontuar.
- **Pontuação por modelo (texto livre):** opaca e difícil de explicar ao
  assinante. A escada por tipo de documento, com janela, é simples e
  auditável.

## Consequências

**Positivas.**
- O portal anuncia concursos meses antes do edital, com prova oficial e
  previsão de data: argumento de marketing e de venda do LexLearn.
- A especulação dos sites de concursos vira busca, não conteúdo.

**Negativas / a monitorar.**
- As janelas vêm da experiência; até a medição (item 6), a previsão pode
  errar, sobretudo em órgãos estaduais e municipais.
- O PNCP depende de os órgãos publicarem lá; estados e municípios atrasam.
- Os sites de concursos mudam de estrutura e de regras de acesso; alguns
  bloqueiam robôs.
- Revisão jurídica: citar o órgão e o documento oficial é seguro; a página
  nunca atribui especulação a um concorrente.

## Implantação (depois do aceite)

1. Modelo **Sinal** (tipo, força, órgão, data e URL do documento oficial),
   as janelas num arquivo versionado, o cálculo de pontuação, previsão e
   prazo; o painel do curador.
2. **Coletor do PNCP** (licitação, aviso de contratação direta e contrato
   com as bancas validadas).
3. A página do concurso **Previsto**: pontuação, previsão do edital, linha
   do tempo dos sinais.
4. **Gatilho dos sites de concursos:** pistas por RSS ou listagem, que só
   disparam a busca oficial.
5. **Anexo V do PLOA/LOA** (anual) e o `coletar_dou` (com o INLABS).
6. A medição do item 6.
