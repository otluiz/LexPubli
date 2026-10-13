"""Domínio do LexPubli: concursos, órgãos, bancas, cargos e a fila de curadoria.

Fluxo do spike (ADR-0001):
    fonte (changedetection.io) ──webhook──▶ Descoberta(pendente)
    curadoria no admin ──aprova + liga a um ConcursoPage──▶ OutboxEvent
    worker `publicar_eventos` ──▶ RabbitMQ (lexpubli.events)
"""
from __future__ import annotations

from django.db import models, transaction
from django.utils import timezone
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page
from wagtail.search import index

from .util import dominio_oficial, slug_lex, uuid7


def _sites_de_banca() -> list[str]:
    return [s for s in Banca.objects.exclude(site="").values_list("site", flat=True)]


def _url_comparavel(url: str) -> str:
    """https://www.stj.jus.br/x/ e http://stj.jus.br/x -> stj.jus.br/x"""
    from urllib.parse import urlsplit

    p = urlsplit((url or "").strip())
    host = (p.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    if not host:
        return ""
    return host + p.path.rstrip("/") + (f"?{p.query}" if p.query else "")


def _exigir_oficial(campo: str, url: str) -> None:
    """ADR-0002: o que sai do LexPubli como fonte é página oficial. Agregador
    (PCI etc.) só serve de índice, como origem de uma Descoberta."""
    from django.core.exceptions import ValidationError

    if url and not dominio_oficial(url, _sites_de_banca()):
        raise ValidationError({campo: "Use a página oficial: domínio .gov.br, .leg.br, .jus.br, "
                                      ".mp.br, .def.br ou o site de uma banca cadastrada. "
                                      "Agregador é só índice (ADR-0002)."})


# --- Cadastros ---------------------------------------------------------------
class Orgao(index.Indexed, models.Model):
    class Esfera(models.TextChoices):
        FEDERAL = "federal", "Federal"
        ESTADUAL = "estadual", "Estadual"
        DISTRITAL = "distrital", "Distrital"
        MUNICIPAL = "municipal", "Municipal"

    nome = models.CharField(max_length=200)
    sigla = models.CharField(max_length=30, blank=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True,
                            help_text="Gerado da sigla (ou do nome) se vazio. Ex.: sefaz_al")
    esfera = models.CharField(max_length=10, choices=Esfera.choices)
    uf = models.CharField("UF", max_length=2, blank=True)

    panels = [
        FieldPanel("nome"),
        FieldRowPanel([FieldPanel("sigla"), FieldPanel("slug")]),
        FieldRowPanel([FieldPanel("esfera"), FieldPanel("uf")]),
    ]
    search_fields = [index.SearchField("nome"), index.AutocompleteField("sigla")]

    class Meta:
        verbose_name = "órgão"
        verbose_name_plural = "órgãos"
        ordering = ["nome"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_lex(self.sigla or self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.sigla or self.nome


class Banca(models.Model):
    nome = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True, blank=True,
                            help_text="O MESMO slug do LexCorpus (chave do storage). Ex.: cebraspe")
    site = models.URLField(blank=True)

    panels = [FieldPanel("nome"), FieldPanel("slug"), FieldPanel("site")]

    class Meta:
        ordering = ["nome"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_lex(self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


# --- Páginas -----------------------------------------------------------------
class StatusConcurso(models.TextChoices):
    PREVISTO = "previsto", "Previsto"
    AUTORIZADO = "autorizado", "Autorizado"
    EDITAL_ABERTO = "edital_aberto", "Edital aberto"
    INSCRICOES_ENCERRADAS = "inscricoes_encerradas", "Inscrições encerradas"
    PROVA_REALIZADA = "prova_realizada", "Prova realizada"
    RESULTADO = "resultado", "Resultado"
    ENCERRADO = "encerrado", "Encerrado"


class Carreira(models.TextChoices):
    """Lista fixa da curadoria (ADR-0004 §2). É a mesma do contrato
    (common.schema.json, $defs/career): um teste confere. Valor novo = MINOR
    no contrato, com o consumidor (LexCorpus) atualizado primeiro."""
    FISCAL = "fiscal", "Fiscal (Sefaz, Receita)"
    CONTROLE = "controle", "Controle (TCU, TCEs, CGU)"
    TRIBUNAIS = "tribunais", "Tribunais (TJ, TRF, TRT, TRE)"
    JURIDICA = "juridica", "Jurídica (procuradorias, defensorias, MP, magistratura)"
    POLICIAL = "policial", "Policial (PF, PRF, PC, PM)"
    LEGISLATIVA = "legislativa", "Legislativa (câmaras, assembleias, Senado)"
    BANCARIA = "bancaria", "Bancária (BB, Caixa, BNB, BNDES, Bacen)"
    ADMINISTRATIVA = "administrativa", "Administrativa (executivo em geral)"
    ESTATAIS = "estatais", "Estatais (Petrobras, Transpetro e similares)"
    SAUDE = "saude", "Saúde"
    EDUCACAO = "educacao", "Educação"


class ConcursosIndexPage(Page):
    """Página inicial do portal: lista os concursos publicados."""

    introducao = RichTextField(blank=True)

    content_panels = Page.content_panels + [FieldPanel("introducao")]
    subpage_types = ["concursos.ConcursoPage"]
    max_count = 1

    class Meta:
        verbose_name = "índice de concursos"

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        ctx["concursos"] = (
            ConcursoPage.objects.child_of(self).live().public()
            .select_related("orgao", "banca").order_by("-first_published_at")
        )
        return ctx


class ConcursoPage(Page):
    contest_id = models.UUIDField(default=uuid7, unique=True, editable=False)
    contest_slug = models.SlugField(max_length=80, unique=True, blank=True,
                                    help_text="Gerado como {órgão}_{ano} se vazio. Ex.: sefaz_al_2026")
    orgao = models.ForeignKey(Orgao, on_delete=models.PROTECT, related_name="concursos")
    banca = models.ForeignKey(Banca, on_delete=models.PROTECT, null=True, blank=True,
                              related_name="concursos", help_text="Vazio = banca ainda não definida.")
    ano = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=24, choices=StatusConcurso.choices,
                              default=StatusConcurso.PREVISTO)
    carreira = models.CharField(max_length=20, choices=Carreira.choices, blank=True,
                                help_text="Orienta a busca de provas relacionadas no LexCorpus.")
    data_prova = models.DateField("data da prova", null=True, blank=True)
    inscricoes_inicio = models.DateField(null=True, blank=True)
    inscricoes_fim = models.DateField(null=True, blank=True)
    edital_url = models.URLField("URL do edital", blank=True)
    fonte_url = models.URLField("URL da fonte", help_text="Página oficial de onde vieram os dados.")
    resumo = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldRowPanel([FieldPanel("orgao"), FieldPanel("banca")]),
        FieldRowPanel([FieldPanel("ano"), FieldPanel("status"), FieldPanel("contest_slug")]),
        FieldRowPanel([FieldPanel("carreira"), FieldPanel("data_prova")]),
        MultiFieldPanel(
            [FieldRowPanel([FieldPanel("inscricoes_inicio"), FieldPanel("inscricoes_fim")])],
            heading="Inscrições",
        ),
        FieldRowPanel([FieldPanel("edital_url"), FieldPanel("fonte_url")]),
        FieldPanel("resumo"),
        InlinePanel("cargos", label="Cargos", min_num=1),
    ]
    search_fields = Page.search_fields + [index.SearchField("resumo")]
    parent_page_types = ["concursos.ConcursosIndexPage"]
    subpage_types: list[str] = []

    class Meta:
        verbose_name = "concurso"

    def save(self, *args, **kwargs):
        if not self.contest_slug and self.orgao_id and self.ano:
            self.contest_slug = f"{self.orgao.slug}_{self.ano}"
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        _exigir_oficial("fonte_url", self.fonte_url)

    @property
    def total_vagas(self) -> int | None:
        vagas = [c.vagas for c in self.cargos.all() if c.vagas is not None]
        return sum(vagas) if vagas else None

    @property
    def maior_salario(self):
        salarios = [c.salario for c in self.cargos.all() if c.salario is not None]
        return max(salarios) if salarios else None


class Cargo(Orderable):
    concurso = ParentalKey(ConcursoPage, on_delete=models.CASCADE, related_name="cargos")
    nome = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, blank=True)
    vagas = models.PositiveIntegerField(null=True, blank=True)
    salario = models.DecimalField("remuneração inicial (R$)", max_digits=10, decimal_places=2,
                                  null=True, blank=True)
    escolaridade = models.CharField(max_length=60, blank=True)

    panels = [
        FieldPanel("nome"),
        FieldRowPanel([FieldPanel("vagas"), FieldPanel("salario"), FieldPanel("escolaridade")]),
    ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_lex(self.nome)[:120]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


# --- Fontes de descoberta (ADR-0007) -----------------------------------------
class Fonte(models.Model):
    """Página oficial (ou o DOU) que o LexPubli vigia. O cadastro é a fonte
    da verdade; o changedetection.io só executa (ADR-0007 §1). Tudo o que
    uma fonte aponta vira Descoberta pendente: a curadoria continua sendo a
    porta."""

    class Poder(models.TextChoices):
        EXECUTIVO = "executivo", "Executivo"
        LEGISLATIVO = "legislativo", "Legislativo"
        JUDICIARIO = "judiciario", "Judiciário"
        MINISTERIO_PUBLICO = "ministerio_publico", "Ministério Público"

    class Tipo(models.TextChoices):
        DOU = "dou", "DOU (coletor próprio)"
        PAGINA = "pagina", "Página (changedetection)"

    class Onda(models.TextChoices):
        A = "A", "A — federal"
        B = "B", "B — regional"
        C = "C", "C — estadual"

    nome = models.CharField(max_length=200)
    poder = models.CharField(max_length=20, choices=Poder.choices)
    esfera = models.CharField(max_length=10, choices=Orgao.Esfera.choices)
    orgao = models.ForeignKey(Orgao, on_delete=models.PROTECT, null=True, blank=True,
                              related_name="fontes",
                              help_text="Quando a fonte é de um órgão só.")
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.PAGINA)
    url = models.URLField(max_length=500, unique=True, help_text="A página oficial.")
    carreira_sugerida = models.CharField(
        max_length=20, choices=Carreira.choices, blank=True,
        help_text="Só SUGESTÃO para o curador; quem grava a carreira do concurso é ele (ADR-0004).")
    onda = models.CharField(max_length=1, choices=Onda.choices, default=Onda.A)
    prioridade = models.PositiveSmallIntegerField(default=3, help_text="1 = vigiar primeiro.")
    intervalo_horas = models.PositiveSmallIntegerField(
        default=6, help_text="Mínimo de 1 h por página (ADR-0007 §4); o DOU é diário.")
    ativa = models.BooleanField(
        default=False, help_text="Só depois de conferida: texto sem JS (ou API/feed) e robots.txt.")
    motivo_inativa = models.CharField(max_length=300, blank=True,
                                      help_text="Ex.: página só com JS; robots.txt proíbe.")
    conferida_em = models.DateField(null=True, blank=True)
    changedetection_uuid = models.CharField(max_length=40, blank=True, editable=False,
                                            help_text="Preenchido pela sincronização.")

    panels = [
        FieldPanel("nome"),
        FieldRowPanel([FieldPanel("poder"), FieldPanel("esfera"), FieldPanel("onda")]),
        FieldRowPanel([FieldPanel("orgao"), FieldPanel("carreira_sugerida")]),
        FieldRowPanel([FieldPanel("tipo"), FieldPanel("url")]),
        FieldRowPanel([FieldPanel("prioridade"), FieldPanel("intervalo_horas")]),
        FieldRowPanel([FieldPanel("ativa"), FieldPanel("conferida_em"),
                       FieldPanel("motivo_inativa")]),
    ]

    class Meta:
        ordering = ["onda", "prioridade", "nome"]

    def __str__(self):
        return self.nome

    @classmethod
    def do_aviso(cls, url: str, watch_uuid: str = "") -> "Fonte | None":
        """A Fonte de um aviso do changedetection: pelo uuid do watch (o corpo
        da notificação o traz) ou pela URL vigiada, sem www e sem barra final."""
        if watch_uuid:
            fonte = cls.objects.filter(changedetection_uuid=watch_uuid).first()
            if fonte:
                return fonte
        alvo = _url_comparavel(url)
        if not alvo:
            return None
        return next((f for f in cls.objects.filter(url__icontains=alvo.split("/", 1)[0])
                     if _url_comparavel(f.url) == alvo), None)

    def clean(self):
        from django.core.exceptions import ValidationError

        _exigir_oficial("url", self.url)
        if self.intervalo_horas < 1:
            raise ValidationError({"intervalo_horas": "No mínimo 1 hora (ADR-0007 §4)."})
        if self.tipo == self.Tipo.DOU and self.intervalo_horas < 24:
            raise ValidationError({"intervalo_horas": "O DOU é coletado 1 vez por dia."})
        if self.ativa and not self.conferida_em:
            raise ValidationError({"ativa": "Confira a fonte (texto sem JS, robots.txt) e "
                                            "registre a data antes de ativá-la."})
        if not self.ativa and self.conferida_em and not self.motivo_inativa:
            raise ValidationError({"motivo_inativa": "Fonte conferida e inativa: diga por quê."})


# --- Curadoria ---------------------------------------------------------------
class Descoberta(models.Model):
    """Algo que uma fonte apontou e um humano precisa avaliar.

    Só a aprovação (status=aprovada + concurso ligado) gera evento: o
    ecossistema recebe informação curada, nunca o ruído bruto das fontes.
    """

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADA = "aprovada", "Aprovada"
        REJEITADA = "rejeitada", "Rejeitada"
        DUPLICADA = "duplicada", "Duplicada"

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    titulo = models.CharField(max_length=300)
    fonte = models.CharField(max_length=40, default="manual",
                             help_text="Quem apontou: changedetection, manual, ...")
    fonte_url = models.URLField(max_length=500)
    fonte_vigiada = models.ForeignKey(
        "Fonte", on_delete=models.SET_NULL, null=True, blank=True, related_name="descobertas",
        help_text="A Fonte do cadastro que apontou a mudança (ADR-0007): dá o poder e a "
                  "carreira sugerida. Preenchida pelo webhook.")
    resumo = models.TextField(blank=True, help_text="Trecho/diff recebido da fonte.")
    payload = models.JSONField(default=dict, blank=True, help_text="Corpo bruto recebido (auditoria).")
    chave_dedup = models.CharField(max_length=64, unique=True, editable=False,
                                   help_text="sha256(fonte_url + resumo): reentrega do webhook não duplica.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    concurso = models.ForeignKey(ConcursoPage, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="descobertas",
                                 help_text="Obrigatório para aprovar.")
    duplicada_de = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="duplicatas")
    detectada_em = models.DateTimeField(default=timezone.now)
    decidida_em = models.DateTimeField(null=True, blank=True, editable=False)

    panels = [
        FieldPanel("titulo"),
        FieldRowPanel([FieldPanel("fonte"), FieldPanel("fonte_url")]),
        FieldRowPanel([FieldPanel("fonte_vigiada", read_only=True)]),
        FieldPanel("resumo"),
        FieldRowPanel([FieldPanel("status"), FieldPanel("concurso"), FieldPanel("duplicada_de")]),
    ]

    class Meta:
        ordering = ["-detectada_em"]

    def __str__(self):
        return self.titulo

    @property
    def poder(self) -> str:
        return self.fonte_vigiada.get_poder_display() if self.fonte_vigiada else ""

    @property
    def carreira_sugerida(self) -> str:
        """Só sugestão: quem grava a carreira do concurso é o curador (ADR-0004)."""
        f = self.fonte_vigiada
        return f.get_carreira_sugerida_display() if f and f.carreira_sugerida else ""

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.status == self.Status.APROVADA and not self.concurso_id:
            raise ValidationError({"concurso": "Ligue a descoberta a um concurso para aprová-la."})
        if self.status == self.Status.APROVADA and not dominio_oficial(
                self.concurso.fonte_url, _sites_de_banca()):
            # o anúncio leva a fonte do CONCURSO (o LexCorpus resolve o alvo
            # por ela); a fonte_url da descoberta pode ser um agregador
            raise ValidationError({"concurso": "A URL da fonte do concurso não é oficial: "
                                               "corrija-a na página do concurso antes de aprovar."})
        if self.status == self.Status.DUPLICADA and not self.duplicada_de_id:
            raise ValidationError({"duplicada_de": "Indique de qual descoberta esta é duplicata."})
        if self.duplicada_de_id and self.duplicada_de_id == self.id:
            raise ValidationError({"duplicada_de": "Uma descoberta não duplica a si mesma."})

    def save(self, *args, **kwargs):
        from .eventos import registrar_descoberta_aprovada

        anterior = (
            Descoberta.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if not self._state.adding else None
        )
        if self.status != anterior and self.status != self.Status.PENDENTE:
            self.decidida_em = timezone.now()
        acabou_de_aprovar = self.status == self.Status.APROVADA and anterior != self.Status.APROVADA
        with transaction.atomic():
            super().save(*args, **kwargs)
            if acabou_de_aprovar:
                registrar_descoberta_aprovada(self)


class OutboxEvent(models.Model):
    """Transactional outbox: o evento nasce na MESMA transação da mudança.

    O worker `publicar_eventos` lê os pendentes e publica no RabbitMQ. Se o
    broker estiver fora, nada se perde: o evento espera aqui.
    """

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PUBLICADO = "publicado", "Publicado"
        INVALIDO = "invalido", "Inválido (não publicado)"

    event_id = models.UUIDField(primary_key=True, editable=False)
    event_type = models.CharField(max_length=80)
    envelope = models.JSONField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    tentativas = models.PositiveIntegerField(default=0)
    ultimo_erro = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    publicado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["criado_em"]
        indexes = [models.Index(fields=["status", "criado_em"])]
        verbose_name = "evento (outbox)"
        verbose_name_plural = "eventos (outbox)"

    def __str__(self):
        return f"{self.event_type} {self.event_id}"
