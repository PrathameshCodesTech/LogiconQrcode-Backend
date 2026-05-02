import re
from pathlib import Path
from rest_framework import serializers

FAKE_NUMBERS = {'0000000000', '1111111111', '1234567890', '9999999999'}
ALLOWED_UPLOAD_EXTENSIONS = {'.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png'}
ALLOWED_UPLOAD_CONTENT_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/jpeg',
    'image/png',
}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
MAX_FILES_PER_SUBMISSION = 5


def normalize_mobile(mobile: str) -> str:
    mobile = mobile.strip().replace(' ', '').replace('-', '')
    if mobile.startswith('+91'):
        mobile = mobile[3:]
    elif mobile.startswith('91') and len(mobile) == 12:
        mobile = mobile[2:]
    return mobile


def validate_mobile_number(value: str) -> str:
    if not value:
        raise serializers.ValidationError("Mobile number is required.")
    normalized = normalize_mobile(value)
    if not re.match(r'^[6-9]\d{9}$', normalized):
        raise serializers.ValidationError("Enter a valid 10-digit Indian mobile number.")
    if normalized in FAKE_NUMBERS:
        raise serializers.ValidationError("Please enter a valid mobile number.")
    return normalized


def validate_campaign_token(token: str):
    from surveys.models import QRCampaign
    from django.utils import timezone

    try:
        campaign = QRCampaign.objects.get(token=token)
    except QRCampaign.DoesNotExist:
        raise serializers.ValidationError("Invalid campaign token.")

    if not campaign.is_active:
        raise serializers.ValidationError("This campaign is no longer active.")

    now = timezone.now()
    if campaign.starts_at and campaign.starts_at > now:
        raise serializers.ValidationError("This campaign has not started yet.")
    if campaign.ends_at and campaign.ends_at < now:
        raise serializers.ValidationError("This campaign has ended.")

    return campaign


def validate_campaign_role(campaign, role_id):
    if role_id is None:
        return None
    from surveys.models import CampaignRole

    try:
        cr = CampaignRole.objects.select_related('role').get(
            campaign=campaign, role_id=role_id, is_active=True
        )
        return cr.role
    except CampaignRole.DoesNotExist:
        raise serializers.ValidationError("Selected role is not valid for this campaign.")


def validate_submission_file(uploaded_file):
    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise serializers.ValidationError(
            f"File '{uploaded_file.name}' has an unsupported file type."
        )

    content_type = getattr(uploaded_file, 'content_type', '')
    if content_type and content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise serializers.ValidationError(
            f"File '{uploaded_file.name}' has an unsupported content type."
        )

    if uploaded_file.size > MAX_UPLOAD_SIZE_BYTES:
        raise serializers.ValidationError(
            f"File '{uploaded_file.name}' exceeds the 10MB limit."
        )

    return uploaded_file
