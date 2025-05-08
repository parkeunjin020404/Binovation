from django.urls import path
from .views import *

urlpatterns = [
    path('post/', TrashStatusView.as_view(), name='trash_status_post'),
    path('weekly-average/<str:device_name>/', DeviceWeeklyAverageView.as_view(), name='device-weekly-average'),
    path('yesterday-hourly/<str:device_name>/', HourlyStatsYesterdayView.as_view(), name='yesterday-hourly'),
    path('latest-all/', LatestStatusAllDevicesView.as_view(), name='latest-all'),
    path('route/<str:start>/', RouteRecommendationView.as_view(), name='route'),
    path('<str:device_name>/', TrashStatusLatestView.as_view(), name='latest_status'),
]   
