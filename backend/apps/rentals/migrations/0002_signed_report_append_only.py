"""Handover.Sign: a signed condition report "cannot subsequently be altered".

The model guards in rentals/models.py give a clear error; these triggers
enforce the same rule for raw SQL and any path that bypasses the ORM, as
for invoices and ledger entries. An unsigned report stays editable (it is
filled in, then signed). vrms_reject_modification() comes from
core.0001_initial.
"""

from django.db import migrations

REPORT_TRIGGER_SQL = """
CREATE TRIGGER rentals_conditionreport_signed_append_only
BEFORE UPDATE OR DELETE ON rentals_conditionreport
FOR EACH ROW WHEN (OLD.signature <> '')
EXECUTE FUNCTION vrms_reject_modification();
"""
REPORT_TRIGGER_REVERSE_SQL = (
    "DROP TRIGGER IF EXISTS rentals_conditionreport_signed_append_only "
    "ON rentals_conditionreport;"
)

# A photo is part of the signed document: none may be added to, changed on
# or removed from a signed report.
PHOTO_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION rentals_reject_photo_change_on_signed_report() RETURNS trigger AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM rentals_conditionreport
        WHERE signature <> ''
          AND id IN (
              CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE NEW.report_id END,
              CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.report_id END
          )
    ) THEN
        RAISE EXCEPTION 'VRMS: % of a photo on a signed condition report is not permitted', TG_OP
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER rentals_conditionphoto_signed_append_only
BEFORE INSERT OR UPDATE OR DELETE ON rentals_conditionphoto
FOR EACH ROW EXECUTE FUNCTION rentals_reject_photo_change_on_signed_report();
"""
PHOTO_FUNCTION_REVERSE_SQL = """
DROP TRIGGER IF EXISTS rentals_conditionphoto_signed_append_only ON rentals_conditionphoto;
DROP FUNCTION IF EXISTS rentals_reject_photo_change_on_signed_report();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("rentals", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(REPORT_TRIGGER_SQL, REPORT_TRIGGER_REVERSE_SQL),
        migrations.RunSQL(PHOTO_FUNCTION_SQL, PHOTO_FUNCTION_REVERSE_SQL),
    ]
