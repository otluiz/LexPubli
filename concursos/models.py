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

from .util import slug_lex, uuid7


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
    inscricoes_inicio = models.DateField(null=True, blank=True)
    inscricoes_fim = models.DateField(null=True, blank=True)
    edital_url = models.URLField("URL do edital", blank=True)
    fonte_url = models.URLField("URL da fonte", help_text="Página oficial de onde vieram os dados.")
    resumo = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldRowPanel([FieldPanel("orgao"), FieldPanel("banca")]),
        FieldRowPanel([FieldPanel("ano"), FieldPanel("status"), FieldPanel("contest_slug")]),
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
        FieldPanel("resumo"),
        FieldRowPanel([FieldPanel("status"), FieldPanel("concurso"), FieldPanel("duplicada_de")]),
    ]

    class Meta:
        ordering = ["-detectada_em"]

    def __str__(self):
        return self.titulo

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.status == self.Status.APROVADA and not self.concurso_id:
            raise ValidationError({"concurso": "Ligue a descoberta a um concurso para aprová-la."})
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
