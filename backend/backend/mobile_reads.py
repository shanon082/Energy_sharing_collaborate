"""Bounded, stable pagination for consumer reads; never calls external systems."""

from rest_framework import serializers


class ReadPageSerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, max_value=50, default=30)
    before_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1, required=False)


def read_page(queryset, params):
    serializer = ReadPageSerializer(data=params)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    if values.get("before_id"):
        queryset = queryset.filter(pk__lt=values["before_id"])
    rows = list(queryset.order_by("-pk")[:values["limit"] + 1])
    has_more = len(rows) > values["limit"]
    rows = rows[:values["limit"]]
    return rows, {"has_more": has_more, "next_before_id": rows[-1].pk if has_more else None}
