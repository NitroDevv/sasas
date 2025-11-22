import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ==================== KONFIGURATSIYA ====================
BOT_TOKEN = "8132396703:AAG2tAq0qm_QnVFErsMpd0RcL1pyqVR9a2Y"
ADMIN_ID = "8281933162"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class RedBlackKassaBot:
    def __init__(self):
        self.token = BOT_TOKEN
        self.admin_id = ADMIN_ID
        self.admins = self.load_admins()
        self.initialize_file_system()

    # ==================== MAJBURIY OBUNA FUNKSIYASI ====================

    async def joinchat(self, user_id: int, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None) -> bool:
        """Majburiy obunani tekshirish"""
        try:
            channels = self.get_setting("kanal/ch.txt")
            if not channels or channels.strip() == "":
                return True

            channel_list = [ch.strip() for ch in channels.split('\n') if ch.strip()]
            if not channel_list:
                return True

            keyboard = []
            all_subscribed = True

            for channel in channel_list:
                if channel.startswith('@'):
                    channel_username = channel[1:]
                else:
                    channel_username = channel

                try:
                    # Kanal nomini olish
                    chat = await context.bot.get_chat(f"@{channel_username}")
                    channel_title = chat.title

                    # Foydalanuvchi a'zoligini tekshirish
                    member = await context.bot.get_chat_member(f"@{channel_username}", user_id)
                    status = member.status

                    if status in ['creator', 'administrator', 'member']:
                        # Obuna bo'lgan
                        keyboard.append(
                            [InlineKeyboardButton(f"✅ {channel_title}", url=f"https://t.me/{channel_username}")])
                    else:
                        # Obuna bo'lmagan
                        keyboard.append(
                            [InlineKeyboardButton(f"❌ {channel_title}", url=f"https://t.me/{channel_username}")])
                        all_subscribed = False

                except Exception as e:
                    logger.error(f"Kanal tekshirishda xato {channel}: {e}")
                    keyboard.append([InlineKeyboardButton(f"❌ {channel}", url=f"https://t.me/{channel_username}")])
                    all_subscribed = False

            # Tekshirish tugmasini qo'shish
            keyboard.append([InlineKeyboardButton("🔄 Tekshirish", callback_data="check_subscription")])

            if not all_subscribed:
                if update and hasattr(update, 'message'):
                    await update.message.reply_text(
                        "<b>⚠️ Botdan to'liq foydalanish uchun quyidagi kanallarimizga obuna bo'ling va «🔄 Tekshirish» tugmasini bosing!</b>",
                        parse_mode='HTML',
                        disable_web_page_preview=True,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                return False
            else:
                return True

        except Exception as e:
            logger.error(f"Joinchat funksiyasida xato: {e}")
            return True

    async def check_subscription_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Tekshirish tugmasi handleri"""
        query = update.callback_query
        user_id = query.from_user.id

        await query.answer()

        if query.data == "check_subscription":
            is_subscribed = await self.joinchat(user_id, None, context)

            if is_subscribed:
                # Referal bonus berish
                try:
                    ref_id_file = f"step/{user_id}.id"
                    cid_file = f"step/{user_id}.cid"

                    if os.path.exists(ref_id_file) and os.path.exists(cid_file):
                        with open(ref_id_file, "r") as f:
                            ref_id = f.read().strip()
                        with open(cid_file, "r") as f:
                            cid = f.read().strip()

                        if ref_id != str(user_id):
                            referal_bonus = int(self.get_setting("pul/referal.txt"))
                            currency = self.get_setting("pul/valyuta.txt")

                            current_balance = int(self.get_user_data(cid, "hisob"))
                            new_balance = current_balance + referal_bonus
                            self.set_user_data(cid, "hisob", str(new_balance))

                            current_refs = int(self.get_user_data(cid, "referal"))
                            new_refs = current_refs + 1
                            self.set_user_data(cid, "referal", str(new_refs))

                            await context.bot.send_message(
                                chat_id=int(cid),
                                text=f"🎉 Yangi referal! Hisobingizga {referal_bonus} {currency} qo'shildi!",
                                parse_mode='HTML'
                            )

                        # Fayllarni o'chirish
                        if os.path.exists(ref_id_file):
                            os.remove(ref_id_file)
                        if os.path.exists(cid_file):
                            os.remove(cid_file)

                except Exception as e:
                    logger.error(f"Referal bonus berishda xato: {e}")

                await query.message.delete()
                start_text = self.get_setting("matn/start.txt")
                await context.bot.send_message(
                    chat_id=user_id,
                    text=start_text,
                    parse_mode='HTML',
                    reply_markup=self.get_main_menu(str(user_id))
                )
            else:
                await query.answer("⚠️ Hali barcha kanallarga obuna bo'lmagansiz!", show_alert=True)

    # ==================== HANDLERLARGA MAJBURIY OBUNA TEKSHIRISH QO'SHISH ====================

    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)

        if self.is_banned(user_id):
            await update.message.reply_text("❌ Siz bloklangansiz!")
            return

        self.add_user_to_stats(user_id)

        # Majburiy obunani tekshirish
        is_subscribed = await self.joinchat(update.effective_user.id, update, context)
        if not is_subscribed:
            # Agar obuna bo'lmagan bo'lsa, step ni saqlaymiz
            if context.args and len(context.args) > 0:
                ref_id = context.args[0]
                if ref_id != user_id:
                    os.makedirs("step", exist_ok=True)
                    with open(f"step/{user_id}.id", "w") as f:
                        f.write(ref_id)
                    with open(f"step/{user_id}.cid", "w") as f:
                        f.write(ref_id)
            return

        # Agar obuna bo'lgan bo'lsa yoki obuna talab qilinmasa
        if context.args and len(context.args) > 0:
            ref_id = context.args[0]
            if ref_id != user_id:
                await self.process_referal(ref_id, user_id, context)

        start_text = self.get_setting("matn/start.txt")
        await update.message.reply_text(
            start_text,
            parse_mode='HTML',
            reply_markup=self.get_main_menu(user_id)
        )
        self.delete_user_step(user_id)

    async def bet_deposit_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if self.is_banned(user_id):
            await update.message.reply_text("❌ Siz bloklangansiz!")
            return

        # Majburiy obunani tekshirish
        is_subscribed = await self.joinchat(update.effective_user.id, update, context)
        if not is_subscribed:
            return

        text = """<b>❓O'zbekistonda qimor va tavakkalchilikka asoslangan o'yinlarni tashkil etish, o'tkazish va targ'ib qilish faoliyati uchun javobgarlik mavjud !

❓ Siz  «️✅ Qabul qildim» tugmasini bosish orqali bunga rozilik bildirgan bo'lasiz</b>"""

        keyboard = [[InlineKeyboardButton("✅ Qabul qildim", callback_data="ovozber")]]
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    async def balance_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if self.is_banned(user_id):
            await update.message.reply_text("❌ Siz bloklangansiz!")
            return

        # Majburiy obunani tekshirish
        is_subscribed = await self.joinchat(update.effective_user.id, update, context)
        if not is_subscribed:
            return

        balance = self.get_user_data(user_id, "hisob")
        ref_count = self.get_user_data(user_id, "referal")
        min_withdraw = self.get_setting("pul/minpul.txt")
        currency = self.get_setting("pul/valyuta.txt")

        caption = f"""🖥️ <b>Profilingiz haqida ma'lumot:</b>

🪪 <b>Ismingiz:</b> {update.effective_user.first_name}
🆔 <b>ID raqamingiz:</b> <code>{user_id}</code>
💰 <b>Hisobingiz:</b> {balance} {currency}
🗣️ <b>Takliflaringiz:</b> {ref_count} ta
💰 <b>Minimal pul yechish:</b> {min_withdraw} {currency}

<b>@RedBlackKassa | Official 2024</b>"""

        keyboard = [[InlineKeyboardButton("💳 Pul yechish", callback_data="yechish")]]
        await update.message.reply_photo(
            photo="https://t.me/DasturchiNet/1888",
            caption=caption,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def referal_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if self.is_banned(user_id):
            await update.message.reply_text("❌ Siz bloklangansiz!")
            return

        # Majburiy obunani tekshirish
        is_subscribed = await self.joinchat(update.effective_user.id, update, context)
        if not is_subscribed:
            return

        ref_count = self.get_user_data(user_id, "referal")
        ref_bonus = self.get_setting("pul/referal.txt")
        currency = self.get_setting("pul/valyuta.txt")
        bot_username = (await context.bot.get_me()).username

        caption = f"""🗣️ <b>Sizning referallaringiz:</b> {ref_count} ta
🔗 <b>Sizning referal havolangiz:</b>

<code>https://t.me/{bot_username}?start={user_id}</code> 

💰 <b>Har bir referalingiz uchun sizga {ref_bonus} {currency} beriladi!</b>"""

        await update.message.reply_photo(
            photo="https://t.me/DasturchiNet/1888",
            caption=caption,
            parse_mode='HTML'
        )

    async def payments_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if self.is_banned(user_id):
            await update.message.reply_text("❌ Siz bloklangansiz!")
            return

        # Majburiy obunani tekshirish
        is_subscribed = await self.joinchat(update.effective_user.id, update, context)
        if not is_subscribed:
            return

        payment_channel = self.get_setting("kanal/tolovlar.txt")
        await update.message.reply_text(
            f"<b>🗒️ Bizning bot orqali to'langan barcha to'lovlar kanali:</b> {payment_channel}",
            parse_mode='HTML'
        )

    async def guide_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if self.is_banned(user_id):
            await update.message.reply_text("❌ Siz bloklangansiz!")
            return

        # Majburiy obunani tekshirish
        is_subscribed = await self.joinchat(update.effective_user.id, update, context)
        if not is_subscribed:
            return

        guide_text = """<b>❓ Bot nima qila oladi?

— Botimiz orqali Bukmeker kompaniyalarda o'z hisobingizni to'ldirishingiz mumkin

❓ Referal orqali yig'ilgan pulni qanday yechib olaman?

— 💵 Hisobim bo'limiga o'ting va «💰 Pul yechish» tugmasini bosing. To'lov tizimlaridan birini tanlang. Karta raqamingiz yoki telefon raqamingizni kiriting.</b>"""
        await update.message.reply_text(guide_text, parse_mode='HTML')

    # ==================== CALLBACK HANDLER ====================

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = query.data

        await query.answer()

        if self.is_banned(user_id):
            await query.message.edit_text("❌ Siz bloklangansiz!")
            return

        logger.info(f"Callback data: {data} from user: {user_id}")

        # Tekshirish tugmasi
        if data == "check_subscription":
            await self.check_subscription_handler(update, context)
            return

        # 1XBET to'ldirish
        elif data == "ovozber":
            # Majburiy obunani tekshirish
            is_subscribed = await self.joinchat(query.from_user.id, None, context)
            if not is_subscribed:
                await query.answer("⚠️ Avval barcha kanallarga obuna bo'ling!", show_alert=True)
                return

            await query.message.delete()
            await context.bot.send_photo(
                chat_id=query.from_user.id,
                photo="https://t.me/DasturchiNet/1890",
                caption="<b>💴 1XBET ID raqamingizni kiriting\n\n✅ <i>Namuna:</i> <code>181380567</code></b>",
                parse_mode='HTML',
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("◀️ Orqaga")]], resize_keyboard=True)
            )
            self.set_user_step(user_id, "oplata")

        # Pul yechish
        elif data == "yechish":
            # Majburiy obunani tekshirish
            is_subscribed = await self.joinchat(query.from_user.id, None, context)
            if not is_subscribed:
                await query.answer("⚠️ Avval barcha kanallarga obuna bo'ling!", show_alert=True)
                return

            payment_types = self.get_setting("number/turi.txt")
            if not payment_types.strip():
                await query.answer("⚠️ Pul yechish tizimlari qo'shilmagan!", show_alert=True)
                return

            payment_list = [pt.strip() for pt in payment_types.split('\n') if pt.strip()]
            keyboard = []
            for payment in payment_list:
                keyboard.append([InlineKeyboardButton(payment, callback_data=f"pay-{payment}")])
            keyboard.append([InlineKeyboardButton("◀️ Orqaga", callback_data="orqaga12")])

            await query.edit_message_caption(
                caption="<b>💳 Pul yechish tizimlaridan birini tanlang:</b>",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        # To'lov tizimini tanlash
        elif data.startswith("pay-"):
            payment_type = data.replace("pay-", "")
            min_withdraw = int(self.get_setting("pul/minpul.txt"))
            balance = int(self.get_user_data(user_id, "hisob"))

            if balance >= min_withdraw:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"<b>✅ {payment_type} qabul qilindi!</b>\n\nHamyon raqamini yuboring:",
                    parse_mode='HTML',
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("◀️ Orqaga")]], resize_keyboard=True)
                )
                self.set_user_step(user_id, f"wallet-{payment_type}")
            else:
                currency = self.get_setting("pul/valyuta.txt")
                await query.answer(f"⚠️ Minimal pul yechish narxi: {min_withdraw} {currency}", show_alert=True)

        # Tasdiqlash
        elif data.startswith("tasdiq-"):
            parts = data.split('-')
            if len(parts) >= 4:
                payment_type = parts[1]
                wallet_number = parts[2]
                amount = parts[3]
                await self.process_withdrawal_request(user_id, payment_type, wallet_number, amount, query, context)

        # Bekor qilish
        elif data == "bekor":
            await query.message.delete()
            start_text = self.get_setting("matn/start.txt")
            await context.bot.send_message(
                chat_id=user_id,
                text=start_text,
                parse_mode='HTML',
                reply_markup=self.get_main_menu(user_id)
            )

        # Orqaga
        elif data == "orqaga12":
            await query.message.delete()
            start_text = self.get_setting("matn/start.txt")
            await context.bot.send_message(
                chat_id=user_id,
                text=start_text,
                parse_mode='HTML',
                reply_markup=self.get_main_menu(user_id)
            )

        # Admin panel callbacklari
        elif data == "hozirgi_holat":
            await self.show_current_settings(query, context)
        elif data == "admin_user":
            await self.set_admin_user(query, context)
        elif data == "min_pul":
            await self.set_min_withdraw(query, context)
        elif data == "taklif_narxi":
            await self.set_referal_bonus(query, context)
        elif data == "majburiy_obuna":
            await self.manage_channels(query, context)
        elif data == "tolovlar":
            await self.set_payment_channel(query, context)
        elif data == "stats":
            await self.refresh_stats(query, context)
        elif data == "list":
            await self.show_admins_list(query, context)
        elif data == "add":
            await self.add_admin(query, context)
        elif data == "remove":
            await self.remove_admin(query, context)
        elif data == "new":
            await self.add_payment_system(query, context)
        elif data.startswith("del-"):
            payment_type = data.replace("del-", "")
            await self.delete_payment_system(payment_type, query, context)
        elif data == "oddiy_xabar":
            await self.send_broadcast_message(query, context)
        elif data == "forward_xabar":
            await self.send_forward_broadcast(query, context)

        # Majburiy obuna callbacklari
        elif data == "majburiy_obuna1":
            await self.add_channel(query, context)
        elif data == "majburiy_obuna2":
            await self.delete_channels(query, context)
        elif data == "majburiy_obuna3":
            await self.show_channels_list(query, context)

        # Admin orqaga tugmalari
        elif data == "asosiy":
            await query.edit_message_text(
                text="<b>*⃣ Birlamchi sozlamalar bo'limiga xush kelibsiz!</b>\n\n<i>Nimani o'zgartiramiz?</i>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Hozirgi holat", callback_data="hozirgi_holat"),
                     InlineKeyboardButton("🔐 Admin useri", callback_data="admin_user")],
                    [InlineKeyboardButton("💳 Minimal pul yechish narxi", callback_data="min_pul"),
                     InlineKeyboardButton("🔗 Taklif narxi", callback_data="taklif_narxi")]
                ])
            )
        elif data == "admins":
            if user_id == self.admin_id:
                keyboard = [
                    [InlineKeyboardButton("📑 Ro'yxatni ko'rish", callback_data="list")],
                    [InlineKeyboardButton("➕ Qo'shish", callback_data="add"),
                     InlineKeyboardButton("🗑 O'chirish", callback_data="remove")]
                ]
            else:
                keyboard = [[InlineKeyboardButton("📑 Ro'yxatni ko'rish", callback_data="list")]]

            await query.edit_message_text(
                text="<b>Quyidagilardan birini tanlang:</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif data == "kanalsoz":
            await query.edit_message_text(
                text="<b>Quyidagilardan birini tanlang:</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Majburiy obuna", callback_data="majburiy_obuna")],
                    [InlineKeyboardButton("🔐 To'lovlar uchun", callback_data="tolovlar")]
                ])
            )
        elif data == "tolovtizim":
            payment_types = self.get_setting("number/turi.txt")
            if not payment_types.strip():
                keyboard = [[InlineKeyboardButton("➕ Yechish tizimi qo'shish", callback_data="new")]]
            else:
                payment_list = [pt.strip() for pt in payment_types.split('\n') if pt.strip()]
                keyboard = []
                for payment in payment_list:
                    keyboard.append([InlineKeyboardButton(f"{payment} - ni o'chirish", callback_data=f"del-{payment}")])
                keyboard.append([InlineKeyboardButton("➕ Yechish tizimi qo'shish", callback_data="new")])

            await query.edit_message_text(
                text="<b>Quyidagilardan birini tanlang:</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        # Admin tasdiqlash tugmalari
        elif data.startswith("on="):
            target_user = data.replace("on=", "")
            await self.approve_payment(target_user, query, context)
        elif data.startswith("off="):
            target_user = data.replace("off=", "")
            await self.reject_payment(target_user, query, context)

        # Pul yechish admin tasdiqlash
        elif data.startswith("tolandi-"):
            await self.process_payment_approval(data, query, context, approved=True)
        elif data.startswith("tolanmadi-"):
            await self.process_payment_approval(data, query, context, approved=False)

    # ==================== QOLGAN METODLAR ====================

    def load_admins(self) -> List[str]:
        try:
            os.makedirs("statistika", exist_ok=True)
            if not os.path.exists("statistika/admins.txt"):
                with open("statistika/admins.txt", "w", encoding="utf-8") as f:
                    f.write(self.admin_id)
                return [self.admin_id]

            with open("statistika/admins.txt", "r", encoding="utf-8") as f:
                admins = f.read().strip().split('\n')
                if self.admin_id not in admins:
                    admins.append(self.admin_id)
                return [admin.strip() for admin in admins if admin.strip()]
        except Exception as e:
            logger.error(f"Adminlarni yuklashda xato: {e}")
            return [self.admin_id]

    def initialize_file_system(self):
        directories = [
            "foydalanuvchi", "foydalanuvchi/referal", "foydalanuvchi/invest", "foydalanuvchi/hisob",
            "sozlamalar/hamyon", "sozlamalar/number", "sozlamalar/kanal", "sozlamalar/tugma",
            "sozlamalar/matn", "sozlamalar/pul", "statistika", "sozlamalar", "otkazma", "step", "ban"
        ]

        for directory in directories:
            os.makedirs(directory, exist_ok=True)

        default_settings = {
            "pul/referal.txt": "500", "pul/sarsoni.txt": "2", "pul/minpul.txt": "5000",
            "pul/admin.txt": "", "pul/valyuta.txt": "so'm", "pul/bonmiq.txt": "1000",
            "pul/bonnom.txt": "",
            "pul/token.txt": "https://openbudget.uz/boards/initiatives/initiative/31/9a7dcff2-8c8f-448d-861d-05e580592bca",
            "tugma/tugma1.txt": "💳 1XBET to'ldirish", "tugma/tugma2.txt": "💵 Hisobim",
            "tugma/tugma3.txt": "🗣️ Referal", "tugma/tugma4.txt": "📃 To'lovlar",
            "tugma/tugma5.txt": "📑 Yo'riqnoma",
            "matn/start.txt": "<b>🦁 RedBlackKassa botiga xush kelibsiz.\n\n✅ Quyidagi tugmalardan birini tanlang!</b>",
            "kanal/ch.txt": "", "kanal/tolovlar.txt": "", "number/turi.txt": ""
        }

        for file_path, content in default_settings.items():
            full_path = f"sozlamalar/{file_path}"
            if not os.path.exists(full_path):
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)

        if not os.path.exists("statistika/obunachi.txt"):
            with open("statistika/obunachi.txt", "w", encoding="utf-8") as f:
                f.write("")

    def get_user_data(self, user_id: str, data_type: str) -> str:
        try:
            file_path = f"foydalanuvchi/{data_type}/{user_id}.txt"
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            return "0"
        except Exception as e:
            logger.error(f"Foydalanuvchi ma'lumotlarini olishda xato: {e}")
            return "0"

    def set_user_data(self, user_id: str, data_type: str, value: str):
        try:
            file_path = f"foydalanuvchi/{data_type}/{user_id}.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(str(value))
        except Exception as e:
            logger.error(f"Foydalanuvchi ma'lumotlarini saqlashda xato: {e}")

    def get_setting(self, setting_path: str) -> str:
        try:
            file_path = f"sozlamalar/{setting_path}"
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            return ""
        except Exception as e:
            logger.error(f"Sozlamani olishda xato: {e}")
            return ""

    def set_setting(self, setting_path: str, value: str):
        try:
            file_path = f"sozlamalar/{setting_path}"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(str(value))
        except Exception as e:
            logger.error(f"Sozlamani saqlashda xato: {e}")

    def is_admin(self, user_id: str) -> bool:
        return str(user_id) in self.admins

    def add_user_to_stats(self, user_id: str):
        try:
            with open("statistika/obunachi.txt", "r+", encoding="utf-8") as f:
                content = f.read()
                if user_id not in content.split('\n'):
                    f.write(f"{user_id}\n")
        except Exception as e:
            logger.error(f"Statistika ga qo'shishda xato: {e}")

    def get_user_step(self, user_id: str) -> str:
        try:
            step_file = f"step/{user_id}.txt"
            if os.path.exists(step_file):
                with open(step_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
            return ""
        except Exception as e:
            logger.error(f"Step olishda xato: {e}")
            return ""

    def set_user_step(self, user_id: str, step: str):
        try:
            step_file = f"step/{user_id}.txt"
            with open(step_file, "w", encoding="utf-8") as f:
                f.write(step)
        except Exception as e:
            logger.error(f"Step saqlashda xato: {e}")

    def delete_user_step(self, user_id: str):
        try:
            step_file = f"step/{user_id}.txt"
            if os.path.exists(step_file):
                os.remove(step_file)
        except Exception as e:
            logger.error(f"Step o'chirishda xato: {e}")

    def is_banned(self, user_id: str) -> bool:
        try:
            ban_file = f"ban/{user_id}.txt"
            return os.path.exists(ban_file)
        except Exception as e:
            logger.error(f"Ban tekshirishda xato: {e}")
            return False

    def get_main_menu(self, user_id: str) -> ReplyKeyboardMarkup:
        if self.is_admin(user_id):
            keyboard = [
                [KeyboardButton("💳 1XBET to'ldirish")],
                [KeyboardButton("💵 Hisobim"), KeyboardButton("🗣️ Referal")],
                [KeyboardButton("📃 To'lovlar"), KeyboardButton("📑 Yo'riqnoma")],
                [KeyboardButton("🗄 Boshqaruv")]
            ]
        else:
            keyboard = [
                [KeyboardButton("💳 1XBET to'ldirish")],
                [KeyboardButton("💵 Hisobim"), KeyboardButton("🗣️ Referal")],
                [KeyboardButton("📃 To'lovlar"), KeyboardButton("📑 Yo'riqnoma")]
            ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_admin_menu(self) -> ReplyKeyboardMarkup:
        keyboard = [
            [KeyboardButton("*⃣ Birlamchi sozlamalar")],
            [KeyboardButton("📢 Kanallar"), KeyboardButton("📊 Statistika")],
            [KeyboardButton("🔎 Foydalanuvchini boshqarish")],
            [KeyboardButton("👤 Adminlar"), KeyboardButton("💵 Yechish tizimi")],
            [KeyboardButton("📨 Xabarnoma"), KeyboardButton("◀️ Orqaga")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    async def process_referal(self, ref_id: str, new_user_id: str, context: ContextTypes.DEFAULT_TYPE):
        try:
            referal_bonus = int(self.get_setting("pul/referal.txt"))
            currency = self.get_setting("pul/valyuta.txt")

            current_balance = int(self.get_user_data(ref_id, "hisob"))
            new_balance = current_balance + referal_bonus
            self.set_user_data(ref_id, "hisob", str(new_balance))

            current_refs = int(self.get_user_data(ref_id, "referal"))
            new_refs = current_refs + 1
            self.set_user_data(ref_id, "referal", str(new_refs))

            await context.bot.send_message(
                chat_id=ref_id,
                text=f"🎉 Yangi referal! Hisobingizga {referal_bonus} {currency} qo'shildi!",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Referal qayta ishlashda xato: {e}")

    async def admin_panel_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return

        await update.message.reply_text(
            "<b>🗄 Boshqaruv paneliga xush kelibsiz!</b>",
            parse_mode='HTML',
            reply_markup=self.get_admin_menu()
        )
        self.delete_user_step(user_id)

    async def back_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if self.is_banned(user_id):
            await update.message.reply_text("❌ Siz bloklangansiz!")
            return

        self.delete_user_step(user_id)
        start_text = self.get_setting("matn/start.txt")
        await update.message.reply_text(
            start_text,
            parse_mode='HTML',
            reply_markup=self.get_main_menu(user_id)
        )

    # ==================== ADMIN PANEL HANDLERLARI ====================

    async def admin_settings_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return

        keyboard = [
            [InlineKeyboardButton("📋 Hozirgi holat", callback_data="hozirgi_holat"),
             InlineKeyboardButton("🔐 Admin useri", callback_data="admin_user")],
            [InlineKeyboardButton("💳 Minimal pul yechish narxi", callback_data="min_pul"),
             InlineKeyboardButton("🔗 Taklif narxi", callback_data="taklif_narxi")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="asosiy")]
        ]
        await update.message.reply_text(
            "<b>*⃣ Birlamchi sozlamalar bo'limiga xush kelibsiz!</b>\n\n<i>Nimani o'zgartiramiz?</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def admin_channels_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return

        keyboard = [
            [InlineKeyboardButton("🔐 Majburiy obuna", callback_data="majburiy_obuna")],
            [InlineKeyboardButton("🔐 To'lovlar uchun", callback_data="tolovlar")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="kanalsoz")]
        ]
        await update.message.reply_text(
            "<b>📢 Kanallar bo'limiga xush kelibsiz!</b>\n\nQuyidagilardan birini tanlang:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def admin_stats_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return

        try:
            with open("statistika/obunachi.txt", "r", encoding="utf-8") as f:
                users = f.read().strip().split('\n')
                users_count = len([user for user in users if user.strip()])
        except:
            users_count = 0

        import psutil
        load = psutil.getloadavg()[0]
        text = f"<b>📊 Bot statistikasi:</b>\n\n💡 <b>O'rtacha yuklanish:</b> <code>{load:.2f}</code>\n👥 <b>Foydalanuvchilar:</b> {users_count} ta"
        keyboard = [[InlineKeyboardButton("🔁 Yangilash", callback_data="stats"),
                     InlineKeyboardButton("◀️ Orqaga", callback_data="asosiy")]]

        await update.message.reply_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    async def admin_manage_users_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return

        await update.message.reply_text(
            "<b>🔎 Foydalanuvchini boshqarish</b>\n\nKerakli foydalanuvchining ID raqamini yuboring:",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🗄 Boshqaruv")]], resize_keyboard=True)
        )
        self.set_user_step(user_id, "idraqam")

    async def admin_admins_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return

        if user_id == self.admin_id:
            keyboard = [
                [InlineKeyboardButton("📑 Ro'yxatni ko'rish", callback_data="list")],
                [InlineKeyboardButton("➕ Qo'shish", callback_data="add"),
                 InlineKeyboardButton("🗑 O'chirish", callback_data="remove")],
                [InlineKeyboardButton("◀️ Orqaga", callback_data="admins")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("📑 Ro'yxatni ko'rish", callback_data="list")],
                [InlineKeyboardButton("◀️ Orqaga", callback_data="admins")]
            ]

        await update.message.reply_text(
            "<b>👤 Adminlar boshqaruvi</b>\n\nQuyidagilardan birini tanlang:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def admin_withdraw_system_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return

        payment_types = self.get_setting("number/turi.txt")
        if not payment_types.strip():
            keyboard = [[InlineKeyboardButton("➕ Yechish tizimi qo'shish", callback_data="new")]]
        else:
            payment_list = [pt.strip() for pt in payment_types.split('\n') if pt.strip()]
            keyboard = []
            for payment in payment_list:
                keyboard.append([InlineKeyboardButton(f"🗑 {payment} ni o'chirish", callback_data=f"del-{payment}")])
            keyboard.append([InlineKeyboardButton("➕ Yechish tizimi qo'shish", callback_data="new")])

        keyboard.append([InlineKeyboardButton("◀️ Orqaga", callback_data="tolovtizim")])

        await update.message.reply_text(
            "<b>💵 Pul yechish tizimlari</b>\n\nQuyidagilardan birini tanlang:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def admin_notification_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return

        keyboard = [
            [InlineKeyboardButton("📨 Oddiy xabar", callback_data="oddiy_xabar")],
            [InlineKeyboardButton("📨 Forward xabar", callback_data="forward_xabar")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="asosiy")]
        ]
        await update.message.reply_text(
            "<b>📨 Xabarnoma yuborish</b>\n\nYuboriladigan xabar turini tanlang:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ==================== ADMIN CALLBACK METHODLARI ====================

    async def show_current_settings(self, query, context):
        admin_user = self.get_setting("pul/admin.txt")
        min_withdraw = self.get_setting("pul/minpul.txt")
        referal_bonus = self.get_setting("pul/referal.txt")
        currency = self.get_setting("pul/valyuta.txt")

        text = f"""<b>📋 Hozirgi sozlamalar:</b>

💰 <b>Taklif narxi:</b> {referal_bonus} {currency}
👤 <b>Admin useri:</b> {admin_user if admin_user else "Kiritilmagan"}
💳 <b>Minimal pul yechish:</b> {min_withdraw} {currency}"""

        keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="asosiy")]]
        await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    async def set_admin_user(self, query, context):
        await query.message.delete()
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="<b>🔐 Yangi admin username ni yuboring:</b>\n\nNamuna: @username",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🗄 Boshqaruv")]], resize_keyboard=True)
        )
        self.set_user_step(query.from_user.id, "admin-user")

    async def set_min_withdraw(self, query, context):
        await query.message.delete()
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="<b>💳 Yangi minimal pul yechish miqdorini yuboring:</b>",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🗄 Boshqaruv")]], resize_keyboard=True)
        )
        self.set_user_step(query.from_user.id, "yech")

    async def set_referal_bonus(self, query, context):
        await query.message.delete()
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="<b>🔗 Yangi taklif narxini yuboring:</b>",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🗄 Boshqaruv")]], resize_keyboard=True)
        )
        self.set_user_step(query.from_user.id, "taklif")

    async def manage_channels(self, query, context):
        keyboard = [
            [InlineKeyboardButton("📋 Ro'yxatni ko'rish", callback_data="majburiy_obuna3")],
            [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="majburiy_obuna1"),
             InlineKeyboardButton("🗑 O'chirish", callback_data="majburiy_obuna2")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="kanalsoz")]
        ]
        await query.edit_message_text(
            text="<b>🔐 Majburiy obuna kanallari</b>\n\nQuyidagilardan birini tanlang:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def add_channel(self, query, context):
        await query.message.delete()
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="<b>📢 Qo'shmoqchi bo'lgan kanal manzilini yuboring:</b>\n\nNamuna: @kanal yoki https://t.me/kanal",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🗄 Boshqaruv")]], resize_keyboard=True)
        )
        self.set_user_step(query.from_user.id, "majburiy1")

    async def delete_channels(self, query, context):
        try:
            self.set_setting("kanal/ch.txt", "")
            await query.edit_message_text("<b>✅ Barcha kanallar ro'yxati tozalandi!</b>", parse_mode='HTML')
        except Exception as e:
            await query.edit_message_text("<b>❌ Kanallar o'chirishda xatolik!</b>", parse_mode='HTML')

    async def show_channels_list(self, query, context):
        channels = self.get_setting("kanal/ch.txt")
        if not channels or not channels.strip():
            text = "<b>📭 Hozircha kanallar ulanmagan!</b>"
        else:
            channel_list = [ch.strip() for ch in channels.split('\n') if ch.strip()]
            soni = len(channel_list)
            channels_text = "\n".join([f"• {ch}" for ch in channel_list])
            text = f"""<b>📋 Ulangan kanallar ro'yxati:</b>
➖➖➖➖➖➖➖➖

{channels_text}

<b>📊 Ulangan kanallar soni:</b> {soni} ta"""

        keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="majburiy_obuna")]]
        await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    async def set_payment_channel(self, query, context):
        await query.message.delete()
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="<b>📢 To'lovlar kanali manzilini yuboring:</b>\n\nNamuna: @kanal yoki https://t.me/kanal",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🗄 Boshqaruv")]], resize_keyboard=True)
        )
        self.set_user_step(query.from_user.id, "tolovlar")

    async def refresh_stats(self, query, context):
        try:
            with open("statistika/obunachi.txt", "r", encoding="utf-8") as f:
                users = f.read().strip().split('\n')
                users_count = len([user for user in users if user.strip()])
        except:
            users_count = 0

        import psutil
        load = psutil.getloadavg()[0]
        text = f"<b>📊 Bot statistikasi:</b>\n\n💡 <b>O'rtacha yuklanish:</b> <code>{load:.2f}</code>\n👥 <b>Foydalanuvchilar:</b> {users_count} ta"
        keyboard = [[InlineKeyboardButton("🔁 Yangilash", callback_data="stats"),
                     InlineKeyboardButton("◀️ Orqaga", callback_data="asosiy")]]

        await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_admins_list(self, query, context):
        try:
            with open("statistika/admins.txt", "r", encoding="utf-8") as f:
                admins_list = f.read().strip()
        except:
            admins_list = "Adminlar ro'yxati topilmadi"

        await query.edit_message_text(
            text=f"<b>📑 Botdagi adminlar ro'yxati:</b>\n\n{admins_list}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="admins")]])
        )

    async def add_admin(self, query, context):
        await query.message.delete()
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="<b>➕ Yangi admin ID raqamini kiriting:</b>",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🗄 Boshqaruv")]], resize_keyboard=True)
        )
        self.set_user_step(query.from_user.id, "add-admin")

    async def remove_admin(self, query, context):
        await query.message.delete()
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="<b>🗑 O'chirish kerak bo'lgan admin ID raqamini kiriting:</b>",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🗄 Boshqaruv")]], resize_keyboard=True)
        )
        self.set_user_step(query.from_user.id, "remove-admin")

    async def add_payment_system(self, query, context):
        await query.message.delete()
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="<b>➕ Yangi to'lov tizimi nomini yuboring:</b>\n\nMasalan: Payme, Click, Uzumbank",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🗄 Boshqaruv")]], resize_keyboard=True)
        )
        self.set_user_step(query.from_user.id, "turi")

    async def delete_payment_system(self, payment_type: str, query, context):
        payment_types = self.get_setting("number/turi.txt")
        new_types = payment_types.replace(f"\n{payment_type}", "").replace(payment_type, "")
        self.set_setting("number/turi.txt", new_types.strip())
        await query.edit_message_text(
            text=f"<b>✅ {payment_type} - to'lov tizimi o'chirildi!</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="tolovtizim")]])
        )

    async def send_broadcast_message(self, query, context):
        await query.message.delete()
        try:
            with open("statistika/obunachi.txt", "r", encoding="utf-8") as f:
                users_count = len([line for line in f.read().split('\n') if line.strip()])
        except:
            users_count = 0

        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=f"<b>📨 Xabarnoma yuborish</b>\n\n{users_count} ta foydalanuvchiga yuboriladigan xabar matnini yuboring:",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🗄 Boshqaruv")]], resize_keyboard=True)
        )
        self.set_user_step(query.from_user.id, "oddiy")

    async def send_forward_broadcast(self, query, context):
        await query.message.delete()
        try:
            with open("statistika/obunachi.txt", "r", encoding="utf-8") as f:
                users_count = len([line for line in f.read().split('\n') if line.strip()])
        except:
            users_count = 0

        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=f"<b>📨 Forward xabar yuborish</b>\n\n{users_count} ta foydalanuvchiga yuboriladigan xabarni forward shaklida yuboring:",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🗄 Boshqaruv")]], resize_keyboard=True)
        )
        self.set_user_step(query.from_user.id, "forward")

    # ==================== TO'LOV TASDIQLASH METHODLARI ====================

    async def process_payment_approval(self, data: str, query, context, approved: bool):
        """Pul yechishni tasdiqlash yoki rad etish"""
        try:
            parts = data.split('-')
            user_id = parts[1]

            if approved:
                wallet = parts[2] if len(parts) > 2 else ""
                amount = parts[3] if len(parts) > 3 else ""

                await query.message.delete()
                await context.bot.send_message(
                    chat_id=self.admin_id,
                    text=f"<a href='tg://user?id={user_id}'>Foydalanuvchi</a> <b> {amount} so'm puli to'lab berildi!</b>",
                    parse_mode='HTML'
                )

                payment_channel = self.get_setting("kanal/tolovlar.txt")
                if payment_channel:
                    await context.bot.send_message(
                        chat_id=payment_channel,
                        text=f"""<b>📑 Foydalanuvchiga puli to'lab berildi!</b>

👤 <b><a href='tg://user?id={user_id}'>Foydalanuvchi</a>
🆔 ID:</b> <code>{user_id}</code>
💸 <b>Miqdori:</b> {amount} so'm

🎯 <b>Xolat: Muvaffaqiyatli</b>""",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("👤 Foydalanuvchi", url=f"tg://user?id={user_id}")]
                        ])
                    )

                await context.bot.send_message(
                    chat_id=user_id,
                    text="<b>✅ Pullaringiz to'lab berildi!</b>",
                    parse_mode='HTML'
                )
            else:
                amount = parts[2] if len(parts) > 2 else ""
                balance = int(self.get_user_data(user_id, "hisob"))
                new_balance = balance + int(amount)
                self.set_user_data(user_id, "hisob", str(new_balance))

                await query.message.delete()
                await context.bot.send_message(
                    chat_id=self.admin_id,
                    text=f"<a href='tg://user?id={user_id}'>Foydalanuvchi</a> <b>arizasi bekor qilindi!</b>",
                    parse_mode='HTML'
                )
                await context.bot.send_message(
                    chat_id=user_id,
                    text="<b>⚠️ Arizangiz bekor qilindi!</b>",
                    parse_mode='HTML'
                )

        except Exception as e:
            logger.error(f"Payment approval xatosi: {e}")

    async def process_withdrawal_request(self, user_id: str, payment_type: str, wallet_number: str,
                                         amount: str, query, context):
        try:
            balance = int(self.get_user_data(user_id, "hisob"))
            amount_int = int(amount)

            if balance >= amount_int:
                new_balance = balance - amount_int
                self.set_user_data(user_id, "hisob", str(new_balance))

                await query.message.delete()
                await context.bot.send_message(
                    chat_id=user_id,
                    text="<b>✉️ Pul yechib olish uchun adminga ariza yuborildi!</b>",
                    parse_mode='HTML',
                    reply_markup=self.get_main_menu(user_id)
                )

                currency = self.get_setting("pul/valyuta.txt")
                admin_message = f"""💵 <a href='tg://user?id={user_id}'>{user_id}</a> <b>pul yechib olmoqchi!</b>

• <b>To'lov turi:</b> {payment_type}
• <b>Pul miqdori:</b> {amount} {currency}
• <b>Hamyon raqami:</b> {wallet_number}"""

                keyboard = [
                    [InlineKeyboardButton("✅ To'landi", callback_data=f"tolandi-{user_id}-{wallet_number}-{amount}"),
                     InlineKeyboardButton("❌ To'lanmadi", callback_data=f"tolanmadi-{user_id}-{amount}")]
                ]

                await context.bot.send_message(
                    chat_id=self.admin_id,
                    text=admin_message,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            else:
                await query.answer("⚠️ Hisobingizda mablag' yetarli emas!", show_alert=True)

        except Exception as e:
            logger.error(f"Pul yechish so'rovini qayta ishlashda xato: {e}")
            await query.answer("Xatolik yuz berdi!", show_alert=True)

    async def approve_payment(self, target_user: str, query, context):
        try:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=target_user,
                text="<b>✅ So'rovingiz qabul qilindi!</b>",
                parse_mode='HTML'
            )
            await context.bot.send_message(
                chat_id=self.admin_id,
                text=f"<b>✅ Foydalanuvchi cheki qabul qilindi!</b>",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"To'lovni tasdiqlashda xato: {e}")

    async def reject_payment(self, target_user: str, query, context):
        try:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=target_user,
                text="<b>🚫 Sizning so'rovingiz soxtaligi sababli bekor qilindi!</b>",
                parse_mode='HTML'
            )
            await context.bot.send_message(
                chat_id=self.admin_id,
                text=f"<b>✅ Foydalanuvchi sorovi bekor qilindi!</b>",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"To'lovni rad etishda xato: {e}")

    # ==================== MESSAGE HANDLER ====================

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        text = update.message.text

        if self.is_banned(user_id):
            await update.message.reply_text("❌ Siz bloklangansiz!")
            return

        if text == "◀️ Orqaga":
            await self.back_handler(update, context)
            return

        user_step = self.get_user_step(user_id)

        # Foydalanuvchi boshqarish - ID raqam kiritish
        if user_step == "idraqam":
            if text == "🗄 Boshqaruv":
                self.delete_user_step(user_id)
                await self.admin_panel_handler(update, context)
            else:
                if os.path.exists(f"foydalanuvchi/hisob/{text}.txt"):
                    with open("step/odam.txt", "w") as f:
                        f.write(text)

                    asos = self.get_user_data(text, "hisob")
                    kirit = self.get_user_data(text, "hisob") + ".1"
                    sarhisob = self.get_user_data(text, "hisob") + ".sarmoya"
                    odam = self.get_user_data(text, "referal")

                    ban_status = "🔔 Banlash"
                    if self.is_banned(text):
                        ban_status = "🔕 Bandan olish"

                    user_info = f"""<b>✅ Foydalanuvchi topildi:</b> <a href='tg://user?id={text}'>{text}</a>

<b>Asosiy balans:</b> {asos} so'm
<b>Sarmoya balans:</b> {sarhisob} so'm
<b>Takliflari:</b> {odam} ta

<b>Kiritgan pullari:</b> {kirit} so'm"""

                    keyboard = [
                        [InlineKeyboardButton(ban_status, callback_data="ban")],
                        [InlineKeyboardButton("➕ Pul qo'shish", callback_data="qoshish"),
                         InlineKeyboardButton("➖ Pul ayirish", callback_data="ayirish")]
                    ]

                    await update.message.reply_text(
                        user_info,
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    self.delete_user_step(user_id)
                else:
                    await update.message.reply_text(
                        "<b>❌ Ushbu foydalanuvchi botdan foydalanmaydi!</b>\n\n<i>Qayta yuboring:</i>",
                        parse_mode='HTML'
                    )

        elif user_step == "oplata":
            if text == "◀️ Orqaga":
                self.delete_user_step(user_id)
                await self.back_handler(update, context)
                return

            # Bu yerga ID saqlaymiz
            os.makedirs("step", exist_ok=True)
            with open(f"step/betid.{user_id}", "w") as f:
                f.write(text)

            await update.message.reply_text(
                "<b>💰 Qancha pul to‘ldirmoqchisiz?</b>\n\n"
                "Minimal: <b>50 000 so‘m</b>\nMaksimal: <b>5 000 000 so‘m</b>",
                parse_mode='HTML'
            )

            self.set_user_step(user_id, "summa")
            return

        elif user_step == "summa":
            if not text.isdigit():
                await update.message.reply_text("❌ Faqat raqam kiriting!")
                return

            summa = int(text)

            if summa < 50000 or summa > 5000000:
                await update.message.reply_text("⚠️ 50 000 — 5 000 000 oralig‘ida summa kiriting!")
                return

            with open(f"step/summa.{user_id}", "w") as f:
                f.write(text)

            # Endi ID ni o‘qiymiz
            with open(f"step/betid.{user_id}", "r") as f:
                bet_id = f.read().strip()

            instructions = f"""
            <b>⚠️ Diqqat !!!</b>

            💸 To'lovni quyidagi kartaga o'tkazing:

            💳 Humo: <code>5614684809828005</code>
            👤 <i>SHOMUROTOV BEHRUZ</i>

            ➕ <b>{text} so‘m</b> 1XBET hisobingizga o'tkaziladi.

            💸 Minimal pul miqdori: <code>50.000</code> uzs  
            💸 Maksimal pul miqdori: <code>5.000.000</code> uzs

            <b>📸 To'lovni amalga oshirib, to'lov chekini yuboring.</b>

            ⚠️ To'lov qilganingizdan keyin <b>{text} so‘m</b> hisobingizga qo'shiladi.
            Yuqoridagi talablarni bajarmasangiz, biz aybdor emasmiz.
            """
            await update.message.reply_text(instructions, parse_mode='HTML')

            self.set_user_step(user_id, "rasm")
            return


        # Xabarnoma yuborish
        elif user_step == "oddiy":
            if text == "🗄 Boshqaruv":
                self.delete_user_step(user_id)
                await self.admin_panel_handler(update, context)
            else:
                await update.message.reply_text(
                    "<b>⏳ Xabar yuborish boshlandi...</b>",
                    parse_mode='HTML',
                    reply_markup=self.get_admin_menu()
                )

                try:
                    with open("statistika/obunachi.txt", "r", encoding="utf-8") as f:
                        users = [line.strip() for line in f.read().split('\n') if line.strip()]

                    sent_count = 0
                    failed_count = 0
                    for user in users:
                        try:
                            await context.bot.send_message(
                                chat_id=user,
                                text=text,
                                parse_mode='HTML'
                            )
                            sent_count += 1
                            await asyncio.sleep(0.1)  # Spamdan qochish uchun
                        except Exception as e:
                            failed_count += 1
                            continue

                    await update.message.reply_text(
                        f"<b>✅ Xabar yuborish yakunlandi!</b>\n\n📨 Yuborildi: {sent_count} ta\n❌ Xatolik: {failed_count} ta",
                        parse_mode='HTML',
                        reply_markup=self.get_admin_menu()
                    )
                except Exception as e:
                    await update.message.reply_text(
                        f"<b>❌ Xabar yuborishda xatolik: {e}</b>",
                        parse_mode='HTML'
                    )
                finally:
                    self.delete_user_step(user_id)

        # Admin sozlamalari
        elif user_step == "admin-user":
            if text == "🗄 Boshqaruv":
                self.delete_user_step(user_id)
                await self.admin_panel_handler(update, context)
            else:
                if "@" in text:
                    self.set_setting("pul/admin.txt", text)
                    await update.message.reply_text("<b>✅ Admin username muvaffaqiyatli o'zgartirildi!</b>",
                                                    parse_mode='HTML',
                                                    reply_markup=self.get_admin_menu())
                    self.delete_user_step(user_id)
                else:
                    await update.message.reply_text(
                        "⚠️ <b>Xato kiritildi! Iltimos, @ bilan boshlangan username kiriting.</b>", parse_mode='HTML')

        elif user_step == "yech":
            if text == "🗄 Boshqaruv":
                self.delete_user_step(user_id)
                await self.admin_panel_handler(update, context)
            else:
                try:
                    amount = int(text)
                    self.set_setting("pul/minpul.txt", str(amount))
                    await update.message.reply_text(
                        "<b>✅ Minimal pul yechish miqdori muvaffaqiyatli o'zgartirildi!</b>", parse_mode='HTML',
                        reply_markup=self.get_admin_menu())
                    self.delete_user_step(user_id)
                except ValueError:
                    await update.message.reply_text("⚠️ <b>Iltimos, raqam kiriting!</b>", parse_mode='HTML')

        elif user_step == "taklif":
            if text == "🗄 Boshqaruv":
                self.delete_user_step(user_id)
                await self.admin_panel_handler(update, context)
            else:
                try:
                    amount = int(text)
                    self.set_setting("pul/referal.txt", str(amount))
                    await update.message.reply_text("<b>✅ Taklif narxi muvaffaqiyatli o'zgartirildi!</b>",
                                                    parse_mode='HTML',
                                                    reply_markup=self.get_admin_menu())
                    self.delete_user_step(user_id)
                except ValueError:
                    await update.message.reply_text("⚠️ <b>Iltimos, raqam kiriting!</b>", parse_mode='HTML')

        elif user_step == "tolovlar":
            if text == "🗄 Boshqaruv":
                self.delete_user_step(user_id)
                await self.admin_panel_handler(update, context)
            else:
                # Kanal manzilini tozalash
                channel_username = text.strip()
                if channel_username.startswith('https://t.me/'):
                    channel_username = '@' + channel_username.split('/')[-1]
                elif not channel_username.startswith('@'):
                    channel_username = '@' + channel_username

                if '@' in channel_username:
                    self.set_setting("kanal/tolovlar.txt", channel_username)
                    await update.message.reply_text(f"<b>✅ {channel_username} - to'lovlar kanali qo'shildi</b>",
                                                    parse_mode='HTML',
                                                    reply_markup=self.get_admin_menu())
                    self.delete_user_step(user_id)
                else:
                    await update.message.reply_text(
                        "<b>⚠️ Kanal manzili kiritishda xatolik:</b>\n\nMasalan: @kanal yoki https://t.me/kanal",
                        parse_mode='HTML')

        elif user_step == "majburiy1":
            if text == "🗄 Boshqaruv":
                self.delete_user_step(user_id)
                await self.admin_panel_handler(update, context)
            else:
                # Kanal manzilini tozalash
                channel_username = text.strip()
                if channel_username.startswith('https://t.me/'):
                    channel_username = '@' + channel_username.split('/')[-1]
                elif not channel_username.startswith('@'):
                    channel_username = '@' + channel_username

                if '@' in channel_username:
                    current_channels = self.get_setting("kanal/ch.txt")
                    channel_list = [ch.strip() for ch in current_channels.split('\n') if ch.strip()]

                    # Agar kanal allaqachon mavjud bo'lmasa
                    if channel_username not in channel_list:
                        if current_channels:
                            new_channels = f"{current_channels}\n{channel_username}"
                        else:
                            new_channels = channel_username
                        self.set_setting("kanal/ch.txt", new_channels)
                        await update.message.reply_text(f"<b>✅ {channel_username} - kanal qo'shildi</b>",
                                                        parse_mode='HTML',
                                                        reply_markup=self.get_admin_menu())
                    else:
                        await update.message.reply_text(f"<b>⚠️ {channel_username} - kanal allaqachon mavjud!</b>",
                                                        parse_mode='HTML')
                    self.delete_user_step(user_id)
                else:
                    await update.message.reply_text(
                        "<b>⚠️ Kanal manzili kiritishda xatolik:</b>\n\nMasalan: @kanal yoki https://t.me/kanal",
                        parse_mode='HTML')

        elif user_step == "turi":
            if text == "🗄 Boshqaruv":
                self.delete_user_step(user_id)
                await self.admin_panel_handler(update, context)
            else:
                current_types = self.get_setting("number/turi.txt")
                new_types = f"{current_types}\n{text}" if current_types else text
                self.set_setting("number/turi.txt", new_types.strip())
                await update.message.reply_text("<b>✅ To'lov tizimi qo'shildi!</b>", parse_mode='HTML',
                                                reply_markup=self.get_admin_menu())
                self.delete_user_step(user_id)

        # Admin qo'shish
        elif user_step == "add-admin":
            if text == "🗄 Boshqaruv":
                self.delete_user_step(user_id)
                await self.admin_panel_handler(update, context)
            else:
                try:
                    new_admin_id = text.strip()
                    # Adminlar ro'yxatini yangilash
                    with open("statistika/admins.txt", "a", encoding="utf-8") as f:
                        f.write(f"\n{new_admin_id}")

                    # Adminlar listini qayta yuklash
                    self.admins = self.load_admins()

                    await update.message.reply_text(f"<b>✅ {new_admin_id} - yangi admin qo'shildi!</b>",
                                                    parse_mode='HTML',
                                                    reply_markup=self.get_admin_menu())
                    self.delete_user_step(user_id)
                except Exception as e:
                    await update.message.reply_text(f"<b>❌ Xatolik: {e}</b>", parse_mode='HTML')

        # Admin o'chirish
        elif user_step == "remove-admin":
            if text == "🗄 Boshqaruv":
                self.delete_user_step(user_id)
                await self.admin_panel_handler(update, context)
            else:
                try:
                    remove_admin_id = text.strip()
                    # Asosiy adminni o'chirishni oldini olish
                    if remove_admin_id == self.admin_id:
                        await update.message.reply_text("<b>❌ Asosiy adminni o'chirib bo'lmaydi!</b>",
                                                        parse_mode='HTML')
                        return

                    # Adminlar ro'yxatini yangilash
                    with open("statistika/admins.txt", "r", encoding="utf-8") as f:
                        admins = f.read().strip().split('\n')

                    new_admins = [admin for admin in admins if admin.strip() != remove_admin_id]

                    with open("statistika/admins.txt", "w", encoding="utf-8") as f:
                        f.write('\n'.join(new_admins))

                    # Adminlar listini qayta yuklash
                    self.admins = self.load_admins()

                    await update.message.reply_text(f"<b>✅ {remove_admin_id} - admin o'chirildi!</b>",
                                                    parse_mode='HTML',
                                                    reply_markup=self.get_admin_menu())
                    self.delete_user_step(user_id)
                except Exception as e:
                    await update.message.reply_text(f"<b>❌ Xatolik: {e}</b>", parse_mode='HTML')

        # Hamyon raqami kiritish
        elif user_step.startswith("wallet-"):
            payment_type = user_step.replace("wallet-", "")
            if text == "◀️ Orqaga":
                self.delete_user_step(user_id)
                await self.back_handler(update, context)
            else:
                self.set_user_step(user_id, f"miqdor-{payment_type}-{text}")
                balance = self.get_user_data(user_id, "hisob")
                currency = self.get_setting("pul/valyuta.txt")
                await update.message.reply_text(
                    f"<b>✅ Hamyon raqam qabul qilindi!</b>\n\n💰 <b>Qancha pul yechmoqchisiz?</b>\n\n💳 <b>Balansingiz:</b> {balance} {currency}",
                    parse_mode='HTML',
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("◀️ Orqaga")]], resize_keyboard=True)
                )

        # Miqdor kiritish
        elif user_step.startswith("miqdor-"):
            parts = user_step.split('-')
            if len(parts) >= 3:
                payment_type = parts[1]
                wallet_number = parts[2]

                if text == "◀️ Orqaga":
                    self.delete_user_step(user_id)
                    await self.back_handler(update, context)
                else:
                    try:
                        amount = int(text)
                        min_withdraw = int(self.get_setting("pul/minpul.txt"))
                        balance = int(self.get_user_data(user_id, "hisob"))
                        currency = self.get_setting("pul/valyuta.txt")

                        if amount >= min_withdraw:
                            if balance >= amount:
                                confirmation_text = f"""
✅ <b>Qabul qilindi!</b>

• <b>To'lov turi:</b> {payment_type}
• <b>Pul miqdori:</b> {amount} {currency}
• <b>Hamyon raqamingiz:</b> {wallet_number}

<b>Ma'lumotlar to'g'ri ekanligiga ishonch hosil qilgan bo'lsangiz, ✅ Tasdiqlash tugmasini bosing!</b>"""
                                keyboard = [
                                    [InlineKeyboardButton("✅ Tasdiqlash",
                                                          callback_data=f"tasdiq-{payment_type}-{wallet_number}-{amount}")],
                                    [InlineKeyboardButton("❌ Bekor qilish", callback_data="bekor")]
                                ]
                                await update.message.reply_text(confirmation_text, parse_mode='HTML',
                                                                reply_markup=InlineKeyboardMarkup(keyboard))
                                self.delete_user_step(user_id)
                            else:
                                await update.message.reply_text("⚠️ <b>Hisobingizda mablag' yetarli emas!</b>",
                                                                parse_mode='HTML')
                        else:
                            await update.message.reply_text(
                                f"<b>⚠️ Minimal pul yechish narxi: {min_withdraw} {currency}</b>", parse_mode='HTML')
                    except ValueError:
                        await update.message.reply_text("⚠️ <b>Iltimos, raqam kiriting!</b>", parse_mode='HTML')

    async def photo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if self.is_banned(user_id):
            await update.message.reply_text("❌ Siz bloklangansiz!")
            return

        user_step = self.get_user_step(user_id)
        if user_step == "rasm":
            photo = update.message.photo[-1]
            user_name = update.effective_user.first_name

            try:
                with open(f"step/hisob.{user_id}", "r") as f:
                    bet_id = f.read().strip()
            except:
                bet_id = "Noma'lum"

            await update.message.reply_text(
                "<b>📮 So'rovingiz ko'rib chiqish uchun yuborildi.\n\n⏰ Administratorlarimiz 15 - 60 daqiqa ichida tekshirib chiqishadi. Agar tasdiqlansa 1XBET hisobingizga pul qo'shiladi!</b>",
                parse_mode='HTML',
                reply_markup=self.get_main_menu(user_id)
            )

            admin_message = f"""📄 <b>Foydalanuvchidan check:

👮‍♂️ Foydalanuvchi:</b> <a href='tg://user?id={user_id}'>{user_name}</a>
🔎 <b>ID raqami:</b> {user_id}
💵 <b>1XBET Raqami:</b> <code>{bet_id}</code>"""

            keyboard = [
                [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"on={user_id}"),
                 InlineKeyboardButton("❌ Bekor qilish", callback_data=f"off={user_id}")]
            ]

            await context.bot.send_photo(
                chat_id=self.admin_id,
                photo=photo.file_id,
                caption=admin_message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            self.delete_user_step(user_id)


def main():
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        bot = RedBlackKassaBot()

        # Handlerlar
        application.add_handler(CommandHandler("start", bot.start_handler))

        # Asosiy menyu handlerlari
        application.add_handler(MessageHandler(filters.Text(["💳 1XBET to'ldirish"]), bot.bet_deposit_handler))
        application.add_handler(MessageHandler(filters.Text(["💵 Hisobim"]), bot.balance_handler))
        application.add_handler(MessageHandler(filters.Text(["🗣️ Referal"]), bot.referal_handler))
        application.add_handler(MessageHandler(filters.Text(["📃 To'lovlar"]), bot.payments_handler))
        application.add_handler(MessageHandler(filters.Text(["📑 Yo'riqnoma"]), bot.guide_handler))
        application.add_handler(MessageHandler(filters.Text(["🗄 Boshqaruv"]), bot.admin_panel_handler))
        application.add_handler(MessageHandler(filters.Text(["◀️ Orqaga"]), bot.back_handler))

        # Admin panel handlerlari
        application.add_handler(MessageHandler(filters.Text(["*⃣ Birlamchi sozlamalar"]), bot.admin_settings_handler))
        application.add_handler(MessageHandler(filters.Text(["📢 Kanallar"]), bot.admin_channels_handler))
        application.add_handler(MessageHandler(filters.Text(["📊 Statistika"]), bot.admin_stats_handler))
        application.add_handler(
            MessageHandler(filters.Text(["🔎 Foydalanuvchini boshqarish"]), bot.admin_manage_users_handler))
        application.add_handler(MessageHandler(filters.Text(["👤 Adminlar"]), bot.admin_admins_handler))
        application.add_handler(MessageHandler(filters.Text(["💵 Yechish tizimi"]), bot.admin_withdraw_system_handler))
        application.add_handler(MessageHandler(filters.Text(["📨 Xabarnoma"]), bot.admin_notification_handler))

        # Callback query handler - BIRTA HANDLER YETARLI
        application.add_handler(CallbackQueryHandler(bot.callback_handler))

        # Xabar handlerlari
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.message_handler))
        application.add_handler(MessageHandler(filters.PHOTO, bot.photo_handler))

        logger.info("Bot ishga tushdi...")
        print("=" * 50)
        print("🤖 RedBlackKassa Bot ishga tushdi!")
        print(f"👤 Admin ID: {ADMIN_ID}")
        print(f"🔑 Token: {BOT_TOKEN}")
        print("=" * 50)

        application.run_polling()

    except Exception as e:
        logger.error(f"Asosiy dasturda xato: {e}")
        print(f"Xatolik: {e}")


if __name__ == "__main__":
    main()