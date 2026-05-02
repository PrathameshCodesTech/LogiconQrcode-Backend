import django_filters
from .models import Submission


class SubmissionFilter(django_filters.FilterSet):
    date_from = django_filters.DateTimeFilter(field_name='submitted_at', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='submitted_at', lookup_expr='lte')
    mobile_number = django_filters.CharFilter(field_name='mobile_number_normalized', lookup_expr='icontains')
    campaign_id = django_filters.NumberFilter(field_name='campaign_id')
    site_id = django_filters.NumberFilter(field_name='site_id')

    class Meta:
        model = Submission
        fields = ['status', 'campaign_id', 'site_id']
