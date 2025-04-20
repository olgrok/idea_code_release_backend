from rest_framework import generics
from main.models import Event
from .serializers import EventSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend
from main.models import Event
from .serializers import EventSerializer, SubjectSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from main.models import User
class EventCreateView(generics.CreateAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]  # Example: Require authentication
    def perform_create(self, serializer):
        serializer.save(initiator=User.objects.get(user_id=self.request.user.id))  # Set initiator to the logged-in user


class EventListView(generics.ListAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['date', 'room', 'initiator']  # Exact matches
    search_fields = ['subject', 'description']  # Partial matches
    ordering_fields = ['date', 'start_slot', 'end_slot'] #ordering

    def get_queryset(self):
        queryset = super().get_queryset()
        subject = self.request.query_params.get('subject', None)
        if subject is not None:
            queryset = queryset.filter(subject__icontains=subject) # case-insensitive contains
        return queryset

@api_view(['GET'])
def list_subjects(request):
    """
    Returns a list of distinct event subjects.
    """
    subjects = Event.objects.values('subject').distinct()
    serializer = SubjectSerializer(subjects, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)