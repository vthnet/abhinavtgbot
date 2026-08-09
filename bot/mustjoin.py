from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import MUST_JOIN_CHANNEL

# Private channel details
PRIVATE_CHANNEL_ID =  -1004217309976
PRIVATE_CHANNEL_LINK = "https://t.me/rush_networks"
PRIVATE_CHANNEL_ID2 =  -1004217309976

BOTUSER = "neuidbot"
# Welcome text with HTML formatting
WELCOME_TEXT = ("❌ 𝖸𝗈𝗎 𝗆𝗎𝗌𝗍 𝗌𝗎𝖻𝗌𝖼𝗋𝗂𝖻𝖾 𝗍𝗈 𝗍𝗁𝖾 𝗈𝖿𝖿𝗂𝖼𝗂𝖺𝗅 𝖻𝗈𝗍 𝖼𝗁𝖺𝗇𝗇𝖾𝗅 𝗍𝗈 𝗎𝗌𝖾 𝗍𝗁𝖾 𝖻𝗈𝗍...\n\n<blockquote>- <b>𝖢𝗁𝖺𝗇𝗇𝖾𝗅</b> - @neumrkt</blockquote>\n\n<b>• Press Verify Button below to check</b>")



async def check_join(client, message: types.Message):
    """
    Check if the user has joined both required channels.
    If not, send the join message and return False.
    """
    try:
        # Public channel check
        member1 = await client.get_chat_member(PRIVATE_CHANNEL_ID2, message.from_user.id)

        # Private channel check
        member2 = await client.get_chat_member(PRIVATE_CHANNEL_ID, message.from_user.id)

        if (member1.status in ["left", "kicked"]) or (member2.status in ["left", "kicked"]):
            await send_join_message(message)
            return False

        return True
    except Exception:
        await send_join_message(message)
        return False


async def send_join_message(message: types.Message):
    """
    Send a message asking the user to join the required channels,
    with inline buttons for both channels in one row and Verify below.
    """
    kb = InlineKeyboardBuilder()

    # First row: both channels
    kb.row(
        types.InlineKeyboardButton(text="📢 Network", url=f"https://t.me/rush_networks"),
        types.InlineKeyboardButton(text="💌 logs ", url="https://t.me/coderush_official")
    )
    kb.row(
         types.InlineKeyboardButton(text="Verify Join ☑️", callback_data="back_main")
    )
        

    

    await message.answer(
        WELCOME_TEXT,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
