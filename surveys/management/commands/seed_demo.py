from django.core.management.base import BaseCommand
from surveys.models import Organization, Site, Role, QRCampaign, CampaignRole, FormField
from surveys.services import generate_campaign_token


class Command(BaseCommand):
    help = 'Seed demo data for Logicon Facility Management'

    def handle(self, *args, **options):
        self.stdout.write('Seeding demo data...')

        def upsert_form_field(role, label, key, ftype, order, extra, translations):
            defaults = {
                'label': label,
                'field_type': ftype,
                'sort_order': order,
                'is_active': True,
                'is_required': False,
                'translations': translations,
            }
            defaults.update(extra)
            field, created = FormField.objects.get_or_create(
                campaign=campaign,
                field_key=key,
                role=role,
                defaults=defaults,
            )
            if not created:
                for attr, value in defaults.items():
                    setattr(field, attr, value)
                field.save(update_fields=list(defaults.keys()))
            return field

        org, _ = Organization.objects.get_or_create(
            slug='logicon-facility-management',
            defaults={'name': 'Logicon Facility Management', 'is_active': True},
        )

        site, _ = Site.objects.get_or_create(
            organization=org,
            code='MUM-01',
            defaults={
                'name': 'Mumbai Site',
                'address': '123 Industrial Area, Andheri East',
                'city': 'Mumbai',
                'state': 'Maharashtra',
                'is_active': True,
            },
        )

        role_data = [
            ('Housekeeping', 'housekeeping'),
            ('Security Guard', 'security-guard'),
            ('Electrician', 'electrician'),
            ('Plumber', 'plumber'),
            ('Supervisor', 'supervisor'),
        ]
        roles = {}
        for name, code in role_data:
            role, _ = Role.objects.get_or_create(
                organization=org,
                code=code,
                defaults={'name': name, 'is_active': True},
            )
            if role.name != name or not role.is_active:
                role.name = name
                role.is_active = True
                role.save(update_fields=['name', 'is_active'])
            roles[code] = role

        campaign, _ = QRCampaign.objects.get_or_create(
            organization=org,
            title='Logicon Facility Hiring Drive',
            defaults={
                'site': site,
                'token': generate_campaign_token(),
                'is_active': True,
                'allow_duplicates': True,
                'requires_otp': False,
                'shuffle_fields': True,
                'default_language': 'en',
                'enabled_languages': ['en', 'hi', 'mr'],
            },
        )
        campaign.site = site
        campaign.is_active = True
        campaign.allow_duplicates = True
        campaign.requires_otp = False
        campaign.shuffle_fields = True
        campaign.default_language = 'en'
        campaign.enabled_languages = ['en', 'hi', 'mr']
        if not campaign.token:
            campaign.token = generate_campaign_token()
        campaign.save(update_fields=[
            'site', 'is_active', 'allow_duplicates', 'requires_otp',
            'shuffle_fields', 'default_language', 'enabled_languages', 'token',
        ])

        for role in roles.values():
            CampaignRole.objects.get_or_create(
                campaign=campaign,
                role=role,
                defaults={'is_active': True},
            )

        FormField.objects.filter(campaign=campaign, field_key='name', role=None).update(is_active=False)

        common_fields = [
            ('Age', 'age', 'number', 0, {'min_value': 18, 'max_value': 60}, {
                'hi': {'label': 'आयु'},
                'mr': {'label': 'वय'},
            }),
            ('Gender', 'gender', 'select', 1, {'options': ['Male', 'Female', 'Other', 'Prefer not to say']}, {
                'hi': {'label': 'लिंग', 'options': ['पुरुष', 'महिला', 'अन्य', 'बताना नहीं चाहता']},
                'mr': {'label': 'लिंग', 'options': ['पुरुष', 'स्त्री', 'इतर', 'सांगणे पसंत नाही']},
            }),
            ('Current Location', 'current_location', 'text', 2, {}, {
                'hi': {'label': 'वर्तमान स्थान'},
                'mr': {'label': 'सध्याचे स्थान'},
            }),
            ('Experience Years', 'experience_years', 'number', 3, {'min_value': 0, 'max_value': 40}, {
                'hi': {'label': 'अनुभव वर्ष'},
                'mr': {'label': 'अनुभवाची वर्षे'},
            }),
            ('Expected Salary', 'expected_salary', 'number', 4, {}, {
                'hi': {'label': 'अपेक्षित वेतन'},
                'mr': {'label': 'अपेक्षित वेतन'},
            }),
            ('Joining Availability', 'joining_availability', 'date', 5, {}, {
                'hi': {'label': 'उपलब्धता तिथि'},
                'mr': {'label': 'उपलब्धतेची तारीख'},
            }),
        ]
        for label, key, ftype, order, extra, translations in common_fields:
            upsert_form_field(None, label, key, ftype, order, extra, translations)

        security_role = roles['security-guard']
        security_fields = [
            ('Height (cm)', 'height', 'number', 0, {'min_value': 150, 'max_value': 220}, {
                'hi': {'label': 'ऊंचाई (सेमी)'},
                'mr': {'label': 'उंची (सेमी)'},
            }),
            ('Has Security Experience', 'has_security_experience', 'boolean', 1, {}, {
                'hi': {'label': 'सुरक्षा अनुभव है?'},
                'mr': {'label': 'सुरक्षा अनुभव आहे का?'},
            }),
            ('Has License', 'has_license', 'boolean', 2, {}, {
                'hi': {'label': 'लाइसेंस है?'},
                'mr': {'label': 'परवाना आहे का?'},
            }),
        ]
        for label, key, ftype, order, extra, translations in security_fields:
            upsert_form_field(security_role, label, key, ftype, order, extra, translations)

        electrician_role = roles['electrician']
        electrician_fields = [
            ('Certification', 'certification', 'text', 0, {}, {
                'hi': {'label': 'प्रमाणीकरण'},
                'mr': {'label': 'प्रमाणपत्र'},
            }),
            ('Years Electrical Experience', 'years_electrical_experience', 'number', 1, {'min_value': 0}, {
                'hi': {'label': 'विद्युत अनुभव वर्ष'},
                'mr': {'label': 'विद्युत अनुभवाची वर्षे'},
            }),
        ]
        for label, key, ftype, order, extra, translations in electrician_fields:
            upsert_form_field(electrician_role, label, key, ftype, order, extra, translations)

        housekeeping_role = roles['housekeeping']
        housekeeping_translations = {
                    'hi': {'label': 'पाली प्राथमिकता', 'options': ['सुबह', 'दोपहर', 'रात', 'कोई भी']},
                    'mr': {'label': 'शिफ्ट प्राधान्य', 'options': ['सकाळ', 'दुपार', 'रात्र', 'कोणतीही']},
        }
        upsert_form_field(
            housekeeping_role,
            'Shift Preference',
            'shift_preference',
            'select',
            0,
            {'options': ['Morning', 'Afternoon', 'Night', 'Any']},
            housekeeping_translations,
        )

        self.stdout.write(self.style.SUCCESS('\nDemo data seeded successfully!'))
        self.stdout.write(f'  Organization : {org.name}')
        self.stdout.write(f'  Site         : {site.name}')
        self.stdout.write(f'  Campaign     : {campaign.title}')
        self.stdout.write(self.style.SUCCESS(f'  Token        : {campaign.token}'))
        self.stdout.write(f'  Public URL   : /api/public/campaigns/{campaign.token}/')
