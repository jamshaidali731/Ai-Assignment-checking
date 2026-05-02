from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from main.models import Notification
from main.serizalizer import NotificationSerializer

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by('-sent_time')
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)
