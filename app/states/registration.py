from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    first_name = State()
    last_name = State()
    phone_number = State()
    password = State()


class LoginStates(StatesGroup):
    phone_number = State()
    password = State()