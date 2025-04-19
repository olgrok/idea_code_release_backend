# msu_book/groups/forms.py

from django import forms
from .models import BookingGroup

class GroupCreationForm(forms.ModelForm):
    class Meta:
        model = BookingGroup
        fields = ['name']
        labels = {
            'name': 'Название группы (необязательно)',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Например, "Команда для проекта X"'})
        }