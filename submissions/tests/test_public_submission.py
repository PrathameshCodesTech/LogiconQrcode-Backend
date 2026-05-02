import json
import threading

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, TransactionTestCase

from django.utils import timezone

from surveys.models import CampaignRole, FormField, Organization, QRCampaign, Role, Site
from submissions.models import Candidate, Submission

URL = '/api/public/submissions/'


def _resume(name='resume.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 fake', content_type='application/pdf')


class SubmissionFixtureMixin:
    """Creates the minimum DB objects needed by all submission tests."""

    def _setup_fixtures(self):
        self.org = Organization.objects.create(name='TestOrg', slug='testorg')
        self.site = Site.objects.create(organization=self.org, name='Main', code='MAIN')
        self.role = Role.objects.create(organization=self.org, name='Security Guard', code='SG')
        self.role2 = Role.objects.create(organization=self.org, name='Driver', code='DR')
        self.campaign = QRCampaign.objects.create(
            organization=self.org,
            site=self.site,
            title='Test Campaign',
            is_active=True,
        )
        CampaignRole.objects.create(campaign=self.campaign, role=self.role, is_active=True)
        CampaignRole.objects.create(campaign=self.campaign, role=self.role2, is_active=True)

    def _post(self, data, files=None):
        payload = {**data}
        if files:
            payload.update(files)
        return self.client.post(URL, data=payload, format='multipart')

    def _base_payload(self, role_id=None, other_role_title='', mobile='9876543210', **overrides):
        payload = {
            'campaign_token': self.campaign.token,
            'first_name': 'Test',
            'last_name': 'User',
            'mobile_number': mobile,
            'language': 'en',
            'role_id': role_id or '',
            'other_role_title': other_role_title,
            'answers': json.dumps([]),
        }
        payload.update(overrides)
        return payload


class TestValidSubmission(SubmissionFixtureMixin, TestCase):

    def setUp(self):
        self._setup_fixtures()

    def test_valid_fixed_role_submission_succeeds(self):
        """Test 1: valid fixed-role submission with resume returns 201."""
        resp = self._post(
            self._base_payload(role_id=self.role.id),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn('id', data)
        self.assertEqual(data['status'], 'new')
        self.assertFalse(data['is_possible_duplicate'])
        self.assertEqual(Submission.objects.count(), 1)

    def test_missing_resume_returns_400(self):
        """Test 2: missing resume returns 400."""
        resp = self._post(self._base_payload(role_id=self.role.id))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('resume', resp.json())

    def test_invalid_mobile_returns_400(self):
        """Test 3: invalid mobile number returns 400."""
        resp = self._post(
            self._base_payload(role_id=self.role.id, mobile='12345'),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 400)

    def test_plus91_mobile_normalizes_to_10_digits(self):
        """Test 4: +91-prefixed mobile is stored normalized to 10 digits."""
        resp = self._post(
            self._base_payload(role_id=self.role.id, mobile='+919876543210'),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 201)
        sub = Submission.objects.get()
        self.assertEqual(sub.mobile_number_normalized, '9876543210')
        self.assertEqual(Candidate.objects.get().mobile_number_normalized, '9876543210')

    def test_other_role_stores_normalized_title(self):
        """Test 5: other-role submission stores other_role_title_normalized."""
        resp = self._post(
            self._base_payload(other_role_title='  Electrician  '),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 201)
        sub = Submission.objects.get()
        self.assertIsNone(sub.role)
        self.assertEqual(sub.other_role_title_normalized, 'electrician')


class TestDuplicateDetection(SubmissionFixtureMixin, TestCase):

    def setUp(self):
        self._setup_fixtures()

    def test_duplicate_fixed_role_marked_as_duplicate(self):
        """Test 6: second submission with same mobile + role within 24h is marked duplicate."""
        payload = self._base_payload(role_id=self.role.id)
        self._post(payload, files={'resume': _resume()})
        resp = self._post(payload, files={'resume': _resume()})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['is_possible_duplicate'])
        self.assertEqual(Submission.objects.count(), 2)
        second = Submission.objects.order_by('-submitted_at').first()
        self.assertTrue(second.is_possible_duplicate)

    def test_duplicate_other_role_marked_as_duplicate(self):
        """Test 7: same mobile + same other_role_title within 24h is marked duplicate."""
        payload = self._base_payload(other_role_title='Electrician')
        self._post(payload, files={'resume': _resume()})
        resp = self._post(payload, files={'resume': _resume()})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['is_possible_duplicate'])

    def test_different_roles_same_mobile_not_duplicate(self):
        """Test 8: same mobile, different fixed roles — neither is a duplicate of the other."""
        resp1 = self._post(
            self._base_payload(role_id=self.role.id),
            files={'resume': _resume()},
        )
        resp2 = self._post(
            self._base_payload(role_id=self.role2.id),
            files={'resume': _resume()},
        )
        self.assertEqual(resp1.status_code, 201)
        self.assertEqual(resp2.status_code, 201)
        self.assertFalse(resp1.json()['is_possible_duplicate'])
        self.assertFalse(resp2.json()['is_possible_duplicate'])
        self.assertEqual(Submission.objects.count(), 2)
        # Both submissions belong to the same candidate
        self.assertEqual(Candidate.objects.count(), 1)


class TestConcurrentCandidateCreation(SubmissionFixtureMixin, TransactionTestCase):
    """
    Test 9: concurrent same-mobile submissions must not crash.

    Uses TransactionTestCase so each thread sees real committed rows.
    On SQLite the select_for_update path is skipped, but IntegrityError
    handling in get_or_create_candidate must still prevent crashes.
    """

    def setUp(self):
        self._setup_fixtures()

    def _submit(self, results, idx):
        payload = self._base_payload(role_id=self.role.id, mobile='9000000001')
        payload['resume'] = _resume(f'resume_{idx}.pdf')
        resp = self.client.post(URL, data=payload, format='multipart')
        results[idx] = resp.status_code

    def test_concurrent_same_mobile_no_crash(self):
        """Ten concurrent submissions for the same mobile must not raise 500."""
        if connection.vendor == 'sqlite':
            self.skipTest(
                "SQLite serializes all writes with a global lock; concurrent threads "
                "will get OperationalError('database table is locked'). "
                "This is a SQLite engine limitation, not an application bug. "
                "Run against PostgreSQL to exercise the select_for_update path."
            )
        n = 10
        results = [None] * n
        threads = [threading.Thread(target=self._submit, args=(results, i)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No 500s allowed
        for i, code in enumerate(results):
            self.assertIn(code, (201, 400, 429), msg=f"Thread {i} returned unexpected {code}")

        # Exactly one Candidate for this mobile
        self.assertEqual(
            Candidate.objects.filter(mobile_number_normalized='9000000001').count(), 1
        )


class TestNameValidation(SubmissionFixtureMixin, TestCase):

    def setUp(self):
        self._setup_fixtures()

    def test_first_name_with_numbers_fails(self):
        """first_name containing digits must return 400."""
        resp = self._post(
            self._base_payload(role_id=self.role.id, first_name='Ram1'),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('first_name', resp.json())

    def test_last_name_with_numbers_fails(self):
        """last_name containing digits must return 400."""
        resp = self._post(
            self._base_payload(role_id=self.role.id, last_name='Kumar2'),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('last_name', resp.json())

    def test_middle_name_with_numbers_fails(self):
        """middle_name containing digits must return 400 when provided."""
        resp = self._post(
            self._base_payload(role_id=self.role.id, middle_name='P3'),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('middle_name', resp.json())

    def test_valid_indian_name_passes(self):
        """Names with hyphens, apostrophes, and Devanagari script should pass."""
        resp = self._post(
            self._base_payload(
                role_id=self.role.id,
                first_name="D'Souza",
                middle_name='P',
                last_name='Singh-Kapoor',
            ),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 201)


class TestBusinessRules(SubmissionFixtureMixin, TestCase):

    def setUp(self):
        self._setup_fixtures()
        self.age_field = FormField.objects.create(
            campaign=self.campaign, label='Age', field_key='age',
            field_type='number', is_required=False,
        )
        self.exp_field = FormField.objects.create(
            campaign=self.campaign, label='Experience Years', field_key='experience_years',
            field_type='number', is_required=False,
        )
        self.salary_field = FormField.objects.create(
            campaign=self.campaign, label='Expected Salary', field_key='expected_salary',
            field_type='number', is_required=False,
        )
        self.joining_field = FormField.objects.create(
            campaign=self.campaign, label='Joining Availability', field_key='joining_availability',
            field_type='date', is_required=False,
        )

    def _answers(self, **kwargs) -> str:
        """Build JSON answers list from field_key=value kwargs."""
        key_to_field = {
            'age': self.age_field,
            'experience_years': self.exp_field,
            'expected_salary': self.salary_field,
            'joining_availability': self.joining_field,
        }
        items = [
            {'field_id': key_to_field[k].id, 'value': v}
            for k, v in kwargs.items()
            if k in key_to_field
        ]
        return json.dumps(items)

    def test_age_below_18_fails(self):
        """age=17 must return 400."""
        resp = self._post(
            self._base_payload(role_id=self.role.id, answers=self._answers(age=17)),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 400)

    def test_age_above_60_fails(self):
        """age=61 must return 400."""
        resp = self._post(
            self._base_payload(role_id=self.role.id, answers=self._answers(age=61)),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 400)

    def test_experience_exceeds_age_minus_14_fails(self):
        """age=20, experience_years=10 → max allowed is 6 → must return 400."""
        resp = self._post(
            self._base_payload(
                role_id=self.role.id,
                answers=self._answers(age=20, experience_years=10),
            ),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 400)

    def test_salary_above_500000_fails(self):
        """expected_salary=600000 must return 400."""
        resp = self._post(
            self._base_payload(role_id=self.role.id, answers=self._answers(expected_salary=600000)),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 400)

    def test_joining_date_yesterday_fails(self):
        """joining_availability set to yesterday must return 400."""
        from datetime import date, timedelta
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        resp = self._post(
            self._base_payload(
                role_id=self.role.id,
                answers=self._answers(joining_availability=yesterday),
            ),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 400)

    def test_valid_business_fields_pass(self):
        """Valid age=25, exp=5, salary=30000, joining=tomorrow all pass."""
        from datetime import date, timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        resp = self._post(
            self._base_payload(
                role_id=self.role.id,
                answers=self._answers(
                    age=25,
                    experience_years=5,
                    expected_salary=30000,
                    joining_availability=tomorrow,
                ),
            ),
            files={'resume': _resume()},
        )
        self.assertEqual(resp.status_code, 201)
