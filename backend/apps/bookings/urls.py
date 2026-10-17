"""Bookings API routes, mounted under /api/v1/bookings/."""

from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("", views.BookingListCreateView.as_view(), name="booking-list"),
    path("awaiting-cash/", views.AwaitingCashListView.as_view(), name="booking-awaiting-cash"),
    path("<int:pk>/", views.BookingDetailView.as_view(), name="booking-detail"),
    path("<int:pk>/hold/", views.BookingHoldView.as_view(), name="booking-hold"),
    path("<int:pk>/pay/", views.BookingPayView.as_view(), name="booking-pay"),
    path("<int:pk>/cash/", views.BookingCashView.as_view(), name="booking-cash"),
    path("<int:pk>/invoice/", views.BookingInvoiceView.as_view(), name="booking-invoice"),
    path("<int:pk>/cancel/", views.BookingCancelView.as_view(), name="booking-cancel"),
    path(
        "<int:pk>/modify/quote/",
        views.BookingModifyQuoteView.as_view(),
        name="booking-modify-quote",
    ),
    path("<int:pk>/modify/", views.BookingModifyView.as_view(), name="booking-modify"),
    path(
        "<int:pk>/extend/quote/",
        views.BookingExtendQuoteView.as_view(),
        name="booking-extend-quote",
    ),
    path("<int:pk>/extend/", views.BookingExtendView.as_view(), name="booking-extend"),
]
