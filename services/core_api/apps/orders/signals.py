from apps.orders.models import Order
from apps.orders.tasks import broadcast_order_update, send_order_confirmation_email
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Order)
def on_order_saved(sender, instance: Order, created: bool, **kwargs):
    if created:
        send_order_confirmation_email.delay(str(instance.id))
    broadcast_order_update.delay(str(instance.id))
