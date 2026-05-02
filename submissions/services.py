import re
from django.db import IntegrityError, connection
from django.utils import timezone
from datetime import timedelta

from .validators import normalize_mobile, validate_submission_file, MAX_FILES_PER_SUBMISSION
from .models import (
    Candidate,
    Submission,
    SubmissionAnswer,
    SubmissionDocument,
    SubmissionReview,
)


def normalize_mobile_number(mobile: str) -> str:
    return normalize_mobile(mobile)


def normalize_other_role_title(title: str) -> str:
    """Normalize other role title for duplicate detection."""
    return ' '.join(title.strip().lower().split())


def get_or_create_candidate(mobile_normalized: str, full_name: str = '') -> tuple:
    try:
        candidate, created = Candidate.objects.get_or_create(
            mobile_number_normalized=mobile_normalized,
            defaults={'mobile_number': mobile_normalized, 'latest_name': full_name},
        )
    except IntegrityError:
        # Two concurrent requests for the same mobile hit the unique constraint.
        # The other request already inserted — fetch it instead.
        candidate = Candidate.objects.get(mobile_number_normalized=mobile_normalized)
        created = False
    if not created and full_name:
        candidate.latest_name = full_name
        candidate.save(update_fields=['latest_name', 'updated_at'])
    return candidate, created


def detect_duplicate_submission(candidate, campaign, role, other_role_title_normalized=None) -> tuple:
    threshold = timezone.now() - timedelta(hours=24)
    qs = Submission.objects.filter(
        candidate=candidate,
        campaign=campaign,
        submitted_at__gte=threshold,
    )
    if role:
        qs = qs.filter(role=role, other_role_title_normalized='')
    else:
        qs = qs.filter(role__isnull=True, other_role_title_normalized=other_role_title_normalized)

    if qs.exists():
        reason = (
            "Same mobile submitted for same campaign and role within 24 hours"
            if role else
            f"Same mobile submitted for 'Other: {other_role_title_normalized}' role within 24 hours"
        )
        return True, reason
    return False, ""


def create_submission_with_answers(validated_data: dict, request=None) -> Submission:
    campaign = validated_data['campaign']
    role = validated_data.get('role')
    other_role_title = validated_data.get('other_role_title', '').strip()
    other_role_title_normalized = normalize_other_role_title(other_role_title) if other_role_title else ''

    first_name = validated_data.get('first_name', '').strip()
    middle_name = validated_data.get('middle_name', '').strip()
    last_name = validated_data.get('last_name', '').strip()
    full_name = ' '.join(part for part in [first_name, middle_name, last_name] if part)

    mobile = validated_data['mobile_number']
    mobile_normalized = normalize_mobile_number(mobile)

    candidate, _ = get_or_create_candidate(mobile_normalized, full_name)

    # On PostgreSQL, lock this candidate's row so that concurrent submissions
    # for the same mobile are serialized before duplicate detection runs.
    # SQLite does not support SELECT FOR UPDATE, so skip it there.
    if connection.vendor != 'sqlite':
        candidate = Candidate.objects.select_for_update().get(pk=candidate.pk)

    is_duplicate, duplicate_reason = detect_duplicate_submission(
        candidate, campaign, role, other_role_title_normalized
    )

    ip_address = None
    user_agent = ''
    if request:
        ip_address = _get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')

    submission = Submission.objects.create(
        candidate=candidate,
        campaign=campaign,
        site=campaign.site,
        role=role,
        full_name=full_name,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        other_role_title=other_role_title,
        other_role_title_normalized=other_role_title_normalized,
        mobile_number=mobile,
        mobile_number_normalized=mobile_normalized,
        language=validated_data.get('language', 'en'),
        is_possible_duplicate=is_duplicate,
        duplicate_reason=duplicate_reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    answers_data = validated_data.get('answers', [])
    if answers_data:
        answer_objs = [
            SubmissionAnswer(
                submission=submission,
                field=ans['field'],
                field_label_snapshot=ans['field'].label,
                field_type_snapshot=ans['field'].field_type,
                value=ans['value'],
            )
            for ans in answers_data
        ]
        SubmissionAnswer.objects.bulk_create(answer_objs)

    return submission


def create_submission_documents(submission: Submission, files) -> list:
    uploaded_files = _flatten_uploaded_files(files)
    if len(uploaded_files) > MAX_FILES_PER_SUBMISSION:
        from rest_framework import serializers

        raise serializers.ValidationError(
            f"A maximum of {MAX_FILES_PER_SUBMISSION} files can be uploaded."
        )

    for _, uploaded_file in uploaded_files:
        validate_submission_file(uploaded_file)

    documents = []
    for field_name, uploaded_file in uploaded_files:
        form_field = _get_file_form_field(submission, field_name)
        documents.append(
            SubmissionDocument.objects.create(
                submission=submission,
                field=form_field,
                document_type=_document_type_from_field_name(field_name),
                file=uploaded_file,
                original_filename=uploaded_file.name,
                content_type=getattr(uploaded_file, 'content_type', ''),
                size_bytes=uploaded_file.size,
            )
        )

    return documents


def create_review_log(submission, user, new_status: str, note: str = '') -> SubmissionReview:
    review = SubmissionReview.objects.create(
        submission=submission,
        reviewed_by=user,
        old_status=submission.status,
        new_status=new_status,
        note=note,
    )
    submission.status = new_status
    submission.save(update_fields=['status', 'updated_at'])
    return review


def _get_client_ip(request) -> str:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _flatten_uploaded_files(files) -> list:
    uploaded_files = []
    for field_name in files:
        for uploaded_file in files.getlist(field_name):
            uploaded_files.append((field_name, uploaded_file))
    return uploaded_files


def _document_type_from_field_name(field_name: str) -> str:
    normalized = field_name.lower()
    if normalized == 'resume':
        return 'resume'
    if normalized in {'id_proof', 'idproof', 'identity'}:
        return 'id_proof'
    if normalized in {'certificate', 'certificates'}:
        return 'certificate'
    return 'other'


def _get_file_form_field(submission: Submission, field_name: str):
    prefixes = ('field_', 'file_')
    for prefix in prefixes:
        if field_name.startswith(prefix):
            raw_id = field_name.replace(prefix, '', 1)
            if raw_id.isdigit():
                return submission.campaign.form_fields.filter(
                    id=int(raw_id),
                    field_type='file',
                    is_active=True,
                ).first()
    return None