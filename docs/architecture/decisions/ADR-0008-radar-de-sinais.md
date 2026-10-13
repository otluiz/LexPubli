<!-- Arquivo:  docs/architecture/decisions/ADR-0008-radar-de-sinais.md
     Função:   registra o radar de sinais de concurso futuro: o que conta
               como sinal (orçamento, autorização, comissão, banca
               contratada), como os boatos dos sites de concursos são
               usados só como pista, e como um sinal verificado vira uma
               chamada no portal. -->

# ADR-0008: Radar de sinais de concurso futuro

- Status: **Proposto**
- Data: 2026-10-13
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0002 (fonte oficial obrigatória; agregador só como
  índice), ADR-0004 (concurso-alvo; status Previsto e Autorizado), ADR-0007
  (fontes por Poder; §3a, notícias oficiais).

## Contexto

O dono do produto observou (13/10):

- **A previsão orçamentária** de um órgão pode antecipar um concurso.
- **Os sites de concursos e os cursinhos** começam a "vender" um concurso
  muito antes do edital: anunciam o certame e vendem assinaturas antecipadas,
  apoiados em algum movimento do órgão, real ou não.
- O LexPubli deve **varrer também esses sites**, **conferir a veracidade**
  no que é oficial e, confirmada a informação, **fazer a chamada** no portal.

Hoje o LexPubli só conhece **concursos** (ConcursoPage), alimentados por
Descobertas de fontes oficiais (ADR-0007). Um concurso futuro não tem edital,
banca nem vagas: o que existe são **sinais**, de força muito diferente. Uma
comissão designada em portaria é quase certeza; uma postagem de cursinho
sobre "concurso previsto", não.

## Decisão

### 1. O sinal vira cadastro, e tem força

O LexPubli ganha o cadastro **Sinal**: órgão, tipo, data, o que diz, a URL
de onde veio e a **evidência oficial** (a URL do documento oficial que o
comprova). Os tipos formam uma escada, do mais fraco ao mais forte:

| Força | Tipo de sinal | Onde a evidência oficial costuma estar |
|---|---|---|
| 0 | **Boato**: site de concursos ou cursinho anuncia | nenhuma, até ser verificado |
| 1 | **Pedido de autorização** feito pelo órgão | notícia do órgão; ofício citado em ato oficial |
| 2 | **Previsão orçamentária**: provimento de cargos no projeto de lei do orçamento (PLOA, Anexo V na União) ou na LDO/LOA estadual | site do orçamento federal ou estadual |
| 3 | **Orçamento aprovado** com provimento (LOA) | Diário Oficial |
| 4 | **Autorização** do concurso (na União, portaria do MGI) | DOU (ADR-0007 §2) |
| 5 | **Comissão do concurso** designada | portaria no diário ou boletim do órgão; notícia (ADR-0007 §3a) |
| 6 | **Banca contratada**: dispensa ou contrato com a banca | PNCP (Portal Nacional de Contratações Públicas, API pública); diário |
| 7 | **Edital publicado** | vira concurso com edital, o fluxo de hoje |

A força é do **tipo** de sinal; o curador não a inventa. Um concurso futuro
mostra o sinal mais forte já verificado.

### 2. Sites de concursos e cursinhos: pista, nunca fonte

A regra do ADR-0002 não muda: **agregador é índice**. No radar ele tem um
papel claro:

- os sites de concursos entram como **fontes de pista**: pelo feed RSS
  quando houver, ou pela listagem de notícias; sempre com respeito ao
  `robots.txt`, sem contornar Turnstile ou captcha;
- cada pista vira um **Sinal de força 0 (boato)**, que **não é publicado**;
- o curador (ou a busca automática, item 3) procura a **evidência
  oficial**. Achou: o sinal sobe para a força do documento achado, com a URL
  oficial. Não achou em um prazo (ex.: 30 dias): o sinal é **descartado**,
  com o motivo registrado;
- do site de concursos guardam-se só o título, o link e a data, para
  auditoria. O texto deles não é copiado nem republicado.

### 3. Sinais com fonte estruturada, coletados direto

Alguns sinais têm fonte oficial **estruturada**, e não precisam de pista:

- **Banca contratada (força 6):** o PNCP tem API pública de contratações. A
  busca é pelo objeto ("concurso público", "processo seletivo") e pelos CNPJs
  das bancas validadas. É o sinal mais forte antes do edital e o mais fácil
  de automatizar. **É a primeira coleta a fazer.**
- **Autorização (força 4):** as portarias do MGI no DOU (o `coletar_dou` do
  ADR-0007, que espera a conta no INLABS).
- **Previsão orçamentária (força 2):** o Anexo V do PLOA e da LOA da União
  lista o provimento autorizado por órgão. É uma vez por ano (PLOA em
  agosto, LOA na aprovação): uma planilha, lida e comparada com a do ano
  anterior.

Indicadores para avaliar depois, por serem mais fracos ou mais trabalhosos:
projetos de lei que **criam cargos** (dados abertos da Câmara e do Senado);
**vacância** e aposentadorias (Painel Estatístico de Pessoal da União);
acórdãos do TCU que mandam **substituir terceirizados** por concursados;
LDO e LOA **estaduais** (onda C do ADR-0007).

### 4. A chamada no portal

- Um sinal **verificado** (força 1 ou mais, com evidência oficial) pode virar
  uma **chamada**: a página do concurso com status **Previsto** (ou
  **Autorizado**, na força 4), com a **linha do tempo dos sinais** e o link
  de cada evidência oficial.
- A página separa o que é **oficial** do que é **boato** sem citar o
  cursinho: "o órgão designou a comissão em 02/10 (portaria nº …)", e não
  "fulano disse que vai ter concurso". Esse é o argumento de venda: **o
  LexPubli confere**.
- Cada chamada leva a **chamada ao LexLearn** ("comece a estudar antes do
  edital"), que já existe em todas as páginas.
- A curadoria continua sendo a porta: **nenhum sinal se publica sozinho**,
  nem os coletados direto (item 3).

### 5. O que não muda

- O `contest.discovery.created` para o LexCorpus continua saindo só na
  aprovação de um **concurso** (ADR-0002, ADR-0004). O sinal não é evento
  do contrato. Se um dia o LexCorpus quiser começar a varredura por carreira
  ao ver um sinal forte, é decisão de outro ADR, com o consumidor primeiro.
- O LexPubli não fala com o LexLearn (ADR-0005); a chamada é só um link.

## Alternativas consideradas

- **Publicar o que os sites de concursos publicam, com a fonte citada:**
  rápido, mas é exatamente o que o mercado já faz, e repete o erro deles
  quando o boato não se confirma. Rejeitada: o diferencial é conferir.
- **Ignorar sites de concursos:** perde-se a pista mais rápida. Muitas vezes
  eles leem uma notícia do órgão antes de nós. Rejeitada: pista sim, fonte não.
- **Força calculada por modelo (texto livre):** opaca e difícil de auditar.
  A escada por tipo de documento é simples e explicável ao assinante.

## Consequências

**Positivas.**
- O portal passa a anunciar concursos semanas ou meses antes do edital, com
  prova oficial: argumento de marketing e de venda do LexLearn.
- Os boatos dos sites de concursos viram trabalho de verificação, não
  conteúdo.

**Negativas / a monitorar.**
- Mais trabalho de curadoria: o volume de pistas precisa ser medido, e o
  descarte por prazo evita fila infinita.
- Os sites de concursos mudam de estrutura e de regras de acesso; alguns
  bloqueiam robôs. Respeitar o `robots.txt` pode deixar sites de fora.
- Revisão jurídica: citar o órgão e o documento oficial é seguro; a página
  nunca atribui um boato a um site concorrente.

## Implantação (depois do aceite)

1. Modelo **Sinal** (tipo e força, órgão, URLs de origem e de evidência,
   status a verificar/verificado/descartado, prazo) e o painel do curador;
   a página do concurso Previsto ganha a linha do tempo dos sinais.
2. **Coletor do PNCP** (banca contratada): API pública, CNPJs das bancas
   validadas e termos do objeto; cada contratação vira Sinal de força 6, a
   verificar.
3. **Pistas dos sites de concursos:** cadastro como `Fonte` de um tipo
   próprio (`pista`), sem domínio oficial exigido, só RSS ou listagem,
   `robots.txt` conferido; cada aviso vira Sinal de força 0.
4. **Anexo V do PLOA/LOA:** leitura anual da planilha, comparada com o ano
   anterior.
5. Medir depois de 30 dias: pistas recebidas, verificadas e descartadas;
   antecedência média entre o primeiro sinal verificado e o edital.
