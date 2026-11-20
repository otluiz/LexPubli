<!-- Arquivo:  docs/architecture/decisions/ADR-0013-identidade-e-ciclo-de-vida-do-concurso.md
     Função:   define o que identifica um concurso antes e depois do edital,
               quando o radar junta sinais numa mesma página, e como uma
               página do radar termina, com ou sem edital. -->

# ADR-0013: Identidade e ciclo de vida do concurso

- Status: **Aceito** (19/11/2026, depois de confirmada no PNCP a premissa da D1)
- Data: 2026-11-13
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0002 (`contest_slug` nos eventos para o LexCorpus),
  ADR-0008 (radar de sinais; janela e prazo), ADR-0012 (trilhas)

## Contexto

O radar parte de um pressuposto: um órgão, um concurso. `radar.aplicar`
liga **todo** sinal solto do órgão à chamada que já existe, e o
`contest_slug` é `<órgão>_<ano>`, único.

A Polícia Civil do Acre quebrou o pressuposto em 13/11. A página do
concurso mostrava:

- 22/10/2026, banca contratada: "cargos da Polícia Civil";
- 06/11/2026, licitação da banca: "cargos de **nível superior**".

Dois problemas na mesma tela:

1. **Ordem impossível.** A contratação aparece depois do contrato. O
   contrato usa a data de assinatura; a licitação, a data de publicação no
   PNCP. São datas de naturezas diferentes, comparadas como se fossem a
   mesma.
2. **Talvez dois concursos numa página só.** Os objetos falam de recortes
   diferentes. Se forem processos distintos, o radar juntou sem perguntar.

O candidato pensa em outra coisa: um concurso é o **edital de abertura**.
Retificação, convocação, resultado e homologação citam sempre o mesmo
edital ("Edital nº 01/2026 – PCAC"). Mas o radar trabalha antes do edital,
quando esse número não existe, e o concurso pode nunca chegar a ter um.

## Decisões

### D1: A identidade tem duas fases

| Fase | Identidade | Fonte |
|---|---|---|
| Antes do edital | o **processo de contratação da banca** | número de controle do PNCP; o contrato aponta para a compra que o originou |
| Do edital em diante | o **número do edital de abertura** | cabeçalho do edital, repetido pela banca em todos os atos seguintes |

A ponte entre as fases é a banca: o edital é publicado pela banca
contratada naquele processo. Quando o edital sai, o concurso **herda** a
identidade provisória e passa a ser chamado pelo número do edital.

Sinais que não têm processo (autorização, comissão, notícia oficial)
identificam o órgão, não o concurso.

**Premissa confirmada em 19/11/2026.** O contrato do IFG com o Instituto
AOCP, consultado na API de consulta do PNCP (`/v1/contratos`), traz os dois
números:

| Campo | Valor | O que é |
|---|---|---|
| `numeroControlePNCP` | `10870883000144-2-000204/2026` | o contrato |
| `numeroControlePncpCompra` | `10870883000144-1-000061/2026` | a compra que o originou: **a identidade do processo** |
| `processo` | `23372.000722/2026-89` | o processo administrativo do órgão (texto livre, formato varia) |

A identidade usada é o `numeroControlePncpCompra` no contrato e o
`numeroControlePNCP` na própria compra (aviso, dispensa), que são o mesmo
número. O `processo` administrativo fica guardado, mas não identifica: o
formato muda de órgão para órgão.

O mesmo registro mostra o problema da D3: assinado em 21/09/2026,
publicado no PNCP em 06/10/2026. E o edital desse processo (TAE, AOCP) saiu
no DOU em 16/11/2026, 41 dias depois da publicação do contrato: é a
antecedência que o radar existe para dar.

### D2: O radar só junta automaticamente o que é do mesmo processo

O `Sinal` guarda o número do processo PNCP quando houver. `aplicar` liga um
sinal à página quando:

- o sinal é do mesmo processo de algum sinal da página; ou
- o sinal não tem processo, e o órgão tem uma única página no radar.

Fora disso o sinal fica solto e vai para um painel do admin, "Sinal de outro
processo do mesmo órgão", e quem decide é o curador: mesmo concurso ou
concurso novo. Na dúvida, a pessoa decide; o radar não chuta.

### D3: Dentro de um processo, a ordem é a do procedimento

Na linha do tempo, os documentos do mesmo processo aparecem na ordem do
procedimento (aviso ou dispensa, depois contrato), não pela data de cada
registro. Cada data diz o que é: "assinado em", "publicado no PNCP em".

### D4: A página diz quem ela é

- `ConcursoPage` ganha `processo_pncp` (preenchido pelo radar) e
  `edital_numero` (preenchido pelo curador).
- Antes do edital, o título leva o recorte quando o órgão tem mais de um
  concurso: "PCAC 2027 — nível superior". A página mostra "banca contratada
  no processo PNCP nº …".
- Depois, o título e o card mostram "Edital nº 01/2026": o mesmo número que
  o candidato vê no PDF.
- Órgão com mais de um concurso: cada página aponta para as outras ("Este
  órgão tem outro concurso no radar").
- O `contest_slug` ganha o recorte quando houver colisão
  (`pcac_2027_nivel_superior`). Ele é texto opaco nos contratos de evento
  v1, então a mudança é compatível; slug já publicado não muda.

### D5: O número do edital é sugerido pelo radar e confirmado pelo curador

Uma pista ou o changedetection que encontre "Edital nº …" do órgão gera uma
sugestão no painel. O curador confirma a qual concurso ela pertence. Ligar
um edital ao concurso errado é o erro mais caro desta ADR, justamente no
caso de um órgão com dois concursos.

### D6: Toda página do radar termina, e termina às claras

| Desfecho | O que acontece |
|---|---|
| O edital sai | `edital_numero` preenchido, status "Edital aberto". **A URL não muda.** |
| Atrasou | já existe: passada a janela, o selo vira "atrasado" (ADR-0008). |
| Não se concretizou | 12 meses depois do fim da janela sem sinal novo, ou antes por decisão do curador: status novo, **"Não chegou a edital"**. |

Uma página "Não chegou a edital" sai das listas da home e **continua no
ar**, com os documentos e a previsão que foi feita. Um sinal novo do mesmo
processo a reabre. Os 12 meses ficam em `janelas_sinais.json`, para
calibrar sem mexer em código.

Não se apaga página do radar. A credibilidade se mede pelo que o radar
acertou e pelo que errou; com essas páginas o portal pode publicar "X% das
previsões viraram edital".

## Ordem de implementação

1. ~~Confirmar no PNCP que o contrato aponta para a compra de origem~~
   (confirmado em 19/11, ver D1). Guardar o processo no `Sinal` e no
   caderno. Os cadernos já gravados não têm o campo, e a coleta não pede
   de novo um dia que já está no caderno: como preencher os antigos se
   decide nesta etapa.
2. D2 e o painel de sinais de outro processo.
3. D3: ordem por procedimento e o rótulo de cada data.
4. D4 e D5: campos, título, quadro de outros concursos, sugestão de edital.
5. D6: o status "Não chegou a edital" e a tolerância de 12 meses.

## Consequências

**Positivas.** Dois concursos do mesmo órgão deixam de virar uma página só.
A identidade da página bate com a que o candidato conhece, o edital. O
radar passa a ter histórico de acerto, que vira argumento de credibilidade.

**Negativas.** Mais decisões para a curadoria: cada processo novo de um
órgão que já tem página passa pelo painel. Sinais sem processo continuam
identificando só o órgão.
