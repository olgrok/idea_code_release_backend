from django.db import models
# Remove: from django.conf import settings
from django.db.models import Sum
# Import the User model directly
from main.models import User

# Delete the entire BookingGroup class definition from this file
# class BookingGroup(models.Model):
#     ... (DELETE ALL LINES FOR THIS CLASS) ...

# Delete the entire GroupContribution class definition from this file
# class GroupContribution(models.Model):
#     ... (DELETE ALL LINES FOR THIS CLASS) ...

# Keep other imports if needed for other models in this file in the future
# from django.db import models
# from main.models import User # This import might be needed if you add other group-specific models later
