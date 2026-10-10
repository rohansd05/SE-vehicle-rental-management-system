"""Accounts API routes, mounted at /api/v1/."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/verify-otp/", views.VerifyOTPView.as_view(), name="verify-otp"),
    path("auth/resend-otp/", views.ResendOTPView.as_view(), name="resend-otp"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", views.RefreshView.as_view(), name="refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/password/change/", views.PasswordChangeView.as_view(), name="password-change"),
    path("me/", views.MeView.as_view(), name="me"),
    path("me/verify-mobile/", views.ConfirmMobileView.as_view(), name="verify-mobile"),
    path("licence/", views.LicenceView.as_view(), name="licence"),
    path("licences/", views.PendingLicenceListView.as_view(), name="licence-pending"),
    path("licences/<int:pk>/approve/", views.LicenceApproveView.as_view(), name="licence-approve"),
    path("licences/<int:pk>/reject/", views.LicenceRejectView.as_view(), name="licence-reject"),
]
