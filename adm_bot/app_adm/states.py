from aiogram.fsm.state import StatesGroup, State


class Admin_ID(StatesGroup):
    admin_id = State()


class User_State(StatesGroup):
    user_tg_id = State()
    user_tg_id_user_info = State()
    user_tg_id_block_user = State()
    user_tg_id_unblock_user = State()
    user_tg_id_get_messages = State()
    user_tg_id_delete_messages = State()
    user_tg_id_change_wallet = State()
    user_tg_id_set_driver_admin = State()
    driver_tg_id_for_set_status_is_deleted = State()


class Table_Name(StatesGroup):
    table_name = State()


class Promo_Code_State(StatesGroup):
    name_promo_code = State()
    bonuses = State()
    name_promo_code_for_deletion = State()


class Reg_Admin(StatesGroup):
    tg_id_admin = State()
    username_admin = State()
    name_admin = State()
    contact_admin = State()
    adm_id = State()
    driver_adm_id = State()


class User_Wallet(StatesGroup):
    increase_client_bonuses = State()
    reduce_client_bonuses = State()
    increase_driver_coins = State()
    reduce_driver_coins = State()
    client_id = State()
    driver_id = State()


class Delete_Account(StatesGroup):
    soft_delete_account = State()
    full_delete_account = State()


class Change_PSWRD(StatesGroup):
    old_pswrd = State()
    new_pswrd = State()
    confirm_new_pswrd = State()
