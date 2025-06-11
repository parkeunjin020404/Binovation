import requests, json, os
from .models import DeviceToken

# fcm.py
import requests
import json
from google.oauth2 import service_account
import google.auth.transport.requests

# 🔐 1. Access Token 발급 함수
def get_fcm_access_token():
    credentials = service_account.Credentials.from_service_account_file(
        'binovation-3ae58-dff2c962d61b.json',  # 실제 경로
        scopes=["https://www.googleapis.com/auth/firebase.messaging"]
    )
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token

# 🚀 2. FCM V1 푸시 전송 함수
def send_push_notification_to_ios(token, title, body, category="push"):
    access_token = get_fcm_access_token()
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; UTF-8",
    }

    payload = {
        "message": {
            "token": token,
            "notification": {
                "title": title,
                "body": body
            },
            "data": {
                "category": category,
                "click_action": "FLUTTER_NOTIFICATION_CLICK"
            }
        }
    }

    project_id = "binovation-3ae58"  

    response = requests.post(
        f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
        headers=headers,
        data=json.dumps(payload)
    )

    print("🔥 FCM 응답:", response.status_code, response.text)
