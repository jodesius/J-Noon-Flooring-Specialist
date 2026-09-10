from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("", views.index, name="index"),
    path("quote/", views.quote, name="quote"),
    path("quote/<uuid:slug>/", views.quote_detail, name="quote_detail"),
    path("call/", views.call, name="call"),
]
