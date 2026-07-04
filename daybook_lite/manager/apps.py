from django.apps import AppConfig
from django.db.models.signals import post_migrate

def sync_configuration_keys(sender, **kwargs):
    # Import the model here to prevent AppRegistryNotReady errors
    from .models import Configuration
    Configuration.initialize_defaults()

class ManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'manager'
    
    def ready(self):
        # Connect the signal so it runs automatically after migrations
        post_migrate.connect(sync_configuration_keys, sender=self)