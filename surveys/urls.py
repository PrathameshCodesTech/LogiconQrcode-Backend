from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('admin/organizations', views.OrganizationViewSet, basename='admin-organizations')
router.register('admin/sites', views.SiteViewSet, basename='admin-sites')
router.register('admin/roles', views.RoleViewSet, basename='admin-roles')
router.register('admin/campaigns', views.QRCampaignViewSet, basename='admin-campaigns')
router.register('admin/form-fields', views.FormFieldViewSet, basename='admin-form-fields')

urlpatterns = [
    path('public/campaigns/<str:token>/', views.PublicCampaignDetailView.as_view(), name='public-campaign-detail'),
    path('admin/campaigns/<int:pk>/qrcode/', views.CampaignQRCodeView.as_view(), name='admin-campaign-qrcode'),
] + router.urls
