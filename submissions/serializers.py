import json
import re
from datetime import datetime
from django.db.models import Q
from rest_framework import serializers

from .models import Candidate, Submission, SubmissionAnswer, SubmissionDocument, SubmissionReview
from .validators import validate_mobile_number, validate_campaign_token, validate_campaign_role
from surveys.models import FormField


class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = '__all__'


class SubmissionAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionAnswer
        fields = ['id', 'field', 'field_label_snapshot', 'field_type_snapshot', 'value', 'created_at']


class SubmissionDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionDocument
        fields = '__all__'


class SubmissionReviewSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionReview
        fields = ['id', 'old_status', 'new_status', 'note', 'reviewed_by_name', 'created_at']

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None


def get_applied_role_display(obj) -> str:
    if obj.role:
        return obj.role.name
    if obj.other_role_title:
        return f"Other: {obj.other_role_title}"
    return '-'


def count_distinct_roles_for_mobile_campaign(obj) -> int:
    role_keys = set()
    submissions = Submission.objects.filter(
        campaign=obj.campaign,
        mobile_number_normalized=obj.mobile_number_normalized,
    ).values_list('role_id', 'other_role_title_normalized')
    for role_id, other_role_title in submissions:
        if role_id:
            role_keys.add(f"role:{role_id}")
        elif other_role_title:
            role_keys.add(f"other:{other_role_title}")
    return len(role_keys)


class SubmissionListSerializer(serializers.ModelSerializer):
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)
    role_name = serializers.SerializerMethodField()
    site_name = serializers.CharField(source='site.name', read_only=True)
    same_mobile_campaign_count = serializers.SerializerMethodField()
    has_other_applications = serializers.SerializerMethodField()
    applied_role_display = serializers.SerializerMethodField()
    first_name = serializers.CharField(read_only=True)
    middle_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    other_role_title = serializers.CharField(read_only=True)

    class Meta:
        model = Submission
        fields = [
            'id', 'mobile_number', 'full_name', 'first_name', 'middle_name',
            'last_name', 'campaign_title', 'role_name', 'site_name', 'status',
            'language', 'is_possible_duplicate', 'submitted_at',
            'same_mobile_campaign_count', 'has_other_applications',
            'applied_role_display', 'other_role_title',
        ]

    def get_role_name(self, obj):
        return obj.role.name if obj.role else (obj.other_role_title or '-')

    def get_applied_role_display(self, obj):
        return get_applied_role_display(obj)

    def get_same_mobile_campaign_count(self, obj):
        return count_distinct_roles_for_mobile_campaign(obj)

    def get_has_other_applications(self, obj):
        return Submission.objects.filter(
            campaign=obj.campaign,
            mobile_number_normalized=obj.mobile_number_normalized,
        ).count() > 1


class OtherApplicationSerializer(serializers.ModelSerializer):
    role_name = serializers.SerializerMethodField()
    applied_role_display = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            'id', 'full_name', 'mobile_number', 'role_name', 'status',
            'is_possible_duplicate', 'submitted_at', 'other_role_title',
            'applied_role_display',
        ]

    def get_role_name(self, obj):
        return obj.role.name if obj.role else (obj.other_role_title or '-')

    def get_applied_role_display(self, obj):
        return get_applied_role_display(obj)


class SubmissionDetailSerializer(serializers.ModelSerializer):
    answers = SubmissionAnswerSerializer(many=True, read_only=True)
    documents = SubmissionDocumentSerializer(many=True, read_only=True)
    reviews = serializers.SerializerMethodField()
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)
    role_name = serializers.SerializerMethodField()
    site_name = serializers.CharField(source='site.name', read_only=True)
    other_applications = serializers.SerializerMethodField()
    applied_role_display = serializers.SerializerMethodField()
    first_name = serializers.CharField(read_only=True)
    middle_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    other_role_title = serializers.CharField(read_only=True)

    class Meta:
        model = Submission
        fields = '__all__'

    def get_reviews(self, obj):
        return SubmissionReviewSerializer(obj.reviews.all()[:10], many=True).data

    def get_role_name(self, obj):
        return obj.role.name if obj.role else (obj.other_role_title or '-')

    def get_applied_role_display(self, obj):
        return get_applied_role_display(obj)

    def get_other_applications(self, obj):
        others = Submission.objects.filter(
            campaign=obj.campaign,
            mobile_number_normalized=obj.mobile_number_normalized,
        ).exclude(id=obj.id).order_by('-submitted_at')
        return OtherApplicationSerializer(others, many=True).data


class AnswerInputSerializer(serializers.Serializer):
    field_id = serializers.IntegerField()
    value = serializers.JSONField()


def _clean_str(val):
    if not isinstance(val, str):
        return val
    stripped = val.strip()
    return stripped if stripped else val.strip()


class SubmissionCreateSerializer(serializers.Serializer):
    campaign_token = serializers.CharField()
    role_id = serializers.IntegerField(required=False, allow_null=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default='')
    middle_name = serializers.CharField(required=False, allow_blank=True, default='')
    last_name = serializers.CharField(required=False, allow_blank=True, default='')
    mobile_number = serializers.CharField()
    language = serializers.CharField(required=False, allow_blank=True, default='')
    other_role_title = serializers.CharField(required=False, allow_blank=True, default='', max_length=200)
    answers = serializers.JSONField(required=False, default=list)

    def validate_mobile_number(self, value):
        return validate_mobile_number(value)

    def validate_first_name(self, value):
        cleaned = _clean_str(value)
        if not cleaned:
            raise serializers.ValidationError("First name is required.")
        if len(cleaned) < 2:
            raise serializers.ValidationError("First name must be at least 2 characters.")
        return cleaned

    def validate_middle_name(self, value):
        if value:
            return _clean_str(value)
        return ''

    def validate_last_name(self, value):
        cleaned = _clean_str(value)
        if not cleaned:
            raise serializers.ValidationError("Last name is required.")
        if len(cleaned) < 2:
            raise serializers.ValidationError("Last name must be at least 2 characters.")
        return cleaned

    def validate_other_role_title(self, value):
        if value:
            cleaned = _clean_str(value)
            if len(cleaned) < 2:
                raise serializers.ValidationError("Role title must be at least 2 characters.")
            return cleaned
        return ''

    def validate_answers(self, value):
        if value in ('', None):
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Answers must be valid JSON.")
        if not isinstance(value, list):
            raise serializers.ValidationError("Answers must be a list.")
        normalized = []
        for answer in value:
            if not isinstance(answer, dict):
                raise serializers.ValidationError("Each answer must be an object.")
            if 'field_id' not in answer:
                raise serializers.ValidationError("Each answer must include field_id.")
            if 'value' not in answer:
                raise serializers.ValidationError("Each answer must include value.")
            try:
                field_id = int(answer['field_id'])
            except (TypeError, ValueError):
                raise serializers.ValidationError("field_id must be an integer.")
            normalized.append({'field_id': field_id, 'value': answer['value']})
        return normalized

    def validate(self, data):
        campaign = validate_campaign_token(data['campaign_token'])
        role = validate_campaign_role(campaign, data.get('role_id'))
        other_role_title = data.get('other_role_title', '').strip()

        if role and other_role_title:
            data['other_role_title'] = ''

        if not role and not other_role_title:
            raise serializers.ValidationError(
                "Please select a role or enter a role title."
            )

        data['campaign'] = campaign
        data['role'] = role

        lang = data.get('language', '').strip()
        if not lang:
            lang = campaign.default_language
        enabled = campaign.enabled_languages or ['en']
        if lang not in enabled:
            raise serializers.ValidationError(
                f"Language '{lang}' is not enabled for this campaign. "
                f"Allowed: {enabled}"
            )
        data['language'] = lang

        answers = data.get('answers', [])
        provided_field_ids = set()
        if answers:
            field_ids = [a['field_id'] for a in answers]
            fields = {
                f.id: f
                for f in FormField.objects.filter(id__in=field_ids, campaign=campaign, is_active=True)
            }
            validated_answers = []
            for ans in answers:
                field = fields.get(ans['field_id'])
                if not field:
                    raise serializers.ValidationError(
                        f"Field {ans['field_id']} does not belong to this campaign."
                    )
                if field.role_id is not None and (role is None or field.role_id != role.id):
                    raise serializers.ValidationError(
                        f"Field '{field.label}' is not valid for the selected role."
                    )
                provided_field_ids.add(field.id)
                self._validate_field_value(field, ans['value'])
                validated_answers.append({'field': field, 'value': ans['value']})
            data['answers'] = validated_answers

        self._validate_required_fields(campaign, role, provided_field_ids, data.get('answers', []))
        return data

    def _validate_required_fields(self, campaign, role, provided_field_ids, validated_answers):
        required_fields = FormField.objects.filter(
            campaign=campaign,
            is_active=True,
            is_required=True,
        ).filter(Q(role__isnull=True) | Q(role=role))
        answer_values = {
            answer['field'].id: answer['value']
            for answer in validated_answers
            if 'field' in answer
        }
        missing = []
        for field in required_fields:
            if field.id not in provided_field_ids or answer_values.get(field.id) in ('', None, []):
                missing.append(field.label)
        if missing:
            raise serializers.ValidationError(
                f"Required fields missing: {', '.join(missing)}."
            )

    def _validate_field_value(self, field, value):
        if value in ('', None, []):
            if field.is_required:
                raise serializers.ValidationError(f"'{field.label}' is required.")
            return
        if field.field_type == 'select' and field.options:
            if value not in field.options:
                raise serializers.ValidationError(
                    f"'{value}' is not a valid option for '{field.label}'."
                )
        elif field.field_type == 'multi_select' and field.options:
            if not isinstance(value, list):
                raise serializers.ValidationError(f"'{field.label}' expects a list.")
            invalid = [v for v in value if v not in field.options]
            if invalid:
                raise serializers.ValidationError(
                    f"Invalid options {invalid} for '{field.label}'."
                )
        elif field.field_type in ('text', 'textarea'):
            if not isinstance(value, str):
                raise serializers.ValidationError(f"'{field.label}' must be text.")
            if field.min_length and len(value) < field.min_length:
                raise serializers.ValidationError(
                    f"'{field.label}' must be at least {field.min_length} characters."
                )
            if field.max_length and len(value) > field.max_length:
                raise serializers.ValidationError(
                    f"'{field.label}' exceeds max length of {field.max_length}."
                )
        elif field.field_type == 'number':
            try:
                num = float(value)
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"'{field.label}' must be a number.")
            if field.min_value is not None and num < float(field.min_value):
                raise serializers.ValidationError(
                    f"'{field.label}' must be at least {field.min_value}."
                )
            if field.max_value is not None and num > float(field.max_value):
                raise serializers.ValidationError(
                    f"'{field.label}' must be at most {field.max_value}."
                )
        elif field.field_type == 'email':
            if value and not re.match(r'^[^@]+@[^@]+\.[^@]+$', str(value)):
                raise serializers.ValidationError(f"'{field.label}' must be a valid email.")
        elif field.field_type == 'date':
            if value:
                try:
                    datetime.fromisoformat(str(value))
                except ValueError:
                    raise serializers.ValidationError(
                        f"'{field.label}' must be a valid ISO date (YYYY-MM-DD)."
                    )


class SubmissionStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Submission.STATUS_CHOICES)
    note = serializers.CharField(required=False, allow_blank=True, default='')
