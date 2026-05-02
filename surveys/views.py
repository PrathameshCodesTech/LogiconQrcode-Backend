import io
import qrcode
from django.conf import settings as django_settings
from django.http import HttpResponse
from rest_framework import viewsets, generics, permissions
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from .models import Organization, Site, Role, QRCampaign, CampaignRole, FormField
from .serializers import (
    OrganizationSerializer, SiteSerializer, RoleSerializer,
    QRCampaignSerializer, CampaignRoleSerializer, FormFieldSerializer,
    PublicCampaignSerializer,
)
from .services import get_public_campaign, is_campaign_active


class PublicCampaignDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PublicCampaignSerializer

    def get_object(self):
        token = self.kwargs['token']
        campaign = get_public_campaign(token)
        if not campaign or not is_campaign_active(campaign):
            raise NotFound("Campaign not found or inactive.")
        return campaign


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'slug']


class SiteViewSet(viewsets.ModelViewSet):
    queryset = Site.objects.select_related('organization').all()
    serializer_class = SiteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['organization', 'is_active']
    search_fields = ['name', 'code', 'city']


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.select_related('organization').all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['organization', 'is_active']
    search_fields = ['name', 'code']


class QRCampaignViewSet(viewsets.ModelViewSet):
    queryset = QRCampaign.objects.select_related('organization', 'site').all()
    serializer_class = QRCampaignSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['organization', 'site', 'is_active']
    search_fields = ['title', 'token']
    http_method_names = ['get', 'post', 'patch', 'head', 'options']


class CampaignQRCodeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            campaign = QRCampaign.objects.get(pk=pk)
        except QRCampaign.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Campaign not found.")

        frontend_url = getattr(django_settings, 'FRONTEND_URL', 'http://localhost:5173')
        apply_url = f"{frontend_url}/apply/{campaign.token}"

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(apply_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        filename = f"qr_{campaign.token[:12]}.png"
        response = HttpResponse(buffer.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Campaign-Title'] = campaign.title
        response['X-Apply-URL'] = apply_url
        return response


class FormFieldViewSet(viewsets.ModelViewSet):
    queryset = FormField.objects.select_related('campaign', 'role').all()
    serializer_class = FormFieldSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['campaign', 'role', 'is_active', 'field_type']
    search_fields = ['label', 'field_key']
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
