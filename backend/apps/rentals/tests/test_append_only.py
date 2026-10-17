"""Handover.Sign: a signed condition report "cannot subsequently be altered", by any path.

The model guards are in test_models.py; these prove the database triggers
of migration 0002 refuse raw SQL too, as for invoices and ledger entries.
"""

import pytest
from django.db import IntegrityError, connection, transaction

from apps.rentals.tests.factories import ConditionPhotoFactory, ConditionReportFactory

pytestmark = pytest.mark.django_db


def _sql(statement: str, params: list) -> None:
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(statement, params)


def test_raw_update_of_a_signed_report_is_refused():
    report = ConditionReportFactory(signed=True)
    with pytest.raises(IntegrityError, match="append-only"):
        _sql("UPDATE rentals_conditionreport SET fuel_level = 10 WHERE id = %s", [report.pk])


def test_raw_delete_of_a_signed_report_is_refused():
    report = ConditionReportFactory(signed=True)
    with pytest.raises(IntegrityError, match="append-only"):
        _sql("DELETE FROM rentals_conditionreport WHERE id = %s", [report.pk])


def test_raw_unsigning_is_refused():
    report = ConditionReportFactory(signed=True)
    with pytest.raises(IntegrityError):
        _sql("UPDATE rentals_conditionreport SET signature = '' WHERE id = %s", [report.pk])


def test_an_unsigned_report_can_still_be_filled_in_and_signed():
    report = ConditionReportFactory()
    _sql("UPDATE rentals_conditionreport SET fuel_level = 10 WHERE id = %s", [report.pk])
    _sql(
        "UPDATE rentals_conditionreport SET signature = 'rentals/signatures/x.png' WHERE id = %s",
        [report.pk],
    )
    report.refresh_from_db()
    assert report.fuel_level == 10 and report.is_signed_in_db


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE rentals_conditionphoto SET caption = 'Changed' WHERE id = %s",
        "DELETE FROM rentals_conditionphoto WHERE id = %s",
    ],
    ids=["update", "delete"],
)
def test_raw_change_of_a_signed_reports_photo_is_refused(statement):
    photo = ConditionPhotoFactory()
    _sql(
        "UPDATE rentals_conditionreport SET signature = 'rentals/signatures/x.png' WHERE id = %s",
        [photo.report_id],
    )
    with pytest.raises(IntegrityError, match="signed condition report"):
        _sql(statement, [photo.pk])


def test_raw_insert_of_a_photo_on_a_signed_report_is_refused():
    report = ConditionReportFactory(signed=True)
    with pytest.raises(IntegrityError, match="signed condition report"):
        _sql(
            "INSERT INTO rentals_conditionphoto (report_id, image, caption, uploaded_at) "
            "VALUES (%s, 'rentals/photos/x.jpg', 'Extra', now())",
            [report.pk],
        )


def test_photos_of_an_unsigned_report_can_change():
    photo = ConditionPhotoFactory()
    _sql("UPDATE rentals_conditionphoto SET caption = 'Rear' WHERE id = %s", [photo.pk])
    _sql("DELETE FROM rentals_conditionphoto WHERE id = %s", [photo.pk])
