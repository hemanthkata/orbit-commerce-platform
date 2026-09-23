from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Registers the Celery Beat periodic tasks this project ships with."

    def handle(self, *args, **options):
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour="1", day_of_week="*", day_of_month="*", month_of_year="*"
        )
        task, created = PeriodicTask.objects.get_or_create(
            name="Daily sales report",
            defaults={
                "crontab": schedule,
                "task": "apps.orders.tasks.generate_daily_sales_report",
            },
        )
        if not created:
            task.crontab = schedule
            task.task = "apps.orders.tasks.generate_daily_sales_report"
            task.save()

        self.stdout.write(
            self.style.SUCCESS("Beat schedule seeded: 'Daily sales report' @ 01:00 UTC")
        )
