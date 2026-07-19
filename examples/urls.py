from django.urls import path

from . import views

app_name = "examples"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("rendered-samples/", views.rendered_samples, name="rendered_samples"),
]
