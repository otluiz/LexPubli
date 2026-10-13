from django.conf import settings
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.contrib.sitemaps.views import sitemap
from wagtail.documents import urls as wagtaildocs_urls

from concursos import views

urlpatterns = [
    path(settings.LEXPUBLI_ADMIN_PATH, include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("webhooks/changedetection/", views.webhook_changedetection, name="webhook_changedetection"),
    path("sitemap.xml", sitemap),
    path("robots.txt", views.robots_txt),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [path("", include(wagtail_urls))]
