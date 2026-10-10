"""Pay.Invoice, Pay.Ledger, History.Immutable: no UPDATE or DELETE, by any path."""

import pytest
from django.db import IntegrityError, connection, transaction

from apps.core.exceptions import ImmutableRecordError
from apps.payments.tests.factories import (
    InvoiceAdjustmentFactory,
    InvoiceFactory,
    InvoiceLineFactory,
    LedgerEntryFactory,
)

pytestmark = pytest.mark.django_db

CASES = [
    pytest.param(InvoiceFactory, "tax_amount", id="Invoice"),
    pytest.param(InvoiceLineFactory, "amount", id="InvoiceLine"),
    pytest.param(InvoiceAdjustmentFactory, "amount", id="InvoiceAdjustment"),
    pytest.param(LedgerEntryFactory, "amount", id="LedgerEntry"),
]


@pytest.mark.parametrize(("factory_class", "field"), CASES)
def test_orm_save_of_existing_row_raises(factory_class, field):
    row = factory_class()
    setattr(row, field, 1)
    with pytest.raises(ImmutableRecordError):
        row.save()


@pytest.mark.parametrize(("factory_class", "field"), CASES)
def test_orm_delete_raises(factory_class, field):
    with pytest.raises(ImmutableRecordError):
        factory_class().delete()


@pytest.mark.parametrize(("factory_class", "field"), CASES)
def test_queryset_update_and_delete_raise(factory_class, field):
    row = factory_class()
    queryset = type(row).objects.filter(pk=row.pk)
    with pytest.raises(ImmutableRecordError):
        queryset.update(**{field: 1})
    with pytest.raises(ImmutableRecordError):
        queryset.delete()


@pytest.mark.parametrize(("factory_class", "field"), CASES)
def test_raw_sql_update_raises(factory_class, field):
    row = factory_class()
    table = row._meta.db_table
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET {field} = 1 WHERE id = %s", [row.pk])


@pytest.mark.parametrize(("factory_class", "field"), CASES)
def test_raw_sql_delete_raises(factory_class, field):
    row = factory_class()
    table = row._meta.db_table
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {table} WHERE id = %s", [row.pk])
