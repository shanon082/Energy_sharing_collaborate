from django.contrib import admin
from .models import User, Profile, UserAccountDetails



admin.site.register(User)
admin.site.register(Profile)

@admin.register(UserAccountDetails)
class UserAccountDetailsAdmin(admin.ModelAdmin):
    list_display = ['user', 'account_number', 'energy_preference']
    search_fields = ['user__email', 'account_number']