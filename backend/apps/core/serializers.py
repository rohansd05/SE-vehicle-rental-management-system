"""Core serializers."""

from rest_framework import serializers


class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "degraded"])
    database = serializers.ChoiceField(choices=["ok", "unreachable"])
    agency_name = serializers.CharField()
    currency = serializers.CharField()
