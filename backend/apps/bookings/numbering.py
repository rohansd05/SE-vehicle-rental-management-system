"""Gap-free sequential numbers: booking references (Book.Done.Store), invoices (Pay.Invoice).

A transaction-scoped PostgreSQL advisory lock per sequence serialises the
"read the last number, add one" step, so two concurrent confirmations never
receive the same number; the unique constraints on the columns stay as the
last line of defence. Must be called inside transaction.atomic().
"""

from django.db import connection, transaction
from django.db.models import Model


class SequenceExhaustedError(Exception):
    """Every number of this prefix is used (for example a 10,000th booking in one day)."""


def next_in_sequence(model: type[Model], field: str, prefix: str, width: int) -> str:
    """The next `prefix` + zero-padded number for `model.field`, e.g. VRMS-20261020-0001."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("next_in_sequence() must run inside transaction.atomic().")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))", [f"{model._meta.label}:{prefix}"]
        )
    last = (
        model.objects.filter(**{f"{field}__startswith": prefix})
        .order_by(f"-{field}")
        .values_list(field, flat=True)
        .first()
    )
    number = int(last[len(prefix) :]) + 1 if last else 1
    if number >= 10**width:
        raise SequenceExhaustedError(f"No numbers left for {prefix}.")
    return f"{prefix}{number:0{width}d}"
