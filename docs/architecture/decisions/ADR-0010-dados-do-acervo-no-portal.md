<!-- Arquivo:  docs/architecture/decisions/ADR-0010-dados-do-acervo-no-portal.md
     Função:   estuda como o portal público (LexPubli) pode exibir dados
               vivos do acervo (provas disponíveis, cobertura de estudo,
               roteiro) sem o LexLearn alcançá-lo — preservando o isolamento
               do ADR-0005. NÃO decide; registra o mapa dono-do-dado e as
               opções para o dono do produto maturar e alinhar com o
               LexCorpus. -->

# ADR-0010: Dados do acervo no portal público (em estudo)

- Status: **Em estudo** desde 2026-11-02 (Prof. Othon Luiz). NÃO decidido.
  Depende de alinhamento com o parceiro do LexCorpus e de confirmar que não
  fere o isolamento do ADR-0005.
- Data: 2026-11-02
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0005 (LexPubli NÃO chama o LexLearn; único contato é a
  pasta /data/raw/editais), ADR-0002/0004 (fronteira e eventos
  LexPubli↔LexCorpus), ADR-0003 (editais pela pasta), ADR-0006 (isolamento;
  princípio do PULL pelo lado protegido). Backlog: "Página do concurso mostra
  o acervo", itens 3 e 6 de 02/11.

## Contexto

O dono do produto quer que a **página pública do concurso** (LexPubli) mostre
**dados vivos** do que o ecossistema tem para aquele concurso — não só um link
de saída. Exemplos: "12 provas anteriores disponíveis", "disciplinas do edital
já cobertas", um "roteiro de estudos". Isso enriquece a página (conversão,
SEO) em vez de apenas mandar o visitante para o LexLearn.

Restrição dura (ADR-0005): o **LexPubli é o projeto exposto à internet**; o
**LexLearn guarda o banco e, no futuro, os clientes pagantes**. Por isso o
LexLearn **não alcança o LexPubli**, e o LexPubli **não chama o LexLearn**
(só deposita editais na pasta). Decisão do dono do produto (02/11): **não
abrir um canal LexLearn→LexPubli**; achar solução que preserve o isolamento.

## O mapa que decide tudo: quem é o dono do dado

| O que o portal quer mostrar      | Dado necessário            | Dono natural |
|----------------------------------|----------------------------|--------------|
| "N provas anteriores disponíveis"| provas/gabaritos adquiridos| **LexCorpus**|
| "disciplinas do edital cobertas" | disciplinas extraídas do edital | **LexLearn** |
| "roteiro de estudos"             | roteiro montado do acervo  | **LexLearn** |

O LexPubli já conversa com o LexCorpus (bidirecional, ADR-0002/0004). Não
conversa com o LexLearn (ADR-0005). Logo: o que o **LexCorpus sabe**, o portal
pode obter limpo; o que só o **LexLearn sabe**, não — sem um novo caminho.

## Opções em estudo

### A — Portal só convida; o dado vive no LexLearn
O roteiro e o inventário são TELAS do LexLearn, alcançadas por link do
LexPubli com o `contest_slug` na URL (como o botão "Começar a estudar", em
nova aba). O LexPubli nunca lê nada; o LexLearn monta tudo com o que tem.
- (+) Isolamento perfeito; zero dado cruzando; alinhado aos papéis.
- (−) O portal não mostra dado vivo — só encaminha. Não enriquece a página
  pública. (Rejeitada pelo dono do produto em 02/11 por isso.)

### B — LexCorpus como fonte do que o portal mostra
O portal obtém do **LexCorpus** (não do LexLearn) o que existe para o
concurso, pelo canal que já existe.
- (+) Resolve LIMPO a linha "provas disponíveis" — é conhecimento do
  LexCorpus. Enriquece a página. Não toca o LexLearn.
- (−) NÃO cobre "disciplinas cobertas" nem "roteiro": isso é estado do
  LexLearn, que o LexCorpus não conhece. B pura entrega só metade.

### B-triangulada — LexLearn empurra estado ao LexCorpus; portal lê o LexCorpus
Para cobrir a metade do LexLearn sem o portal tocá-lo: o **LexLearn publica,
por iniciativa própria e para o LexCorpus** (push do lado protegido, nunca
pull do exposto — princípio do ADR-0006), um resumo por concurso, ex.:
"cobertura de estudo = pronta|parcial|ausente", "disciplinas = [...]". O
LexCorpus agrega ao que já sabe de provas. O LexPubli consulta **só o
LexCorpus**.
- (+) O portal nunca toca o LexLearn; o LexLearn nunca é alcançado (ele
  empurra quando quer); o LexCorpus vira o hub de estado do ecossistema —
  papel coerente com o que já exerce.
- (−) Exige um canal NOVO LexLearn→LexCorpus (toca a fronteira ADR-0002).
  Mais seguro que LexLearn→LexPubli (o LexCorpus não é o exposto), mas ainda
  é decisão de arquitetura, com schema de evento a desenhar e alinhamento com
  o parceiro do LexCorpus. Cuidado para o LexCorpus não virar um espelho do
  banco do LexLearn (expor só o mínimo: status de cobertura, não conteúdo).

## Encaminhamento (sem decidir)

1. **Avançar já, sem fronteira nova:** a linha "provas disponíveis" via
   LexCorpus (opção B, parte limpa) — já é o item de backlog "Página do
   concurso mostra o acervo". Não depende deste ADR.
2. **Maturar:** B-triangulada para "disciplinas/roteiro". Pontos a decidir
   com o parceiro do LexCorpus:
   - o LexLearn topa empurrar estado de cobertura ao LexCorpus?
   - qual o mínimo a expor (status de cobertura, nunca conteúdo de estudo)?
   - schema do evento LexLearn→LexCorpus; em qual broker; permissões.
3. **Roteiro de estudos como feature:** segue sendo função-fim do LexLearn
   (gerar o roteiro). Este ADR trata só de COMO o portal exibiria um reflexo
   dele, não de construí-lo.

## Decisão

PENDENTE. Nada implementado. Rever quando o dono do produto e o parceiro do
LexCorpus avaliarem a B-triangulada.
