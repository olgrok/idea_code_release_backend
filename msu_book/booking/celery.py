import os
from celery import Celery
from django.conf import settings

# Устанавливаем переменную окружения для настроек Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'msu_book.settings')

# Создаем экземпляр Celery
app = Celery('msu_book')

# Загружаем конфигурацию из настроек Django (префикс 'CELERY_')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически обнаруживаем задачи в файлах tasks.py приложений Django
app.autodiscover_tasks()

# (Опционально) Пример простой задачи для отладки
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
