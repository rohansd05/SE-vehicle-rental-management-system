"""Accounts API routes, mounted at /api/v1/."""

from django.urls import path

from . import admin_views, views

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

# Staff accounts and the blacklist (Module N3, UC 12): admin_views.py, Administrator only.
urlpatterns += [
    path("admin/users/", admin_views.StaffListView.as_view(), name="admin-users"),
    path("admin/users/<int:pk>/", admin_views.StaffDetailView.as_view(), name="admin-user"),
    path(
        "admin/users/<int:pk>/disable/",
        admin_views.StaffDisableView.as_view(),
        name="admin-user-disable",
    ),
    path(
        "admin/users/<int:pk>/enable/",
        admin_views.StaffEnableView.as_view(),
        name="admin-user-enable",
    ),
    path("admin/customers/", admin_views.CustomerListView.as_view(), name="admin-customers"),
    path(
        "admin/customers/<int:pk>/",
        admin_views.CustomerDetailView.as_view(),
        name="admin-customer",
    ),
    path(
        "admin/customers/<int:pk>/blacklist/",
        admin_views.CustomerBlacklistView.as_view(),
        name="admin-customer-blacklist",
    ),
    path(
        "admin/customers/<int:pk>/lift-blacklist/",
        admin_views.CustomerLiftBlacklistView.as_view(),
        name="admin-customer-lift-blacklist",
    ),
    path(
        "admin/customers/<int:pk>/bookings/<int:booking_id>/cancel/",
        admin_views.CustomerBookingCancelView.as_view(),
        name="admin-customer-booking-cancel",
    ),
]
