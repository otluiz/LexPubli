<!-- Arquivo:  docs/architecture/decisions/ADR-0012-escopo-por-carreira.md
     Função:   troca o corte do radar de "esfera" (federal, estadual,
               distrital) para "carreira": entram a carreira fiscal
               municipal e a Rede Federal de Educação Profissional, em
               qualquer lugar do país. -->

# ADR-0012: O radar recorta por carreira, não por esfera

- Status: **Proposto** em 2026-11-12. Falta decidir D1(c), a procuradoria municipal.
- Data: 2026-11-12
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0002 (fonte oficial obrigatória; agregador só como
  índice), ADR-0005 (fronteira com o LexLearn), ADR-0007 (fontes por Poder;
  a "onda C" que adiou os municípios), ADR-0008 (radar de sinais; PNCP).

## Contexto

Hoje a descoberta automática só cobre órgãos federais, estaduais e
distritais. Concurso municipal é só contado no PNCP (`pncp.py`, "onda C"), e
o reconhecedor das pistas (`orgaos.py`) só identifica órgãos federais, TJs,
MPs e TREs. Nenhuma fonte cadastrada é municipal ou de instituição de ensino.

O corte foi por esfera para conter volume: 5.570 municípios, a maioria
publicando concurso pequeno, cada achado passando pela curadoria. Mas a
esfera não mede o que importa para o produto. Dois casos de 12/11:

- **ISS Caruaru.** Auditor e Analista Fiscal Municipal, banca IBAM,
  inscrições encerradas em 08/10, prova em 29/11/2026. É reta final, o
  público principal do LexLearn, e o radar não viu nada: município, e banca
  fora da lista de validadas.
- **Rede Federal de Educação Profissional** (IFs, CEFETs, UTFPR, Colégio
  Pedro II). Federal, mas invisível: parte das instituições faz o concurso
  com comissão própria, sem contratar banca, e aí não há contrato no PNCP;
  nenhuma página de concursos delas está cadastrada; e o reconhecedor não
  conhece as siglas. É de onde o LexLearn surgiu, e a expansão da rede está
  abrindo concursos.

O que une os dois casos é a **carreira**: candidatos que estudam a mesma
matéria e prestam concursos em série, em qualquer cidade.

## Decisões

### D1: O radar acompanha carreiras

Entram, em qualquer esfera e em todo o país:

- **(a) Trilha fiscal e controle**, em todas as esferas: auditor e analista
  fiscal, fiscal de tributos ("ISS <cidade>"), Receita e Sefaz, tribunais de
  contas (controle externo) e controladorias (controle interno). Federal e
  estadual já entravam pela esfera; a trilha passa a marcá-los, e o que
  muda é o município, que entra quando é desta trilha. Bancas e cursinhos
  apontam 2026 e 2027 como anos de concursos fiscais e de controle.
- **(b) Rede Federal de EPCT:** professor do Ensino Básico, Técnico e
  Tecnológico (EBTT) e técnico-administrativo (TAE), nas 38 instituições da
  rede e no CEFET-MG, CEFET-RJ, UTFPR e Colégio Pedro II.
- **(c) Procuradoria municipal:** *a decidir.* Estuda direito tributário e
  administrativo, e costuma pagar bem nas cidades grandes.

Continua como está o que já é coberto (federal, estadual, distrital). Os
outros concursos municipais seguem só contados.

Universidades federais (69) ficam para depois desta medição: mesma lógica da
Rede Federal, volume maior.

### D2: Cada canal reconhece a carreira do seu jeito

- **Pistas** (PCI, Gran, Estratégia): é o canal mais produtivo, porque os
  cursinhos vendem curso para exatamente esses concursos. O reconhecedor
  passa a identificar (i) as siglas da Rede Federal (IFS, IFPE, IF Baiano,
  IF Sertão-PE...) e (ii) município + termo fiscal ("ISS Caruaru", "auditor
  fiscal de Maringá"). A pista continua só disparando a busca do documento
  oficial (ADR-0002).
- **PNCP:** publicação municipal deixa de ser só contada quando o órgão ou a
  unidade compradora é fazendária ou de controle (Fazenda, Finanças,
  Receita, Controladoria) ou o objeto cita a carreira. O objeto quase nunca
  cita o cargo, então este canal pega menos que as pistas.
- **Leitura retroativa do PNCP, com caderno.** Do edital à prova são cerca
  de dois meses, mas a contratação da banca vem meses antes do edital (no
  ISS Caruaru, edital em 06/08 e prova em 29/11). Para ver os concursos
  deste ano que ainda não tiveram prova, o coletor lê para trás desde
  01/01/2026, em lotes por noite (`--desde 2026-01-01 --limite-dias 15`),
  porque o PNCP bloqueia quem pede demais. Cada dia lido vira um arquivo no
  caderno, com as publicações de concurso de todas as esferas: é o ponto
  de retomada e o material da medição, sem pedir de novo ao PNCP.
- **Fontes (onda E):** a página de concursos de cada instituição da Rede
  Federal, conferida como as demais (texto sem JavaScript, robots.txt), no
  changedetection.

### D3: Órgão municipal tem município

O `Orgao` ganha `municipio` e `codigo_ibge`. O nome no portal fica
"Prefeitura de Caruaru — PE", na mesma lógica do `nome_com_estado`.

### D4: Acervo e geração ficam do lado de lá

ISS (LC 116/2003), ITBI, IPTU, CTN e o código tributário de cada município;
Lei 8.112, Lei 11.892/2008 e LDB para a Rede Federal. Adquirir provas e
legislação é do LexCorpus; gerar questões é decisão do Administrador do
LexLearn (ADR-0005). Esta ADR só faz o portal enxergar os concursos.

## Ordem de implementação

1. **Medir antes de abrir:** caderno do PNCP desde 01/01/2026 e
   `medir_escopo`, que conta por trilha e esfera o que D1 deixaria entrar.
   Feito em 12/11; falta rodar a leitura retroativa no gpu01.
2. Reconhecedor das pistas: siglas da Rede Federal e município + termo
   fiscal; campo `municipio` no `Orgao`.
3. Onda E: as páginas de concursos da Rede Federal.
4. PNCP: municipal fazendário.

## Consequências

**Positivas.** O portal passa a ver concursos de reta final que hoje não
vê, com público grande e menos concorrido que as carreiras federais de
ponta. A Rede Federal liga o portal à origem do LexLearn.

**Negativas.** Mais trabalho de curadoria; o volume real só se sabe pela
medição do passo 1. Reconhecer município em texto livre erra mais que
reconhecer sigla de tribunal.

**Reavaliar** se a fila da curadoria passar do que uma pessoa revisa em
meia hora por dia: aí o corte aperta (por exemplo, municípios acima de um
porte) antes de qualquer outra coisa.
