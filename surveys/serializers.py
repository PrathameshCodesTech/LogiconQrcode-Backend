from rest_framework import serializers
from .models import Organization, Site, Role, QRCampaign, CampaignRole, FormField
from .services import shuffle_fields_if_enabled
from .constants import SUPPORTED_LANGUAGES, LANGUAGE_NATIVE_LABELS


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = '__all__'


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'


class CampaignRoleSerializer(serializers.ModelSerializer):
    role_detail = RoleSerializer(source='role', read_only=True)

    class Meta:
        model = CampaignRole
        fields = ['id', 'campaign', 'role', 'role_detail', 'is_active']


class FormFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormField
        fields = '__all__'


class QRCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRCampaign
        fields = '__all__'
        read_only_fields = ['token', 'created_at', 'updated_at']


class PublicSiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ['id', 'name', 'code', 'city', 'state']


class PublicRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'code']


class PublicFormFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormField
        fields = [
            'id', 'label', 'field_key', 'field_type', 'help_text',
            'placeholder', 'options', 'is_required', 'sort_order',
            'min_length', 'max_length', 'min_value', 'max_value', 'role',
            'translations',
        ]


class PublicCampaignSerializer(serializers.ModelSerializer):
    site = PublicSiteSerializer(read_only=True)
    roles = serializers.SerializerMethodField()
    common_fields = serializers.SerializerMethodField()
    role_fields = serializers.SerializerMethodField()
    settings = serializers.SerializerMethodField()
    languages = serializers.SerializerMethodField()

    class Meta:
        model = QRCampaign
        fields = [
            'id', 'title', 'token', 'site', 'roles', 'common_fields', 'role_fields', 'settings',
            'default_language', 'enabled_languages', 'languages',
        ]

    def get_roles(self, obj):
        active_roles = obj.campaign_roles.filter(is_active=True).select_related('role')
        return PublicRoleSerializer([cr.role for cr in active_roles], many=True).data

    def get_common_fields(self, obj):
        fields = obj.form_fields.filter(is_active=True, role__isnull=True).order_by('sort_order', 'id')
        fields = shuffle_fields_if_enabled(fields, obj)
        return PublicFormFieldSerializer(fields, many=True).data

    def get_role_fields(self, obj):
        fields = obj.form_fields.filter(is_active=True, role__isnull=False).order_by('sort_order', 'id')
        result = {}
        for f in fields:
            key = str(f.role_id)
            if key not in result:
                result[key] = []
            result[key].append(PublicFormFieldSerializer(f).data)
        if obj.shuffle_fields:
            import random

            for values in result.values():
                random.shuffle(values)
        return result

    def get_settings(self, obj):
        return {
            'shuffle_fields': obj.shuffle_fields,
            'requires_otp': obj.requires_otp,
            'allow_duplicates': obj.allow_duplicates,
        }

    def get_languages(self, obj):
        lang_map = dict(SUPPORTED_LANGUAGES)
        result = []
        for code in (obj.enabled_languages or ['en']):
            if code in lang_map:
                result.append({
                    'code': code,
                    'label': lang_map[code],
                    'native_label': LANGUAGE_NATIVE_LABELS.get(code, lang_map[code]),
                })
        return result
