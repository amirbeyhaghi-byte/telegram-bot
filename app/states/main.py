from aiogram.fsm.state import State, StatesGroup


class MainStates(StatesGroup):
    menu = State()
    entering_gift_code = State()
    admin_menu = State()
    creating_gift_code = State()
    admin_search_user = State()
    sending_receipt = State()
