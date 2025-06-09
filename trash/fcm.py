import requests, json, os
from .models import DeviceToken

FCM_SERVER_KEY = os.environ.get('FCM_SERVER_KEY')

def send_push_notification_to_ios(title, body, category="push"):
    tokens = DeviceToken.objects.values_list('token', flat=True)
    if not tokens:
        return

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'key={FCM_SERVER_KEY}',
    }

    for token in tokens:
        payload = {
            'to': token,
            'notification': {'title': title, 'body': body},
            'data': {'click_action': 'FLUTTER_NOTIFICATION_CLICK', 'category': category}
        }
        requests.post('https://fcm.googleapis.com/fcm/send', headers=headers, data=json.dumps(payload))
