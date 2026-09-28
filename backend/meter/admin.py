from django.contrib import admin
from .models import Meter, MeterToken, MeterBalanceSnapshot, MeterUsageDaily


admin.site.register(Meter)
admin.site.register(MeterToken)
admin.site.register(MeterBalanceSnapshot)
admin.site.register(MeterUsageDaily)
