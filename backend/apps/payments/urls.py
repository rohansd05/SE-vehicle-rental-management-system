"""Payments API routes, mounted under /api/v1/payments/."""

from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("due/", views.DueView.as_view(), name="due"),
    path("refunds/", views.RefundListView.as_view(), name="refund-list"),
    path("refunds/<int:pk>/approve/", views.RefundApproveView.as_view(), name="refund-approve"),
    path("refunds/<int:pk>/reject/", views.RefundRejectView.as_view(), name="refund-reject"),
    path("refunds/<int:pk>/pay-out/", views.RefundPayOutView.as_view(), name="refund-pay-out"),
    path("<int:pk>/refund/", views.PaymentRefundView.as_view(), name="payment-refund"),
    path("bookings/<int:pk>/capture/", views.BookingCaptureView.as_view(), name="booking-capture"),
    path("webhook/", views.GatewayNotificationView.as_view(), name="webhook"),
]
