"""DEMO photographs for the catalogue (Module R4; Search.Detail, Fleet.Add: at least four).

Every demo vehicle (chassis number starting "DEMO", from any seed) gets
photographs up to VEHICLE_PHOTOS_MINIMUM, one per side. They are generated
placeholder cards that say "Demo photo" with the side and the registration,
not photographs of real vehicles: no licensed photo exists for every side of
every model (D23), and a representative photo must never pose as the vehicle
itself (B12). An Administrator replaces them with real photographs (Fleet.Add,
N3). Like the demo vehicle documents, they are not audited one by one.

Plain `seed_demo` data: no append-only rows, so `--reset` keeps working (a
reset deletes the photos with their vehicles; the files are kept and reused).
"""

import io
from collections.abc import Callable

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw, ImageFont

from .models import Vehicle, VehiclePhoto

SIZE = (960, 640)
BACKGROUND = (226, 232, 236)  # a pale grey-blue card
INK = (31, 41, 51)


def _card(lines: list[str]) -> bytes:
    image = Image.new("RGB", SIZE, BACKGROUND)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=44)
    y = SIZE[1] // 2 - 40 * len(lines)
    for line in lines:
        width = draw.textlength(line, font=font)
        draw.text(((SIZE[0] - width) / 2, y), line, fill=INK, font=font)
        y += 80
    out = io.BytesIO()
    image.save(out, "JPEG", quality=80)
    return out.getvalue()


def _photo_key(vehicle: Vehicle, side: str) -> str:
    """One stable object key per vehicle and side, so a re-run reuses the file (SI-3)."""
    name = f"vehicles/photos/demo/{vehicle.registration_no}-{side.lower()}.jpg"
    if not default_storage.exists(name):
        lines = [
            "Demo photo",
            f"{vehicle.brand} {vehicle.model}",
            f"{side}, {vehicle.registration_no}",
        ]
        default_storage.save(name, ContentFile(_card(lines)))
    return name


def seed_demo_photos(count: Callable[[str, bool], None]) -> None:
    """Top every demo vehicle up to the Fleet.Add minimum of photographs."""
    sides = settings.HANDOVER_PHOTO_SIDES  # Front, Rear, Left, Right
    vehicles = Vehicle.objects.filter(chassis_number__startswith="DEMO").prefetch_related("photos")
    for vehicle in vehicles:
        have = len(vehicle.photos.all())
        for position in range(have, settings.VEHICLE_PHOTOS_MINIMUM):
            side = sides[position % len(sides)]
            VehiclePhoto.objects.create(
                vehicle=vehicle, image=_photo_key(vehicle, side), position=position
            )
            count("vehicle photos", True)
