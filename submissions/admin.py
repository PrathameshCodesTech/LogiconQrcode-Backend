from django.contrib import admin
from .models import Candidate, Submission, SubmissionAnswer, SubmissionDocument, SubmissionReview


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ['mobile_number_normalized', 'latest_name', 'created_at']
    search_fields = ['mobile_number_normalized', 'latest_name']


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['id', 'mobile_number', 'full_name', 'campaign', 'role', 'status', 'is_possible_duplicate', 'submitted_at']
    search_fields = ['mobile_number', 'mobile_number_normalized', 'full_name']
    list_filter = ['status', 'is_possible_duplicate', 'campaign', 'role', 'site']
    readonly_fields = ['submitted_at', 'updated_at']


@admin.register(SubmissionAnswer)
class SubmissionAnswerAdmin(admin.ModelAdmin):
    list_display = ['submission', 'field_label_snapshot', 'field_type_snapshot', 'created_at']
    search_fields = ['field_label_snapshot', 'submission__mobile_number']


@admin.register(SubmissionDocument)
class SubmissionDocumentAdmin(admin.ModelAdmin):
    list_display = ['submission', 'document_type', 'original_filename', 'size_bytes', 'created_at']


@admin.register(SubmissionReview)
class SubmissionReviewAdmin(admin.ModelAdmin):
    list_display = ['submission', 'reviewed_by', 'old_status', 'new_status', 'created_at']
    list_filter = ['new_status']
