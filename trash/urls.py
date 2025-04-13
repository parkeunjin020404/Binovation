from django.urls import path
from .views import *

urlpatterns = [
    path('post/', TrashStatusView.as_view(), name='trash_status_post'),
    path('<str:device_name>/', TrashStatusLatestView.as_view(), name='latest_status'),
]
