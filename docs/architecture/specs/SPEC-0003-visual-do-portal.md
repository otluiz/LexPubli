# SPEC-0003 — Visual do portal e radar vivo

- **Status:** implementada (11/11/2026)
- **Data:** 2026-11-10
- **Relacionadas:** SPEC-0002 (captura de interesse), ADR-0005 (fronteira LexPubli × LexLearn)
- **Base visual:** versão **03-sinal**, preservada em `docs/frontend/0001-frontend-radar.patch` e nas pré-visualizações `preview_claro.png`, `preview_concurso.png`, `preview_mobile.png`, `concurso_isca.png`

---

## 1. Problema

O portal funciona e é feio o suficiente para não ser levado a sério. O visual atual cumpre o básico — tipografia legível, paleta coerente, hero com radar — mas foi escrito para não atrapalhar, não para convencer. Quem chega pelo Google compara, mesmo sem querer, com o que viu em outro lugar.

A experiência com o Lovable foi útil por isso: a página gerada lá não tinha nada por trás — a lista de concursos era fictícia, não havia banco, não havia radar, não havia 180 fontes monitoradas. Mas era mais bonita. O conteúdo que importa está aqui e não se copia; a aparência está lá e migra.

Há um segundo problema, menor na aparência e maior no significado. O radar do hero gira sempre igual, independentemente do que o sistema encontrou. É enfeite. Numa página cuja promessa inteira é "nós achamos antes", um radar que não mostra o que foi achado desperdiça o melhor elemento gráfico que o projeto tem.

## 2. Decisões

### D1 — A base é a versão 03-sinal

As três versões (Vigília, Editorial, Sinal) ficam registradas em `docs/frontend/`, mas só a 03-sinal vira implementação. As outras duas não viram tema alternativo nem opção de configuração — ficam como registro do caminho percorrido.

Razão: três variantes mantidas é três vezes o custo de cada mudança futura, para um portal que tem um dono e nenhum designer.

### D2 — O radar mostra descobertas reais

Cada ponto no radar corresponde a uma `ConcursoPage` publicada. A posição no disco indica recência: quanto mais recente a descoberta, mais perto do centro. O varredor acende o ponto ao passar. Cada ponto é clicável e leva à página do concurso.

Quando não há descoberta recente, o radar gira vazio. Isso é informação correta, não falha.

Razão: ponto inventado no radar é o mesmo erro da lista fictícia do Lovable, num lugar onde dói mais — é exatamente a parte da página que afirma que o sistema encontra coisas.

### D3 — Sem JavaScript para o que é visual

Radar, animações e estados de foco são CSS. Se algum efeito exigir JavaScript para existir, o efeito é cortado, não o contrário.

Razão: a página precisa funcionar depressa, em rede ruim e em telefone modesto — que é como boa parte do público vai chegar. Página de concurso é consultada no ônibus.

### D4 — Tema claro e escuro por preferência do sistema

O portal respeita `prefers-color-scheme`. Não há botão de alternância nesta spec.

Razão: o botão exige guardar a escolha, guardar exige JavaScript, e JavaScript para trocar cor contraria D3. Se a demanda aparecer depois, entra como spec própria com a decisão tomada de forma consciente.

### D5 — Fontes auto-hospedadas

Fraunces e Inter saem do Google Fonts e passam a ser servidas pelo próprio portal, em `woff2`, com `font-display: swap`.

Razão: duas. A primeira é desempenho — some uma conexão a domínio externo no caminho crítico da primeira renderização. A segunda é que carregar fonte de terceiro envia o IP de cada visitante para esse terceiro sem que ele saiba, o que é transferência de dado pessoal a título gratuito e sem base legal clara. É evitável com meia hora de trabalho.

### D6 — Nenhum dado fictício na página

Números, contagens e exemplos vêm do banco. Se a consulta não tem resposta, o bloco não aparece — não se preenche com valor de exemplo.

Razão: o `.numeros-grade` já faz isso certo hoje (fontes totais, fontes de notícia, contagem de concursos saem do banco). A regra fica escrita para não se perder quando a página crescer.

### D7 — Cabeçalho ganha navegação

O `base.html` atual tem marca e lema, e nada mais. Passa a ter navegação mínima: início, e o link para o LexLearn com o rótulo que a SPEC-0002 D5 definiu.

Razão: sem navegação, quem entra numa página de concurso pelo Google não tem como descobrir que existe um portal em volta.

## 3. Escopo

Dentro:

1. Aplicar a 03-sinal em `site.css`, `base.html`, `concursos_index_page.html` e `concurso_page.html`.
2. Radar vivo conforme D2, alimentado pelos concursos mais recentes já carregados pela home.
3. Cabeçalho com navegação (D7).
4. Fontes auto-hospedadas (D5).
5. Tema claro conforme `prefers-color-scheme` (D4).
6. Revisão de acessibilidade: contraste, foco visível, `prefers-reduced-motion`.

Fora:

- Formulário de interesse e tudo que a SPEC-0002 trata.
- Botão de alternância de tema.
- Página de administração do portal, área de aluno, gamificação.
- Qualquer coisa no LexLearn.

## 4. Critérios de aceite

1. O HTML servido não faz requisição a domínio de terceiros — nem fonte, nem script, nem folha de estilo.
2. Com três concursos publicados, o radar mostra três pontos, cada um ligado à sua página.
3. Com zero concursos publicados, a home renderiza sem erro e o radar gira vazio.
4. Com `prefers-reduced-motion: reduce`, nenhuma animação roda; o radar aparece estático com os pontos visíveis.
5. Com `prefers-color-scheme: light`, a página é legível e o contraste de texto sobre fundo atinge AA (4,5:1 para texto corrido).
6. Navegação por teclado percorre cabeçalho, pontos do radar e cartões, com foco sempre visível.
7. Em viewport de 360px de largura, nada transborda horizontalmente.
8. O teste de regressão de comentários de template segue verde, e a suíte inteira passa.

## 5. Riscos

**O radar com poucos pontos parece vazio e fraco.** Hoje são duas descobertas (Acre 2027, Seap 2027). Um radar com dois pontos pode comunicar "esse sistema não acha nada". Mitigação: a definição de recência precisa ser generosa — últimos noventa dias, não últimos sete — e o `.numeros-grade` logo abaixo mostra os números grandes (180 fontes, 10.529 publicações varridas), que é onde está a escala de verdade.

**Trabalho visual não termina.** Sempre dá para melhorar mais um pouco, e isso compete com funcionalidade que ainda não existe. Mitigação: os critérios de aceite acima são a definição de pronto. Atendidos, a spec fecha, mesmo que dê para melhorar.

**Regressão na página de concurso.** É a página que o Google indexa e a que mais importa. Mitigação: os testes existentes cobrem conteúdo e presença dos blocos; conferir `preview_concurso.png` antes de fechar.

## 6. Notas de implementação

- **Radar em SVG, não em CSS puro.** A CSP não aceita `style=""`, então a posição de cada ponto vai em atributos do SVG (`cx`, `cy`). O momento em que o varredor acende cada ponto vem de 24 classes `.setor-N` (15° cada) no `site.css`; o ângulo sai do slug e é estável entre visitas. Lógica em `concursos/radar_vivo.py`.
- **Recência:** 90 dias desde a primeira publicação. Concurso mais antigo sai do radar e continua na lista.
- **Rótulo** só no ponto mais recente (sigla do órgão + ano), na primeira posição em volta dele que não cubra outro ponto.
- **CTA do hero:** "Ver os concursos", âncora para a lista. A 03-sinal tinha "Acompanhar um concurso", mas acompanhar depende da SPEC-0002, que está travada pela D6 dela.
- **`--verde` do tema claro** passou de `#1f8a5b` (4,1:1) para `#187a4f` (5,1:1) para atingir AA no selo.
- **Critério 7** não tem teste automático (precisa de navegador). Conferido no Chrome a 360px: `scrollWidth` = 360 na home e na página de concurso.
- Testes: `tests/test_visual.py`, um por critério.

