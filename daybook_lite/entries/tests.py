from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from entries.models import Transactions
from manager.models import Accounts, Shop


class TransactionPieChartTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_superuser(
			username='adminuser',
			email='admin@example.com',
			password='StrongPass123!'
		)
		self.shop = Shop.objects.create(short_name='SHOP1', name='Shop One')
		self.other_shop = Shop.objects.create(short_name='SHOP2', name='Shop Two')

		self.account_with_blank_english_name = Accounts.objects.create(
			shop=self.shop,
			e_name='',
			t_name='தமிழ் கணக்கு',
		)
		self.account_with_english_name = Accounts.objects.create(
			shop=self.other_shop,
			e_name='English Account',
			t_name='',
		)

		today = timezone.localdate()
		Transactions.objects.create(
			id='TXN-1',
			shop=self.shop,
			acc=self.account_with_blank_english_name,
			amount=1200,
			tr_type='DEBIT',
			remarks='Debit test',
			transaction_dt=timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time())),
		)
		Transactions.objects.create(
			id='TXN-2',
			shop=self.other_shop,
			acc=self.account_with_english_name,
			amount=800,
			tr_type='CREDIT',
			remarks='Credit test',
			transaction_dt=timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time())),
		)

	def test_transaction_pie_data_falls_back_to_t_name_when_e_name_is_blank(self):
		self.client.force_login(self.user)
		today = timezone.localdate()
		response = self.client.get(
			reverse('api:transaction_pie_data'),
			{
				'from_date': (today - timedelta(days=1)).isoformat(),
				'to_date': (today + timedelta(days=1)).isoformat(),
			},
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()

		self.assertIn('தமிழ் கணக்கு', payload['debit']['labels'])
		self.assertNotIn('No Account', payload['debit']['labels'])
		self.assertIn('English Account', payload['credit']['labels'])
