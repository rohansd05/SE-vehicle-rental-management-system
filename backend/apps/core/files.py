"""SI-3: stored documents are retrieved only through signed, expiring links.

The database holds only the object key. A link is the key signed with the
SECRET_KEY and a timestamp, valid for MEDIA_URL_EXPIRY_SECONDS (900 s, under
the 15 minutes SI-3 allows). Media files are never served directly.
"""

import mimetypes

from django.conf import settings
from django.core import signing
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.urls import reverse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

SALT = "vrms.signed-file"


def signed_file_url(field_file, request=None) -> str | None:
    if not field_file:
        return None
    token = signing.TimestampSigner(salt=SALT).sign_object({"name": field_file.name})
    path = reverse("core:signed-file", args=[token])
    return request.build_absolute_uri(path) if request is not None else path


class SignedFileView(APIView):
    """Serve one stored file to whoever holds a valid, unexpired link.

    The signature is the credential, so no session or token is needed; a
    forged or expired link gets a 404 that says nothing about the file.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        tags=["Files"],
        summary="Download a stored file through a signed link (SI-3)",
        responses={200: OpenApiResponse(description="The file"), 404: None},
    )
    def get(self, request, token: str):
        try:
            value = signing.TimestampSigner(salt=SALT).unsign_object(
                token, max_age=settings.MEDIA_URL_EXPIRY_SECONDS
            )
        except signing.BadSignature as exc:  # includes SignatureExpired
            raise Http404 from exc
        name = value.get("name", "")
        if not name or not default_storage.exists(name):
            raise Http404
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        response = FileResponse(default_storage.open(name, "rb"), content_type=content_type)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
