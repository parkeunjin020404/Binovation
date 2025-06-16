from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import *
from django.db.models import Avg
from .serializers import *
from django.db.models.functions import TruncDate
import datetime
from django.db.models.functions import ExtractHour
from django.db.models import OuterRef, Subquery
from django.db.models import Max
from datetime import datetime, timedelta
from .utils import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from datetime import datetime, timedelta
from .models import TrashStatus

class TrashStatusView(APIView):
    def post(self, request):
        try:
            is_many = isinstance(request.data, list)
            serializer = TrashStatusSerializer(data=request.data, many=is_many)

            if serializer.is_valid():
                instances = serializer.save()

                if not is_many:
                    instances = [instances]

                for instance in instances:
                    fill = calc_fill(instance.distance)

                    if fill >= 100:
                        create_full_bin_alert(instance.device_name, fill_level="위험")
                    elif fill >= 80:
                        create_full_bin_alert(instance.device_name, fill_level="경고")

                return Response({"message": "Data saved successfully"}, status=status.HTTP_201_CREATED)
            else:
                print("Serializer validation errors:", serializer.errors)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(f"🔥 Error in TrashStatusView POST: {e}")
            return Response({"error": "Internal Server Error", "details": str(e)}, status=500)

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

            start_building = device_name.split('_')[0]

            # 출발점이 있는 건물의 쓰레기통 모두 포함
            same_building_bins = [b for b in all_bins if b["device_name"].startswith(start_building)]
            other_bins = [b for b in all_bins if not b["device_name"].startswith(start_building)]

            # 출발점 쓰레기통 포함 여부 확인 및 추가
            start_bin = next((b for b in same_building_bins if b["device_name"] == device_name), None)
            if not start_bin:
                start_bin = {"device_name": device_name, "fill_percent": 0}
                same_building_bins.insert(0, start_bin)

            route = [start_bin]
            visited = {start_bin["device_name"]}

            # 동일 건물 내 다른 층 쓰레기통 모두 포함
            for b in same_building_bins:
                if b["device_name"] not in visited and len(route) < 6:
                    route.append(b)
                    visited.add(b["device_name"])

            # 다른 건물 쓰레기통도 가까운 순으로 최대 6개까지 포함
            while other_bins and len(route) < 6:
                current = route[-1]
                next_bin = min(other_bins, key=lambda b: calc_travel_time(current, b))
                if next_bin["device_name"] not in visited:
                    route.append(next_bin)
                    visited.add(next_bin["device_name"])
                other_bins.remove(next_bin)

            # 출발점이 가짜라면 제거
            if start_bin["fill_percent"] == 0:
                route = route[1:]

            # 층 정보 포함해서 건물별로 층들을 모음
            from collections import defaultdict
            building_floors = defaultdict(set)

            for b in route:
                if '_floor' in b['device_name']:
                    building, floor = b['device_name'].split('_floor')
                    floor = int(floor)
                    building_floors[building].add(floor)

            building_map = {
                'Lib': '도서관',
                'SocSci': '사회과학관',
                'Human': '인문관',
                'Cyber': '사이버관',
                'EDU': '교수개발원'
            }

            ordered_buildings = []
            seen = set()
            for b in route:
                building = b['device_name'].split('_')[0]
                if building not in seen:
                    seen.add(building)
                    ordered_buildings.append(building)

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
                fill_raw = 100
            else:
                fill_raw = ((65 - d) / (65 - 10)) * 100

            fill = int(fill_raw // 10) * 10

            if fill >= 80:
                message = "지금 수거하세요" if fill == 100 else "30분 이내에 수거해 주세요!"
                bins.append({
                    "device_name": entry.device_name,
                    "current_fill": fill,
                    "message": message,
                })

        bins_sorted = sorted(bins, key=lambda x: x['current_fill'], reverse=True)
        return Response(bins_sorted[:6], status=status.HTTP_200_OK)

class AllBuildingsUsageStatsView(APIView):
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        try:
            start = datetime.strptime(start_date, '%Y-%m-%d') if start_date else datetime.now() - timedelta(days=7)
            end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else datetime.now()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        buildings = ['Lib', 'EDU', 'Human', 'SocSci', 'Cyber']
        max_d = 65.0
        min_d = 10.0
        fill_threshold = 90.0
        empty_threshold = 10.0

        def calc_fill(distance):
            return max(0, min(100, round((max_d - distance) / (max_d - min_d) * 100)))

        from collections import defaultdict, Counter

        results = []

        for building in buildings:
            qs = TrashStatus.objects.filter(
                device_name__startswith=building,
                date_time__date__range=(start.date(), end.date())
            ).order_by('device_name', 'date_time')

            if not qs.exists():
                results.append({
                    "building": building,
                    "avg_empty_per_day": 0,
                    "most_frequent_hour": None
                })
                continue

            empty_counts_by_day = defaultdict(int)
            hour_counter = Counter()
            prev_fill = {}

            for record in qs:
                device = record.device_name
                date = record.date_time.date()
                hour = record.date_time.hour
                fill = calc_fill(record.distance)

                prev = prev_fill.get(device)
                if prev is not None:
                    prev_fill_percent = calc_fill(prev.distance)
                    if prev_fill_percent >= fill_threshold and fill <= empty_threshold:
                        empty_counts_by_day[date] += 1
                prev_fill[device] = record

                if fill >= fill_threshold:
                    hour_counter[hour] += 1

            total_days = (end.date() - start.date()).days + 1
            avg_empty = round(sum(empty_counts_by_day.values()) / total_days, 2)
            most_frequent_hour = hour_counter.most_common(1)[0][0] if hour_counter else None

            results.append({
                "building": building,
                "avg_empty_per_day": avg_empty,
                "most_frequent_hour": most_frequent_hour
            })

        return Response(results)
    

from .models import Alert
from .fcm import send_push_notification_to_ios 

class DeviceTokenView(APIView):
    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "토큰 저장됨"}, status=201)
        return Response(serializer.errors, status=400)
    
from .models import DeviceToken

class ComplaintCreateView(APIView):
    def post(self, request):
        try:
            serializer = ComplaintSerializer(data=request.data)
            if serializer.is_valid():
                complaint = serializer.save()

                # Alert 테이블에 저장
                Alert.objects.create(
                    title="민원 접수됨",
                    message=f"{complaint.building} {complaint.floor}층에 민원이 등록되었습니다.",
                    category="민원",
                    is_sent=True
                )

                # 토큰 리스트 불러와서 푸시 전송
                tokens = DeviceToken.objects.values_list('token', flat=True)
                for token in tokens:
                    send_push_notification_to_ios(
                        token=token,
                        title="민원 접수됨",
                        body="해당 쓰레기통에 민원이 등록되었습니다.",
                        category="민원"
                    )

                return Response({"message": "Complaint registered"}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print("🔥 Complaint POST 처리 중 에러 발생:", str(e))
            return Response({"error": "Internal Server Error", "details": str(e)}, status=500)

class ComplaintListView(APIView):
    def get(self, request):
        complaints = Complaint.objects.order_by('-created_at')  # 최신순 정렬
        serializer = ComplaintSerializer(complaints, many=True)
        return Response(serializer.data)
    def delete(self, request):
        deleted_count, _ = Complaint.objects.all().delete()
        return Response({"message": f"민원 {deleted_count}개가 모두 삭제되었습니다."}, status=status.HTTP_200_OK)

class AlertListView(APIView):
    def get(self, request, category):
        if category not in ['푸시', '민원']:
            return Response({"error": "잘못된 category"}, status=400)

        alerts = Alert.objects.filter(category=category).order_by('-created_at')
        serializer = AlertSerializer(alerts, many=True)
        return Response(serializer.data)

class AlertClearView(APIView):
    def delete(self, request, category):
        if category not in ['푸시', '민원']:
            return Response({"error": "잘못된 category입니다"}, status=400)

        deleted_count, _ = Alert.objects.filter(category=category).delete()
        return Response({"message": f"{category} 알림 {deleted_count}개 삭제됨"}, status=status.HTTP_200_OK)
    
class PushAlertListView(APIView):
    def get(self, request):
        latest_data = (
            TrashStatus.objects
            .values('device_name')
            .annotate(latest_time=Max('date_time'))
        )

        alerts = []
        for row in latest_data:
            entry = TrashStatus.objects.filter(
                device_name=row['device_name'],
                date_time=row['latest_time']
            ).first()

            if not entry:
                continue

            d = entry.distance
            if d <= 10 or d >= 800:
                fill_raw = 100
            else:
                fill_raw = ((65 - d) / (65 - 10)) * 100

            fill = int(fill_raw // 10) * 10

            if fill >= 80:
                message = "지금 수거하세요" if fill == 100 else "30분 이내에 수거해 주세요!"
                alerts.append({
                    "device_name": entry.device_name,
                    "current_fill": fill,
                    "message": message,
                    "created_at": entry.date_time
                })

        alerts_sorted = sorted(alerts, key=lambda x: x['created_at'], reverse=True)
        return Response(alerts_sorted, status=status.HTTP_200_OK)