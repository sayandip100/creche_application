from django.contrib import admin

from healthcenter.models import MedicineUnit


@admin.register(MedicineUnit)
class MedicineUnitAdmin(admin.ModelAdmin):
    list_display = ['id', 'unit_name']
    search_fields = ['unit_name']
    ordering = ['unit_name']
