from aiogram.fsm.state import StatesGroup, State


class Price_for_trip(StatesGroup):
    new_trip_price = State()
    new_price = State()


class Client_Reject(StatesGroup):
    cli_rej = State()
    origin_cli_rej = State()


class Driver_Reject(StatesGroup):
    driver_rej = State()
    order_status = State()


class Change_Name(StatesGroup):
    new_name = State()


class Reg(StatesGroup):
    name = State()
    contact = State()
    role = State()
    key = State()
    region = State()
    model_car = State()
    number_car = State()
    photo_car = State()
    photo_driver = State()


class Destination(StatesGroup):
    preorder_flag = State()
    current_date = State()
    submission_date = State()
    submission_time = State()
    location_point = State()
    start_coords = State()
    destination_point = State()
    end_coords = State()
    drive_deсition = State()
    confirm_the_trip = State()
    comment = State()
    trip_time = State()
    distance = State()
    price = State()


class Driving_process(StatesGroup):
    driver_id = State()
    order_id = State()
    driver_location = State()


class Feedback(StatesGroup):
    feedback = State()


class TimerStates(StatesGroup):
    waiting_for_timer = State()


class Bonuses(StatesGroup):
    number_bonuses = State()
    perc_of_the_amount = State()


class Promo_Code(StatesGroup):
    name_promo_code = State()


class Referral_Link(StatesGroup):
    name_referral_link = State()


class Reminder(StatesGroup):
    remind_about_preorder = State()
