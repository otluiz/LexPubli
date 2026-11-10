<!-- Arquivo:  docs/architecture/specs/SPEC-0002-home-do-lexpubli.md
     Função:   dar ao LexPubli uma porta de entrada — hoje a raiz do site é a
               lista de concursos e não existe página que explique o produto —
               e um destino para a conversão, enquanto o LexLearn não tem
               landing nem cadastro. -->

# SPEC-0002: Home page do LexPubli e captura de interesse

- Status: **Aceita**
- Data: 2026-11-10
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0005 (fronteira com o LexLearn), ADR-0006 (isolamento no
  gpu01), SPEC-0001 (retrieval), branch `feat/frontend-apelativo-lexlearn`
  (já na `main`)
- Origem do desenho: variação "03 Sinal" do protótipo feito no Lovable
  (projeto `quantumlearn-page`). O protótipo é **referência visual**, não
  código a ser importado.

## Contexto

O portal não tem home page. Medido em 10/11/2026 na `main`:

| Fato | Estado |
|---|---|
| Templates | 3 arquivos, 183 linhas no total |
| Raiz do site | `ConcursosIndexPage` (`max_count = 1`) — quem chega em `/` cai na lista |
| Modelo de home | Não existe |
| Cabeçalho | `base.html`, 26 linhas: marca em texto + lema, sem navegação |
| Tema | Só `prefers-color-scheme`; não há alternador |
| Fontes | Fraunces + Inter, já carregadas no `base.html` |
| `site.css` | 290 linhas, tokens próprios (`--noite`, `--sinal`, `--brasa`, `--sereno`) |

Quem chega pelo Google numa página de concurso é atendido. Quem ouve falar
do LexPubli e digita o endereço encontra uma lista sem explicação: não há
onde dizer o que o produto faz, nem onde converter.

**O LexLearn não tem landing nem cadastro** (verificado em 10/11/2026: existe
o painel do aplicativo, sem autenticação, em rede interna). Sem um destino,
a principal chamada da home terminaria no vazio — ou, pior, levaria um
visitante anônimo a um painel sem login. Por isso esta spec inclui a página
de captura de interesse, no próprio LexPubli.

## Objetivo

Criar a página inicial do LexPubli: uma porta de entrada que explica a
promessa — descobrir o concurso na autorização, antes do edital — com prova
concreta, e que leva a duas ações: acompanhar um concurso e registrar
interesse em estudar para ele.

**A janela "antes do edital" é o momento de conversão.** Um concurso
descoberto na autorização dá meses de preparação. Quem começa aí se prepara
melhor e é o candidato natural a virar usuário do LexLearn. A home é
desenhada em torno disso, não como folheto institucional.

## Fora do escopo

- Qualquer mudança na densidade, na ordenação ou no desempenho da lista de
  concursos. Ela continua como está.
- A landing e as telas de cadastro e login do LexLearn (v0.5). Virão depois;
  quando existirem, a página de captura passa a apontar para elas.
- Expor o LexLearn à internet. Decisão de outra ordem, que mexe no modelo de
  ameaça do ADR-0006 e na separação de VMs do ADR-0014. Merece ADR próprio.
- O design system formal. Os tokens continuam no `site.css`; a extração
  para referência compartilhada é outra spec.
- Autenticação, área logada ou cobrança no portal.
- Gamificação (v0.4).
- Link profundo por concurso para o LexLearn.
- Envio de e-mail (confirmação, boas-vindas, campanha). Esta spec só grava o
  interesse; disparo é outra spec.

## Restrições

- **Sem React, sem Tailwind, sem build de frontend.** O portal é Wagtail com
  template Django e CSS escrito à mão. O protótipo do Lovable é reimplementado,
  nunca importado.
- **Sem dependência JavaScript nova.** O alternador de tema é JS puro, e o
  formulário de captura funciona sem JavaScript.
- O `site.css` mantém os nomes de token em português já existentes. Tokens
  novos seguem a mesma convenção.
- A identidade declarada no cabeçalho do `site.css` continua valendo: a
  ousadia mora no hero; o resto fica quieto para o conteúdo respirar.
- Nenhum número na página pode ser inventado. Todo dado exibido sai do banco
  ou de uma contagem real, com a data da apuração.
- ADR-0005 continua valendo: a home fala do LexLearn, mas não consome API
  nem evento dele.
- O e-mail capturado é dado pessoal. Coleta com finalidade declarada na
  própria página, sem caixa pré-marcada, com registro de data e origem.

## Decisões

| Questão | Decisão | Razão |
|---|---|---|
| Raiz do site | `HomePage` passa a ser a raiz; a lista vai para `/concursos/`, com 301 da raiz antiga | O portal está em modo de teste e nada foi indexado. Daqui a alguns meses a mesma mudança custaria posicionamento |
| Grafismo do radar | SVG animado por CSS, com `prefers-reduced-motion` respeitado | Uma transformação CSS basta para a varredura e o pulso; é leve e entrega o "grade de radar + pulso" que o `site.css` já prometia |
| Concursos na home | Sim, os 3 mais recentes, cada um com chamada para estudar. Com menos de 3, a seção some | Prova viva de que o radar funciona, e é o principal caminho de conversão |
| Destino da conversão | Página `/estudar/` no próprio LexPubli, com captura de e-mail | O LexLearn não tem landing nem cadastro. Apontar para o painel exporia um aplicativo sem autenticação; bloquear a home adiaria o portal por causa de outro projeto |
| Memória do tema | `localStorage` | Cookie obrigaria aviso de cookies, sem ganho nenhum em troca |
| Lema no cabeçalho | Só nas páginas internas | Na home a manchete do hero já diz isso com mais força; em `/concursos/` e nas páginas de concurso, onde não há hero, ele continua explicando o produto |

## Contrato

| Peça | Onde | O que muda |
|---|---|---|
| `HomePage` | `concursos/models.py` | Novo `Page`, `max_count = 1`, `parent_page_types = ["wagtailcore.Page"]`, `subpage_types = ["concursos.ConcursosIndexPage", "concursos.EstudarPage"]` |
| `EstudarPage` | `concursos/models.py` | Novo `Page`, `max_count = 1`, servida em `/estudar/` |
| `Interesse` | `concursos/models.py` | Novo modelo: `email`, `concurso` (FK opcional), `origem` (texto curto), `criado_em`. `unique_together` em (`email`, `concurso`) |
| `ConcursosIndexPage` | `concursos/models.py` | `parent_page_types = ["concursos.HomePage"]`; conteúdo intocado |
| `home_page.html` | `concursos/templates/concursos/` | Novo template com as seções abaixo |
| `estudar_page.html` | `concursos/templates/concursos/` | Explicação do LexLearn + formulário de captura |
| `base.html` | `concursos/templates/` | Cabeçalho novo: logo em SVG, navegação, "LexLearn ↗", alternador de tema, CTA. Lema só quando não for a home |
| `site.css` | `concursos/static/concursos/` | Tokens novos, estilos do cabeçalho e das seções da home |
| `tema.js` | `concursos/static/concursos/` | Alternador de tema em JS puro, guardando em `localStorage`, com `prefers-color-scheme` como padrão |
| Migração | `concursos/migrations/` | `HomePage`, `EstudarPage`, `Interesse` e remanejamento da árvore |

### Seções da home, em ordem

1. **Hero** — sobretítulo, manchete em duas linhas (a segunda em Fraunces
   itálico, na cor sinal), subtítulo de duas linhas, CTA primário
   ("Acompanhar um concurso") e secundário ("Como funciona"). Radar em SVG
   animado à direita, com varredura e pontos captados.
2. **Como funciona** — as quatro etapas do ciclo, na ordem: autorizado,
   banca definida, edital publicado, inscrições abertas. Os nomes saem de
   `StatusConcurso`, não são escritos à mão no template.
3. **Últimos concursos descobertos** — os 3 mais recentes, cada cartão com
   órgão, etapa atual, data da descoberta e **duas ações**: acompanhar o
   concurso no portal e "Estudar para este concurso", que leva a `/estudar/`
   com o concurso no parâmetro. Com menos de 3 concursos, a seção inteira
   não é renderizada.
4. **Prova em números** — fontes monitoradas, publicações lidas na última
   varredura, concursos acompanhados, com a data da apuração ao lado.
5. **O radar por dentro** — como o sinal vira descoberta, em linguagem de
   quem estuda, não de quem programa.
6. **Chamada para o LexLearn** — reaproveita o `_chamada_lexlearn.html`
   que já existe; não duplicar. O argumento é o tempo: quem começa na
   autorização estuda meses antes dos concorrentes.
7. **Rodapé** — o aviso de fontes oficiais que já está no `base.html`.

### Página `/estudar/`

Explica o que o LexLearn faz — transforma a legislação do edital em resumo,
quiz e flashcards — e diz com franqueza que está em preparação. Formulário
com um campo de e-mail e um botão. Quando vier de um cartão de concurso, o
nome do concurso aparece na página e vai gravado junto.

Depois de enviar, confirma na própria página o que foi registrado e o que
acontece em seguida. Sem promessa de data.

## Critérios de aceite

- [ ] `HomePage` existe, é a raiz do site e tem `max_count = 1` — provado por teste
- [ ] A lista responde em `/concursos/` e a raiz antiga devolve 301 — provado por teste
- [ ] A lista de concursos renderiza o mesmo HTML de antes da mudança — provado por teste de regressão do template
- [ ] Nenhum número da home é constante no template: todos vêm do banco ou de contagem, com data de apuração — provado por leitura do template e por teste
- [ ] Com menos de 3 concursos no banco, a seção "Últimos concursos descobertos" não é renderizada — provado por teste
- [ ] As etapas da seção "Como funciona" saem de `StatusConcurso`, não de texto fixo — provado por teste
- [ ] O lema aparece em `/concursos/` e nas páginas de concurso, e não aparece na home — provado por teste
- [ ] `/estudar/` grava um `Interesse` com e-mail, concurso (quando houver) e origem — provado por teste
- [ ] O mesmo e-mail enviado duas vezes para o mesmo concurso não duplica registro, e a página responde sem erro — provado por teste
- [ ] E-mail inválido é recusado com mensagem na própria página, sem perder o concurso de origem — provado por teste
- [ ] O formulário de `/estudar/` funciona com JavaScript desligado — provado por teste de POST direto
- [ ] A finalidade da coleta está escrita na página, sem caixa pré-marcada — provado por leitura do template
- [ ] Nenhuma chamada a API ou evento do LexLearn em todo o fluxo — provado por leitura e por teste
- [ ] Em viewport de 360 px de largura, o CTA primário aparece sem rolagem — provado por teste de layout ou verificação manual registrada
- [ ] Com `prefers-reduced-motion: reduce`, o radar não anima — provado por teste ou verificação manual registrada
- [ ] Contraste de texto e de componentes passa em AA nos dois temas — provado pelo Lighthouse ou pelo axe
- [ ] Lighthouse na home: Performance ≥ 90, Acessibilidade ≥ 95, SEO = 100, no perfil móvel
- [ ] O tempo de resposta de `/concursos/` não piora — provado por medição antes e depois
- [ ] O alternador de tema funciona sem JavaScript habilitado (degrada para `prefers-color-scheme`) — provado por verificação manual registrada
- [ ] Nenhuma dependência nova em `package.json` ou `requirements.txt`
- [ ] `site.css` continua abaixo de 600 linhas
- [ ] A suíte de testes passa inteira (171 testes na `main` de 10/11)

## Riscos e perguntas em aberto

- Formulário público é alvo de robô. Sem captcha (dependência nova e atrito
  para o usuário), a defesa é campo-armadilha escondido e limite por IP.
  Vigiar a tabela `Interesse` nas primeiras semanas.
- Mover a raiz mexe na árvore de páginas do Wagtail. A migração precisa ser
  testada num banco com dados, não só vazio. Mitigação: dump do banco do
  gpu01 antes de rodar.
- A "prova em números" fica fraca enquanto houver poucos concursos
  acompanhados. Mitigação: mostrar o que é forte hoje — 180 fontes e o
  volume lido na varredura — e deixar a contagem de concursos para quando
  crescer.
- O radar é o ativo distintivo da página. Animado por CSS é barato, mas uma
  varredura mal feita pode pesar na pintura em celular antigo. Medir no
  Lighthouse móvel, não só no desktop.
- A conversão pela seção 3 depende de haver descobertas recentes. Em semana
  parada, a home perde o principal caminho de conversão. Mitigação: a seção
  6 e a página `/estudar/` continuam existindo e não dependem de volume.
- Lista de interessados sem envio de e-mail envelhece. Quanto mais tempo
  entre o cadastro e o primeiro contato, menor a conversão. A spec de
  disparo não deveria demorar.
- [ ] A página `/estudar/` pergunta mais alguma coisa além do e-mail — para
  qual concurso, qual carreira? Mais campos qualificam a lista e reduzem a
  taxa de envio.

## Histórico

| Data | Mudança |
|---|---|
| 2026-11-10 | Criada, a partir do protótipo "03 Sinal" |
| 2026-11-10 | Aceita. Seis decisões registradas. Seção de últimos concursos passa a ser caminho de conversão |
| 2026-11-10 | Verificado que o LexLearn não tem landing nem cadastro. Incluída a página `/estudar/` com captura de interesse, que elimina a dependência externa |
