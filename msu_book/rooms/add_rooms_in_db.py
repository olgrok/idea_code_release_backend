from main.models import Room, RoomType, BuildingChoices
import rooms.room_lists as room_lists

def add_rooms(rooms, floor, building=BuildingChoices.PHYS):
    features = {}
    for room in rooms:
        if Room.objects.filter(name=room).exists():
            continue
        room_obj = Room.objects.create(
            name=room,
            capacity=20,
            building=building,
            floor=floor,
            room_type=RoomType.SEMINAR,
            features=features,
            is_active=True,
        )
        room_obj.save()

# add
def add_all_rooms():
    auditorium_provider = room_lists.AuditoriumProvider()

    # Убедитесь, что get_room_basement и другие методы возвращают список комнат
    add_rooms(auditorium_provider.get_room_basement(),building=BuildingChoices.PHYS, floor=0)  # floors 0 to 5
    add_rooms(auditorium_provider.get_room_1st_floor(),building=BuildingChoices.PHYS, floor=1)
    add_rooms(auditorium_provider.get_room_2nd_floor(),building=BuildingChoices.PHYS, floor=2)
    add_rooms(auditorium_provider.get_room_3rd_floor(),building=BuildingChoices.PHYS, floor=3)
    add_rooms(auditorium_provider.get_room_4th_floor(),building=BuildingChoices.PHYS, floor=4)
    add_rooms(auditorium_provider.get_room_5th_floor(), building=BuildingChoices.PHYS, floor=5)
