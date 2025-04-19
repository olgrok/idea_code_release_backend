import requests
from datetime import date, timedelta

def get_json_timetable_room_by_id(room_id):
    date_url = date.today() + timedelta(days=35)
    url = "https://api.profcomff.com/timetable/event/?end=" + str(date_url) + "&room_id=" + str(room_id) + "&format=json&limit=1000000&offset=0"

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Ошибка запроса: {response.status_code}")

