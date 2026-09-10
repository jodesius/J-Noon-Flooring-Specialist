from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("", views.index, name="index"),
    path("quote/", views.quote, name="quote"),
    path("quote/<uuid:slug>/", views.quote_detail, name="quote_detail"),
    path("call/", views.call, name="call"),
    path("book/", views.book, name="book"),
    path("projects/", views.projects, name="projects"),
    path("manage/", views.manage, name="manage"),
    path("projects/<uuid:slug>/", views.project_detail, name="project_detail"),
    path(
        "projects/<uuid:slug>/invoice/<str:number>/",
        views.invoice_pdf,
        name="invoice_pdf",
    ),
    path("projects/<uuid:slug>/pay/deposit/", views.pay_deposit, name="pay_deposit"),
    path("projects/<uuid:slug>/pay/balance/", views.pay_balance, name="pay_balance"),
    path("pay/<uuid:slug>/", views.checkout, name="checkout"),
    path("pay/<uuid:slug>/done/", views.checkout_return, name="checkout_return"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
