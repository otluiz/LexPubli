# Plano — Automação de status do concurso por data

**Status:** proposto (aguarda decisão do dono do produto + alinhamento LexCorpus)
**Origem:** bug observado em 02/11/2026 — concurso Sefaz-AL 2026 aparecia em
"Inscrições abertas" na home com `inscricoes_fim = 21/10/2026` (já vencida).

## Diagnóstico

A home (`ConcursosIndexPage.GRUPOS`) agrupa concursos **pelo campo `status`**,
não pela data. O concurso continuava `edital_aberto` porque nada rebaixa o
status quando a data de inscrição vence — não há automação nem signal de
tempo. O frontend apenas reflete fielmente o `status` do banco; o bug é de
**lógica de domínio**, não de template.

## Transições que o tempo governa

Só duas transições têm uma data que as comprova objetivamente:

| De                      | Para                    | Gatilho                 |
|-------------------------|-------------------------|-------------------------|
| `edital_aberto`         | `inscricoes_encerradas` | `inscricoes_fim < hoje` |
| `inscricoes_encerradas` | `prova_realizada`       | `data_prova < hoje`     |

As demais (`prova_realizada → resultado → encerrado`) dependem de fato
externo (sai resultado, encerra), que nenhuma data prova. **A automação não
as toca** — ficam com curadoria ou sinal. Princípio: a automação só avança o
que uma data comprova; nunca adivinha, nunca retrocede.

## Desenho proposto

Management command `atualizar_status_por_data`, idempotente e conservador,
rodado por cron (como `coletar_pncp` e `processar_pistas`):

- Seleciona `edital_aberto` com `inscricoes_fim` preenchida e `< hoje`
  → `inscricoes_encerradas`.
- Seleciona `inscricoes_encerradas` com `data_prova` preenchida e `< hoje`
  → `prova_realizada`.
- `--simular` (dry-run): lista o que mudaria sem gravar.
- Loga cada transição (concurso, de→para, data que disparou).
- Só avança; data ausente = não mexe.
- Idempotente: rodar de novo não faz nada se já está no estado certo.

Agendar 1x/dia (de madrugada), junto dos outros comandos do gpu01.

## A QUESTÃO DE FRONTEIRA (decisão pendente) — ALINHAR com LexCorpus

`status` está em `CAMPOS_ATUALIZAVEIS` (eventos.py), e
`contest.discovery.updated` dispara no `page_published` (signals.py). Então
**como** a automação salva o status muda se há evento ao LexCorpus:

- **Publicar via revisão** (`save_revision().publish()`): o evento
  `contest.discovery.updated` sai — o LexCorpus é notificado de que as
  inscrições encerraram. Consistente com o Wagtail (página publicada = revisão
  publicada). PORÉM: hoje o `.updated` é emitido pela curadoria publicando à
  mão (ADR-0004, Fase 1). Um cron virar **emissor automático de eventos entre
  projetos** é comportamento novo — precisa registro no ADR-0004 e ciência do
  LexCorpus (ele vai receber updates não-humanos).

- **`save()` direto, sem publish**: a transição é interna ao LexPubli; o
  LexCorpus NÃO é notificado. Mais conservador na fronteira, mas cria
  divergência entre a página publicada e a revisão (o Wagtail trabalha com
  revisões — a página pública pode mostrar o status novo enquanto a última
  revisão mostra o antigo, ou vice-versa, dependendo de como se salva).

### Opções para decidir

1. **Emitir evento** (publicar via revisão). Registrar no ADR-0004 que o cron
   também emite `.updated`; avisar o LexCorpus. Argumento: o LexCorpus
   *deveria* saber que inscrições encerraram (pode afetar priorização de
   coleta). É a fronteira funcionando.
2. **Não emitir** (transição interna). Resolver a divergência revisão/publicado
   de forma explícita. Argumento: transição por tempo não é "novidade de
   conteúdo" que justifique notificar outro projeto.

Recomendação para discussão: **opção 1** parece mais alinhada ao espírito do
ADR-0004 (o ecossistema reage ao ciclo do concurso), desde que registrada e
alinhada. Mas é decisão do dono do produto.

## Salvaguarda de exibição (independente, baixo risco)

Enquanto a automação não existe/roda, a home pode se proteger de dado atrasado:
não listar em "Inscrições abertas" um concurso cujo `inscricoes_fim` já passou,
mesmo com `status = edital_aberto`. É um filtro na view, sem tocar status nem
fronteira. Pode entrar antes da automação como rede de segurança — ou ser
dispensada se a automação cobrir o caso. Decidir junto.

## Próximos passos

- [ ] Decisão do dono do produto: emitir evento ou não (seção Fronteira)
- [ ] Se emitir: nota no ADR-0004 + alinhar com LexCorpus
- [ ] Escrever `atualizar_status_por_data` (+ `--simular`, logs, teste)
- [ ] Agendar no cron do gpu01 (1x/dia)
- [ ] (Opcional) salvaguarda de exibição na view da home
- [ ] Corrigir o dado atual do Sefaz-AL 2026 à mão no painel (independe de tudo acima)
