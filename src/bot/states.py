from aiogram.fsm.state import State, StatesGroup


class ShiftStart(StatesGroup):
    selecting_site = State()
    entering_site_name = State()
    awaiting_location = State()
    awaiting_photo = State()


class ShiftStop(StatesGroup):
    confirming = State()
    awaiting_end_location = State()
    awaiting_end_photo = State()


class GeofenceEdit(StatesGroup):
    collecting_points = State()


class Onboarding(StatesGroup):
    awaiting_name = State()
    awaiting_rate = State()
    awaiting_reminder = State()


class CalendarFlow(StatesGroup):
    awaiting_advance_amount = State()
    awaiting_payment_amount = State()


class ProfileEdit(StatesGroup):
    awaiting_name = State()
    awaiting_rate = State()
    awaiting_currency = State()
    awaiting_remind_hour = State()
