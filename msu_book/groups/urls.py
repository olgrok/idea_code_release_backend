from django.urls import path, include
# Используем стандартный роутер DRF
from rest_framework.routers import DefaultRouter
from . import views

# Создаем стандартный роутер
router = DefaultRouter()
# Регистрируем основной ресурс BookingGroup
router.register(r'groups', views.BookingGroupViewSet, basename='bookinggroup')

# Определяем URL-шаблоны для GroupContribution вручную,
# чтобы включить group_pk
contribution_patterns = [
    path('list/', views.GroupContributionViewSet.as_view({'get': 'list_contributions'}), name='group-contribution-list'),
    path('my-contribution/', views.GroupContributionViewSet.as_view({'get': 'my_contribution'}), name='group-contribution-my'),
    path('add/', views.GroupContributionViewSet.as_view({'post': 'add_contribution'}), name='group-contribution-add'),
    path('withdraw/', views.GroupContributionViewSet.as_view({'post': 'withdraw_contribution'}), name='group-contribution-withdraw'),
]

# Основные URL-шаблоны приложения
urlpatterns = [
    # Включаем URL-адреса, сгенерированные роутером для /groups/ и /groups/{pk}/
    path('', include(router.urls)),
    # Добавляем пути для вкладов, вложенные вручную
    # Пример: /groups/{group_pk}/contributions/list/
    path('groups/<int:group_pk>/contributions/', include(contribution_patterns)),
]
