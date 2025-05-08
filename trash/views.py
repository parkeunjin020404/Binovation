from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import TrashStatus
from django.db.models import Avg
from .serializers import TrashStatusSerializer
from django.db.models.functions import TruncDate
import datetime
from django.db.models.functions import ExtractHour
from django.db.models import OuterRef, Subquery
from django.db.models import Max
class TrashStatusView(APIView):
    def post(self, request):
        serializer = TrashStatusSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Data saved successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TrashStatusLatestView(APIView):
    def get(self, request, device_name):
        try:
            latest = TrashStatus.objects.filter(device_name=device_name).latest('date_time')
        except TrashStatus.DoesNotExist:
            return Response({"error": "Device not found"}, status=status.HTTP_404_NOT_FOUND)

        measured = latest.distance

        # 기준 거리
        max_d = 65.0  # 빈 통일 때
        min_d = 10.0  # 가득 찼을 때

        # 예외 및 fill 계산
        if measured >= 800:
            fill = 0
            level = 0
            status_msg = "sensor_error"
        elif measured <= 10:
            fill = 100
            level = 100
            status_msg = "full"
        else:
            raw_fill = ((max_d - measured) / (max_d - min_d)) * 100
            raw_fill = max(0, min(raw_fill, 100))
            fill = int(raw_fill // 10) * 10  # 10% 단위로 끊기 (버림)
            level = fill  
            status_msg = "normal"

        return Response({
            "device_name": latest.device_name,
            "distance": latest.distance,
            "date_time": latest.date_time,
            "fill_percent": fill,  # 이제 0, 10, 20, ..., 100 중 하나
            "level": level,
            "status": status_msg
        }, status=status.HTTP_200_OK)

class DeviceWeeklyAverageView(APIView):
    def get(self, request, device_name):
        today = datetime.date.today()
        week_ago = today - datetime.timedelta(days=6)

        # 1. 날짜별 평균 distance 계산
        data = (
            TrashStatus.objects
            .filter(device_name=device_name, date_time__date__range=(week_ago, today))
            .annotate(date=TruncDate('date_time'))
            .values('date')
            .annotate(avg_distance=Avg('distance'))
            .order_by('date')
        )

        if not data:
            return Response({"error": "No data found for this device."}, status=status.HTTP_404_NOT_FOUND)

        # 2. 평균 distance → fill_percent 수식 적용
        max_d = 65.0
        min_d = 10.0
        result = {}

        for item in data:
            avg_d = item['avg_distance']
            raw_fill = ((max_d - avg_d) / (max_d - min_d)) * 100
            fill_percent = max(0, min(round(raw_fill, 1), 100))  # 0~100 범위 제한
            result[str(item['date'])] = fill_percent

        return Response(result)
    
class HourlyStatsYesterdayView(APIView):
    def get(self, request, device_name):
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        data = (
            TrashStatus.objects
            .filter(device_name=device_name, date_time__date=yesterday)
            .annotate(hour=ExtractHour('date_time'))
            .values('hour')
            .annotate(avg_distance=Avg('distance'))
            .order_by('hour')
        )

        if not data:
            return Response({"error": "No data for this device on yesterday."}, status=status.HTTP_404_NOT_FOUND)

        max_d = 65.0
        min_d = 10.0
        result = {}

        for item in data:
            hour = str(item['hour']).zfill(2)
            d = item['avg_distance']
            fill = ((max_d - d) / (max_d - min_d)) * 100
            result[hour] = max(0, min(round(fill, 1), 100))

        return Response(result)
    



class LatestStatusAllDevicesView(APIView):
    def get(self, request):
        devices = TrashStatus.objects.values_list('device_name', flat=True).distinct()
        result = []
        max_d, min_d = 65.0, 10.0

        for device in devices:
            entry = (
                TrashStatus.objects
                .filter(device_name=device)
                .order_by('-date_time')
                .first()
            )

            if not entry or entry.distance is None:
                continue

            d = entry.distance
            if d >= 800:
                fill = 0
                status_msg = "sensor_error"
            elif d <= 10:
                fill = 100
                status_msg = "full"
            else:
                raw = ((max_d - d) / (max_d - min_d)) * 100
                fill = int(max(0, min(raw, 100)) // 10 * 10)
                status_msg = "normal"

            result.append({
                "device_name": entry.device_name,
                "distance": entry.distance,
                "date_time": entry.date_time,
                "fill_percent": fill,
                "status": status_msg
            })

        return Response(result)
    
from django.db.models import Max
from rest_framework.views import APIView
from rest_framework.response import Response
from trash.models import TrashStatus  # ← 실제 앱/모델명 맞게 수정하세요

building_name_map = {
    'Lib': '도서관',
    'SocSci': '사회과학관',
    'Human': '인문과학관',
    'Cyber': '사이버관',
    'CDI': '교수개발원'
}

building_travel_time = {
    '사회과학관': {'도서관': 2, '사이버관': 4, '인문과학관': 6, '교수개발원': 7},
    '도서관': {'사회과학관': 2, '사이버관': 2, '인문과학관': 8, '교수개발원': 9},
    '사이버관': {'사회과학관': 4, '도서관': 2, '인문과학관': 10, '교수개발원': 11},
    '인문과학관': {'사회과학관': 6, '도서관': 8, '사이버관': 10, '교수개발원': 0.5},
    '교수개발원': {'사회과학관': 7, '도서관': 9, '사이버관': 11, '인문과학관': 0.5}
}

FLOOR_TIME = 0.5

def parse_bin_name(device_name):
    code, floor = device_name.split('_floor')
    return code, int(floor)

def calc_fill(distance):
    if distance >= 800:
        return None
    elif distance <= 10:
        return 100
    else:
        raw = ((65 - distance) / (65 - 10)) * 100
        return int(max(0, min(raw, 100)) // 10 * 10)

def calc_travel_time(bin1, bin2):
    code1, floor1 = parse_bin_name(bin1["device_name"])
    code2, floor2 = parse_bin_name(bin2["device_name"])
    bldg1 = building_name_map[code1]
    bldg2 = building_name_map[code2]
    base = building_travel_time[bldg1][bldg2]
    floor_gap = abs(floor1 - floor2) * FLOOR_TIME
    return base + floor_gap

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import TrashStatus
from django.db.models import Max

# 건물 코드 → 한글명
building_name_map = {
    'Lib': '도서관',
    'SocSci': '사회과학관',
    'Human': '인문과학관',
    'Cyber': '사이버관',
    'CDI': '교수개발원',
}

# 이동 시간(분)
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
    if distance >= 800:
        return None
    elif distance <= 10:
        return 100
    else:
        return int(((65 - distance) / (65 - 10)) * 100 // 10 * 10)

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

class RouteRecommendationView(APIView):
    def get(self, request, device_name):
        try:
            latest = (
                TrashStatus.objects
                .values('device_name')
                .annotate(latest=Max('date_time'))
            )

            bins = []
            for row in latest:
                entry = TrashStatus.objects.filter(
                    device_name=row['device_name'],
                    date_time=row['latest']
                ).first()
                if not entry:
                    continue
                fill = calc_fill(entry.distance)
                if fill is not None and fill >= 80:
                    bins.append({
                        "device_name": entry.device_name,
                        "fill_percent": fill
                    })

            # 출발점 추가
            if not any(b["device_name"] == device_name for b in bins):
                bins.insert(0, {"device_name": device_name, "fill_percent": 0})

            start_bin = next(b for b in bins if b["device_name"] == device_name)
            remaining = [b for b in bins if b["device_name"] != device_name]

            route = [start_bin]
            while remaining:
                current = route[-1]
                next_bin = min(remaining, key=lambda b: calc_travel_time(current, b))
                route.append(next_bin)
                remaining.remove(next_bin)

            result = [
                {
                    "device_name": b["device_name"],
                    "fill_percent": b["fill_percent"],
                    "order": i + 1
                }
                for i, b in enumerate(route)
            ]
            return Response(result)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)