import requests, json, os
from .models import DeviceToken

FCM_SERVER_KEY = os.environ.get('FCM_SERVER_KEY')

def send_push_notification_to_ios(title, body, category="push"):
    tokens = DeviceToken.objects.values_list('token', flat=True)
    if not tokens:
        print("푸시 알림: 저장된 토큰 없음")
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

        response = requests.post('https://fcm.googleapis.com/fcm/send', headers=headers, data=json.dumps(payload))
        print(f"[FCM 푸시 전송] token: {token}, 응답 코드: {response.status_code}, 응답 본문: {response.text}")