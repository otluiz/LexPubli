<!-- Arquivo:  docs/architecture/specs/MODELO-spec.md
     Função:   modelo de spec (SDD) para os projetos do ecossistema Lex.
               Copie este arquivo, renomeie e preencha. -->

# Modelo de spec

A spec diz **o quê**, o que fica de fora e **como provar que ficou pronto**.
O ADR continua dizendo **por quê** uma escolha foi feita. Uma spec por
feature, com uma página, versionada ao lado do código.

| Artefato | Responde | Quando escrever | Onde fica |
|---|---|---|---|
| ADR | Por que escolhemos X entre alternativas | Decisão arquitetural relevante | `docs/architecture/decisions/NNNN-*.md` |
| Spec | O quê, fora do escopo, contrato, critérios de aceite | Antes de implementar uma feature ou mudar um contrato | `docs/architecture/specs/SPEC-NNNN-*.md` |
| Teste | Se o critério continua valendo | Junto da implementação | `tests/` |

## Ciclo de uma spec

1. Diagnóstico primeiro (grep, contagens, testes isolados). A spec só é
   escrita depois que a causa está entendida.
2. Spec em status Rascunho, com critérios de aceite que um script ou teste
   consegue verificar.
3. Se a spec exigir uma escolha arquitetural, ela vira um ADR separado e a
   spec aponta para ele.
4. A spec vira o prompt do Claude Code local: escopo, arquivos que não podem
   ser tocados e critérios.
5. O PR cita a spec. Revisar o PR é conferir cada critério, um por um.
6. Após o merge, status Implementada. Mudanças depois disso entram no
   histórico da própria spec.

---

<!-- A partir daqui começa o modelo propriamente dito. -->

<!-- Arquivo:  docs/architecture/specs/SPEC-NNNN-<slug>.md
     Função:   <uma linha: o que esta spec garante> -->

# SPEC-NNNN: `<título>`

- Status: Rascunho | Aceita | Implementada | Substituída
- Data: AAAA-MM-DD
- Autor: Prof. Othon Luiz
- Relacionados: ADR-..., SPEC-..., branch `feature/...`

## Contexto

O que foi medido, com data. Fatos, não impressões.

## Objetivo

Uma ou duas frases: o que muda para o usuário ou para o pipeline.

## Fora do escopo

- O que esta spec NÃO faz (e qual spec fará, se houver).

## Restrições

- Arquivos que não podem ser tocados.
- Operações destrutivas: dry-run por padrão, `--executar` para escrever.
- Fronteiras (ADR-0005, local-first).

## Contrato

Entradas, saídas, formatos, códigos de erro, schema versionado.

## Critérios de aceite

- [ ] `<fato mensurável>` — provado por `<comando ou teste>`

Um critério que não aponta comando ou teste não é critério. "Script criado"
e "endpoint criado" não provam nada.

## Riscos e perguntas em aberto

- `<risco>` — mitigação
- [ ] `<pergunta>` — quem decide

## Histórico

| Data | Mudança |
|---|---|
| AAAA-MM-DD | Criada |
