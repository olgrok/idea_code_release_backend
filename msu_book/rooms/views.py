from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import rooms.add_rooms_in_db as add_rooms_in_db # Импортируем нужную функцию

class ImportRoomsView(APIView):
    def get(self, request):
        try:
            add_rooms_in_db.add_all_rooms()  # Добавляем все аудитории в базу данных
            return Response({'status': 'success', 'message': 'Rooms added successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
