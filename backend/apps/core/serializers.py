"""Core serializers."""

from rest_framework import serializers

from apps.accounts.models import User

from .models import AuditLog


class AuditActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "name", "email", "role"]
        read_only_fields = fields


class AuditEntrySerializer(serializers.ModelSerializer):
    """Fleet.Audit: the user, the date and time, and the previous and new values."""

    actor = AuditActorSerializer(read_only=True, allow_null=True)
    before = serializers.JSONField(read_only=True, allow_null=True)
    after = serializers.JSONField(read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "timestamp",
            "actor",
            "action",
            "entity_type",
            "entity_id",
            "before",
            "after",
            "ip_address",
        ]
        read_only_fields = fields


class AuditFilterSerializer(serializers.Serializer):
    """Query parameters of the audit log viewer."""

    actor = serializers.CharField(required=False, allow_blank=True, default="")
    action = serializers.CharField(required=False, allow_blank=True, default="")
    entity_type = serializers.CharField(required=False, allow_blank=True, default="")
    entity_id = serializers.CharField(required=False, allow_blank=True, default="")
    date_from = serializers.DateField(required=False, allow_null=True, default=None)
    date_to = serializers.DateField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        if attrs["date_from"] and attrs["date_to"] and attrs["date_to"] < attrs["date_from"]:
            raise serializers.ValidationError({"date_to": ["The end date is before the start."]})
        return attrs


class AuditFilterOptionsSerializer(serializers.Serializer):
    actions = serializers.ListField(child=serializers.CharField())
    entity_types = serializers.ListField(child=serializers.CharField())


class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "degraded"])
    database = serializers.ChoiceField(choices=["ok", "unreachable"])
    agency_name = serializers.CharField()
    currency = serializers.CharField()
