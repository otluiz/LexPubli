<!-- Arquivo:  docs/architecture/specs/SPEC-0004-boletim-semanal-por-trilha.md
     Função:   garante o boletim semanal por trilha de carreira, começando
               pela Rede Federal: gerado dos dados do radar, revisado por
               uma pessoa, enviado por e-mail e arquivado no portal. -->

# SPEC-0004: Boletim semanal por trilha

- Status: Rascunho
- Data: 2026-11-12
- Módulo: LexStudy (ADR-0011: módulo do LexPubli)
- Relacionadas: ADR-0002 (fonte oficial), ADR-0012 (trilhas de carreira),
  SPEC-0002 (captura de interesse; D6 e D7)

## 1. Problema

Os cursinhos já estão chamando para os próximos concursos de IF, com
professor conhecido, live marcada e oferta. O LexPubli não tem nada que
leve o radar até o candidato: quem não volta ao portal não fica sabendo.

A SPEC-0002 está travada pela D6 dela: a captura de e-mail não vai ao ar
sem um disparo que exista e funcione. O boletim é esse disparo.

O ativo do negócio é credibilidade. O boletim só vale se cada linha dele
for verificável.

## 2. Decisões

**D1. Um boletim por trilha, não por concurso.** Começa pela Rede Federal
de EPCT; a trilha fiscal e controle usa a mesma máquina quando a ADR-0012
for aceita. O aviso por concurso continua sendo da SPEC-0002.

**D2. Conteúdo só do banco, com link oficial em cada item.** Nenhum texto
escrito por IA, nenhum dado de agregador. Seções, nesta ordem:
1. *Provas chegando:* reta final da trilha, com a contagem de dias;
2. *Inscrições abertas:* com o prazo;
3. *Sinais novos da semana:* portaria de vagas, comissão, banca
   contratada, edital publicado.

**D3. Semana sem novidade não tem boletim.** Nada de edição de enchimento.
Silêncio também é informação, e enchimento gasta a credibilidade.

**D4. Uma pessoa aprova antes do envio.** O radar gera a edição como
rascunho; o curador revê no painel e clica em "Enviar". Sem aprovação,
nada sai.

**D5. Cada edição é uma página pública.** `/boletim/<trilha>/<ano>-<semana>/`,
com o mesmo conteúdo do e-mail. Serve de prova do que foi dito e quando, e
o Google indexa.

**D6. A edição é congelada.** O conteúdo enviado é gravado na própria
edição. Se um concurso mudar depois, a edição antiga continua mostrando o
que foi dito naquela semana.

**D7. Mesmo consentimento da SPEC-0002.** Confirmação dupla, descadastro em
um clique sem login, e a data e hora do consentimento guardadas.

**D8. Sem rastreamento.** Nenhum pixel de abertura e nenhum link
redirecionado para contar clique. Mede-se o que é do LexPubli: inscritos
confirmados e descadastros por edição.

## 3. Modelo de dados

- `Assinatura`: email, trilha, token (UUID), criado_em, confirmado_em,
  descadastrado_em. Unicidade em (email, trilha).
- `EdicaoBoletim`: trilha, ano e semana ISO (únicos juntos), conteudo
  (JSON congelado), gerada_em, aprovada_em, aprovada_por, enviada_em,
  enviados.
- A trilha de um concurso vem do órgão, por `concursos/trilhas.py`.

## 4. Escopo

Dentro:
1. Comando `gerar_boletim --trilha rede_federal`, semanal no cron, que cria
   o rascunho ou não cria nada (D3).
2. Revisão e envio pelo painel (D4), com o envio em lote pelo SMTP
   configurado.
3. Inscrição na home e na página de concurso da trilha; confirmação;
   descadastro.
4. Página pública de cada edição e do arquivo da trilha.

Fora:
- WhatsApp: depois, quando houver lista e motivo para pagar a API oficial.
- Vídeos, com ou sem avatar.
- A trilha fiscal e controle, até a ADR-0012 ser aceita.
- Segmentação, testes A/B e qualquer recurso de ferramenta de marketing.

## 5. Critérios de aceite

1. Com um concurso da Rede Federal em reta final, `gerar_boletim` cria um
   rascunho com esse concurso em "Provas chegando", com a contagem de dias
   e o link oficial.
2. Sem nada novo na semana, `gerar_boletim` não cria edição.
3. Rodar `gerar_boletim` duas vezes na mesma semana não duplica a edição.
4. Nenhum e-mail sai de edição sem `aprovada_em`.
5. Só recebe quem confirmou e não se descadastrou; cada e-mail leva o link
   de descadastro, que funciona sem login e em um clique.
6. A página pública da edição mostra o conteúdo congelado, mesmo depois de
   o concurso mudar de status.
7. Todo item do boletim tem link para fonte oficial (`dominio_oficial`); um
   item sem ele barra a geração.
8. O HTML do e-mail e da página não tem pixel nem link de rastreamento.

## 6. Riscos

**Pouco conteúdo no começo.** Hoje o radar quase não vê a Rede Federal: a
onda E e o coletor do DOU ainda não existem (ADR-0012). Até lá, o boletim
depende do que a curadoria cadastrar à mão. Mitigação: D3 evita a edição
vazia, e a medição da ADR-0012 diz quando a cobertura chega.

**Entrega de e-mail.** Domínio e remetente novos caem em spam. SPF, DKIM e
DMARC antes do primeiro envio, e um teste com provedores diferentes.

**O boletim desliza para marketing.** A oferta do LexLearn cabe numa linha
ao pé do e-mail, nunca no meio dos itens. O dia em que o boletim vender mais
do que informar, ele perde a razão de ser assinado.
