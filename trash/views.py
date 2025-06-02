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
from datetime import datetime, timedelta
from .utils import *
class TrashStatusView(APIView):
    def post(self, request):
        # 리스트로 온 경우: many=True
        is_many = isinstance(request.data, list)

        serializer = TrashStatusSerializer(data=request.data, many=is_many)
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

            if d <= 10 or d >= 800:
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


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import TrashStatus
from django.db.models import Max



class RouteRecommendationView(APIView):
    def get(self, request, device_name):
        try:
            latest = (
                TrashStatus.objects
                .values('device_name')
                .annotate(latest=Max('date_time'))
            )

            all_bins = []
            for row in latest:
                entry = TrashStatus.objects.filter(
                    device_name=row['device_name'],
                    date_time=row['latest']
                ).first()
                if not entry:
                    continue
                fill = calc_fill(entry.distance)
                if fill is not None and fill >= 80:
                    all_bins.append({
                        "device_name": entry.device_name,
                        "fill_percent": fill
                    })

            # 출발점 정보 확보 및 제외된 나머지로 필터링
            start_bin = next((b for b in all_bins if b["device_name"] == device_name), None)
            if not start_bin:
                start_bin = {"device_name": device_name, "fill_percent": 0}

            remaining = [b for b in all_bins if b["device_name"] != device_name]

            # 거리 기반 정렬 (최대 6개)
            remaining = sorted(remaining, key=lambda b: calc_travel_time(start_bin, b))[:5]  # 5개 + 출발점 = 6개

            route = [start_bin] + remaining

            # 건물 매핑
            building_map = {
                'Lib': '도서관',
                'SocSci': '사회과학관',
                'Human': '인문관',
                'Cyber': '사이버관',
                'EDU': '교수개발원'
            }

            from collections import defaultdict, OrderedDict
            building_floors = defaultdict(list)

            for b in route:
                if '_floor' in b['device_name']:
                    building, floor = b['device_name'].split('_floor')
                    floor = int(floor)
                    building_floors[building].append(floor)

            ordered_buildings = list(OrderedDict.fromkeys([b['device_name'].split('_')[0] for b in route]))
            recommended_route = ' → '.join([building_map.get(b, b) for b in ordered_buildings])

            details = []
            for b in ordered_buildings:
                floors = sorted(building_floors[b], reverse=True)
                label = ' → '.join([f"{floor}층" for floor in floors])
                details.append(f"{building_map.get(b, b)} {label}")

            estimated_time = f"{len(ordered_buildings) * 5}분"

            return Response({
                "recommended_route": recommended_route,
                "estimated_time": estimated_time,
                "total_bins": len(route),
                "details": details
            })

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class WeeklyAverageAllDevicesView(APIView):
    def get(self, request):
        today = datetime.today().date()
        week_ago = today - timedelta(days=6)

        max_d = 65.0
        min_d = 10.0

        # Step 1. 일주일치 모든 디바이스의 날짜별 평균 distance 조회
        data = (
            TrashStatus.objects
            .filter(date_time__date__range=(week_ago, today))
            .annotate(date=TruncDate('date_time'))
            .values('device_name', 'date')
            .annotate(avg_distance=Avg('distance'))
            .order_by('device_name', 'date')
        )

        if not data:
            return Response({"error": "No data found."}, status=status.HTTP_404_NOT_FOUND)

        # Step 2. 기기별 fill_percent 계산 및 그룹핑
        result = {}

        for item in data:
            name = item['device_name']
            avg_d = item['avg_distance']
            raw_fill = ((max_d - avg_d) / (max_d - min_d)) * 100
            fill_percent = max(0, min(round(raw_fill, 1), 100))

            if name not in result:
                result[name] = {}
            result[name][str(item['date'])] = fill_percent

        return Response(result)


class HourlyStatsYesterdayAllDevicesView(APIView):
    def get(self, request):
        try:
            today = datetime.today().date()
            yesterday = today - timedelta(days=1)

            max_d = 65.0
            min_d = 10.0

            data = (
                TrashStatus.objects
                .filter(date_time__date=yesterday, distance__isnull=False)
                .annotate(hour=ExtractHour('date_time'))
                .values('device_name', 'hour')
                .annotate(avg_distance=Avg('distance'))
                .order_by('device_name', 'hour')
            )

            if not data:
                return Response({"error": "No data found for any device on yesterday."}, status=status.HTTP_404_NOT_FOUND)

            result = {}
            for item in data:
                device = item['device_name']
                hour = str(item['hour']).zfill(2)
                d = item['avg_distance']
                fill = ((max_d - d) / (max_d - min_d)) * 100
                fill = max(0, min(round(fill, 1), 100))

                if device not in result:
                    result[device] = {}
                result[device][hour] = fill

            return Response(result)

        except Exception as e:
            return Response({"error": str(e)}, status=500)
        

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import TrashStatus
from django.utils.timezone import now
from datetime import timedelta
from django.db.models import Max

class EmergencyAlertView(APIView):
    def get(self, request):
        # 디바이스별 최신 데이터
        latest_data = (
            TrashStatus.objects
            .values('device_name')
            .annotate(latest_time=Max('date_time'))
        )

        bins = []
        for row in latest_data:
            entry = TrashStatus.objects.filter(
                device_name=row['device_name'],
                date_time=row['latest_time']
            ).first()

            if not entry:
                continue

            d = entry.distance
            if d <= 10 or d >= 800:
                fill = 100
            else:
                fill = round(((65 - d) / (65 - 10)) * 100, 1)
 
            if fill >= 80:
                status_msg = None if fill == 100 else "30분 이내에 수거해 주세요!"
                bins.append({
                    "device_name": entry.device_name,
                    "current_fill": fill,
                    "status": status_msg
                })

        top6 = sorted(bins, key=lambda x: x["current_fill"], reverse=True)[:6]
        return Response(top6, status=status.HTTP_200_OK)