import secrets
import random
from django.utils import timezone

from .models import QRCampaign


def generate_campaign_token() -> str:
    return secrets.token_urlsafe(16)


def get_public_campaign(token: str):
    try:
        return QRCampaign.objects.select_related('site', 'organization').prefetch_related(
            'campaign_roles__role', 'form_fields'
        ).get(token=token)
    except QRCampaign.DoesNotExist:
        return None


def is_campaign_active(campaign: QRCampaign) -> bool:
    if not campaign.is_active:
        return False
    now = timezone.now()
    if campaign.starts_at and campaign.starts_at > now:
        return False
    if campaign.ends_at and campaign.ends_at < now:
        return False
    return True


def shuffle_fields_if_enabled(fields, campaign: QRCampaign):
    fields = list(fields)
    if campaign.shuffle_fields:
        random.shuffle(fields)
    return fields
