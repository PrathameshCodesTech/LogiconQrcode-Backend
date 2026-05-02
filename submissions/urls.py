from django.urls import path

from . import views

urlpatterns = [
    path('public/submissions/', views.PublicSubmissionCreateView.as_view(), name='public-submission-create'),
    path('admin/submissions/', views.AdminSubmissionListView.as_view(), name='admin-submission-list'),
    path('admin/submissions/export/', views.AdminSubmissionExportView.as_view(), name='admin-submission-export'),
    path('admin/submissions/<int:pk>/', views.AdminSubmissionDetailView.as_view(), name='admin-submission-detail'),
    path('admin/submissions/<int:pk>/status/', views.AdminSubmissionStatusUpdateView.as_view(), name='admin-submission-status'),
    path('admin/submissions/<int:pk>/resume-url/', views.AdminSubmissionResumeUrlView.as_view(), name='admin-submission-resume-url'),
]
