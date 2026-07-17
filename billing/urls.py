from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("usage/", views.ingest_usage, name="ingest_usage"),
]
