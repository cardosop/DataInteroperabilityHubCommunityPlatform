"""
Search Serializers
"""
from rest_framework import serializers
from .models import SearchIndex, SearchAnalytics


class SearchResultSerializer(serializers.Serializer):
    """Serializer for search results"""
    id = serializers.UUIDField()
    type = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    relevance_score = serializers.FloatField()
    classification = serializers.CharField(allow_null=True)
    owner_id = serializers.UUIDField(allow_null=True)
    owner_email = serializers.EmailField(allow_null=True)
    domain = serializers.CharField(allow_null=True)
    tags = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    quality_status = serializers.CharField(allow_null=True)
    compliance_status = serializers.CharField(allow_null=True)
    indexed_at = serializers.DateTimeField(allow_null=True)


class SearchResponseSerializer(serializers.Serializer):
    """Serializer for search API response"""
    results = SearchResultSerializer(many=True)
    total = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    query = serializers.CharField()
    analytics_id = serializers.UUIDField(required=False, allow_null=True)


class SearchSuggestionSerializer(serializers.Serializer):
    """Serializer for search suggestions"""
    text = serializers.CharField()
    type = serializers.CharField()
    id = serializers.UUIDField(allow_null=True)
    similarity = serializers.FloatField()


class SearchAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for search analytics"""
    class Meta:
        model = SearchAnalytics
        fields = [
            'id',
            'query',
            'query_type',
            'filters',
            'result_count',
            'no_results',
            'clicked_result_id',
            'clicked_result_type',
            'clicked_at',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SearchAnalyticsDashboardSerializer(serializers.Serializer):
    """Serializer for search analytics dashboard"""
    popular_searches = serializers.ListField(
        child=serializers.DictField()
    )
    search_trends = serializers.ListField(
        child=serializers.DictField()
    )
    no_result_queries = serializers.ListField(
        child=serializers.DictField()
    )
    click_through_rate = serializers.FloatField()
    total_searches = serializers.IntegerField()
    total_clicks = serializers.IntegerField()

