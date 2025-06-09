from django.urls import path
from .views import *

urlpatterns = [
    path('post/', TrashStatusView.as_view(), name='trash_status_post'),
    path('emergency/', EmergencyAlertView.as_view(), name='emergency-alert'),
    path('weekly-average/<str:device_name>/', DeviceWeeklyAverageView.as_view(), name='device-weekly-average'),
    path('weekly-average/', WeeklyAverageAllDevicesView.as_view(), name='weekly-average-all'),
    path('yesterday-hourly/all/', HourlyStatsYesterdayAllDevicesView.as_view(), name='hourly-stats-all'),
    path('yesterday-hourly/<str:device_name>/', HourlyStatsYesterdayView.as_view(), name='yesterday-hourly'),
    path('latest-all/', LatestStatusAllDevicesView.as_view(), name='latest-all'),
    path('device-token/', DeviceTokenView.as_view(), name='device-token'),
    path('api/building-usage-stats/', AllBuildingsUsageStatsView.as_view(), name='all-building-usage-stats'),
    path('route/<str:device_name>/', RouteRecommendationView.as_view(), name='route'),
    path('<str:device_name>/', TrashStatusLatestView.as_view(), name='latest_status'),  # ← 이건 맨 아래!
]