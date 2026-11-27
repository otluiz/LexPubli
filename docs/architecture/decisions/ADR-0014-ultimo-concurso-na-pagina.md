<!-- Arquivo:  docs/architecture/decisions/ADR-0014-ultimo-concurso-na-pagina.md
     Função:   define como a página do concurso mostra o salário, as vagas e
               a banca do último concurso do mesmo órgão e cargo, de quem é
               cada dado, e as regras para não vender previsão como fato.
     Não confundir com a ADR-0014_LL (VMs no gpu01), do LexLearn. -->

# ADR-0014: Último concurso na página

- Status: **Proposto**
- Data: 2026-11-22
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0002 (fronteira LexPubli × LexCorpus; fatos de concurso
  são livres), ADR-0003 (editais no storage), ADR-0010 (dados do acervo no
  portal, em estudo), ADR-0013 (identidade do concurso), ADR-0015 (LexStudy
  como vitrine antes do edital; motivou a revisão da D2 em 27/11),
  ADR-0012_LL (isolamento do LexLearn)

## Contexto

Antes do edital, a página do concurso não tem o que mais atrai o candidato:
quanto paga. A chamada da ANPD, em 22/11, mostrava:

- o radar (nota 6 de 7, licitação da banca para 50 cargos de Especialista
  em Regulação de Proteção de Dados);
- "Cargos, vagas e salários ainda não foram divulgados: saem no edital."

É verdade, mas o candidato quer uma ordem de grandeza para decidir se vale
estudar. Ela existe, na maioria dos casos, no **edital do último concurso**
do mesmo órgão e cargo. O mesmo edital traz o conteúdo programático, que é a
outra pergunta do candidato: o que estudar.

Três projetos tocam nisso, e a ADR-0002 já diz quem faz o quê: o LexPubli
cuida dos **concursos** (fatos: órgão, banca, vagas, salário, datas), o
LexCorpus dos **documentos** (provas e gabaritos, atuais e anteriores), e o
LexLearn do que se extrai do conteúdo (ADR-0010).

## Decisões

### D1: Cada dado tem um dono

| O que a página mostra | Dono | Como chega |
|---|---|---|
| O link oficial do edital anterior | **LexCorpus** (acha, porque já está na página do certame) | informado junto com as provas do certame anterior (D2) |
| O PDF do edital anterior em `/data/raw/editais/` | **LexPubli** (o curador confere e grava) | ADR-0003, sob autorização humana |
| Ano, banca, cargo, salário inicial e vagas do concurso anterior | **LexPubli** (é fato de concurso) | o curador lê no edital e preenche (D3) |
| Disciplinas cobradas | **LexLearn** (extração do edital) | fora desta ADR: depende da ADR-0010 |

### D2: O pedido ao LexCorpus

Quando o LexCorpus coleta um certame anterior (`relation: previous`), ele já
está na página da banca onde fica o edital de abertura. O pedido é
**informar o link oficial do edital de abertura** desse certame no
`document.acquisition.completed`, num campo opcional novo,
`previous_edital_url`.

**Revisado em 27/11/2026** (alinhamento do ADR-0015). A primeira versão
pedia ao LexCorpus que baixasse o PDF e o contasse com um papel novo,
`edital`, em `files`. Foi trocada pelo link por dois motivos:

- **Não era compatível com o contrato v1**, ao contrário do que esta D2
  dizia. O objeto `files` tem `additionalProperties: false` e só aceita
  `prova`, `gabarito_preliminar` e `gabarito_definitivo`. Um evento com
  `edital` seria recusado na validação, dos dois lados.
- **Guardar o PDF esbarrava em fronteiras.** Em `/data/raw/exams/`, o
  LexLearn ingeriria editais sozinho, contra o ADR-0012_LL. Em
  `/data/raw/editais/`, o LexCorpus passaria a escrever onde hoje só o
  LexPubli escreve, contra o ADR-0003. Com o link, o curador confere o
  edital e o grava pelo ADR-0003, como já faz, e nenhuma fronteira muda.

Como fica:

- O campo `previous_edital_url` entra no `document.acquisition.completed`
  **v1.1**, como opcional, só nos eventos com `relation: previous`. É uma
  URI oficial (banca ou órgão, nunca agregador).
- **Consumidor primeiro:** o LexPubli aceita o campo no schema antes de o
  LexCorpus passar a enviá-lo. A cópia em `LexCorpus/schema/lexpubli/v1/`
  acompanha.
- O LexCorpus **não baixa** o edital. O `RE_DESCARTAR` do `heuristics.py`
  continua descartando o PDF, e só o link é guardado.
- Vale para os certames anteriores que ele já coleta (no máximo ~3 por
  concurso, pela política da Porta 2). A página usa só o mais recente.
- Precisa do aceite do parceiro do LexCorpus. Sem ele, o resto desta ADR
  funciona com o curador achando o edital por conta própria.
- Quando o link chega, o concurso aparece no painel "Edital anterior para
  conferir" (D3). O curador abre o link, confere órgão e cargo, e só então
  grava o PDF em `/data/raw/editais/`.

### D3: O bloco "Último concurso"

`ConcursoPage` ganha um registro do concurso anterior, preenchido pelo
curador: ano, banca, cargo, salário inicial, vagas, o link do edital
(documento oficial, como todo link do radar) e a data em que foi conferido.
Quando o LexCorpus avisar que há edital anterior (D2), o concurso aparece num
painel do admin, "Edital anterior para conferir".

O bloco fica acima de "Cargos" e só aparece enquanto o concurso novo não tem
cargos cadastrados. Saindo o edital novo, os números dele mandam e o bloco
sai da página.

### D4: Regras, para não vender previsão como fato

1. **O valor é o do edital antigo, com o ano.** "Salário inicial no edital
   de 2022: R$ X." Sem correção pela inflação, sem estimativa do valor novo.
2. **Sempre o aviso e o documento.** "O novo edital pode trazer outros
   valores e outro número de vagas", e o link do edital antigo.
3. **O cargo tem que ser o mesmo.** Se o cargo mudou de nome ou de carreira
   entre um concurso e outro, o curador registra o cargo como estava no
   edital antigo, e o bloco diz isso.
4. **Sem edital anterior oficial, o bloco não aparece.** Nada de valor de
   agregador, de notícia ou de "estimativa do mercado".

### D5: Carreira nova, sem concurso anterior

Quando o órgão nunca fez concurso para aquele cargo, o salário pode estar
na **lei que criou a carreira**. O curador pode registrar a lei como fonte,
com as mesmas regras da D4: "Remuneração inicial prevista na Lei nº …", com
o link para o texto oficial. A chamada da ANPD pode ser um desses casos, e é
o curador quem confere, não o radar.

### D6: Disciplinas ficam de fora

O conteúdo programático está no mesmo PDF, mas extraí-lo e cruzá-lo com o
acervo é trabalho do LexLearn, e o LexPubli não lê o LexLearn (ADR-0005). O
bloco não mostra disciplinas até a ADR-0010 ser decidida. Linkar o PDF do
edital antigo já dá ao candidato o conteúdo programático na fonte.

## Ordem de implementação

1. D3 e D4 com preenchimento manual: o modelo, o bloco na página e as
   regras. Não depende do LexCorpus.
2. D5: a lei como fonte alternativa.
3. D2: alinhar com o parceiro do LexCorpus o papel `edital`; depois, o
   painel "Edital anterior para conferir".
4. Futuro: extrair do PDF os campos da D3 como sugestão. O curador confere
   antes de publicar, sempre.

## Consequências

**Positivas.** A página do concurso antes do edital passa a responder a
pergunta que decide se o candidato vai estudar, com documento oficial. O
link do edital antigo leva o conteúdo programático junto. É conteúdo que
agregador nenhum entrega com essa disciplina de fonte, e reforça a
credibilidade em vez de gastá-la.

**Negativas.** Mais trabalho de curadoria: cada concurso no radar pede um
edital antigo conferido à mão até a extração existir. Valor de concurso
antigo pode desanimar ou animar demais o candidato; o aviso da D4 é o que
segura isso, e ele não pode sair da página.
