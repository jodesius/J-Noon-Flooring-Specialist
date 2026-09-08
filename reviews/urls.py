from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("", views.review_list, name="list"),
    path("new/", views.review_create, name="create"),
    path("<uuid:slug>/edit/", views.review_update, name="update"),
    path("<uuid:slug>/delete/", views.review_delete, name="delete"),
]
