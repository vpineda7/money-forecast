from django.shortcuts import render
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from records.models import get_last_day_of_month, Record, Account, INCOME, OUTCOME,\
							 SAVINGS, SYSTEM_ACCOUNTS, INITIAL_BALANCE_SLUG

class MonthControl(object):
	def __init__(self, user, month, year):
		self.user = user
		self.month = month
		self.year = year
		self.today = date.today()
		self.start_date = date(day=1, month=month, year=year)
		# end_date is the last day of the month
		self.end_date = get_last_day_of_month(month, year)
		self.last_month = (self.start_date-relativedelta(months=1))
		self._get_records()
		self._calculate_totals()

	def _calculate_totals(self):
		self.initial_balance = self.get_initial_balance()
		self.income_monthly = sum([x.value for x in self.income_monthly_list])
		self.income_variable = sum([x.value for x in self.income_variable_list])
		self.outcome_monthly = sum([x.value for x in self.outcome_monthly_list])
		self.outcome_variable = sum([x.value for x in self.outcome_variable_list])
		self.total_income = self.income_monthly + self.income_variable
		self.total_outcome = self.outcome_monthly + self.outcome_variable
		self.difference = ((self.income_monthly+self.income_variable) -
						 	(self.outcome_monthly+self.outcome_variable))
		self.final_balance = self.initial_balance + self.difference

	def _get_records(self):
		self.income_monthly_list = self._get_records_by_type(INCOME, False)
		self.income_variable_list = self._get_records_by_type(INCOME, True)
		self.outcome_monthly_list = self._get_records_by_type(OUTCOME, False)
		self.outcome_variable_list = self._get_records_by_type(OUTCOME, True)

	def _get_records_by_type(self, account, one_time_only):
		records = self.get_queryset().filter(is_paid_off=False) # TODO: improve the way to track paid off or it could disappear prematurely
		records = records.filter( Q(end_date__isnull=True) | Q(end_date__range=(self.start_date, self.end_date)) )
		records = records.filter(account__type_account=account, day_of_month__isnull=one_time_only)

		if one_time_only:
			# If not recurring, then it should check the start date
			records = records.filter(start_date__range=(self.start_date, self.end_date))
		return records

	def get_queryset(self):
		# Make sure to filter only records by the user
		records = Record.objects.filter(user=self.user) 

		# All records must start in the month or earlier
		records = records.filter(start_date__lte=self.end_date)
		
		return records

	def get_initial_balance(self):
		balance = self.get_queryset().filter(account__type_account=SYSTEM_ACCOUNTS, account__slug=INITIAL_BALANCE_SLUG) 
		# Initial Balance must be from this month
		balance = balance.filter(start_date__range=(self.start_date, self.end_date))
		if balance.count():
			return balance[0].value
		else:
			# TODO: Have to improve it, raising errors when no last balance is found
			last_balance = MonthControl(self.user, self.last_month.month, self.last_month.year)
			return last_balance.final_balance

	def set_initial_balance(self, value):
		# TODO: set record for initial balance for the month
		pass

	def get_upcoming_records(self):
		"""
		This will return a tuple with the date for the month and the record.
		It is necessary since you can't get the date of a recurring event inside the template
		"""
		outcomes  = self.outcome_monthly_list | self.outcome_variable_list
		upcoming = []
		results = []

		for record in outcomes:
			# Calculate dates
			results.append((record.get_date_for_month(self.month, self.year), record))

		# Sort per date
		results.sort(key=lambda r: r[0])

		for record in results:
			if record[0] >= self.today:
				upcoming.append(record)
		return upcoming

	def get_savings_totals(self):
		# TODO: Sum up all savings by account to display in a table
		pass


def _get_account_id(user, type_account, slug):
	account = Account.objects.filter(user=user, type_account=type_account, slug=slug)
	# The slugs might have changed
	if account.count():
		return account[0].id
	else:
		return 0

@login_required
def index(request):
	month_list = []
	today = datetime.today()
	for i in range(0,13):
		target_month = today+relativedelta(months=i)
		month_list.append(MonthControl(request.user, target_month.month, target_month.year))

	current_month = month_list[0]

	income_id = _get_account_id(request.user, INCOME, 'extra_income')
	outcome_id = _get_account_id(request.user, OUTCOME, 'extra_outcome')
	savings_id = _get_account_id(request.user, SAVINGS, 'savings')
	set_balance_id = _get_account_id(request.user, SYSTEM_ACCOUNTS, INITIAL_BALANCE_SLUG)
	return render(request, "base.html", locals())
