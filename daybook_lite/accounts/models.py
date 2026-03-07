from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class User(AbstractUser):
    phone_regex = RegexValidator(
        regex=r'^\d{10}$',
        message="Phone number must be exactly 10 digits."
    )
    
    mobile_number = models.CharField(
        validators=[phone_regex],
        max_length=10,
        blank=True,
        null=True,
        help_text="10 digit mobile number"
    )
    
    alternate_number = models.CharField(
        validators=[phone_regex],
        max_length=10,
        blank=True,
        null=True,
        help_text="10 digit alternate number"
    )
    
    def __str__(self) -> str:
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.username
