from django.db import models
from django.contrib.auth import get_user_model
from surveys.constants import SUPPORTED_LANGUAGES

User = get_user_model()


class Candidate(models.Model):
    mobile_number = models.CharField(max_length=20)
    mobile_number_normalized = models.CharField(max_length=10, unique=True)
    latest_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['mobile_number_normalized']),
        ]

    def __str__(self):
        return f"{self.mobile_number_normalized} ({self.latest_name})"


class Submission(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
        ('contacted', 'Contacted'),
        ('hired', 'Hired'),
        ('duplicate', 'Duplicate'),
    ]

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='submissions')
    campaign = models.ForeignKey('surveys.QRCampaign', on_delete=models.CASCADE, related_name='submissions')
    site = models.ForeignKey('surveys.Site', on_delete=models.SET_NULL, null=True, blank=True, related_name='submissions')
    role = models.ForeignKey('surveys.Role', on_delete=models.SET_NULL, null=True, blank=True, related_name='submissions')
    full_name = models.CharField(max_length=200, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    other_role_title = models.CharField(max_length=200, blank=True)
    other_role_title_normalized = models.CharField(max_length=200, blank=True)
    mobile_number = models.CharField(max_length=20)
    mobile_number_normalized = models.CharField(max_length=10)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    language = models.CharField(max_length=10, choices=SUPPORTED_LANGUAGES, default='en')
    is_possible_duplicate = models.BooleanField(default=False)
    duplicate_reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['mobile_number_normalized']),
            models.Index(fields=['status']),
            models.Index(fields=['submitted_at']),
            models.Index(fields=['campaign']),
            models.Index(fields=['role']),
            models.Index(fields=['site']),
            # Composite indexes for duplicate detection and admin list queries
            models.Index(fields=['campaign', 'mobile_number_normalized']),
            models.Index(fields=['campaign', 'mobile_number_normalized', 'role']),
            models.Index(fields=['campaign', 'mobile_number_normalized', 'other_role_title_normalized']),
            models.Index(fields=['candidate', 'campaign', 'submitted_at']),
            models.Index(fields=['campaign', 'status', 'submitted_at']),
        ]

    def __str__(self):
        return f"Submission {self.id} - {self.mobile_number_normalized}"


class SubmissionAnswer(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='answers')
    field = models.ForeignKey('surveys.FormField', on_delete=models.SET_NULL, null=True, related_name='answers')
    field_label_snapshot = models.CharField(max_length=200)
    field_type_snapshot = models.CharField(max_length=20)
    value = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Answer for {self.field_label_snapshot}"


class SubmissionDocument(models.Model):
    DOCUMENT_TYPES = [
        ('resume', 'Resume'),
        ('id_proof', 'ID Proof'),
        ('certificate', 'Certificate'),
        ('other', 'Other'),
    ]

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='documents')
    field = models.ForeignKey('surveys.FormField', on_delete=models.SET_NULL, null=True, blank=True, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='other')
    file = models.FileField(upload_to='submission_documents/')
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document_type} - {self.original_filename}"


class SubmissionReview(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='reviews')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews')
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Review {self.submission_id}: {self.old_status} -> {self.new_status}"
