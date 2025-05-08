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
        # 1. 각 device_name 별 최신 date_time 구함
        latest_by_device = (
            TrashStatus.objects
            .values('device_name')
            .annotate(latest_time=Max('date_time'))
        )

        result = []
        max_d = 65.0
        min_d = 10.0

        for item in latest_by_device:
            device_name = item['device_name']
            latest_time = item['latest_time']

            entry = TrashStatus.objects.filter(
                device_name=device_name,
                date_time=latest_time
            ).order_by('-id').first()  # 같은 시간 여러개 있을 수도 있음

            if not entry or entry.distance is None:
                continue

            d = entry.distance
            if d >= 800:
                fill = 0
                status = "sensor_error"
            elif d <= 10:
                fill = 100
                status = "full"
            else:
                raw = ((max_d - d) / (max_d - min_d)) * 100
                fill = int(max(0, min(raw, 100)) // 10 * 10)
                status = "normal"

            result.append({
                "device_name": entry.device_name,
                "distance": entry.distance,
                "date_time": entry.date_time,
                "fill_percent": fill,
                "status": status
            })

        return Response(result)