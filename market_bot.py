# -*- coding: utf-8 -*-
"""
market_bot.py — Market Bot (All-in-One Merged & Fixed Edition)
==============================================================
يجمع هذا الملف جميع ملفات المشروع الخمسة:
  config.py + db.py + buyer_handlers.py + seller_handlers.py + main.py
مع الحفاظ على كافة الميزات وإصلاح جميع الأخطاء البرمجية والمنطقية والأمنية.
"""

from __future__ import annotations

import asyncio
import csv
import html
import io
import logging
import math
import os
import re
import time
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Any, Final, Optional

import qrcode
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BufferedInputFile,
    CallbackQuery,
    ErrorEvent,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    delete,
    desc,
    event,
    func,
    nullslast,
    or_,
    select,
    text as sql_text,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    selectinload,
)

# ════════════════════════════════════════════════════════════════════
# 1. CONFIGURATION & LOCALIZATION (config.py)
# ════════════════════════════════════════════════════════════════════

BASE_DIR: Final[str] = os.path.dirname(os.path.abspath(__file__))
os.makedirs(BASE_DIR, exist_ok=True)
DB_PATH: Final[str] = os.path.join(BASE_DIR, "market_v10.db")

BOT_TOKEN: Final[str] = "9279025943:AAH0UpNhdvpzhrJykauXq1FhgAbHax3OTiY"
if not BOT_TOKEN or ":" not in BOT_TOKEN:
    raise ValueError("BOT_TOKEN غير صالح أو فارغ.")

ADMIN_IDS: Final[list[int]] = [8262706717]
SUPPORT_CONTACT: Final[str] = "@YourUsername"
DB_URL: Final[str] = f"sqlite+aiosqlite:///{DB_PATH}"

ITEMS_PER_PAGE: Final[int] = 5
MAX_STORES_PER_USER: Final[int] = 3
MAX_PRODUCT_PHOTOS: Final[int] = 3

MAX_STORE_NAME_LEN: Final[int] = 100
MAX_STORE_BIO_LEN: Final[int] = 500
MAX_STORE_SLUG_LEN: Final[int] = 50
MAX_STORE_SHARE_TEXT_LEN: Final[int] = 1000
MAX_STORE_CONTACT_LEN: Final[int] = 100
MAX_PRODUCT_TITLE_LEN: Final[int] = 200
MAX_PRODUCT_DESC_LEN: Final[int] = 2000
MAX_PRODUCT_VARS_LEN: Final[int] = 200
MAX_ORDER_NOTE_LEN: Final[int] = 500
MAX_REPORT_REASON_LEN: Final[int] = 500
MAX_TICKET_SUBJECT_LEN: Final[int] = 200
MAX_PROFILE_NAME_LEN: Final[int] = 100
MAX_PROFILE_PHONE_LEN: Final[int] = 50

DEFAULT_CURRENCY: Final[str] = "DZD"
DEFAULT_LANG: Final[str] = "ar"
LANGS: Final[list[str]] = ["ar", "en", "fr"]
LANG_NAMES: Final[dict[str, str]] = {
    "ar": "🇩🇿 العربية",
    "en": "🇬🇧 English",
    "fr": "🇫🇷 Français",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("market_bot")


def utcnow() -> datetime:
    """Naive UTC datetime for consistent SQLite DateTime comparisons."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def esc(val: Any) -> str:
    """Escape untrusted user text for Telegram HTML parse mode."""
    return html.escape(str(val or ""), quote=True)


def csv_safe(val: Any) -> str:
    """Prevent CSV Formula Injection in Excel/Sheets."""
    s = str(val or "")
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


def is_admin(tg_id: int) -> bool:
    return tg_id in ADMIN_IDS


def get_lang_name(code: str) -> str:
    return LANG_NAMES.get(code, LANG_NAMES[DEFAULT_LANG])


def all_langs() -> list[str]:
    return list(LANGS)


TEXTS: dict[str, dict[str, str]] = {
    "ar": {
        "choose_lang": "🌐 اختر لغتك:",
        "lang_set": "✅ تم تعيين اللغة إلى العربية",
        "welcome": (
            "🌟 <b>مرحباً بك في Market Bot!</b> 🌟\n\n"
            "منصتك المتكاملة للتجارة داخل تلجرام. سواء كنت بائعاً يبحث عن جمهور، أو مشترياً يبحث عن الأفضل — نحن هنا لنجعل تجربتك أسهل وأسرع!\n\n"
            "🛍️ <b>للمشتري:</b> تصفح المنتجات، أضف للسلة، وتابع طلباتك بكل سهولة.\n"
            "🚀 <b>للبائع:</b> افتح متجرك مجاناً، أضف منتجاتك، وأدر طلباتك من مكان واحد.\n\n"
            "اختر من القائمة أدناه وابدأ الآن 👇"
        ),
        "main_menu": "🏠 <b>القائمة الرئيسية</b>",
        "btn_buyer_section": "🛍️ المشتري",
        "btn_seller_section": "🏪 البائع",
        "btn_profile_section": "👤 حسابي",
        "btn_admin": "👨‍💼 الإدارة",
        "buyer_menu_title": "🛍️ <b>قسم المشتري</b>\n\nابحث عن أفضل المنتجات وتصفح المتاجر:",
        "seller_menu_title": "🏪 <b>قسم البائع</b>\n\nأدر متجرك، منتجاتك، وطلباتك باحترافية:",
        "choose_store": "\n\nلديك عدة متاجر، اختر المتجر الذي تريد إدارته:",
        "add_new_store": "➕ فتح متجر جديد",
        "max_stores_reached": "⚠️ وصلت للحد الأقصى (3 متاجر)",
        "btn_browse": "🛍️ تصفح المنتجات",
        "btn_browse_cats": "📂 تصفح بالتصنيفات",
        "btn_search": "🔎 بحث عن منتج",
        "btn_search_store": "🏪 بحث عن متجر",
        "btn_cart": "🛒 سلة المشتريات",
        "btn_my_orders": "📦 طلباتي",
        "btn_mystore": "🏪 متجري",
        "btn_become_seller": "🚀 كن بائعاً (افتح متجرك)",
        "btn_account": "👤 حسابي",
        "btn_profile": "👤 ملفي الشخصي",
        "btn_favorites": "❤️ المفضلة",
        "btn_top_stores": "🏪 دليل المتاجر",
        "btn_support": "🆘 الدعم الفني",
        "btn_lang": "🌐 اللغة",
        "account_menu": "⚙️ <b>حسابي والإعدادات</b>\n\nيمكنك الوصول لجميع خياراتك من هنا:",
        "sponsored_ad": "📢 <b>إعلان ممول</b>",
        "btn_ads_section": "📢 الإعلانات",
        "ads_menu_title": "📢 <b>قسم الإعلانات</b>\n\nاكتشف أفضل العروض، أو أعلن عن منتجك وبوتك هنا:",
        "btn_browse_featured": "⭐ المنتجات المميزة",
        "btn_browse_bot_ads": "🤖 إعلانات البوتات",
        "btn_create_bot_ad": "➕ أعلن عن بوتك هنا",
        "btn_buy_product_ad": "📢 تمييز منتج",
        "featured_products_title": "⭐ <b>المنتجات المميزة</b>\n\nهذه المنتجات دفع أصحابها مقابل ظهورها هنا:",
        "bot_ads_title": "🤖 <b>إعلانات البوتات</b>\n\nتصفح أفضل البوتات على تلجرام:",
        "no_bot_ads": "لا توجد إعلانات بوتات حالياً.",
        "bot_ad_name": "🤖 أدخل اسم البوت:",
        "bot_ad_username": "🔗 أدخل معرف البوت (بدون @) [مثال: MyAwesomeBot]:",
        "bot_ad_desc": "📝 أدخل وصفاً جذاباً للبوت (ماذا يفعل؟):",
        "bot_ad_photo": "🖼️ أرسل صورة/لوغو البوت (إلزامي):",
        "bot_ad_review": "📋 <b>مراجعة الإعلان</b>\n\nالاسم: {name}\nالمعرف: @{username}\nالوصف: {desc}\n\nسيتم إرسال طلبك للإدارة للموافقة.",
        "bot_ad_submitted": "✅ تم إرسال إعلان البوت للمراجعة. سيظهر بعد موافقة الإدارة.",
        "ad_packages_title": "💎 <b>باقات تمييز المنتجات</b>\n\nاختر الباقة التي تناسبك لتمييز منتجك وجعله يظهر في أعلى القائمة:",
        "ad_pkg_basic": "🥉 باقة أساسية (3 أيام) - 1000 دج",
        "ad_pkg_pro": "🥈 باقة احترافية (7 أيام) - 2000 دج",
        "ad_pkg_vip": "🥇 باقة VIP (30 يوم) - 7000 دج",
        "ad_payment_instructions": (
            "💳 <b>تعليمات الدفع:</b>\n\n"
            "1️⃣ قم بتحويل المبلغ إلى الحساب البريدي: <code>0000000000</code>\n"
            "2️⃣ أرسل صورة إثبات الدفع (لقطة شاشة) في هذه المحادثة.\n"
            "3️⃣ بعد التحقق، سيتم تفعيل تمييز منتجك فوراً."
        ),
        "btn_send_payment_proof": "📸 إرسال إثبات الدفع",
        "payment_proof_received": "✅ تم استلام إثبات الدفع. سيتم مراجعته وتفعيل التمييز قريباً.",
        "btn_manage_bot_ads": "🤖 إدارة إعلانات البوتات",
        "btn_manage_ad_requests": "💰 طلبات الدفع",
        "bot_ads_pending": "⏳ إعلانات البوتات المعلقة:",
        "ad_requests_pending": "⏳ طلبات الدفع المعلقة:",
        "btn_approve_bot_ad": "✅ موافقة",
        "btn_reject_bot_ad": "❌ رفض",
        "btn_confirm_payment": "💰 تأكيد الدفع",
        "admin_bot_ad_view": "🤖 <b>مراجعة إعلان بوت</b>\n\nالاسم: {name}\nالمعرف: @{username}\nالوصف: {desc}\n",
        "admin_ad_req_view": "💰 <b>طلب دفع جديد</b>\n\nالمستخدم: <code>{user_id}</code>\nالباقة: {package}\nالمبلغ: {price}\nالنوع: {type}\n\nيرجى التحقق من إثبات الدفع ثم تأكيده.",
        "btn_back": "🔙 رجوع",
        "btn_cancel": "❌ إلغاء",
        "btn_confirm": "✅ تأكيد",
        "btn_approve": "✅ موافقة",
        "btn_reject": "❌ رفض",
        "no_products": "لا توجد منتجات.",
        "all_products": "🛍️ <b>جميع المنتجات</b>\nتصفح أحدث المنتجات المعروضة:",
        "cats_browse_title": "📂 <b>التصنيفات</b>\nاختر تصنيفاً لعرض منتجاته:",
        "product": "📦 <b>{title}</b>\n\n{desc}\n\n💰 السعر: {price} {currency}\n🚚 التوصيل: {delivery}\n🏪 البائع: {store}\n⭐ التقييم: {rating}{stock}{review}{vars}{flash}",
        "out_of_stock_warn": "\n\n⚠️ <b>نفدت الكمية حالياً</b>",
        "stock_left": "\n📦 المتبقي: {qty}",
        "vars_list": "\n🎨 الخيارات: {vars}",
        "flash_sale_warn": "\n\n🔥 <b>عرض خاطف!</b> السعر القديم: {old_price}، ينتهي بعد {time}",
        "btn_contact": "💬 طرق التواصل مع البائع",
        "btn_rate": "⭐ تقييم المتجر",
        "btn_order": "🛒 اطلب الآن",
        "btn_add_cart": "🛒 أضف إلى السلة",
        "btn_remove_fav": "💔 إزالة من المفضلة",
        "btn_add_fav": "❤️ حفظ في المفضلة",
        "btn_report_prod": "🚨 إبلاغ عن المنتج",
        "btn_report_store": "🚨 إبلاغ عن المتجر",
        "btn_restock": "🔔 أخبرني عند التوفر",
        "btn_similar": "🎯 منتجات مشابهة",
        "restock_saved": "✅ سنخبرك بمجرد توفر هذا المنتج!",
        "restock_notify": "🔔 <b>خبر سار!</b>\n\nالمنتج الذي تنتظره <b>{title}</b> متوفر الآن في متجر {store}.\n💰 السعر: {price}",
        "contact_methods_menu": "💬 <b>طرق التواصل مع البائع</b>\nاختر طريقة التواصل التي تناسبك:",
        "contact_telegram": "✈️ تليجرام",
        "contact_phone": "📞 اتصال هاتفي",
        "contact_whatsapp": "🟢 واتساب",
        "contact_instagram": "📸 إنستغرام",
        "contact_not_avail": "هذه الطريقة غير متوفرة لدى البائع.",
        "fav_added": "✅ تمت الإضافة للمفضلة",
        "fav_removed": "❌ تمت الإزالة من المفضلة",
        "fav_empty": "المفضلة فارغة.",
        "my_favorites": "❤️ <b>مفضلاتك:</b>",
        "cart_added": "✅ تمت الإضافة للسلة.",
        "cart_empty": "سلتك فارغة.",
        "my_cart": "🛒 <b>سلة المشتريات:</b>",
        "cart_checkout": "✅ إتمام الطلب",
        "cart_clear": "🗑️ إفراغ السلة",
        "abandoned_cart_msg": "🛒 <b>مرحباً {name}، لقد نسيت شيئاً!</b>\n\nلقد تركت منتج <b>{product}</b> في سلتك. هل تود إكمال طلبك قبل نفاد الكمية؟",
        "rating_prompt": "اختر تقييمك للمتجر:",
        "rating_comment_prompt": "شكراً! هل تريد إضافة تعليق نصي؟",
        "rating_thanks": "✅ شكراً لك! تم تسجيل تقييمك بنجاح.",
        "rating_invalid": "لقد قمت بتقييم هذا المتجر مسبقاً.",
        "btn_skip_comment": "⏭️ تخطي التعليق",
        "latest_review": "\n💬 آخر تعليق: <i>{comment}</i>",
        "var_select_prompt": "🎨 الرجاء اختيار الخيار المطلوب:",
        "store_welcome": "🏪 <b>متجرك: {name} {badge}</b>\n\n📦 المنتجات: {products}\n👁️ المشاهدات: {views}\n👥 المتابعون: {followers}\n⭐ التقييم: {rating}",
        "verified_badge": "✅",
        "btn_seller_guide": "❓ دليل الاستخدام",
        "seller_guide_text": (
            "📖 <b>دليل استخدام البائع</b>\n\n"
            "1️⃣ <b>إضافة منتج:</b> اضغط على '➕ إضافة منتج'، واملأ البيانات.\n"
            "2️⃣ <b>مشاركة المتجر:</b> اذهب إلى '🔗 مشاركة المتجر'، وشاركه على قنواتك.\n"
            "3️⃣ <b>طلبات متجري:</b> عند وصول طلب جديد، ستجد إشعاراً.\n"
            "4️⃣ <b>العروض الخاطفة:</b> لجذب المشترين، أنشئ عرضاً خاطفاً.\n\n"
            "💡 <i>نصيحة: أضف شعاراً (لوغو) لمتجرك لزيادة ثقة الزبائن.</i>"
        ),
        "btn_add_product": "➕ إضافة منتج",
        "btn_my_products": "📦 منتجاتي",
        "btn_my_stats": "📊 إحصائياتي",
        "btn_seller_orders": "🛒 طلبات متجري",
        "btn_promos": "🎟️ أكواد الخصم",
        "btn_seller_broadcast": "📢 مراسلة المتابعين",
        "btn_share": "🔗 مشاركة المتجر",
        "btn_settings": "⚙️ إعدادات المتجر",
        "btn_flash_sale": "🔥 إنشاء عرض خاطف",
        "store_create_prompt": "🏪 أدخل اسم متجرك:",
        "store_created": "✅ تم إنشاء متجرك بنجاح! أنت الآن بائع.",
        "share_menu": "🔗 <b>مشاركة متجرك</b>\n\nاختر طريقة المشاركة:\n\n1️⃣ <b>منشور جاهز:</b> أرسل منشوراً باللوغو وزر دخول.\n2️⃣ <b>رمز QR:</b> احصل على صورة QR Code للمتجر.\n3️⃣ <b>تخصيص الرابط:</b> اجعل رابط متجرك يحمل اسمك.\n4️⃣ <b>تخصيص نص المنشور:</b> اكتب رسالة تسويقية.",
        "btn_share_post": "📝 إرسال منشور جاهز",
        "btn_share_qr": "📸 إنشاء رمز QR للمتجر",
        "btn_custom_slug": "🔗 تخصيص رابط المتجر",
        "btn_custom_text": "✏️ تخصيص نص المنشور",
        "qr_caption": "📸 رمز QR لمتجر: <b>{name}</b>\n\nامسح الكود بالكاميرا للدخول إلى المتجر مباشرة.",
        "inline_share_text": "🛍️ <b>مرحباً بك في متجر {name}!</b>\n\n{store_bio}\n\n⭐ التقييم: {rating}\n👥 المتابعون: {followers}\n\nاضغط على الزر أدناه لتصفح منتجات المتجر مباشرة:",
        "inline_share_btn": "🛍️ دخول المتجر",
        "enter_custom_slug": "🔗 أدخل اسماً مخصصاً للرابط (حروف إنجليزية وأرقام و _ فقط، ولا يكون أرقاماً فقط).\nمثال: <code>my_store_2024</code>",
        "slug_taken": "❌ هذا الاسم مستخدم بالفعل، جرب اسماً آخر.",
        "slug_success": "✅ تم تخصيص الرابط بنجاح! رابطك الجديد هو:\nhttps://t.me/{bot_username}?start=store_{slug}",
        "enter_custom_share_text": "✏️ أرسل الرسالة التي تريد أن تظهر مع رابط متجرك:",
        "share_text_success": "✅ تم حفظ نص المشاركة بنجاح.",
        "top_stores_title": "🏪 <b>دليل أفضل المتاجر</b>\n\nتصفح المتاجر الأكثر نشاطاً وشعبية:",
        "top_stores_empty": "لا توجد متاجر نشطة حالياً.",
        "store_welcome_deeplink": "👋 أهلاً بك في متجر <b>{name} {badge}</b>!\n\n{store_bio}\n\n⭐ التقييم: {rating}\n\nتصفح منتجاتنا:",
        "settings_menu": "⚙️ <b>إعدادات المتجر</b>\nاختر ما تريد تعديله:",
        "btn_edit_name": "✏️ تعديل اسم المتجر",
        "btn_edit_bio": "📝 تعديل وصف المتجر",
        "btn_edit_logo": "🖼️ تعديل شعار المتجر (اللوغو)",
        "btn_edit_contacts": "📞 تعديل طرق التواصل",
        "enter_new_name": "أدخل اسم المتجر الجديد:",
        "enter_new_bio": "أدخل وصف المتجر الجديد:",
        "send_logo": "أرسل صورة لتكون شعاراً لمتجرك:",
        "contacts_menu": "📞 <b>طرق التواصل</b>\nاختر الطريقة التي تريد تعديلها:",
        "enter_contact_tg": "أدخل معرف التلجرام (مثال: @username):",
        "enter_contact_phone": "أدخل رقم الهاتف (مثال: +213555123456):",
        "enter_contact_whatsapp": "أدخل رقم الواتساب (مثال: +213555123456):",
        "enter_contact_insta": "أدخل رابط أو معرف الإنستغرام:",
        "settings_updated": "✅ تم التحديث بنجاح!",
        "manage_product": "⚙️ <b>إدارة المنتج: {title}</b>",
        "btn_edit_price": "💰 تعديل السعر",
        "btn_edit_desc": "📝 تعديل الوصف",
        "btn_edit_stock": "📦 تعديل الكمية",
        "btn_toggle_stock": "📦 تغيير حالة الكمية",
        "btn_delete_prod": "🗑️ حذف المنتج",
        "enter_new_price": "أدخل السعر الجديد (رقم موجب أكبر من 0):",
        "enter_new_desc": "أدخل الوصف الجديد:",
        "enter_new_stock": "أدخل الكمية الجديدة (رقم صحيح 0 أو أكثر):",
        "prod_updated": "✅ تم التحديث.",
        "prod_deleted": "🗑️ تم حذف المنتج بنجاح.",
        "stock_out": "تم تحديد المنتج كـ (نفدت الكمية).",
        "stock_in": "تم تحديد المنتج كـ (متوفر).",
        "confirm_delete": "هل أنت متأكد من الحذف؟",
        "btn_yes_delete": "⚠️ نعم، احذف",
        "my_products_list": "📦 <b>منتجاتك:</b>\nاضغط على المنتج لإدارته:",
        "profile_menu": "👤 <b>ملفك الشخصي</b>\n\nالاسم: {name}\nالهاتف: {phone}\nالعنوان: {address}\n\nيمكنك تعديل بياناتك لتسريع الطلبات المستقبلية:",
        "btn_edit_profile_name": "✏️ تعديل الاسم",
        "btn_edit_profile_phone": "✏️ تعديل الهاتف",
        "btn_edit_profile_address": "✏️ تعديل العنوان",
        "enter_p_name": "أدخل اسمك الكامل:",
        "enter_p_phone": "أدخل رقم هاتفك:",
        "enter_p_address": "أدخل عنوانك بالتفصيل:",
        "profile_updated": "✅ تم حفظ بياناتك.",
        "buyer_orders_list": "📦 <b>سجل طلباتك:</b>\nاضغط على الطلب لتفاصيله:",
        "buyer_orders_empty": "ليس لديك أي طلبات سابقة.",
        "buyer_order_details": "📋 <b>طلبك #{id}</b>\n\n📦 المنتج: {product}\n🎨 الخيار: {variation}\n💰 السعر: {price}\n🚚 التوصيل: {delivery}\n📌 الحالة: {status}\n📅 التاريخ: {date}",
        "order_status_notify": "🔔 <b>تحديث على طلبك #{id}</b>\n\nمرحباً {name}، تم تغيير حالة طلبك إلى: {status}",
        "btn_use_saved": "✅ استخدام عنواني المحفوظ",
        "btn_change_status": "🔄 تغيير الحالة",
        "status_pending": "⏳ قيد الانتظار",
        "status_shipped": "🚚 تم الشحن",
        "status_completed": "✅ مكتمل",
        "status_cancelled": "❌ ملغي",
        "status_updated": "✅ تم تحديث حالة الطلب.",
        "orders_list": "🛒 <b>طلباتك:</b>\nاضغط على الطلب لتفاصيله:",
        "order_details": "📋 <b>تفاصيل الطلب #{id}</b>\n\n📦 المنتج: {product}\n🎨 الخيار: {variation}\n👤 الاسم: {name}\n📞 الهاتف: {phone}\n📍 العنوان: {address}\n📝 ملاحظة: {note}\n\n💰 السعر: {price}\n🚚 التوصيل: {delivery}\n📌 الحالة: {status}",
        "orders_empty": "لا توجد طلبات حتى الآن.",
        "btn_export_orders": "📥 تصدير الطلبات (Excel)",
        "export_success": "✅ تم تصدير طلباتك بنجاح!",
        "order_name": "🛒 الرجاء إدخال <b>اسمك الكامل</b>:",
        "order_phone": "📞 أدخل <b>رقم هاتفك</b> للتواصل:",
        "order_address": "📍 أدخل <b>عنوانك</b> بالتفصيل:",
        "order_note": "📝 هل لديك أي ملاحظات إضافية؟ (أرسل الملاحظة أو اضغط تخطي):",
        "btn_skip_note": "⏭️ تخطي الملاحظات",
        "order_promo": "🎟️ هل لديك كود خصم؟ أرسله الآن أو اضغط (تخطي):",
        "btn_skip_promo": "⏭️ تخطي (لا يوجد كود)",
        "invalid_promo": "❌ كود الخصم غير صالح أو لا ينطبق على هذه المنتجات. أرسل كوداً آخر أو اضغط تخطي:",
        "promo_applied": "✅ تم تطبيق الخصم! السعر الجديد: {price}",
        "order_success": "✅ تم إرسال طلبك للبائع بنجاح! سيتواصل معك قريباً.",
        "new_order_notify": "🔔 <b>وصلك طلب جديد!</b>\n\n📦 المنتج: {product}\n🎨 الخيار: {variation}\n👤 الاسم: {name}\n📞 الهاتف: {phone}\n📍 العنوان: {address}\n📝 ملاحظة: {note}\n💰 السعر: {price}\n🚚 التوصيل: {delivery}",
        "public_store": "🏪 <b>متجر: {name} {badge}</b>\n📝 {bio}\n⭐ التقييم: {rating}\n👥 المتابعون: {followers}\n\nاختر منتجاً:",
        "btn_follow": "🔔 متابعة المتجر",
        "btn_unfollow": "🔕 إلغاء المتابعة",
        "followed": "✅ تمت متابعة المتجر.",
        "unfollowed": "❌ تم إلغاء المتابعة.",
        "new_prod_follower_notify": "🔔 <b>منتج جديد!</b>\n\nمتجر <b>{store}</b> أضاف منتجاً:\n📦 {product}\n💰 {price}",
        "store_search_prompt": "🏪 أدخل اسم المتجر للبحث عنه:",
        "store_search_results": "🏪 <b>نتائج البحث عن المتاجر:</b>",
        "store_search_empty": "لا توجد متاجر بهذا الاسم.",
        "report_prompt": "🚨 الرجاء كتابة سبب الإبلاغ (مثال: احتيال، منتج مقلد...):",
        "report_sent": "✅ تم إرسال البلاغ للإدارة. شكراً لمساعدتنا!",
        "report_new_admin": "🚨 <b>بلاغ جديد!</b>\n\nالنوع: {type}\nالسبب: {reason}\n\nرابط: {link}",
        "promo_manage": "🎟️ <b>أكواد الخصم</b>\nاختر الإجراء:",
        "btn_add_promo": "➕ إضافة كود خصم",
        "btn_list_promos": "📋 أكوادك الحالية",
        "promo_add_prompt": "أدخل الكود ونسبة الخصم (من 1 إلى 99) مفصولين بمسافة.\nمثال: <code>SALE20 20</code>",
        "promo_added": "✅ تم إضافة كود الخصم.",
        "promo_deleted": "🗑️ تم حذف الكود.",
        "promos_list": "📋 <b>أكواد الخصم:</b>\nاضغط على الكود لحذفه:",
        "add_category": "📂 اختر تصنيف المنتج:",
        "btn_skip_category": "⏭️ بدون تصنيف",
        "add_title": "📝 أدخل اسم المنتج:",
        "add_desc": "📝 أدخل وصف المنتج:",
        "add_price": "💰 أدخل السعر (رقم موجب أكبر من 0):",
        "add_delivery_fee": "🚚 أدخل سعر التوصيل لهذا المنتج (0 إذا كان مجانياً):",
        "add_stock": "📦 أدخل الكمية المتوفرة (رقم صحيح 1 أو أكثر):",
        "add_variations": "🎨 أدخل خيارات المنتج (مثل: أحمر,أزرق,أخضر) مفصولة بفاصلة، أو اضغط تخطي:",
        "btn_skip_vars": "⏭️ تخطي (بدون خيارات)",
        "add_photo": "🖼️ أرسل الصورة <b>الأساسية</b> للمنتج:",
        "add_photo_2": "🖼️ أرسل الصورة <b>الثانية</b> (اختياري)، أو اضغط تخطي:",
        "add_photo_3": "🖼️ أرسل الصورة <b>الثالثة</b> (اختياري)، أو اضغط تخطي:",
        "btn_skip_photo": "⏭️ تخطي الصورة",
        "add_review": "📋 <b>مراجعة المنتج</b>\n\nالاسم: {title}\nالتصنيف: {category}\nالسعر: {price}\nالتوصيل: {delivery}\nالكمية: {stock}\nالخيارات: {vars}\n\nسيُرسل للمراجعة.",
        "product_submitted": "✅ تم إرسال المنتج للمراجعة.",
        "product_approved_notify": "✅ تمت الموافقة على منتجك: {title}",
        "product_rejected_notify": "❌ رُفض منتجك: {title}\nالسبب: {reason}",
        "flash_sale_menu": "🔥 <b>العروض الخاطفة</b>\n\nاختر منتجاً لإنشاء عرض خاطف عليه.",
        "flash_sale_select_prod": "اختر المنتج:",
        "flash_sale_enter_price": "أدخل سعر العرض الخاطف (أكبر من 0 وأقل من السعر الأصلي):",
        "flash_sale_enter_hours": "أدخل مدة العرض بالساعات (من 1 إلى 720 ساعة):",
        "flash_sale_created": "✅ تم تفعيل العرض الخاطف بنجاح!",
        "flash_sale_active": "🔥 عرض خاطف",
        "stats": "📊 <b>إحصائيات متجرك</b>\n\n👁️ المشاهدات: {views}\n📦 المنتجات: {products}\n🛒 إجمالي الطلبات: {orders}\n💵 إجمالي المبيعات: {revenue}\n⭐ التقييم: {rating}\n\n🏆 <b>الأكثر مبيعاً:</b>\n{top}",
        "top_prod_line": "• {name} ({count} طلبات)\n",
        "ads_info": "📢 <b>الإعلانات المميزة</b>",
        "admin_panel": "👨‍💼 <b>لوحة الإدارة</b>",
        "btn_pending": "⏳ منتجات قيد المراجعة",
        "btn_broadcast": "📢 رسالة جماعية (إذاعة)",
        "btn_manage_cats": "📂 إدارة التصنيفات",
        "btn_global_stats": "📊 إحصائيات المنصة",
        "btn_reports": "🚨 البلاغات",
        "btn_tickets": "🎫 تذاكر الدعم",
        "btn_manage_stores": "🏪 إدارة المتاجر",
        "btn_verify": "✅ توثيق المتجر",
        "btn_unverify": "❌ إلغاء التوثيق",
        "admin_stores_list": "🏪 <b>قائمة المتاجر:</b>\nاضغط على المتجر لإدارته:",
        "admin_store_view": "🏪 <b>إدارة متجر: {name}</b>\n\n👤 المالك: <code>{owner_id}</code>\n📦 المنتجات: {products}\n✅ الحالة: {status}",
        "pending_empty": "✅ لا توجد منتجات قيد المراجعة.",
        "reject_reason": "أدخل سبب الرفض:",
        "approved": "✅ تمت الموافقة.",
        "rejected": "❌ تم الرفض.",
        "search_prompt": "🔎 أدخل كلمة للبحث:",
        "search_empty": "لا توجد نتائج.",
        "my_products_empty": "لا توجد منتجات بعد.",
        "cancelled": "❌ تم الإلغاء.",
        "not_admin": "غير مصرح.",
        "search_results": "🔎 نتائج البحث:",
        "share_text": "تصفح منتجاتي عبر متجري:",
        "page_info": "صفحة {current} من {total}",
        "btn_next": "➡️ التالي",
        "btn_prev": "⬅️ السابق",
        "broadcast_prompt": "📢 أرسل الرسالة التي تريد إذاعتها:",
        "broadcast_started": "⏳ جاري الإرسال...",
        "broadcast_done": "✅ تمت الإذاعة بنجاح لـ {count} مستخدم.",
        "seller_broadcast_prompt": "📢 أرسل الرسالة التي تريد إرسالها لمتابعي متجرك:",
        "seller_broadcast_done": "✅ تم إرسال الرسالة لـ {count} متابع.",
        "cats_manage": "📂 <b>إدارة التصنيفات</b>",
        "btn_add_cat": "➕ إضافة تصنيف",
        "cat_add_prompt": "أدخل اسم التصنيف بالترتيب (عربي, إنجليزي, فرنسي) مفصولة بفاصلة:\nمثال: <code>سيارات,Cars,Voitures</code>",
        "cat_added": "✅ تم إضافة التصنيف.",
        "cat_deleted": "🗑️ تم حذف التصنيف. (المنتجات أصبحت بدون تصنيف)",
        "cat_del_confirm": "هل أنت متأكد من حذف هذا التصنيف؟",
        "global_stats": "📊 <b>إحصائيات المنصة</b>\n\n👥 إجمالي المستخدمين: {users}\n🏪 إجمالي المتاجر: {stores}\n📦 إجمالي المنتجات: {products}\n🛒 إجمالي الطلبات: {orders}",
        "reports_list": "🚨 <b>البلاغات المعلقة:</b>",
        "reports_empty": "✅ لا توجد بلاغات معلقة.",
        "report_resolved": "✅ تم حل البلاغ.",
        "support_msg": "🆘 <b>الدعم الفني</b>\n\nيمكنك إرسال استفسارك أو مشكلتك للإدارة، وسيتم الرد عليك هنا في البوت.",
        "btn_new_ticket": "📝 فتح تذكرة جديدة",
        "btn_my_tickets": "📋 تذاكري السابقة",
        "ticket_subject": "أدخل موضوع المشكلة باختصار:",
        "ticket_body": "الآن اكتب تفاصيل المشكلة (نص أو صورة):",
        "ticket_created": "✅ تم إنشاء تذكرة رقم #{id}. سيتم الرد عليك قريباً.",
        "ticket_reply_from_admin": "💬 <b>رد الإدارة على تذكرتك #{id}:</b>\n\n{text}",
        "tickets_empty": "ليس لديك تذاكر.",
        "ticket_status_open": "🟢 مفتوحة",
        "ticket_status_closed": "🔴 مغلقة",
        "btn_reply_ticket": "↩️ رد",
        "btn_close_ticket": "🔒 إغلاق التذكرة",
        "ticket_closed": "🔒 تم إغلاق التذكرة.",
        "ticket_reply_prompt": "أدخل ردك على التذكرة:",
    },
    "en": {
        "choose_lang": "🌐 Choose your language:",
        "lang_set": "✅ Language set to English",
        "welcome": (
            "🌟 <b>Welcome to Market Bot!</b> 🌟\n\n"
            "Your all-in-one commerce platform inside Telegram.\n\n"
            "🛍️ <b>For buyers:</b> browse products, add to cart, and track orders.\n"
            "🚀 <b>For sellers:</b> open your store for free and manage orders.\n\n"
            "Pick from the menu below to get started 👇"
        ),
        "main_menu": "🏠 <b>Main Menu</b>",
        "btn_buyer_section": "🛍️ Buyer",
        "btn_seller_section": "🏪 Seller",
        "btn_profile_section": "👤 My Account",
        "btn_admin": "👨‍💼 Admin",
        "buyer_menu_title": "🛍️ <b>Buyer Section</b>\n\nFind the best products and browse stores:",
        "seller_menu_title": "🏪 <b>Seller Section</b>\n\nManage your store, products and orders:",
        "choose_store": "\n\nYou have several stores, choose one to manage:",
        "add_new_store": "➕ Open a new store",
        "max_stores_reached": "⚠️ You've reached the maximum (3 stores)",
        "btn_browse": "🛍️ Browse products",
        "btn_browse_cats": "📂 Browse by category",
        "btn_search": "🔎 Search for a product",
        "btn_search_store": "🏪 Search stores",
        "btn_cart": "🛒 Shopping cart",
        "btn_my_orders": "📦 My orders",
        "btn_mystore": "🏪 My store",
        "btn_become_seller": "🚀 Become a seller (open your store)",
        "btn_account": "👤 My account",
        "btn_profile": "👤 My profile",
        "btn_favorites": "❤️ Favorites",
        "btn_top_stores": "🏪 Store directory",
        "btn_support": "🆘 Support",
        "btn_lang": "🌐 Language",
        "account_menu": "⚙️ <b>My Account & Settings</b>\n\nAccess all your options here:",
        "sponsored_ad": "📢 <b>Sponsored Ad</b>",
        "btn_ads_section": "📢 Ads",
        "ads_menu_title": "📢 <b>Ads Section</b>\n\nDiscover the best offers, or advertise your product and bot here:",
        "btn_browse_featured": "⭐ Featured products",
        "btn_browse_bot_ads": "🤖 Bot ads",
        "btn_create_bot_ad": "➕ Advertise your bot here",
        "btn_buy_product_ad": "📢 Feature a product",
        "featured_products_title": "⭐ <b>Featured Products</b>\n\nThese products are promoted by their owners:",
        "bot_ads_title": "🤖 <b>Bot Ads</b>\n\nBrowse the best Telegram bots:",
        "no_bot_ads": "No bot ads at the moment.",
        "bot_ad_name": "🤖 Enter the bot name:",
        "bot_ad_username": "🔗 Enter the bot username (without @) [e.g., MyAwesomeBot]:",
        "bot_ad_desc": "📝 Enter an attractive description (what does it do?):",
        "bot_ad_photo": "🖼️ Send the bot's logo/photo (required):",
        "bot_ad_review": "📋 <b>Ad Review</b>\n\nName: {name}\nUsername: @{username}\nDescription: {desc}\n\nYour request will be sent to the admin for approval.",
        "bot_ad_submitted": "✅ Bot ad sent for review. It will appear once approved.",
        "ad_packages_title": "💎 <b>Featured Product Packages</b>\n\nChoose the package that suits you to feature your product:",
        "ad_pkg_basic": "🥉 Basic (3 days) - 1000 DZD",
        "ad_pkg_pro": "🥈 Pro (7 days) - 2000 DZD",
        "ad_pkg_vip": "🥇 VIP (30 days) - 7000 DZD",
        "ad_payment_instructions": (
            "💳 <b>Payment instructions:</b>\n\n"
            "1️⃣ Transfer the amount to: <code>0000000000</code>\n"
            "2️⃣ Send a screenshot of the payment proof.\n"
            "3️⃣ After verification, the ad will be activated."
        ),
        "btn_send_payment_proof": "📸 Send payment proof",
        "payment_proof_received": "✅ Payment proof received. It will be reviewed shortly.",
        "btn_manage_bot_ads": "🤖 Manage bot ads",
        "btn_manage_ad_requests": "💰 Payment requests",
        "bot_ads_pending": "⏳ Pending bot ads:",
        "ad_requests_pending": "⏳ Pending payment requests:",
        "btn_approve_bot_ad": "✅ Approve",
        "btn_reject_bot_ad": "❌ Reject",
        "btn_confirm_payment": "💰 Confirm payment",
        "admin_bot_ad_view": "🤖 <b>Bot Ad Review</b>\n\nName: {name}\nUsername: @{username}\nDescription: {desc}\n",
        "admin_ad_req_view": "💰 <b>New Payment Request</b>\n\nUser: <code>{user_id}</code>\nPackage: {package}\nAmount: {price}\nType: {type}\n\nPlease verify the payment proof and confirm.",
        "btn_back": "🔙 Back",
        "btn_cancel": "❌ Cancel",
        "btn_confirm": "✅ Confirm",
        "btn_approve": "✅ Approve",
        "btn_reject": "❌ Reject",
        "no_products": "No products available.",
        "all_products": "🛍️ <b>All Products</b>\nBrowse the latest listings:",
        "cats_browse_title": "📂 <b>Categories</b>\nSelect a category to view products:",
        "product": "📦 <b>{title}</b>\n\n{desc}\n\n💰 Price: {price} {currency}\n🚚 Delivery: {delivery}\n🏪 Seller: {store}\n⭐ Rating: {rating}{stock}{review}{vars}{flash}",
        "out_of_stock_warn": "\n\n⚠️ <b>Currently out of stock</b>",
        "stock_left": "\n📦 Remaining: {qty}",
        "vars_list": "\n🎨 Options: {vars}",
        "flash_sale_warn": "\n\n🔥 <b>Flash sale!</b> Old price: {old_price}, ends in {time}",
        "btn_contact": "💬 Contact seller",
        "btn_rate": "⭐ Rate the store",
        "btn_order": "🛒 Order now",
        "btn_add_cart": "🛒 Add to cart",
        "btn_remove_fav": "💔 Remove from favorites",
        "btn_add_fav": "❤️ Add to favorites",
        "btn_report_prod": "🚨 Report product",
        "btn_report_store": "🚨 Report store",
        "btn_restock": "🔔 Notify me when available",
        "btn_similar": "🎯 Similar products",
        "restock_saved": "✅ We'll notify you as soon as it's available!",
        "restock_notify": "🔔 <b>Good news!</b>\n\nThe product you're waiting for <b>{title}</b> is now available at {store}.\n💰 Price: {price}",
        "contact_methods_menu": "💬 <b>Contact the seller</b>\nChoose a contact method:",
        "contact_telegram": "✈️ Telegram",
        "contact_phone": "📞 Phone call",
        "contact_whatsapp": "🟢 WhatsApp",
        "contact_instagram": "📸 Instagram",
        "contact_not_avail": "This contact method is not available.",
        "fav_added": "✅ Added to favorites",
        "fav_removed": "❌ Removed from favorites",
        "fav_empty": "Favorites is empty.",
        "my_favorites": "❤️ <b>Your Favorites:</b>",
        "cart_added": "✅ Added to cart.",
        "cart_empty": "Your cart is empty.",
        "my_cart": "🛒 <b>Shopping Cart:</b>",
        "cart_checkout": "✅ Checkout",
        "cart_clear": "🗑️ Clear cart",
        "abandoned_cart_msg": "🛒 <b>Hello {name}, you forgot something!</b>\n\nYou left <b>{product}</b> in your cart. Complete your order before it's gone!",
        "rating_prompt": "Choose your rating for the store:",
        "rating_comment_prompt": "Thanks! Would you like to add a comment?",
        "rating_thanks": "✅ Thank you! Your rating has been recorded.",
        "rating_invalid": "You have already rated this store.",
        "btn_skip_comment": "⏭️ Skip comment",
        "latest_review": "\n💬 Latest comment: <i>{comment}</i>",
        "var_select_prompt": "🎨 Please choose the required option:",
        "store_welcome": "🏪 <b>Your store: {name} {badge}</b>\n\n📦 Products: {products}\n👁️ Views: {views}\n👥 Followers: {followers}\n⭐ Rating: {rating}",
        "verified_badge": "✅",
        "btn_seller_guide": "❓ User guide",
        "seller_guide_text": "📖 <b>Seller Guide</b>\n\n1️⃣ Add product\n2️⃣ Share store\n3️⃣ Manage orders\n4️⃣ Create flash sales",
        "btn_add_product": "➕ Add product",
        "btn_my_products": "📦 My products",
        "btn_my_stats": "📊 My stats",
        "btn_seller_orders": "🛒 Store orders",
        "btn_promos": "🎟️ Promo codes",
        "btn_seller_broadcast": "📢 Message followers",
        "btn_share": "🔗 Share store",
        "btn_settings": "⚙️ Store settings",
        "btn_flash_sale": "🔥 Create flash sale",
        "store_create_prompt": "🏪 Enter your store name:",
        "store_created": "✅ Your store has been created! You're now a seller.",
        "share_menu": "🔗 <b>Share your store</b>\n\nChoose a sharing method:",
        "btn_share_post": "📝 Send ready post",
        "btn_share_qr": "📸 Generate store QR",
        "btn_custom_slug": "🔗 Customize store link",
        "btn_custom_text": "✏️ Customize post text",
        "qr_caption": "📸 QR code for: <b>{name}</b>\n\nScan with your camera to enter the store.",
        "inline_share_text": "🛍️ <b>Welcome to {name}!</b>\n\n{store_bio}\n\n⭐ Rating: {rating}\n👥 Followers: {followers}\n\nTap below to browse:",
        "inline_share_btn": "🛍️ Enter store",
        "enter_custom_slug": "🔗 Enter a custom link name (letters, digits, underscore; not digits only).\nExample: <code>my_store_2024</code>",
        "slug_taken": "❌ This name is already taken, try another.",
        "slug_success": "✅ Link customized! Your new link is:\nhttps://t.me/{bot_username}?start=store_{slug}",
        "enter_custom_share_text": "✏️ Send the message you want shown with your store link:",
        "share_text_success": "✅ Share text saved successfully.",
        "top_stores_title": "🏪 <b>Top Stores Directory</b>\n\nBrowse the most active stores:",
        "top_stores_empty": "No active stores at the moment.",
        "store_welcome_deeplink": "👋 Welcome to <b>{name} {badge}</b>!\n\n{store_bio}\n\n⭐ Rating: {rating}\n\nBrowse our products:",
        "settings_menu": "⚙️ <b>Store Settings</b>\nChoose what to edit:",
        "btn_edit_name": "✏️ Edit store name",
        "btn_edit_bio": "📝 Edit store description",
        "btn_edit_logo": "🖼️ Edit store logo",
        "btn_edit_contacts": "📞 Edit contact methods",
        "enter_new_name": "Enter the new store name:",
        "enter_new_bio": "Enter the new store description:",
        "send_logo": "Send a photo to use as your store logo:",
        "contacts_menu": "📞 <b>Contact Methods</b>\nChoose a method to edit:",
        "enter_contact_tg": "Enter Telegram username (e.g., @username):",
        "enter_contact_phone": "Enter phone number (e.g., +213555123456):",
        "enter_contact_whatsapp": "Enter WhatsApp number (e.g., +213555123456):",
        "enter_contact_insta": "Enter Instagram link or username:",
        "settings_updated": "✅ Updated successfully!",
        "manage_product": "⚙️ <b>Manage Product: {title}</b>",
        "btn_edit_price": "💰 Edit price",
        "btn_edit_desc": "📝 Edit description",
        "btn_edit_stock": "📦 Edit quantity",
        "btn_toggle_stock": "📦 Toggle stock status",
        "btn_delete_prod": "🗑️ Delete product",
        "enter_new_price": "Enter the new price (positive number > 0):",
        "enter_new_desc": "Enter the new description:",
        "enter_new_stock": "Enter the new quantity (integer >= 0):",
        "prod_updated": "✅ Updated.",
        "prod_deleted": "🗑️ Product deleted successfully.",
        "stock_out": "Product marked as out of stock.",
        "stock_in": "Product marked as available.",
        "confirm_delete": "Are you sure you want to delete?",
        "btn_yes_delete": "⚠️ Yes, delete",
        "my_products_list": "📦 <b>Your products:</b>\nTap a product to manage it:",
        "profile_menu": "👤 <b>Your Profile</b>\n\nName: {name}\nPhone: {phone}\nAddress: {address}\n\nEdit your data to speed up future orders:",
        "btn_edit_profile_name": "✏️ Edit name",
        "btn_edit_profile_phone": "✏️ Edit phone",
        "btn_edit_profile_address": "✏️ Edit address",
        "enter_p_name": "Enter your full name:",
        "enter_p_phone": "Enter your phone number:",
        "enter_p_address": "Enter your address in detail:",
        "profile_updated": "✅ Your data has been saved.",
        "buyer_orders_list": "📦 <b>Your Order History:</b>\nTap an order for details:",
        "buyer_orders_empty": "You have no previous orders.",
        "buyer_order_details": "📋 <b>Your order #{id}</b>\n\n📦 Product: {product}\n🎨 Option: {variation}\n💰 Price: {price}\n🚚 Delivery: {delivery}\n📌 Status: {status}\n📅 Date: {date}",
        "order_status_notify": "🔔 <b>Update on your order #{id}</b>\n\nHello {name}, your order status changed to: {status}",
        "btn_use_saved": "✅ Use my saved address",
        "btn_change_status": "🔄 Change status",
        "status_pending": "⏳ Pending",
        "status_shipped": "🚚 Shipped",
        "status_completed": "✅ Completed",
        "status_cancelled": "❌ Cancelled",
        "status_updated": "✅ Order status updated.",
        "orders_list": "🛒 <b>Your Orders:</b>\nTap an order for details:",
        "order_details": "📋 <b>Order Details #{id}</b>\n\n📦 Product: {product}\n🎨 Option: {variation}\n👤 Name: {name}\n📞 Phone: {phone}\n📍 Address: {address}\n📝 Note: {note}\n\n💰 Price: {price}\n🚚 Delivery: {delivery}\n📌 Status: {status}",
        "orders_empty": "No orders yet.",
        "btn_export_orders": "📥 Export orders (CSV)",
        "export_success": "✅ Orders exported successfully!",
        "order_name": "🛒 Please enter your <b>full name</b>:",
        "order_phone": "📞 Enter your <b>phone number</b>:",
        "order_address": "📍 Enter your <b>address</b> in detail:",
        "order_note": "📝 Any additional notes? (Send note or tap skip):",
        "btn_skip_note": "⏭️ Skip notes",
        "order_promo": "🎟️ Do you have a promo code? Send it now or tap skip:",
        "btn_skip_promo": "⏭️ Skip (no code)",
        "invalid_promo": "❌ Invalid or inapplicable promo code. Try another or tap skip:",
        "promo_applied": "✅ Discount applied! New price: {price}",
        "order_success": "✅ Your order has been sent to the seller! They'll contact you soon.",
        "new_order_notify": "🔔 <b>New order received!</b>\n\n📦 Product: {product}\n🎨 Option: {variation}\n👤 Name: {name}\n📞 Phone: {phone}\n📍 Address: {address}\n📝 Note: {note}\n💰 Price: {price}\n🚚 Delivery: {delivery}",
        "public_store": "🏪 <b>Store: {name} {badge}</b>\n📝 {bio}\n⭐ Rating: {rating}\n👥 Followers: {followers}\n\nChoose a product:",
        "btn_follow": "🔔 Follow store",
        "btn_unfollow": "🔕 Unfollow",
        "followed": "✅ Store followed.",
        "unfollowed": "❌ Unfollowed.",
        "new_prod_follower_notify": "🔔 <b>New product!</b>\n\nStore <b>{store}</b> added a product:\n📦 {product}\n💰 {price}",
        "store_search_prompt": "🏪 Enter a store name to search:",
        "store_search_results": "🏪 <b>Store search results:</b>",
        "store_search_empty": "No stores with that name.",
        "report_prompt": "🚨 Please write the reason for the report (e.g., scam, fake product...):",
        "report_sent": "✅ Report sent to admin. Thank you!",
        "report_new_admin": "🚨 <b>New Report!</b>\n\nType: {type}\nReason: {reason}\n\nLink: {link}",
        "promo_manage": "🎟️ <b>Promo Codes</b>\nChoose an action:",
        "btn_add_promo": "➕ Add promo code",
        "btn_list_promos": "📋 Your current codes",
        "promo_add_prompt": "Enter the code and discount percentage (1-99) separated by space.\nExample: <code>SALE20 20</code>",
        "promo_added": "✅ Promo code added.",
        "promo_deleted": "🗑️ Code deleted.",
        "promos_list": "📋 <b>Promo codes:</b>\nTap a code to delete it:",
        "add_category": "📂 Choose a category for your product:",
        "btn_skip_category": "⏭️ No category",
        "add_title": "📝 Enter the product name:",
        "add_desc": "📝 Enter the product description:",
        "add_price": "💰 Enter the price (positive number > 0):",
        "add_delivery_fee": "🚚 Enter the delivery fee (0 if free):",
        "add_stock": "📦 Enter the available quantity (integer >= 1):",
        "add_variations": "🎨 Enter product options (e.g., red,blue,green) separated by comma, or tap skip:",
        "btn_skip_vars": "⏭️ Skip (no options)",
        "add_photo": "🖼️ Send the <b>main</b> product image:",
        "add_photo_2": "🖼️ Send the <b>second</b> image (optional), or tap skip:",
        "add_photo_3": "🖼️ Send the <b>third</b> image (optional), or tap skip:",
        "btn_skip_photo": "⏭️ Skip image",
        "add_review": "📋 <b>Product Review</b>\n\nName: {title}\nCategory: {category}\nPrice: {price}\nDelivery: {delivery}\nQuantity: {stock}\nOptions: {vars}\n\nWill be sent for review.",
        "product_submitted": "✅ Product submitted for review.",
        "product_approved_notify": "✅ Your product has been approved: {title}",
        "product_rejected_notify": "❌ Your product was rejected: {title}\nReason: {reason}",
        "flash_sale_menu": "🔥 <b>Flash Sales</b>\n\nChoose a product to create a flash sale:",
        "flash_sale_select_prod": "Choose the product:",
        "flash_sale_enter_price": "Enter the flash sale price (> 0 and lower than original):",
        "flash_sale_enter_hours": "Enter the sale duration in hours (1 to 720):",
        "flash_sale_created": "✅ Flash sale activated successfully!",
        "flash_sale_active": "🔥 Flash sale",
        "stats": "📊 <b>Store Stats</b>\n\n👁️ Views: {views}\n📦 Products: {products}\n🛒 Total Orders: {orders}\n💵 Total Sales: {revenue}\n⭐ Rating: {rating}\n\n🏆 <b>Best Sellers:</b>\n{top}",
        "top_prod_line": "• {name} ({count} orders)\n",
        "ads_info": "📢 <b>Featured Ads</b>",
        "admin_panel": "👨‍💼 <b>Admin Panel</b>",
        "btn_pending": "⏳ Pending products",
        "btn_broadcast": "📢 Broadcast",
        "btn_manage_cats": "📂 Manage categories",
        "btn_global_stats": "📊 Platform stats",
        "btn_reports": "🚨 Reports",
        "btn_tickets": "🎫 Support tickets",
        "btn_manage_stores": "🏪 Manage stores",
        "btn_verify": "✅ Verify store",
        "btn_unverify": "❌ Unverify",
        "admin_stores_list": "🏪 <b>Stores List:</b>\nTap a store to manage it:",
        "admin_store_view": "🏪 <b>Manage store: {name}</b>\n\n👤 Owner: <code>{owner_id}</code>\n📦 Products: {products}\n✅ Status: {status}",
        "pending_empty": "✅ No pending products.",
        "reject_reason": "Enter the rejection reason:",
        "approved": "✅ Approved.",
        "rejected": "❌ Rejected.",
        "search_prompt": "🔎 Enter a search term:",
        "search_empty": "No results.",
        "my_products_empty": "No products yet.",
        "cancelled": "❌ Cancelled.",
        "not_admin": "Unauthorized.",
        "search_results": "🔎 Search results:",
        "share_text": "Browse my products via my store:",
        "page_info": "Page {current} of {total}",
        "btn_next": "➡️ Next",
        "btn_prev": "⬅️ Previous",
        "broadcast_prompt": "📢 Send the message you want to broadcast:",
        "broadcast_started": "⏳ Sending...",
        "broadcast_done": "✅ Broadcast completed for {count} users.",
        "seller_broadcast_prompt": "📢 Send the message you want to send to your store followers:",
        "seller_broadcast_done": "✅ Message sent to {count} followers.",
        "cats_manage": "📂 <b>Manage Categories</b>",
        "btn_add_cat": "➕ Add category",
        "cat_add_prompt": "Enter the category names (Arabic, English, French) separated by comma:\nExample: <code>سيارات,Cars,Voitures</code>",
        "cat_added": "✅ Category added.",
        "cat_deleted": "🗑️ Category deleted. (Products are now uncategorized)",
        "cat_del_confirm": "Are you sure you want to delete this category?",
        "global_stats": "📊 <b>Platform Stats</b>\n\n👥 Total Users: {users}\n🏪 Total Stores: {stores}\n📦 Total Products: {products}\n🛒 Total Orders: {orders}",
        "reports_list": "🚨 <b>Pending Reports:</b>",
        "reports_empty": "✅ No pending reports.",
        "report_resolved": "✅ Report resolved.",
        "support_msg": "🆘 <b>Support</b>\n\nYou can send your inquiry or issue to the admin, and you'll be replied to here in the bot.",
        "btn_new_ticket": "📝 Open a new ticket",
        "btn_my_tickets": "📋 My tickets",
        "ticket_subject": "Enter a brief subject for the issue:",
        "ticket_body": "Now write the details of the issue (text or photo):",
        "ticket_created": "✅ Ticket #{id} created. You'll be replied to soon.",
        "ticket_reply_from_admin": "💬 <b>Admin reply to your ticket #{id}:</b>\n\n{text}",
        "tickets_empty": "You have no tickets.",
        "ticket_status_open": "🟢 Open",
        "ticket_status_closed": "🔴 Closed",
        "btn_reply_ticket": "↩️ Reply",
        "btn_close_ticket": "🔒 Close ticket",
        "ticket_closed": "🔒 Ticket closed.",
        "ticket_reply_prompt": "Enter your reply to the ticket:",
    },
    "fr": {
        "choose_lang": "🌐 Choisissez votre langue :",
        "lang_set": "✅ Langue définie sur le français",
        "main_menu": "🏠 <b>Menu Principal</b>",
        "btn_buyer_section": "🛍️ Acheteur",
        "btn_seller_section": "🏪 Vendeur",
        "btn_profile_section": "👤 Mon Compte",
        "btn_admin": "👨‍💼 Admin",
        "btn_ads_section": "📢 Publicités",
        "btn_browse": "🛍️ Parcourir les produits",
        "btn_browse_cats": "📂 Par catégorie",
        "btn_search": "🔎 Rechercher un produit",
        "btn_search_store": "🏪 Rechercher un magasin",
        "btn_cart": "🛒 Panier",
        "btn_my_orders": "📦 Mes commandes",
        "btn_favorites": "❤️ Favoris",
        "btn_top_stores": "🏪 Annuaire des magasins",
        "btn_support": "🆘 Support",
        "btn_lang": "🌐 Langue",
        "btn_become_seller": "🚀 Devenir vendeur",
        "btn_add_product": "➕ Ajouter un produit",
        "btn_my_products": "📦 Mes produits",
        "btn_my_stats": "📊 Mes statistiques",
        "btn_settings": "⚙️ Paramètres du magasin",
        "btn_back": "🔙 Retour",
        "btn_cancel": "❌ Annuler",
        "btn_confirm": "✅ Confirmer",
        "btn_approve": "✅ Approuver",
        "btn_reject": "❌ Rejeter",
        "btn_next": "➡️ Suivant",
        "btn_prev": "⬅️ Précédent",
        "page_info": "Page {current} sur {total}",
        "no_products": "Aucun produit.",
        "all_products": "🛍️ <b>Tous les produits</b>\nDécouvrez les dernières offres :",
        "btn_order": "🛒 Commander",
        "btn_add_cart": "🛒 Ajouter au panier",
        "status_pending": "⏳ En attente",
        "status_shipped": "🚚 Expédiée",
        "status_completed": "✅ Terminée",
        "status_cancelled": "❌ Annulée",
        "cart_empty": "Votre panier est vide.",
        "cart_checkout": "✅ Passer la commande",
        "search_prompt": "🔎 Entrez un terme de recherche :",
        "search_empty": "Aucun résultat.",
        "cancelled": "❌ Annulé.",
        "admin_panel": "👨‍💼 <b>Panneau d'Administration</b>",
        "cat_deleted": "🗑️ Catégorie supprimée. (Les produits ne sont plus catégorisés)",
    },
}


def _setup_fallbacks() -> None:
    for lang in LANGS:
        if lang == DEFAULT_LANG:
            continue
        for k, v in TEXTS[DEFAULT_LANG].items():
            TEXTS[lang].setdefault(k, v)
    for k, v_en in TEXTS["en"].items():
        v_ar = TEXTS[DEFAULT_LANG].get(k)
        if k not in TEXTS["fr"] or TEXTS["fr"][k] == v_ar:
            TEXTS["fr"][k] = v_en


_setup_fallbacks()


def t(lang: str, key: str, **kw: Any) -> str:
    section = TEXTS.get(lang or DEFAULT_LANG)
    txt: str | None = section.get(key) if section is not None else None
    if txt is None:
        txt = TEXTS[DEFAULT_LANG].get(key)
    if txt is None:
        return key
    if not kw:
        return txt
    try:
        return txt.format(**kw)
    except (KeyError, IndexError, ValueError):
        return txt


# ════════════════════════════════════════════════════════════════════
# 2. DATABASE ORM LAYER (db.py)
# ════════════════════════════════════════════════════════════════════

Session: Optional[async_sessionmaker] = None
_engine: Optional[AsyncEngine] = None


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    lang: Mapped[str] = mapped_column(String(2), default="ar")
    role: Mapped[str] = mapped_column(String(10), default="buyer")
    saved_name: Mapped[str] = mapped_column(String(100), default="")
    saved_phone: Mapped[str] = mapped_column(String(50), default="")
    saved_address: Mapped[str] = mapped_column(Text, default="")
    ad_credits: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(100))
    contact: Mapped[str] = mapped_column(String(100), default="")
    contact_phone: Mapped[str] = mapped_column(String(50), default="")
    contact_whatsapp: Mapped[str] = mapped_column(String(50), default="")
    contact_instagram: Mapped[str] = mapped_column(String(100), default="")
    custom_slug: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, nullable=True
    )
    share_text: Mapped[str] = mapped_column(Text, default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    logo_file_id: Mapped[str] = mapped_column(String(200), default="")
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    products = relationship("Product", back_populates="store", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="store", cascade="all, delete-orphan")
    followers = relationship("StoreFollower", back_populates="store", cascade="all, delete-orphan")
    promos = relationship("PromoCode", back_populates="store", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(50))
    name_en: Mapped[str] = mapped_column(String(50))
    name_fr: Mapped[str] = mapped_column(String(50))


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default=DEFAULT_CURRENCY)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0)
    photo_file_id: Mapped[str] = mapped_column(String(200))
    photo_file_id_2: Mapped[str] = mapped_column(String(200), default="")
    photo_file_id_3: Mapped[str] = mapped_column(String(200), default="")

    flash_sale_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    flash_sale_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reject_reason: Mapped[str] = mapped_column(String(200), default="")
    featured_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    views: Mapped[int] = mapped_column(Integer, default=0)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=10)
    variations: Mapped[str] = mapped_column(String(200), default="")
    is_out_of_stock: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    store = relationship("Store", back_populates="products")
    category = relationship("Category")
    orders = relationship("Order", back_populates="product")
    favorites = relationship("Favorite", back_populates="product", cascade="all, delete-orphan")
    cart_items = relationship("CartItem", back_populates="product", cascade="all, delete-orphan")
    restock_alerts = relationship("RestockAlert", back_populates="product", cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("store_id", "buyer_tg_id", name="uq_review_store_buyer"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    buyer_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    store = relationship("Store", back_populates="reviews")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    store_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    product_title: Mapped[str] = mapped_column(String(200), default="")
    product_currency: Mapped[str] = mapped_column(String(10), default=DEFAULT_CURRENCY)
    seller_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    buyer_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    buyer_name: Mapped[str] = mapped_column(String(100))
    buyer_phone: Mapped[str] = mapped_column(String(50))
    buyer_address: Mapped[str] = mapped_column(Text)
    buyer_note: Mapped[str] = mapped_column(Text, default="")
    variation: Mapped[str] = mapped_column(String(100), default="")
    price: Mapped[float] = mapped_column(Float)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    product = relationship("Product", back_populates="orders")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_tg_id", "product_id", name="uq_fav_user_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    product = relationship("Product", back_populates="favorites")


class StoreFollower(Base):
    __tablename__ = "store_followers"
    __table_args__ = (
        UniqueConstraint("store_id", "user_tg_id", name="uq_follower_store_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    store = relationship("Store", back_populates="followers")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint(
            "user_tg_id", "product_id", "variation",
            name="uq_cart_user_product_var",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    variation: Mapped[str] = mapped_column(String(100), default="")
    reminded: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    product = relationship("Product", back_populates="cart_items")


class PromoCode(Base):
    __tablename__ = "promo_codes"
    __table_args__ = (
        UniqueConstraint("store_id", "code", name="uq_promo_store_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(50), index=True)
    discount_percent: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    store = relationship("Store", back_populates="promos")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RestockAlert(Base):
    __tablename__ = "restock_alerts"
    __table_args__ = (
        UniqueConstraint("user_tg_id", "product_id", name="uq_restock_user_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    product = relationship("Product", back_populates="restock_alerts")


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    subject: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    messages = relationship(
        "TicketMessage", back_populates="ticket", cascade="all, delete-orphan"
    )


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True
    )
    sender_tg_id: Mapped[int] = mapped_column(BigInteger)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    ticket = relationship("SupportTicket", back_populates="messages")


class BotAd(Base):
    __tablename__ = "bot_ads"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    bot_name: Mapped[str] = mapped_column(String(100))
    bot_username: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    photo_file_id: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AdRequest(Base):
    __tablename__ = "ad_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    ad_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[int] = mapped_column(Integer)
    package_name: Mapped[str] = mapped_column(String(50))
    price: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


async def _ensure_schema_columns(conn) -> None:
    """Safely add new columns if upgrading an existing market_v10.db file."""
    migrations = [
        ("products", "is_deleted", "BOOLEAN DEFAULT 0"),
        ("orders", "store_id", "INTEGER"),
        ("orders", "product_title", "VARCHAR(200) DEFAULT ''"),
        ("orders", "product_currency", f"VARCHAR(10) DEFAULT '{DEFAULT_CURRENCY}'"),
    ]
    for table, col, ddl in migrations:
        res = await conn.execute(sql_text(f"PRAGMA table_info({table})"))
        cols = {row[1] for row in res.fetchall()}
        if col not in cols:
            await conn.execute(sql_text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


async def init_db() -> async_sessionmaker:
    global Session, _engine

    if _engine is not None:
        with suppress(Exception):
            await _engine.dispose()

    _engine = create_async_engine(DB_URL, echo=False)

    @event.listens_for(_engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_schema_columns(conn)

    Session = async_sessionmaker(_engine, expire_on_commit=False)
    return Session


async def seed_categories(session_factory: async_sessionmaker) -> None:
    async with session_factory() as s:
        existing = (await s.execute(select(Category).limit(1))).scalar_one_or_none()
        if existing:
            return
        s.add_all([
            Category(name_ar="إلكترونيات", name_en="Electronics", name_fr="Électronique"),
            Category(name_ar="أزياء", name_en="Fashion", name_fr="Mode"),
            Category(name_ar="منزل", name_en="Home", name_fr="Maison"),
            Category(name_ar="رياضة", name_en="Sports", name_fr="Sport"),
            Category(name_ar="كتب", name_en="Books", name_fr="Livres"),
        ])
        await s.commit()


# ════════════════════════════════════════════════════════════════════
# 3. ROUTERS, FSM STATES & SHARED HELPERS
# ════════════════════════════════════════════════════════════════════

buyer_router = Router()
seller_router = Router()

BOT_USERNAME: str = ""

_LANG_CACHE: dict[int, tuple[str, float]] = {}
_LANG_CACHE_TTL = 300
_ADMIN_STORE_SEARCH: dict[int, str] = {}
_BROADCAST_COOLDOWN: dict[int, float] = {}
_BROADCAST_COOLDOWN_SEC = 300
_SLUG_RE = re.compile(r"^[a-z0-9_]{3,50}$")


def invalidate_lang_cache(tg_id: int) -> None:
    _LANG_CACHE.pop(tg_id, None)


def _broadcast_cooldown_remaining(uid: int) -> int:
    last = _BROADCAST_COOLDOWN.get(uid, 0.0)
    return max(0, int(_BROADCAST_COOLDOWN_SEC - (time.time() - last)))


def _cat_name(cat: Optional[Category], lang: str) -> str:
    if not cat:
        return "-"
    if lang == "en":
        return cat.name_en or cat.name_ar
    if lang == "fr":
        return cat.name_fr or cat.name_en or cat.name_ar
    return cat.name_ar


def _product_vars(p: Product) -> list[str]:
    if not p.variations:
        return []
    return [v.strip() for v in p.variations.split(",") if v.strip()]


def _parse_positive_float(raw: str, allow_zero: bool = False) -> Optional[float]:
    try:
        val = float((raw or "").replace(",", ".").strip())
    except ValueError:
        return None
    if not math.isfinite(val):
        return None
    if allow_zero:
        return val if val >= 0 else None
    return val if val > 0 else None


def _parse_int_range(raw: str, min_val: int, max_val: int = 10_000_000) -> Optional[int]:
    try:
        val = int((raw or "").strip())
    except ValueError:
        return None
    return val if min_val <= val <= max_val else None


class AddProduct(StatesGroup):
    category = State()
    title = State()
    desc = State()
    price = State()
    delivery_fee = State()
    stock = State()
    variations = State()
    photo_1 = State()
    photo_2 = State()
    photo_3 = State()
    confirm = State()


class CreateStore(StatesGroup):
    name = State()


class Search(StatesGroup):
    query = State()


class SearchStore(StatesGroup):
    query = State()


class RejectFSM(StatesGroup):
    reason = State()


class EditStoreFSM(StatesGroup):
    name = State()
    bio = State()
    logo = State()
    contact_tg = State()
    contact_phone = State()
    contact_whatsapp = State()
    contact_insta = State()
    custom_slug = State()
    custom_share_text = State()


class EditProductFSM(StatesGroup):
    price = State()
    desc = State()
    stock = State()


class OrderFSM(StatesGroup):
    name = State()
    phone = State()
    address = State()
    note = State()
    promo = State()


class BroadcastFSM(StatesGroup):
    message = State()


class SellerBroadcastFSM(StatesGroup):
    message = State()


class AddCategoryFSM(StatesGroup):
    names = State()


class ReviewFSM(StatesGroup):
    comment = State()


class ReportFSM(StatesGroup):
    reason = State()


class AddPromoFSM(StatesGroup):
    code_data = State()


class ProfileFSM(StatesGroup):
    name = State()
    phone = State()
    address = State()


class FlashSaleFSM(StatesGroup):
    select_product = State()
    enter_price = State()
    enter_hours = State()


class SupportTicketFSM(StatesGroup):
    subject = State()
    body = State()
    reply = State()


class BotAdFSM(StatesGroup):
    name = State()
    username = State()
    desc = State()
    photo = State()
    confirm = State()


class ProductAdFSM(StatesGroup):
    select_product = State()
    select_package = State()
    payment_proof = State()


class AdminTicketReplyFSM(StatesGroup):
    message = State()


class AdminStoreSearchFSM(StatesGroup):
    query = State()


async def get_lang(tg_id: int) -> str:
    now = time.time()
    cached = _LANG_CACHE.get(tg_id)
    if cached:
        lang, ts = cached
        if now - ts < _LANG_CACHE_TTL:
            return lang
    async with Session() as s:
        u = (await s.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
        lang = u.lang if u and u.lang else DEFAULT_LANG
    _LANG_CACHE[tg_id] = (lang, now)
    return lang


async def ensure_user(s, tg_id: int, default_lang: str = DEFAULT_LANG) -> User:
    u = (await s.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
    if not u:
        u = User(tg_id=tg_id, lang=default_lang)
        s.add(u)
        await s.flush()
    return u


async def get_stores_by_owner(tg_id: int):
    async with Session() as s:
        return (await s.execute(select(Store).where(Store.owner_tg_id == tg_id))).scalars().all()


async def get_store_rating(store_id: int, s) -> str:
    avg = (await s.execute(select(func.avg(Review.rating)).where(Review.store_id == store_id))).scalar()
    return f"{avg:.1f} ⭐" if avg else "لا يوجد تقييم"


async def is_store_owner(tg_id: int, store_id: int) -> bool:
    async with Session() as s:
        st = (await s.execute(select(Store).where(Store.id == store_id))).scalar_one_or_none()
        return bool(st and st.owner_tg_id == tg_id)


async def is_product_owner(tg_id: int, product_id: int) -> bool:
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == product_id, Product.is_deleted.is_(False)))).scalar_one_or_none()
        if not p:
            return False
        st = (await s.execute(select(Store).where(Store.id == p.store_id))).scalar_one_or_none()
        return bool(st and st.owner_tg_id == tg_id)


async def is_order_seller(tg_id: int, order_id: int) -> bool:
    async with Session() as s:
        o = (await s.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
        return bool(o and o.seller_tg_id == tg_id)


async def is_order_buyer(tg_id: int, order_id: int) -> bool:
    async with Session() as s:
        o = (await s.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
        return bool(o and o.buyer_tg_id == tg_id)


async def _get_owned_product(tg_id: int, pid: int):
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid, Product.is_deleted.is_(False)))).scalar_one_or_none()
        if not p:
            return None, None, "not_found"
        st = (await s.execute(select(Store).where(Store.id == p.store_id))).scalar_one_or_none()
        if not st or st.owner_tg_id != tg_id:
            return None, None, "unauthorized"
        return p, st, None


async def _guard_edit(cb: CallbackQuery, pid: int):
    p, _st, err = await _get_owned_product(cb.from_user.id, pid)
    if err == "not_found":
        await cb.answer("Not found", show_alert=True)
        return None
    if err == "unauthorized":
        await cb.answer("⛔ غير مصرح.", show_alert=True)
        return None
    if p.status == "pending":
        await cb.answer(
            "⏳ المنتج قيد المراجعة من الإدارة، لا يمكن التعديل حتى يتم البت فيه.",
            show_alert=True,
        )
        return None
    return p


async def notify_admins(bot: Bot, text: str, reply_markup=None, photo: str | None = None):
    for admin_id in ADMIN_IDS:
        try:
            if photo:
                await bot.send_photo(admin_id, photo=photo, caption=text, reply_markup=reply_markup)
            else:
                await bot.send_message(admin_id, text, reply_markup=reply_markup)
        except Exception as e:
            logger.warning(f"notify admin {admin_id} failed: {e}")


async def _safe_send_copy(message: Message, uid: int) -> bool:
    """Copy a message to a user while respecting Telegram FloodWait."""
    for _ in range(2):
        try:
            await message.copy_to(chat_id=uid)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except Exception:
            return False
    return False


def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=LANG_NAMES[l], callback_data=f"lang:{l}")] for l in LANGS]
    )


async def get_main_kb(tg_id: int, lang: str) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text=t(lang, "btn_buyer_section")), KeyboardButton(text=t(lang, "btn_seller_section"))],
        [KeyboardButton(text=t(lang, "btn_profile_section")), KeyboardButton(text=t(lang, "btn_ads_section"))],
    ]
    if tg_id in ADMIN_IDS:
        kb.append([KeyboardButton(text=t(lang, "btn_admin"))])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def back_kb(lang: str, callback: str = "menu:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=callback)]]
    )


def build_pagination_kb(items, page: int, prefix: str, lang: str, extra_buttons=None) -> InlineKeyboardMarkup:
    extra_buttons = extra_buttons or []
    total_pages = max(1, math.ceil(len(items) / ITEMS_PER_PAGE))
    page = max(1, min(page, total_pages))
    kb = []
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    for label, cb in items[start:end]:
        kb.append([InlineKeyboardButton(text=label, callback_data=cb)])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text=t(lang, "btn_prev"), callback_data=f"{prefix}:{page-1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=t(lang, "page_info", current=page, total=total_pages), callback_data="ignore"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text=t(lang, "btn_next"), callback_data=f"{prefix}:{page+1}"))
    if nav:
        kb.append(nav)
    for b in extra_buttons:
        kb.append([b])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def _current_price(p: Product) -> float:
    if p.flash_sale_price and p.flash_sale_ends_at and p.flash_sale_ends_at > utcnow():
        return float(p.flash_sale_price)
    return float(p.price)


def _product_line(p: Product) -> str:
    now = utcnow()
    flash = "🔥 " if (p.flash_sale_price and p.flash_sale_ends_at and p.flash_sale_ends_at > now) else ""
    star = "⭐ " if (p.featured_until and p.featured_until > now) else ""
    oos = "⚠️ " if p.is_out_of_stock else ""
    return f"{star}{flash}{oos}{p.title} — {_current_price(p):g} {p.currency}"


def _buyer_menu_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_browse"), callback_data="nav:browse"),
         InlineKeyboardButton(text=t(lang, "btn_browse_cats"), callback_data="nav:cats")],
        [InlineKeyboardButton(text=t(lang, "btn_search"), callback_data="nav:search"),
         InlineKeyboardButton(text=t(lang, "btn_search_store"), callback_data="nav:search_store")],
        [InlineKeyboardButton(text=t(lang, "btn_cart"), callback_data="nav:cart"),
         InlineKeyboardButton(text=t(lang, "btn_top_stores"), callback_data="nav:top_stores")],
        [InlineKeyboardButton(text=t(lang, "btn_browse_bot_ads"), callback_data="nav:bot_ads")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")],
    ])


def _account_menu_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_profile"), callback_data="nav:profile")],
        [InlineKeyboardButton(text=t(lang, "btn_my_orders"), callback_data="nav:orders"),
         InlineKeyboardButton(text=t(lang, "btn_favorites"), callback_data="nav:favs")],
        [InlineKeyboardButton(text=t(lang, "btn_support"), callback_data="nav:support"),
         InlineKeyboardButton(text=t(lang, "btn_lang"), callback_data="nav:lang")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")],
    ])


async def _render_buyer_menu(msg_obj, lang: str):
    await msg_obj.answer(t(lang, "buyer_menu_title"), reply_markup=_buyer_menu_kb(lang))


async def _render_account_menu(msg_obj, lang: str):
    await msg_obj.answer(t(lang, "account_menu"), reply_markup=_account_menu_kb(lang))


async def show_public_store(target_msg: Message, store_id: int, lang: str, page: int = 1, is_deeplink: bool = False, viewer_id: Optional[int] = None):
    uid = viewer_id or target_msg.chat.id
    async with Session() as s:
        store = (await s.execute(select(Store).where(Store.id == store_id))).scalar_one_or_none()
        if not store:
            return await target_msg.answer(t(lang, "no_products"))
        products = (
            await s.execute(
                select(Product)
                .where(Product.store_id == store_id, Product.status == "approved", Product.is_deleted.is_(False))
                .order_by(nullslast(Product.featured_until.desc()), Product.created_at.desc())
            )
        ).scalars().all()
        rating = await get_store_rating(store.id, s)
        followers_count = (await s.execute(select(func.count(StoreFollower.id)).where(StoreFollower.store_id == store.id))).scalar()
        is_following = (
            await s.execute(
                select(StoreFollower).where(StoreFollower.store_id == store.id, StoreFollower.user_tg_id == uid)
            )
        ).scalar_one_or_none()
    bio = esc(store.bio) if store.bio else "لا يوجد وصف."
    badge = t(lang, "verified_badge") if store.verified else ""
    if is_deeplink:
        text = t(lang, "store_welcome_deeplink", name=esc(store.name), badge=badge, store_bio=bio, rating=rating)
    else:
        text = t(lang, "public_store", name=esc(store.name), badge=badge, bio=bio, rating=rating, followers=followers_count)
    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    extra = []
    if is_following:
        extra.append(InlineKeyboardButton(text=t(lang, "btn_unfollow"), callback_data=f"fol_rm:{store.id}"))
    else:
        extra.append(InlineKeyboardButton(text=t(lang, "btn_follow"), callback_data=f"fol_add:{store.id}"))
    extra.append(InlineKeyboardButton(text=t(lang, "btn_report_store"), callback_data=f"rep_store:{store.id}"))
    extra.append(InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer"))
    kb = build_pagination_kb(items, page, f"pubstore:{store.id}", lang, extra)
    if store.logo_file_id:
        await target_msg.answer_photo(photo=store.logo_file_id, caption=text, reply_markup=kb)
    else:
        await target_msg.answer(text, reply_markup=kb)


async def send_store_dashboard(msg_obj, store_id: int, lang: str):
    async with Session() as s:
        store = await s.get(Store, store_id)
        if not store:
            return
        pcount = (
            await s.execute(
                select(func.count(Product.id)).where(Product.store_id == store.id, Product.is_deleted.is_(False))
            )
        ).scalar()
        vcount = (
            await s.execute(
                select(func.coalesce(func.sum(Product.views), 0)).where(Product.store_id == store.id, Product.is_deleted.is_(False))
            )
        ).scalar()
        fcount = (await s.execute(select(func.count(StoreFollower.id)).where(StoreFollower.store_id == store.id))).scalar()
        rating = await get_store_rating(store.id, s)
        total_stores = (await s.execute(select(func.count(Store.id)).where(Store.owner_tg_id == store.owner_tg_id))).scalar()
    badge = t(lang, "verified_badge") if store.verified else ""
    text = t(lang, "store_welcome", name=esc(store.name), badge=badge, products=pcount, views=vcount, followers=fcount, rating=rating)
    kb = [
        [InlineKeyboardButton(text=t(lang, "btn_add_product"), callback_data=f"st_add:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_my_products"), callback_data=f"st_list:{store.id}:1"),
         InlineKeyboardButton(text=t(lang, "btn_seller_orders"), callback_data=f"st_orders:{store.id}:1")],
        [InlineKeyboardButton(text=t(lang, "btn_flash_sale"), callback_data=f"st_flash:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_promos"), callback_data=f"st_promos:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_buy_product_ad"), callback_data=f"st_buy_ad:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_my_stats"), callback_data=f"st_stats:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_share"), callback_data=f"st_share:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_seller_broadcast"), callback_data=f"st_broadcast:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_settings"), callback_data=f"st_settings:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_seller_guide"), callback_data=f"st_guide:{store.id}")],
    ]
    if total_stores < MAX_STORES_PER_USER:
        kb.append([InlineKeyboardButton(text=t(lang, "add_new_store"), callback_data="nav:become_seller")])
    else:
        kb.append([InlineKeyboardButton(text=t(lang, "max_stores_reached"), callback_data="ignore")])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")])
    await msg_obj.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


async def _build_admin_panel_kb(lang: str) -> InlineKeyboardMarkup:
    async with Session() as s:
        c = (await s.execute(select(func.count(Product.id)).where(Product.status == "pending", Product.is_deleted.is_(False)))).scalar()
        r = (await s.execute(select(func.count(Report.id)).where(Report.status == "pending"))).scalar()
        tck = (await s.execute(select(func.count(SupportTicket.id)).where(SupportTicket.status == "open"))).scalar()
        bads = (await s.execute(select(func.count(BotAd.id)).where(BotAd.status == "pending"))).scalar()
        adreqs = (await s.execute(select(func.count(AdRequest.id)).where(AdRequest.status == "pending"))).scalar()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{t(lang, 'btn_pending')} ({c})", callback_data="admin:pending"),
         InlineKeyboardButton(text=f"{t(lang, 'btn_reports')} ({r})", callback_data="admin:reports")],
        [InlineKeyboardButton(text=f"{t(lang, 'btn_tickets')} ({tck})", callback_data="admin:tickets"),
         InlineKeyboardButton(text=t(lang, "btn_manage_stores"), callback_data="admin:stores")],
        [InlineKeyboardButton(text=t(lang, "btn_manage_cats"), callback_data="admin:cats"),
         InlineKeyboardButton(text=t(lang, "btn_global_stats"), callback_data="admin:gstats")],
        [InlineKeyboardButton(text=f"{t(lang, 'btn_manage_bot_ads')} ({bads})", callback_data="admin:botads"),
         InlineKeyboardButton(text=f"{t(lang, 'btn_manage_ad_requests')} ({adreqs})", callback_data="admin:adreqs")],
        [InlineKeyboardButton(text=t(lang, "btn_broadcast"), callback_data="admin:broadcast")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")],
    ])


# ════════════════════════════════════════════════════════════════════
# 4. COMMANDS & MAIN NAVIGATION (buyer_handlers)
# ════════════════════════════════════════════════════════════════════

@buyer_router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(message: Message, command: CommandObject, state: FSMContext):
    args = command.args or ""
    if args.startswith("store_"):
        try:
            identifier = args[len("store_"):]
            async with Session() as s:
                await ensure_user(s, message.from_user.id, DEFAULT_LANG)
                await s.commit()
                if identifier.isdigit():
                    store = (await s.execute(select(Store).where(Store.id == int(identifier)))).scalar_one_or_none()
                else:
                    store = (await s.execute(select(Store).where(Store.custom_slug == identifier.lower()))).scalar_one_or_none()
            if store:
                lang = await get_lang(message.from_user.id)
                await show_public_store(message, store.id, lang, page=1, is_deeplink=True, viewer_id=message.from_user.id)
                return
        except Exception as e:
            logger.error(f"Deep link error: {e}")
    await cmd_start(message, state)


@buyer_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    is_new = False
    async with Session() as s:
        user = (await s.execute(select(User).where(User.tg_id == message.from_user.id))).scalar_one_or_none()
        if not user:
            is_new = True
            user = User(tg_id=message.from_user.id, lang="")
            s.add(user)
            await s.commit()
        lang = user.lang or ""
    if is_new or not lang:
        return await message.answer(t(DEFAULT_LANG, "choose_lang"), reply_markup=lang_kb())
    async with Session() as s:
        ad = (
            await s.execute(
                select(BotAd)
                .where(BotAd.status == "approved", BotAd.expires_at.isnot(None), BotAd.expires_at > utcnow())
                .order_by(func.random())
                .limit(1)
            )
        ).scalar_one_or_none()
    if ad:
        ad_text = f"{t(lang, 'sponsored_ad')}\n\n🤖 <b>{esc(ad.bot_name)}</b>\n{esc(ad.description)}"
        ad_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=f"🚀 تجربة @{ad.bot_username}", url=f"https://t.me/{ad.bot_username}")]]
        )
        try:
            if ad.photo_file_id:
                await message.answer_photo(photo=ad.photo_file_id, caption=ad_text, reply_markup=ad_kb)
            else:
                await message.answer(ad_text, reply_markup=ad_kb)
            await asyncio.sleep(0.3)
        except Exception:
            pass
    kb = await get_main_kb(message.from_user.id, lang)
    await message.answer(t(lang, "welcome"), reply_markup=kb)


@buyer_router.callback_query(F.data.startswith("lang:"))
async def set_lang(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = cb.data.split(":")[1]
    if lang not in LANGS:
        return await cb.answer()
    async with Session() as s:
        u = (await s.execute(select(User).where(User.tg_id == cb.from_user.id))).scalar_one_or_none()
        if u:
            u.lang = lang
        else:
            s.add(User(tg_id=cb.from_user.id, lang=lang))
        await s.commit()
    invalidate_lang_cache(cb.from_user.id)
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "lang_set"))
    kb = await get_main_kb(cb.from_user.id, lang)
    await cb.message.answer(t(lang, "main_menu"), reply_markup=kb)
    await cb.answer()


@buyer_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    kb = await get_main_kb(message.from_user.id, lang)
    await message.answer(t(lang, "cancelled"), reply_markup=kb)


@buyer_router.callback_query(F.data == "menu:home")
async def menu_home(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_lang(cb.from_user.id)
    kb = await get_main_kb(cb.from_user.id, lang)
    await cb.message.answer(t(lang, "main_menu"), reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data == "ignore")
async def ignore_cb(cb: CallbackQuery):
    await cb.answer()


@buyer_router.callback_query(F.data == "redirect_cart")
async def redirect_cart(cb: CallbackQuery):
    await view_cart_for_user(cb.message, cb.from_user.id)
    await cb.answer()


@buyer_router.message(F.text.in_([t(l, "btn_buyer_section") for l in LANGS]))
async def buyer_section_menu(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    await _render_buyer_menu(message, lang)


@buyer_router.message(F.text.in_([t(l, "btn_profile_section") for l in LANGS]))
async def account_menu_handler(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    await _render_account_menu(message, lang)


@buyer_router.callback_query(F.data.startswith("nav:"))
async def nav_callback_handler(cb: CallbackQuery, state: FSMContext):
    action = cb.data.split(":")[1]
    uid = cb.from_user.id
    lang = await get_lang(uid)
    if action == "profile":
        await view_profile_for_user(cb.message, uid)
    elif action == "favs":
        await my_favs_for_user(cb.message, uid)
    elif action == "top_stores":
        await top_stores_for_user(cb.message, uid)
    elif action == "support":
        await support_menu_for_user(cb.message, uid)
    elif action == "cart":
        await view_cart_for_user(cb.message, uid)
    elif action == "orders":
        await buyer_orders_for_user(cb.message, uid)
    elif action == "admin":
        if uid in ADMIN_IDS:
            kb = await _build_admin_panel_kb(lang)
            await cb.message.answer(t(lang, "admin_panel"), reply_markup=kb)
    elif action == "browse":
        await browse_all_for_user(cb.message, uid)
    elif action == "cats":
        await browse_categories_for_user(cb.message, uid)
    elif action == "search":
        await state.set_state(Search.query)
        await cb.message.answer(t(lang, "search_prompt"), reply_markup=ReplyKeyboardRemove())
    elif action == "search_store":
        await state.set_state(SearchStore.query)
        await cb.message.answer(t(lang, "store_search_prompt"), reply_markup=ReplyKeyboardRemove())
    elif action == "lang":
        await cb.message.answer(t(lang, "choose_lang"), reply_markup=lang_kb())
    elif action == "account":
        await _render_account_menu(cb.message, lang)
    elif action == "buyer":
        await _render_buyer_menu(cb.message, lang)
    elif action == "bot_ads":
        await _render_bots_list(cb, 1)
        return
    elif action == "become_seller":
        stores = await get_stores_by_owner(uid)
        if len(stores) >= MAX_STORES_PER_USER:
            await cb.answer("❌ وصلت للحد الأقصى (3 متاجر).", show_alert=True)
            return
        await state.set_state(CreateStore.name)
        await cb.message.answer(t(lang, "store_create_prompt"), reply_markup=ReplyKeyboardRemove())
    await cb.answer()


# ════════════════════════════════════════════════════════════════════
# 5. BUYER FEATURES — ADS, PROFILE, SUPPORT, ORDERS, CART & CHECKOUT
# ════════════════════════════════════════════════════════════════════

# ─── Ads ───

@buyer_router.message(F.text.in_([t(l, "btn_ads_section") for l in LANGS]))
async def ads_menu(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_browse_featured"), callback_data="ads:featured:1")],
        [InlineKeyboardButton(text=t(lang, "btn_browse_bot_ads"), callback_data="ads:bots:1")],
        [InlineKeyboardButton(text=t(lang, "btn_create_bot_ad"), callback_data="ads:create_bot")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")],
    ])
    await message.answer(t(lang, "ads_menu_title"), reply_markup=kb)


@buyer_router.callback_query(F.data == "menu:ads")
async def menu_ads_cb(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_browse_featured"), callback_data="ads:featured:1")],
        [InlineKeyboardButton(text=t(lang, "btn_browse_bot_ads"), callback_data="ads:bots:1")],
        [InlineKeyboardButton(text=t(lang, "btn_create_bot_ad"), callback_data="ads:create_bot")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")],
    ])
    try:
        await cb.message.edit_text(t(lang, "ads_menu_title"), reply_markup=kb)
    except Exception:
        await cb.message.answer(t(lang, "ads_menu_title"), reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("ads:featured:"))
async def ads_featured(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[2])
    async with Session() as s:
        products = (
            await s.execute(
                select(Product)
                .where(
                    Product.status == "approved",
                    Product.is_deleted.is_(False),
                    Product.featured_until.isnot(None),
                    Product.featured_until > utcnow(),
                )
                .order_by(Product.featured_until.desc())
            )
        ).scalars().all()
    if not products:
        return await cb.answer(t(lang, "no_products"), show_alert=True)
    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    kb = build_pagination_kb(items, page, "ads:featured", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:ads")])
    try:
        await cb.message.edit_text(t(lang, "featured_products_title"), reply_markup=kb)
    except Exception:
        await cb.message.answer(t(lang, "featured_products_title"), reply_markup=kb)
    await cb.answer()


async def _render_bots_list(cb: CallbackQuery, page: int):
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        bots = (
            await s.execute(
                select(BotAd)
                .where(BotAd.status == "approved", BotAd.expires_at.isnot(None), BotAd.expires_at > utcnow())
                .order_by(BotAd.created_at.desc())
            )
        ).scalars().all()
    if not bots:
        return await cb.answer(t(lang, "no_bot_ads"), show_alert=True)
    items = [(f"🤖 {b.bot_name}", f"ads:view_bot:{b.id}") for b in bots]
    kb = build_pagination_kb(items, page, "ads:bots", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:ads")])
    try:
        await cb.message.edit_text(t(lang, "bot_ads_title"), reply_markup=kb)
    except Exception:
        await cb.message.answer(t(lang, "bot_ads_title"), reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("ads:bots:"))
async def ads_bots(cb: CallbackQuery):
    page = int(cb.data.split(":")[2])
    await _render_bots_list(cb, page)


@buyer_router.callback_query(F.data.startswith("ads:view_bot:"))
async def ads_view_bot(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    bot_id = int(cb.data.split(":")[2])
    async with Session() as s:
        b = (await s.execute(select(BotAd).where(BotAd.id == bot_id))).scalar_one_or_none()
        if not b:
            return await cb.answer("Not found", show_alert=True)
        b.views += 1
        await s.commit()
    caption = f"🤖 <b>{esc(b.bot_name)}</b>\n\n{esc(b.description)}\n\n🔗 @{esc(b.bot_username)}\n👁️ المشاهدات: {b.views}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚀 تجربة @{b.bot_username}", url=f"https://t.me/{b.bot_username}")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="ads:bots:1")],
    ])
    if b.photo_file_id:
        await cb.message.answer_photo(photo=b.photo_file_id, caption=caption, reply_markup=kb)
    else:
        await cb.message.answer(caption, reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data == "ads:create_bot")
async def create_bot_ad_start(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    await state.set_state(BotAdFSM.name)
    await cb.message.answer(t(lang, "bot_ad_name"), reply_markup=ReplyKeyboardRemove())
    await cb.answer()


@buyer_router.message(BotAdFSM.name)
async def bot_ad_name(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        return await message.answer(t(await get_lang(message.from_user.id), "bot_ad_name"))
    await state.update_data(name=message.text.strip()[:100])
    await state.set_state(BotAdFSM.username)
    await message.answer(t(await get_lang(message.from_user.id), "bot_ad_username"))


@buyer_router.message(BotAdFSM.username)
async def bot_ad_username(message: Message, state: FSMContext):
    raw = (message.text or "").strip().replace("https://t.me/", "").lstrip("@")[:100]
    if not re.match(r"^[A-Za-z0-9_]{3,64}$", raw):
        return await message.answer(t(await get_lang(message.from_user.id), "bot_ad_username"))
    await state.update_data(username=raw)
    await state.set_state(BotAdFSM.desc)
    await message.answer(t(await get_lang(message.from_user.id), "bot_ad_desc"))


@buyer_router.message(BotAdFSM.desc)
async def bot_ad_desc(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        return await message.answer(t(await get_lang(message.from_user.id), "bot_ad_desc"))
    await state.update_data(desc=message.text.strip()[:500])
    await state.set_state(BotAdFSM.photo)
    await message.answer(t(await get_lang(message.from_user.id), "bot_ad_photo"))


@buyer_router.message(BotAdFSM.photo, F.photo)
async def bot_ad_photo(message: Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await finalize_bot_ad(message, message.from_user.id, state)


@buyer_router.message(BotAdFSM.photo, ~F.photo)
async def bot_ad_photo_invalid(message: Message):
    await message.answer(t(await get_lang(message.from_user.id), "bot_ad_photo"))


async def finalize_bot_ad(message_obj, user_id: int, state: FSMContext):
    data = await state.get_data()
    await state.set_state(BotAdFSM.confirm)
    lang = await get_lang(user_id)
    text = t(
        lang,
        "bot_ad_review",
        name=esc(data.get("name", "")),
        username=esc(data.get("username", "")),
        desc=esc(data.get("desc", "")[:100]),
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_confirm"), callback_data="botad:confirm"),
        InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="menu:ads"),
    ]])
    await message_obj.answer(text, reply_markup=kb)


@buyer_router.callback_query(F.data == "botad:confirm")
async def bot_ad_confirm(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("name"):
        return await cb.answer("انتهت الجلسة، ابدأ من جديد.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        ad = BotAd(
            owner_tg_id=cb.from_user.id,
            bot_name=data["name"],
            bot_username=data["username"],
            description=data["desc"],
            photo_file_id=data.get("photo", ""),
            status="pending",
        )
        s.add(ad)
        await s.commit()
        await s.refresh(ad)
        ad_id = ad.id
    await state.clear()
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "bot_ad_submitted"))
    await cb.message.answer(t(lang, "main_menu"), reply_markup=await get_main_kb(cb.from_user.id, lang))
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("ar", "btn_approve_bot_ad"), callback_data=f"admin:botad_app:{ad_id}"),
        InlineKeyboardButton(text=t("ar", "btn_reject_bot_ad"), callback_data=f"admin:botad_rej:{ad_id}"),
    ]])
    admin_text = t("ar", "admin_bot_ad_view", name=esc(data["name"]), username=esc(data["username"]), desc=esc(data["desc"]))
    await notify_admins(cb.bot, admin_text, reply_markup=admin_kb, photo=data.get("photo") or None)
    await cb.answer()


# ─── Profile ───

async def view_profile_for_user(target_msg: Message, uid: int):
    lang = await get_lang(uid)
    async with Session() as s:
        u = await ensure_user(s, uid, lang)
        await s.commit()
    name = esc(u.saved_name) if u.saved_name else "غير محدد"
    phone = esc(u.saved_phone) if u.saved_phone else "غير محدد"
    addr = esc(u.saved_address) if u.saved_address else "غير محدد"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_edit_profile_name"), callback_data="prof_edit:name")],
        [InlineKeyboardButton(text=t(lang, "btn_edit_profile_phone"), callback_data="prof_edit:phone")],
        [InlineKeyboardButton(text=t(lang, "btn_edit_profile_address"), callback_data="prof_edit:address")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:account")],
    ])
    await target_msg.answer(t(lang, "profile_menu", name=name, phone=phone, address=addr), reply_markup=kb)


@buyer_router.message(F.text.in_([t(l, "btn_profile") for l in LANGS]))
async def view_profile(message: Message):
    await view_profile_for_user(message, message.from_user.id)


@buyer_router.callback_query(F.data.startswith("prof_edit:"))
async def edit_profile_start(cb: CallbackQuery, state: FSMContext):
    field = cb.data.split(":")[1]
    lang = await get_lang(cb.from_user.id)
    if field == "name":
        await state.set_state(ProfileFSM.name)
        await cb.message.answer(t(lang, "enter_p_name"))
    elif field == "phone":
        await state.set_state(ProfileFSM.phone)
        await cb.message.answer(t(lang, "enter_p_phone"))
    elif field == "address":
        await state.set_state(ProfileFSM.address)
        await cb.message.answer(t(lang, "enter_p_address"))
    await cb.answer()


@buyer_router.message(ProfileFSM.name)
async def save_profile_name(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "enter_p_name"))
    async with Session() as s:
        u = await ensure_user(s, message.from_user.id, lang)
        u.saved_name = message.text.strip()[:MAX_PROFILE_NAME_LEN]
        await s.commit()
    await message.answer(t(lang, "profile_updated"), reply_markup=await get_main_kb(message.from_user.id, lang))
    await state.clear()


@buyer_router.message(ProfileFSM.phone)
async def save_profile_phone(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "enter_p_phone"))
    async with Session() as s:
        u = await ensure_user(s, message.from_user.id, lang)
        u.saved_phone = message.text.strip()[:MAX_PROFILE_PHONE_LEN]
        await s.commit()
    await message.answer(t(lang, "profile_updated"), reply_markup=await get_main_kb(message.from_user.id, lang))
    await state.clear()


@buyer_router.message(ProfileFSM.address)
async def save_profile_address(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "enter_p_address"))
    async with Session() as s:
        u = await ensure_user(s, message.from_user.id, lang)
        u.saved_address = message.text.strip()[:500]
        await s.commit()
    await message.answer(t(lang, "profile_updated"), reply_markup=await get_main_kb(message.from_user.id, lang))
    await state.clear()


# ─── Support Tickets ───

async def support_menu_for_user(target_msg: Message, uid: int):
    lang = await get_lang(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_new_ticket"), callback_data="ticket:new")],
        [InlineKeyboardButton(text=t(lang, "btn_my_tickets"), callback_data="ticket:list:1")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:account")],
    ])
    await target_msg.answer(t(lang, "support_msg"), reply_markup=kb)


@buyer_router.message(F.text.in_([t(l, "btn_support") for l in LANGS]))
async def support_menu(message: Message):
    await support_menu_for_user(message, message.from_user.id)


@buyer_router.callback_query(F.data == "ticket:new")
async def ticket_new_start(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    await state.set_state(SupportTicketFSM.subject)
    await cb.message.answer(t(lang, "ticket_subject"), reply_markup=ReplyKeyboardRemove())
    await cb.answer()


@buyer_router.message(SupportTicketFSM.subject)
async def ticket_subject_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "ticket_subject"))
    await state.update_data(subject=message.text.strip()[:MAX_TICKET_SUBJECT_LEN])
    await state.set_state(SupportTicketFSM.body)
    await message.answer(t(lang, "ticket_body"))


@buyer_router.message(SupportTicketFSM.body)
async def ticket_body_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    subject = data.get("subject", "-")
    body_text = (message.text or message.caption or "صورة/ملف")[:2000]
    async with Session() as s:
        ticket = SupportTicket(user_tg_id=message.from_user.id, subject=subject)
        s.add(ticket)
        await s.commit()
        await s.refresh(ticket)
        s.add(TicketMessage(ticket_id=ticket.id, sender_tg_id=message.from_user.id, text=body_text, is_admin=False))
        await s.commit()
        ticket_id = ticket.id
    await state.clear()
    kb = await get_main_kb(message.from_user.id, lang)
    await message.answer(t(lang, "ticket_created", id=ticket_id), reply_markup=kb)
    await notify_admins(
        message.bot,
        f"🎫 تذكرة جديدة #{ticket_id} من {esc(message.from_user.full_name)}\n"
        f"الموضوع: {esc(subject)}\n\n{esc(body_text)}",
    )


@buyer_router.callback_query(F.data.startswith("ticket:list:"))
async def ticket_list(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[2])
    async with Session() as s:
        tickets = (
            await s.execute(
                select(SupportTicket)
                .where(SupportTicket.user_tg_id == cb.from_user.id)
                .order_by(SupportTicket.created_at.desc())
            )
        ).scalars().all()
    if not tickets:
        return await cb.answer(t(lang, "tickets_empty"), show_alert=True)
    items = [(f"{'🟢' if tk.status == 'open' else '🔴'} #{tk.id} - {tk.subject}", f"ticket:view:{tk.id}") for tk in tickets]
    kb = build_pagination_kb(items, page, "ticket:list", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:account")])
    try:
        await cb.message.edit_text(t(lang, "btn_my_tickets"), reply_markup=kb)
    except Exception:
        await cb.message.answer(t(lang, "btn_my_tickets"), reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("ticket:view:"))
async def ticket_view(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    t_id = int(cb.data.split(":")[2])
    async with Session() as s:
        tk = (await s.execute(select(SupportTicket).where(SupportTicket.id == t_id))).scalar_one_or_none()
        if not tk or tk.user_tg_id != cb.from_user.id:
            return await cb.answer("Not found", show_alert=True)
        msgs = (
            await s.execute(select(TicketMessage).where(TicketMessage.ticket_id == t_id).order_by(TicketMessage.created_at.asc()))
        ).scalars().all()
    status_str = t(lang, "ticket_status_open") if tk.status == "open" else t(lang, "ticket_status_closed")
    text = f"🎫 <b>تذكرة #{t_id}: {esc(tk.subject)}</b> ({status_str})\n\n"
    for m in msgs:
        sender = "👨‍💼 الإدارة:" if m.is_admin else "👤 أنت:"
        text += f"{sender}\n{esc(m.text)}\n\n"
    rows = []
    if tk.status == "open":
        rows.append([InlineKeyboardButton(text=t(lang, "btn_reply_ticket"), callback_data=f"ticket:reply:{t_id}")])
        rows.append([InlineKeyboardButton(text=t(lang, "btn_close_ticket"), callback_data=f"ticket:close:{t_id}")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="ticket:list:1")])
    await cb.message.answer(text[:4000], reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


async def _is_ticket_owner(tg_id: int, t_id: int) -> bool:
    async with Session() as s:
        tk = (await s.execute(select(SupportTicket).where(SupportTicket.id == t_id))).scalar_one_or_none()
        return bool(tk and tk.user_tg_id == tg_id)


@buyer_router.callback_query(F.data.startswith("ticket:close:"))
async def ticket_close_user(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    t_id = int(cb.data.split(":")[2])
    if not await _is_ticket_owner(cb.from_user.id, t_id):
        return await cb.answer("Not found", show_alert=True)
    async with Session() as s:
        tk = (await s.execute(select(SupportTicket).where(SupportTicket.id == t_id))).scalar_one_or_none()
        if tk:
            tk.status = "closed"
            await s.commit()
    await cb.answer(t(lang, "ticket_closed"), show_alert=True)
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=back_kb(lang, "ticket:list:1"))


@buyer_router.callback_query(F.data.startswith("ticket:reply:"))
async def ticket_reply_start(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    t_id = int(cb.data.split(":")[2])
    if not await _is_ticket_owner(cb.from_user.id, t_id):
        return await cb.answer("Not found", show_alert=True)
    await state.update_data(ticket_id=t_id)
    await state.set_state(SupportTicketFSM.reply)
    await cb.message.answer(t(lang, "ticket_reply_prompt"))
    await cb.answer()


@buyer_router.message(SupportTicketFSM.reply)
async def ticket_reply_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    t_id = data.get("ticket_id")
    await state.clear()
    if not t_id or not await _is_ticket_owner(message.from_user.id, t_id):
        return
    body_text = (message.text or message.caption or "صورة/ملف")[:2000]
    async with Session() as s:
        tk = (await s.execute(select(SupportTicket).where(SupportTicket.id == t_id))).scalar_one_or_none()
        if not tk:
            return
        s.add(TicketMessage(ticket_id=t_id, sender_tg_id=message.from_user.id, text=body_text, is_admin=False))
        tk.status = "open"
        await s.commit()
    kb = await get_main_kb(message.from_user.id, lang)
    await message.answer("✅ تم إرسال ردك للإدارة.", reply_markup=kb)
    await notify_admins(
        message.bot,
        f"💬 رد جديد على تذكرة #{t_id} من {esc(message.from_user.full_name)}:\n\n{esc(body_text)}",
    )


# ─── Buyer Orders ───

async def buyer_orders_for_user(target_msg: Message, uid: int):
    lang = await get_lang(uid)
    async with Session() as s:
        orders = (
            await s.execute(select(Order).where(Order.buyer_tg_id == uid).order_by(Order.created_at.desc()))
        ).scalars().all()
    if not orders:
        return await target_msg.answer(t(lang, "buyer_orders_empty"), reply_markup=back_kb(lang, "nav:account"))
    status_icons = {"pending": "⏳", "shipped": "🚚", "completed": "✅", "cancelled": "❌"}
    items = [(f"{status_icons.get(o.status, '')} طلب #{o.id} - {o.buyer_name}", f"b_ord_view:{o.id}") for o in orders]
    kb = build_pagination_kb(items, 1, "b_ord_pg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:account")])
    await target_msg.answer(t(lang, "buyer_orders_list"), reply_markup=kb)


@buyer_router.message(F.text.in_([t(l, "btn_my_orders") for l in LANGS]))
async def buyer_orders_list(message: Message):
    await buyer_orders_for_user(message, message.from_user.id)


@buyer_router.callback_query(F.data.startswith("b_ord_pg:"))
async def buyer_orders_pg(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[1])
    async with Session() as s:
        orders = (
            await s.execute(select(Order).where(Order.buyer_tg_id == cb.from_user.id).order_by(Order.created_at.desc()))
        ).scalars().all()
    status_icons = {"pending": "⏳", "shipped": "🚚", "completed": "✅", "cancelled": "❌"}
    items = [(f"{status_icons.get(o.status, '')} طلب #{o.id} - {o.buyer_name}", f"b_ord_view:{o.id}") for o in orders]
    kb = build_pagination_kb(items, page, "b_ord_pg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:account")])
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("b_ord_view:"))
async def buyer_order_details(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    oid = int(cb.data.split(":")[1])
    if not await is_order_buyer(cb.from_user.id, oid):
        return await cb.answer("Not found", show_alert=True)
    async with Session() as s:
        o = (await s.execute(select(Order).where(Order.id == oid))).scalar_one_or_none()
        if not o:
            return await cb.answer("Not found", show_alert=True)
        p = (await s.execute(select(Product).where(Product.id == o.product_id))).scalar_one_or_none() if o.product_id else None
    p_title = esc(p.title if p else (o.product_title or "منتج محذوف"))
    p_curr = esc(p.currency if p else (o.product_currency or DEFAULT_CURRENCY))
    status_map = {
        "pending": t(lang, "status_pending"),
        "shipped": t(lang, "status_shipped"),
        "completed": t(lang, "status_completed"),
        "cancelled": t(lang, "status_cancelled"),
    }
    date_str = o.created_at.strftime("%Y-%m-%d %H:%M")
    text = t(
        lang,
        "buyer_order_details",
        id=oid,
        product=p_title,
        variation=esc(o.variation or "-"),
        price=f"{o.price:.2f} {p_curr}",
        delivery=f"{o.delivery_fee:g} {p_curr}",
        status=status_map.get(o.status, o.status),
        date=date_str,
    )
    await cb.message.answer(text, reply_markup=back_kb(lang, "nav:account"))
    await cb.answer()


# ─── Cart & Checkout ───

@buyer_router.callback_query(F.data.startswith("restock:"))
async def restock_add(cb: CallbackQuery):
    pid = int(cb.data.split(":")[1])
    lang = await get_lang(cb.from_user.id)
    try:
        async with Session() as s:
            s.add(RestockAlert(user_tg_id=cb.from_user.id, product_id=pid))
            await s.commit()
    except IntegrityError:
        pass
    await cb.answer(t(lang, "restock_saved"), show_alert=True)


@buyer_router.callback_query(F.data.startswith("cart_add:"))
async def cart_add(cb: CallbackQuery):
    pid = int(cb.data.split(":")[1])
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid, Product.is_deleted.is_(False), Product.status == "approved"))).scalar_one_or_none()
        if not p or p.is_out_of_stock:
            return await cb.answer("⚠️ نفدت الكمية.", show_alert=True)
        vars_list = _product_vars(p)
        if vars_list:
            # Use index in callback_data to stay well within Telegram's 64-byte limit
            kb = [[InlineKeyboardButton(text=v, callback_data=f"cart_var:{pid}:{idx}")] for idx, v in enumerate(vars_list)]
            await cb.message.answer(t(lang, "var_select_prompt"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
            await cb.answer()
            return
    try:
        async with Session() as s:
            s.add(CartItem(user_tg_id=cb.from_user.id, product_id=pid, variation=""))
            await s.commit()
    except IntegrityError:
        pass
    await cb.answer(t(lang, "cart_added"), show_alert=True)


@buyer_router.callback_query(F.data.startswith("cart_var:"))
async def cart_add_var(cb: CallbackQuery):
    _, pid_str, idx_str = cb.data.split(":", 2)
    pid = int(pid_str)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid, Product.is_deleted.is_(False)))).scalar_one_or_none()
        if not p:
            return await cb.answer("Not found", show_alert=True)
        vars_list = _product_vars(p)
        if idx_str.isdigit() and 0 <= int(idx_str) < len(vars_list):
            var = vars_list[int(idx_str)]
        else:
            var = idx_str[:100]
        try:
            s.add(CartItem(user_tg_id=cb.from_user.id, product_id=pid, variation=var))
            await s.commit()
        except IntegrityError:
            pass
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "cart_added"))
    await cb.answer()


async def view_cart_for_user(target_msg: Message, uid: int):
    lang = await get_lang(uid)
    async with Session() as s:
        cart_items = (await s.execute(select(CartItem).where(CartItem.user_tg_id == uid))).scalars().all()
        if not cart_items:
            return await target_msg.answer(t(lang, "cart_empty"), reply_markup=back_kb(lang, "nav:buyer"))
        p_ids = [c.product_id for c in cart_items]
        products = (
            await s.execute(
                select(Product).where(Product.id.in_(p_ids), Product.status == "approved", Product.is_deleted.is_(False))
            )
        ).scalars().all()

    if not products:
        return await target_msg.answer(t(lang, "cart_empty"), reply_markup=back_kb(lang, "nav:buyer"))

    by_id = {p.id: p for p in products}
    total = 0.0
    lines = []
    has_available = False
    for c in cart_items:
        p = by_id.get(c.product_id)
        if not p:
            continue
        price = _current_price(p)
        var_str = f" ({esc(c.variation)})" if c.variation else ""
        if p.is_out_of_stock:
            lines.append(f"⚠️ <s>{esc(p.title)}</s>{var_str} — نفدت الكمية")
        else:
            total += price
            has_available = True
            lines.append(f"📦 {esc(p.title)}{var_str} - {price:.2f} {esc(p.currency)}")

    if not lines:
        return await target_msg.answer(t(lang, "cart_empty"), reply_markup=back_kb(lang, "nav:buyer"))

    text = t(lang, "my_cart") + "\n\n" + "\n".join(lines)
    if has_available:
        text += f"\n\n💰 <b>الإجمالي: {total:.2f}</b>"
    else:
        text += "\n\n⚠️ <b>جميع المنتجات في سلتك نفدت كميتها حالياً.</b>"

    rows = []
    if has_available:
        rows.append([InlineKeyboardButton(text=t(lang, "cart_checkout"), callback_data="cart_checkout")])
    rows.append([InlineKeyboardButton(text=t(lang, "cart_clear"), callback_data="cart_clear")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")])
    await target_msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@buyer_router.message(F.text.in_([t(l, "btn_cart") for l in LANGS]))
async def view_cart(message: Message):
    await view_cart_for_user(message, message.from_user.id)


@buyer_router.callback_query(F.data == "cart_clear")
async def cart_clear(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        await s.execute(delete(CartItem).where(CartItem.user_tg_id == cb.from_user.id))
        await s.commit()
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "cart_empty"), reply_markup=back_kb(lang, "nav:buyer"))
    await cb.answer()


@buyer_router.callback_query(F.data == "cart_checkout")
async def cart_checkout_start(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await start_checkout_flow(cb.message, cb.from_user.id, state)
    await cb.answer()


async def start_checkout_flow(msg_obj, user_id: int, state: FSMContext):
    lang = await get_lang(user_id)
    async with Session() as s:
        u = await ensure_user(s, user_id, lang)
        await s.commit()
        has_profile = bool(u.saved_name and u.saved_phone and u.saved_address)
    if has_profile:
        await state.update_data(p_name=u.saved_name, p_phone=u.saved_phone, p_address=u.saved_address)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_use_saved"), callback_data="checkout_use_saved")],
            [InlineKeyboardButton(text="✏️ إدخال بيانات جديدة", callback_data="checkout_new_info")],
        ])
        await msg_obj.answer(
            f"👤 الاسم: {esc(u.saved_name)}\n📞 الهاتف: {esc(u.saved_phone)}\n📍 العنوان: {esc(u.saved_address)}",
            reply_markup=kb,
        )
    else:
        await state.set_state(OrderFSM.name)
        await msg_obj.answer(t(lang, "order_name"), reply_markup=ReplyKeyboardRemove())


@buyer_router.callback_query(F.data == "checkout_new_info")
async def checkout_new_info(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    await state.set_state(OrderFSM.name)
    await cb.message.answer(t(lang, "order_name"), reply_markup=ReplyKeyboardRemove())
    await cb.answer()


@buyer_router.callback_query(F.data == "checkout_use_saved")
async def checkout_use_saved(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    await state.set_state(OrderFSM.note)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_note"), callback_data="skip_note")]])
    await cb.message.answer(t(lang, "order_note"), reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("order_start:"))
async def order_start(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    pid = int(cb.data.split(":")[1])
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid, Product.is_deleted.is_(False), Product.status == "approved"))).scalar_one_or_none()
    if not p or p.is_out_of_stock:
        return await cb.answer("⚠️ نفدت الكمية.", show_alert=True)
    vars_list = _product_vars(p)
    if vars_list:
        kb = [[InlineKeyboardButton(text=v, callback_data=f"order_var:{pid}:{idx}")] for idx, v in enumerate(vars_list)]
        await cb.message.answer(t(lang, "var_select_prompt"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        await cb.answer()
        return
    await state.clear()
    await state.update_data(order_pid=pid, selected_var="")
    await start_checkout_flow(cb.message, cb.from_user.id, state)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("order_var:"))
async def order_var_select(cb: CallbackQuery, state: FSMContext):
    _, pid_str, idx_str = cb.data.split(":", 2)
    pid = int(pid_str)
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid, Product.is_deleted.is_(False)))).scalar_one_or_none()
        if not p:
            return await cb.answer("Not found", show_alert=True)
        vars_list = _product_vars(p)
        var = vars_list[int(idx_str)] if (idx_str.isdigit() and 0 <= int(idx_str) < len(vars_list)) else idx_str[:100]
    await state.clear()
    await state.update_data(order_pid=pid, selected_var=var)
    await start_checkout_flow(cb.message, cb.from_user.id, state)
    await cb.answer()


@buyer_router.message(OrderFSM.name)
async def order_name(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "order_name"))
    await state.update_data(p_name=message.text.strip()[:MAX_PROFILE_NAME_LEN])
    await state.set_state(OrderFSM.phone)
    await message.answer(t(lang, "order_phone"))


@buyer_router.message(OrderFSM.phone)
async def order_phone(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "order_phone"))
    await state.update_data(p_phone=message.text.strip()[:MAX_PROFILE_PHONE_LEN])
    await state.set_state(OrderFSM.address)
    await message.answer(t(lang, "order_address"))


@buyer_router.message(OrderFSM.address)
async def order_address(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "order_address"))
    await state.update_data(p_address=message.text.strip()[:500])
    await state.set_state(OrderFSM.note)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_note"), callback_data="skip_note")]])
    await message.answer(t(lang, "order_note"), reply_markup=kb)


@buyer_router.callback_query(F.data == "skip_note")
async def skip_note(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    await state.update_data(order_note="")
    await state.set_state(OrderFSM.promo)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_promo"), callback_data="skip_promo")]])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "order_promo"), reply_markup=kb)
    await cb.answer()


@buyer_router.message(OrderFSM.note)
async def order_note(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.update_data(order_note=(message.text or "").strip()[:MAX_ORDER_NOTE_LEN])
    await state.set_state(OrderFSM.promo)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_promo"), callback_data="skip_promo")]])
    await message.answer(t(lang, "order_promo"), reply_markup=kb)


@buyer_router.callback_query(F.data == "skip_promo")
async def skip_promo(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await process_checkout(cb.message, cb.from_user.id, state, None)


@buyer_router.message(OrderFSM.promo)
async def apply_promo(message: Message, state: FSMContext):
    code = (message.text or "").strip().upper()
    if not code:
        return await process_checkout(message, message.from_user.id, state, None)
    await process_checkout(message, message.from_user.id, state, code)


async def process_checkout(message_obj, user_id: int, state: FSMContext, promo_code: str | None):
    lang = await get_lang(user_id)
    data = await state.get_data()
    name = data.get("p_name", "")
    phone = data.get("p_phone", "")
    addr = data.get("p_address", "")
    note = data.get("order_note", "")
    is_direct_order = bool(data.get("order_pid"))

    if not (name and phone and addr):
        await state.clear()
        return await message_obj.answer(t(lang, "cancelled"), reply_markup=await get_main_kb(user_id, lang))

    pairs = []
    async with Session() as s:
        u = await ensure_user(s, user_id, lang)
        if not u.saved_name:
            u.saved_name, u.saved_phone, u.saved_address = name, phone, addr

        if is_direct_order:
            p = (
                await s.execute(
                    select(Product).where(Product.id == data["order_pid"], Product.status == "approved", Product.is_deleted.is_(False))
                )
            ).scalar_one_or_none()
            if p:
                pairs.append((p, data.get("selected_var", "")))
        else:
            cart_items = (await s.execute(select(CartItem).where(CartItem.user_tg_id == user_id))).scalars().all()
            for ci in cart_items:
                p = (
                    await s.execute(
                        select(Product).where(Product.id == ci.product_id, Product.status == "approved", Product.is_deleted.is_(False))
                    )
                ).scalar_one_or_none()
                if p:
                    pairs.append((p, ci.variation))

        if not pairs:
            if not is_direct_order:
                await s.execute(delete(CartItem).where(CartItem.user_tg_id == user_id))
            await s.commit()
            await state.clear()
            return await message_obj.answer(t(lang, "cart_empty"), reply_markup=await get_main_kb(user_id, lang))

        by_store: dict[int, list[tuple[Product, str]]] = {}
        for p, var in pairs:
            by_store.setdefault(p.store_id, []).append((p, var))

        # Validate promo code before creating orders so invalid codes don't silently charge full price
        store_discounts: dict[int, int] = {}
        if promo_code:
            for store_id in by_store:
                promo = (
                    await s.execute(
                        select(PromoCode).where(
                            PromoCode.store_id == store_id,
                            PromoCode.code == promo_code,
                            PromoCode.is_active.is_(True),
                        )
                    )
                ).scalar_one_or_none()
                if promo and 1 <= promo.discount_percent <= 99:
                    store_discounts[store_id] = promo.discount_percent
            if not store_discounts:
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_promo"), callback_data="skip_promo")]]
                )
                return await message_obj.answer(t(lang, "invalid_promo"), reply_markup=kb)

        orders_created = 0
        failed_titles: list[str] = []
        seller_notifications: list[tuple[int, str]] = []
        total_charged = 0.0

        for store_id, list_ in by_store.items():
            store = (await s.execute(select(Store).where(Store.id == store_id))).scalar_one_or_none()
            if not store:
                continue
            discount_percent = store_discounts.get(store_id, 0)

            for p, var in list_:
                base = _current_price(p)
                final_price = max(0.0, base * (1 - discount_percent / 100.0))

                res = await s.execute(
                    update(Product)
                    .where(Product.id == p.id, Product.stock_quantity > 0, Product.is_deleted.is_(False))
                    .values(stock_quantity=Product.stock_quantity - 1)
                )
                if res.rowcount == 0:
                    failed_titles.append(p.title)
                    continue

                await s.execute(
                    update(Product)
                    .where(Product.id == p.id, Product.stock_quantity <= 0)
                    .values(is_out_of_stock=True)
                )
                order = Order(
                    product_id=p.id,
                    store_id=store.id,
                    product_title=p.title,
                    product_currency=p.currency,
                    seller_tg_id=store.owner_tg_id,
                    buyer_tg_id=user_id,
                    buyer_name=name,
                    buyer_phone=phone,
                    buyer_address=addr,
                    buyer_note=note,
                    variation=var,
                    price=final_price,
                    delivery_fee=p.delivery_fee,
                )
                s.add(order)
                orders_created += 1
                total_charged += final_price

                sl = await get_lang(store.owner_tg_id)
                seller_text = t(
                    sl,
                    "new_order_notify",
                    product=esc(p.title),
                    variation=esc(var or "-"),
                    name=esc(name),
                    phone=esc(phone),
                    address=esc(addr),
                    note=esc(note or "-"),
                    price=f"{final_price:.2f} {esc(p.currency)}",
                    delivery=f"{p.delivery_fee:g} {esc(p.currency)}",
                )
                seller_notifications.append((store.owner_tg_id, seller_text))

        # Only clear cart when checking out FROM cart, not direct "Order now"
        if not is_direct_order:
            await s.execute(delete(CartItem).where(CartItem.user_tg_id == user_id))
        await s.commit()

    await state.clear()

    for seller_uid, seller_text in seller_notifications:
        with suppress(Exception):
            await message_obj.bot.send_message(seller_uid, seller_text)

    if orders_created == 0:
        failed_str = "\n• " + "\n• ".join(esc(x) for x in failed_titles[:5]) if failed_titles else ""
        await message_obj.answer(
            f"⚠️ <b>لم يتم إنشاء أي طلب</b>\n\nالمنتجات التالية نفدت كميتها قبل إتمام الطلب:{failed_str}",
            reply_markup=await get_main_kb(user_id, lang),
        )
    elif failed_titles:
        await message_obj.answer(
            "⚠️ <b>تنبيه:</b> بعض المنتجات نفدت كميتها ولم تُضف للطلب:\n"
            + "\n".join(f"• {esc(x)}" for x in failed_titles)
            + f"\n\n✅ تم إنشاء <b>{orders_created}</b> طلب بنجاح.",
            reply_markup=await get_main_kb(user_id, lang),
        )
    else:
        promo_note = f"\n{t(lang, 'promo_applied', price=f'{total_charged:.2f}')}" if store_discounts else ""
        await message_obj.answer(t(lang, "order_success") + promo_note, reply_markup=await get_main_kb(user_id, lang))


# ════════════════════════════════════════════════════════════════════
# 6. BUYER FEATURES — BROWSE, CATEGORIES, SEARCH, PRODUCT VIEW, SOCIAL
# ════════════════════════════════════════════════════════════════════

async def browse_all_for_user(target_msg: Message, uid: int):
    lang = await get_lang(uid)
    async with Session() as s:
        products = (
            await s.execute(
                select(Product)
                .where(Product.status == "approved", Product.is_deleted.is_(False))
                .order_by(nullslast(Product.featured_until.desc()), Product.created_at.desc())
            )
        ).scalars().all()
    if not products:
        return await target_msg.answer(t(lang, "no_products"), reply_markup=back_kb(lang, "nav:buyer"))
    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    kb = build_pagination_kb(items, 1, "browse_pg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")])
    await target_msg.answer(t(lang, "all_products"), reply_markup=kb)


@buyer_router.message(F.text.in_([t(l, "btn_browse") for l in LANGS]))
async def browse_all(message: Message):
    await browse_all_for_user(message, message.from_user.id)


@buyer_router.callback_query(F.data.startswith("browse_pg:"))
async def browse_pg(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[1])
    async with Session() as s:
        products = (
            await s.execute(
                select(Product)
                .where(Product.status == "approved", Product.is_deleted.is_(False))
                .order_by(nullslast(Product.featured_until.desc()), Product.created_at.desc())
            )
        ).scalars().all()
    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    kb = build_pagination_kb(items, page, "browse_pg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")])
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=kb)
    await cb.answer()


async def browse_categories_for_user(target_msg: Message, uid: int):
    lang = await get_lang(uid)
    async with Session() as s:
        cats = (await s.execute(select(Category).order_by(Category.id.asc()))).scalars().all()
    if not cats:
        return await target_msg.answer(t(lang, "no_products"), reply_markup=back_kb(lang, "nav:buyer"))
    kb = [[InlineKeyboardButton(text=f"📂 {_cat_name(c, lang)}", callback_data=f"cat_browse:{c.id}:1")] for c in cats]
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")])
    await target_msg.answer(t(lang, "cats_browse_title"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@buyer_router.callback_query(F.data.startswith("cat_browse:"))
async def cat_browse(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    _, cid_str, page_str = cb.data.split(":")
    cid, page = int(cid_str), int(page_str)
    async with Session() as s:
        cat = (await s.execute(select(Category).where(Category.id == cid))).scalar_one_or_none()
        products = (
            await s.execute(
                select(Product)
                .where(Product.category_id == cid, Product.status == "approved", Product.is_deleted.is_(False))
                .order_by(nullslast(Product.featured_until.desc()), Product.created_at.desc())
            )
        ).scalars().all()
    if not products:
        return await cb.answer(t(lang, "no_products"), show_alert=True)
    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    kb = build_pagination_kb(items, page, f"cat_browse:{cid}", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:cats")])
    title = f"📂 <b>{esc(_cat_name(cat, lang))}</b>"
    try:
        await cb.message.edit_text(title, reply_markup=kb)
    except Exception:
        await cb.message.answer(title, reply_markup=kb)
    await cb.answer()


@buyer_router.message(F.text.in_([t(l, "btn_search") for l in LANGS]))
async def search_start(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.set_state(Search.query)
    await message.answer(t(lang, "search_prompt"), reply_markup=ReplyKeyboardRemove())


@buyer_router.message(Search.query)
async def search_exec(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    raw_q = (message.text or "").strip()
    if not raw_q:
        return await message.answer(t(lang, "search_prompt"))
    q = f"%{raw_q}%"
    async with Session() as s:
        products = (
            await s.execute(
                select(Product).where(
                    Product.status == "approved",
                    Product.is_deleted.is_(False),
                    or_(Product.title.ilike(q), Product.description.ilike(q)),
                )
            )
        ).scalars().all()
    await state.clear()
    if not products:
        return await message.answer(t(lang, "search_empty"), reply_markup=await get_main_kb(message.from_user.id, lang))
    await state.update_data(search_query=q)
    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    kb = build_pagination_kb(items, 1, "search_pg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")])
    await message.answer(t(lang, "search_results"), reply_markup=kb)
    await message.answer(t(lang, "main_menu"), reply_markup=await get_main_kb(message.from_user.id, lang))


@buyer_router.callback_query(F.data.startswith("search_pg:"))
async def search_pg(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[1])
    data = await state.get_data()
    q = data.get("search_query")
    if not q:
        return await cb.answer()
    async with Session() as s:
        products = (
            await s.execute(
                select(Product).where(
                    Product.status == "approved",
                    Product.is_deleted.is_(False),
                    or_(Product.title.ilike(q), Product.description.ilike(q)),
                )
            )
        ).scalars().all()
    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    kb = build_pagination_kb(items, page, "search_pg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")])
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=kb)
    await cb.answer()


@buyer_router.message(SearchStore.query)
async def search_store_exec(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    raw_q = (message.text or "").strip()
    await state.clear()
    if not raw_q:
        return await message.answer(t(lang, "store_search_empty"), reply_markup=await get_main_kb(message.from_user.id, lang))
    q = f"%{raw_q}%"
    async with Session() as s:
        stores = (
            await s.execute(
                select(Store).where(or_(Store.name.ilike(q), Store.bio.ilike(q), Store.custom_slug.ilike(q))).limit(50)
            )
        ).scalars().all()
    if not stores:
        return await message.answer(t(lang, "store_search_empty"), reply_markup=await get_main_kb(message.from_user.id, lang))
    items = [(f"🏪 {st.name} {t(lang, 'verified_badge') if st.verified else ''}".strip(), f"pubstore:{st.id}:1") for st in stores]
    kb = build_pagination_kb(items, 1, "top_store_pg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")])
    await message.answer(t(lang, "store_search_results"), reply_markup=kb)
    await message.answer(t(lang, "main_menu"), reply_markup=await get_main_kb(message.from_user.id, lang))


async def top_stores_for_user(target_msg: Message, uid: int):
    lang = await get_lang(uid)
    async with Session() as s:
        stores = (
            await s.execute(
                select(Store).outerjoin(StoreFollower).group_by(Store.id).order_by(func.count(StoreFollower.id).desc()).limit(50)
            )
        ).scalars().all()
    if not stores:
        return await target_msg.answer(t(lang, "top_stores_empty"), reply_markup=back_kb(lang, "nav:buyer"))
    items = [(f"🏪 {st.name} {t(lang, 'verified_badge') if st.verified else ''}".strip(), f"pubstore:{st.id}:1") for st in stores]
    kb = build_pagination_kb(items, 1, "top_store_pg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")])
    await target_msg.answer(t(lang, "top_stores_title"), reply_markup=kb)


@buyer_router.message(F.text.in_([t(l, "btn_top_stores") for l in LANGS]))
async def top_stores(message: Message):
    await top_stores_for_user(message, message.from_user.id)


@buyer_router.callback_query(F.data.startswith("top_store_pg:"))
async def top_stores_pg(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[1])
    async with Session() as s:
        stores = (
            await s.execute(
                select(Store).outerjoin(StoreFollower).group_by(Store.id).order_by(func.count(StoreFollower.id).desc()).limit(50)
            )
        ).scalars().all()
    items = [(f"🏪 {st.name} {t(lang, 'verified_badge') if st.verified else ''}".strip(), f"pubstore:{st.id}:1") for st in stores]
    kb = build_pagination_kb(items, page, "top_store_pg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")])
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("pubstore:"))
async def pubstore_view(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    _, store_id, page = cb.data.split(":")
    with suppress(Exception):
        await cb.message.delete()
    await show_public_store(cb.message, int(store_id), lang, int(page), viewer_id=cb.from_user.id)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("similar:"))
async def similar_prods(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    parts = cb.data.split(":")
    if len(parts) == 4:
        store_id, exclude_pid, page = int(parts[1]), int(parts[2]), int(parts[3])
    elif len(parts) == 3:
        store_id, exclude_pid, page = int(parts[1]), 0, int(parts[2])
    else:
        return await cb.answer()

    async with Session() as s:
        q = select(Product).where(Product.store_id == store_id, Product.status == "approved", Product.is_deleted.is_(False))
        if exclude_pid > 0:
            q = q.where(Product.id != exclude_pid)
        products = (await s.execute(q.limit(20))).scalars().all()

    if not products:
        return await cb.answer(t(lang, "no_products"), show_alert=True)

    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    back_callback = f"prod:{exclude_pid}" if exclude_pid > 0 else "nav:buyer"
    prefix = f"similar:{store_id}:{exclude_pid}" if exclude_pid > 0 else f"similar:{store_id}"
    kb = build_pagination_kb(items, page, prefix, lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=back_callback)])
    await cb.message.answer(t(lang, "all_products"), reply_markup=kb)
    await cb.answer()


# ─── Product View & Contact ───

@buyer_router.callback_query(F.data.startswith("prod:"))
async def prod_view(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    pid = int(cb.data.split(":")[1])
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid, Product.is_deleted.is_(False)))).scalar_one_or_none()
        if not p:
            return await cb.answer("Not found", show_alert=True)
        p.views += 1
        await s.commit()
        store = (await s.execute(select(Store).where(Store.id == p.store_id))).scalar_one_or_none()
        rating = await get_store_rating(store.id, s) if store else "—"
        is_fav = (
            await s.execute(select(Favorite).where(Favorite.user_tg_id == cb.from_user.id, Favorite.product_id == pid))
        ).scalar_one_or_none()
        latest_rev = (
            await s.execute(
                select(Review).where(Review.store_id == p.store_id, Review.comment != "").order_by(Review.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()

    stock_warn = t(lang, "out_of_stock_warn") if p.is_out_of_stock else ""
    stock_left = t(lang, "stock_left", qty=p.stock_quantity) if not p.is_out_of_stock else ""
    rev_text = t(lang, "latest_review", comment=esc(latest_rev.comment)) if latest_rev else ""
    vars_text = t(lang, "vars_list", vars=esc(p.variations)) if p.variations else ""
    current_price = _current_price(p)
    flash_text = ""
    now = utcnow()
    if p.flash_sale_price and p.flash_sale_ends_at and p.flash_sale_ends_at > now:
        tl = p.flash_sale_ends_at - now
        total_hours = int(tl.total_seconds() // 3600)
        minutes = int((tl.total_seconds() % 3600) // 60)
        flash_text = t(lang, "flash_sale_warn", old_price=f"{p.price:g} {esc(p.currency)}", time=f"{total_hours}س {minutes}د")
    badge = t(lang, "verified_badge") if store and store.verified else ""
    store_name = f"{esc(store.name)} {badge}".strip() if store else "-"
    caption = t(
        lang,
        "product",
        title=esc(p.title),
        desc=esc((p.description or "")[:700]),
        price=f"{current_price:g}",
        currency=esc(p.currency),
        delivery=f"{p.delivery_fee:g} {esc(p.currency)}",
        store=store_name,
        rating=rating,
        stock=stock_warn + stock_left,
        review=rev_text,
        vars=vars_text,
        flash=flash_text,
    )

    btns = []
    if not p.is_out_of_stock:
        btns.append([InlineKeyboardButton(text=t(lang, "btn_add_cart"), callback_data=f"cart_add:{p.id}")])
        btns.append([InlineKeyboardButton(text=t(lang, "btn_order"), callback_data=f"order_start:{p.id}")])
    else:
        btns.append([InlineKeyboardButton(text=t(lang, "btn_restock"), callback_data=f"restock:{p.id}")])
    if store:
        btns.append([InlineKeyboardButton(text=t(lang, "btn_contact"), callback_data=f"contact_menu:{store.id}")])
    fav_text = t(lang, "btn_remove_fav") if is_fav else t(lang, "btn_add_fav")
    fav_cb = f"fav_rm:{pid}" if is_fav else f"fav_add:{pid}"
    btns.append([
        InlineKeyboardButton(text=fav_text, callback_data=fav_cb),
        InlineKeyboardButton(text=t(lang, "btn_report_prod"), callback_data=f"rep_prod:{pid}"),
    ])
    btns.append([InlineKeyboardButton(text=t(lang, "btn_similar"), callback_data=f"similar:{p.store_id}:{p.id}:1")])
    if store:
        btns.append([InlineKeyboardButton(text=t(lang, "btn_rate"), callback_data=f"rate_store:{store.id}")])
    btns.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"pubstore:{p.store_id}:1")])
    kb = InlineKeyboardMarkup(inline_keyboard=btns)

    photos = [ph for ph in (p.photo_file_id, p.photo_file_id_2, p.photo_file_id_3) if ph]
    try:
        if len(photos) == 1:
            await cb.message.answer_photo(photo=photos[0], caption=caption[:1024], reply_markup=kb)
        elif len(photos) > 1:
            media = [InputMediaPhoto(media=ph, caption=caption[:1024] if i == 0 else None) for i, ph in enumerate(photos)]
            await cb.message.answer_media_group(media=media)
            await cb.message.answer("اختر الإجراء:", reply_markup=kb)
        else:
            await cb.message.answer(caption, reply_markup=kb)
    except Exception as e:
        logger.error(f"Failed to send product photos: {e}")
        with suppress(Exception):
            await cb.message.answer(caption, reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("contact_menu:"))
async def contact_menu(cb: CallbackQuery):
    store_id = int(cb.data.split(":")[1])
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        store = (await s.execute(select(Store).where(Store.id == store_id))).scalar_one_or_none()
    if not store:
        return await cb.answer("Error", show_alert=True)
    kb = []
    if store.contact:
        url = store.contact if store.contact.startswith("http") else f"https://t.me/{store.contact.lstrip('@')}"
        kb.append([InlineKeyboardButton(text=t(lang, "contact_telegram"), url=url)])
    if store.contact_phone:
        kb.append([InlineKeyboardButton(text=t(lang, "contact_phone"), url=f"tel:{store.contact_phone}")])
    if store.contact_whatsapp:
        num = re.sub(r"[^\d]", "", store.contact_whatsapp)
        if num:
            kb.append([InlineKeyboardButton(text=t(lang, "contact_whatsapp"), url=f"https://wa.me/{num}")])
    if store.contact_instagram:
        url = store.contact_instagram if store.contact_instagram.startswith("http") else f"https://instagram.com/{store.contact_instagram.lstrip('@')}"
        kb.append([InlineKeyboardButton(text=t(lang, "contact_instagram"), url=url)])
    if not kb:
        return await cb.answer(t(lang, "contact_not_avail"), show_alert=True)
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"pubstore:{store_id}:1")])
    await cb.message.answer(t(lang, "contact_methods_menu"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


# ─── Favorites, Follow, Ratings & Reports ───

@buyer_router.callback_query(F.data.startswith("fav_add:"))
async def fav_add(cb: CallbackQuery):
    pid = int(cb.data.split(":")[1])
    lang = await get_lang(cb.from_user.id)
    try:
        async with Session() as s:
            s.add(Favorite(user_tg_id=cb.from_user.id, product_id=pid))
            await s.commit()
    except IntegrityError:
        pass
    await cb.answer(t(lang, "fav_added"))


@buyer_router.callback_query(F.data.startswith("fav_rm:"))
async def fav_rm(cb: CallbackQuery):
    pid = int(cb.data.split(":")[1])
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        await s.execute(delete(Favorite).where(Favorite.user_tg_id == cb.from_user.id, Favorite.product_id == pid))
        await s.commit()
    await cb.answer(t(lang, "fav_removed"))


async def my_favs_for_user(target_msg: Message, uid: int):
    lang = await get_lang(uid)
    async with Session() as s:
        favs = (await s.execute(select(Favorite.product_id).where(Favorite.user_tg_id == uid))).scalars().all()
        if not favs:
            return await target_msg.answer(t(lang, "fav_empty"), reply_markup=back_kb(lang, "nav:account"))
        products = (
            await s.execute(
                select(Product).where(Product.id.in_(favs), Product.status == "approved", Product.is_deleted.is_(False))
            )
        ).scalars().all()
    if not products:
        return await target_msg.answer(t(lang, "fav_empty"), reply_markup=back_kb(lang, "nav:account"))
    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    kb = build_pagination_kb(items, 1, "favpg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:account")])
    await target_msg.answer(t(lang, "my_favorites"), reply_markup=kb)


@buyer_router.message(F.text.in_([t(l, "btn_favorites") for l in LANGS]))
async def my_favs(message: Message):
    await my_favs_for_user(message, message.from_user.id)


@buyer_router.callback_query(F.data.startswith("favpg:"))
async def fav_pg(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[1])
    async with Session() as s:
        favs = (await s.execute(select(Favorite.product_id).where(Favorite.user_tg_id == cb.from_user.id))).scalars().all()
        products = (
            await s.execute(
                select(Product).where(Product.id.in_(favs), Product.status == "approved", Product.is_deleted.is_(False))
            )
        ).scalars().all()
    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    kb = build_pagination_kb(items, page, "favpg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:account")])
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("fol_add:"))
async def fol_add(cb: CallbackQuery):
    store_id = int(cb.data.split(":")[1])
    lang = await get_lang(cb.from_user.id)
    try:
        async with Session() as s:
            s.add(StoreFollower(store_id=store_id, user_tg_id=cb.from_user.id))
            await s.commit()
    except IntegrityError:
        pass
    await cb.answer(t(lang, "followed"), show_alert=True)


@buyer_router.callback_query(F.data.startswith("fol_rm:"))
async def fol_rm(cb: CallbackQuery):
    store_id = int(cb.data.split(":")[1])
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        await s.execute(delete(StoreFollower).where(StoreFollower.store_id == store_id, StoreFollower.user_tg_id == cb.from_user.id))
        await s.commit()
    await cb.answer(t(lang, "unfollowed"), show_alert=True)


@buyer_router.callback_query(F.data.startswith("rate_store:"))
async def rate_store(cb: CallbackQuery):
    store_id = int(cb.data.split(":")[1])
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        existing = (
            await s.execute(select(Review).where(Review.store_id == store_id, Review.buyer_tg_id == cb.from_user.id))
        ).scalar_one_or_none()
    if existing:
        return await cb.answer(t(lang, "rating_invalid"), show_alert=True)
    buttons = [[InlineKeyboardButton(text=f"{i} ⭐", callback_data=f"do_rate:{store_id}:{i}") for i in range(1, 6)]]
    await cb.message.answer(t(lang, "rating_prompt"), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("do_rate:"))
async def do_rate(cb: CallbackQuery, state: FSMContext):
    _, store_id, rating = cb.data.split(":")
    r_int = int(rating)
    if not (1 <= r_int <= 5):
        return await cb.answer()
    await state.update_data(rev_store_id=int(store_id), rev_rating=r_int)
    await state.set_state(ReviewFSM.comment)
    lang = await get_lang(cb.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_comment"), callback_data="skip_comment")]])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "rating_comment_prompt"), reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data == "skip_comment")
async def skip_comment(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    data = await state.get_data()
    if data.get("rev_store_id"):
        try:
            async with Session() as s:
                s.add(Review(store_id=data["rev_store_id"], buyer_tg_id=cb.from_user.id, rating=data["rev_rating"], comment=""))
                await s.commit()
        except IntegrityError:
            pass
    await state.clear()
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "rating_thanks"))
    await cb.answer()


@buyer_router.message(ReviewFSM.comment)
async def review_comment(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    if data.get("rev_store_id"):
        try:
            async with Session() as s:
                s.add(
                    Review(
                        store_id=data["rev_store_id"],
                        buyer_tg_id=message.from_user.id,
                        rating=data["rev_rating"],
                        comment=(message.text or "").strip()[:500],
                    )
                )
                await s.commit()
        except IntegrityError:
            pass
    await state.clear()
    await message.answer(t(lang, "rating_thanks"), reply_markup=await get_main_kb(message.from_user.id, lang))


@buyer_router.callback_query(F.data.startswith("rep_prod:"))
async def report_prod_start(cb: CallbackQuery, state: FSMContext):
    pid = int(cb.data.split(":")[1])
    await state.update_data(target_type="product", target_id=pid)
    await state.set_state(ReportFSM.reason)
    await cb.message.answer(t(await get_lang(cb.from_user.id), "report_prompt"))
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("rep_store:"))
async def report_store_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    await state.update_data(target_type="store", target_id=sid)
    await state.set_state(ReportFSM.reason)
    await cb.message.answer(t(await get_lang(cb.from_user.id), "report_prompt"))
    await cb.answer()


@buyer_router.message(ReportFSM.reason)
async def report_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    reason = (message.text or "").strip()[:MAX_REPORT_REASON_LEN]
    if not reason:
        return await message.answer(t(lang, "report_prompt"))
    async with Session() as s:
        s.add(Report(reporter_tg_id=message.from_user.id, target_type=data["target_type"], target_id=data["target_id"], reason=reason))
        await s.commit()
    await state.clear()
    await message.answer(t(lang, "report_sent"), reply_markup=await get_main_kb(message.from_user.id, lang))
    link = f"https://t.me/{BOT_USERNAME}?start=store_{data['target_id']}" if data["target_type"] == "store" else f"منتج #{data['target_id']}"
    await notify_admins(message.bot, t("ar", "report_new_admin", type=esc(data["target_type"]), reason=esc(reason), link=esc(link)))


# ════════════════════════════════════════════════════════════════════
# 7. SELLER SECTION (seller_handlers)
# ════════════════════════════════════════════════════════════════════

@seller_router.message(F.text.in_([t(l, "btn_seller_section") for l in LANGS]))
async def seller_section_menu(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    stores = await get_stores_by_owner(message.from_user.id)
    if not stores:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_become_seller"), callback_data="nav:become_seller")],
            [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")],
        ])
        await message.answer(t(lang, "seller_menu_title"), reply_markup=kb)
        return
    if len(stores) == 1:
        await send_store_dashboard(message, stores[0].id, lang)
        return
    kb = []
    for st in stores:
        badge = t(lang, "verified_badge") if st.verified else ""
        kb.append([InlineKeyboardButton(text=f"🏪 {st.name} {badge}".strip(), callback_data=f"mngstore:{st.id}")])
    if len(stores) < MAX_STORES_PER_USER:
        kb.append([InlineKeyboardButton(text=t(lang, "add_new_store"), callback_data="nav:become_seller")])
    else:
        kb.append([InlineKeyboardButton(text=t(lang, "max_stores_reached"), callback_data="ignore")])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")])
    await message.answer(t(lang, "seller_menu_title") + t(lang, "choose_store"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@seller_router.callback_query(F.data.startswith("mngstore:"))
async def manage_store_select(cb: CallbackQuery):
    store_id = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, store_id):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    with suppress(Exception):
        await cb.message.delete()
    await send_store_dashboard(cb.message, store_id, lang)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_guide:"))
async def store_guide(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    kb = back_kb(lang, f"mngstore:{sid}")
    try:
        await cb.message.edit_text(t(lang, "seller_guide_text"), reply_markup=kb)
    except Exception:
        await cb.message.answer(t(lang, "seller_guide_text"), reply_markup=kb)
    await cb.answer()


@seller_router.message(CreateStore.name)
async def create_store_name(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "store_create_prompt"))
    stores = await get_stores_by_owner(message.from_user.id)
    if len(stores) >= MAX_STORES_PER_USER:
        await state.clear()
        return await message.answer("❌ وصلت للحد الأقصى (3 متاجر).", reply_markup=await get_main_kb(message.from_user.id, lang))
    async with Session() as s:
        s.add(Store(owner_tg_id=message.from_user.id, name=message.text.strip()[:MAX_STORE_NAME_LEN], contact=message.from_user.username or ""))
        u = await ensure_user(s, message.from_user.id, lang)
        u.role = "seller"
        await s.commit()
    await state.clear()
    await message.answer(t(lang, "store_created"), reply_markup=await get_main_kb(message.from_user.id, lang))


# ─── Store Settings ───

@seller_router.callback_query(F.data.startswith("st_settings:"))
async def store_settings(cb: CallbackQuery):
    store_id = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, store_id):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_edit_name"), callback_data=f"st_setname:{store_id}")],
        [InlineKeyboardButton(text=t(lang, "btn_edit_bio"), callback_data=f"st_setbio:{store_id}")],
        [InlineKeyboardButton(text=t(lang, "btn_edit_logo"), callback_data=f"st_setlogo:{store_id}")],
        [InlineKeyboardButton(text=t(lang, "btn_edit_contacts"), callback_data=f"st_setcontacts:{store_id}")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{store_id}")],
    ])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "settings_menu"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_setname:"))
async def store_setname_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(edit_store_id=sid)
    await state.set_state(EditStoreFSM.name)
    await cb.message.answer(t(await get_lang(cb.from_user.id), "enter_new_name"))
    await cb.answer()


@seller_router.message(EditStoreFSM.name)
async def store_setname_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "enter_new_name"))
    data = await state.get_data()
    sid = data.get("edit_store_id")
    if sid and await is_store_owner(message.from_user.id, sid):
        async with Session() as s:
            store = (await s.execute(select(Store).where(Store.id == sid))).scalar_one_or_none()
            if store:
                store.name = message.text.strip()[:MAX_STORE_NAME_LEN]
                await s.commit()
    await message.answer(t(lang, "settings_updated"), reply_markup=await get_main_kb(message.from_user.id, lang))
    await state.clear()


@seller_router.callback_query(F.data.startswith("st_setbio:"))
async def store_setbio_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(edit_store_id=sid)
    await state.set_state(EditStoreFSM.bio)
    await cb.message.answer(t(await get_lang(cb.from_user.id), "enter_new_bio"))
    await cb.answer()


@seller_router.message(EditStoreFSM.bio)
async def store_setbio_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "enter_new_bio"))
    data = await state.get_data()
    sid = data.get("edit_store_id")
    if sid and await is_store_owner(message.from_user.id, sid):
        async with Session() as s:
            store = (await s.execute(select(Store).where(Store.id == sid))).scalar_one_or_none()
            if store:
                store.bio = message.text.strip()[:MAX_STORE_BIO_LEN]
                await s.commit()
    await message.answer(t(lang, "settings_updated"), reply_markup=await get_main_kb(message.from_user.id, lang))
    await state.clear()


@seller_router.callback_query(F.data.startswith("st_setlogo:"))
async def store_setlogo_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(edit_store_id=sid)
    await state.set_state(EditStoreFSM.logo)
    await cb.message.answer(t(await get_lang(cb.from_user.id), "send_logo"))
    await cb.answer()


@seller_router.message(EditStoreFSM.logo, F.photo)
async def store_setlogo_save(message: Message, state: FSMContext):
    data = await state.get_data()
    sid = data.get("edit_store_id")
    if sid and await is_store_owner(message.from_user.id, sid):
        async with Session() as s:
            store = (await s.execute(select(Store).where(Store.id == sid))).scalar_one_or_none()
            if store:
                store.logo_file_id = message.photo[-1].file_id
                await s.commit()
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "settings_updated"), reply_markup=await get_main_kb(message.from_user.id, lang))
    await state.clear()


@seller_router.message(EditStoreFSM.logo, ~F.photo)
async def store_setlogo_invalid(message: Message):
    await message.answer(t(await get_lang(message.from_user.id), "send_logo"))


@seller_router.callback_query(F.data.startswith("st_setcontacts:"))
async def store_setcontacts_menu(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "contact_telegram"), callback_data=f"st_setcontact_tg:{sid}")],
        [InlineKeyboardButton(text=t(lang, "contact_phone"), callback_data=f"st_setcontact_phone:{sid}")],
        [InlineKeyboardButton(text=t(lang, "contact_whatsapp"), callback_data=f"st_setcontact_wa:{sid}")],
        [InlineKeyboardButton(text=t(lang, "contact_instagram"), callback_data=f"st_setcontact_insta:{sid}")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"st_settings:{sid}")],
    ])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "contacts_menu"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_setcontact_"))
async def store_setcontact_start(cb: CallbackQuery, state: FSMContext):
    # Fixed: removeprefix("st_setcontact_") properly extracts "tg:5" instead of "setcontact_tg:5"
    field_raw = cb.data.removeprefix("st_setcontact_")
    field, sid_str = field_raw.split(":", 1)
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(edit_store_id=sid)
    lang = await get_lang(cb.from_user.id)
    if field == "tg":
        await state.set_state(EditStoreFSM.contact_tg)
        await cb.message.answer(t(lang, "enter_contact_tg"))
    elif field == "phone":
        await state.set_state(EditStoreFSM.contact_phone)
        await cb.message.answer(t(lang, "enter_contact_phone"))
    elif field == "wa":
        await state.set_state(EditStoreFSM.contact_whatsapp)
        await cb.message.answer(t(lang, "enter_contact_whatsapp"))
    elif field == "insta":
        await state.set_state(EditStoreFSM.contact_insta)
        await cb.message.answer(t(lang, "enter_contact_insta"))
    await cb.answer()


async def _save_store_contact(message: Message, state: FSMContext, attr: str, transform=None):
    data = await state.get_data()
    sid = data.get("edit_store_id")
    if sid and await is_store_owner(message.from_user.id, sid):
        val = (message.text or "").strip()[:MAX_STORE_CONTACT_LEN]
        if transform:
            val = transform(val)
        async with Session() as s:
            store = (await s.execute(select(Store).where(Store.id == sid))).scalar_one_or_none()
            if store:
                setattr(store, attr, val)
                await s.commit()
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "settings_updated"), reply_markup=await get_main_kb(message.from_user.id, lang))
    await state.clear()


@seller_router.message(EditStoreFSM.contact_tg)
async def save_contact_tg(message: Message, state: FSMContext):
    await _save_store_contact(message, state, "contact", transform=lambda v: v.replace("https://t.me/", "").lstrip("@"))


@seller_router.message(EditStoreFSM.contact_phone)
async def save_contact_phone(message: Message, state: FSMContext):
    await _save_store_contact(message, state, "contact_phone")


@seller_router.message(EditStoreFSM.contact_whatsapp)
async def save_contact_wa(message: Message, state: FSMContext):
    await _save_store_contact(message, state, "contact_whatsapp")


@seller_router.message(EditStoreFSM.contact_insta)
async def save_contact_insta(message: Message, state: FSMContext):
    await _save_store_contact(message, state, "contact_instagram", transform=lambda v: v.replace("https://instagram.com/", "").lstrip("@"))


# ─── Share Store ───

@seller_router.callback_query(F.data.startswith("st_share:"))
async def share_menu(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_share_post"), callback_data=f"st_share_post:{sid}")],
        [InlineKeyboardButton(text=t(lang, "btn_share_qr"), callback_data=f"st_share_qr:{sid}")],
        [InlineKeyboardButton(text=t(lang, "btn_custom_slug"), callback_data=f"st_set_slug:{sid}")],
        [InlineKeyboardButton(text=t(lang, "btn_custom_text"), callback_data=f"st_set_text:{sid}")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}")],
    ])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "share_menu"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_share_post:"))
async def share_post(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        store = (await s.execute(select(Store).where(Store.id == sid))).scalar_one_or_none()
        if not store:
            return await cb.answer("Not found")
        rating = await get_store_rating(store.id, s)
        fc = (await s.execute(select(func.count(StoreFollower.id)).where(StoreFollower.store_id == store.id))).scalar()
    slug = store.custom_slug if store.custom_slug else str(store.id)
    share_url = f"https://t.me/{BOT_USERNAME}?start=store_{slug}"
    text = (
        esc(store.share_text)
        if store.share_text
        else t(lang, "inline_share_text", name=esc(store.name), store_bio=esc(store.bio or "لا يوجد وصف."), rating=rating, followers=fc)
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "inline_share_btn"), url=share_url)]])
    if store.logo_file_id:
        await cb.message.answer_photo(photo=store.logo_file_id, caption=text[:1024], reply_markup=kb)
    else:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_share_qr:"))
async def share_qr(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        store = (await s.execute(select(Store).where(Store.id == sid))).scalar_one_or_none()
    if not store:
        return await cb.answer("Not found")
    slug = store.custom_slug if store.custom_slug else str(store.id)
    share_url = f"https://t.me/{BOT_USERNAME}?start=store_{slug}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(share_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, "PNG")
    bio.seek(0)
    photo = BufferedInputFile(bio.read(), filename=f"qr_{store.id}.png")
    await cb.message.answer_photo(photo=photo, caption=t(lang, "qr_caption", name=esc(store.name)))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_set_slug:"))
async def set_custom_slug_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(edit_store_id=sid)
    await state.set_state(EditStoreFSM.custom_slug)
    await cb.message.answer(t(await get_lang(cb.from_user.id), "enter_custom_slug"))
    await cb.answer()


@seller_router.message(EditStoreFSM.custom_slug)
async def set_custom_slug_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    new_slug = (message.text or "").strip().lower()
    # Fixed: allow letters, digits, underscore (3-50 chars) and forbid digits-only to prevent Store.id collision
    if not _SLUG_RE.match(new_slug) or new_slug.isdigit():
        return await message.answer("❌ استخدم حروفاً إنجليزية وأرقاماً و _ فقط (3-50 حرفاً)، ولا يكن أرقاماً فقط.")
    data = await state.get_data()
    sid = data.get("edit_store_id")
    if not sid or not await is_store_owner(message.from_user.id, sid):
        await state.clear()
        return await message.answer("⛔ غير مصرح.")
    async with Session() as s:
        existing = (await s.execute(select(Store).where(Store.custom_slug == new_slug, Store.id != sid))).scalar_one_or_none()
        if existing:
            return await message.answer(t(lang, "slug_taken"))
        store = (await s.execute(select(Store).where(Store.id == sid))).scalar_one_or_none()
        if store:
            store.custom_slug = new_slug
            await s.commit()
    await state.clear()
    await message.answer(
        t(lang, "slug_success", bot_username=BOT_USERNAME, slug=new_slug),
        reply_markup=await get_main_kb(message.from_user.id, lang),
    )


@seller_router.callback_query(F.data.startswith("st_set_text:"))
async def set_share_text_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(edit_store_id=sid)
    await state.set_state(EditStoreFSM.custom_share_text)
    await cb.message.answer(t(await get_lang(cb.from_user.id), "enter_custom_share_text"))
    await cb.answer()


@seller_router.message(EditStoreFSM.custom_share_text)
async def set_share_text_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    sid = data.get("edit_store_id")
    if sid and await is_store_owner(message.from_user.id, sid):
        async with Session() as s:
            store = (await s.execute(select(Store).where(Store.id == sid))).scalar_one_or_none()
            if store:
                store.share_text = (message.text or "").strip()[:MAX_STORE_SHARE_TEXT_LEN]
                await s.commit()
    await state.clear()
    await message.answer(t(lang, "share_text_success"), reply_markup=await get_main_kb(message.from_user.id, lang))


# ─── Manage Products ───

@seller_router.callback_query(F.data.startswith("st_list:"))
async def store_list(cb: CallbackQuery):
    _, sid, page = cb.data.split(":")
    sid, page = int(sid), int(page)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        products = (
            await s.execute(
                select(Product)
                .where(Product.store_id == sid, Product.is_deleted.is_(False))
                .order_by(Product.created_at.desc())
            )
        ).scalars().all()
    if not products:
        with suppress(Exception):
            await cb.message.edit_text(
                t(lang, "my_products_empty"),
                reply_markup=back_kb(lang, f"mngstore:{sid}"),
            )
        return await cb.answer()
    icons = {"approved": "✅", "pending": "⏳", "rejected": "❌"}
    now = utcnow()
    items = []
    for p in products:
        flash = "🔥 " if (p.flash_sale_price and p.flash_sale_ends_at and p.flash_sale_ends_at > now) else ""
        items.append((f"{icons.get(p.status, '?')} {flash}{p.title} — {p.price:g} {p.currency}", f"mng:{p.id}"))
    kb = build_pagination_kb(items, page, f"st_list:{sid}", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}")])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "my_products_list"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("mng:"))
async def manage_product(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    pid = int(cb.data.split(":")[1])
    p, _st, err = await _get_owned_product(cb.from_user.id, pid)
    if err == "not_found":
        return await cb.answer("Not found", show_alert=True)
    if err == "unauthorized":
        return await cb.answer("⛔ غير مصرح.", show_alert=True)

    if p.status == "pending":
        text = (
            f"⏳ <b>{esc(p.title)}</b>\n\n"
            "حالة المنتج: <b>قيد المراجعة من الإدارة</b>.\n"
            "لا يمكن تعديل المنتج حتى يتم البت فيه.\n\n"
            f"💵 السعر: {p.price:g} {esc(p.currency)}\n"
            f"📦 الكمية: {p.stock_quantity}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_delete_prod"), callback_data=f"mngdel:{pid}")],
            [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{p.store_id}")],
        ])
        with suppress(Exception):
            await cb.message.edit_text(text, reply_markup=kb)
        return await cb.answer()

    if p.status == "rejected":
        text = (
            f"❌ <b>{esc(p.title)}</b>\n\n"
            f"<b>سبب الرفض:</b> {esc(p.reject_reason or 'غير محدد')}\n\n"
            f"💵 السعر: {p.price:g} {esc(p.currency)}\n"
            f"📦 الكمية: {p.stock_quantity}\n\n"
            "يمكنك تعديل المنتج ثم إعادة إرساله للمراجعة."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 إعادة إرسال للمراجعة", callback_data=f"mngresubmit:{pid}")],
            [InlineKeyboardButton(text=t(lang, "btn_edit_price"), callback_data=f"mngprice:{pid}")],
            [InlineKeyboardButton(text=t(lang, "btn_edit_desc"), callback_data=f"mngdesc:{pid}")],
            [InlineKeyboardButton(text=t(lang, "btn_edit_stock"), callback_data=f"mngstock_edit:{pid}")],
            [InlineKeyboardButton(text=t(lang, "btn_delete_prod"), callback_data=f"mngdel:{pid}")],
            [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{p.store_id}")],
        ])
        with suppress(Exception):
            await cb.message.edit_text(text, reply_markup=kb)
        return await cb.answer()

    stock_text = "❌ نفدت" if p.is_out_of_stock else f"✅ متوفر ({p.stock_quantity})"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_edit_price"), callback_data=f"mngprice:{pid}")],
        [InlineKeyboardButton(text=t(lang, "btn_edit_desc"), callback_data=f"mngdesc:{pid}")],
        [InlineKeyboardButton(text=t(lang, "btn_edit_stock"), callback_data=f"mngstock_edit:{pid}")],
        [InlineKeyboardButton(text=f"{t(lang, 'btn_toggle_stock')} ({stock_text})", callback_data=f"mngstock:{pid}")],
        [InlineKeyboardButton(text=t(lang, "btn_delete_prod"), callback_data=f"mngdel:{pid}")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{p.store_id}")],
    ])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "manage_product", title=esc(p.title)), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("mngresubmit:"))
async def resubmit_product(cb: CallbackQuery):
    pid = int(cb.data.split(":")[1])
    p, _st, err = await _get_owned_product(cb.from_user.id, pid)
    if err:
        return await cb.answer("⛔ غير مصرح." if err == "unauthorized" else "Not found", show_alert=True)
    if p.status != "rejected":
        return await cb.answer("المنتج ليس في حالة رفض.", show_alert=True)

    async with Session() as s:
        p_db = (await s.execute(select(Product).where(Product.id == pid))).scalar_one()
        p_db.status = "pending"
        p_db.reject_reason = ""
        await s.commit()
        ptitle, pphoto, price_str = p_db.title, p_db.photo_file_id, f"{p_db.price:g} {p_db.currency}"
        stock, delivery, vars_ = p_db.stock_quantity, p_db.delivery_fee, p_db.variations or "-"

    await cb.answer("✅ تم إعادة إرسال المنتج للمراجعة.", show_alert=True)
    with suppress(Exception):
        await cb.message.edit_text(f"✅ تم إعادة إرسال <b>{esc(ptitle)}</b> للمراجعة.\n\nسيتم إعلامك بالنتيجة فوراً.")

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Approve", callback_data=f"admin:approve:{pid}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"admin:reject:{pid}"),
    ]])
    caption = (
        f"📥 <b>إعادة إرسال منتج (سابقاً مرفوض)</b>\n"
        f"<b>{esc(ptitle)}</b>\n"
        f"الكمية: {stock}\nالتوصيل: {delivery:g}\nالخيارات: {esc(vars_)}\n"
        f"السعر: {esc(price_str)}"
    )
    await notify_admins(cb.bot, caption, reply_markup=admin_kb, photo=pphoto)


@seller_router.callback_query(F.data.startswith("mngprice:"))
async def edit_price_start(cb: CallbackQuery, state: FSMContext):
    pid = int(cb.data.split(":")[1])
    if not await _guard_edit(cb, pid):
        return
    await state.update_data(edit_pid=pid)
    await state.set_state(EditProductFSM.price)
    await cb.message.answer(t(await get_lang(cb.from_user.id), "enter_new_price"))
    await cb.answer()


@seller_router.message(EditProductFSM.price)
async def edit_price_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    price = _parse_positive_float(message.text or "", allow_zero=False)
    if price is None:
        return await message.answer(t(lang, "enter_new_price"))
    data = await state.get_data()
    pid = data.get("edit_pid")
    if pid and await is_product_owner(message.from_user.id, pid):
        async with Session() as s:
            p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
            if p and p.status != "pending":
                p.price = price
                if p.flash_sale_price and p.flash_sale_price >= price:
                    p.flash_sale_price = None
                    p.flash_sale_ends_at = None
                await s.commit()
    await message.answer(t(lang, "prod_updated"), reply_markup=await get_main_kb(message.from_user.id, lang))
    await state.clear()


@seller_router.callback_query(F.data.startswith("mngdesc:"))
async def edit_desc_start(cb: CallbackQuery, state: FSMContext):
    pid = int(cb.data.split(":")[1])
    if not await _guard_edit(cb, pid):
        return
    await state.update_data(edit_pid=pid)
    await state.set_state(EditProductFSM.desc)
    await cb.message.answer(t(await get_lang(cb.from_user.id), "enter_new_desc"))
    await cb.answer()


@seller_router.message(EditProductFSM.desc)
async def edit_desc_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "enter_new_desc"))
    data = await state.get_data()
    pid = data.get("edit_pid")
    if pid and await is_product_owner(message.from_user.id, pid):
        async with Session() as s:
            p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
            if p and p.status != "pending":
                p.description = message.text.strip()[:MAX_PRODUCT_DESC_LEN]
                await s.commit()
    await message.answer(t(lang, "prod_updated"), reply_markup=await get_main_kb(message.from_user.id, lang))
    await state.clear()


@seller_router.callback_query(F.data.startswith("mngstock_edit:"))
async def edit_stock_start(cb: CallbackQuery, state: FSMContext):
    pid = int(cb.data.split(":")[1])
    if not await _guard_edit(cb, pid):
        return
    await state.update_data(edit_pid=pid)
    await state.set_state(EditProductFSM.stock)
    await cb.message.answer(t(await get_lang(cb.from_user.id), "enter_new_stock"))
    await cb.answer()


async def _notify_restock_alerts(bot: Bot, s, p: Product):
    store = (await s.execute(select(Store).where(Store.id == p.store_id))).scalar_one_or_none()
    alerts = (await s.execute(select(RestockAlert).where(RestockAlert.product_id == p.id))).scalars().all()
    for alert in alerts:
        try:
            alang = await get_lang(alert.user_tg_id)
            await bot.send_message(
                alert.user_tg_id,
                t(
                    alang,
                    "restock_notify",
                    title=esc(p.title),
                    store=esc(store.name if store else "-"),
                    price=f"{_current_price(p):g} {esc(p.currency)}",
                ),
            )
            await s.delete(alert)
            await asyncio.sleep(0.05)
        except Exception:
            pass


@seller_router.message(EditProductFSM.stock)
async def edit_stock_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    qty = _parse_int_range(message.text or "", 0)
    if qty is None:
        return await message.answer(t(lang, "enter_new_stock"))
    data = await state.get_data()
    pid = data.get("edit_pid")
    if not pid or not await is_product_owner(message.from_user.id, pid):
        await state.clear()
        return await message.answer("⛔ غير مصرح.")
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
        if not p or p.status == "pending":
            await state.clear()
            return await message.answer("⏳ المنتج قيد المراجعة، لا يمكن التعديل.")
        was_out = p.is_out_of_stock
        p.stock_quantity = qty
        p.is_out_of_stock = (qty == 0)
        await s.commit()
        if was_out and qty > 0:
            await _notify_restock_alerts(message.bot, s, p)
            await s.commit()
    await message.answer(t(lang, "prod_updated"), reply_markup=await get_main_kb(message.from_user.id, lang))
    await state.clear()


@seller_router.callback_query(F.data.startswith("mngstock:"))
async def toggle_stock(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    pid = int(cb.data.split(":")[1])
    if not await _guard_edit(cb, pid):
        return
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one()
        was_out = p.is_out_of_stock
        p.is_out_of_stock = not p.is_out_of_stock
        if p.is_out_of_stock:
            p.stock_quantity = 0
        elif p.stock_quantity <= 0:
            p.stock_quantity = 1
        await s.commit()
        is_out = p.is_out_of_stock
        if was_out and not is_out:
            await _notify_restock_alerts(cb.bot, s, p)
            await s.commit()
    await cb.answer(t(lang, "stock_out") if is_out else t(lang, "stock_in"), show_alert=True)
    await manage_product(cb)


@seller_router.callback_query(F.data.startswith("mngdel:"))
async def delete_product_start(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    pid = int(cb.data.split(":")[1])
    if not await is_product_owner(cb.from_user.id, pid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_yes_delete"), callback_data=f"mngdel_yes:{pid}")],
        [InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data=f"mng:{pid}")],
    ])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "confirm_delete"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("mngdel_yes:"))
async def delete_product_conf(cb: CallbackQuery):
    pid = int(cb.data.split(":")[1])
    if not await is_product_owner(cb.from_user.id, pid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    # Soft-delete so existing Orders keep working cleanly; remove from active carts/favorites/alerts
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
        if p:
            p.is_deleted = True
            p.is_out_of_stock = True
            await s.execute(delete(CartItem).where(CartItem.product_id == pid))
            await s.execute(delete(Favorite).where(Favorite.product_id == pid))
            await s.execute(delete(RestockAlert).where(RestockAlert.product_id == pid))
            await s.commit()
    lang = await get_lang(cb.from_user.id)
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "prod_deleted"))
    await cb.answer()


# ─── Add Product (with Category selection) ───

@seller_router.callback_query(F.data.startswith("st_add:"))
async def add_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    await state.clear()
    await state.update_data(active_store_id=sid, category_id=None, category_name="-")
    async with Session() as s:
        cats = (await s.execute(select(Category).order_by(Category.id.asc()))).scalars().all()
    if cats:
        await state.set_state(AddProduct.category)
        kb = [[InlineKeyboardButton(text=f"📂 {_cat_name(c, lang)}", callback_data=f"addcat:{c.id}")] for c in cats]
        kb.append([InlineKeyboardButton(text=t(lang, "btn_skip_category"), callback_data="addcat:0")])
        await cb.message.answer(t(lang, "add_category"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await state.set_state(AddProduct.title)
        await cb.message.answer(t(lang, "add_title"), reply_markup=ReplyKeyboardRemove())
    await cb.answer()


@seller_router.callback_query(AddProduct.category, F.data.startswith("addcat:"))
async def add_select_category(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    cid = int(cb.data.split(":")[1])
    cat_name = "-"
    if cid > 0:
        async with Session() as s:
            c = (await s.execute(select(Category).where(Category.id == cid))).scalar_one_or_none()
            if c:
                cat_name = _cat_name(c, lang)
            else:
                cid = 0
    await state.update_data(category_id=cid if cid > 0 else None, category_name=cat_name)
    await state.set_state(AddProduct.title)
    with suppress(Exception):
        await cb.message.edit_text(f"📂 {esc(cat_name)}")
    await cb.message.answer(t(lang, "add_title"), reply_markup=ReplyKeyboardRemove())
    await cb.answer()


@seller_router.message(AddProduct.title)
async def add_title(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "add_title"))
    await state.update_data(title=message.text.strip()[:MAX_PRODUCT_TITLE_LEN])
    await state.set_state(AddProduct.desc)
    await message.answer(t(lang, "add_desc"))


@seller_router.message(AddProduct.desc)
async def add_desc(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer(t(lang, "add_desc"))
    await state.update_data(desc=message.text.strip()[:MAX_PRODUCT_DESC_LEN])
    await state.set_state(AddProduct.price)
    await message.answer(t(lang, "add_price"))


@seller_router.message(AddProduct.price)
async def add_price(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    price = _parse_positive_float(message.text or "", allow_zero=False)
    if price is None:
        return await message.answer(t(lang, "add_price"))
    await state.update_data(price=price)
    await state.set_state(AddProduct.delivery_fee)
    await message.answer(t(lang, "add_delivery_fee"))


@seller_router.message(AddProduct.delivery_fee)
async def add_delivery(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    d = _parse_positive_float(message.text or "", allow_zero=True)
    if d is None:
        return await message.answer(t(lang, "add_delivery_fee"))
    await state.update_data(delivery=d)
    await state.set_state(AddProduct.stock)
    await message.answer(t(lang, "add_stock"))


@seller_router.message(AddProduct.stock)
async def add_stock(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    stock = _parse_int_range(message.text or "", 1)
    if stock is None:
        return await message.answer(t(lang, "add_stock"))
    await state.update_data(stock=stock)
    await state.set_state(AddProduct.variations)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_vars"), callback_data="skip_vars")]])
    await message.answer(t(lang, "add_variations"), reply_markup=kb)


@seller_router.callback_query(F.data == "skip_vars")
async def skip_vars(cb: CallbackQuery, state: FSMContext):
    await state.update_data(vars="")
    await state.set_state(AddProduct.photo_1)
    with suppress(Exception):
        await cb.message.edit_text(t(await get_lang(cb.from_user.id), "add_photo"))
    await cb.answer()


@seller_router.message(AddProduct.variations)
async def add_vars(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if raw.lower() in ("تخطي", "skip"):
        raw = ""
    await state.update_data(vars=raw[:MAX_PRODUCT_VARS_LEN])
    await state.set_state(AddProduct.photo_1)
    await message.answer(t(await get_lang(message.from_user.id), "add_photo"))


@seller_router.message(AddProduct.photo_1, F.photo)
async def add_photo_1(message: Message, state: FSMContext):
    await state.update_data(photo_1=message.photo[-1].file_id)
    await state.set_state(AddProduct.photo_2)
    lang = await get_lang(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_photo"), callback_data="skip_photo2")]])
    await message.answer(t(lang, "add_photo_2"), reply_markup=kb)


@seller_router.message(AddProduct.photo_1, ~F.photo)
async def add_photo_1_invalid(message: Message):
    await message.answer(t(await get_lang(message.from_user.id), "add_photo"))


@seller_router.callback_query(F.data == "skip_photo2")
async def skip_photo2(cb: CallbackQuery, state: FSMContext):
    await state.update_data(photo_2="")
    await state.set_state(AddProduct.photo_3)
    lang = await get_lang(cb.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_photo"), callback_data="skip_photo3")]])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "add_photo_3"), reply_markup=kb)
    await cb.answer()


@seller_router.message(AddProduct.photo_2, F.photo)
async def add_photo_2(message: Message, state: FSMContext):
    await state.update_data(photo_2=message.photo[-1].file_id)
    await state.set_state(AddProduct.photo_3)
    lang = await get_lang(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_photo"), callback_data="skip_photo3")]])
    await message.answer(t(lang, "add_photo_3"), reply_markup=kb)


@seller_router.message(AddProduct.photo_2, ~F.photo)
async def add_photo_2_invalid(message: Message):
    lang = await get_lang(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_photo"), callback_data="skip_photo2")]])
    await message.answer(t(lang, "add_photo_2"), reply_markup=kb)


@seller_router.callback_query(F.data == "skip_photo3")
async def skip_photo3(cb: CallbackQuery, state: FSMContext):
    await state.update_data(photo_3="")
    await finalize_add_product(cb.message, cb.from_user.id, state)
    await cb.answer()


@seller_router.message(AddProduct.photo_3, F.photo)
async def add_photo_3(message: Message, state: FSMContext):
    await state.update_data(photo_3=message.photo[-1].file_id)
    await finalize_add_product(message, message.from_user.id, state)


@seller_router.message(AddProduct.photo_3, ~F.photo)
async def add_photo_3_invalid(message: Message):
    lang = await get_lang(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_photo"), callback_data="skip_photo3")]])
    await message.answer(t(lang, "add_photo_3"), reply_markup=kb)


async def finalize_add_product(message_obj, user_id: int, state: FSMContext):
    data = await state.get_data()
    await state.set_state(AddProduct.confirm)
    lang = await get_lang(user_id)
    text = t(
        lang,
        "add_review",
        title=esc(data.get("title", "-")),
        category=esc(data.get("category_name", "-")),
        price=data.get("price", 0),
        delivery=data.get("delivery", 0),
        stock=data.get("stock", 0),
        vars=esc(data.get("vars") or "بدون خيارات"),
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_confirm"), callback_data="addprod:confirm"),
        InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="addprod:cancel"),
    ]])
    await message_obj.answer(text, reply_markup=kb)


@seller_router.callback_query(F.data == "addprod:cancel")
async def add_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_lang(cb.from_user.id)
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "cancelled"))
    await cb.message.answer(t(lang, "main_menu"), reply_markup=await get_main_kb(cb.from_user.id, lang))
    await cb.answer()


@seller_router.callback_query(F.data == "addprod:confirm")
async def add_confirm(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    sid = data.get("active_store_id")
    if not sid or not await is_store_owner(cb.from_user.id, sid):
        await state.clear()
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        p = Product(
            store_id=sid,
            category_id=data.get("category_id"),
            title=data["title"],
            description=data["desc"],
            price=data["price"],
            delivery_fee=data["delivery"],
            photo_file_id=data["photo_1"],
            photo_file_id_2=data.get("photo_2", ""),
            photo_file_id_3=data.get("photo_3", ""),
            stock_quantity=data["stock"],
            variations=data.get("vars", ""),
            status="pending",
        )
        s.add(p)
        await s.commit()
        await s.refresh(p)
        pid, ptitle, pphoto = p.id, p.title, data["photo_1"]
        stock, delivery, vars_ = data["stock"], data["delivery"], data.get("vars", "") or "-"
    await state.clear()
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "product_submitted"))
    await cb.message.answer(t(lang, "main_menu"), reply_markup=await get_main_kb(cb.from_user.id, lang))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Approve", callback_data=f"admin:approve:{pid}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"admin:reject:{pid}"),
    ]])
    caption = f"📥 New product: <b>{esc(ptitle)}</b>\nالكمية: {stock}\nالتوصيل: {delivery:g}\nالخيارات: {esc(vars_)}"
    await notify_admins(cb.bot, caption, reply_markup=kb, photo=pphoto)
    await cb.answer()


# ─── Store Orders & Safe CSV Export ───

@seller_router.callback_query(F.data.startswith("st_orders:"))
async def store_orders_list(cb: CallbackQuery):
    _, sid, page = cb.data.split(":")
    sid, page = int(sid), int(page)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        orders = (
            await s.execute(
                select(Order)
                .outerjoin(Product, Order.product_id == Product.id)
                .where(or_(Order.store_id == sid, Product.store_id == sid))
                .order_by(Order.created_at.desc())
            )
        ).scalars().all()
    if not orders:
        with suppress(Exception):
            await cb.message.edit_text(t(lang, "orders_empty"), reply_markup=back_kb(lang, f"mngstore:{sid}"))
        return await cb.answer()
    icons = {"pending": "⏳", "shipped": "🚚", "completed": "✅", "cancelled": "❌"}
    items = [(f"{icons.get(o.status, '')} طلب #{o.id} - {o.buyer_name}", f"ord_view:{o.id}") for o in orders]
    extra = [
        InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}"),
        InlineKeyboardButton(text=t(lang, "btn_export_orders"), callback_data=f"st_export:{sid}"),
    ]
    kb = build_pagination_kb(items, page, f"st_orders:{sid}", lang, extra)
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "orders_list"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_export:"))
async def export_orders(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    await cb.answer("⏳ جاري تجهيز الملف...", show_alert=True)
    async with Session() as s:
        rows = (
            await s.execute(
                select(Order, Product)
                .outerjoin(Product, Order.product_id == Product.id)
                .where(or_(Order.store_id == sid, Product.store_id == sid))
                .order_by(Order.created_at.desc())
            )
        ).all()
    if not rows:
        return await cb.message.answer("لا توجد طلبات لتصديرها.")
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["رقم الطلب", "التاريخ", "اسم المنتج", "الخيار", "الكمية", "سعر المنتج", "التوصيل", "الإجمالي", "اسم المشتري", "الهاتف", "العنوان", "ملاحظات", "الحالة"])
    for o, p in rows:
        p_title = p.title if p else (o.product_title or "منتج محذوف")
        p_curr = p.currency if p else (o.product_currency or DEFAULT_CURRENCY)
        total = o.price + o.delivery_fee
        writer.writerow([
            o.id,
            o.created_at.strftime("%Y-%m-%d %H:%M"),
            csv_safe(p_title),
            csv_safe(o.variation),
            "1",
            f"{o.price:.2f} {p_curr}",
            f"{o.delivery_fee:g} {p_curr}",
            f"{total:.2f} {p_curr}",
            csv_safe(o.buyer_name),
            csv_safe(o.buyer_phone),
            csv_safe(o.buyer_address),
            csv_safe(o.buyer_note),
            o.status,
        ])
    csv_data = output.getvalue().encode("utf-8")
    await cb.message.answer_document(BufferedInputFile(csv_data, filename="orders.csv"), caption=t(lang, "export_success"))


@seller_router.callback_query(F.data.startswith("ord_view:"))
async def order_view(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    oid = int(cb.data.split(":")[1])
    if not await is_order_seller(cb.from_user.id, oid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await _render_order_view(cb, oid, lang)
    await cb.answer()


async def _render_order_view(cb: CallbackQuery, oid: int, lang: str):
    async with Session() as s:
        order = (await s.execute(select(Order).where(Order.id == oid))).scalar_one_or_none()
        if not order:
            return
        p = (await s.execute(select(Product).where(Product.id == order.product_id))).scalar_one_or_none() if order.product_id else None
    p_title = esc(p.title if p else (order.product_title or "منتج محذوف"))
    p_curr = esc(p.currency if p else (order.product_currency or DEFAULT_CURRENCY))
    sid = order.store_id or (p.store_id if p else 0)
    sm = {
        "pending": t(lang, "status_pending"),
        "shipped": t(lang, "status_shipped"),
        "completed": t(lang, "status_completed"),
        "cancelled": t(lang, "status_cancelled"),
    }
    text = t(
        lang,
        "order_details",
        id=oid,
        product=p_title,
        variation=esc(order.variation or "-"),
        name=esc(order.buyer_name),
        phone=esc(order.buyer_phone),
        address=esc(order.buyer_address),
        note=esc(order.buyer_note or "-"),
        price=f"{order.price:.2f} {p_curr}",
        delivery=f"{order.delivery_fee:g} {p_curr}",
        status=sm.get(order.status, order.status),
    )
    back_cb = f"st_orders:{sid}:1" if sid else "menu:home"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "status_pending"), callback_data=f"ord_st:{oid}:pending")],
        [InlineKeyboardButton(text=t(lang, "status_shipped"), callback_data=f"ord_st:{oid}:shipped")],
        [InlineKeyboardButton(text=t(lang, "status_completed"), callback_data=f"ord_st:{oid}:completed")],
        [InlineKeyboardButton(text=t(lang, "status_cancelled"), callback_data=f"ord_st:{oid}:cancelled")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=back_cb)],
    ])
    with suppress(Exception):
        await cb.message.edit_text(text, reply_markup=kb)


@seller_router.callback_query(F.data.startswith("ord_st:"))
async def order_status_change(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    _, oid_str, new_status = cb.data.split(":")
    oid = int(oid_str)
    if not await is_order_seller(cb.from_user.id, oid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    if new_status not in ("pending", "shipped", "completed", "cancelled"):
        return await cb.answer()

    async with Session() as s:
        order = (await s.execute(select(Order).where(Order.id == oid))).scalar_one_or_none()
        if not order:
            return await cb.answer("Not found", show_alert=True)
        prev_status = order.status
        order.status = new_status

        if new_status == "cancelled" and prev_status != "cancelled" and order.product_id:
            p = (await s.execute(select(Product).where(Product.id == order.product_id, Product.is_deleted.is_(False)))).scalar_one_or_none()
            if p:
                was_out = p.is_out_of_stock
                p.stock_quantity += 1
                p.is_out_of_stock = False
                if was_out:
                    await _notify_restock_alerts(cb.bot, s, p)

        await s.commit()

        if new_status in ("shipped", "completed", "cancelled"):
            with suppress(Exception):
                bl = await get_lang(order.buyer_tg_id)
                sm = {
                    "pending": t(bl, "status_pending"),
                    "shipped": t(bl, "status_shipped"),
                    "completed": t(bl, "status_completed"),
                    "cancelled": t(bl, "status_cancelled"),
                }
                txt = t(bl, "order_status_notify", id=oid, name=esc(order.buyer_name), status=sm[new_status])
                await cb.bot.send_message(order.buyer_tg_id, txt)

    await cb.answer(t(lang, "status_updated"), show_alert=True)
    await _render_order_view(cb, oid, lang)


# ─── Seller Broadcast & Stats ───

@seller_router.callback_query(F.data.startswith("st_broadcast:"))
async def seller_broadcast_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    remaining = _broadcast_cooldown_remaining(cb.from_user.id)
    if remaining > 0:
        mins, secs = divmod(remaining, 60)
        return await cb.answer(f"⏳ يجب الانتظار {mins}د {secs}ث قبل إرسال بث جديد.", show_alert=True)
    await state.update_data(broadcast_store_id=sid)
    await state.set_state(SellerBroadcastFSM.message)
    await cb.message.answer(t(await get_lang(cb.from_user.id), "seller_broadcast_prompt"))
    await cb.answer()


@seller_router.message(SellerBroadcastFSM.message)
async def seller_broadcast_send(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    sid = data.get("broadcast_store_id")
    await state.clear()
    if not sid or not await is_store_owner(message.from_user.id, sid):
        return await message.answer("⛔ غير مصرح.")
    if _broadcast_cooldown_remaining(message.from_user.id) > 0:
        return await message.answer("⏳ لا يمكن إرسال بث الآن (فترة انتظار).")
    async with Session() as s:
        followers = (await s.execute(select(StoreFollower.user_tg_id).where(StoreFollower.store_id == sid))).scalars().all()
    _BROADCAST_COOLDOWN[message.from_user.id] = time.time()
    status_msg = await message.answer(t(lang, "broadcast_started"))
    success = 0
    for uid in followers:
        if await _safe_send_copy(message, uid):
            success += 1
        await asyncio.sleep(0.05)
    with suppress(Exception):
        await status_msg.edit_text(t(lang, "seller_broadcast_done", count=success))


@seller_router.callback_query(F.data.startswith("st_stats:"))
async def store_stats(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        pcount = (await s.execute(select(func.count(Product.id)).where(Product.store_id == sid, Product.is_deleted.is_(False)))).scalar()
        vcount = (await s.execute(select(func.coalesce(func.sum(Product.views), 0)).where(Product.store_id == sid, Product.is_deleted.is_(False)))).scalar()
        ocount = (
            await s.execute(
                select(func.count(Order.id))
                .outerjoin(Product, Order.product_id == Product.id)
                .where(or_(Order.store_id == sid, Product.store_id == sid))
            )
        ).scalar()
        revenue = (
            await s.execute(
                select(func.coalesce(func.sum(Order.price), 0))
                .outerjoin(Product, Order.product_id == Product.id)
                .where(or_(Order.store_id == sid, Product.store_id == sid), Order.status != "cancelled")
            )
        ).scalar()
        rating = await get_store_rating(sid, s)
        top_results = (
            await s.execute(
                select(Product.title, func.count(Order.id))
                .join(Order, Order.product_id == Product.id)
                .where(Product.store_id == sid, Order.status != "cancelled")
                .group_by(Product.id)
                .order_by(desc(func.count(Order.id)))
                .limit(5)
            )
        ).all()
    top_text = "".join(t(lang, "top_prod_line", name=esc(name), count=count) for name, count in top_results) or "لا توجد مبيعات بعد."
    text = t(lang, "stats", views=vcount, products=pcount, orders=ocount, revenue=f"{revenue:.2f}", rating=rating, top=top_text)
    await cb.message.answer(text)
    await cb.answer()


# ─── Promo Codes (per-store unique & 1-99% validated) ───

@seller_router.callback_query(F.data.startswith("st_promos:"))
async def seller_promos(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_add_promo"), callback_data=f"st_add_promo:{sid}")],
        [InlineKeyboardButton(text=t(lang, "btn_list_promos"), callback_data=f"st_list_promos:{sid}")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}")],
    ])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "promo_manage"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_add_promo:"))
async def promo_add_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(promo_store_id=sid)
    await state.set_state(AddPromoFSM.code_data)
    await cb.message.answer(t(await get_lang(cb.from_user.id), "promo_add_prompt"))
    await cb.answer()


@seller_router.message(AddPromoFSM.code_data)
async def promo_add_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    sid = data.get("promo_store_id")
    if not sid or not await is_store_owner(message.from_user.id, sid):
        await state.clear()
        return await message.answer("⛔ غير مصرح.")
    parts = (message.text or "").split()
    if len(parts) != 2:
        return await message.answer(t(lang, "promo_add_prompt"))
    percent = _parse_int_range(parts[1], 1, 99)
    if percent is None:
        return await message.answer(t(lang, "promo_add_prompt"))
    code = parts[0].upper()[:50]
    async with Session() as s:
        existing = (
            await s.execute(select(PromoCode).where(PromoCode.store_id == sid, PromoCode.code == code))
        ).scalar_one_or_none()
        if existing:
            return await message.answer("هذا الكود موجود بالفعل في متجرك.")
        s.add(PromoCode(store_id=sid, code=code, discount_percent=percent))
        await s.commit()
    await state.clear()
    await message.answer(t(lang, "promo_added"), reply_markup=await get_main_kb(message.from_user.id, lang))


@seller_router.callback_query(F.data.startswith("st_list_promos:"))
async def promo_list(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        promos = (await s.execute(select(PromoCode).where(PromoCode.store_id == sid))).scalars().all()
    if not promos:
        return await cb.answer("لا توجد أكواد.", show_alert=True)
    kb = [[InlineKeyboardButton(text=f"❌ {p.code} ({p.discount_percent}%)", callback_data=f"promo_del:{p.id}")] for p in promos]
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"st_promos:{sid}")])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "promos_list"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("promo_del:"))
async def promo_del(cb: CallbackQuery):
    pid = int(cb.data.split(":")[1])
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        p = (await s.execute(select(PromoCode).where(PromoCode.id == pid))).scalar_one_or_none()
        if not p:
            return await cb.answer()
        if not await is_store_owner(cb.from_user.id, p.store_id):
            return await cb.answer("⛔ غير مصرح.", show_alert=True)
        sid = p.store_id
        await s.delete(p)
        await s.commit()
    await cb.answer(t(lang, "promo_deleted"), show_alert=True)
    async with Session() as s:
        promos = (await s.execute(select(PromoCode).where(PromoCode.store_id == sid))).scalars().all()
    if not promos:
        with suppress(Exception):
            await cb.message.edit_text("لا توجد أكواد.", reply_markup=back_kb(lang, f"st_promos:{sid}"))
        return
    kb = [[InlineKeyboardButton(text=f"❌ {pr.code} ({pr.discount_percent}%)", callback_data=f"promo_del:{pr.id}")] for pr in promos]
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"st_promos:{sid}")])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "promos_list"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


# ─── Flash Sales (strictly validated) ───

@seller_router.callback_query(F.data.startswith("st_flash:"))
async def flash_sale_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        products = (
            await s.execute(select(Product).where(Product.store_id == sid, Product.status == "approved", Product.is_deleted.is_(False)))
        ).scalars().all()
    if not products:
        return await cb.answer("لا توجد منتجات لعمل عرض عليها.", show_alert=True)
    kb = [[InlineKeyboardButton(text=p.title, callback_data=f"fs_select:{p.id}:{sid}")] for p in products]
    kb.append([InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data=f"mngstore:{sid}")])
    await state.set_state(FlashSaleFSM.select_product)
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "flash_sale_select_prod"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


@seller_router.callback_query(FlashSaleFSM.select_product, F.data.startswith("fs_select:"))
async def flash_sale_select(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    _, pid_str, sid_str = cb.data.split(":")
    pid, sid = int(pid_str), int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid) or not await is_product_owner(cb.from_user.id, pid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(fs_pid=pid, fs_store_id=sid)
    await state.set_state(FlashSaleFSM.enter_price)
    await cb.message.answer(t(lang, "flash_sale_enter_price"))
    await cb.answer()


@seller_router.message(FlashSaleFSM.enter_price)
async def flash_sale_price(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    price = _parse_positive_float(message.text or "", allow_zero=False)
    if price is None:
        return await message.answer(t(lang, "flash_sale_enter_price"))
    data = await state.get_data()
    pid = data.get("fs_pid")
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
    if not p or price >= p.price:
        return await message.answer(t(lang, "flash_sale_enter_price"))
    await state.update_data(fs_price=price)
    await state.set_state(FlashSaleFSM.enter_hours)
    await message.answer(t(lang, "flash_sale_enter_hours"))


@seller_router.message(FlashSaleFSM.enter_hours)
async def flash_sale_hours(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    hours = _parse_int_range(message.text or "", 1, 720)
    if hours is None:
        return await message.answer(t(lang, "flash_sale_enter_hours"))
    data = await state.get_data()
    pid = data.get("fs_pid")
    if not pid or not await is_product_owner(message.from_user.id, pid):
        await state.clear()
        return await message.answer("⛔ غير مصرح.")
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one()
        p.flash_sale_price = data["fs_price"]
        p.flash_sale_ends_at = utcnow() + timedelta(hours=hours)
        await s.commit()
    await state.clear()
    await message.answer(t(lang, "flash_sale_created"), reply_markup=await get_main_kb(message.from_user.id, lang))


# ─── Product Featured Ads (ProductAdFSM) ───

@seller_router.callback_query(F.data.startswith("st_buy_ad:"))
async def product_ad_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        products = (
            await s.execute(select(Product).where(Product.store_id == sid, Product.status == "approved", Product.is_deleted.is_(False)))
        ).scalars().all()
    if not products:
        return await cb.answer("لا توجد منتجات معتمدة لتمييزها.", show_alert=True)
    kb = [[InlineKeyboardButton(text=p.title, callback_data=f"pad_sel:{p.id}:{sid}")] for p in products]
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}")])
    await state.set_state(ProductAdFSM.select_product)
    with suppress(Exception):
        await cb.message.edit_text("📢 <b>تمييز منتج</b>\n\nاختر المنتج الذي تريد تمييزه:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


@seller_router.callback_query(ProductAdFSM.select_product, F.data.startswith("pad_sel:"))
async def product_ad_select(cb: CallbackQuery, state: FSMContext):
    _, pid_str, sid_str = cb.data.split(":")
    pid, sid = int(pid_str), int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid) or not await is_product_owner(cb.from_user.id, pid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(pad_pid=pid, pad_store_id=sid)
    await state.set_state(ProductAdFSM.select_package)
    lang = await get_lang(cb.from_user.id)
    pkgs = {"basic": "ad_pkg_basic", "pro": "ad_pkg_pro", "vip": "ad_pkg_vip"}
    kb = [[InlineKeyboardButton(text=t(lang, key), callback_data=f"pad_pkg:{p}:{pid}")] for p, key in pkgs.items()]
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}")])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "ad_packages_title"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


@seller_router.callback_query(ProductAdFSM.select_package, F.data.startswith("pad_pkg:"))
async def product_ad_pkg(cb: CallbackQuery, state: FSMContext):
    _, pkg, pid_str = cb.data.split(":")
    pid = int(pid_str)
    if not await is_product_owner(cb.from_user.id, pid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    prices = {"basic": 1000, "pro": 2000, "vip": 7000}
    await state.update_data(pad_pkg=pkg)
    lang = await get_lang(cb.from_user.id)
    text = f"{t(lang, 'ad_payment_instructions')}\n\n💰 المبلغ: {prices.get(pkg, 1000)} دج"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_send_payment_proof"), callback_data="pad_send_proof")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")],
    ])
    with suppress(Exception):
        await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(ProductAdFSM.select_package, F.data == "pad_send_proof")
async def product_ad_proof_prompt(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ProductAdFSM.payment_proof)
    await cb.message.answer("📸 أرسل صورة إثبات الدفع الآن:")
    await cb.answer()


@seller_router.message(ProductAdFSM.payment_proof, F.photo)
async def product_ad_receive_proof(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    pid, sid, pkg = data.get("pad_pid"), data.get("pad_store_id"), data.get("pad_pkg")
    if not (pid and sid and pkg) or not await is_product_owner(message.from_user.id, pid):
        await state.clear()
        return await message.answer("انتهت الجلسة، ابدأ من جديد.")
    proof = message.photo[-1].file_id
    prices = {"basic": 1000, "pro": 2000, "vip": 7000}
    async with Session() as s:
        areq = AdRequest(
            user_tg_id=message.from_user.id,
            ad_type="product",
            target_id=pid,
            package_name=pkg,
            price=float(prices.get(pkg, 1000)),
            status="pending",
        )
        s.add(areq)
        await s.commit()
        await s.refresh(areq)
        areq_id = areq.id
        p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one()
        ptitle = p.title
    await state.clear()
    await message.answer(t(lang, "payment_proof_received"), reply_markup=await get_main_kb(message.from_user.id, lang))
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("ar", "btn_confirm_payment"), callback_data=f"admin:confirm_payment:{areq_id}"),
        InlineKeyboardButton(text=t("ar", "btn_reject_bot_ad"), callback_data=f"admin:reject_payment:{areq_id}"),
    ]])
    admin_text = t(
        "ar",
        "admin_ad_req_view",
        user_id=message.from_user.id,
        package=esc(pkg),
        price=f"{prices.get(pkg, 1000)} دج",
        type=f"product #{pid} ({esc(ptitle)})",
    )
    await notify_admins(message.bot, admin_text, reply_markup=admin_kb, photo=proof)


@seller_router.message(ProductAdFSM.payment_proof, ~F.photo)
async def product_ad_receive_proof_invalid(message: Message):
    await message.answer("📸 أرسل صورة إثبات الدفع:")


# ════════════════════════════════════════════════════════════════════
# 8. ADMIN PANEL (seller_handlers)
# ════════════════════════════════════════════════════════════════════

@seller_router.message(F.text.in_([t(l, "btn_admin") for l in LANGS]))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    lang = await get_lang(message.from_user.id)
    kb = await _build_admin_panel_kb(lang)
    await message.answer(t(lang, "admin_panel"), reply_markup=kb)


@seller_router.callback_query(F.data == "menu:admin")
async def admin_panel_cb(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    kb = await _build_admin_panel_kb(lang)
    try:
        await cb.message.edit_text(t(lang, "admin_panel"), reply_markup=kb)
    except Exception:
        await cb.message.answer(t(lang, "admin_panel"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:pending"))
async def admin_pending_products(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[2]) if cb.data.startswith("admin:pending_pg:") else 1
    async with Session() as s:
        products = (
            await s.execute(
                select(Product)
                .where(Product.status == "pending", Product.is_deleted.is_(False))
                .order_by(Product.created_at.desc())
            )
        ).scalars().all()
    if not products:
        return await cb.answer(t(lang, "pending_empty"), show_alert=True)
    items = [(f"📥 {p.title} — {p.price:g} {p.currency}", f"admin:pview:{p.id}") for p in products]
    kb = build_pagination_kb(items, page, "admin:pending_pg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")])
    try:
        await cb.message.edit_text(t(lang, "btn_pending"), reply_markup=kb)
    except Exception:
        await cb.message.answer(t(lang, "btn_pending"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:pview:"))
async def admin_pending_view(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    pid = int(cb.data.split(":")[2])
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid, Product.is_deleted.is_(False)))).scalar_one_or_none()
        if not p:
            return await cb.answer("Not found", show_alert=True)
        store = (await s.execute(select(Store).where(Store.id == p.store_id))).scalar_one_or_none()
    caption = (
        f"📥 <b>{esc(p.title)}</b>\n"
        f"💵 {p.price:g} {esc(p.currency)}\n"
        f"📝 {esc((p.description or '')[:300])}\n"
        f"🏪 {esc(store.name if store else '-')}\n"
        f"📦 الكمية: {p.stock_quantity}\n"
        f"🎨 الخيارات: {esc(p.variations or '-')}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("ar", "btn_approve"), callback_data=f"admin:approve:{pid}"),
         InlineKeyboardButton(text=t("ar", "btn_reject"), callback_data=f"admin:reject:{pid}")],
        [InlineKeyboardButton(text=t("ar", "btn_back"), callback_data="admin:pending")],
    ])
    if p.photo_file_id:
        await cb.message.answer_photo(photo=p.photo_file_id, caption=caption[:1024], reply_markup=kb)
    else:
        await cb.message.answer(caption, reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:approve:"))
async def admin_approve_product(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    pid = int(cb.data.split(":")[2])
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid, Product.is_deleted.is_(False)))).scalar_one_or_none()
        if not p:
            return await cb.answer("Not found", show_alert=True)
        p.status = "approved"
        p.reject_reason = ""
        store = (await s.execute(select(Store).where(Store.id == p.store_id))).scalar_one_or_none()
        owner_id = store.owner_tg_id if store else None
        store_name = store.name if store else "-"
        ptitle = p.title
        price_str = f"{p.price:g} {p.currency}"
        followers = (await s.execute(select(StoreFollower.user_tg_id).where(StoreFollower.store_id == p.store_id))).scalars().all()
        await s.commit()
    if owner_id:
        with suppress(Exception):
            sl = await get_lang(owner_id)
            await cb.bot.send_message(owner_id, t(sl, "product_approved_notify", title=esc(ptitle)))
    for fid in followers:
        try:
            fl = await get_lang(fid)
            await cb.bot.send_message(
                fid,
                t(fl, "new_prod_follower_notify", store=esc(store_name), product=esc(ptitle), price=esc(price_str)),
            )
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except Exception:
            pass
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer("✅ " + t("ar", "approved"))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:reject:"))
async def admin_reject_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    pid = int(cb.data.split(":")[2])
    await state.update_data(reject_pid=pid)
    await state.set_state(RejectFSM.reason)
    await cb.message.answer(t("ar", "reject_reason"))
    await cb.answer()


@seller_router.message(RejectFSM.reason)
async def admin_reject_finish(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    data = await state.get_data()
    pid = data.get("reject_pid")
    reason = (message.text or "").strip()[:200] or "غير محدد"
    await state.clear()
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
        if not p:
            return await message.answer("Not found")
        p.status = "rejected"
        p.reject_reason = reason
        store = (await s.execute(select(Store).where(Store.id == p.store_id))).scalar_one_or_none()
        owner_id = store.owner_tg_id if store else None
        ptitle = p.title
        await s.commit()
    if owner_id:
        with suppress(Exception):
            sl = await get_lang(owner_id)
            await message.bot.send_message(owner_id, t(sl, "product_rejected_notify", title=esc(ptitle), reason=esc(reason)))
    await message.answer("✅ " + t("ar", "rejected"), reply_markup=await get_main_kb(message.from_user.id, await get_lang(message.from_user.id)))


@seller_router.callback_query(F.data == "admin:reports")
async def admin_reports(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        reports = (await s.execute(select(Report).where(Report.status == "pending").order_by(Report.created_at.desc()).limit(25))).scalars().all()
    if not reports:
        return await cb.answer(t(lang, "reports_empty"), show_alert=True)
    text = t(lang, "reports_list") + "\n\n"
    kb = []
    for r in reports:
        text += f"#{r.id} • {esc(r.target_type)} #{r.target_id}\nالسبب: {esc(r.reason)}\n\n"
        kb.append([InlineKeyboardButton(text=f"✅ حل #{r.id}", callback_data=f"admin:report_resolve:{r.id}")])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")])
    try:
        await cb.message.edit_text(text[:4000], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        await cb.message.answer(text[:4000], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:report_resolve:"))
async def admin_report_resolve(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    rid = int(cb.data.split(":")[2])
    async with Session() as s:
        r = (await s.execute(select(Report).where(Report.id == rid))).scalar_one_or_none()
        if r:
            r.status = "resolved"
            await s.commit()
    await cb.answer(t("ar", "report_resolved"), show_alert=True)
    await admin_reports(cb)


@seller_router.callback_query(F.data == "admin:cats")
async def admin_cats(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        cats = (await s.execute(select(Category).order_by(Category.id.asc()))).scalars().all()
    kb = [[InlineKeyboardButton(text=f"🗑️ {c.name_ar}", callback_data=f"admin:cat_del:{c.id}")] for c in cats]
    kb.append([InlineKeyboardButton(text=t(lang, "btn_add_cat"), callback_data="admin:cat_add")])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")])
    try:
        await cb.message.edit_text(t(lang, "cats_manage"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        await cb.message.answer(t(lang, "cats_manage"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


@seller_router.callback_query(F.data == "admin:cat_add")
async def admin_cat_add(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.set_state(AddCategoryFSM.names)
    await cb.message.answer(t("ar", "cat_add_prompt"))
    await cb.answer()


@seller_router.message(AddCategoryFSM.names)
async def admin_cat_add_save(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    parts = [p.strip()[:50] for p in (message.text or "").split(",")]
    if len(parts) < 3 or not all(parts[:3]):
        return await message.answer(t("ar", "cat_add_prompt"))
    async with Session() as s:
        s.add(Category(name_ar=parts[0], name_en=parts[1], name_fr=parts[2]))
        await s.commit()
    await state.clear()
    await message.answer(t("ar", "cat_added"), reply_markup=await get_main_kb(message.from_user.id, await get_lang(message.from_user.id)))


@seller_router.callback_query(F.data.startswith("admin:cat_del:"))
async def admin_cat_del_confirm(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    cid = int(cb.data.split(":")[2])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("ar", "btn_yes_delete"), callback_data=f"admin:cat_del_yes:{cid}"),
        InlineKeyboardButton(text=t("ar", "btn_cancel"), callback_data="admin:cats"),
    ]])
    try:
        await cb.message.edit_text(t("ar", "cat_del_confirm"), reply_markup=kb)
    except Exception:
        await cb.message.answer(t("ar", "cat_del_confirm"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:cat_del_yes:"))
async def admin_cat_del_yes(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    cid = int(cb.data.split(":")[2])
    async with Session() as s:
        c = (await s.execute(select(Category).where(Category.id == cid))).scalar_one_or_none()
        if c:
            await s.execute(update(Product).where(Product.category_id == cid).values(category_id=None))
            await s.delete(c)
            await s.commit()
    await cb.answer(t("ar", "cat_deleted"), show_alert=True)
    await admin_cats(cb)


@seller_router.callback_query(F.data == "admin:gstats")
async def admin_gstats(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        users = (await s.execute(select(func.count(User.id)))).scalar()
        stores = (await s.execute(select(func.count(Store.id)))).scalar()
        products = (await s.execute(select(func.count(Product.id)).where(Product.is_deleted.is_(False)))).scalar()
        orders = (await s.execute(select(func.count(Order.id)))).scalar()
    text = t(lang, "global_stats", users=users, stores=stores, products=products, orders=orders)
    kb = back_kb(lang, "menu:admin")
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


# ─── Admin Store Management & Search ───

async def _render_admin_stores(cb_or_msg, page: int, is_cb: bool = True):
    admin_id = cb_or_msg.from_user.id
    lang = await get_lang(admin_id)
    query = _ADMIN_STORE_SEARCH.get(admin_id, "").strip()

    async with Session() as s:
        stmt = select(Store).order_by(Store.created_at.desc())
        if query:
            like = f"%{query}%"
            stmt = stmt.where(or_(Store.name.ilike(like), Store.custom_slug.ilike(like), Store.bio.ilike(like)))
        stores = (await s.execute(stmt.limit(200))).scalars().all()

    if query:
        search_btn = InlineKeyboardButton(text=f'🔎 البحث: "{query}" ❌', callback_data="admin:store_search_clear")
    else:
        search_btn = InlineKeyboardButton(text="🔎 بحث في المتاجر", callback_data="admin:store_search")

    if not stores:
        empty_text = f"لا توجد متاجر مطابقة للبحث: <b>{esc(query)}</b>" if query else "لا توجد متاجر."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [search_btn],
            [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")],
        ])
        if is_cb:
            with suppress(Exception):
                await cb_or_msg.message.edit_text(empty_text, reply_markup=kb)
        else:
            await cb_or_msg.answer(empty_text, reply_markup=kb)
        return

    items = [(f"{'✅ ' if st.verified else ''}🏪 {st.name}", f"admin:store_view:{st.id}") for st in stores]
    kb = build_pagination_kb(
        items,
        page,
        "admin:stores_pg",
        lang,
        extra_buttons=[search_btn, InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")],
    )
    if is_cb:
        with suppress(Exception):
            await cb_or_msg.message.edit_text(t(lang, "admin_stores_list"), reply_markup=kb)
    else:
        await cb_or_msg.answer(t(lang, "admin_stores_list"), reply_markup=kb)


@seller_router.callback_query(F.data == "admin:stores")
async def admin_stores(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    _ADMIN_STORE_SEARCH.pop(cb.from_user.id, None)
    await _render_admin_stores(cb, page=1, is_cb=True)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:stores_pg:"))
async def admin_stores_pg(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    page = int(cb.data.split(":")[2])
    await _render_admin_stores(cb, page=page, is_cb=True)
    await cb.answer()


@seller_router.callback_query(F.data == "admin:store_search")
async def admin_store_search_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.set_state(AdminStoreSearchFSM.query)
    await cb.message.answer(
        "🔎 <b>بحث المتاجر</b>\n\n"
        "أرسل اسم المتجر أو جزءاً منه (أو الـ slug).\n"
        "أو أرسل <code>-</code> لمسح البحث."
    )
    await cb.answer()


@seller_router.message(AdminStoreSearchFSM.query)
async def admin_store_search_apply(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    q = (message.text or "").strip()
    await state.clear()
    if q in ("-", ""):
        _ADMIN_STORE_SEARCH.pop(message.from_user.id, None)
    else:
        _ADMIN_STORE_SEARCH[message.from_user.id] = q[:100]
    await _render_admin_stores(message, page=1, is_cb=False)


@seller_router.callback_query(F.data == "admin:store_search_clear")
async def admin_store_search_clear(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    _ADMIN_STORE_SEARCH.pop(cb.from_user.id, None)
    await _render_admin_stores(cb, page=1, is_cb=True)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:store_view:"))
async def admin_store_view(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    sid = int(cb.data.split(":")[2])
    async with Session() as s:
        st = (await s.execute(select(Store).where(Store.id == sid))).scalar_one_or_none()
        if not st:
            return await cb.answer("Not found", show_alert=True)
        pcount = (await s.execute(select(func.count(Product.id)).where(Product.store_id == sid, Product.is_deleted.is_(False)))).scalar()
    text = (
        f"🏪 <b>{esc(st.name)}</b>\n\n"
        f"👤 المالك: <code>{st.owner_tg_id}</code>\n"
        f"📦 المنتجات: {pcount}\n"
        f"📌 الحالة: {'✅ موثق' if st.verified else '❌ غير موثق'}\n"
        f"📝 {esc(st.bio or '-')}"
    )
    action_btn = (
        InlineKeyboardButton(text=t(lang, "btn_unverify"), callback_data=f"admin:unverify_store:{sid}")
        if st.verified
        else InlineKeyboardButton(text=t(lang, "btn_verify"), callback_data=f"admin:verify_store:{sid}")
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [action_btn],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="admin:stores")],
    ])
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:verify_store:"))
async def admin_verify_store(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    sid = int(cb.data.split(":")[2])
    async with Session() as s:
        st = (await s.execute(select(Store).where(Store.id == sid))).scalar_one_or_none()
        if st:
            st.verified = True
            await s.commit()
    await cb.answer("✅ تم التوثيق.", show_alert=True)
    await admin_store_view(cb)


@seller_router.callback_query(F.data.startswith("admin:unverify_store:"))
async def admin_unverify_store(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    sid = int(cb.data.split(":")[2])
    async with Session() as s:
        st = (await s.execute(select(Store).where(Store.id == sid))).scalar_one_or_none()
        if st:
            st.verified = False
            await s.commit()
    await cb.answer("❌ تم إلغاء التوثيق.", show_alert=True)
    await admin_store_view(cb)


# ─── Admin Broadcast ───

@seller_router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    remaining = _broadcast_cooldown_remaining(cb.from_user.id)
    if remaining > 0:
        mins, secs = divmod(remaining, 60)
        return await cb.answer(f"⏳ يجب الانتظار {mins}د {secs}ث قبل إرسال بث جديد.", show_alert=True)
    await state.set_state(BroadcastFSM.message)
    await cb.message.answer(t("ar", "broadcast_prompt"))
    await cb.answer()


@seller_router.message(BroadcastFSM.message)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    if _broadcast_cooldown_remaining(message.from_user.id) > 0:
        await state.clear()
        return await message.answer("⏳ لا يمكن إرسال بث الآن (فترة انتظار).")
    await state.clear()
    async with Session() as s:
        users = (await s.execute(select(User.tg_id))).scalars().all()
    _BROADCAST_COOLDOWN[message.from_user.id] = time.time()
    status = await message.answer(t("ar", "broadcast_started"))
    success = 0
    for uid in users:
        if await _safe_send_copy(message, uid):
            success += 1
        await asyncio.sleep(0.05)
    with suppress(Exception):
        await status.edit_text(t("ar", "broadcast_done", count=success))


# ─── Admin Support Tickets (reply + close) ───

@seller_router.callback_query(F.data.startswith("admin:tickets"))
async def admin_tickets(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[2]) if cb.data.startswith("admin:tickets_pg:") else 1
    async with Session() as s:
        tickets = (await s.execute(select(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(50))).scalars().all()
    if not tickets:
        return await cb.answer("لا توجد تذاكر.", show_alert=True)
    items = [(f"{'🟢' if tk.status == 'open' else '🔴'} #{tk.id} - {tk.subject}", f"admin:ticket_view:{tk.id}") for tk in tickets]
    kb = build_pagination_kb(items, page, "admin:tickets_pg", lang, [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")])
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "btn_tickets"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:ticket_view:"))
async def admin_ticket_view(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    tid = int(cb.data.split(":")[2])
    async with Session() as s:
        tk = (await s.execute(select(SupportTicket).where(SupportTicket.id == tid))).scalar_one_or_none()
        if not tk:
            return await cb.answer("Not found", show_alert=True)
        msgs = (
            await s.execute(select(TicketMessage).where(TicketMessage.ticket_id == tid).order_by(TicketMessage.created_at.asc()))
        ).scalars().all()
    status_str = "🟢 مفتوحة" if tk.status == "open" else "🔴 مغلقة"
    text = f"🎫 <b>تذكرة #{tid}: {esc(tk.subject)}</b> ({status_str})\nالمستخدم: <code>{tk.user_tg_id}</code>\n\n"
    for m in msgs:
        sender = "👨‍💼 الإدارة" if m.is_admin else f"👤 {m.sender_tg_id}"
        text += f"{sender}:\n{esc(m.text)}\n\n"
    rows = [[InlineKeyboardButton(text=t("ar", "btn_reply_ticket"), callback_data=f"admin:ticket_reply:{tid}")]]
    if tk.status == "open":
        rows.append([InlineKeyboardButton(text=t("ar", "btn_close_ticket"), callback_data=f"admin:ticket_close:{tid}")])
    rows.append([InlineKeyboardButton(text=t("ar", "btn_back"), callback_data="admin:tickets")])
    try:
        await cb.message.edit_text(text[:4000], reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await cb.message.answer(text[:4000], reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:ticket_close:"))
async def admin_ticket_close(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    tid = int(cb.data.split(":")[2])
    async with Session() as s:
        tk = (await s.execute(select(SupportTicket).where(SupportTicket.id == tid))).scalar_one_or_none()
        if tk:
            tk.status = "closed"
            await s.commit()
            uid = tk.user_tg_id
        else:
            return await cb.answer("Not found", show_alert=True)
    with suppress(Exception):
        ulang = await get_lang(uid)
        await cb.bot.send_message(uid, f"{t(ulang, 'ticket_closed')} (#{tid})")
    await cb.answer(t("ar", "ticket_closed"), show_alert=True)
    await admin_ticket_view(cb)


@seller_router.callback_query(F.data.startswith("admin:ticket_reply:"))
async def admin_ticket_reply_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    tid = int(cb.data.split(":")[2])
    await state.update_data(admin_reply_tid=tid)
    await state.set_state(AdminTicketReplyFSM.message)
    await cb.message.answer(t("ar", "ticket_reply_prompt"))
    await cb.answer()


@seller_router.message(AdminTicketReplyFSM.message)
async def admin_ticket_reply_save(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    data = await state.get_data()
    tid = data.get("admin_reply_tid")
    await state.clear()
    if not tid:
        return
    body = (message.text or message.caption or "صورة/ملف")[:2000]
    async with Session() as s:
        tk = (await s.execute(select(SupportTicket).where(SupportTicket.id == tid))).scalar_one_or_none()
        if not tk:
            return await message.answer("Not found")
        s.add(TicketMessage(ticket_id=tid, sender_tg_id=message.from_user.id, is_admin=True, text=body))
        tk.status = "open"
        await s.commit()
        user_id = tk.user_tg_id
    with suppress(Exception):
        ulang = await get_lang(user_id)
        await message.bot.send_message(user_id, t(ulang, "ticket_reply_from_admin", id=tid, text=esc(body)))
    await message.answer("✅ تم إرسال الرد.", reply_markup=await get_main_kb(message.from_user.id, await get_lang(message.from_user.id)))


# ─── Admin Bot Ads ───

@seller_router.callback_query(F.data == "admin:botads")
async def admin_botads(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        ads = (await s.execute(select(BotAd).where(BotAd.status == "pending").order_by(BotAd.created_at.desc()))).scalars().all()
    if not ads:
        return await cb.answer("لا توجد إعلانات معلقة.", show_alert=True)
    text = t(lang, "bot_ads_pending") + "\n\n"
    kb = []
    for a in ads:
        text += f"#{a.id} — {esc(a.bot_name)} (@{esc(a.bot_username)})\n"
        kb.append([
            InlineKeyboardButton(text=f"✅ #{a.id}", callback_data=f"admin:botad_app:{a.id}"),
            InlineKeyboardButton(text=f"❌ #{a.id}", callback_data=f"admin:botad_rej:{a.id}"),
        ])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")])
    try:
        await cb.message.edit_text(text[:4000], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        await cb.message.answer(text[:4000], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:botad_app:"))
async def admin_botad_approve(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    ad_id = int(cb.data.split(":")[2])
    async with Session() as s:
        ad = (await s.execute(select(BotAd).where(BotAd.id == ad_id))).scalar_one_or_none()
        if not ad:
            return await cb.answer("Not found", show_alert=True)
        ad.status = "approved"
        if not ad.expires_at:
            ad.expires_at = utcnow() + timedelta(days=30)
        await s.commit()
        owner, bot_name = ad.owner_tg_id, ad.bot_name
    with suppress(Exception):
        await cb.bot.send_message(owner, f"✅ تمت الموافقة على إعلان بوتك <b>{esc(bot_name)}</b>.")
    await cb.answer("✅ تمت الموافقة.", show_alert=True)
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=None)


@seller_router.callback_query(F.data.startswith("admin:botad_rej:"))
async def admin_botad_reject(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    ad_id = int(cb.data.split(":")[2])
    async with Session() as s:
        ad = (await s.execute(select(BotAd).where(BotAd.id == ad_id))).scalar_one_or_none()
        if not ad:
            return await cb.answer("Not found", show_alert=True)
        ad.status = "rejected"
        await s.commit()
        owner, bot_name = ad.owner_tg_id, ad.bot_name
    with suppress(Exception):
        await cb.bot.send_message(owner, f"❌ تم رفض إعلان بوتك <b>{esc(bot_name)}</b>.")
    await cb.answer("❌ تم الرفض.", show_alert=True)
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=None)


# ─── Admin Payment Requests (fixed: no double-crediting) ───

@seller_router.callback_query(F.data == "admin:adreqs")
async def admin_adreqs(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        reqs = (await s.execute(select(AdRequest).where(AdRequest.status == "pending").order_by(AdRequest.created_at.desc()))).scalars().all()
    if not reqs:
        return await cb.answer("لا توجد طلبات دفع معلقة.", show_alert=True)
    text = t(lang, "ad_requests_pending") + "\n\n"
    kb = []
    for r in reqs:
        text += f"#{r.id} • user <code>{r.user_tg_id}</code>\nالباقة: {esc(r.package_name)} • {r.price:.0f} دج\n\n"
        kb.append([
            InlineKeyboardButton(text=f"💰 #{r.id}", callback_data=f"admin:confirm_payment:{r.id}"),
            InlineKeyboardButton(text=f"❌ #{r.id}", callback_data=f"admin:reject_payment:{r.id}"),
        ])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")])
    try:
        await cb.message.edit_text(text[:4000], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        await cb.message.answer(text[:4000], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:confirm_payment:"))
async def admin_confirm_payment(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    areq_id = int(cb.data.split(":")[2])

    PACKAGE_DAYS = {"basic": 3, "pro": 7, "vip": 30}
    PACKAGE_LABEL = {"basic": "أساسية (3 أيام)", "pro": "احترافية (7 أيام)", "vip": "VIP (30 يوم)"}

    async with Session() as s:
        areq = (await s.execute(select(AdRequest).where(AdRequest.id == areq_id))).scalar_one_or_none()
        if not areq or areq.status != "pending":
            return await cb.answer("Not found أو تمت معالجته.", show_alert=True)

        days = PACKAGE_DAYS.get(areq.package_name, 3)
        label = PACKAGE_LABEL.get(areq.package_name, "أساسية")
        areq.status = "approved"

        ptitle, new_until = None, None
        if areq.ad_type == "product":
            prod = (await s.execute(select(Product).where(Product.id == areq.target_id, Product.is_deleted.is_(False)))).scalar_one_or_none()
            if prod:
                now = utcnow()
                base = prod.featured_until if (prod.featured_until and prod.featured_until > now) else now
                prod.featured_until = base + timedelta(days=days)
                ptitle, new_until = prod.title, prod.featured_until
        else:
            # Credit user balance only if this was a top-up rather than an already-applied product boost
            u = (await s.execute(select(User).where(User.tg_id == areq.user_tg_id))).scalar_one_or_none()
            if u:
                u.ad_credits = float(u.ad_credits or 0.0) + float(areq.price)

        await s.commit()
        user_id = areq.user_tg_id

    if user_id:
        with suppress(Exception):
            txt = f"✅ تم تأكيد دفعك! (باقة {label})"
            if ptitle and new_until:
                txt += f"\n⭐ منتجك <b>{esc(ptitle)}</b> أصبح مميزاً لمدة <b>{days}</b> أيام، حتى <b>{new_until.strftime('%Y-%m-%d')}</b>."
            await cb.bot.send_message(user_id, txt)

    await cb.answer(f"✅ تم التأكيد ({days} يوم).", show_alert=True)
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=None)


@seller_router.callback_query(F.data.startswith("admin:reject_payment:"))
async def admin_reject_payment(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    areq_id = int(cb.data.split(":")[2])
    async with Session() as s:
        areq = (await s.execute(select(AdRequest).where(AdRequest.id == areq_id))).scalar_one_or_none()
        if not areq or areq.status != "pending":
            return await cb.answer("Not found.", show_alert=True)
        areq.status = "rejected"
        await s.commit()
        user_id = areq.user_tg_id
    with suppress(Exception):
        await cb.bot.send_message(user_id, "❌ تم رفض إثبات الدفع. يرجى التواصل مع الدعم.")
    await cb.answer("❌ تم الرفض.", show_alert=True)
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=None)


# ════════════════════════════════════════════════════════════════════
# 9. BACKGROUND TASKS, ERROR HANDLER & ENTRYPOINT (main.py)
# ════════════════════════════════════════════════════════════════════

async def abandoned_cart_task(bot: Bot) -> None:
    """Remind users about forgotten cart items every 30 minutes (N+1 free)."""
    while True:
        try:
            await asyncio.sleep(1800)
            logger.info("Checking for abandoned carts...")

            async with Session() as s:
                cutoff = utcnow() - timedelta(hours=2)
                stmt = (
                    select(CartItem)
                    .options(selectinload(CartItem.product))
                    .join(Product, CartItem.product_id == Product.id)
                    .where(
                        CartItem.created_at <= cutoff,
                        CartItem.reminded.is_(False),
                        Product.status == "approved",
                        Product.is_deleted.is_(False),
                        Product.is_out_of_stock.is_(False),
                    )
                )
                items = (await s.execute(stmt)).scalars().all()
                if not items:
                    continue

                by_user: dict[int, list[CartItem]] = {}
                for it in items:
                    by_user.setdefault(it.user_tg_id, []).append(it)

                users_rows = (
                    await s.execute(select(User).where(User.tg_id.in_(list(by_user.keys()))))
                ).scalars().all()
                users_by_id = {u.tg_id: u for u in users_rows}

                sent_any = False
                for uid, user_items in by_user.items():
                    try:
                        user = users_by_id.get(uid)
                        if not user:
                            continue
                        lang = user.lang or DEFAULT_LANG
                        titles = [ci.product.title for ci in user_items if ci.product]
                        if not titles:
                            continue
                        shown = esc(titles[0])
                        if len(titles) > 1:
                            shown += f" (+{len(titles) - 1})"
                        msg = t(
                            lang,
                            "abandoned_cart_msg",
                            name=esc(user.saved_name or "المستخدم"),
                            product=shown,
                        )
                        kb = InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text=t(lang, "btn_cart"), callback_data="redirect_cart")
                        ]])
                        await bot.send_message(uid, msg, reply_markup=kb)
                        for ci in user_items:
                            ci.reminded = True
                        sent_any = True
                    except TelegramRetryAfter as e:
                        await asyncio.sleep(e.retry_after + 0.5)
                    except TelegramAPIError as e:
                        logger.warning(f"TelegramAPIError reminding {uid}: {e}")
                    except Exception:
                        logger.exception(f"Error reminding {uid}")

                if sent_any:
                    await s.commit()

        except asyncio.CancelledError:
            logger.info("abandoned_cart_task cancelled")
            raise
        except Exception:
            logger.exception("Unexpected error in abandoned_cart_task")


async def global_error_handler(event: ErrorEvent) -> bool:
    logger.exception("Unhandled error: %s", event.exception)
    upd = event.update
    chat_id: int | None = None
    callback = None
    try:
        if upd.message:
            chat_id = upd.message.chat.id
        elif upd.callback_query:
            chat_id = upd.callback_query.from_user.id
            callback = upd.callback_query
        elif upd.inline_query:
            return True
    except Exception:
        pass
    if callback is not None:
        with suppress(Exception):
            await callback.answer("حدث خطأ غير متوقع", show_alert=False)
    if chat_id:
        with suppress(Exception):
            await event.bot.send_message(chat_id, "⚠️ حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.")
    return True


async def set_bot_commands(bot: Bot) -> None:
    with suppress(TelegramAPIError):
        await bot.set_my_commands([
            BotCommand(command="start", description="بدء / Start"),
            BotCommand(command="cancel", description="إلغاء / Cancel"),
        ])


async def main() -> None:
    global BOT_USERNAME

    await init_db()
    if Session is None:
        raise RuntimeError("Database initialization failed (Session is None)")
    await seed_categories(Session)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    bg_task: asyncio.Task | None = None

    try:
        me = await bot.get_me()
        BOT_USERNAME = me.username or ""
        logger.info(f"Bot started as @{BOT_USERNAME}")

        await set_bot_commands(bot)
        with suppress(TelegramAPIError):
            await bot.delete_webhook(drop_pending_updates=True)

        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(buyer_router)
        dp.include_router(seller_router)
        dp.errors.register(global_error_handler)

        bg_task = asyncio.create_task(abandoned_cart_task(bot))
        await dp.start_polling(bot)

    finally:
        if bg_task is not None:
            bg_task.cancel()
            with suppress(asyncio.CancelledError):
                await bg_task
        with suppress(Exception):
            await bot.session.close()
        if _engine is not None:
            with suppress(Exception):
                await _engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopped")
