# Fronteiras do ecossistema Lex — resumo

Resumo das ADR-0002 e ADR-0005 do repositório LexPubli (`docs/architecture/decisions/`), com a decisão do LexStudy por cima. Em caso de dúvida, o texto da ADR manda; este resumo é para consulta rápida.

## Quem é quem

| | LexPubli | LexCorpus | LexLearn |
|---|---|---|---|
| Papel | portal público: descobre **concursos** (notícia, edital, cronograma, vagas) | descobre e coleta **documentos**: provas e gabaritos, atuais e anteriores | acervo, DNA das bancas, geração de questões (GPU), produto pago |
| Decide | se o concurso é real e relevante (curadoria humana) | o que coletar, de onde, com qual spider e quando | o que gerar, para qual concurso e em que ordem (Administrador do LexLearn) |
| Publica | páginas públicas e eventos `contest.*` | arquivos no storage e eventos `concurso.*` e `document.acquisition.*` | — |
| Nunca faz | escolher spider, baixar PDF, chamar o LexLearn | publicar para o público, julgar relevância de concurso | receber ordem do portal público |

## ADR-0002 — LexPubli × LexCorpus (aceita em 12/10/2026)

- **O LexPubli avisa, o LexCorpus decide.** Integração só por eventos; sem código ou banco compartilhado.
- **Porta 1 (humana, no LexPubli):** só concurso aprovado pela curadoria gera `contest.discovery.created`.
- **Porta 2 (política, no LexCorpus):** o operador define a política (bancas validadas — hoje Cebraspe, FGV, FCC, Cesgranrio; score mínimo; confirmação no catálogo do órgão; no máximo ~3 certames anteriores por concurso), e a política resolve os casos de rotina. O que fica fora dela vai para a fila do operador.
- **Resposta do LexCorpus:** `document.acquisition.completed | awaiting_operator | failed`, no envelope v1 do LexPubli, com `correlation_id` = `event_id` de origem. **Sem caminhos de storage** na resposta: o LexPubli só precisa saber *que* existem provas.
- Os schemas ficam em `contracts/events/v1/` no LexPubli (dono do envelope); o LexCorpus valida com uma cópia ("consumidor primeiro").
- **Agregadores (PCI etc.) são índice, nunca fonte.** Nada é publicado só com base no agregador: precisa de `fonte_url` oficial (banca, órgão, diário oficial). Não se copia texto de agregador. Respeitar robots.txt, não contornar captcha/Turnstile, limitar frequência, User-Agent identificável.

## ADR-0005 — LexPubli × LexLearn (aceita em 13/10/2026)

- **A automação existe só entre LexPubli e LexCorpus.** Nenhum contrato de evento do LexPubli tem o LexLearn como produtor ou consumidor.
- **Único ponto de contato LexPubli → LexLearn:** a pasta `/data/raw/editais/`, gravada sob autorização humana e de fonte oficial (ADR-0003). O LexPubli não publica eventos para o LexLearn, não assina nada dele e não chama a API dele.
- **Brokers separados:** a automação LexPubli ↔ LexCorpus usa o broker próprio do LexPubli. O LexPubli não tem credencial do broker do LexLearn. O LexCorpus fala com dois brokers (LexPubli para `contest.*`/`document.*`; LexLearn só para o v2.1).
- **O v2.1 (LexCorpus → LexLearn, `/data/raw/exams/`, `concurso.*`) continua automático**: alimenta o acervo e o DNA das bancas. Entrar no acervo não é decisão de geração.
- **Geração é por demanda e do Administrador do LexLearn.** A prioridade do LexPubli (Heat Engine, curadoria) serve ao portal e à ordem de coleta do LexCorpus, não à GPU. Revogados: o LexLearn assinando `contest.*` e o `study.target.ready`.
- **Convite para estudar no portal** é só um link de saída, posto pela curadoria. Do lado do LexLearn, consultar outros sistemas é "navegar sim, executar não".
- Fases revistas: (1) alvo e relacionadas, só LexPubli + LexCorpus; (2) o portal mostra quantas provas anteriores existem, a partir dos `document.acquisition.*`; (3) o Heat Engine ordena as coletas e o painel mostra "tempo até provas disponíveis".

## Decisão de 11/11/2026 — LexStudy

LexStudy é nome de produto e **módulo do LexPubli**, não quarta aplicação (ver `adr/ADR-LexStudy-modulo-do-LexPubli.md`). A integração por eventos proposta no levantamento foi recusada por contrariar a ADR-0002 e a ADR-0005. Avança só a PoC A (verticalização de edital); o verticalizado só vai ao ar **com incidência**.
