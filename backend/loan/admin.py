from django.contrib import admin
from .models import LoanApplication, LoanDisbursement, LoanRepayment, UserCreditSignal

admin.site.register(LoanApplication)
admin.site.register(LoanDisbursement)
admin.site.register(LoanRepayment)
admin.site.register(UserCreditSignal)
