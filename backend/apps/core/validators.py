"""Upload validation (D3): extension, size and Pillow verify().

python-magic is not used (D3); Pillow decodes the header and checks the
file's structure, and the decoded format must match an allowed type.
"""

from pathlib import PurePath

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

PILLOW_FORMATS = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG"}


def validate_image_upload(upload, *, extensions: tuple[str, ...], max_bytes: int) -> None:
    extension = PurePath(upload.name or "").suffix.lower().lstrip(".")
    if extension not in extensions:
        allowed = ", ".join(f".{ext}" for ext in extensions)
        raise ValidationError(f"Upload a file of type {allowed}.")
    if upload.size > max_bytes:
        raise ValidationError(f"The file is larger than {max_bytes // (1024 * 1024)} MB.")
    try:
        upload.seek(0)
        with Image.open(upload) as image:
            detected = image.format
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValidationError("The file is not a valid image.") from exc
    finally:
        upload.seek(0)
    if detected != PILLOW_FORMATS.get(extension):
        raise ValidationError("The file content does not match its file type.")
