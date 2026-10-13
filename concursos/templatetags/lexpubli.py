import json

from django import template
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

register = template.Library()

# Mesmo escape do json_script do Django: impede fechar o <script> por dentro.
_ESCAPES = {ord(">"): "\\u003E", ord("<"): "\\u003C", ord("&"): "\\u0026"}


@register.simple_tag(takes_context=True)
def json_ld(context, pagina):
    """schema.org JobPosting, um por cargo, num @graph.

    Concurso público é, para buscadores, uma oferta de emprego. Campos sem
    valor conhecido ficam de fora (não inventar dado).
    """
    request = context.get("request")
    url = request.build_absolute_uri(pagina.url) if request else pagina.url
    data_publicacao = pagina.inscricoes_inicio or (
        pagina.first_published_at.date() if pagina.first_published_at else None
    )
    descricao = strip_tags(pagina.resumo or "").strip() or pagina.title
    orgao = {"@type": "GovernmentOrganization", "name": pagina.orgao.nome}
    local = {"@type": "Place", "address": {"@type": "PostalAddress", "addressCountry": "BR"}}
    if pagina.orgao.uf:
        local["address"]["addressRegion"] = pagina.orgao.uf

    grafo = []
    for cargo in pagina.cargos.all():
        item = {
            "@type": "JobPosting",
            "title": cargo.nome,
            "description": descricao,
            "hiringOrganization": orgao,
            "jobLocation": local,
            "employmentType": "FULL_TIME",
            "directApply": False,
            "url": url,
        }
        if data_publicacao:
            item["datePosted"] = data_publicacao.isoformat()
        if pagina.inscricoes_fim:
            item["validThrough"] = pagina.inscricoes_fim.isoformat() + "T23:59:59-03:00"
        if cargo.vagas is not None:
            item["totalJobOpenings"] = cargo.vagas
        if cargo.salario is not None:
            item["baseSalary"] = {
                "@type": "MonetaryAmount",
                "currency": "BRL",
                "value": {"@type": "QuantitativeValue", "value": float(cargo.salario), "unitText": "MONTH"},
            }
        grafo.append(item)

    corpo = json.dumps({"@context": "https://schema.org", "@graph": grafo}, ensure_ascii=False)
    return mark_safe(f'<script type="application/ld+json">{corpo.translate(_ESCAPES)}</script>')


@register.filter
def brl(valor):
    """25270.68 -> 'R$ 25.270,68'."""
    if valor is None:
        return ""
    inteiro, _, centavos = f"{float(valor):,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"
