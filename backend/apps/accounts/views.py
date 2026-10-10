"""Accounts API views: registration, OTP, sign-in, tokens, profile and password.

Every view declares permission_classes explicitly (SE-4) and a throttle
scope. Customer self-registration is the only way to create an account
through the API; staff, technician, administrator and branch manager
accounts are created in the Django admin.
"""

from django.conf import settings
from django.contrib.auth import authenticate, user_logged_in
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, Throttled, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.core.permissions import IsAdministrator, IsBranchStaff, IsCustomer

from . import services
from .cookies import clear_refresh_cookie, read_refresh_cookie, set_refresh_cookie
from .models import Licence, User
from .serializers import (
    AccessTokenSerializer,
    DetailSerializer,
    EmailSerializer,
    LicenceRejectSerializer,
    LicenceReviewSerializer,
    LicenceSerializer,
    LicenceSubmitSerializer,
    LoginSerializer,
    OTPCodeSerializer,
    PasswordChangeSerializer,
    ProfileSerializer,
    ProfileUpdateResponseSerializer,
    ProfileUpdateSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    UserSummarySerializer,
    VerifyOTPSerializer,
)

# SE-8: the same message whatever the reason, so it never reveals whether an
# account exists, is unverified or is disabled.
GENERIC_LOGIN_FAILURE = "Unable to sign in with the details provided."
GENERIC_OTP_FAILURE = "The code is invalid or has expired."
SESSION_ENDED = "Your session has ended. Please sign in again."

COOKIE_NOTE = (
    "The refresh token is never in a response body (D21). It is set as the httpOnly, "
    "SameSite=Strict cookie `vrms_refresh`, scoped to /api/v1/auth/, which the browser "
    "sends back automatically. Keep the access token in memory only."
)

AUTH_TAG = "Authentication"
PROFILE_TAG = "Profile"


class _ThrottledView(APIView):
    throttle_classes = [ScopedRateThrottle]


class _PublicView(_ThrottledView):
    """Anonymous endpoints: no authentication is attempted at all."""

    permission_classes = [AllowAny]
    authentication_classes: list = []


class RegisterView(_PublicView):
    """SE-7: create an inactive customer account and send an OTP by SMS."""

    throttle_scope = "auth_register"

    @extend_schema(
        tags=[AUTH_TAG],
        summary="Register as a customer",
        request=RegisterSerializer,
        responses={201: RegisterResponseSerializer, 400: OpenApiResponse(description="Invalid")},
        examples=[
            OpenApiExample(
                "Register",
                request_only=True,
                value={
                    "email": "asha@example.com",
                    "password": "Str0ng!Passw0rd",
                    "name": "Asha Rao",
                    "mobile_no": "+919812345678",
                    "address": "14 Hill Road, Bandra (W), Mumbai 400050",
                    "date_of_birth": "1996-04-12",
                    "emergency_contact_name": "Ravi Rao",
                    "emergency_contact_mobile": "+919812300000",
                },
            )
        ],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = services.register_customer(**serializer.validated_data, request=request)
        body = {
            "email": customer.user.email,
            "detail": "Account created. Enter the code sent by SMS to verify your mobile number.",
        }
        return Response(body, status=status.HTTP_201_CREATED)


class VerifyOTPView(_PublicView):
    """SE-7: verify the registration code and activate the account."""

    throttle_scope = "auth_otp_verify"

    @extend_schema(
        tags=[AUTH_TAG],
        summary="Verify the registration OTP",
        request=VerifyOTPSerializer,
        responses={200: DetailSerializer, 400: DetailSerializer},
        examples=[
            OpenApiExample(
                "Verify", request_only=True, value={"email": "asha@example.com", "code": "123456"}
            )
        ],
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.activate_account(**serializer.validated_data, request=request)
        except services.OTPError as exc:
            raise ValidationError({"detail": GENERIC_OTP_FAILURE}) from exc
        return Response({"detail": "Your account is verified. You can now sign in."})


class ResendOTPView(_PublicView):
    """Send a new registration code; the previous one stops working."""

    throttle_scope = "auth_otp_resend"

    @extend_schema(
        tags=[AUTH_TAG],
        summary="Resend the registration OTP",
        request=EmailSerializer,
        responses={200: DetailSerializer, 429: DetailSerializer},
        examples=[OpenApiExample("Resend", request_only=True, value={"email": "asha@example.com"})],
    )
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        cooldown = settings.OTP_RESEND_COOLDOWN.total_seconds()
        # The cooldown applies to any address, so it reveals nothing either.
        if not cache.add(f"otp-resend:{email}", True, timeout=cooldown):
            raise Throttled(wait=cooldown, detail="Please wait before requesting another code.")
        services.resend_registration_otp(email, request)
        return Response(
            {"detail": "If an unverified account uses this address, a new code has been sent."}
        )


class LoginView(_PublicView):
    """Sign in and receive a JWT pair. SE-8 lockout is applied by django-axes."""

    throttle_scope = "auth_login"

    @extend_schema(
        tags=[AUTH_TAG],
        summary="Sign in",
        request=LoginSerializer,
        description=(
            "Returns the access token (5 minutes) and the user, and sets the refresh "
            "cookie (30 minutes). " + COOKIE_NOTE
        ),
        responses={
            200: AccessTokenSerializer,
            401: DetailSerializer,
            403: OpenApiResponse(DetailSerializer, description="Account locked (SE-8)"),
        },
        examples=[
            OpenApiExample(
                "Sign in",
                request_only=True,
                value={"email": "customer@vrms.test", "password": "Demo@1234"},
            )
        ],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        # The plain HttpRequest, so axes' flags reach AxesMiddleware.
        django_request = request._request
        user = authenticate(
            django_request, username=email, password=serializer.validated_data["password"]
        )
        if user is None:
            services.record_failed_login(email, request)
            # An explicit 401: with no authentication classes DRF would turn
            # AuthenticationFailed into a 403.
            return Response(
                {"detail": GENERIC_LOGIN_FAILURE, "code": "authentication_failed"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        # Resets the axes failure count (consecutive failures, SE-8).
        user_logged_in.send(sender=user.__class__, request=django_request, user=user)
        services.record_login(user, request)
        refresh = RefreshToken.for_user(user)
        response = Response(
            {"access": str(refresh.access_token), "user": UserSummarySerializer(user).data}
        )
        set_refresh_cookie(response, str(refresh))
        return response


def _session_ended() -> Response:
    response = Response(
        {"detail": SESSION_ENDED, "code": "session_ended"}, status=status.HTTP_401_UNAUTHORIZED
    )
    clear_refresh_cookie(response)
    return response


class RefreshView(_PublicView):
    """SE-9, D19, D21: trade the refresh cookie for a new access token.

    The cookie rotates: a new refresh token is set and the old one is
    blacklisted, so a copied cookie works at most once.
    """

    throttle_scope = "auth_token"

    @extend_schema(
        tags=[AUTH_TAG],
        summary="Refresh the access token",
        description=(
            "No request body. Reads the refresh cookie, blacklists it, sets a new one and "
            "returns a new access token and the user (also used to restore a session when "
            "the page loads). 401 with code `session_ended` when the cookie is missing, "
            "expired or already used; the cookie is then cleared. " + COOKIE_NOTE
        ),
        request=None,
        responses={200: AccessTokenSerializer, 401: DetailSerializer},
    )
    def post(self, request):
        raw = read_refresh_cookie(request)
        if raw is None:
            return _session_ended()
        serializer = TokenRefreshSerializer(data={"refresh": raw})
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError, AuthenticationFailed):
            return _session_ended()
        access = serializer.validated_data["access"]
        claim = settings.SIMPLE_JWT.get("USER_ID_CLAIM", "user_id")
        user = User.objects.get(pk=AccessToken(access)[claim])
        response = Response({"access": access, "user": UserSummarySerializer(user).data})
        set_refresh_cookie(response, serializer.validated_data.get("refresh", raw))
        return response


class LogoutView(_PublicView):
    """Blacklist the refresh cookie's token and clear the cookie (D21).

    No access token is needed: after 30 idle minutes the access token has
    long expired, yet the browser must still be able to drop the httpOnly
    cookie, which page scripts cannot touch. SameSite=Strict keeps other
    sites from triggering it.
    """

    throttle_scope = "auth_token"

    @extend_schema(
        tags=[AUTH_TAG],
        summary="Sign out",
        description=(
            "No request body and no access token needed. Blacklists the refresh token in "
            "the cookie, if any, and always clears the cookie. " + COOKIE_NOTE
        ),
        request=None,
        responses={204: None},
    )
    def post(self, request):
        raw = read_refresh_cookie(request)
        if raw is not None:
            try:
                token = RefreshToken(raw)  # also rejects a blacklisted token
                claim = settings.SIMPLE_JWT.get("USER_ID_CLAIM", "user_id")
                user = User.objects.filter(pk=token.get(claim)).first()
                token.blacklist()
                if user is not None:
                    services.record_logout(user, request)
            except TokenError:
                pass  # already expired or used: nothing left to revoke
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class PasswordChangeView(_ThrottledView):
    """Change the password; every session ends and the user signs in again."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "auth_password"

    @extend_schema(
        tags=[AUTH_TAG],
        summary="Change password",
        request=PasswordChangeSerializer,
        responses={200: DetailSerializer, 400: OpenApiResponse(description="Invalid")},
        examples=[
            OpenApiExample(
                "Change password",
                request_only=True,
                value={"current_password": "Demo@1234", "new_password": "N3w!Passw0rd-2026"},
            )
        ],
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        services.change_password(request.user, serializer.validated_data["new_password"], request)
        response = Response({"detail": "Password changed. Please sign in again."})
        clear_refresh_cookie(response)  # every refresh token was blacklisted (A11)
        return response


class MeView(_ThrottledView):
    """The signed-in user's own profile."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "auth_profile"

    @extend_schema(tags=[PROFILE_TAG], summary="My profile", responses=ProfileSerializer)
    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    @extend_schema(
        tags=[PROFILE_TAG],
        summary="Update my profile",
        description=(
            "Name and address change at once. A new mobile number is applied only after "
            "the code sent to it is confirmed at /api/v1/me/verify-mobile/ (SE-7)."
        ),
        request=ProfileUpdateSerializer,
        responses=ProfileUpdateResponseSerializer,
        examples=[
            OpenApiExample("Change mobile", request_only=True, value={"mobile_no": "+919898989898"})
        ],
    )
    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        pending = services.update_profile(request.user, serializer.validated_data, request)
        data = ProfileSerializer(request.user).data
        return Response({**data, "mobile_change_pending": pending})


class ConfirmMobileView(_ThrottledView):
    """SE-7: confirm a new mobile number with the code sent to it."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "auth_otp_verify"

    @extend_schema(
        tags=[PROFILE_TAG],
        summary="Confirm a new mobile number",
        request=OTPCodeSerializer,
        responses={200: ProfileSerializer, 400: DetailSerializer},
        examples=[OpenApiExample("Confirm", request_only=True, value={"code": "123456"})],
    )
    def post(self, request):
        serializer = OTPCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = services.confirm_mobile_change(
                request.user, serializer.validated_data["code"], request
            )
        except services.OTPError as exc:
            raise ValidationError({"detail": GENERIC_OTP_FAILURE}) from exc
        return Response(ProfileSerializer(user).data)


# ─── Driving licence ──────────────────────────────────────────────────────

LICENCE_TAG = "Licence"
VERIFICATION_TAG = "Licence verification"


class LicenceView(_ThrottledView):
    """The customer's own driving licence (Book.Eligible.No: submit a licence now)."""

    permission_classes = [IsCustomer]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "licence_submit"

    def get_throttles(self):
        return super().get_throttles() if self.request.method == "POST" else []

    @extend_schema(tags=[LICENCE_TAG], summary="My driving licence", responses=LicenceSerializer)
    def get(self, request):
        # Every customer has a licence status (Appendix A); one created in the
        # admin may not have a row yet, so it starts as Not Submitted.
        licence, _ = Licence.objects.get_or_create(customer=request.user.customer)
        return Response(LicenceSerializer(licence, context={"request": request}).data)

    @extend_schema(
        tags=[LICENCE_TAG],
        summary="Submit or resubmit my driving licence",
        description=(
            "Multipart form. Both images are required (Appendix A front and back image): "
            "JPG or PNG, at most 5 MB. An already-expired licence is refused (BR-2). The "
            "licence then awaits verification by branch staff or an administrator."
        ),
        request={"multipart/form-data": LicenceSubmitSerializer},
        responses={200: LicenceSerializer, 400: OpenApiResponse(description="Invalid")},
        examples=[
            OpenApiExample(
                "Submit",
                request_only=True,
                value={
                    "licence_number": "MH02 20190012345",
                    "issuing_authority": "RTO Mumbai (West)",
                    "issue_date": "2019-06-01",
                    "expiry_date": "2039-05-31",
                    "categories": ["Car", "Two-Wheeler"],
                    "front_image": "(binary)",
                    "back_image": "(binary)",
                },
            )
        ],
    )
    def post(self, request):
        serializer = LicenceSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            licence = services.submit_licence(
                request.user.customer, serializer.validated_data, request
            )
        except services.LicenceError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(LicenceSerializer(licence, context={"request": request}).data)


class PendingLicenceListView(ListAPIView):
    """Licences awaiting verification, oldest first.

    Licences are not tied to a branch, so every branch's staff see the queue.
    """

    permission_classes = [IsBranchStaff | IsAdministrator]
    serializer_class = LicenceReviewSerializer

    def get_queryset(self):
        return (
            Licence.objects.filter(status=Licence.Status.PENDING_VERIFICATION)
            .select_related("customer__user")
            .prefetch_related("categories")
            .order_by("updated_at")
        )

    @extend_schema(tags=[VERIFICATION_TAG], summary="Licences pending verification")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class LicenceApproveView(APIView):
    permission_classes = [IsBranchStaff | IsAdministrator]

    @extend_schema(
        tags=[VERIFICATION_TAG],
        summary="Approve a licence",
        request=None,
        responses={200: LicenceReviewSerializer, 400: DetailSerializer, 404: None},
    )
    def post(self, request, pk: int):
        get_object_or_404(Licence, pk=pk)
        try:
            licence = services.approve_licence(pk, request.user, request)
        except services.LicenceError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(LicenceReviewSerializer(licence, context={"request": request}).data)


class LicenceRejectView(APIView):
    permission_classes = [IsBranchStaff | IsAdministrator]

    @extend_schema(
        tags=[VERIFICATION_TAG],
        summary="Reject a licence (a reason is required)",
        request=LicenceRejectSerializer,
        responses={200: LicenceReviewSerializer, 400: DetailSerializer, 404: None},
        examples=[
            OpenApiExample(
                "Reject",
                request_only=True,
                value={"reason": "The photograph of the back of the licence is unreadable."},
            )
        ],
    )
    def post(self, request, pk: int):
        get_object_or_404(Licence, pk=pk)
        serializer = LicenceRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            licence = services.reject_licence(
                pk, request.user, serializer.validated_data["reason"], request
            )
        except services.LicenceError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(LicenceReviewSerializer(licence, context={"request": request}).data)
