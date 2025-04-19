from main.models import Room, TIME_SLOTS_DETAILS, BookingSlot, BookingSlotStatus
from rooms.room_lists import get_id_all_rooms
from timetable.get_timetable_by_id_room import get_json_timetable_room_by_id
from datetime import datetime

def get_room_id_by_name(room_name: str) -> int | None:
    try:
        room = Room.objects.get(name=room_name)
        return room.id
    except Room.DoesNotExist:
        return None


def add_timetable_list():
    room_dict = get_id_all_rooms()
    for room_name, room_id in room_dict.items():
        # print(str(room_name) + "  // " + str(room_id))
        schedule = get_json_timetable_room_by_id(room_id)
        # print(f"Расписание для аудитории {room_name} (ID {room_id}):")
        for item in schedule["items"]:
            start_ts = item["start_ts"]
            end_ts = item["end_ts"]
            for room in item["room"]:
                if room["id"] == room_id:

                    number_slot = convert_from_time_to_time_slots(start_ts[11:16])
                    # print(str(room["name"]) + "  // " + str(start_ts[:10]) + " // " + " // " + "status: unavailable // " + "room_id" + str(get_room_id_by_name(room["name"])) + " // " + str(start_ts[11:16]) + " // " + str(number_slot))
                    BookingSlot.objects.get_or_create(room_id= get_room_id_by_name(room["name"]), date=start_ts[:10], status=BookingSlotStatus.UNAVAILABLE, slot_number=number_slot)
                    BookingSlot.objects.get_or_create(room_id= get_room_id_by_name(room["name"]), date=start_ts[:10], status=BookingSlotStatus.UNAVAILABLE, slot_number=number_slot + 1)
                    # print(f"Аудитория: {room['name']}, начало: {start_ts}, конец: {end_ts}, предмет {item['name']}")


def convert_from_time_to_time_slots(time_str: str) -> int | None:
    # Преобразуем строку в datetime.time
    target_time = datetime.strptime(time_str, "%H:%M").time()

    # Сравниваем со слотами
    for slot_num, slot in TIME_SLOTS_DETAILS.items():
        if slot["start"] == target_time:
            return slot_num
    return None
