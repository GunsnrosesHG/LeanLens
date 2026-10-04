import time

import requests

from django.core.cache import cache
from django.core.paginator import Paginator
from rest_framework.response import Response
from rest_framework import status, generics, viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.http import JsonResponse

from src.Core.const import ONVIFFINDER_SERVICE_URL

from src.Core.management.commands.startprocess import start_process
from src.Core.serializers import SystemMessagesSerializer, EmptySerializer
from src.Core.models import SystemMessage


# --- RGPD : statut d'anonymisation remonté par le worker (leanlens-algo) ---

GDPR_STATUS_CACHE_KEY = "gdpr:worker-status"
# Sans heartbeat pendant 10 min, le statut est considéré obsolète.
GDPR_STALE_AFTER_S = 600


class GdprWorkerStatusAPIView(APIView):
    """Heartbeat RGPD du worker : publie sa config d'anonymisation.

    Appelé périodiquement par leanlens-algo (POST, compte de service JWT).
    Stocké dans le cache Redis (partagé entre les process gunicorn).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = EmptySerializer

    def post(self, request, *args, **kwargs):
        data = request.data if isinstance(request.data, dict) else {}
        mode = str(data.get("blur_mode") or "pixelate")
        if mode not in ("pixelate", "blur", "solid"):
            mode = "pixelate"
        payload = {
            "blur_faces": bool(data.get("blur_faces", False)),
            "blur_mode": mode,
            "algorithm": str(data.get("algorithm") or "")[:100],
            "camera": str(data.get("camera") or "")[:30],
            "worker": str(data.get("worker") or "")[:100],
            "reported_at": time.time(),
        }
        cache.set(GDPR_STATUS_CACHE_KEY, payload, timeout=None)
        return Response({"status": True}, status=status.HTTP_200_OK)


class GdprStatusAPIView(APIView):
    """Statut d'anonymisation affiché sur la page RGPD de l'UI v2."""

    permission_classes = [IsAuthenticated]
    serializer_class = EmptySerializer

    def get(self, request, *args, **kwargs):
        payload = cache.get(GDPR_STATUS_CACHE_KEY)
        if not payload:
            return Response(
                {
                    "reported": False,
                    "blur_active": False,
                    "blur_mode": None,
                    "algorithm": None,
                    "camera": None,
                    "age_seconds": None,
                    "stale": True,
                }
            )
        age = max(0, int(time.time() - payload.get("reported_at", 0)))
        return Response(
            {
                "reported": True,
                "blur_active": bool(payload.get("blur_faces")),
                "blur_mode": payload.get("blur_mode"),
                "algorithm": payload.get("algorithm"),
                "camera": payload.get("camera"),
                "age_seconds": age,
                "stale": age > GDPR_STALE_AFTER_S,
            }
        )


class FindCameraAPIView(generics.GenericAPIView):
    serializer_class = EmptySerializer

    def get(self, request, *args, **kwargs):
        cameras_response = requests.get(f"{ONVIFFINDER_SERVICE_URL}:7654/get_all_rtsp_cameras/")
        try:
            cameras = cameras_response.json()
        except ValueError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        response_data = {"results": cameras}
        return Response(response_data, status=status.HTTP_200_OK)


class SystemMessagesApiView(
    mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = SystemMessagesSerializer
    queryset = SystemMessage.objects.order_by("-id")

    def get_queryset(self):
        page_size = self.request.query_params.get('page_size', 25)
        paginator = Paginator(self.queryset, page_size)
        page_number = self.request.query_params.get('page', 1)
        page = paginator.get_page(page_number)
        return page


def start_all_processing(request):
    start_process()
    response_data = {'message': 'successfully'}
    return JsonResponse(response_data)
