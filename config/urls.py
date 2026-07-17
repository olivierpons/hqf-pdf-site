from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

# set_language posts here, and must stay outside i18n_patterns: it is what
# picks the language prefix, so it cannot live behind one. The usage feed is a
# machine endpoint with no page to translate, so it stays outside too.
urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("billing/", include("billing.urls")),
]

urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("accounts/", include("accounts.urls")),
)
