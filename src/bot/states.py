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
