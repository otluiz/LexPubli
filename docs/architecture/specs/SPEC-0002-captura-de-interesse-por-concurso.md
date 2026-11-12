# SPEC-0002 — Captura de interesse por concurso

- **Status:** proposta
- **Data:** 2026-11-10
- **Substitui:** a versão anterior da SPEC-0002 ("Home do LexPubli" / "Caminho de conversão do portal"), que está na `main` e deve ser removida no mesmo commit.
- **Relacionadas:** ADR-0005 (fronteira LexPubli × LexLearn), ADR-0013_LL (itinerário de estudos a partir do edital), SPEC-0003 (visual da home, a escrever)

---

## 1. Problema

O portal já traz gente de fora. Quem busca "concurso Sefaz AL 2026" no Google cai numa `ConcursoPage` específica, lê o que o radar encontrou, e vai embora. Não fica nada: nem para o visitante, que precisa voltar manualmente para saber se o edital saiu, nem para o projeto, que não sabe quem esteve ali nem por qual concurso.

O bloco de chamada atual (`_chamada_lexlearn.html`) tenta resolver isso com um botão "Começar a estudar" apontando para o LexLearn. Isso não funciona hoje por um motivo simples: o LexLearn não tem cadastro nem página de entrada. Quem clica cai num painel que não o recebe. A promessa do botão é maior do que o produto do outro lado consegue cumprir.

## 2. Correção de rumo registrada

A versão anterior desta spec propunha criar uma `EstudarPage` nova, a partir da leitura equivocada de que o portal não tinha home. O portal tem home: é a `ConcursosIndexPage`, servida por `concursos_index_page.html`.

Fica o registro, porque o erro é do tipo que se repete: **ausência de arquivo com o nome esperado não é ausência da função.**

## 3. Decisões

### D1 — Nenhuma página nova

O formulário de interesse vive dentro da `ConcursoPage`, num bloco ao fim do conteúdo. Não se cria `EstudarPage` nem `AcompanharPage`.

Razão: a página de detalhes do concurso já existe e já é onde a pessoa está quando o interesse aparece. Uma página intermediária só adiciona um clique entre a vontade e a ação.

### D2 — A promessa é aviso, não estudo

O bloco pede e-mail para **avisar quando aquele concurso mudar de status** — edital publicado, inscrições abertas, data de prova confirmada.

Razão: é o que o portal já sabe fazer. O radar monitora 180 fontes e detecta mudança; avisar por e-mail é consequência direta disso, não produto novo. "Estudar" é uma decisão do aluno e exige um produto que ainda não recebe ninguém.

### D3 — Segunda intenção, opcional e menor

Abaixo do campo de e-mail, uma caixa de seleção desmarcada por padrão: *"Quando o LexLearn abrir para este concurso, quero saber."*

Razão: é instrumento de medida antes de ser funil. A proporção entre quem deixa e-mail e quem marca a caixa é a demanda real pelo LexLearn, medida com gente que chegou sozinha atrás de um concurso específico — o público mais qualificado que o projeto tem. Essa proporção decide se a landing do LexLearn vale o esforço, e a lista de espera já sai pronta.

### D4 — Nada nos cartões da lista

Os cartões da home não ganham botão nem formulário. O convite aparece só na página do concurso.

Razão: a home é um índice. Dezesseis chamadas para ação numa lista não convertem dezesseis vezes mais; poluem.

### D5 — O botão global muda de rótulo

Em `_chamada_lexlearn.html`, "Começar a estudar" passa a "Conhecer o LexLearn", e o bloco descreve o produto em vez de convidar a usá-lo.

Razão: enquanto não houver cadastro do outro lado, o rótulo deve descrever o que o clique faz de verdade. O link permanece — quem quiser ver, vê.

### D6 — Captura não vai ao ar sem disparo

O formulário só é publicado quando o envio do aviso existir e estiver testado. Até lá, o código pode estar na `main`, mas atrás de uma chave de funcionalidade desligada.

Razão: coletar e-mail prometendo aviso e não avisar é pior do que não coletar. Queima a lista e a confiança de uma vez só, e as duas são difíceis de reconstruir.

### D7 — Consentimento com confirmação dupla

O e-mail só entra na lista depois que a pessoa confirma por link enviado. O registro guarda data e hora do consentimento, e todo aviso leva link de descadastro em um clique, sem login.

Razão: base legal da LGPD é o consentimento (art. 7º, I), e consentimento precisa ser demonstrável. Confirmação dupla também protege contra inscrição de terceiros em endereço alheio.

---

## 4. Modelo de dados

Novo modelo em `concursos/models.py`:

| campo | tipo | observação |
|---|---|---|
| `email` | `EmailField` | normalizado em minúsculas |
| `concurso` | `FK(ConcursoPage, on_delete=CASCADE)` | `related_name="interesses"` |
| `intencao` | `CharField(choices)` | `AVISO` ou `AVISO_E_ESTUDO` |
| `token` | `UUIDField` | usado na confirmação e no descadastro |
| `criado_em` | `DateTimeField(auto_now_add=True)` | |
| `confirmado_em` | `DateTimeField(null=True)` | nulo = ainda não confirmado |
| `descadastrado_em` | `DateTimeField(null=True)` | nulo = ativo |

Restrição de unicidade em `(email, concurso)`. Reinscrição no mesmo concurso atualiza o registro existente em vez de criar outro.

Registros não confirmados há mais de 7 dias são removidos por rotina de limpeza — não viram lista.

## 5. Escopo

Dentro:

1. Modelo `Interesse` e migração.
2. Bloco de formulário na `ConcursoPage`, atrás da chave `LEXPUBLI_CAPTURA_INTERESSE`.
3. Fluxo de confirmação: e-mail com link, página de confirmação, página de descadastro.
4. Detecção de mudança de status da `ConcursoPage` e disparo do aviso aos confirmados.
5. Proteção contra robô: campo-armadilha oculto e limite por IP. Sem serviço externo — vale a premissa local-first.
6. Rótulo do bloco global (D5).
7. Remoção da versão anterior desta spec.

Fora:

- Visual da home, cabeçalho, radar vivo, alternância de tema — **SPEC-0003**.
- Landing e cadastro do LexLearn — depende do número que D3 produzir.
- Envio em massa, segmentação, qualquer coisa parecida com ferramenta de marketing.
- Painel de métricas. Por ora, consulta no `shell` resolve.

## 6. Critérios de aceite

1. Visitante deixa e-mail na página de um concurso, recebe link, confirma, e o registro aparece com `confirmado_em` preenchido.
2. Mudança de status do concurso dispara aviso a todos os confirmados daquele concurso, e a ninguém mais.
3. Link de descadastro funciona sem login e em um clique.
4. Mesmo e-mail no mesmo concurso duas vezes não cria dois registros.
5. Envio com o campo-armadilha preenchido é descartado em silêncio.
6. Com a chave desligada, nenhum vestígio do formulário aparece no HTML servido.
7. Nenhum comentário de template ou referência a ADR vaza para a página — o teste de regressão de 10/11 cobre isso e deve continuar verde.
8. A `ConcursosIndexPage` segue sem chamada para ação nos cartões.

## 7. Questão em aberto para a implementação

Detectar mudança de status exige saber o estado anterior. A `ConcursoPage` guarda o status atual, não o histórico. Duas saídas, a decidir na implementação:

- sinal `pre_save` comparando com o valor em banco antes de gravar;
- campo `status_notificado` na própria página, atualizado depois do disparo.

A segunda é mais feia e mais robusta: sobrevive a falha de envio no meio do caminho, porque o que marca o aviso como entregue é o registro, não o momento da gravação.

## 8. Riscos

**O número de D3 vem baixo.** É informação, não fracasso — e custa pouco para obter. Melhor descobrir com cem visitantes reais do que depois de construir a landing.

**Entrega de e-mail.** Domínio novo, remetente novo, e-mail transacional: há chance de cair em caixa de spam e nunca se saber. Mitigação: SPF, DKIM e DMARC configurados antes de ligar a chave, e um teste real com endereços de provedores diferentes.

**A chave fica desligada por tempo indeterminado** e o código apodrece sem uso. Mitigação: D6 define a ordem — disparo primeiro, captura depois; não se faz a captura antes.
