# ADR-0011 — LexStudy é módulo do LexPubli, não serviço separado

- **Status:** aceito
- **Data:** 2026-11-11
- **Substitui:** nada
- **Relacionadas:** ADR-0002 (fronteira LexPubli × LexCorpus), ADR-0005 (fronteira LexPubli × LexLearn), ADR-0014 (virtualização do gpu01), SPEC-0002 (captura de interesse)
- **Estudo de origem:** `LexStudy_levantamento_specs_adrs_v0.1.0`, de 11/11/2026

> Numeração: no repositório LexPubli a última ADR na `main` é a ADR-0010; o próximo número livre é **ADR-0011**. Conferir com `ls docs/architecture/decisions/ | tail -3` antes de commitar.

---

## Contexto

Em 11/11/2026 chegou um levantamento técnico propondo o **LexStudy**: uma quarta aplicação do ecossistema, responsável pela jornada do candidato — seleção de concurso, verticalização de edital, planejamento, cronograma, acompanhamento e relacionamento comercial. O pacote trazia três ADRs e quatro specs.

A oportunidade de produto é real e foi bem identificada. O gatilho foi observar que os concorrentes — Estratégia Concursos, mentorias de nicho — usam o **edital verticalizado gratuito** como principal mecanismo de captação: entregam o conteúdo programático reorganizado em troca de nome, e-mail e telefone.

O que estava em questão não era se a funcionalidade vale, e sim onde ela mora.

## Decisões

### D1 — LexStudy é nome de produto e módulo, não aplicação

As funcionalidades propostas para o LexStudy entram como módulo do **LexPubli**. Não se cria quarta aplicação, quarto banco, quarto deploy.

Razão: o custo escondido da separação é a identidade compartilhada. Duas aplicações com os mesmos usuários exigem provedor de identidade, propagação de autorização e reconciliação de sessão — semanas de trabalho que não produzem nada visível para o candidato.

O LexPubli já tem o que o módulo precisa: os editais que o radar encontra, o tráfego orgânico do Google, as páginas de concurso indexadas e, pela SPEC-0002, a captura de interesse.

### D2 — A parte de integração do levantamento não vale

A ADR-LEXSTUDY-0002 propõe que o LexPubli publique eventos de concurso/edital para consumo do LexStudy e do LexCorpus. Isso contradiz decisão já tomada: a ADR-0005 estabeleceu que entre LexPubli e LexLearn não há evento nem API, apenas link; a ADR-0002 definiu o canal LexPubli → LexCorpus.

O levantamento foi escrito sem acesso às ADRs do ecossistema — a seção "Relacionadas" das três ADRs propostas cita decisões por tema, sem número nem título, o que indica suposição e não leitura.

Consequência: nada da ADR-LEXSTUDY-0002 é aprovado. Se um dia a separação acontecer, o desenho de integração recomeça a partir das ADRs reais.

### D3 — Avança apenas a PoC A

Do levantamento inteiro, entra na fila só a prova de conceito de **verticalização**: componente que recebe um edital em PDF e produz JSON canônico versionado, com conferência humana e rastreabilidade de origem (página e posição no documento).

O projeto `edital-verticalizado` (licença MIT) serve como referência técnica, sujeito a D5.

A PoC B (planejamento, ciclos, calendário) fica fora. Planejador de estudo sem acervo para estudar é casa sem terreno.

### D4 — Verticalizado puro não vai ao ar

O edital verticalizado sozinho é commodity: o maior concorrente do mercado já entrega de graça. Publicar o mesmo artefato significa entrar em último lugar numa disputa onde somos o menor.

O que o módulo publica é o verticalizado **com incidência**: cada tópico do edital acompanhado de quanto foi efetivamente cobrado nas provas anteriores daquela banca, com link para cada prova. Isso exige acervo processado — exatamente o que o LexCorpus adquire e o LexLearn processa — e é o que o concorrente não tem.

Enquanto a incidência não existir, o verticalizado não é publicado como material de captação.

### D5 — Nenhum código de terceiro sem auditoria

A ADR-LEXSTUDY-0003 sobrevive inteira e é incorporada: licença do repositório e das dependências verificadas no momento da incorporação, não confiadas a um documento; avisos de copyright preservados; inventário de componentes mantido.

Em particular: **Track Concursos** tem licença proprietária que proíbe derivação e uso comercial — não se reutiliza nada, nem adaptado. **Edital-Esquematizado** não tem licença identificada, o que não concede permissão alguma — serve como referência de fluxo observada, não como fonte de código.

### D6 — O estudo fica arquivado com ressalva

O pacote vai para `docs/architecture/studies/lexstudy-2026-11/`, com um cabeçalho no README registrando que D1 e D2 desta ADR o superam em parte.

Razão: estudo descartado some; estudo arquivado com a ressalva no topo evita que alguém volte a encontrá-lo daqui a seis meses e o trate como aprovado.

## Consequências

**Positivas.** Nenhuma superfície operacional nova. O módulo nasce com tráfego e com editais, em vez de precisar conquistar os dois. A funcionalidade mais valiosa do levantamento (verticalização) avança isolada, sem arrastar o resto.

**Negativas.** O LexPubli acumula responsabilidade: era radar público, passa a ter também jornada do candidato. Existe risco real de virar aplicação-canivete. A reavaliação abaixo é a válvula.

**Custo evitado.** Identidade compartilhada, quarto pipeline de deploy, quarta VM no desenho da ADR-0014, e a sincronização de progresso entre dois bancos — que a SPEC-LEXSTUDY-004 descreve corretamente como problema de consistência eventual, com deduplicação e ordenação. Esse é trabalho de equipe, não de pessoa só.

## Condições para reavaliar

Reabrir a decisão quando **duas** destas forem verdadeiras:

1. Existe receita recorrente vinda do módulo;
2. O módulo tem usuários autenticados em número que torne a identidade compartilhada inevitável de qualquer forma;
3. O ciclo de deploy do LexPubli passa a ser freado pelo módulo, ou o contrário;
4. Há mais de uma pessoa trabalhando no código.

Uma só não basta. A primeira sozinha é tentação; a quarta sozinha é organograma.

## Alternativas consideradas

**Criar o LexStudy como serviço agora**, conforme o levantamento. Rejeitada por D1 — o custo de identidade e operação não se paga antes de haver receita.

**Colocar o módulo no LexLearn.** Rejeitada: o LexLearn não tem tráfego de entrada nem cadastro, e é ele que está atrás do perímetro com o banco e a GPU (ADR-0014). Captação é superfície pública; não se coloca superfície pública no núcleo.

**Engavetar inteiro.** Rejeitada: a verticalização com incidência é diferencial defensável e o acervo para produzi-la já está sendo construído por outro motivo.
