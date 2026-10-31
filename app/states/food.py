from aiogram.fsm.state import State, StatesGroup


class FoodStates(StatesGroup):
    # کاربر در حال نوشتن عبارت جستجو است
    searching = State()
