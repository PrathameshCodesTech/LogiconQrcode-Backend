from django.contrib import admin
from .models import Organization, Site, Role, QRCampaign, CampaignRole, FormField


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'created_at']
    search_fields = ['name', 'slug']
    list_filter = ['is_active']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'organization', 'city', 'state', 'is_active']
    search_fields = ['name', 'code', 'city']
    list_filter = ['organization', 'is_active']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'organization', 'is_active']
    search_fields = ['name', 'code']
    list_filter = ['organization', 'is_active']


@admin.register(QRCampaign)
class QRCampaignAdmin(admin.ModelAdmin):
    list_display = ['title', 'token', 'organization', 'site', 'is_active', 'starts_at', 'ends_at']
    search_fields = ['title', 'token']
    list_filter = ['organization', 'is_active']
    readonly_fields = ['token', 'created_at', 'updated_at']


@admin.register(CampaignRole)
class CampaignRoleAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'role', 'is_active']
    list_filter = ['is_active', 'campaign']


@admin.register(FormField)
class FormFieldAdmin(admin.ModelAdmin):
    list_display = ['label', 'campaign', 'role', 'field_type', 'is_required', 'sort_order', 'is_active']
    search_fields = ['label', 'field_key']
    list_filter = ['campaign', 'role', 'field_type', 'is_required', 'is_active']
    ordering = ['campaign', 'sort_order']
