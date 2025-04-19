from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from timetable.timetable_list import add_timetable_list


class ImportTimeTableView(APIView):
    def get(self, request):
        try:
            add_timetable_list()
            return Response({'status': 'success', 'message': 'timetable added successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
