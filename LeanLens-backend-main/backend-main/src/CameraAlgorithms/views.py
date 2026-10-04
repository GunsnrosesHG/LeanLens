import logging

from django.core.validators import validate_ipv46_address
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import NotFound

logger = logging.getLogger(__name__)

from src.Core.paginators import NoPagination
from src.Core.permissions import IsStaffPermission, IsSuperuserPermission

from src.CameraAlgorithms.models import Camera, ZoneCameras
from src.CameraAlgorithms.models import Algorithm, CameraAlgorithm, CameraAlgorithmLog
from src.CameraAlgorithms.services.tasks import uploading_algorithm
from src.CameraAlgorithms.services.cameraalgorithm import CreateCameraAlgorithms, DeleteCamera
from src.CameraAlgorithms.serializers import (
    AlgorithmDetailSerializer,
    CameraAlgorithmFullSerializer,
    CameraModelSerializer,
    CreateCameraAlgorithmSerializer,
    CameraAlgorithmLogSerializer,
    ZoneCameraSerializer,
    UniqueImageNameSerializer,
    AlgorithmInfoSerializer,
    CameraSerializer, CameraWithAlgorithmsSerializer,
)


class CameraAPIView(generics.ListAPIView):
    serializer_class = CameraModelSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NoPagination
    queryset = Camera.objects.all().order_by('id')

    def post(self, request, *args, **kwargs):
        """PFE: create a camera row directly.

        The upstream creation path goes through the onvif/cam-stream services
        (`sender('add_camera')` -> :3010), which are not deployed/usable here —
        so the v2 UI writes the Camera row itself. The leanlens-algo worker
        picks cameras up through get-process polling; detection only starts
        once an algorithm link exists (page Algorithmes).
        Accepts {"ip" | "id", "name"?, "username"?, "password"?}.
        """
        data = request.data if isinstance(request.data, dict) else {}
        ip = data.get("ip") or data.get("id")
        if not ip:
            return Response(
                {"ip": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_ipv46_address(str(ip))
        except (DjangoValidationError, ValueError):
            return Response(
                {"ip": ["Enter a valid IP address."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        username = str(data.get("username") or "")[:100]
        password = str(data.get("password") or "")[:100]
        name = str(data.get("name") or "")[:100] or str(ip)

        camera, created = Camera.objects.get_or_create(
            id=str(ip),
            defaults={
                "name": name,
                "username": username,
                "password": password,
                "is_active": True,
            },
        )
        if not created:
            return Response(
                {"detail": "Camera already exists.", "id": camera.id},
                status=status.HTTP_409_CONFLICT,
            )
        logger.warning("Camera [%s] created via v2 UI", camera.id)
        return Response(CameraModelSerializer(camera).data, status=status.HTTP_201_CREATED)


class AlgorithmDetailApiView(ModelViewSet):
    serializer_class = AlgorithmDetailSerializer
    permission_classes = [IsAuthenticated]
    queryset = Algorithm.objects.all().exclude(is_available=False).order_by('name')
    pagination_class = NoPagination


class AlgorithmProcessApiView(generics.ListAPIView):
    serializer_class = CameraAlgorithmFullSerializer
    queryset = CameraAlgorithm.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = NoPagination


class CameraAlgorithmProcessApiView(generics.ListAPIView):
    serializer_class = CameraWithAlgorithmsSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NoPagination

    def get_queryset(self):
        camera_ip = self.kwargs.get("camera_ip")
        queryset = Camera.objects.all()

        if camera_ip:
            queryset = queryset.filter(id=camera_ip)
            if not queryset.exists():
                raise NotFound(f"No data found for camera_ip: {camera_ip}")

        return queryset


class DeleteCameraAPIView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated, IsSuperuserPermission | IsStaffPermission]
    queryset = Camera.objects.all()

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        result = DeleteCamera(instance)
        return Response(result, status=status.HTTP_200_OK)


class CreateCameraAlgorithmsApiView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateCameraAlgorithmSerializer

    def post(self, request, *args, **kwargs):
        """Creates a separate camera and camera/algorithm"""
        serializer = CreateCameraAlgorithmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        CreateCameraAlgorithms(serializer.validated_data)
        return Response(status=status.HTTP_201_CREATED)


class CameraAlgorithmLogListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    queryset = CameraAlgorithmLog.objects.all()
    serializer_class = CameraAlgorithmLogSerializer


class ZoneCameraListAPIView(ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = NoPagination
    queryset = ZoneCameras.objects.all()
    serializer_class = ZoneCameraSerializer


class ZoneCameraListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        camera_ip = request.GET.get("camera")
        queryset = (
            ZoneCameras.objects.filter(camera=camera_ip)
            if camera_ip
            else ZoneCameras.objects.all()
        )
        serializer = ZoneCameraSerializer(queryset, many=True)
        return Response(serializer.data)


class CameraZoneAlgorithmView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        camera_id = request.GET.get("camera")
        queryset = (
            CameraAlgorithm.objects.filter(camera_id=camera_id)
            if camera_id
            else CameraAlgorithm.objects.all()
        )

        algorithms = {}

        for camera_algorithm in queryset:
            algorithm_name = camera_algorithm.algorithm.name
            zones = camera_algorithm.zones
            zone_ids = [zone["id"] for zone in zones] if zones else []
            if algorithm_name in algorithms:
                algorithms[algorithm_name].extend(zone_ids)
            else:
                algorithms[algorithm_name] = zone_ids

        response_data = {"camera": camera_id, "algorithms": algorithms}

        return Response(response_data)


class UniqueImageNameView(APIView):
    """Getting unique container names"""
    def get(self, request, format=None):
        serializer = UniqueImageNameSerializer()
        data = serializer.get_unique_image_names(None)
        return Response(data, status=status.HTTP_200_OK)


class AlgorithmInfoView(APIView):
    def get_queryset(self):
        return Algorithm.objects.exclude(image_name=None)

    def get(self, request, format=None):
        algorithms = self.get_queryset()
        serializer = AlgorithmInfoSerializer(algorithms, many=True)

        additional_data = {
            "name": "5S Control version",
            "version": "v0.5.5",
            "date": "11.27.2023",
            "description": ""
        }

        data = serializer.data
        data.append(additional_data)

        return Response(reversed(data), status=status.HTTP_200_OK)


class UploadAlgorithmView(APIView):
    def post(self, request, id_algorithm: int, format=None):

        algorithm = Algorithm.objects.get(id=id_algorithm)
        uploading_algorithm.apply_async((algorithm.id, algorithm.image_name))

        return Response({"message": "File upload started"}, status=status.HTTP_202_ACCEPTED)


class CameraAlgorithmToggleApiView(APIView):
    """PFE (LeanLens) : active/désactive un algorithme pour une caméra.

    Le endpoint amont `create-process/` pilote le algorithms-controller
    (spawn de conteneurs Docker par pid). Le déploiement PFE exécute la
    détection dans le worker autonome `leanlens-algo` (env-driven), et le
    controller amont est hors service : ce endpoint synchronise donc
    directement l'affectation CameraAlgorithm (même sémantique que le
    bootstrap de première installation), que le worker interroge via
    GET get-process/<ip>/ pour suspendre/reprendre la détection.

    POST {"camera": "<ip>", "algorithm": "<name>", "is_active": true|false}
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        camera_ip = request.data.get("camera")
        algorithm_name = request.data.get("algorithm")
        is_active = bool(request.data.get("is_active", True))

        if not camera_ip or not algorithm_name:
            return Response(
                {"error": "camera and algorithm are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        camera = Camera.objects.filter(id=camera_ip).first()
        if camera is None:
            return Response(
                {"error": f"Camera {camera_ip} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        algorithm = Algorithm.objects.filter(name=algorithm_name).first()
        if algorithm is None:
            return Response(
                {"error": f"Algorithm {algorithm_name} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if is_active:
            _, created = CameraAlgorithm.objects.get_or_create(
                camera=camera,
                algorithm=algorithm,
                defaults={"process_id": 0, "zones": None, "is_active": True},
            )
            return Response(
                {
                    "status": True,
                    "created": created,
                    "message": f"{algorithm_name} enabled on {camera_ip}",
                },
                status=status.HTTP_200_OK,
            )

        deleted, _ = CameraAlgorithm.objects.filter(
            camera=camera, algorithm=algorithm
        ).delete()
        return Response(
            {
                "status": True,
                "deleted": deleted,
                "message": f"{algorithm_name} disabled on {camera_ip}",
            },
            status=status.HTTP_200_OK,
        )


class CameraListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = NoPagination
    queryset = Camera.objects.all()
    serializer_class = CameraSerializer
