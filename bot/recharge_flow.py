import datetime
from bson import ObjectId

from aiogram import F
from aiogram.types import (
    CallbackQuery,
    Message,
    FSInputFile,
    CopyTextButton
)
from html import escape 
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import StateFilter, Command
from pathlib import Path

# Import the fixed functions
from .oxapay import create_invoice, check_invoice

# CONFIG
USDT_TO_INR = 90
MIN_USDT = 0.1
UPI_ID = "happyhuu@fam"
QR_PATH = Path(__file__).resolve().parent.parent / "Qr.jpg"

class RechargeState(StatesGroup):
    choose_method = State()
    upi_amount = State()
    upi_screenshot = State()
    crypto_amount = State()

def register_recharge_handlers(dp, bot, users_col, txns_col, crypto_col, ADMIN_IDS):

    # ==============================
    # 1. MENU
    # ==============================
    async def show_recharge_menu(target: Message, state: FSMContext, edit=False):
        await state.clear()
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 INR (UPI)", callback_data="recharge_upi")
        kb.button(text="🪙 Crypto (Auto)", callback_data="recharge_crypto")
        kb.adjust(1)

        text = "💰 <b>Add Balance</b>\n\nChoose a payment method:"
        if edit:
            await target.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())
        await state.set_state(RechargeState.choose_method)

    @dp.callback_query(F.data == "recharge")
    async def recharge_btn(cq: CallbackQuery, state: FSMContext):
        await show_recharge_menu(cq.message, state, edit=True)

    @dp.message(Command("recharge"))
    async def recharge_cmd(message: Message, state: FSMContext):
        await show_recharge_menu(message, state, edit=False)

    # ==============================
    # 2. UPI FLOW
    # ==============================
    @dp.callback_query(F.data == "recharge_upi")
    async def recharge_upi(cq: CallbackQuery, state: FSMContext):
        await cq.message.delete()
        
        try:
            qr = FSInputFile(QR_PATH)
        except:
            await cq.answer("Server Error: QR missing", show_alert=True)
            return

        kb = InlineKeyboardBuilder()
        kb.button(text="Copy UPI", copy_text=CopyTextButton(text=UPI_ID))
        kb.button(text="✅ Deposit Done", callback_data="upi_done")
        kb.adjust(1)

        msg = await cq.message.answer_photo(
            qr,
            caption=f"📲 <b>UPI Payment</b>\n\nID: <code>{UPI_ID}</code>\n\nPay and click 'Deposit Done'.",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        await state.update_data(last_msg=msg.message_id)

    @dp.callback_query(F.data == "upi_done")
    async def upi_done(cq: CallbackQuery, state: FSMContext):
        await cq.message.delete()
        msg = await cq.message.answer("💰 Enter amount sent (INR):")
        await state.update_data(last_msg=msg.message_id)
        await state.set_state(RechargeState.upi_amount)

    @dp.message(StateFilter(RechargeState.upi_amount))
    async def upi_amt(message: Message, state: FSMContext):
        await message.delete()
        data = await state.get_data()
        try:
            await bot.delete_message(message.chat.id, data.get("last_msg"))
        except: pass

        if not message.text.isdigit():
            msg = await message.answer("❌ Invalid amount.")
            await state.update_data(last_msg=msg.message_id)
            return

        amount = float(message.text)
        msg = await message.answer("📸 Send Screenshot:")
        await state.update_data(amount=amount, last_msg=msg.message_id)
        await state.set_state(RechargeState.upi_screenshot)

    @dp.message(StateFilter(RechargeState.upi_screenshot), F.photo)
    async def upi_screen(message: Message, state: FSMContext):
        data = await state.get_data()
        try:
            await bot.delete_message(message.chat.id, data.get("last_msg"))
        except: pass

        txn_id = txns_col.insert_one({
            "user_id": message.from_user.id,
            "username": message.from_user.username,
            "full_name": message.from_user.full_name,
            "amount": data["amount"],
            "method": "upi",
            "status": "pending",
            "created_at": datetime.datetime.utcnow()
        }).inserted_id

        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Approve", callback_data=f"approve_txn:{txn_id}")
        kb.button(text="❌ Decline", callback_data=f"decline_txn:{txn_id}")
        
        for admin in ADMIN_IDS:
            await bot.send_photo(
                admin, message.photo[-1].file_id,
                caption=
                f"🧾 <b>UPI</b>\nUser: {escape(message.from_user.full_name)}\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"🆔 Username: @{message.from_user.username}\n"
                f"Amt: ₹{data['amount']}",
                parse_mode="HTML", reply_markup=kb.as_markup()
            )
        
        await message.answer("✅ Deposit Request Submitted!\n\n⚡ Your proof is being verified.\n📝 Status: <code>Pending</code>\n⏳ Time: 3 Hours (Max)\n\nYou will be notified automatically once funds are added.")
        await state.clear()

    # ==============================
    # 3. CRYPTO FLOW (OXAPAY)
    # ==============================
    @dp.callback_query(F.data == "recharge_crypto")
    async def recharge_crypto(cq: CallbackQuery, state: FSMContext):
        await cq.message.delete()
        msg = await cq.message.answer(f"🪙 Enter amount in USDT (Min: {MIN_USDT}):")
        await state.update_data(last_msg=msg.message_id)
        await state.set_state(RechargeState.crypto_amount)

    @dp.message(StateFilter(RechargeState.crypto_amount))
    async def crypto_amt(message: Message, state: FSMContext):
        # 1. Cleanup UI
        await message.delete()
        data = await state.get_data()
        try:
            await bot.delete_message(message.chat.id, data.get("last_msg"))
        except: pass

        # 2. Validate
        try:
            usdt = float(message.text)
            if usdt < MIN_USDT: raise ValueError
        except:
            msg = await message.answer("❌ Invalid amount.")
            await state.update_data(last_msg=msg.message_id)
            return

        # 3. Generate Invoice
        wait_msg = await message.answer("⌛ Generating Invoice...")
        order_id = f"Oxa_{message.from_user.id}_{int(datetime.datetime.now().timestamp())}"
        
        res = create_invoice(usdt, order_id)

        if not res["success"]:
            await wait_msg.edit_text(f"❌ API Error: {res['error']}")
            await state.clear()
            return

        # 4. Extract Data (New API Structure)
        # response structure: { "data": { "track_id": "...", "payment_url": "..." } }
        inv_data = res["data"]
        track_id = str(inv_data["track_id"])
        pay_url = inv_data["payment_url"]
        
        inr_val = round(usdt * USDT_TO_INR, 2)

        # 5. Save to DB
        crypto_col.insert_one({
            "user_id": message.from_user.id,
            "track_id": track_id,
            "amount_usdt": usdt,
            "amount_inr": inr_val,
            "status": "pending",
            "created_at": datetime.datetime.utcnow()
        })

        # 6. Show Invoice
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Pay Now", url=pay_url)
        kb.button(text="✅ I Have Paid", callback_data=f"check_crypto:{track_id}")
        kb.button(text="❌ Cancel", callback_data=f"cancel_crypto:{track_id}")
        kb.adjust(1)

        await wait_msg.delete()
        await message.answer(
            f"📋 <b>Crypto Invoice</b>\n\n"
            f"💵 Amount: <b>{usdt} USDT</b>\n"
            f"💰 INR Value: ₹{inr_val}\n"
            f"⏳ Expires in: 30 Mins\n\n"
            f"⚠️ Send EXACT amount shown on the link.",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        await state.clear()

    @dp.callback_query(F.data.startswith("check_crypto"))
    async def check_crypto(cq: CallbackQuery):
        track_id = cq.data.split(":")[1]
        
        # Check DB
        inv = crypto_col.find_one({"track_id": track_id})
        if not inv:
            await cq.answer("Invoice not found.", show_alert=True)
            return
        
        if inv["status"] == "paid":
            await cq.answer("Already Paid!", show_alert=True)
            return

        # Check API
        api_res = check_invoice(track_id) # Returns the full JSON response
        
        # The Check Status endpoint usually returns "status": "Paid" or "Waiting" inside "data" or root
        # Let's inspect the common structure for check status:
        # { "result": 100, "message": "...", "data": { "status": "Paid", ... } }
        # OR simply { "status": "Paid" ... } depending on exact endpoint version.
        # We will check deeply.
        
        remote_status = "unknown"
        if "data" in api_res and "status" in api_res["data"]:
            remote_status = str(api_res["data"]["status"]).lower()
        elif "status" in api_res:
             remote_status = str(api_res["status"]).lower()

        if remote_status in ["paid", "complete", "confirmed"]:
            # Success
            crypto_col.update_one({"track_id": track_id}, {"$set": {"status": "paid"}})
            users_col.update_one({"_id": inv["user_id"]}, {"$inc": {"balance": inv["amount_inr"]}})
            usdt = inv["amount_usdt"]
            inr = inv["amount_inr"]
            
            await cq.message.delete()
            await bot.send_message(
                inv["user_id"],
                f"✅ <b>Payment Received!</b>\n\n"
                f"💵 Amount Added: <b>{usdt} USDT</b>\n"
                f"💰 INR Value: ₹{inv['amount_inr']}\n"
                f"➕ Track ID - <code>{track_id}</code> ",
                parse_mode="HTML"
            )
            admin_log_text = (
                f"🚀 <b>New Crypto Payment Received</b>\n\n"
                f"👤 <b>User:</b> {escape(cq.from_user.full_name)}\n"
                f"🆔 <b>User ID:</b> <code>{inv['user_id']}</code>\n"
                f"🔗 <b>Username:</b> @{cq.from_user.username or 'N/A'}\n"
                f"🪙 <b>Amount Added:</b> {usdt} USDT\n"
                f"🇮🇳 <b>INR Value:</b> ₹{inr}\n"
                f"🧾 <b>Track ID:</b> <code>{track_id}</code>\n"
            )
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, admin_log_text, parse_mode="HTML")
                except Exception as e:
                    print(f"Error sending log to admin {admin_id}: {e}")
        elif remote_status == "confirming":
            await cq.answer("⏳ Payment detected but confirming on blockchain. Please wait.", show_alert=True)
        else:
            await cq.answer(f"Status: {remote_status.capitalize()}\nPayment not confirmed yet.", show_alert=True)
    @dp.callback_query(F.data.startswith("cancel_crypto"))
    async def cancel_crypto(cq: CallbackQuery):
        await cq.message.delete()
        await cq.answer("Cancelled")

    # ==============================
    # 4. ADMIN
    # ==============================
    @dp.callback_query(F.data.startswith("approve_txn"))
    async def approve_txn(cq: CallbackQuery):
        txn_id = cq.data.split(":")[1]
        txn = txns_col.find_one({"_id": ObjectId(txn_id)})
        if txn and txn["status"] == "pending":
            users_col.update_one({"_id": txn["user_id"]}, {"$inc": {"balance": txn["amount"]}})
            txns_col.update_one({"_id": ObjectId(txn_id)}, {"$set": {"status": "approved"}})
            await bot.send_message(txn["user_id"], f"✅ Deposit Approved\n\n💸 Balance added: ₹{txn['amount']}")
            await cq.message.edit_caption(caption=cq.message.caption+"\n\n✅ APPROVED", parse_mode="HTML")
        await cq.answer("Done")

    @dp.callback_query(F.data.startswith("decline_txn"))
    async def decline_txn(cq: CallbackQuery):
        txn_id = cq.data.split(":")[1]
        txns_col.update_one({"_id": ObjectId(txn_id)}, {"$set": {"status": "declined"}})
        await cq.message.edit_caption(caption=cq.message.caption+"\n\n❌ DECLINED", parse_mode="HTML")
        await cq.answer("Declined")
