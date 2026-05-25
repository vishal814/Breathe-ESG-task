from django.urls import path, include
from rest_framework.routers import DefaultRouter
from esg_app.views import (
    ClientViewSet, LocationMappingViewSet, EmissionFactorViewSet,
    IngestionSourceViewSet, NormalizedRecordViewSet,
    UploadSAPView, UploadUtilityView, PullTravelView
)

router = DefaultRouter()
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'locations', LocationMappingViewSet, basename='location')
router.register(r'factors', EmissionFactorViewSet, basename='factor')
router.register(r'ingestions', IngestionSourceViewSet, basename='ingestion')
router.register(r'records', NormalizedRecordViewSet, basename='record')

urlpatterns = [
    path('', include(router.urls)),
    path('ingest/sap/', UploadSAPView.as_view(), name='ingest-sap'),
    path('ingest/utility/', UploadUtilityView.as_view(), name='ingest-utility'),
    path('ingest/travel/', PullTravelView.as_view(), name='ingest-travel'),
]
