"""Klaviatura qurish yordamchilari. Reply-klaviaturalar suhbat davomida doim
ko'rinadigan "Bekor qilish"/"O'tkazib yuborish" kabi tugmalar uchun, inline
klaviaturalar esa ro'yxatdan tanlash (mijoz/mahsulot/supplier) va
tasdiqlash/bekor qilish uchun ishlatiladi (PhoneAd-bot'dagi
`step_keyboard()`/`models_keyboard(page)` uslubiga o'xshash)."""
import calendar as calendar_module
from datetime import date

from telebot import types

CANCEL_TEXT = "❌ Bekor qilish"
BACK_TEXT = "⬅️ Orqaga"
SKIP_TEXT = "⏭ O'tkazib yuborish"
DONE_TEXT = "✅ Yakunlash"
ADD_MORE_TEXT = "➕ Yana qo'shish"

MENU_DASHBOARD = '📊 Dashboard'
MENU_PURCHASES = '🛒 Xarid'
MENU_BUTCHERING = "🔪 Bo'laklash"
MENU_SALES = '💰 Sotish'
MENU_PAYMENTS = "💳 To'lovlar"
MENU_EXPENSES = '🧾 Xarajatlar'
MENU_INVENTORY = '📦 Ombor'
MENU_REPORTS = '📈 Hisobotlar'
MENU_CUSTOMERS = '👥 Mijozlar'
MENU_SUPPLIERS = '🚚 Yetkazib beruvchilar'
MENU_KASSA = '💵 Kassa'


def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(MENU_DASHBOARD)
    kb.row(MENU_PURCHASES, MENU_BUTCHERING)
    kb.row(MENU_SALES, MENU_PAYMENTS)
    kb.row(MENU_EXPENSES, MENU_INVENTORY)
    kb.row(MENU_CUSTOMERS, MENU_SUPPLIERS)
    kb.row(MENU_REPORTS, MENU_KASSA)
    return kb


def cancel_only():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(CANCEL_TEXT)
    return kb


def cancel_and_skip():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(SKIP_TEXT)
    kb.row(CANCEL_TEXT)
    return kb


def confirm_cancel_inline(confirm_data, cancel_data='noop:cancel'):
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton('✅ Tasdiqlash', callback_data=confirm_data),
        types.InlineKeyboardButton('❌ Bekor qilish', callback_data=cancel_data),
    )
    return kb


def picker(prefix, items, page=0, page_size=8, extra_rows=None):
    """`items`: [(id, label), ...]. Callback data: "{prefix}:{id}" har bir
    qator uchun, "{prefix}_pg:{page}" sahifalash uchun."""
    kb = types.InlineKeyboardMarkup()
    start = page * page_size
    chunk = items[start:start + page_size]
    for item_id, label in chunk:
        kb.row(types.InlineKeyboardButton(str(label)[:60], callback_data=f'{prefix}:{item_id}'))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton('⬅️', callback_data=f'{prefix}_pg:{page - 1}'))
    if start + page_size < len(items):
        nav.append(types.InlineKeyboardButton('➡️', callback_data=f'{prefix}_pg:{page + 1}'))
    if nav:
        kb.row(*nav)
    for row in (extra_rows or []):
        kb.row(*row)
    return kb


MONTH_NAMES_UZ = [
    'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
    'Iyul', 'Avgust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr',
]
WEEKDAY_LABELS_UZ = ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya']


def calendar_keyboard(prefix, year=None, month=None, extra_rows=None):
    """Oy grid'i: har bir kun `{prefix}:{YYYY-MM-DD}`, oy almashtirish
    `{prefix}_nav:{YYYY-MM}`, bo'sh/sarlavha katakchalari `noop:cal`
    callback_data bilan (dispatcher bularni indamay javob beradi)."""
    today = date.today()
    year = year or today.year
    month = month or today.month
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    kb = types.InlineKeyboardMarkup(row_width=7)
    kb.row(
        types.InlineKeyboardButton('◀️', callback_data=f'{prefix}_nav:{prev_year}-{prev_month:02d}'),
        types.InlineKeyboardButton(f'{MONTH_NAMES_UZ[month - 1]} {year}', callback_data='noop:cal'),
        types.InlineKeyboardButton('▶️', callback_data=f'{prefix}_nav:{next_year}-{next_month:02d}'),
    )
    kb.row(*[types.InlineKeyboardButton(w, callback_data='noop:cal') for w in WEEKDAY_LABELS_UZ])
    for week in calendar_module.Calendar(firstweekday=0).monthdayscalendar(year, month):
        kb.row(*[
            types.InlineKeyboardButton(
                str(day) if day else ' ',
                callback_data=f'{prefix}:{year}-{month:02d}-{day:02d}' if day else 'noop:cal',
            )
            for day in week
        ])
    for row in (extra_rows or []):
        kb.row(*row)
    return kb


def add_more_or_done(add_data, done_data):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(ADD_MORE_TEXT, callback_data=add_data))
    kb.row(types.InlineKeyboardButton(DONE_TEXT, callback_data=done_data))
    return kb
