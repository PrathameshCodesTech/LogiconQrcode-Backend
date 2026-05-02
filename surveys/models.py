import secrets
from django.core.exceptions import ValidationError
from django.db import models
from .constants import SUPPORTED_LANGUAGES


def default_enabled_languages():
    return ['en']


class Organization(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Site(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='sites')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class Role(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class QRCampaign(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='campaigns')
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    title = models.CharField(max_length=200)
    token = models.CharField(max_length=64, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    allow_duplicates = models.BooleanField(default=True)
    requires_otp = models.BooleanField(default=False)
    shuffle_fields = models.BooleanField(default=True)
    default_language = models.CharField(max_length=10, choices=SUPPORTED_LANGUAGES, default='en')
    enabled_languages = models.JSONField(default=default_enabled_languages)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def clean(self):
        valid_codes = {code for code, _ in SUPPORTED_LANGUAGES}
        if self.enabled_languages:
            invalid = [c for c in self.enabled_languages if c not in valid_codes]
            if invalid:
                raise ValidationError(
                    f"Invalid language codes in enabled_languages: {invalid}"
                )
        if self.default_language not in (self.enabled_languages or []):
            raise ValidationError(
                "default_language must be in enabled_languages."
            )

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(16)
        super().save(*args, **kwargs)


class CampaignRole(models.Model):
    campaign = models.ForeignKey(QRCampaign, on_delete=models.CASCADE, related_name='campaign_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='campaign_roles')
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('campaign', 'role')

    def __str__(self):
        return f"{self.campaign.title} - {self.role.name}"


class FormField(models.Model):
    FIELD_TYPES = [
        ('text', 'Text'),
        ('textarea', 'Textarea'),
        ('number', 'Number'),
        ('date', 'Date'),
        ('email', 'Email'),
        ('select', 'Select'),
        ('multi_select', 'Multi Select'),
        ('boolean', 'Boolean'),
        ('file', 'File'),
    ]

    campaign = models.ForeignKey(QRCampaign, on_delete=models.CASCADE, related_name='form_fields')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='form_fields')
    label = models.CharField(max_length=200)
    field_key = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    help_text = models.TextField(blank=True)
    placeholder = models.CharField(max_length=200, blank=True)
    options = models.JSONField(default=list)
    is_required = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    min_length = models.IntegerField(null=True, blank=True)
    max_length = models.IntegerField(null=True, blank=True)
    min_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    translations = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.label} ({self.campaign.title})"
