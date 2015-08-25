from hotel import *


@all_renderable(c.STAFF_ROOMS)
class Root:
    def index(self, session):
        attendee = session.admin_attendee()
        three_days_before = (c.EPOCH - timedelta(days=3)).strftime('%A')
        two_days_before = (c.EPOCH - timedelta(days=2)).strftime('%A')
        day_before = (c.EPOCH - timedelta(days=1)).strftime('%A')
        last_day = c.ESCHATON.strftime('%A')
        return {
            'dump': _hotel_dump(session),
            'nights': [{
                'core': False,
                'name': three_days_before.lower(),
                'val': getattr(c, three_days_before.upper()),
                'desc': three_days_before + ' night (for super-early setup volunteers)'
            }, {
                'core': False,
                'name': two_days_before.lower(),
                'val': getattr(c, two_days_before.upper()),
                'desc': two_days_before + ' night (for early setup volunteers)'
            }, {
                'core': False,
                'name': day_before.lower(),
                'val': getattr(c, day_before.upper()),
                'desc': day_before + ' night (for setup volunteers)'
            }] + [{
                'core': True,
                'name': c.NIGHTS[night].lower(),
                'val': night,
                'desc': c.NIGHTS[night]
            } for night in c.CORE_NIGHTS] + [{
                'core': False,
                'name': last_day.lower(),
                'val': getattr(c, last_day.upper()),
                'desc': last_day + ' night (for teardown volunteers)'
            }]
        }

    @ajax
    def create_room(self, session, **params):
        params['nights'] = list(filter(bool, [params.pop(night, None) for night in c.NIGHT_NAMES]))
        session.add(session.room(params))
        session.commit()
        return _hotel_dump(session)

    @ajax
    def edit_room(self, session, **params):
        params['nights'] = list(filter(bool, [params.pop(night, None) for night in c.NIGHT_NAMES]))
        session.room(params)
        session.commit()
        return _hotel_dump(session)

    @ajax
    def delete_room(self, session, id):
        room = session.room(id)
        session.delete(room)
        session.commit()
        return _hotel_dump(session)

    @ajax
    def lock_in_room(self, session, id):
        room = session.room(id)
        room.locked_in = True
        session.commit()
        return _hotel_dump(session)

    @ajax
    def assign_to_room(self, session, attendee_id, room_id):
        room = session.room(room_id)
        for other_room in session.query(RoomAssignment).filter_by(attendee_id=attendee_id).all():
            if set(other_room.nights_ints).intersection(room.nights_ints):
                break  # don't assign someone to a room which overlaps with an existing room assignment
        else:
            attendee = session.attendee(attendee_id)
            ra = RoomAssignment(attendee=attendee, room=room)
            session.add(ra)
            hr = attendee.hotel_requests
            if room.setup_teardown:
                hr.approved = True
            elif not hr.approved:
                hr.decline()
            session.commit()
        return _hotel_dump(session)

    @ajax
    def unassign_from_room(self, session, attendee_id):
        for ra in session.query(RoomAssignment).filter_by(attendee_id=attendee_id).all():
            session.delete(ra)
        session.commit()
        return _hotel_dump(session)


def _attendee_dict(attendee):
    return {
        'id': attendee.id,
        'name': attendee.full_name,
        'nights': getattr(attendee.hotel_requests, 'nights_display', ''),
        'special_needs': getattr(attendee.hotel_requests, 'special_needs', ''),
        'wanted_roommates': getattr(attendee.hotel_requests, 'wanted_roommates', ''),
        'unwanted_roommates': getattr(attendee.hotel_requests, 'unwanted_roommates', ''),
        'approved': int(getattr(attendee.hotel_requests, 'approved', False)),
        'departments': ' / '.join(attendee.assigned_depts_labels),
        'nights_lookup': {night: getattr(attendee.hotel_requests, night, False) for night in c.NIGHT_NAMES},
    }


def _room_dict(session, room):
    return dict({
        'id': room.id,
        'notes': room.notes,
        'locked_in': room.locked_in,
        'nights': room.nights_display,
        'attendees': [_attendee_dict(ra.attendee) for ra in sorted(room.assignments, key=lambda ra: ra.attendee.full_name)]
    }, **{
        night: getattr(room, night) for night in c.NIGHT_NAMES
    })


def _get_declined(session):
    return [_attendee_dict(a) for a in session.query(Attendee)
                                              .order_by(Attendee.full_name)
                                              .join(Attendee.hotel_requests)
                                              .filter(Attendee.hotel_requests != None, HotelRequests.nights == '').all()]


def _get_unconfirmed(session, assigned_ids):
    return [_attendee_dict(a) for a in session.query(Attendee)
                                              .order_by(Attendee.full_name)
                                              .filter(Attendee.badge_type == c.STAFF_BADGE,
                                                      Attendee.hotel_requests == None).all()
                              if a not in assigned_ids]


def _get_unassigned(session, assigned_ids):
    return [_attendee_dict(a) for a in session.query(Attendee)
                                              .order_by(Attendee.full_name)
                                              .join(Attendee.hotel_requests)
                                              .filter(Attendee.hotel_requests != None,
                                                      HotelRequests.nights != '').all()
                              if a.id not in assigned_ids]


def _hotel_dump(session):
    rooms = [_room_dict(session, room) for room in session.query(Room).order_by(Room.created).all()]
    assigned = sum([r['attendees'] for r in rooms], [])
    assigned_ids = [a['id'] for a in assigned]
    return {
        'rooms': rooms,
        'assigned': assigned,
        'declined': _get_declined(session),
        'unconfirmed': _get_unconfirmed(session, assigned_ids),
        'unassigned': _get_unassigned(session, assigned_ids)
    }
