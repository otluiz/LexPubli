<!-- Arquivo:  docs/architecture/decisions/ADR-0006-isolamento-fisico-no-gpu01.md
     Função:   registra como o LexPubli roda no lexlearn-gpu01 até o
               lançamento, isolado do LexLearn: VM própria, NVMe dedicado em
               passthrough e rede própria (VLAN) no MikroTik. -->

# ADR-0006: Isolamento físico do LexPubli no gpu01 (até o lançamento)

- Status: **Proposto**
- Data: 2026-10-13
- Autor: Prof. Othon Luiz
- Relacionados: ADR-0001 (plataforma; hospedagem em aberto), ADR-0003
  (editais), ADR-0005 (fronteira com o LexLearn; broker próprio, §2a);
  LexLearn ADR-0009 (arquitetura distribuída), ADR-0010 (perímetro
  MikroTik), ADR-0011 (uma fila por ambiente) e ADR-0012 (isolamento do
  LexLearn).

## Contexto

O ADR-0005 tirou o LexPubli de todos os caminhos lógicos até o LexLearn:
sem eventos, sem API, sem broker. O único ponto de contato ficou a pasta
`/data/raw/editais/`. Falta o isolamento **físico**, porque:

- o LexPubli é o único projeto **exposto à internet** (portal público,
  monitor de fontes que visita sites de terceiros);
- o LexLearn guarda o banco, o DNA das bancas e, no futuro, os dados dos
  clientes pagantes.

Decisão do dono do produto (13/10): **até o lançamento**, o LexPubli fica
no `lexlearn-gpu01`, com um **NVMe novo dedicado** e uma **rede própria
(VLAN) no MikroTik**. Uma máquina separada fica para depois do lançamento.

### O que foi medido no gpu01 (13/10, só leitura)

| Item | Estado |
|---|---|
| CPU / RAM | Xeon E5-2695 v4 (18c/36t), 62 GiB (2 em uso) |
| Disco | 1 NVMe (Kingston NV3 1 TB) com SO, Docker e dados do LexLearn |
| Placa | Machinist X99-MR9A-PRO. O único M.2 NVMe está ocupado |
| PCIe | Duas portas da CPU **livres** (`00:01.0` e `00:03.0`), cada uma no **próprio grupo IOMMU** (31 e 34). Uma porta do chipset livre (`00:1c.0`, grupo 41) |
| Virtualização | `/dev/kvm` presente, IOMMU ativo (48 grupos). libvirt **não** instalado |
| Rede | Uma placa (`enp6s0`, Realtek 1 GbE), `172.16.10.40/24`, rota default `172.16.10.1` |
| Docker | Sem `userns-remap` |
| Perímetro (ADR-0010) | MikroTik hEX lite, RouterOS 6.49, 5 portas 10/100; segmento `172.16.10.0/24` atrás de um switch |

### Por que só um disco novo não basta

Com o LexPubli no mesmo Docker do host, um disco separado isola **dados** e
**I/O**: o portal não enche o disco do LexLearn. Mas o kernel e o daemon do
Docker continuam **comuns**. Quem escapa de um container é root no host e
lê todos os discos. Como o LexPubli é o projeto exposto, esse é o risco que
importa.

## Decisão

### 1. Uma VM KVM só para o LexPubli

- **Kernel e Docker próprios.** Um escape de container do LexPubli fica
  dentro da VM e não chega ao host.
- Debian 12 (o mesmo do host), libvirt + QEMU/KVM. Sugestão inicial:
  **4 vCPU e 6 GiB de RAM**, com limite de CPU no libvirt para não competir
  com o Ollama. A stack medida no spike usa cerca de 1,2 GiB.
- A VM roda **tudo do LexPubli**: portal, worker, PostgreSQL,
  changedetection.io e o broker próprio (ADR-0005 §2a). O compose é o
  mesmo de hoje.
- A VM **não** recebe a GPU. Nenhum serviço do LexLearn roda nela.

### 2. NVMe dedicado, entregue inteiro à VM (passthrough VFIO)

- **Hardware:** adaptador passivo PCIe x4 → M.2 NVMe numa das portas livres
  **da CPU** (`00:01.0` ou `00:03.0`), mais um SSD M.2 2280 TLC com DRAM.
  O ideal é ter proteção contra queda de energia, por causa do PostgreSQL
  (Kingston DC2000B); a alternativa é linha NAS (WD Red SN700). O slot é
  PCIe 3.0, e um SSD Gen4 funciona a cerca de 3,5 GB/s.
- **O NVMe é ligado ao `vfio-pci` no boot.** O driver `nvme` do host nunca
  o reconhece, e o host não monta o disco. A VM instala o sistema nele.
- O disco da VM é **cifrado com LUKS**. Isso protege o disco fora da
  máquina (descarte, roubo). Não protege contra o root do host, que
  controla a VM de qualquer forma. O isolamento aqui protege o LexLearn do
  LexPubli, não o contrário.
- **Condição para usar o passthrough:** depois de instalado, o NVMe precisa
  aparecer sob uma porta da CPU, sozinho no grupo IOMMU dele. Se aparecer
  num grupo compartilhado, troca-se de slot. Não se usa o patch ACS
  override, que finge um isolamento que o hardware não tem.

### 3. Rede própria: VLAN no MikroTik, porta dedicada

- **VLAN 20 `lexpubli`**, sub-rede `172.16.20.0/24`, gateway `172.16.20.1`
  no MikroTik. A VM tem IP fixo (`172.16.20.10`), sem DHCP, como no
  segmento do LexLearn (ADR-0010 D5).
- **Transporte preferido: uma segunda placa de rede no gpu01**, PCIe x1 na
  porta do chipset (`00:1c.0`), também em passthrough para a VM e cabeada
  direto numa porta própria do MikroTik (ex.: `ether2`), fora do switch e
  fora da bridge do LexLearn.
  - O host nunca vê um quadro do LexPubli.
  - O tráfego do LexPubli não passa pelo switch do segmento `172.16.10.0/24`.
  - As portas do MikroTik são 10/100, o que basta para o portal.
- **Transporte provisório**, se a segunda placa ainda não existir: VLAN 20
  com tag sobre o `enp6s0`, numa bridge Linux do host **sem IP na VLAN 20**.
  Funciona, mas o kernel do host encaminha os quadros, e um switch sem
  gerência entre o gpu01 e o MikroTik precisa deixar a tag passar. É aceito
  só como passo intermediário.
- **Firewall no MikroTik** (forward), na ordem:

  | Origem → destino | Regra | Por quê |
  |---|---|---|
  | VLAN 20 → `172.16.10.0/24` | **DROP** | O LexPubli não alcança o LexLearn, o backup nem o Ollama |
  | VLAN 20 → internet | ACCEPT (com NAT) | Fontes (changedetection) e o Cloudflare Tunnel, só de saída |
  | `172.16.10.40` → `172.16.20.10:5671` | ACCEPT | O LexCorpus (no host) consome o broker do LexPubli, com TLS |
  | `172.16.10.40` → `172.16.20.10:22` | ACCEPT | Administração (ProxyJump pelo gpu01) e o pull dos editais (§5) |
  | resto → VLAN 20 | DROP | Nada mais entra |
  | internet → VLAN 20 | sem DNAT | O portal é publicado pelo Tunnel, não por porta aberta |

  Toda conexão entre as redes **parte do lado do LexLearn** para a VM,
  nunca da VM para o lado do LexLearn.
- A configuração vai para `scripts/mikrotik/lexlearn-gw.rsc` (no LexLearn,
  onde mora a configuração do roteador, ADR-0010 D1). Ela é aplicada seção
  por seção, com o `/export` conferido depois. São as duas lições do
  ADR-0010: safe mode na hora certa, e comando aceito não é comando efetivo.

### 4. Exposição: Cloudflare Tunnel de dentro da VM

- O `cloudflared` roda **na VM** e abre só conexão de saída. O MikroTik
  não ganha DNAT novo, e o 80/443 que hoje vai para o gpu01 (frontend do
  LexLearn, ADR-0010 D6) não muda.
- O túnel publica só o portal. O painel (`/painel/`) e o `/webhooks/`
  **não** passam pelo túnel: o painel é acessado pelo administrador via SSH
  com redirecionamento de porta, e o webhook só é chamado pelo
  changedetection dentro da VM. Isso fecha o item de backlog "/webhooks/ só
  na rede interna".
- `LEXPUBLI_HTTPS=1` (o Cloudflare termina o TLS público).

### 5. Editais: o LexLearn busca, o LexPubli não escreve

O ADR-0003 previa o worker do LexPubli montando `/data/raw/editais/`. Com a
VM, **o LexPubli não monta nada do host**, e o sentido do caminho se
inverte:

- O LexPubli grava os editais autorizados numa **pasta de exportação no
  próprio NVMe**, com o mesmo leiaute e o mesmo sidecar `edital-1.0`
  (ADR-0003 §2–3).
- O lado do LexLearn **puxa** essa pasta com `rsync` por SSH, usando uma
  chave restrita na VM (`rrsync -ro`, só leitura, só a pasta de exportação).
  O destino é `/data/raw/editais/`.
- **Quem dispara o pull é o Administrador do LexLearn** (ADR-0005 §2), por
  comando manual ou por um timer que ele mesmo liga no host. A ingestão
  continua sendo decisão dele (`POST /exams/ingerir-lote`).
- As regras do ADR-0003 continuam: sidecar renomeado antes do PDF (o rsync
  copia para temporários e renomeia), nunca apagar nem sobrescrever (o pull
  roda sem `--delete`).

Com isso, o LexPubli **não tem nenhum caminho de escrita** no território do
LexLearn. A pasta deixa de ser um ponto de escrita e vira um ponto de
leitura, controlado pelo lado que lê.

### 6. Broker com TLS

O LexCorpus passa a atravessar o roteador até o broker do LexPubli:

- AMQPS na porta 5671, com uma CA privada do ecossistema. A 5672 sem TLS
  não sai da VM.
- No LexCorpus, `LEXPUBLI_RABBIT_URL=amqps://lexcorpus:…@172.16.20.10:5671/lexpubli`,
  verificando o certificado.
- A gestão do RabbitMQ (15672) só é acessível dentro da VM, via SSH.

### 7. Backups do LexPubli

Também por **pull**: o `lexlearn-backup` (`172.16.10.30`) ou o host buscam
o dump do PostgreSQL do LexPubli pela mesma via SSH restrita. A VM nunca
escreve no backup. A regra de forward para isso entra junto com a do §3,
quando o backup for implementado.

## Alternativas consideradas

- **Só o NVMe novo, no mesmo Docker do host:** isola disco e I/O, não o
  kernel. Rejeitada como solução final; é o que se tem enquanto a VM não
  existe (o LexPubli ainda roda só no notebook).
- **NVMe como disco virtio da VM** (o host enxerga o dispositivo e o
  repassa): mais simples, mas o driver e o sistema de arquivos do host
  tocam o disco. O passthrough custa pouco a mais e é a separação de fato.
- **Máquina ou VPS separada já agora:** isolamento total, mas é decisão
  para depois do lançamento (dono do produto, 13/10). Este desenho facilita
  a mudança: a VM, a VLAN e os caminhos de pull e TLS são os mesmos que uma
  máquina separada usaria.
- **Rootless Docker / userns-remap no host, sem VM:** reduz o impacto de um
  escape, mas o kernel continua compartilhado. Pode ser adotado **dentro**
  da VM como camada extra.

## Consequências

**Positivas.**
- Um LexPubli comprometido fica preso em kernel, disco e rede próprios.
  Para chegar ao LexLearn, precisaria escapar da VM (KVM), um caminho muito
  mais difícil que escapar de um container.
- Nenhum caminho de escrita nem conexão sai do LexPubli em direção ao
  LexLearn. Tudo parte do lado do LexLearn.
- O portal sai do ar sem tocar no LexLearn, e o LexLearn sai sem tocar no
  portal (só o host é comum).
- Mudar para uma máquina separada depois é mover a VM (ou o disco), não
  redesenhar.

**Negativas / a monitorar.**
- O hardware e o hipervisor continuam comuns: queda de energia, falha da
  placa ou uma falha no KVM atingem os dois.
- Mais operação: libvirt, VFIO, uma VLAN, uma CA para o AMQPS e um túnel.
- As portas 10/100 do MikroTik limitam a banda do portal. Basta para o
  lançamento; revisar com o link dedicado.
- O ADR-0003 §5 (worker montando `/data/raw/editais`) é revisto pelo §5
  deste ADR quando ele for aceito.

## Implantação

1. **Hardware:** adaptador PCIe → M.2, SSD e segunda placa de rede PCIe x1.
   Conferir em `lspci -tv` que o NVMe ficou sob `00:01.0` ou `00:03.0`, e
   a placa de rede sob `00:1c.0`, cada um sozinho no grupo IOMMU dele.
   Conferir também que a GPU não cobre o slot.
2. **Host:** instalar libvirt/QEMU; `vfio-pci.ids=` do NVMe e da placa
   nova; conferir que o host não os enxerga (`lsblk`, `ip link`).
3. **MikroTik:** VLAN 20 na porta dedicada, endereço `172.16.20.1/24`, NAT
   de saída e as regras de forward do §3. Aplicar em seções, com `/export`
   depois. Registrar no LexLearn (ADR novo ou nota, conforme a regra de ADRs
   de lá).
4. **VM:** Debian 12 no NVMe com LUKS; Docker; o compose do LexPubli;
   AMQPS; `cloudflared`; usuário `rrsync` só leitura para a pasta de
   exportação.
5. **Testes de fronteira** (a VM tem de falhar em todos):
   - a VM alcançar `172.16.10.40:5672`, `172.16.10.40:11434`, `:8183` e
     `172.16.10.30`;
   - o host montar ou listar o NVMe da VM;
   - o túnel servir `/painel/` ou `/webhooks/`.

   E passar em: E2E aprovação → LexCorpus (via AMQPS) → resposta, e pull
   de um edital.
6. **ADR-0003:** nota de revisão do §5 (pull no lugar do mount).
