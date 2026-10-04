from rest_framework.routers import DefaultRouter

from django.urls import path, include

from .views import (
    FindCameraAPIView,
    SystemMessagesApiView,
    GdprStatusAPIView,
    GdprWorkerStatusAPIView,
    start_all_processing,
)

api_router = DefaultRouter()

api_router.register("system-message", SystemMessagesApiView, basename="system-message")

urlpatterns = [
    path("", include(api_router.urls)),
    path("find_cameras/", FindCameraAPIView.as_view(), name="find-cameras"),
    path("start-process/", start_all_processing, name="start-process"),
    path("gdpr/worker-status/", GdprWorkerStatusAPIView.as_view(), name="gdpr-worker-status"),
    path("gdpr/status/", GdprStatusAPIView.as_view(), name="gdpr-status"),
]
