import requests, json
from .models import DeviceToken

import os
FCM_SERVER_KEY = os.environ.get('FCM_SERVER_KEY')  # docker-compose에서 환경변수로 주입

def send_push_notification_to_ios(title, body):
    tokens = DeviceToken.objects.values_list('token', flat=True)

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'key={FCM_SERVER_KEY}',
    }

    for token in tokens:
        payload = {
            'to': token,
            'notification': {'title': title, 'body': body},
            'data': {'click_action': 'FLUTTER_NOTIFICATION_CLICK', 'category': 'complaint'}
        }
        requests.post('https://fcm.googleapis.com/fcm/send', headers=headers, data=json.dumps(payload))
