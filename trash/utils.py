# trash/utils.py
from pyfcm import FCMNotification
from django.conf import settings
from .models import DeviceToken

building_name_map = {
    'Lib': '도서관',
    'SocSci': '사회과학관',
    'Human': '인문과학관',
    'Cyber': '사이버관',
    'EDU': '교수개발원',
}

building_travel_time = {
    '도서관': {'사회과학관': 2, '사이버관': 2, '인문과학관': 8, '교수개발원': 9},
    '사회과학관': {'도서관': 2, '사이버관': 4, '인문과학관': 6, '교수개발원': 7},
    '사이버관': {'도서관': 2, '사회과학관': 4, '인문과학관': 10, '교수개발원': 11},
    '인문과학관': {'도서관': 8, '사회과학관': 6, '사이버관': 10, '교수개발원': 0.5},
    '교수개발원': {'도서관': 9, '사회과학관': 7, '사이버관': 11, '인문과학관': 0.5},
}

FLOOR_TIME = 0.5

def parse_bin_name(device_name):
    try:
        code, floor = device_name.split('_floor')
        return code, int(floor)
    except:
        return None, None

def calc_fill(distance):
    if distance <= 10 or distance >= 800:
        return 100
    else:
        raw = ((65 - distance) / (65 - 10)) * 100
        return int(max(0, min(raw, 100)) // 10 * 10)

def calc_travel_time(bin1, bin2):
    code1, floor1 = parse_bin_name(bin1["device_name"])
    code2, floor2 = parse_bin_name(bin2["device_name"])
    if not code1 or not code2:
        return float('inf')
    try:
        bldg1 = building_name_map[code1]
        bldg2 = building_name_map[code2]
        base = building_travel_time[bldg1][bldg2]
        floor_gap = abs(floor1 - floor2) * FLOOR_TIME
        return base + floor_gap
    except:
        return float('inf')

def send_push_notification_to_ios(title, body):
    tokens = DeviceToken.objects.values_list('token', flat=True)
    if not tokens:
        return

    push_service = FCMNotification(api_key=settings.FCM_SERVER_KEY)
    result = push_service.notify_multiple_devices(
        registration_ids=list(tokens),
        message_title=title,
        message_body=body
    )
    print("🔥 FCM 응답:", result)