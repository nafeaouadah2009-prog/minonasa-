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
import sqlite3
import tempfile
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
    FSInputFile,
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
    and_,
    case,
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
MAX_STORES_VIP: Final[int] = 5
MAX_PRODUCT_PHOTOS: Final[int] = 3

AD_PACKAGES: Final[dict[str, dict[str, Any]]] = {
    "basic": {"days": 3, "price": 1000.0, "label": "أساسية (3 أيام)"},
    "pro": {"days": 7, "price": 2000.0, "label": "احترافية (7 أيام)"},
    "vip": {"days": 30, "price": 7000.0, "label": "VIP (30 يوم)"},
}

VIP_PLANS: Final[dict[str, dict[str, Any]]] = {
    "vip_30": {"days": 30, "price": 3000.0, "label": "👑 باقة VIP شهرية (30 يوم) - 3000 دج"},
    "vip_90": {"days": 90, "price": 7500.0, "label": "👑 باقة VIP ربع سنوية (90 يوم) - 7500 دج"},
}

ALGERIA_WILAYAS: Final[dict[str, str]] = {
    "01": "أدرار", "02": "الشلف", "03": "الأغواط", "04": "أم البواقي", "05": "باتنة",
    "06": "بجاية", "07": "بسكرة", "08": "بشار", "09": "البليدة", "10": "البويرة",
    "11": "تمنراست", "12": "تبسة", "13": "تلمسان", "14": "تيارت", "15": "تيزي وزو",
    "16": "الجزائر", "17": "الجلفة", "18": "جيجل", "19": "سطيف", "20": "سعيدة",
    "21": "سكيكدة", "22": "سيدي بلعباس", "23": "عنابة", "24": "قالمة", "25": "قسنطينة",
    "26": "المدية", "27": "مستغانم", "28": "المسيلة", "29": "معسكر", "30": "ورقلة",
    "31": "وهران", "32": "البيض", "33": "إليزي", "34": "برج بوعريريج", "35": "بومرداس",
    "36": "الطارف", "37": "تندوف", "38": "تيسمسيلت", "39": "الوادي", "40": "خنشلة",
    "41": "سوق أهراس", "42": "تيبازة", "43": "ميلة", "44": "عين الدفلى", "45": "النعامة",
    "46": "عين تموشنت", "47": "غرداية", "48": "غليزان", "49": "تيميمون", "50": "برج باجي مختار",
    "51": "أولاد جلال", "52": "بني عباس", "53": "عين صالح", "54": "عين قزام", "55": "تقرت",
    "56": "جانت", "57": "المغير", "58": "المنيعة",
}

ALGERIA_WILAYAS_FR: Final[dict[str, str]] = {
    "01": "Adrar", "02": "Chlef", "03": "Laghouat", "04": "Oum El Bouaghi", "05": "Batna",
    "06": "Béjaïa", "07": "Biskra", "08": "Béchar", "09": "Blida", "10": "Bouira",
    "11": "Tamanrasset", "12": "Tébessa", "13": "Tlemcen", "14": "Tiaret", "15": "Tizi Ouzou",
    "16": "Alger", "17": "Djelfa", "18": "Jijel", "19": "Sétif", "20": "Saïda",
    "21": "Skikda", "22": "Sidi Bel Abbès", "23": "Annaba", "24": "Guelma", "25": "Constantine",
    "26": "Médéa", "27": "Mostaganem", "28": "M'Sila", "29": "Mascara", "30": "Ouargla",
    "31": "Oran", "32": "El Bayadh", "33": "Illizi", "34": "Bordj Bou Arréridj", "35": "Boumerdès",
    "36": "El Tarf", "37": "Tindouf", "38": "Tissemsilt", "39": "El Oued", "40": "Khenchela",
    "41": "Souk Ahras", "42": "Tipaza", "43": "Mila", "44": "Aïn Defla", "45": "Naâma",
    "46": "Aïn Témouchent", "47": "Ghardaïa", "48": "Relizane", "49": "Timimoun", "50": "Bordj Badji Mokhtar",
    "51": "Ouled Djellal", "52": "Béni Abbès", "53": "In Salah", "54": "In Guezzam", "55": "Touggourt",
    "56": "Djanet", "57": "El M'Ghair", "58": "El Meniaa",
}


def wilaya_label(code: str, lang: str = "ar") -> str:
    raw = (code or "").strip()
    c = raw.zfill(2) if raw.isdigit() else raw
    lookup = ALGERIA_WILAYAS_FR if lang in ("fr", "en") else ALGERIA_WILAYAS
    name = lookup.get(c)
    return f"{c} - {name}" if name else (raw or "-")

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
        "btn_vip_pkg": "👑 باقة VIP",
        "btn_wallet": "💳 محفظتي",
        "btn_admin_channel": "📢 قناة النشر التلقائي",
        "btn_admin_backup": "💾 نسخ احتياطي",
        "analytics_period_7": "📅 آخر 7 أيام",
        "analytics_period_30": "🗓️ آخر 30 يوماً",
        "analytics_period_0": "♾️ كل الأوقات",
        "analytics_export_csv": "📥 تصدير تقرير التحليلات (CSV)",
        "analytics_refresh": "🔄 تحديث التقرير",
        "analytics_store_title": "📊 <b>تقارير وتحليلات المتجر</b>",
        "analytics_platform_title": "📊 <b>تقارير وتحليلات المنصة</b>",
        "analytics_period_lbl": "⏱️ الفترة",
        "analytics_overview": "📌 <b>ملخص الأداء:</b>",
        "analytics_orders_breakdown": "📦 <b>توزيع حالات الطلبات:</b>",
        "analytics_daily_trend": "📈 <b>تطور المبيعات اليومي:</b>",
        "analytics_top_wilayas": "🗺️ <b>أكثر الولايات طلباً:</b>",
        "analytics_delivery_split": "🚚 <b>توزيع طرق التوصيل:</b>",
        "analytics_top_products": "🏆 <b>أكثر المنتجات مبيعاً وربحاً:</b>",
        "analytics_top_stores": "🏪 <b>أفضل المتاجر مبيعاً:</b>",
        "analytics_no_data": "لا توجد بيانات كافية في هذه الفترة.",
        "analytics_home_lbl": "🏠 للمنزل",
        "analytics_desk_lbl": "🏢 للمكتب (Stop Desk)",
        "analytics_csv_caption": "📊 <b>تقرير التحليلات الشامل ({period})</b>\n📅 {date} UTC",
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
        "btn_vip_pkg": "👑 VIP Plan",
        "btn_wallet": "💳 My Wallet",
        "btn_admin_channel": "📢 Auto-Post Channel",
        "btn_admin_backup": "💾 DB Backup",
        "analytics_period_7": "📅 Last 7 days",
        "analytics_period_30": "🗓️ Last 30 days",
        "analytics_period_0": "♾️ All time",
        "analytics_export_csv": "📥 Export Analytics (CSV)",
        "analytics_refresh": "🔄 Refresh report",
        "analytics_store_title": "📊 <b>Store Analytics & Reports</b>",
        "analytics_platform_title": "📊 <b>Platform Analytics & Reports</b>",
        "analytics_period_lbl": "⏱️ Period",
        "analytics_overview": "📌 <b>Performance Overview:</b>",
        "analytics_orders_breakdown": "📦 <b>Order Status Breakdown:</b>",
        "analytics_daily_trend": "📈 <b>Daily Sales Trend:</b>",
        "analytics_top_wilayas": "🗺️ <b>Top Ordering Wilayas:</b>",
        "analytics_delivery_split": "🚚 <b>Delivery Methods Split:</b>",
        "analytics_top_products": "🏆 <b>Top Products by Revenue:</b>",
        "analytics_top_stores": "🏪 <b>Top Performing Stores:</b>",
        "analytics_no_data": "No data available for this period.",
        "analytics_home_lbl": "🏠 Home Delivery",
        "analytics_desk_lbl": "🏢 Stop Desk",
        "analytics_csv_caption": "📊 <b>Full Analytics Report ({period})</b>\n📅 {date} UTC",
    },
    "fr": {
        "choose_lang": "🌐 Choisissez votre langue :",
        "lang_set": "✅ Langue définie sur le français",
        "welcome": (
            "🌟 <b>Bienvenue sur Market Bot !</b> 🌟\n\n"
            "Votre plateforme e-commerce complète sur Telegram. Que vous soyez vendeur à la recherche de clients ou acheteur en quête des meilleures offres — nous rendons votre expérience plus simple et plus rapide !\n\n"
            "🛍️ <b>Pour l'acheteur :</b> parcourez les produits, ajoutez au panier et suivez vos commandes en toute simplicité.\n"
            "🚀 <b>Pour le vendeur :</b> ouvrez votre boutique gratuitement, ajoutez vos produits et gérez vos commandes au même endroit.\n\n"
            "Choisissez dans le menu ci-dessous pour commencer 👇"
        ),
        "main_menu": "🏠 <b>Menu Principal</b>",
        "btn_buyer_section": "🛍️ Acheteur",
        "btn_seller_section": "🏪 Vendeur",
        "btn_profile_section": "👤 Mon Compte",
        "btn_admin": "👨‍💼 Admin",
        "buyer_menu_title": "🛍️ <b>Espace Acheteur</b>\n\nDécouvrez les meilleurs produits et parcourez les boutiques :",
        "seller_menu_title": "🏪 <b>Espace Vendeur</b>\n\nGérez votre boutique, vos produits et vos commandes :",
        "choose_store": "\n\nVous avez plusieurs boutiques, choisissez celle à gérer :",
        "add_new_store": "➕ Ouvrir une nouvelle boutique",
        "max_stores_reached": "⚠️ Vous avez atteint le maximum autorisé (3 boutiques)",
        "btn_browse": "🛍️ Parcourir les produits",
        "btn_browse_cats": "📂 Par catégorie",
        "btn_search": "🔎 Rechercher un produit",
        "btn_search_store": "🏪 Rechercher une boutique",
        "btn_cart": "🛒 Panier",
        "btn_my_orders": "📦 Mes commandes",
        "btn_mystore": "🏪 Ma boutique",
        "btn_become_seller": "🚀 Devenir vendeur (ouvrir une boutique)",
        "btn_account": "👤 Mon compte",
        "btn_profile": "👤 Mon profil",
        "btn_favorites": "❤️ Favoris",
        "btn_top_stores": "🏪 Annuaire des boutiques",
        "btn_support": "🆘 Support",
        "btn_lang": "🌐 Langue",
        "account_menu": "⚙️ <b>Mon Compte et Paramètres</b>\n\nAccédez à toutes vos options ici :",
        "sponsored_ad": "📢 <b>Annonce Sponsorisée</b>",
        "btn_ads_section": "📢 Publicités",
        "ads_menu_title": "📢 <b>Espace Publicités</b>\n\nDécouvrez les meilleures offres, ou faites la promotion de votre produit et de votre bot ici :",
        "btn_browse_featured": "⭐ Produits en vedette",
        "btn_browse_bot_ads": "🤖 Annonces de bots",
        "btn_create_bot_ad": "➕ Promouvoir votre bot ici",
        "btn_buy_product_ad": "📢 Mettre un produit en vedette",
        "featured_products_title": "⭐ <b>Produits en Vedette</b>\n\nCes produits sont mis en avant par leurs vendeurs :",
        "bot_ads_title": "🤖 <b>Annonces de Bots</b>\n\nDécouvrez les meilleurs bots Telegram :",
        "no_bot_ads": "Aucune annonce de bot pour le moment.",
        "bot_ad_name": "🤖 Entrez le nom du bot :",
        "bot_ad_username": "🔗 Entrez le nom d'utilisateur du bot (sans @) [ex : MonSuperBot] :",
        "bot_ad_desc": "📝 Entrez une description attractive (que fait le bot ?) :",
        "bot_ad_photo": "🖼️ Envoyez le logo ou la photo du bot (obligatoire) :",
        "bot_ad_review": "📋 <b>Aperçu de l'annonce</b>\n\nNom : {name}\nUtilisateur : @{username}\nDescription : {desc}\n\nVotre demande sera envoyée à l'administrateur pour validation.",
        "bot_ad_submitted": "✅ Annonce envoyée pour validation. Elle apparaîtra après approbation.",
        "ad_packages_title": "💎 <b>Forfaits Produit en Vedette</b>\n\nChoisissez le forfait qui vous convient pour promouvoir votre produit :",
        "ad_pkg_basic": "🥉 Basique (3 jours) - 1000 DZD",
        "ad_pkg_pro": "🥈 Pro (7 jours) - 2000 DZD",
        "ad_pkg_vip": "🥇 VIP (30 jours) - 7000 DZD",
        "ad_payment_instructions": (
            "💳 <b>Instructions de paiement :</b>\n\n"
            "1️⃣ Transférez le montant vers : <code>0000000000</code>\n"
            "2️⃣ Envoyez une capture d'écran du reçu de paiement.\n"
            "3️⃣ Après vérification, la promotion sera activée."
        ),
        "btn_send_payment_proof": "📸 Envoyer le reçu de paiement",
        "payment_proof_received": "✅ Reçu de paiement bien reçu. Il sera vérifié sous peu.",
        "btn_manage_bot_ads": "🤖 Gérer les annonces de bots",
        "btn_manage_ad_requests": "💰 Demandes de paiement",
        "bot_ads_pending": "⏳ Annonces de bots en attente :",
        "ad_requests_pending": "⏳ Demandes de paiement en attente :",
        "btn_approve_bot_ad": "✅ Approuver",
        "btn_reject_bot_ad": "❌ Rejeter",
        "btn_confirm_payment": "💰 Confirmer le paiement",
        "admin_bot_ad_view": "🤖 <b>Vérification d'annonce Bot</b>\n\nNom : {name}\nUtilisateur : @{username}\nDescription : {desc}\n",
        "admin_ad_req_view": "💰 <b>Nouvelle Demande de Paiement</b>\n\nUtilisateur : <code>{user_id}</code>\nForfait : {package}\nMontant : {price}\nType : {type}\n\nVeuillez vérifier le reçu et confirmer.",
        "btn_back": "🔙 Retour",
        "btn_cancel": "❌ Annuler",
        "btn_confirm": "✅ Confirmer",
        "btn_approve": "✅ Approuver",
        "btn_reject": "❌ Rejeter",
        "no_products": "Aucun produit disponible.",
        "all_products": "🛍️ <b>Tous les produits</b>\nDécouvrez les dernières offres :",
        "cats_browse_title": "📂 <b>Catégories</b>\nChoisissez une catégorie pour voir les produits :",
        "product": "📦 <b>{title}</b>\n\n{desc}\n\n💰 Prix : {price} {currency}\n🚚 Livraison : {delivery}\n🏪 Vendeur : {store}\n⭐ Note : {rating}{stock}{review}{vars}{flash}",
        "out_of_stock_warn": "\n\n⚠️ <b>Actuellement en rupture de stock</b>",
        "stock_left": "\n📦 Restant : {qty}",
        "vars_list": "\n🎨 Options : {vars}",
        "flash_sale_warn": "\n\n🔥 <b>Vente Flash !</b> Ancien prix : {old_price}, se termine dans {time}",
        "btn_contact": "💬 Contacter le vendeur",
        "btn_rate": "⭐ Noter la boutique",
        "btn_order": "🛒 Commander maintenant",
        "btn_add_cart": "🛒 Ajouter au panier",
        "btn_remove_fav": "💔 Retirer des favoris",
        "btn_add_fav": "❤️ Ajouter aux favoris",
        "btn_report_prod": "🚨 Signaler le produit",
        "btn_report_store": "🚨 Signaler la boutique",
        "btn_restock": "🔔 M'alerter dès le retour en stock",
        "btn_similar": "🎯 Produits similaires",
        "restock_saved": "✅ Nous vous avertirons dès que le produit sera de nouveau disponible !",
        "restock_notify": "🔔 <b>Bonne nouvelle !</b>\n\nLe produit <b>{title}</b> que vous attendiez est de nouveau disponible chez {store}.\n💰 Prix : {price}",
        "contact_methods_menu": "💬 <b>Contacter le vendeur</b>\nChoisissez un moyen de contact :",
        "contact_telegram": "✈️ Telegram",
        "contact_phone": "📞 Appel téléphonique",
        "contact_whatsapp": "🟢 WhatsApp",
        "contact_instagram": "📸 Instagram",
        "contact_not_avail": "Ce moyen de contact n'est pas disponible.",
        "fav_added": "✅ Ajouté aux favoris",
        "fav_removed": "❌ Retiré des favoris",
        "fav_empty": "Votre liste de favoris est vide.",
        "my_favorites": "❤️ <b>Vos Favoris :</b>",
        "cart_added": "✅ Ajouté au panier.",
        "cart_empty": "Votre panier est vide.",
        "my_cart": "🛒 <b>Votre Panier :</b>",
        "cart_checkout": "✅ Passer la commande",
        "cart_clear": "🗑️ Vider le panier",
        "abandoned_cart_msg": "🛒 <b>Bonjour {name}, vous avez oublié quelque chose !</b>\n\nVous avez laissé <b>{product}</b> dans votre panier. Finalisez votre commande avant rupture de stock !",
        "rating_prompt": "Choisissez votre note pour la boutique :",
        "rating_comment_prompt": "Merci ! Souhaitez-vous ajouter un commentaire ?",
        "rating_thanks": "✅ Merci ! Votre avis a bien été enregistré.",
        "rating_invalid": "Vous avez déjà noté cette boutique.",
        "btn_skip_comment": "⏭️ Passer le commentaire",
        "latest_review": "\n💬 Dernier avis : <i>{comment}</i>",
        "var_select_prompt": "🎨 Veuillez choisir l'option souhaitée :",
        "store_welcome": "🏪 <b>Votre boutique : {name} {badge}</b>\n\n📦 Produits : {products}\n👁️ Vues : {views}\n👥 Abonnés : {followers}\n⭐ Note : {rating}",
        "verified_badge": "✅",
        "btn_seller_guide": "❓ Guide vendeur",
        "seller_guide_text": "📖 <b>Guide du Vendeur</b>\n\n1️⃣ Ajoutez vos produits\n2️⃣ Partagez votre boutique\n3️⃣ Gérez vos commandes\n4️⃣ Créez des ventes flash",
        "btn_add_product": "➕ Ajouter un produit",
        "btn_my_products": "📦 Mes produits",
        "btn_my_stats": "📊 Mes statistiques",
        "btn_seller_orders": "🛒 Commandes reçues",
        "btn_promos": "🎟️ Codes promo",
        "btn_seller_broadcast": "📢 Message aux abonnés",
        "btn_share": "🔗 Partager la boutique",
        "btn_settings": "⚙️ Paramètres de la boutique",
        "btn_flash_sale": "🔥 Créer une vente flash",
        "store_create_prompt": "🏪 Entrez le nom de votre boutique :",
        "store_created": "✅ Votre boutique a été créée ! Vous êtes maintenant vendeur.",
        "share_menu": "🔗 <b>Partager votre boutique</b>\n\nChoisissez une méthode de partage :",
        "btn_share_post": "📝 Envoyer une publication prête",
        "btn_share_qr": "📸 Générer le QR code",
        "btn_custom_slug": "🔗 Personnaliser le lien",
        "btn_custom_text": "✏️ Personnaliser le texte",
        "qr_caption": "📸 Code QR de : <b>{name}</b>\n\nScannez-le avec votre caméra pour ouvrir la boutique.",
        "inline_share_text": "🛍️ <b>Bienvenue chez {name} !</b>\n\n{store_bio}\n\n⭐ Note : {rating}\n👥 Abonnés : {followers}\n\nAppuyez ci-dessous pour découvrir nos produits :",
        "inline_share_btn": "🛍️ Ouvrir la boutique",
        "enter_custom_slug": "🔗 Entrez un identifiant personnalisé (lettres, chiffres, tiret bas ; pas uniquement des chiffres).\nExemple : <code>ma_boutique_2024</code>",
        "slug_taken": "❌ Ce nom est déjà pris, essayez-en un autre.",
        "slug_success": "✅ Lien personnalisé ! Votre nouveau lien :\nhttps://t.me/{bot_username}?start=store_{slug}",
        "enter_custom_share_text": "✏️ Envoyez le texte que vous souhaitez afficher avec le lien de votre boutique :",
        "share_text_success": "✅ Texte de partage enregistré avec succès.",
        "top_stores_title": "🏪 <b>Annuaire des Meilleures Boutiques</b>\n\nDécouvrez les boutiques les plus actives :",
        "top_stores_empty": "Aucune boutique active pour le moment.",
        "store_welcome_deeplink": "👋 Bienvenue chez <b>{name} {badge}</b> !\n\n{store_bio}\n\n⭐ Note : {rating}\n\nDécouvrez nos produits :",
        "settings_menu": "⚙️ <b>Paramètres de la Boutique</b>\nChoisissez ce que vous voulez modifier :",
        "btn_edit_name": "✏️ Modifier le nom",
        "btn_edit_bio": "📝 Modifier la description",
        "btn_edit_logo": "🖼️ Modifier le logo",
        "btn_edit_contacts": "📞 Modifier les contacts",
        "enter_new_name": "Entrez le nouveau nom de la boutique :",
        "enter_new_bio": "Entrez la nouvelle description de la boutique :",
        "send_logo": "Envoyez une photo pour le logo de votre boutique :",
        "contacts_menu": "📞 <b>Moyens de Contact</b>\nChoisissez le contact à modifier :",
        "enter_contact_tg": "Entrez votre nom d'utilisateur Telegram (ex : @utilisateur) :",
        "enter_contact_phone": "Entrez votre numéro de téléphone (ex : +213555123456) :",
        "enter_contact_whatsapp": "Entrez votre numéro WhatsApp (ex : +213555123456) :",
        "enter_contact_insta": "Entrez le lien ou le compte Instagram :",
        "settings_updated": "✅ Mis à jour avec succès !",
        "manage_product": "⚙️ <b>Gérer le produit : {title}</b>",
        "btn_edit_price": "💰 Modifier le prix",
        "btn_edit_desc": "📝 Modifier la description",
        "btn_edit_stock": "📦 Modifier le stock",
        "btn_toggle_stock": "📦 Changer disponibilité",
        "btn_delete_prod": "🗑️ Supprimer le produit",
        "enter_new_price": "Entrez le nouveau prix (nombre positif > 0) :",
        "enter_new_desc": "Entrez la nouvelle description :",
        "enter_new_stock": "Entrez la nouvelle quantité (entier >= 0) :",
        "prod_updated": "✅ Mis à jour.",
        "prod_deleted": "🗑️ Produit supprimé avec succès.",
        "stock_out": "Le produit est marqué en rupture de stock.",
        "stock_in": "Le produit est marqué disponible.",
        "confirm_delete": "Êtes-vous sûr de vouloir supprimer ?",
        "btn_yes_delete": "⚠️ Oui, supprimer",
        "my_products_list": "📦 <b>Vos produits :</b>\nAppuyez sur un produit pour le gérer :",
        "profile_menu": "👤 <b>Votre Profil</b>\n\nNom : {name}\nTéléphone : {phone}\nAdresse : {address}\n\nMettez à jour vos infos pour commander plus vite :",
        "btn_edit_profile_name": "✏️ Modifier le nom",
        "btn_edit_profile_phone": "✏️ Modifier le téléphone",
        "btn_edit_profile_address": "✏️ Modifier l'adresse",
        "enter_p_name": "Entrez votre nom complet :",
        "enter_p_phone": "Entrez votre numéro de téléphone :",
        "enter_p_address": "Entrez votre adresse complète :",
        "profile_updated": "✅ Vos informations ont été enregistrées.",
        "buyer_orders_list": "📦 <b>Historique de vos commandes :</b>\nAppuyez sur une commande pour voir les détails :",
        "buyer_orders_empty": "Vous n'avez aucune commande précédente.",
        "buyer_order_details": "📋 <b>Votre commande #{id}</b>\n\n📦 Produit : {product}\n🎨 Option : {variation}\n💰 Prix : {price}\n🚚 Livraison : {delivery}\n📌 Statut : {status}\n📅 Date : {date}",
        "order_status_notify": "🔔 <b>Mise à jour de votre commande #{id}</b>\n\nBonjour {name}, le statut de votre commande est maintenant : {status}",
        "btn_use_saved": "✅ Utiliser mon adresse enregistrée",
        "btn_change_status": "🔄 Changer le statut",
        "status_pending": "⏳ En attente",
        "status_shipped": "🚚 Expédiée",
        "status_completed": "✅ Livrée",
        "status_cancelled": "❌ Annulée",
        "status_updated": "✅ Statut de la commande mis à jour.",
        "orders_list": "🛒 <b>Vos commandes reçues :</b>\nAppuyez sur une commande pour voir les détails :",
        "order_details": "📋 <b>Détails de la commande #{id}</b>\n\n📦 Produit : {product}\n🎨 Option : {variation}\n👤 Nom : {name}\n📞 Téléphone : {phone}\n📍 Adresse : {address}\n📝 Note : {note}\n\n💰 Prix : {price}\n🚚 Livraison : {delivery}\n📌 Statut : {status}",
        "orders_empty": "Aucune commande pour le moment.",
        "btn_export_orders": "📥 Exporter les commandes (CSV)",
        "export_success": "✅ Commandes exportées avec succès !",
        "order_name": "🛒 Veuillez entrer votre <b>nom complet</b> :",
        "order_phone": "📞 Entrez votre <b>numéro de téléphone</b> :",
        "order_address": "📍 Entrez votre <b>adresse</b> détaillée :",
        "order_note": "📝 Une remarque supplémentaire ? (Envoyez ou passez) :",
        "btn_skip_note": "⏭️ Passer la remarque",
        "order_promo": "🎟️ Avez-vous un code promo ? Envoyez-le maintenant ou passez :",
        "btn_skip_promo": "⏭️ Passer (sans code)",
        "invalid_promo": "❌ Code promo invalide ou inapplicable. Réessayez ou passez :",
        "promo_applied": "✅ Réduction appliquée ! Nouveau prix : {price}",
        "order_success": "✅ Votre commande a été envoyée au vendeur ! Il vous contactera bientôt.",
        "new_order_notify": "🔔 <b>Nouvelle commande reçue !</b>\n\n📦 Produit : {product}\n🎨 Option : {variation}\n👤 Nom : {name}\n📞 Téléphone : {phone}\n📍 Adresse : {address}\n📝 Note : {note}\n💰 Prix : {price}\n🚚 Livraison : {delivery}",
        "public_store": "🏪 <b>Boutique : {name} {badge}</b>\n📝 {bio}\n⭐ Note : {rating}\n👥 Abonnés : {followers}\n\nChoisissez un produit :",
        "btn_follow": "🔔 Suivre la boutique",
        "btn_unfollow": "🔕 Ne plus suivre",
        "followed": "✅ Vous suivez maintenant cette boutique.",
        "unfollowed": "❌ Abonnement annulé.",
        "new_prod_follower_notify": "🔔 <b>Nouveau produit !</b>\n\nLa boutique <b>{store}</b> a ajouté un produit :\n📦 {product}\n💰 {price}",
        "store_search_prompt": "🏪 Entrez le nom de la boutique à rechercher :",
        "store_search_results": "🏪 <b>Résultats de recherche des boutiques :</b>",
        "store_search_empty": "Aucune boutique trouvée avec ce nom.",
        "report_prompt": "🚨 Veuillez indiquer le motif du signalement (ex : arnaque, produit contrefait...) :",
        "report_sent": "✅ Signalement envoyé à l'administration. Merci !",
        "report_new_admin": "🚨 <b>Nouveau Signalement !</b>\n\nType : {type}\nMotif : {reason}\n\nLien : {link}",
        "promo_manage": "🎟️ <b>Codes Promo</b>\nChoisissez une action :",
        "btn_add_promo": "➕ Ajouter un code promo",
        "btn_list_promos": "📋 Vos codes actifs",
        "promo_add_prompt": "Entrez le code et le pourcentage de réduction (1-99) séparés par un espace.\nExemple : <code>PROMO20 20</code>",
        "promo_added": "✅ Code promo ajouté.",
        "promo_deleted": "🗑️ Code promo supprimé.",
        "promos_list": "📋 <b>Codes promo :</b>\nAppuyez sur un code pour le supprimer :",
        "add_category": "📂 Choisissez une catégorie pour votre produit :",
        "btn_skip_category": "⏭️ Sans catégorie",
        "add_title": "📝 Entrez le nom du produit :",
        "add_desc": "📝 Entrez la description du produit :",
        "add_price": "💰 Entrez le prix (nombre positif > 0) :",
        "add_delivery_fee": "🚚 Entrez les frais de livraison (0 si gratuit) :",
        "add_stock": "📦 Entrez la quantité en stock (entier >= 1) :",
        "add_variations": "🎨 Entrez les options du produit (ex : Rouge,Bleu,Vert) séparées par une virgule, ou passez :",
        "btn_skip_vars": "⏭️ Passer (sans options)",
        "add_photo": "🖼️ Envoyez la photo <b>principale</b> du produit :",
        "add_photo_2": "🖼️ Envoyez la <b>2e</b> photo (facultatif), ou passez :",
        "add_photo_3": "🖼️ Envoyez la <b>3e</b> photo (facultatif), ou passez :",
        "btn_skip_photo": "⏭️ Passer la photo",
        "add_review": "📋 <b>Récapitulatif du Produit</b>\n\nNom : {title}\nCatégorie : {category}\nPrix : {price}\nLivraison : {delivery}\nQuantité : {stock}\nOptions : {vars}\n\nLe produit sera envoyé pour validation.",
        "product_submitted": "✅ Produit envoyé pour validation.",
        "product_approved_notify": "✅ Votre produit a été approuvé : {title}",
        "product_rejected_notify": "❌ Votre produit a été refusé : {title}\nMotif : {reason}",
        "flash_sale_menu": "🔥 <b>Ventes Flash</b>\n\nChoisissez un produit pour lancer une vente flash :",
        "flash_sale_select_prod": "Choisissez le produit :",
        "flash_sale_enter_price": "Entrez le prix promo (> 0 et inférieur au prix d'origine) :",
        "flash_sale_enter_hours": "Entrez la durée de l'offre en heures (de 1 à 720) :",
        "flash_sale_created": "✅ Vente flash activée avec succès !",
        "flash_sale_active": "🔥 Vente flash",
        "stats": "📊 <b>Statistiques de la Boutique</b>\n\n👁️ Vues : {views}\n📦 Produits : {products}\n🛒 Commandes : {orders}\n💵 Chiffre d'affaires : {revenue}\n⭐ Note : {rating}\n\n🏆 <b>Meilleures ventes :</b>\n{top}",
        "top_prod_line": "• {name} ({count} commandes)\n",
        "ads_info": "📢 <b>Publicités en Vedette</b>",
        "admin_panel": "👨‍💼 <b>Panneau d'Administration</b>",
        "btn_pending": "⏳ Produits en attente",
        "btn_broadcast": "📢 Diffusion générale",
        "btn_manage_cats": "📂 Gérer les catégories",
        "btn_global_stats": "📊 Statistiques plateforme",
        "btn_reports": "🚨 Signalements",
        "btn_tickets": "🎫 Tickets support",
        "btn_manage_stores": "🏪 Gérer les boutiques",
        "btn_verify": "✅ Certifier la boutique",
        "btn_unverify": "❌ Retirer la certification",
        "admin_stores_list": "🏪 <b>Liste des Boutiques :</b>\nAppuyez sur une boutique pour la gérer :",
        "admin_store_view": "🏪 <b>Gérer la boutique : {name}</b>\n\n👤 Propriétaire : <code>{owner_id}</code>\n📦 Produits : {products}\n✅ Statut : {status}",
        "pending_empty": "✅ Aucun produit en attente.",
        "reject_reason": "Entrez le motif du refus :",
        "approved": "✅ Approuvé.",
        "rejected": "❌ Refusé.",
        "search_prompt": "🔎 Entrez un terme de recherche :",
        "search_empty": "Aucun résultat trouvé.",
        "my_products_empty": "Aucun produit pour le moment.",
        "cancelled": "❌ Annulé.",
        "not_admin": "Accès non autorisé.",
        "search_results": "🔎 Résultats de recherche :",
        "share_text": "Découvrez mes produits dans ma boutique :",
        "page_info": "Page {current} sur {total}",
        "btn_next": "➡️ Suivant",
        "btn_prev": "⬅️ Précédent",
        "broadcast_prompt": "📢 Envoyez le message à diffuser à tous les utilisateurs :",
        "broadcast_started": "⏳ Envoi en cours...",
        "broadcast_done": "✅ Diffusion terminée auprès de {count} utilisateurs.",
        "seller_broadcast_prompt": "📢 Envoyez le message à diffuser aux abonnés de votre boutique :",
        "seller_broadcast_done": "✅ Message envoyé à {count} abonnés.",
        "cats_manage": "📂 <b>Gestion des Catégories</b>",
        "btn_add_cat": "➕ Ajouter une catégorie",
        "cat_add_prompt": "Entrez les noms de la catégorie (Arabe, Anglais, Français) séparés par une virgule :\nExemple : <code>سيارات,Cars,Voitures</code>",
        "cat_added": "✅ Catégorie ajoutée.",
        "cat_deleted": "🗑️ Catégorie supprimée. (Les produits ne sont plus catégorisés)",
        "cat_del_confirm": "Êtes-vous sûr de vouloir supprimer cette catégorie ?",
        "global_stats": "📊 <b>Statistiques de la Plateforme</b>\n\n👥 Utilisateurs : {users}\n🏪 Boutiques : {stores}\n📦 Produits : {products}\n🛒 Commandes : {orders}",
        "reports_list": "🚨 <b>Signalements en attente :</b>",
        "reports_empty": "✅ Aucun signalement en attente.",
        "report_resolved": "✅ Signalement résolu.",
        "support_msg": "🆘 <b>Support Technique</b>\n\nVous pouvez envoyer votre question ou problème à l'administration, et vous recevrez une réponse ici dans le bot.",
        "btn_new_ticket": "📝 Ouvrir un ticket",
        "btn_my_tickets": "📋 Mes tickets",
        "ticket_subject": "Entrez un bref sujet pour votre demande :",
        "ticket_body": "Décrivez maintenant votre problème en détail (texte ou photo) :",
        "ticket_created": "✅ Ticket #{id} créé. Nous vous répondrons rapidement.",
        "ticket_reply_from_admin": "💬 <b>Réponse du support sur votre ticket #{id} :</b>\n\n{text}",
        "tickets_empty": "Vous n'avez aucun ticket.",
        "ticket_status_open": "🟢 Ouvert",
        "ticket_status_closed": "🔴 Fermé",
        "btn_reply_ticket": "↩️ Répondre",
        "btn_close_ticket": "🔒 Fermer le ticket",
        "ticket_closed": "🔒 Ticket fermé.",
        "ticket_reply_prompt": "Entrez votre réponse au ticket :",
        "btn_vip_pkg": "👑 Forfait VIP",
        "btn_wallet": "💳 Mon Portefeuille",
        "btn_admin_channel": "📢 Canal Auto-Post",
        "btn_admin_backup": "💾 Sauvegarde BDD",
        "analytics_period_7": "📅 7 derniers jours",
        "analytics_period_30": "🗓️ 30 derniers jours",
        "analytics_period_0": "♾️ Tout le temps",
        "analytics_export_csv": "📥 Exporter les analyses (CSV)",
        "analytics_refresh": "🔄 Actualiser",
        "analytics_store_title": "📊 <b>Analyses et Rapports de la Boutique</b>",
        "analytics_platform_title": "📊 <b>Analyses et Rapports de la Plateforme</b>",
        "analytics_period_lbl": "⏱️ Période",
        "analytics_overview": "📌 <b>Résumé des Performances :</b>",
        "analytics_orders_breakdown": "📦 <b>Répartition des Commandes :</b>",
        "analytics_daily_trend": "📈 <b>Tendance des Ventes :</b>",
        "analytics_top_wilayas": "🗺️ <b>Top Wilayas Commandées :</b>",
        "analytics_delivery_split": "🚚 <b>Modes de Livraison :</b>",
        "analytics_top_products": "🏆 <b>Meilleurs Produits (CA) :</b>",
        "analytics_top_stores": "🏪 <b>Meilleures Boutiques (CA) :</b>",
        "analytics_no_data": "Aucune donnée disponible pour cette période.",
        "analytics_home_lbl": "🏠 À domicile",
        "analytics_desk_lbl": "🏢 Stop Desk",
        "analytics_csv_caption": "📊 <b>Rapport d'Analyses Complet ({period})</b>\n📅 {date} UTC",
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
    saved_wilaya: Mapped[str] = mapped_column(String(60), default="")
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
    default_desk_fee: Mapped[float] = mapped_column(Float, default=0.0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    vip_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    products = relationship("Product", back_populates="store", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="store", cascade="all, delete-orphan")
    followers = relationship("StoreFollower", back_populates="store", cascade="all, delete-orphan")
    promos = relationship("PromoCode", back_populates="store", cascade="all, delete-orphan")
    delivery_rates = relationship("StoreDeliveryRate", back_populates="store", cascade="all, delete-orphan")


class StoreDeliveryRate(Base):
    __tablename__ = "store_delivery_rates"
    __table_args__ = (
        UniqueConstraint("store_id", "wilaya_code", name="uq_delivery_store_wilaya"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    wilaya_code: Mapped[str] = mapped_column(String(10), index=True)
    home_fee: Mapped[float] = mapped_column(Float, default=0.0)
    desk_fee: Mapped[float] = mapped_column(Float, default=0.0)

    store = relationship("Store", back_populates="delivery_rates")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


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
    buyer_wilaya: Mapped[str] = mapped_column(String(60), default="")
    buyer_address: Mapped[str] = mapped_column(Text)
    buyer_note: Mapped[str] = mapped_column(Text, default="")
    variation: Mapped[str] = mapped_column(String(100), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    delivery_type: Mapped[str] = mapped_column(String(20), default="home")
    tracking_info: Mapped[str] = mapped_column(String(300), default="")
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
    quantity: Mapped[int] = mapped_column(Integer, default=1)
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
    payment_proof: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


async def _ensure_schema_columns(conn) -> None:
    """Safely add new columns if upgrading an existing market_v10.db file."""
    migrations = [
        ("users", "saved_wilaya", "VARCHAR(60) DEFAULT ''"),
        ("stores", "default_desk_fee", "FLOAT DEFAULT 0.0"),
        ("stores", "vip_until", "DATETIME"),
        ("stores", "auto_approve", "BOOLEAN DEFAULT 0"),
        ("products", "is_deleted", "BOOLEAN DEFAULT 0"),
        ("cart_items", "quantity", "INTEGER DEFAULT 1"),
        ("orders", "store_id", "INTEGER"),
        ("orders", "product_title", "VARCHAR(200) DEFAULT ''"),
        ("orders", "product_currency", f"VARCHAR(10) DEFAULT '{DEFAULT_CURRENCY}'"),
        ("orders", "quantity", "INTEGER DEFAULT 1"),
        ("orders", "buyer_wilaya", "VARCHAR(60) DEFAULT ''"),
        ("orders", "delivery_type", "VARCHAR(20) DEFAULT 'home'"),
        ("orders", "tracking_info", "VARCHAR(300) DEFAULT ''"),
        ("ad_requests", "payment_proof", "VARCHAR(200) DEFAULT ''"),
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
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
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
    title = State()
    price = State()
    desc = State()
    stock = State()
    category = State()
    photo_upload = State()


class OrderFSM(StatesGroup):
    name = State()
    phone = State()
    wilaya = State()
    delivery_type = State()
    address = State()
    note = State()
    promo = State()


class DeliveryRateFSM(StatesGroup):
    default_home = State()
    default_desk = State()
    wilaya_rate = State()


class OrderShipFSM(StatesGroup):
    tracking = State()


class WalletTopupFSM(StatesGroup):
    custom_amount = State()
    proof = State()


class AdminChannelFSM(StatesGroup):
    channel_id = State()


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


class StoreVipFSM(StatesGroup):
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


def is_store_vip(store: Optional[Store]) -> bool:
    return bool(store and store.vip_until and store.vip_until > utcnow())


def store_badges(store: Optional[Store], lang: str) -> str:
    if not store:
        return ""
    parts = []
    if is_store_vip(store):
        parts.append("👑")
    if store.verified or is_store_vip(store):
        parts.append(t(lang, "verified_badge"))
    return " ".join(parts)


async def user_max_stores(tg_id: int) -> int:
    stores = await get_stores_by_owner(tg_id)
    if any(is_store_vip(st) for st in stores):
        return MAX_STORES_VIP
    return MAX_STORES_PER_USER


async def get_setting(key: str, default: str = "") -> str:
    async with Session() as s:
        row = await s.get(AppSetting, key)
        return row.value if row else default


async def set_setting(key: str, value: str) -> None:
    async with Session() as s:
        row = await s.get(AppSetting, key)
        if row:
            row.value = value
        else:
            s.add(AppSetting(key=key, value=value))
        await s.commit()


async def calculate_delivery_fee(
    s,
    store_id: int,
    product_delivery_fee: float,
    wilaya_code: str,
    delivery_type: str,
) -> float:
    """Compute delivery fee: StoreDeliveryRate(wilaya) -> Store default -> Product delivery_fee."""
    code = (wilaya_code or "").strip().zfill(2) if (wilaya_code or "").strip().isdigit() else ""
    if code:
        rate = (
            await s.execute(
                select(StoreDeliveryRate).where(
                    StoreDeliveryRate.store_id == store_id,
                    StoreDeliveryRate.wilaya_code == code,
                )
            )
        ).scalar_one_or_none()
        if rate:
            return float(rate.desk_fee if delivery_type == "desk" else rate.home_fee)
    store = await s.get(Store, store_id)
    if store:
        if delivery_type == "desk" and store.default_desk_fee > 0:
            return float(store.default_desk_fee)
        if delivery_type == "home" and store.delivery_fee > 0:
            return float(store.delivery_fee)
    return float(product_delivery_fee or 0.0)


def build_wilaya_kb(page: int, prefix: str, select_prefix: str, back_cb: str, lang: str) -> InlineKeyboardMarkup:
    """Paginated 58 Algeria Wilayas keyboard (12 per page in 2 columns)."""
    codes = sorted(ALGERIA_WILAYAS.keys())
    per_page = 12
    total_pages = max(1, math.ceil(len(codes) / per_page))
    page = max(1, min(page, total_pages))
    chunk = codes[(page - 1) * per_page : page * per_page]
    kb = []
    for i in range(0, len(chunk), 2):
        row = []
        for code in chunk[i : i + 2]:
            row.append(
                InlineKeyboardButton(
                    text=wilaya_label(code, lang),
                    callback_data=f"{select_prefix}:{code}",
                )
            )
        kb.append(row)
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text=t(lang, "btn_prev"), callback_data=f"{prefix}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text=t(lang, "btn_next"), callback_data=f"{prefix}:{page + 1}"))
    kb.append(nav)
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def _create_sqlite_backup_sync(src_path: str) -> str:
    """Consistent online SQLite backup safe under WAL mode."""
    ts = utcnow().strftime("%Y%m%d_%H%M%S")
    dst_path = os.path.join(tempfile.gettempdir(), f"market_backup_{ts}.db")
    src_conn = sqlite3.connect(src_path)
    dst_conn = sqlite3.connect(dst_path)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    return dst_path


async def send_backup_to_admins(bot: Bot, target_chat_id: Optional[int] = None, auto: bool = False) -> bool:
    if not os.path.exists(DB_PATH):
        return False
    backup_path = ""
    try:
        backup_path = await asyncio.to_thread(_create_sqlite_backup_sync, DB_PATH)
        size_kb = os.path.getsize(backup_path) / 1024.0
        caption = (
            f"💾 <b>{'نسخة احتياطية يومية تلقائية' if auto else 'نسخة احتياطية لقاعدة البيانات'}</b>\n"
            f"📅 {utcnow().strftime('%Y-%m-%d %H:%M')} UTC\n"
            f"📦 الحجم: {size_kb:.1f} KB"
        )
        recipients = [target_chat_id] if target_chat_id else list(ADMIN_IDS)
        for chat_id in recipients:
            with suppress(Exception):
                await bot.send_document(
                    chat_id,
                    FSInputFile(backup_path, filename=os.path.basename(backup_path)),
                    caption=caption,
                )
        return True
    except Exception as e:
        logger.exception(f"DB backup failed: {e}")
        return False
    finally:
        if backup_path and os.path.exists(backup_path):
            with suppress(Exception):
                os.remove(backup_path)


async def publish_product_to_channel(bot: Bot, product_id: int) -> bool:
    """Auto-publish approved product to configured platform Telegram channel."""
    channel_id = (await get_setting("auto_channel_id", "")).strip()
    if not channel_id:
        return False
    async with Session() as s:
        p = (
            await s.execute(select(Product).where(Product.id == product_id, Product.is_deleted.is_(False)))
        ).scalar_one_or_none()
        if not p or p.status != "approved":
            return False
        store = await s.get(Store, p.store_id)
        cat = await s.get(Category, p.category_id) if p.category_id else None
    badge = store_badges(store, "ar")
    store_name = f"{esc(store.name)} {badge}".strip() if store else "-"
    cat_line = f"\n📂 التصنيف: {esc(cat.name_ar)}" if cat else ""
    caption = (
        f"🆕 <b>{esc(p.title)}</b>\n\n"
        f"{esc((p.description or '')[:400])}\n\n"
        f"💰 السعر: <b>{_current_price(p):g} {esc(p.currency)}</b>\n"
        f"🚚 التوصيل: {p.delivery_fee:g} {esc(p.currency)}{cat_line}\n"
        f"🏪 المتجر: {store_name}"
    )
    deep_url = f"https://t.me/{BOT_USERNAME}?start=prod_{p.id}" if BOT_USERNAME else ""
    kb = (
        InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🛒 عرض وطلب المنتج الآن", url=deep_url)]]
        )
        if deep_url
        else None
    )
    try:
        if p.photo_file_id:
            await bot.send_photo(channel_id, photo=p.photo_file_id, caption=caption[:1024], reply_markup=kb)
        else:
            await bot.send_message(channel_id, caption, reply_markup=kb)
        return True
    except Exception as e:
        logger.warning(f"Auto-post to channel {channel_id} failed for product #{product_id}: {e}")
        return False


def _analytics_bar(value: float, max_val: float, width: int = 8) -> str:
    if max_val <= 0 or value <= 0:
        return "░" * width
    filled = max(1, min(width, int(round((value / max_val) * width))))
    return "█" * filled + "░" * (width - filled)


def _analytics_period_name(days: int, lang: str) -> str:
    if days == 7:
        return t(lang, "analytics_period_7")
    if days == 30:
        return t(lang, "analytics_period_30")
    return t(lang, "analytics_period_0")


def _analytics_kb(scope_prefix: str, csv_prefix: str, days: int, back_cb: str, lang: str) -> InlineKeyboardMarkup:
    def _mark(d: int, key: str) -> str:
        lbl = t(lang, key)
        return f"• {lbl} •" if days == d else lbl

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_mark(7, "analytics_period_7"), callback_data=f"{scope_prefix}:7"),
            InlineKeyboardButton(text=_mark(30, "analytics_period_30"), callback_data=f"{scope_prefix}:30"),
            InlineKeyboardButton(text=_mark(0, "analytics_period_0"), callback_data=f"{scope_prefix}:0"),
        ],
        [
            InlineKeyboardButton(text=t(lang, "analytics_export_csv"), callback_data=f"{csv_prefix}:{days}"),
            InlineKeyboardButton(text=t(lang, "analytics_refresh"), callback_data=f"{scope_prefix}:{days}"),
        ],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=back_cb)],
    ])


async def _fetch_analytics_orders(s, store_id: Optional[int], since: Optional[datetime], until: Optional[datetime] = None):
    stmt = (
        select(
            Order.id,
            Order.store_id,
            Order.product_id,
            Order.product_title,
            Order.quantity,
            Order.price,
            Order.delivery_fee,
            Order.status,
            Order.buyer_wilaya,
            Order.delivery_type,
            Order.created_at,
            Product.title.label("prod_title_live"),
            Product.store_id.label("prod_store_id"),
        )
        .outerjoin(Product, Order.product_id == Product.id)
    )
    if store_id is not None:
        stmt = stmt.where(or_(Order.store_id == store_id, Product.store_id == store_id))
    if since is not None:
        stmt = stmt.where(Order.created_at >= since)
    if until is not None:
        stmt = stmt.where(Order.created_at < until)
    return (await s.execute(stmt)).all()


async def _build_analytics_report(s, store_id: Optional[int], days: int, lang: str) -> str:
    """Build rich HTML analytics report for either a single store or the whole platform."""
    now = utcnow()
    since = now - timedelta(days=days) if days in (7, 30) else None
    rows = await _fetch_analytics_orders(s, store_id, since)

    prev_rev: Optional[float] = None
    if days in (7, 30):
        prev_since = now - timedelta(days=days * 2)
        prev_rows = await _fetch_analytics_orders(s, store_id, prev_since, since)
        prev_rev = sum(float(r.price or 0.0) for r in prev_rows if r.status != "cancelled")

    total_orders = len(rows)
    completed = sum(1 for r in rows if r.status == "completed")
    shipped = sum(1 for r in rows if r.status == "shipped")
    pending = sum(1 for r in rows if r.status == "pending")
    cancelled = sum(1 for r in rows if r.status == "cancelled")
    active_rows = [r for r in rows if r.status != "cancelled"]
    units_sold = sum(max(1, int(r.quantity or 1)) for r in active_rows)
    gross_rev = sum(float(r.price or 0.0) for r in active_rows)
    delivery_total = sum(float(r.delivery_fee or 0.0) for r in active_rows)
    net_prod_rev = max(0.0, gross_rev - delivery_total)
    aov = (gross_rev / len(active_rows)) if active_rows else 0.0

    success_rate = ((total_orders - cancelled) / total_orders * 100.0) if total_orders else 0.0
    cancel_rate = (cancelled / total_orders * 100.0) if total_orders else 0.0
    closed = completed + cancelled
    completion_rate = (completed / closed * 100.0) if closed else 0.0

    trend_badge = ""
    if prev_rev is not None:
        if prev_rev > 0:
            delta_pct = ((gross_rev - prev_rev) / prev_rev) * 100.0
            arrow = "📈" if delta_pct > 0 else ("📉" if delta_pct < 0 else "➖")
            trend_badge = f" ({arrow} {delta_pct:+.1f}%)"
        elif gross_rev > 0:
            trend_badge = " (📈 +100%)"

    # Delivery split
    home_cnt = sum(1 for r in active_rows if (r.delivery_type or "home") != "desk")
    desk_cnt = sum(1 for r in active_rows if (r.delivery_type or "home") == "desk")
    deliv_total_cnt = home_cnt + desk_cnt
    home_pct = (home_cnt / deliv_total_cnt * 100.0) if deliv_total_cnt else 0.0
    desk_pct = (desk_cnt / deliv_total_cnt * 100.0) if deliv_total_cnt else 0.0

    # Top 5 Wilayas
    wilaya_stats: dict[str, list[float]] = {}
    for r in active_rows:
        w = (r.buyer_wilaya or "").strip()
        if not w:
            w = "00"
        elif w.isdigit():
            w = w.zfill(2)
        entry = wilaya_stats.setdefault(w, [0.0, 0.0])
        entry[0] += 1.0
        entry[1] += float(r.price or 0.0)
    top_wilayas = sorted(wilaya_stats.items(), key=lambda kv: (kv[1][0], kv[1][1]), reverse=True)[:5]

    # Top 5 Products by revenue & count
    prod_stats: dict[str, list[float]] = {}
    for r in active_rows:
        pname = (r.prod_title_live or r.product_title or f"#{r.product_id or '?'}").strip()
        entry = prod_stats.setdefault(pname, [0.0, 0.0, 0.0])  # [orders, units, revenue]
        entry[0] += 1.0
        entry[1] += max(1, int(r.quantity or 1))
        entry[2] += float(r.price or 0.0)
    top_prods = sorted(prod_stats.items(), key=lambda kv: (kv[1][2], kv[1][0]), reverse=True)[:5]

    # Daily / Period Sales Trend (last 7 days or 4 weekly buckets for 30d)
    trend_lines: list[str] = []
    if days == 7 or (days == 0 and total_orders > 0):
        bucket_days = 7
        day_buckets: list[tuple[str, int, float]] = []
        for offset in range(bucket_days - 1, -1, -1):
            d_dt = (now - timedelta(days=offset)).date()
            cnt = 0
            rev = 0.0
            for r in active_rows:
                if r.created_at and r.created_at.date() == d_dt:
                    cnt += 1
                    rev += float(r.price or 0.0)
            day_buckets.append((d_dt.strftime("%m/%d"), cnt, rev))
        max_rev_b = max((b[2] for b in day_buckets), default=0.0)
        for lbl, cnt, rev in day_buckets:
            bar = _analytics_bar(rev, max_rev_b, 8)
            trend_lines.append(f"<code>{lbl}</code> {bar} {cnt} | {rev:,.0f} {DEFAULT_CURRENCY}")
    elif days == 30:
        week_buckets: list[tuple[str, int, float]] = []
        for w_idx in range(3, -1, -1):
            w_end = now - timedelta(days=w_idx * 7)
            w_start = w_end - timedelta(days=7)
            cnt = 0
            rev = 0.0
            for r in active_rows:
                if r.created_at and w_start <= r.created_at < w_end:
                    cnt += 1
                    rev += float(r.price or 0.0)
            lbl = f"{w_start.strftime('%d/%m')}-{w_end.strftime('%d/%m')}"
            week_buckets.append((lbl, cnt, rev))
        max_rev_b = max((b[2] for b in week_buckets), default=0.0)
        for lbl, cnt, rev in week_buckets:
            bar = _analytics_bar(rev, max_rev_b, 8)
            trend_lines.append(f"<code>{lbl}</code> {bar} {cnt} | {rev:,.0f} {DEFAULT_CURRENCY}")

    # Localized labels
    if lang == "fr":
        lbl_rev = "Chiffre d'affaires"
        lbl_net = "Revenu net produits"
        lbl_deliv = "Frais livraison"
        lbl_aov = "Panier moyen"
        lbl_orders = "Total commandes"
        lbl_units = "Unités vendues"
        lbl_conv = "Taux de conversion"
        lbl_success = "Taux de maintien"
        lbl_done_rate = "Taux de livraison"
        lbl_cancel = "Taux d'annulation"
        lbl_views = "Vues produits"
        lbl_followers = "Abonnés"
        lbl_users = "Utilisateurs"
        lbl_stores = "Boutiques"
        lbl_prods = "Produits actifs"
        lbl_new = "nouveaux"
        lbl_unknown_w = "Non précisée"
        lbl_ord_short = "cmd"
    elif lang == "en":
        lbl_rev = "Gross Revenue"
        lbl_net = "Net Product Sales"
        lbl_deliv = "Delivery Fees"
        lbl_aov = "Avg Order Value"
        lbl_orders = "Total Orders"
        lbl_units = "Units Sold"
        lbl_conv = "Conversion Rate"
        lbl_success = "Retention Rate"
        lbl_done_rate = "Completion Rate"
        lbl_cancel = "Cancel Rate"
        lbl_views = "Product Views"
        lbl_followers = "Followers"
        lbl_users = "Users"
        lbl_stores = "Stores"
        lbl_prods = "Active Products"
        lbl_new = "new"
        lbl_unknown_w = "Unspecified"
        lbl_ord_short = "ord"
    else:
        lbl_rev = "إجمالي المبيعات"
        lbl_net = "صافي مبيعات المنتجات"
        lbl_deliv = "رسوم التوصيل"
        lbl_aov = "متوسط قيمة الطلب"
        lbl_orders = "إجمالي الطلبات"
        lbl_units = "القطع المباعة"
        lbl_conv = "معدل التحويل"
        lbl_success = "نسبة النجاح"
        lbl_done_rate = "نسبة التسليم"
        lbl_cancel = "نسبة الإلغاء"
        lbl_views = "المشاهدات"
        lbl_followers = "المتابعون"
        lbl_users = "المستخدمون"
        lbl_stores = "المتاجر"
        lbl_prods = "المنتجات النشطة"
        lbl_new = "جديد"
        lbl_unknown_w = "غير محددة"
        lbl_ord_short = "طلب"

    lines: list[str] = []
    if store_id is not None:
        store = await s.get(Store, store_id)
        sname = esc(store.name) if store else f"#{store_id}"
        pcount = (await s.execute(select(func.count(Product.id)).where(Product.store_id == store_id, Product.is_deleted.is_(False)))).scalar() or 0
        vcount = (await s.execute(select(func.coalesce(func.sum(Product.views), 0)).where(Product.store_id == store_id, Product.is_deleted.is_(False)))).scalar() or 0
        fcount = (await s.execute(select(func.count(StoreFollower.id)).where(StoreFollower.store_id == store_id))).scalar() or 0
        rating = await get_store_rating(store_id, s)
        conv_rate = (total_orders / vcount * 100.0) if vcount > 0 else 0.0

        lines.append(f"{t(lang, 'analytics_store_title')} — <b>{sname}</b>")
        lines.append(f"{t(lang, 'analytics_period_lbl')}: <b>{_analytics_period_name(days, lang)}</b>\n")
        lines.append(t(lang, "analytics_overview"))
        lines.append(f"• 💰 {lbl_rev}: <b>{gross_rev:,.0f} {DEFAULT_CURRENCY}</b>{trend_badge}")
        lines.append(f"• 🏷️ {lbl_net}: <b>{net_prod_rev:,.0f} {DEFAULT_CURRENCY}</b> | 🚚 {lbl_deliv}: {delivery_total:,.0f} {DEFAULT_CURRENCY}")
        lines.append(f"• 🧾 {lbl_aov}: <b>{aov:,.0f} {DEFAULT_CURRENCY}</b> | 📦 {lbl_units}: <b>{units_sold}</b>")
        lines.append(f"• 👁️ {lbl_views}: <b>{vcount}</b> | 🎯 {lbl_conv}: <b>{conv_rate:.1f}%</b>")
        lines.append(f"• 📦 {lbl_prods}: <b>{pcount}</b> | 👥 {lbl_followers}: <b>{fcount}</b> | ⭐ {rating}")
    else:
        total_users = (await s.execute(select(func.count(User.id)))).scalar() or 0
        new_users = (
            (await s.execute(select(func.count(User.id)).where(User.created_at >= since))).scalar() or 0
            if since is not None
            else total_users
        )
        total_stores = (await s.execute(select(func.count(Store.id)))).scalar() or 0
        vip_stores = (await s.execute(select(func.count(Store.id)).where(Store.vip_until.is_not(None), Store.vip_until > now))).scalar() or 0
        total_prods = (await s.execute(select(func.count(Product.id)).where(Product.is_deleted.is_(False)))).scalar() or 0

        lines.append(t(lang, "analytics_platform_title"))
        lines.append(f"{t(lang, 'analytics_period_lbl')}: <b>{_analytics_period_name(days, lang)}</b>\n")
        lines.append(t(lang, "analytics_overview"))
        user_extra = f" (+{new_users} {lbl_new})" if since is not None else ""
        lines.append(f"• 👥 {lbl_users}: <b>{total_users}</b>{user_extra} | 🏪 {lbl_stores}: <b>{total_stores}</b> (👑 {vip_stores} VIP)")
        lines.append(f"• 📦 {lbl_prods}: <b>{total_prods}</b> | 🛒 {lbl_orders}: <b>{total_orders}</b>")
        lines.append(f"• 💰 {lbl_rev}: <b>{gross_rev:,.0f} {DEFAULT_CURRENCY}</b>{trend_badge}")
        lines.append(f"• 🏷️ {lbl_net}: <b>{net_prod_rev:,.0f} {DEFAULT_CURRENCY}</b> | 🧾 {lbl_aov}: <b>{aov:,.0f} {DEFAULT_CURRENCY}</b>")

    # Orders Breakdown & Rates
    lines.append(f"\n{t(lang, 'analytics_orders_breakdown')}")
    lines.append(
        f"• {t(lang, 'status_completed')}: <b>{completed}</b> | "
        f"{t(lang, 'status_shipped')}: <b>{shipped}</b> | "
        f"{t(lang, 'status_pending')}: <b>{pending}</b> | "
        f"{t(lang, 'status_cancelled')}: <b>{cancelled}</b>"
    )
    lines.append(
        f"• ✅ {lbl_success}: <b>{success_rate:.1f}%</b> | "
        f"📦 {lbl_done_rate}: <b>{completion_rate:.1f}%</b> | "
        f"❌ {lbl_cancel}: <b>{cancel_rate:.1f}%</b>"
    )

    # Delivery Split
    if deliv_total_cnt > 0:
        lines.append(f"\n{t(lang, 'analytics_delivery_split')}")
        lines.append(
            f"• {t(lang, 'analytics_home_lbl')}: <b>{home_cnt}</b> ({home_pct:.0f}%) | "
            f"{t(lang, 'analytics_desk_lbl')}: <b>{desk_cnt}</b> ({desk_pct:.0f}%)"
        )

    # Daily / Weekly Trend
    if trend_lines and total_orders > 0:
        lines.append(f"\n{t(lang, 'analytics_daily_trend')}")
        lines.extend(trend_lines)

    # Top 5 Wilayas
    lines.append(f"\n{t(lang, 'analytics_top_wilayas')}")
    if top_wilayas:
        max_w_cnt = top_wilayas[0][1][0]
        for idx, (wcode, (wcnt, wrev)) in enumerate(top_wilayas, start=1):
            wname = lbl_unknown_w if wcode == "00" else wilaya_label(wcode, lang)
            share = (wcnt / len(active_rows) * 100.0) if active_rows else 0.0
            bar = _analytics_bar(wcnt, max_w_cnt, 6)
            lines.append(
                f"{idx}. <b>{esc(wname)}</b> {bar} {int(wcnt)} {lbl_ord_short} ({share:.0f}%) — {wrev:,.0f} {DEFAULT_CURRENCY}"
            )
    else:
        lines.append(f"• {t(lang, 'analytics_no_data')}")

    # Top 5 Stores (Admin only)
    if store_id is None:
        store_stats: dict[int, list[float]] = {}
        for r in active_rows:
            st_id = r.store_id or r.prod_store_id
            if st_id:
                entry = store_stats.setdefault(int(st_id), [0.0, 0.0])
                entry[0] += 1.0
                entry[1] += float(r.price or 0.0)
        top_st_ids = sorted(store_stats.items(), key=lambda kv: (kv[1][1], kv[1][0]), reverse=True)[:5]
        lines.append(f"\n{t(lang, 'analytics_top_stores')}")
        if top_st_ids:
            st_objs = (
                await s.execute(select(Store).where(Store.id.in_([sid for sid, _ in top_st_ids])))
            ).scalars().all()
            st_map = {st.id: st.name for st in st_objs}
            for idx, (sid_k, (scnt, srev)) in enumerate(top_st_ids, start=1):
                lines.append(
                    f"{idx}. <b>{esc(st_map.get(sid_k, f'#{sid_k}'))}</b> — {int(scnt)} {lbl_ord_short} ({srev:,.0f} {DEFAULT_CURRENCY})"
                )
        else:
            lines.append(f"• {t(lang, 'analytics_no_data')}")

    # Top 5 Products
    lines.append(f"\n{t(lang, 'analytics_top_products')}")
    if top_prods:
        for idx, (pname, (ocnt, ucnt, prev)) in enumerate(top_prods, start=1):
            lines.append(
                f"{idx}. <b>{esc(pname[:38])}</b> — {int(ocnt)} {lbl_ord_short} (×{int(ucnt)}) | {prev:,.0f} {DEFAULT_CURRENCY}"
            )
    else:
        lines.append(f"• {t(lang, 'analytics_no_data')}")

    report = "\n".join(lines)
    if len(report) > 4000:
        report = report[:3980] + "\n…"
    return report


async def _build_analytics_csv(s, store_id: Optional[int], days: int, lang: str) -> bytes:
    """Generate UTF-8-BOM CSV analytics report (summary + wilayas + products + daily)."""
    now = utcnow()
    since = now - timedelta(days=days) if days in (7, 30) else None
    rows = await _fetch_analytics_orders(s, store_id, since)
    active_rows = [r for r in rows if r.status != "cancelled"]

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["SECTION", "METRIC / NAME", "ORDERS", "UNITS", "REVENUE_DZD", "SHARE_PCT"])

    total_orders = len(rows)
    completed = sum(1 for r in rows if r.status == "completed")
    cancelled = sum(1 for r in rows if r.status == "cancelled")
    gross_rev = sum(float(r.price or 0.0) for r in active_rows)
    deliv_rev = sum(float(r.delivery_fee or 0.0) for r in active_rows)
    units_total = sum(max(1, int(r.quantity or 1)) for r in active_rows)
    w.writerow(["SUMMARY", "Total Orders", total_orders, units_total, f"{gross_rev:.2f}", "100%"])
    w.writerow(["SUMMARY", "Completed Orders", completed, "", "", f"{(completed / total_orders * 100):.1f}%" if total_orders else "0%"])
    w.writerow(["SUMMARY", "Cancelled Orders", cancelled, "", "", f"{(cancelled / total_orders * 100):.1f}%" if total_orders else "0%"])
    w.writerow(["SUMMARY", "Delivery Fees Total", len(active_rows), "", f"{deliv_rev:.2f}", ""])
    w.writerow([])

    # By Wilaya
    wilaya_map: dict[str, list[float]] = {}
    for r in active_rows:
        wc = (r.buyer_wilaya or "").strip()
        wc = wc.zfill(2) if wc.isdigit() else (wc or "00")
        e = wilaya_map.setdefault(wc, [0.0, 0.0, 0.0])
        e[0] += 1.0
        e[1] += max(1, int(r.quantity or 1))
        e[2] += float(r.price or 0.0)
    for wc, (cnt, ucnt, rev) in sorted(wilaya_map.items(), key=lambda kv: kv[1][0], reverse=True):
        wname = "-" if wc == "00" else wilaya_label(wc, lang)
        pct = f"{(cnt / len(active_rows) * 100):.1f}%" if active_rows else "0%"
        w.writerow(["WILAYA", csv_safe(wname), int(cnt), int(ucnt), f"{rev:.2f}", pct])
    w.writerow([])

    # By Product
    prod_map: dict[str, list[float]] = {}
    for r in active_rows:
        pname = (r.prod_title_live or r.product_title or f"#{r.product_id or '?'}").strip()
        e = prod_map.setdefault(pname, [0.0, 0.0, 0.0])
        e[0] += 1.0
        e[1] += max(1, int(r.quantity or 1))
        e[2] += float(r.price or 0.0)
    for pname, (cnt, ucnt, rev) in sorted(prod_map.items(), key=lambda kv: kv[1][2], reverse=True)[:50]:
        pct = f"{(rev / gross_rev * 100):.1f}%" if gross_rev > 0 else "0%"
        w.writerow(["PRODUCT", csv_safe(pname), int(cnt), int(ucnt), f"{rev:.2f}", pct])
    w.writerow([])

    # By Day
    day_map: dict[str, list[float]] = {}
    for r in active_rows:
        dkey = r.created_at.strftime("%Y-%m-%d") if r.created_at else "unknown"
        e = day_map.setdefault(dkey, [0.0, 0.0, 0.0])
        e[0] += 1.0
        e[1] += max(1, int(r.quantity or 1))
        e[2] += float(r.price or 0.0)
    for dkey in sorted(day_map.keys(), reverse=True):
        cnt, ucnt, rev = day_map[dkey]
        w.writerow(["DAILY", dkey, int(cnt), int(ucnt), f"{rev:.2f}", ""])

    return buf.getvalue().encode("utf-8-sig")


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


def build_sql_pagination_kb(
    page_items: list[tuple[str, str]],
    page: int,
    total_count: int,
    prefix: str,
    lang: str,
    top_rows: Optional[list[list[InlineKeyboardButton]]] = None,
    extra_buttons: Optional[list[InlineKeyboardButton]] = None,
) -> InlineKeyboardMarkup:
    """True SQL LIMIT/OFFSET pagination keyboard with optional top filter rows."""
    kb: list[list[InlineKeyboardButton]] = list(top_rows or [])
    total_pages = max(1, math.ceil(total_count / ITEMS_PER_PAGE))
    page = max(1, min(page, total_pages))
    for label, cb in page_items:
        kb.append([InlineKeyboardButton(text=label, callback_data=cb)])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text=t(lang, "btn_prev"), callback_data=f"{prefix}:{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=t(lang, "page_info", current=page, total=total_pages), callback_data="ignore"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text=t(lang, "btn_next"), callback_data=f"{prefix}:{page + 1}"))
    if nav:
        kb.append(nav)
    for b in (extra_buttons or []):
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
        [InlineKeyboardButton(text=t(lang, "btn_profile"), callback_data="nav:profile"),
         InlineKeyboardButton(text=t(lang, "btn_wallet"), callback_data="nav:wallet")],
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
        total = (
            await s.execute(
                select(func.count(Product.id)).where(
                    Product.store_id == store_id, Product.status == "approved", Product.is_deleted.is_(False)
                )
            )
        ).scalar() or 0
        total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
        page = max(1, min(page, total_pages))
        products = (
            await s.execute(
                select(Product)
                .where(Product.store_id == store_id, Product.status == "approved", Product.is_deleted.is_(False))
                .order_by(nullslast(Product.featured_until.desc()), Product.created_at.desc())
                .limit(ITEMS_PER_PAGE)
                .offset((page - 1) * ITEMS_PER_PAGE)
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
    badge = store_badges(store, lang)
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
    kb = build_sql_pagination_kb(items, page, total, f"pubstore:{store.id}", lang, extra_buttons=extra)
    if store.logo_file_id:
        await target_msg.answer_photo(photo=store.logo_file_id, caption=text[:1024], reply_markup=kb)
    else:
        await target_msg.answer(text, reply_markup=kb)


async def send_store_dashboard(msg_obj, store_id: int, lang: str):
    async with Session() as s:
        store = await s.get(Store, store_id)
        if not store:
            return
        u = await ensure_user(s, store.owner_tg_id, lang)
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
        credits = float(u.ad_credits or 0.0)
    vip_active = is_store_vip(store)
    max_allowed = MAX_STORES_VIP if vip_active else MAX_STORES_PER_USER
    badge = store_badges(store, lang)
    vip_line = ""
    if vip_active:
        vip_line = f"\n👑 <b>متجر VIP نشط حتى:</b> {store.vip_until.strftime('%Y-%m-%d')} (نشر مباشر ✅)"
    elif store.auto_approve:
        vip_line = "\n⚡ <b>النشر المباشر مفعّل</b>"
    text = (
        t(lang, "store_welcome", name=esc(store.name), badge=badge, products=pcount, views=vcount, followers=fcount, rating=rating)
        + f"\n💳 <b>رصيد المحفظة:</b> {credits:g} {DEFAULT_CURRENCY}"
        + vip_line
    )
    kb = [
        [InlineKeyboardButton(text=t(lang, "btn_add_product"), callback_data=f"st_add:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_my_products"), callback_data=f"st_list:{store.id}:1"),
         InlineKeyboardButton(text=t(lang, "btn_seller_orders"), callback_data=f"st_orders:{store.id}:1")],
        [InlineKeyboardButton(text=t(lang, "btn_flash_sale"), callback_data=f"st_flash:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_promos"), callback_data=f"st_promos:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_buy_product_ad"), callback_data=f"st_buy_ad:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_vip_pkg"), callback_data=f"st_vip:{store.id}")],
        [InlineKeyboardButton(text=f"{t(lang, 'btn_wallet')} ({credits:g} {DEFAULT_CURRENCY})", callback_data=f"st_wallet:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_my_stats"), callback_data=f"st_stats:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_share"), callback_data=f"st_share:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_seller_broadcast"), callback_data=f"st_broadcast:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_settings"), callback_data=f"st_settings:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_seller_guide"), callback_data=f"st_guide:{store.id}")],
    ]
    if total_stores < max_allowed:
        kb.append([InlineKeyboardButton(text=t(lang, "add_new_store"), callback_data="nav:become_seller")])
    else:
        kb.append([InlineKeyboardButton(text=f"⚠️ ({max_allowed})", callback_data="ignore")])
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
        [InlineKeyboardButton(text=t(lang, "btn_admin_channel"), callback_data="admin:channel"),
         InlineKeyboardButton(text=t(lang, "btn_admin_backup"), callback_data="admin:backup")],
        [InlineKeyboardButton(text=t(lang, "btn_broadcast"), callback_data="admin:broadcast")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")],
    ])


# ════════════════════════════════════════════════════════════════════
# 4. COMMANDS & MAIN NAVIGATION (buyer_handlers)
# ════════════════════════════════════════════════════════════════════

@buyer_router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(message: Message, command: CommandObject, state: FSMContext):
    args = command.args or ""
    if args.startswith("prod_"):
        pid_str = args[len("prod_"):]
        if pid_str.isdigit():
            try:
                async with Session() as s:
                    await ensure_user(s, message.from_user.id, DEFAULT_LANG)
                    await s.commit()
                lang = await get_lang(message.from_user.id)
                if await send_product_card(message, int(pid_str), message.from_user.id, lang):
                    return
            except Exception as e:
                logger.error(f"Product deep link error: {e}")
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
    elif action == "wallet":
        await view_wallet_for_user(cb.message, uid, back_cb="nav:account")
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
        max_stores = await user_max_stores(uid)
        if len(stores) >= max_stores:
            await cb.answer(f"❌ وصلت للحد الأقصى ({max_stores} متاجر).", show_alert=True)
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


# ─── Wallet & Ad Credits Top-up ───

async def view_wallet_for_user(target_msg: Message, uid: int, back_cb: str = "nav:account"):
    lang = await get_lang(uid)
    async with Session() as s:
        u = await ensure_user(s, uid, lang)
        await s.commit()
        bal = float(u.ad_credits or 0.0)
        pending_topups = (
            await s.execute(
                select(func.count(AdRequest.id)).where(
                    AdRequest.user_tg_id == uid,
                    AdRequest.ad_type == "wallet_topup",
                    AdRequest.status == "pending",
                )
            )
        ).scalar() or 0
    pending_line = f"\n⏳ طلبات شحن قيد المراجعة: <b>{pending_topups}</b>" if pending_topups else ""
    text = (
        f"💳 <b>محفظتي (رصيد الترويج و VIP)</b>\n\n"
        f"💰 الرصيد المتاح: <b>{bal:g} {DEFAULT_CURRENCY}</b>{pending_line}\n\n"
        f"💡 يمكنك استخدام الرصيد لتفعيل إعلانات المنتجات وباقات VIP للمتاجر <b>بشكل فوري</b> دون انتظار مراجعة وصل الدفع!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ شحن الرصيد الآن", callback_data="wallet:topup")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=back_cb)],
    ])
    await target_msg.answer(text, reply_markup=kb)


@buyer_router.callback_query(F.data == "wallet:topup")
async def wallet_topup_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_lang(cb.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"1000 {DEFAULT_CURRENCY}", callback_data="wallet:amt:1000"),
            InlineKeyboardButton(text=f"2000 {DEFAULT_CURRENCY}", callback_data="wallet:amt:2000"),
        ],
        [
            InlineKeyboardButton(text=f"5000 {DEFAULT_CURRENCY}", callback_data="wallet:amt:5000"),
            InlineKeyboardButton(text=f"10000 {DEFAULT_CURRENCY}", callback_data="wallet:amt:10000"),
        ],
        [InlineKeyboardButton(text="✏️ مبلغ مخصص", callback_data="wallet:amt:custom")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:wallet")],
    ])
    text = (
        "💳 <b>شحن المحفظة</b>\n\n"
        "اختر المبلغ الذي تريد شحنه ثم أرسل صورة وصل الدفع (CCP / BaridiMob):"
    )
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("wallet:amt:"))
async def wallet_topup_amount_cb(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[2]
    lang = await get_lang(cb.from_user.id)
    if val == "custom":
        await state.set_state(WalletTopupFSM.custom_amount)
        await cb.message.answer(f"✏️ أرسل المبلغ الذي تريد شحنه ({DEFAULT_CURRENCY}) — الحد الأدنى 500:")
        return await cb.answer()
    amt = float(val)
    await state.update_data(topup_amount=amt)
    await state.set_state(WalletTopupFSM.proof)
    await cb.message.answer(
        f"💳 <b>شحن رصيد: {amt:g} {DEFAULT_CURRENCY}</b>\n\n"
        f"{t(lang, 'ad_payment_instructions', price=f'{amt:g}')}"
    )
    await cb.answer()


@buyer_router.message(WalletTopupFSM.custom_amount)
async def wallet_topup_custom_amount(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    try:
        amt = float((message.text or "").replace(",", ".").strip())
        if amt < 500 or amt > 1_000_000:
            raise ValueError()
    except ValueError:
        return await message.answer("❌ يرجى إدخال مبلغ صحيح بين 500 و 1,000,000.")
    await state.update_data(topup_amount=amt)
    await state.set_state(WalletTopupFSM.proof)
    await message.answer(
        f"💳 <b>شحن رصيد: {amt:g} {DEFAULT_CURRENCY}</b>\n\n"
        f"{t(lang, 'ad_payment_instructions', price=f'{amt:g}')}"
    )


@buyer_router.message(WalletTopupFSM.proof, F.photo)
async def wallet_topup_receive_proof(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    amt = float(data.get("topup_amount", 0))
    await state.clear()
    if amt <= 0:
        return await message.answer(t(lang, "cancelled"), reply_markup=await get_main_kb(message.from_user.id, lang))
    photo_id = message.photo[-1].file_id
    async with Session() as s:
        req = AdRequest(
            user_tg_id=message.from_user.id,
            ad_type="wallet_topup",
            target_id=0,
            package_name=f"topup_{int(amt)}",
            price=amt,
            payment_proof=photo_id,
            status="pending",
        )
        s.add(req)
        await s.commit()
        await s.refresh(req)
        req_id = req.id
    await message.answer(
        f"✅ <b>تم إرسال طلب شحن المحفظة (#{req_id}) بنجاح!</b>\n"
        f"💰 المبلغ: <b>{amt:g} {DEFAULT_CURRENCY}</b>\n"
        f"⏳ سيتم إضافة الرصيد لمحفظتك فور تأكيد الإدارة للوصل.",
        reply_markup=await get_main_kb(message.from_user.id, lang),
    )
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تأكيد وشحن الرصيد", callback_data=f"admin:confirm_payment:{req_id}"),
        InlineKeyboardButton(text="❌ رفض الطلب", callback_data=f"admin:reject_payment:{req_id}"),
    ]])
    await notify_admins(
        message.bot,
        f"💳 <b>طلب شحن محفظة جديد #{req_id}</b>\n"
        f"👤 المستخدم: {esc(message.from_user.full_name)} (<code>{message.from_user.id}</code>)\n"
        f"💰 المبلغ المطلوب: <b>{amt:g} {DEFAULT_CURRENCY}</b>",
        reply_markup=admin_kb,
        photo=photo_id,
    )


@buyer_router.message(WalletTopupFSM.proof, ~F.photo)
async def wallet_topup_proof_invalid(message: Message):
    await message.answer("📸 يرجى إرسال صورة وصل الدفع (أو /cancel للإلغاء).")


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

async def _fetch_buyer_orders_page(uid: int, page: int, lang: str):
    async with Session() as s:
        total = (
            await s.execute(select(func.count(Order.id)).where(Order.buyer_tg_id == uid))
        ).scalar() or 0
        total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
        page = max(1, min(page, total_pages))
        orders = (
            await s.execute(
                select(Order)
                .where(Order.buyer_tg_id == uid)
                .order_by(Order.created_at.desc())
                .limit(ITEMS_PER_PAGE)
                .offset((page - 1) * ITEMS_PER_PAGE)
            )
        ).scalars().all()
    status_icons = {"pending": "⏳", "shipped": "🚚", "completed": "✅", "cancelled": "❌"}
    items = [
        (f"{status_icons.get(o.status, '')} طلب #{o.id} (×{o.quantity or 1}) - {o.buyer_name}", f"b_ord_view:{o.id}")
        for o in orders
    ]
    kb = build_sql_pagination_kb(
        items, page, total, "b_ord_pg", lang,
        extra_buttons=[InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:account")],
    )
    return total, kb


async def buyer_orders_for_user(target_msg: Message, uid: int):
    lang = await get_lang(uid)
    total, kb = await _fetch_buyer_orders_page(uid, 1, lang)
    if total == 0:
        return await target_msg.answer(t(lang, "buyer_orders_empty"), reply_markup=back_kb(lang, "nav:account"))
    await target_msg.answer(t(lang, "buyer_orders_list"), reply_markup=kb)


@buyer_router.message(F.text.in_([t(l, "btn_my_orders") for l in LANGS]))
async def buyer_orders_list(message: Message):
    await buyer_orders_for_user(message, message.from_user.id)


@buyer_router.callback_query(F.data.startswith("b_ord_pg:"))
async def buyer_orders_pg(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[1])
    _total, kb = await _fetch_buyer_orders_page(cb.from_user.id, page, lang)
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
    dtype_label = "🏢 مكتب التوصيل (Stop Desk)" if o.delivery_type == "desk" else "🏠 باب المنزل"
    extras = [f"🔢 الكمية: <b>{o.quantity or 1}</b>"]
    if o.buyer_wilaya:
        extras.append(f"🗺️ الولاية: <b>{esc(wilaya_label(o.buyer_wilaya))}</b>")
    extras.append(f"🚚 نوع التوصيل: {dtype_label}")
    if o.tracking_info:
        extras.append(f"🔎 رقم/معلومات التتبع: <code>{esc(o.tracking_info)}</code>")
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
    ) + "\n" + "\n".join(extras)
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
            kb = [[InlineKeyboardButton(text=v, callback_data=f"cart_var:{pid}:{idx}")] for idx, v in enumerate(vars_list)]
            await cb.message.answer(t(lang, "var_select_prompt"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
            await cb.answer()
            return
        existing = (
            await s.execute(
                select(CartItem).where(
                    CartItem.user_tg_id == cb.from_user.id,
                    CartItem.product_id == pid,
                    CartItem.variation == "",
                )
            )
        ).scalar_one_or_none()
        if existing:
            if existing.quantity < p.stock_quantity:
                existing.quantity += 1
                await s.commit()
                return await cb.answer(f"✅ تمت زيادة الكمية في السلة (الكمية: {existing.quantity})", show_alert=True)
            return await cb.answer(f"⚠️ أقصى كمية متوفرة في المخزون هي {p.stock_quantity}.", show_alert=True)
        s.add(CartItem(user_tg_id=cb.from_user.id, product_id=pid, variation="", quantity=1))
        await s.commit()
    await cb.answer(t(lang, "cart_added"), show_alert=True)


@buyer_router.callback_query(F.data.startswith("cart_var:"))
async def cart_add_var(cb: CallbackQuery):
    _, pid_str, idx_str = cb.data.split(":", 2)
    pid = int(pid_str)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid, Product.is_deleted.is_(False)))).scalar_one_or_none()
        if not p or p.is_out_of_stock:
            return await cb.answer("⚠️ غير متوفر.", show_alert=True)
        vars_list = _product_vars(p)
        if idx_str.isdigit() and 0 <= int(idx_str) < len(vars_list):
            var = vars_list[int(idx_str)]
        else:
            var = idx_str[:100]
        existing = (
            await s.execute(
                select(CartItem).where(
                    CartItem.user_tg_id == cb.from_user.id,
                    CartItem.product_id == pid,
                    CartItem.variation == var,
                )
            )
        ).scalar_one_or_none()
        if existing:
            if existing.quantity < p.stock_quantity:
                existing.quantity += 1
                await s.commit()
                msg_done = f"✅ تمت زيادة الكمية في السلة ({existing.quantity}×)"
            else:
                msg_done = f"⚠️ أقصى كمية متوفرة في المخزون هي {p.stock_quantity}."
        else:
            s.add(CartItem(user_tg_id=cb.from_user.id, product_id=pid, variation=var, quantity=1))
            await s.commit()
            msg_done = t(lang, "cart_added")
    with suppress(Exception):
        await cb.message.edit_text(msg_done)
    await cb.answer()


async def _build_cart_view(uid: int, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    async with Session() as s:
        cart_items = (
            await s.execute(select(CartItem).where(CartItem.user_tg_id == uid).order_by(CartItem.id.asc()))
        ).scalars().all()
        if not cart_items:
            return t(lang, "cart_empty"), back_kb(lang, "nav:buyer")
        p_ids = [c.product_id for c in cart_items]
        products = (
            await s.execute(
                select(Product).where(Product.id.in_(p_ids), Product.status == "approved", Product.is_deleted.is_(False))
            )
        ).scalars().all()

    if not products:
        return t(lang, "cart_empty"), back_kb(lang, "nav:buyer")

    by_id = {p.id: p for p in products}
    total = 0.0
    lines = []
    item_rows = []
    has_available = False
    for c in cart_items:
        p = by_id.get(c.product_id)
        if not p:
            continue
        qty = max(1, int(c.quantity or 1))
        price = _current_price(p)
        subtotal = price * qty
        var_str = f" ({esc(c.variation)})" if c.variation else ""
        short_title = (p.title[:16] + "…") if len(p.title) > 16 else p.title
        if p.is_out_of_stock:
            lines.append(f"⚠️ <s>{esc(p.title)}</s>{var_str} — نفدت الكمية")
            item_rows.append([
                InlineKeyboardButton(text=f"🗑️ حذف {short_title}", callback_data=f"cart_rm:{c.id}"),
            ])
        else:
            total += subtotal
            has_available = True
            lines.append(
                f"📦 <b>{esc(p.title)}</b>{var_str}\n"
                f"    الكمية: <b>{qty}</b> × {price:g} = <b>{subtotal:g} {esc(p.currency)}</b>"
            )
            item_rows.append([
                InlineKeyboardButton(text="➖", callback_data=f"cart_dec:{c.id}"),
                InlineKeyboardButton(text=f"{short_title} (×{qty})", callback_data=f"prod:{p.id}"),
                InlineKeyboardButton(text="➕", callback_data=f"cart_inc:{c.id}"),
                InlineKeyboardButton(text="🗑️", callback_data=f"cart_rm:{c.id}"),
            ])

    if not lines:
        return t(lang, "cart_empty"), back_kb(lang, "nav:buyer")

    text = t(lang, "my_cart") + "\n\n" + "\n".join(lines)
    if has_available:
        text += f"\n\n💰 <b>الإجمالي (قبل التوصيل): {total:.2f} {DEFAULT_CURRENCY}</b>"
    else:
        text += "\n\n⚠️ <b>جميع المنتجات في سلتك نفدت كميتها حالياً.</b>"

    rows = list(item_rows)
    if has_available:
        rows.append([InlineKeyboardButton(text=t(lang, "cart_checkout"), callback_data="cart_checkout")])
    rows.append([InlineKeyboardButton(text=t(lang, "cart_clear"), callback_data="cart_clear")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def view_cart_for_user(target_msg: Message, uid: int):
    lang = await get_lang(uid)
    text, kb = await _build_cart_view(uid, lang)
    await target_msg.answer(text, reply_markup=kb)


@buyer_router.callback_query(F.data.startswith("cart_inc:"))
async def cart_inc_item(cb: CallbackQuery):
    cid = int(cb.data.split(":")[1])
    uid = cb.from_user.id
    lang = await get_lang(uid)
    async with Session() as s:
        ci = (await s.execute(select(CartItem).where(CartItem.id == cid, CartItem.user_tg_id == uid))).scalar_one_or_none()
        if not ci:
            return await cb.answer()
        p = await s.get(Product, ci.product_id)
        if not p or p.is_out_of_stock:
            return await cb.answer("⚠️ المنتج نفد من المخزون.", show_alert=True)
        if (ci.quantity or 1) >= p.stock_quantity:
            return await cb.answer(f"⚠️ أقصى كمية متوفرة هي {p.stock_quantity}.", show_alert=True)
        ci.quantity = (ci.quantity or 1) + 1
        await s.commit()
    text, kb = await _build_cart_view(uid, lang)
    with suppress(Exception):
        await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("cart_dec:"))
async def cart_dec_item(cb: CallbackQuery):
    cid = int(cb.data.split(":")[1])
    uid = cb.from_user.id
    lang = await get_lang(uid)
    async with Session() as s:
        ci = (await s.execute(select(CartItem).where(CartItem.id == cid, CartItem.user_tg_id == uid))).scalar_one_or_none()
        if not ci:
            return await cb.answer()
        if (ci.quantity or 1) > 1:
            ci.quantity = (ci.quantity or 1) - 1
        else:
            await s.delete(ci)
        await s.commit()
    text, kb = await _build_cart_view(uid, lang)
    with suppress(Exception):
        await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("cart_rm:"))
async def cart_rm_item(cb: CallbackQuery):
    cid = int(cb.data.split(":")[1])
    uid = cb.from_user.id
    lang = await get_lang(uid)
    async with Session() as s:
        await s.execute(delete(CartItem).where(CartItem.id == cid, CartItem.user_tg_id == uid))
        await s.commit()
    text, kb = await _build_cart_view(uid, lang)
    with suppress(Exception):
        await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer("🗑️ تم حذف المنتج من السلة.")


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
        await state.update_data(
            p_name=u.saved_name,
            p_phone=u.saved_phone,
            p_address=u.saved_address,
            p_wilaya=u.saved_wilaya or "",
        )
        wilaya_line = f"\n🗺️ الولاية: {esc(wilaya_label(u.saved_wilaya))}" if u.saved_wilaya else ""
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_use_saved"), callback_data="checkout_use_saved")],
            [InlineKeyboardButton(text="✏️ إدخال بيانات جديدة", callback_data="checkout_new_info")],
        ])
        await msg_obj.answer(
            f"👤 الاسم: {esc(u.saved_name)}\n📞 الهاتف: {esc(u.saved_phone)}{wilaya_line}\n📍 العنوان: {esc(u.saved_address)}",
            reply_markup=kb,
        )
    else:
        await state.set_state(OrderFSM.name)
        await msg_obj.answer(t(lang, "order_name"), reply_markup=ReplyKeyboardRemove())


async def _ask_checkout_delivery_type(msg_obj, lang: str, wilaya_code: str):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 توصيل لباب المنزل", callback_data="chk_dtype:home")],
        [InlineKeyboardButton(text="🏢 مكتب التوصيل (Stop Desk)", callback_data="chk_dtype:desk")],
    ])
    w_txt = f"🗺️ الولاية المختارة: <b>{esc(wilaya_label(wilaya_code))}</b>\n\n" if wilaya_code else ""
    await msg_obj.answer(f"{w_txt}🚚 اختر طريقة التوصيل المفضلة:", reply_markup=kb)


@buyer_router.callback_query(F.data == "checkout_new_info")
async def checkout_new_info(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    await state.set_state(OrderFSM.name)
    await cb.message.answer(t(lang, "order_name"), reply_markup=ReplyKeyboardRemove())
    await cb.answer()


@buyer_router.callback_query(F.data == "checkout_use_saved")
async def checkout_use_saved(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    data = await state.get_data()
    if not data.get("p_wilaya"):
        await state.set_state(OrderFSM.wilaya)
        kb = build_wilaya_kb(1, "chk_wpg", "chk_w", "menu:home", lang)
        await cb.message.answer("🗺️ اختر ولايتك (أو اكتب رقم الولاية من 1 إلى 58):", reply_markup=kb)
    else:
        await state.set_state(OrderFSM.delivery_type)
        await _ask_checkout_delivery_type(cb.message, lang, data["p_wilaya"])
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
    await state.set_state(OrderFSM.wilaya)
    kb = build_wilaya_kb(1, "chk_wpg", "chk_w", "menu:home", lang)
    await message.answer("🗺️ اختر ولايتك من القائمة (أو أرسل رقم الولاية من 1 إلى 58):", reply_markup=kb)


@buyer_router.callback_query(F.data.startswith("chk_wpg:"))
async def checkout_wilaya_pg(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[1])
    kb = build_wilaya_kb(page, "chk_wpg", "chk_w", "menu:home", lang)
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=kb)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("chk_w:"))
async def checkout_wilaya_select(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    code = cb.data.split(":")[1].zfill(2)
    if code not in ALGERIA_WILAYAS:
        return await cb.answer("❌ ولاية غير صالحة.", show_alert=True)
    await state.update_data(p_wilaya=code)
    await state.set_state(OrderFSM.delivery_type)
    await _ask_checkout_delivery_type(cb.message, lang, code)
    await cb.answer()


@buyer_router.message(OrderFSM.wilaya)
async def checkout_wilaya_text(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    raw = (message.text or "").strip()
    code = raw.zfill(2) if raw.isdigit() else ""
    if code not in ALGERIA_WILAYAS:
        for k, v in ALGERIA_WILAYAS.items():
            if raw and raw in v:
                code = k
                break
    if code not in ALGERIA_WILAYAS:
        return await message.answer("❌ يرجى اختيار الولاية من الأزرار أو كتابة رقمها (1 إلى 58).")
    await state.update_data(p_wilaya=code)
    await state.set_state(OrderFSM.delivery_type)
    await _ask_checkout_delivery_type(message, lang, code)


@buyer_router.callback_query(F.data.startswith("chk_dtype:"))
async def checkout_delivery_type_select(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    dtype = cb.data.split(":")[1]
    if dtype not in ("home", "desk"):
        dtype = "home"
    await state.update_data(p_delivery_type=dtype)
    data = await state.get_data()
    if data.get("p_address"):
        await state.set_state(OrderFSM.note)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_skip_note"), callback_data="skip_note")]])
        await cb.message.answer(t(lang, "order_note"), reply_markup=kb)
    else:
        await state.set_state(OrderFSM.address)
        prompt = "🏢 أرسل اسم البلدية / مكتب التوصيل القريب منك:" if dtype == "desk" else t(lang, "order_address")
        await cb.message.answer(prompt)
    await cb.answer()


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
    wilaya_code = data.get("p_wilaya", "")
    delivery_type = data.get("p_delivery_type", "home")
    note = data.get("order_note", "")
    is_direct_order = bool(data.get("order_pid"))

    if not (name and phone and addr):
        await state.clear()
        return await message_obj.answer(t(lang, "cancelled"), reply_markup=await get_main_kb(user_id, lang))

    pairs: list[tuple[Product, str, int]] = []
    async with Session() as s:
        u = await ensure_user(s, user_id, lang)
        if not u.saved_name:
            u.saved_name, u.saved_phone, u.saved_address = name, phone, addr
        if wilaya_code and not u.saved_wilaya:
            u.saved_wilaya = wilaya_code

        if is_direct_order:
            p = (
                await s.execute(
                    select(Product).where(Product.id == data["order_pid"], Product.status == "approved", Product.is_deleted.is_(False))
                )
            ).scalar_one_or_none()
            if p:
                pairs.append((p, data.get("selected_var", ""), 1))
        else:
            cart_items = (await s.execute(select(CartItem).where(CartItem.user_tg_id == user_id))).scalars().all()
            for ci in cart_items:
                p = (
                    await s.execute(
                        select(Product).where(Product.id == ci.product_id, Product.status == "approved", Product.is_deleted.is_(False))
                    )
                ).scalar_one_or_none()
                if p:
                    pairs.append((p, ci.variation, max(1, int(ci.quantity or 1))))

        if not pairs:
            if not is_direct_order:
                await s.execute(delete(CartItem).where(CartItem.user_tg_id == user_id))
            await s.commit()
            await state.clear()
            return await message_obj.answer(t(lang, "cart_empty"), reply_markup=await get_main_kb(user_id, lang))

        by_store: dict[int, list[tuple[Product, str, int]]] = {}
        for p, var, qty in pairs:
            by_store.setdefault(p.store_id, []).append((p, var, qty))

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
        total_delivery = 0.0
        dtype_label = "🏢 مكتب التوصيل (Stop Desk)" if delivery_type == "desk" else "🏠 باب المنزل"
        w_label = wilaya_label(wilaya_code) if wilaya_code else "—"

        for store_id, list_ in by_store.items():
            store = (await s.execute(select(Store).where(Store.id == store_id))).scalar_one_or_none()
            if not store:
                continue
            discount_percent = store_discounts.get(store_id, 0)

            for p, var, qty in list_:
                base = _current_price(p)
                unit_final = max(0.0, base * (1 - discount_percent / 100.0))
                final_price = unit_final * qty
                computed_delivery = await calculate_delivery_fee(s, store.id, p.delivery_fee, wilaya_code, delivery_type)

                res = await s.execute(
                    update(Product)
                    .where(Product.id == p.id, Product.stock_quantity >= qty, Product.is_deleted.is_(False))
                    .values(stock_quantity=Product.stock_quantity - qty)
                )
                if res.rowcount == 0:
                    failed_titles.append(f"{p.title} (الكمية المطلوبة: {qty})")
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
                    buyer_wilaya=wilaya_code,
                    buyer_address=addr,
                    buyer_note=note,
                    variation=var,
                    quantity=qty,
                    delivery_type=delivery_type,
                    price=final_price,
                    delivery_fee=computed_delivery,
                )
                s.add(order)
                orders_created += 1
                total_charged += final_price
                total_delivery += computed_delivery

                sl = await get_lang(store.owner_tg_id)
                seller_text = (
                    t(
                        sl,
                        "new_order_notify",
                        product=esc(p.title),
                        variation=esc(var or "-"),
                        name=esc(name),
                        phone=esc(phone),
                        address=esc(addr),
                        note=esc(note or "-"),
                        price=f"{final_price:.2f} {esc(p.currency)}",
                        delivery=f"{computed_delivery:g} {esc(p.currency)}",
                    )
                    + f"\n🔢 الكمية: <b>{qty}</b>\n🗺️ الولاية: <b>{esc(w_label)}</b>\n🚚 التوصيل: {dtype_label}"
                )
                seller_notifications.append((store.owner_tg_id, seller_text))

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
            f"⚠️ <b>لم يتم إنشاء أي طلب</b>\n\nالمنتجات التالية نفدت كميتها أو لا تكفي الكمية المطلوبة:{failed_str}",
            reply_markup=await get_main_kb(user_id, lang),
        )
    elif failed_titles:
        await message_obj.answer(
            "⚠️ <b>تنبيه:</b> بعض المنتجات لم تتوفر بالكمية المطلوبة:\n"
            + "\n".join(f"• {esc(x)}" for x in failed_titles)
            + f"\n\n✅ تم إنشاء <b>{orders_created}</b> طلب بنجاح.\n"
            + f"💰 المنتجات: {total_charged:.2f} | 🚚 التوصيل: {total_delivery:g} {DEFAULT_CURRENCY}",
            reply_markup=await get_main_kb(user_id, lang),
        )
    else:
        promo_note = f"\n{t(lang, 'promo_applied', price=f'{total_charged:.2f}')}" if store_discounts else ""
        summary = (
            f"\n\n🗺️ الولاية: <b>{esc(w_label)}</b> ({dtype_label})"
            f"\n💰 إجمالي المنتجات: <b>{total_charged:.2f} {DEFAULT_CURRENCY}</b>"
            f"\n🚚 إجمالي التوصيل: <b>{total_delivery:g} {DEFAULT_CURRENCY}</b>"
            f"\n🧾 الإجمالي الكلي: <b>{total_charged + total_delivery:.2f} {DEFAULT_CURRENCY}</b>"
        )
        await message_obj.answer(t(lang, "order_success") + promo_note + summary, reply_markup=await get_main_kb(user_id, lang))


# ════════════════════════════════════════════════════════════════════
# 6. BUYER FEATURES — BROWSE, CATEGORIES, SEARCH, PRODUCT VIEW, SOCIAL
# ════════════════════════════════════════════════════════════════════

def _browse_filter_rows(base_prefix: str, active_flt: str) -> list[list[InlineKeyboardButton]]:
    def _lbl(key: str, text: str) -> str:
        return f"• {text} •" if active_flt == key else text
    return [
        [
            InlineKeyboardButton(text=_lbl("new", "🆕 الأحدث"), callback_data=f"{base_prefix}:new:1"),
            InlineKeyboardButton(text=_lbl("cheap", "💰 الأرخص"), callback_data=f"{base_prefix}:cheap:1"),
        ],
        [
            InlineKeyboardButton(text=_lbl("flash", "🔥 عروض فلاش"), callback_data=f"{base_prefix}:flash:1"),
            InlineKeyboardButton(text=_lbl("verified", "✓ موثق/VIP"), callback_data=f"{base_prefix}:verified:1"),
        ],
    ]


async def _fetch_filtered_products(flt: str, page: int, category_id: Optional[int] = None):
    now = utcnow()
    if flt not in ("new", "cheap", "flash", "verified"):
        flt = "new"
    async with Session() as s:
        base_conds = [Product.status == "approved", Product.is_deleted.is_(False)]
        if category_id is not None:
            base_conds.append(Product.category_id == category_id)
        if flt == "flash":
            base_conds.append(Product.flash_sale_price.isnot(None))
            base_conds.append(Product.flash_sale_ends_at.isnot(None))
            base_conds.append(Product.flash_sale_ends_at > now)

        count_q = select(func.count(Product.id)).where(*base_conds)
        list_q = select(Product).where(*base_conds)

        if flt == "verified":
            verified_cond = or_(Store.verified.is_(True), and_(Store.vip_until.isnot(None), Store.vip_until > now))
            count_q = count_q.join(Store, Store.id == Product.store_id).where(verified_cond)
            list_q = list_q.join(Store, Store.id == Product.store_id).where(verified_cond)

        if flt == "cheap":
            eff_price = case(
                (
                    and_(
                        Product.flash_sale_price.isnot(None),
                        Product.flash_sale_ends_at.isnot(None),
                        Product.flash_sale_ends_at > now,
                    ),
                    Product.flash_sale_price,
                ),
                else_=Product.price,
            )
            list_q = list_q.order_by(eff_price.asc(), Product.created_at.desc())
        else:
            list_q = list_q.order_by(nullslast(Product.featured_until.desc()), Product.created_at.desc())

        total = (await s.execute(count_q)).scalar() or 0
        total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
        page = max(1, min(page, total_pages))
        products = (
            await s.execute(list_q.limit(ITEMS_PER_PAGE).offset((page - 1) * ITEMS_PER_PAGE))
        ).scalars().all()
    return total, page, products


async def browse_all_for_user(target_msg: Message, uid: int, flt: str = "new"):
    lang = await get_lang(uid)
    total, page, products = await _fetch_filtered_products(flt, 1)
    if total == 0 and flt == "new":
        return await target_msg.answer(t(lang, "no_products"), reply_markup=back_kb(lang, "nav:buyer"))
    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    kb = build_sql_pagination_kb(
        items, page, total, f"browse_pg:{flt}", lang,
        top_rows=_browse_filter_rows("browse_pg", flt),
        extra_buttons=[InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")],
    )
    await target_msg.answer(f"{t(lang, 'all_products')} ({total})", reply_markup=kb)


@buyer_router.message(F.text.in_([t(l, "btn_browse") for l in LANGS]))
async def browse_all(message: Message):
    await browse_all_for_user(message, message.from_user.id)


@buyer_router.callback_query(F.data.startswith("browse_pg:"))
async def browse_pg(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    parts = cb.data.split(":")
    if len(parts) == 3:
        flt, page = parts[1], int(parts[2])
    else:
        flt, page = "new", int(parts[1])
    total, page, products = await _fetch_filtered_products(flt, page)
    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    kb = build_sql_pagination_kb(
        items, page, total, f"browse_pg:{flt}", lang,
        top_rows=_browse_filter_rows("browse_pg", flt),
        extra_buttons=[InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")],
    )
    header = f"{t(lang, 'all_products')} ({total})" if total else f"{t(lang, 'all_products')}\n\nℹ️ لا توجد منتجات تطابق هذا الفلتر حالياً."
    try:
        await cb.message.edit_text(header, reply_markup=kb)
    except Exception:
        with suppress(Exception):
            await cb.message.edit_reply_markup(reply_markup=kb)
    await cb.answer()


async def browse_categories_for_user(target_msg: Message, uid: int):
    lang = await get_lang(uid)
    async with Session() as s:
        cats = (await s.execute(select(Category).order_by(Category.id.asc()))).scalars().all()
    if not cats:
        return await target_msg.answer(t(lang, "no_products"), reply_markup=back_kb(lang, "nav:buyer"))
    kb = [[InlineKeyboardButton(text=f"📂 {_cat_name(c, lang)}", callback_data=f"cat_browse:{c.id}:new:1")] for c in cats]
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")])
    await target_msg.answer(t(lang, "cats_browse_title"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@buyer_router.callback_query(F.data.startswith("cat_browse:"))
async def cat_browse(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    parts = cb.data.split(":")
    if len(parts) == 4:
        cid, flt, page = int(parts[1]), parts[2], int(parts[3])
    else:
        cid, flt, page = int(parts[1]), "new", int(parts[2])
    async with Session() as s:
        cat = (await s.execute(select(Category).where(Category.id == cid))).scalar_one_or_none()
    total, page, products = await _fetch_filtered_products(flt, page, category_id=cid)
    if total == 0 and flt == "new":
        return await cb.answer(t(lang, "no_products"), show_alert=True)
    items = [(_product_line(p), f"prod:{p.id}") for p in products]
    kb = build_sql_pagination_kb(
        items, page, total, f"cat_browse:{cid}:{flt}", lang,
        top_rows=_browse_filter_rows(f"cat_browse:{cid}", flt),
        extra_buttons=[InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:cats")],
    )
    title = f"📂 <b>{esc(_cat_name(cat, lang))}</b> ({total})"
    if total == 0:
        title += "\n\nℹ️ لا توجد منتجات تطابق هذا الفلتر."
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


async def _fetch_top_stores_page(page: int, lang: str):
    now = utcnow()
    vip_rank = case((and_(Store.vip_until.isnot(None), Store.vip_until > now), 1), else_=0)
    async with Session() as s:
        total = (await s.execute(select(func.count(Store.id)))).scalar() or 0
        total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
        page = max(1, min(page, total_pages))
        stores = (
            await s.execute(
                select(Store)
                .outerjoin(StoreFollower)
                .group_by(Store.id)
                .order_by(vip_rank.desc(), func.count(StoreFollower.id).desc(), Store.id.asc())
                .limit(ITEMS_PER_PAGE)
                .offset((page - 1) * ITEMS_PER_PAGE)
            )
        ).scalars().all()
    items = [(f"🏪 {st.name} {store_badges(st, lang)}".strip(), f"pubstore:{st.id}:1") for st in stores]
    kb = build_sql_pagination_kb(
        items, page, total, "top_store_pg", lang,
        extra_buttons=[InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:buyer")],
    )
    return total, kb


async def top_stores_for_user(target_msg: Message, uid: int):
    lang = await get_lang(uid)
    total, kb = await _fetch_top_stores_page(1, lang)
    if total == 0:
        return await target_msg.answer(t(lang, "top_stores_empty"), reply_markup=back_kb(lang, "nav:buyer"))
    await target_msg.answer(t(lang, "top_stores_title"), reply_markup=kb)


@buyer_router.message(F.text.in_([t(l, "btn_top_stores") for l in LANGS]))
async def top_stores(message: Message):
    await top_stores_for_user(message, message.from_user.id)


@buyer_router.callback_query(F.data.startswith("top_store_pg:"))
async def top_stores_pg(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[1])
    _total, kb = await _fetch_top_stores_page(page, lang)
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

async def send_product_card(target_msg: Message, pid: int, viewer_id: int, lang: str) -> bool:
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid, Product.is_deleted.is_(False)))).scalar_one_or_none()
        if not p:
            return False
        p.views += 1
        await s.commit()
        store = (await s.execute(select(Store).where(Store.id == p.store_id))).scalar_one_or_none()
        rating = await get_store_rating(store.id, s) if store else "—"
        is_fav = (
            await s.execute(select(Favorite).where(Favorite.user_tg_id == viewer_id, Favorite.product_id == pid))
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
    badge = store_badges(store, lang)
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
            await target_msg.answer_photo(photo=photos[0], caption=caption[:1024], reply_markup=kb)
        elif len(photos) > 1:
            media = [InputMediaPhoto(media=ph, caption=caption[:1024] if i == 0 else None) for i, ph in enumerate(photos)]
            await target_msg.answer_media_group(media=media)
            await target_msg.answer("اختر الإجراء:", reply_markup=kb)
        else:
            await target_msg.answer(caption, reply_markup=kb)
    except Exception as e:
        logger.error(f"Failed to send product photos: {e}")
        with suppress(Exception):
            await target_msg.answer(caption, reply_markup=kb)
    return True


@buyer_router.callback_query(F.data.startswith("prod:"))
async def prod_view(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    pid = int(cb.data.split(":")[1])
    ok = await send_product_card(cb.message, pid, cb.from_user.id, lang)
    if not ok:
        return await cb.answer("Not found", show_alert=True)
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
        badge = store_badges(st, lang)
        kb.append([InlineKeyboardButton(text=f"🏪 {st.name} {badge}".strip(), callback_data=f"mngstore:{st.id}")])
    max_stores = await user_max_stores(message.from_user.id)
    if len(stores) < max_stores:
        kb.append([InlineKeyboardButton(text=t(lang, "add_new_store"), callback_data="nav:become_seller")])
    else:
        kb.append([InlineKeyboardButton(text=f"🔒 الحد الأقصى ({max_stores} متاجر)", callback_data="ignore")])
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
    max_stores = await user_max_stores(message.from_user.id)
    if len(stores) >= max_stores:
        await state.clear()
        return await message.answer(f"❌ وصلت للحد الأقصى ({max_stores} متاجر).", reply_markup=await get_main_kb(message.from_user.id, lang))
    async with Session() as s:
        s.add(Store(owner_tg_id=message.from_user.id, name=message.text.strip()[:MAX_STORE_NAME_LEN], contact=message.from_user.username or ""))
        u = await ensure_user(s, message.from_user.id, lang)
        u.role = "seller"
        await s.commit()
    await state.clear()
    await message.answer(t(lang, "store_created"), reply_markup=await get_main_kb(message.from_user.id, lang))


# ─── Store Settings & 58-Wilaya Delivery Rates ───

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
        [InlineKeyboardButton(text="🚚 أسعار التوصيل (58 ولاية)", callback_data=f"st_delivery:{store_id}")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{store_id}")],
    ])
    try:
        await cb.message.edit_text(t(lang, "settings_menu"), reply_markup=kb)
    except Exception:
        await cb.message.answer(t(lang, "settings_menu"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_delivery:"))
async def store_delivery_menu(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        st = await s.get(Store, sid)
        custom_count = (
            await s.execute(select(func.count(StoreDeliveryRate.id)).where(StoreDeliveryRate.store_id == sid))
        ).scalar() or 0
    if not st:
        return await cb.answer("Not found", show_alert=True)
    text = (
        f"🚚 <b>إعدادات التوصيل — {esc(st.name)}</b>\n\n"
        f"🏠 السعر الافتراضي لباب المنزل: <b>{st.delivery_fee:g} {DEFAULT_CURRENCY}</b>\n"
        f"🏢 السعر الافتراضي لمكتب التوصيل (Stop Desk): <b>{st.default_desk_fee:g} {DEFAULT_CURRENCY}</b>\n"
        f"🗺️ الولايات المخصصة: <b>{custom_count} / 58</b>\n\n"
        f"💡 عند الطلب، يُحسب السعر تلقائياً حسب ولاية المشتري وطريقة التوصيل (وإن لم تُخصص الولاية يُستخدم السعر الافتراضي)."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 تعديل السعر الافتراضي (للمنزل)", callback_data=f"st_deliv_home:{sid}")],
        [InlineKeyboardButton(text="🏢 تعديل السعر الافتراضي (للمكتب)", callback_data=f"st_deliv_desk:{sid}")],
        [InlineKeyboardButton(text="🗺️ تخصيص سعر لولاية محددة (58 ولاية)", callback_data=f"st_deliv_wpg:{sid}:1")],
        [InlineKeyboardButton(text=f"📋 عرض الولايات المخصصة ({custom_count})", callback_data=f"st_deliv_list:{sid}")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"st_settings:{sid}")],
    ])
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_deliv_home:"))
async def store_deliv_home_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(deliv_sid=sid)
    await state.set_state(DeliveryRateFSM.default_home)
    await cb.message.answer(f"🏠 أرسل السعر الافتراضي للتوصيل لباب المنزل ({DEFAULT_CURRENCY}) — مثال: 600 (أو 0 للمجاني):")
    await cb.answer()


@seller_router.message(DeliveryRateFSM.default_home)
async def store_deliv_home_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    fee = _parse_positive_float(message.text or "", allow_zero=True)
    if fee is None:
        return await message.answer("❌ يرجى إدخال رقم صحيح (مثال: 600 أو 0).")
    data = await state.get_data()
    sid = data.get("deliv_sid")
    await state.clear()
    if sid and await is_store_owner(message.from_user.id, sid):
        async with Session() as s:
            st = await s.get(Store, sid)
            if st:
                st.delivery_fee = fee
                await s.commit()
    await message.answer(
        f"✅ تم تحديث سعر التوصيل الافتراضي للمنزل إلى <b>{fee:g} {DEFAULT_CURRENCY}</b>.",
        reply_markup=back_kb(lang, f"st_delivery:{sid}"),
    )


@seller_router.callback_query(F.data.startswith("st_deliv_desk:"))
async def store_deliv_desk_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(deliv_sid=sid)
    await state.set_state(DeliveryRateFSM.default_desk)
    await cb.message.answer(f"🏢 أرسل السعر الافتراضي للتوصيل لمكتب التوصيل Stop Desk ({DEFAULT_CURRENCY}) — مثال: 400:")
    await cb.answer()


@seller_router.message(DeliveryRateFSM.default_desk)
async def store_deliv_desk_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    fee = _parse_positive_float(message.text or "", allow_zero=True)
    if fee is None:
        return await message.answer("❌ يرجى إدخال رقم صحيح (مثال: 400 أو 0).")
    data = await state.get_data()
    sid = data.get("deliv_sid")
    await state.clear()
    if sid and await is_store_owner(message.from_user.id, sid):
        async with Session() as s:
            st = await s.get(Store, sid)
            if st:
                st.default_desk_fee = fee
                await s.commit()
    await message.answer(
        f"✅ تم تحديث سعر التوصيل الافتراضي للمكتب إلى <b>{fee:g} {DEFAULT_CURRENCY}</b>.",
        reply_markup=back_kb(lang, f"st_delivery:{sid}"),
    )


@seller_router.callback_query(F.data.startswith("st_deliv_wpg:"))
async def store_deliv_wilaya_pg(cb: CallbackQuery):
    _, sid_str, pg_str = cb.data.split(":")
    sid, page = int(sid_str), int(pg_str)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    kb = build_wilaya_kb(page, f"st_deliv_wpg:{sid}", f"st_deliv_w:{sid}", f"st_delivery:{sid}", lang)
    try:
        await cb.message.edit_text("🗺️ اختر الولاية لتحديد سعر التوصيل لها:", reply_markup=kb)
    except Exception:
        await cb.message.answer("🗺️ اختر الولاية لتحديد سعر التوصيل لها:", reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_deliv_w:"))
async def store_deliv_wilaya_pick(cb: CallbackQuery, state: FSMContext):
    _, sid_str, code = cb.data.split(":")
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(deliv_sid=sid, deliv_wilaya=code)
    await state.set_state(DeliveryRateFSM.wilaya_rate)
    await cb.message.answer(
        f"🗺️ <b>تخصيص التوصيل لولاية {esc(wilaya_label(code))}</b>\n\n"
        f"أرسل سعر التوصيل للمنزل ثم للمكتب مفصولين بمسافة:\n"
        f"مثال: <code>700 450</code>\n"
        f"(أو أرسل رقماً واحداً فقط لتطبيقه على المنزل والمكتب معاً)"
    )
    await cb.answer()


@seller_router.message(DeliveryRateFSM.wilaya_rate)
async def store_deliv_wilaya_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    parts = (message.text or "").strip().split()
    if len(parts) == 1:
        home_fee = _parse_positive_float(parts[0], allow_zero=True)
        desk_fee = home_fee
    elif len(parts) >= 2:
        home_fee = _parse_positive_float(parts[0], allow_zero=True)
        desk_fee = _parse_positive_float(parts[1], allow_zero=True)
    else:
        home_fee = desk_fee = None
    if home_fee is None or desk_fee is None:
        return await message.answer("❌ صيغة غير صحيحة. مثال: <code>700 450</code>")
    data = await state.get_data()
    sid, code = data.get("deliv_sid"), data.get("deliv_wilaya")
    await state.clear()
    if sid and code and await is_store_owner(message.from_user.id, sid):
        async with Session() as s:
            rate = (
                await s.execute(
                    select(StoreDeliveryRate).where(
                        StoreDeliveryRate.store_id == sid,
                        StoreDeliveryRate.wilaya_code == code,
                    )
                )
            ).scalar_one_or_none()
            if rate:
                rate.home_fee = home_fee
                rate.desk_fee = desk_fee
            else:
                s.add(StoreDeliveryRate(store_id=sid, wilaya_code=code, home_fee=home_fee, desk_fee=desk_fee))
            await s.commit()
    await message.answer(
        f"✅ تم حفظ أسعار التوصيل لولاية <b>{esc(wilaya_label(code))}</b>:\n"
        f"🏠 المنزل: <b>{home_fee:g} {DEFAULT_CURRENCY}</b>\n"
        f"🏢 المكتب: <b>{desk_fee:g} {DEFAULT_CURRENCY}</b>",
        reply_markup=back_kb(lang, f"st_delivery:{sid}"),
    )


@seller_router.callback_query(F.data.startswith("st_deliv_list:"))
async def store_deliv_list(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        rates = (
            await s.execute(
                select(StoreDeliveryRate)
                .where(StoreDeliveryRate.store_id == sid)
                .order_by(StoreDeliveryRate.wilaya_code.asc())
            )
        ).scalars().all()
    if not rates:
        return await cb.answer("لا توجد ولايات مخصصة بعد، يُستخدم السعر الافتراضي للجميع.", show_alert=True)
    lines = [
        f"• <b>{esc(wilaya_label(r.wilaya_code))}</b>: 🏠 {r.home_fee:g} | 🏢 {r.desk_fee:g} {DEFAULT_CURRENCY}"
        for r in rates
    ]
    text = "📋 <b>أسعار التوصيل المخصصة:</b>\n\n" + "\n".join(lines)
    await cb.message.answer(text[:4000], reply_markup=back_kb(lang, f"st_delivery:{sid}"))
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
        total = (
            await s.execute(
                select(func.count(Product.id)).where(Product.store_id == sid, Product.is_deleted.is_(False))
            )
        ).scalar() or 0
        total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
        page = max(1, min(page, total_pages))
        products = (
            await s.execute(
                select(Product)
                .where(Product.store_id == sid, Product.is_deleted.is_(False))
                .order_by(Product.created_at.desc())
                .limit(ITEMS_PER_PAGE)
                .offset((page - 1) * ITEMS_PER_PAGE)
            )
        ).scalars().all()
    if total == 0:
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
    kb = build_sql_pagination_kb(
        items, page, total, f"st_list:{sid}", lang,
        extra_buttons=[InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}")],
    )
    with suppress(Exception):
        await cb.message.edit_text(f"{t(lang, 'my_products_list')} ({total})", reply_markup=kb)
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
            [
                InlineKeyboardButton(text="✏️ تعديل العنوان", callback_data=f"mngtitle:{pid}"),
                InlineKeyboardButton(text=t(lang, "btn_edit_price"), callback_data=f"mngprice:{pid}"),
            ],
            [
                InlineKeyboardButton(text=t(lang, "btn_edit_desc"), callback_data=f"mngdesc:{pid}"),
                InlineKeyboardButton(text=t(lang, "btn_edit_stock"), callback_data=f"mngstock_edit:{pid}"),
            ],
            [
                InlineKeyboardButton(text="📂 تعديل التصنيف", callback_data=f"mngcat:{pid}"),
                InlineKeyboardButton(text="🖼️ تعديل الصور", callback_data=f"mngphotos:{pid}"),
            ],
            [InlineKeyboardButton(text=t(lang, "btn_delete_prod"), callback_data=f"mngdel:{pid}")],
            [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{p.store_id}")],
        ])
        with suppress(Exception):
            await cb.message.edit_text(text, reply_markup=kb)
        return await cb.answer()

    stock_text = "❌ نفدت" if p.is_out_of_stock else f"✅ متوفر ({p.stock_quantity})"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ تعديل العنوان", callback_data=f"mngtitle:{pid}"),
            InlineKeyboardButton(text=t(lang, "btn_edit_price"), callback_data=f"mngprice:{pid}"),
        ],
        [
            InlineKeyboardButton(text=t(lang, "btn_edit_desc"), callback_data=f"mngdesc:{pid}"),
            InlineKeyboardButton(text=t(lang, "btn_edit_stock"), callback_data=f"mngstock_edit:{pid}"),
        ],
        [
            InlineKeyboardButton(text="📂 تعديل التصنيف", callback_data=f"mngcat:{pid}"),
            InlineKeyboardButton(text="🖼️ تعديل الصور", callback_data=f"mngphotos:{pid}"),
        ],
        [InlineKeyboardButton(text=f"{t(lang, 'btn_toggle_stock')} ({stock_text})", callback_data=f"mngstock:{pid}")],
        [InlineKeyboardButton(text=t(lang, "btn_delete_prod"), callback_data=f"mngdel:{pid}")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{p.store_id}")],
    ])
    try:
        await cb.message.edit_text(t(lang, "manage_product", title=esc(p.title)), reply_markup=kb)
    except Exception:
        await cb.message.answer(t(lang, "manage_product", title=esc(p.title)), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("mngtitle:"))
async def edit_title_start(cb: CallbackQuery, state: FSMContext):
    pid = int(cb.data.split(":")[1])
    if not await _guard_edit(cb, pid):
        return
    await state.update_data(edit_pid=pid)
    await state.set_state(EditProductFSM.title)
    await cb.message.answer("✏️ أرسل العنوان الجديد للمنتج:")
    await cb.answer()


@seller_router.message(EditProductFSM.title)
async def edit_title_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text or not message.text.strip():
        return await message.answer("✏️ أرسل العنوان الجديد للمنتج:")
    data = await state.get_data()
    pid = data.get("edit_pid")
    if pid and await is_product_owner(message.from_user.id, pid):
        async with Session() as s:
            p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
            if p and p.status != "pending":
                p.title = message.text.strip()[:MAX_PRODUCT_TITLE_LEN]
                await s.commit()
    await state.clear()
    await message.answer(t(lang, "prod_updated"), reply_markup=await get_main_kb(message.from_user.id, lang))


@seller_router.callback_query(F.data.startswith("mngcat:"))
async def edit_cat_start(cb: CallbackQuery):
    pid = int(cb.data.split(":")[1])
    if not await _guard_edit(cb, pid):
        return
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        cats = (await s.execute(select(Category).order_by(Category.id.asc()))).scalars().all()
    if not cats:
        return await cb.answer("لا توجد تصنيفات متاحة.", show_alert=True)
    kb = [[InlineKeyboardButton(text=f"📂 {_cat_name(c, lang)}", callback_data=f"mngcat_set:{pid}:{c.id}")] for c in cats]
    kb.append([InlineKeyboardButton(text="🚫 بدون تصنيف", callback_data=f"mngcat_set:{pid}:0")])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mng:{pid}")])
    try:
        await cb.message.edit_text("📂 اختر التصنيف الجديد للمنتج:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        await cb.message.answer("📂 اختر التصنيف الجديد للمنتج:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("mngcat_set:"))
async def edit_cat_save(cb: CallbackQuery):
    _, pid_str, cid_str = cb.data.split(":")
    pid, cid = int(pid_str), int(cid_str)
    if not await _guard_edit(cb, pid):
        return
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
        if p and p.status != "pending":
            p.category_id = cid if cid > 0 else None
            await s.commit()
    await cb.answer("✅ تم تحديث التصنيف.", show_alert=True)
    await manage_product(cb)


@seller_router.callback_query(F.data.startswith("mngphotos:"))
async def edit_photos_menu(cb: CallbackQuery):
    pid = int(cb.data.split(":")[1])
    p = await _guard_edit(cb, pid)
    if not p:
        return
    lang = await get_lang(cb.from_user.id)
    p1 = "✅ موجودة" if p.photo_file_id else "❌ فارغة"
    p2 = "✅ موجودة" if p.photo_file_id_2 else "❌ فارغة"
    p3 = "✅ موجودة" if p.photo_file_id_3 else "❌ فارغة"
    text = (
        f"🖼️ <b>إدارة صور المنتج — {esc(p.title)}</b>\n\n"
        f"• الصورة الرئيسية (1): {p1}\n"
        f"• الصورة الإضافية (2): {p2}\n"
        f"• الصورة الإضافية (3): {p3}"
    )
    rows = [
        [InlineKeyboardButton(text="🔄 تغيير الصورة الرئيسية (1)", callback_data=f"mngphoto_set:{pid}:1")],
        [
            InlineKeyboardButton(text="🔄 تغيير/إضافة الصورة (2)", callback_data=f"mngphoto_set:{pid}:2"),
            InlineKeyboardButton(text="🗑️ حذف (2)", callback_data=f"mngphoto_rm:{pid}:2"),
        ],
        [
            InlineKeyboardButton(text="🔄 تغيير/إضافة الصورة (3)", callback_data=f"mngphoto_set:{pid}:3"),
            InlineKeyboardButton(text="🗑️ حذف (3)", callback_data=f"mngphoto_rm:{pid}:3"),
        ],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mng:{pid}")],
    ]
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("mngphoto_set:"))
async def edit_photo_upload_start(cb: CallbackQuery, state: FSMContext):
    _, pid_str, slot_str = cb.data.split(":")
    pid, slot = int(pid_str), int(slot_str)
    if slot not in (1, 2, 3) or not await _guard_edit(cb, pid):
        return
    await state.update_data(edit_pid=pid, photo_slot=slot)
    await state.set_state(EditProductFSM.photo_upload)
    await cb.message.answer(f"📸 أرسل الصورة الجديدة الآن للخانة رقم <b>{slot}</b>:")
    await cb.answer()


@seller_router.message(EditProductFSM.photo_upload, F.photo)
async def edit_photo_upload_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    pid, slot = data.get("edit_pid"), data.get("photo_slot")
    await state.clear()
    if pid and slot in (1, 2, 3) and await is_product_owner(message.from_user.id, pid):
        attr = {1: "photo_file_id", 2: "photo_file_id_2", 3: "photo_file_id_3"}[slot]
        async with Session() as s:
            p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
            if p and p.status != "pending":
                setattr(p, attr, message.photo[-1].file_id)
                await s.commit()
    await message.answer(
        f"✅ تم تحديث الصورة رقم {slot} بنجاح.",
        reply_markup=back_kb(lang, f"mngphotos:{pid}"),
    )


@seller_router.message(EditProductFSM.photo_upload, ~F.photo)
async def edit_photo_upload_invalid(message: Message):
    await message.answer("📸 يرجى إرسال صورة صالحة (أو /cancel للإلغاء).")


@seller_router.callback_query(F.data.startswith("mngphoto_rm:"))
async def edit_photo_remove(cb: CallbackQuery):
    _, pid_str, slot_str = cb.data.split(":")
    pid, slot = int(pid_str), int(slot_str)
    if slot not in (2, 3) or not await _guard_edit(cb, pid):
        return
    attr = {2: "photo_file_id_2", 3: "photo_file_id_3"}[slot]
    async with Session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
        if p and p.status != "pending":
            setattr(p, attr, "")
            await s.commit()
    await cb.answer(f"🗑️ تم حذف الصورة رقم {slot}.", show_alert=True)
    await edit_photos_menu(cb)


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
        store = await s.get(Store, sid)
        auto_live = bool(store and (store.auto_approve or is_store_vip(store)))
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
            status="approved" if auto_live else "pending",
        )
        s.add(p)
        await s.commit()
        await s.refresh(p)
        pid, ptitle, pphoto = p.id, p.title, data["photo_1"]
        price_str = f"{p.price:g} {p.currency}"
        stock, delivery, vars_ = data["stock"], data["delivery"], data.get("vars", "") or "-"
        store_name = store.name if store else "-"
        followers = (
            (await s.execute(select(StoreFollower.user_tg_id).where(StoreFollower.store_id == sid))).scalars().all()
            if auto_live
            else []
        )
    await state.clear()

    if auto_live:
        with suppress(Exception):
            await cb.message.edit_text(
                f"⚡ <b>تم نشر منتجك مباشرة بنجاح!</b>\n\n📦 <b>{esc(ptitle)}</b>\nمتاح الآن للمشترين بفضل ميزة النشر المباشر / VIP."
            )
        await cb.message.answer(t(lang, "main_menu"), reply_markup=await get_main_kb(cb.from_user.id, lang))
        await publish_product_to_channel(cb.bot, pid)
        if followers:
            async def _notify_store_followers():
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
            asyncio.create_task(_notify_store_followers())
    else:
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
        cond = or_(Order.store_id == sid, Product.store_id == sid)
        total = (
            await s.execute(
                select(func.count(Order.id))
                .outerjoin(Product, Order.product_id == Product.id)
                .where(cond)
            )
        ).scalar() or 0
        total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
        page = max(1, min(page, total_pages))
        orders = (
            await s.execute(
                select(Order)
                .outerjoin(Product, Order.product_id == Product.id)
                .where(cond)
                .order_by(Order.created_at.desc())
                .limit(ITEMS_PER_PAGE)
                .offset((page - 1) * ITEMS_PER_PAGE)
            )
        ).scalars().all()
    if total == 0:
        with suppress(Exception):
            await cb.message.edit_text(t(lang, "orders_empty"), reply_markup=back_kb(lang, f"mngstore:{sid}"))
        return await cb.answer()
    icons = {"pending": "⏳", "shipped": "🚚", "completed": "✅", "cancelled": "❌"}
    items = [
        (f"{icons.get(o.status, '')} طلب #{o.id} (×{o.quantity or 1}) - {o.buyer_name}", f"ord_view:{o.id}")
        for o in orders
    ]
    extra = [
        InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}"),
        InlineKeyboardButton(text=t(lang, "btn_export_orders"), callback_data=f"st_export:{sid}"),
    ]
    kb = build_sql_pagination_kb(items, page, total, f"st_orders:{sid}", lang, extra_buttons=extra)
    with suppress(Exception):
        await cb.message.edit_text(f"{t(lang, 'orders_list')} ({total})", reply_markup=kb)
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
    writer.writerow([
        "رقم الطلب", "التاريخ", "اسم المنتج", "الخيار", "الكمية",
        "سعر المنتج", "التوصيل", "الإجمالي", "اسم المشتري", "الهاتف",
        "الولاية", "طريقة التوصيل", "العنوان", "ملاحظات", "التتبع", "الحالة",
    ])
    for o, p in rows:
        p_title = p.title if p else (o.product_title or "منتج محذوف")
        p_curr = p.currency if p else (o.product_currency or DEFAULT_CURRENCY)
        total = o.price + o.delivery_fee
        dtype = "مكتب التوصيل" if o.delivery_type == "desk" else "باب المنزل"
        writer.writerow([
            o.id,
            o.created_at.strftime("%Y-%m-%d %H:%M"),
            csv_safe(p_title),
            csv_safe(o.variation),
            str(o.quantity or 1),
            f"{o.price:.2f} {p_curr}",
            f"{o.delivery_fee:g} {p_curr}",
            f"{total:.2f} {p_curr}",
            csv_safe(o.buyer_name),
            csv_safe(o.buyer_phone),
            csv_safe(wilaya_label(o.buyer_wilaya) if o.buyer_wilaya else "-"),
            dtype,
            csv_safe(o.buyer_address),
            csv_safe(o.buyer_note),
            csv_safe(o.tracking_info),
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
    await _render_order_view(cb.message, oid, lang, edit=True)
    await cb.answer()


async def _render_order_view(msg_obj: Message, oid: int, lang: str, edit: bool = True):
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
    dtype_label = "🏢 مكتب التوصيل (Stop Desk)" if order.delivery_type == "desk" else "🏠 باب المنزل"
    extras = [f"🔢 الكمية: <b>{order.quantity or 1}</b>"]
    if order.buyer_wilaya:
        extras.append(f"🗺️ الولاية: <b>{esc(wilaya_label(order.buyer_wilaya))}</b>")
    extras.append(f"🚚 طريقة التوصيل: {dtype_label}")
    if order.tracking_info:
        extras.append(f"🔎 معلومات التتبع: <code>{esc(order.tracking_info)}</code>")
    text = (
        t(
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
        + "\n"
        + "\n".join(extras)
    )
    back_cb = f"st_orders:{sid}:1" if sid else "menu:home"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "status_pending"), callback_data=f"ord_st:{oid}:pending")],
        [InlineKeyboardButton(text=t(lang, "status_shipped"), callback_data=f"ord_st:{oid}:shipped")],
        [InlineKeyboardButton(text=t(lang, "status_completed"), callback_data=f"ord_st:{oid}:completed")],
        [InlineKeyboardButton(text=t(lang, "status_cancelled"), callback_data=f"ord_st:{oid}:cancelled")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=back_cb)],
    ])
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=kb)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=kb)


async def _apply_order_status(bot: Bot, oid: int, new_status: str, tracking_info: Optional[str] = None) -> bool:
    async with Session() as s:
        order = (await s.execute(select(Order).where(Order.id == oid))).scalar_one_or_none()
        if not order:
            return False
        prev_status = order.status
        order.status = new_status
        if tracking_info is not None:
            order.tracking_info = tracking_info[:300]

        if new_status == "cancelled" and prev_status != "cancelled" and order.product_id:
            p = (await s.execute(select(Product).where(Product.id == order.product_id, Product.is_deleted.is_(False)))).scalar_one_or_none()
            if p:
                was_out = p.is_out_of_stock
                p.stock_quantity += max(1, int(order.quantity or 1))
                p.is_out_of_stock = False
                if was_out:
                    await _notify_restock_alerts(bot, s, p)

        buyer_tg_id = order.buyer_tg_id
        buyer_name = order.buyer_name
        saved_tracking = order.tracking_info
        await s.commit()

    if new_status in ("shipped", "completed", "cancelled"):
        with suppress(Exception):
            bl = await get_lang(buyer_tg_id)
            sm = {
                "pending": t(bl, "status_pending"),
                "shipped": t(bl, "status_shipped"),
                "completed": t(bl, "status_completed"),
                "cancelled": t(bl, "status_cancelled"),
            }
            txt = t(bl, "order_status_notify", id=oid, name=esc(buyer_name), status=sm[new_status])
            if new_status == "shipped" and saved_tracking:
                txt += f"\n\n🔎 <b>معلومات التتبع / شركة التوصيل:</b>\n<code>{esc(saved_tracking)}</code>"
            await bot.send_message(buyer_tg_id, txt)
    return True


@seller_router.callback_query(F.data.startswith("ord_st:"))
async def order_status_change(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    _, oid_str, new_status = cb.data.split(":")
    oid = int(oid_str)
    if not await is_order_seller(cb.from_user.id, oid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    if new_status not in ("pending", "shipped", "completed", "cancelled"):
        return await cb.answer()

    if new_status == "shipped":
        await state.update_data(ship_oid=oid)
        await state.set_state(OrderShipFSM.tracking)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ تخطي بدون رقم تتبع", callback_data=f"ord_ship_skip:{oid}")],
        ])
        await cb.message.answer(
            f"🚚 <b>شحن الطلب #{oid}</b>\n\n"
            f"أرسل رقم التتبع أو اسم شركة التوصيل (مثال: <code>Yalidine #TRK-12345</code>) ليصل للمشتري فوراً، أو اضغط تخطي:",
            reply_markup=kb,
        )
        return await cb.answer()

    ok = await _apply_order_status(cb.bot, oid, new_status)
    if not ok:
        return await cb.answer("Not found", show_alert=True)
    await cb.answer(t(lang, "status_updated"), show_alert=True)
    await _render_order_view(cb.message, oid, lang, edit=True)


@seller_router.callback_query(F.data.startswith("ord_ship_skip:"))
async def order_ship_skip(cb: CallbackQuery, state: FSMContext):
    oid = int(cb.data.split(":")[1])
    if not await is_order_seller(cb.from_user.id, oid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.clear()
    lang = await get_lang(cb.from_user.id)
    await _apply_order_status(cb.bot, oid, "shipped", tracking_info="")
    await cb.answer(t(lang, "status_updated"), show_alert=True)
    await _render_order_view(cb.message, oid, lang, edit=True)


@seller_router.message(OrderShipFSM.tracking)
async def order_ship_tracking_save(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    oid = data.get("ship_oid")
    await state.clear()
    if not oid or not await is_order_seller(message.from_user.id, oid):
        return await message.answer("⛔ غير مصرح.")
    tracking = (message.text or "").strip()[:300]
    await _apply_order_status(message.bot, oid, "shipped", tracking_info=tracking)
    await message.answer(
        f"✅ تم تحديث الطلب #{oid} إلى <b>تم الشحن</b> وإرسال رقم التتبع للمشتري.",
        reply_markup=await get_main_kb(message.from_user.id, lang),
    )
    await _render_order_view(message, oid, lang, edit=False)


# ─── Background Broadcast Runner & Seller Broadcast / Stats ───

async def _run_broadcast_task(
    source_msg: Message,
    recipients: list[int],
    status_msg: Message,
    done_template: str,
):
    success = 0
    failed = 0
    for uid in recipients:
        if await _safe_send_copy(source_msg, uid):
            success += 1
        else:
            failed += 1
        await asyncio.sleep(0.05)
    with suppress(Exception):
        await status_msg.edit_text(done_template.format(count=success, failed=failed))


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
        followers = list((await s.execute(select(StoreFollower.user_tg_id).where(StoreFollower.store_id == sid))).scalars().all())
    _BROADCAST_COOLDOWN[message.from_user.id] = time.time()
    status_msg = await message.answer(f"{t(lang, 'broadcast_started')} ({len(followers)} متابع — يعمل في الخلفية)")
    done_tpl = t(lang, "seller_broadcast_done", count="{count}")
    asyncio.create_task(_run_broadcast_task(message, followers, status_msg, done_tpl))


@seller_router.callback_query(F.data.startswith("st_stats:"))
async def store_stats(cb: CallbackQuery):
    parts = cb.data.split(":")
    sid = int(parts[1])
    days = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 30
    if days not in (0, 7, 30):
        days = 30
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        text = await _build_analytics_report(s, sid, days, lang)
    kb = _analytics_kb(f"st_stats:{sid}", f"st_stats_csv:{sid}", days, f"mngstore:{sid}", lang)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_stats_csv:"))
async def store_stats_csv(cb: CallbackQuery):
    parts = cb.data.split(":")
    sid = int(parts[1])
    days = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 30
    if days not in (0, 7, 30):
        days = 30
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        csv_bytes = await _build_analytics_csv(s, sid, days, lang)
    period_tag = f"{days}d" if days else "all"
    fname = f"store_{sid}_analytics_{period_tag}_{utcnow().strftime('%Y%m%d')}.csv"
    caption = t(
        lang,
        "analytics_csv_caption",
        period=_analytics_period_name(days, lang),
        date=utcnow().strftime("%Y-%m-%d %H:%M"),
    )
    await cb.message.answer_document(BufferedInputFile(csv_bytes, filename=fname), caption=caption)
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
    pkg_info = AD_PACKAGES.get(pkg, AD_PACKAGES["basic"])
    price = float(pkg_info["price"])
    await state.update_data(pad_pkg=pkg)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        u = await ensure_user(s, cb.from_user.id, lang)
        await s.commit()
        credits = float(u.ad_credits or 0.0)
    text = (
        f"{t(lang, 'ad_payment_instructions')}\n\n"
        f"📦 الباقة: <b>{esc(pkg_info['label'])}</b>\n"
        f"💰 السعر: <b>{price:g} {DEFAULT_CURRENCY}</b>\n"
        f"💳 رصيد محفظتك الحالي: <b>{credits:g} {DEFAULT_CURRENCY}</b>"
    )
    rows = []
    if credits >= price:
        rows.append([
            InlineKeyboardButton(
                text=f"💳 الدفع من المحفظة ({price:g} {DEFAULT_CURRENCY}) — تفعيل فوري ⚡",
                callback_data=f"pad_wallet_pay:{pkg}:{pid}",
            )
        ])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_send_payment_proof"), callback_data="pad_send_proof")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")])
    with suppress(Exception):
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("pad_wallet_pay:"))
async def product_ad_wallet_pay(cb: CallbackQuery, state: FSMContext):
    _, pkg, pid_str = cb.data.split(":")
    pid = int(pid_str)
    uid = cb.from_user.id
    if not await is_product_owner(uid, pid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    pkg_info = AD_PACKAGES.get(pkg)
    if not pkg_info:
        return await cb.answer("❌ باقة غير صالحة.", show_alert=True)
    price = float(pkg_info["price"])
    days = int(pkg_info["days"])
    lang = await get_lang(uid)

    async with Session() as s:
        res = await s.execute(
            update(User)
            .where(User.tg_id == uid, User.ad_credits >= price)
            .values(ad_credits=User.ad_credits - price)
        )
        if res.rowcount == 0:
            return await cb.answer("❌ رصيد المحفظة غير كافٍ.", show_alert=True)
        p = await s.get(Product, pid)
        if not p or p.is_deleted:
            await s.rollback()
            return await cb.answer("❌ المنتج غير موجود.", show_alert=True)
        base_dt = p.featured_until if (p.featured_until and p.featured_until > utcnow()) else utcnow()
        p.featured_until = base_dt + timedelta(days=days)
        until_str = p.featured_until.strftime("%Y-%m-%d %H:%M")
        ptitle = p.title
        await s.commit()

    await state.clear()
    try:
        await cb.message.edit_text(
            f"⚡ <b>تم تفعيل الإعلان المميز فوراً من المحفظة!</b>\n\n"
            f"📦 المنتج: <b>{esc(ptitle)}</b>\n"
            f"💳 المخصوم: <b>{price:g} {DEFAULT_CURRENCY}</b>\n"
            f"📅 مميز حتى: <b>{until_str} UTC</b>"
        )
    except Exception:
        await cb.message.answer(f"⚡ تم تمييز المنتج <b>{esc(ptitle)}</b> حتى {until_str} UTC.")
    await cb.answer("✅ تم التفعيل الفوري!", show_alert=True)


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
    price = float(AD_PACKAGES.get(pkg, AD_PACKAGES["basic"])["price"])
    async with Session() as s:
        areq = AdRequest(
            user_tg_id=message.from_user.id,
            ad_type="product",
            target_id=pid,
            package_name=pkg,
            price=price,
            payment_proof=proof,
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
        price=f"{price:g} {DEFAULT_CURRENCY}",
        type=f"product #{pid} ({esc(ptitle)})",
    )
    await notify_admins(message.bot, admin_text, reply_markup=admin_kb, photo=proof)


@seller_router.message(ProductAdFSM.payment_proof, ~F.photo)
async def product_ad_receive_proof_invalid(message: Message):
    await message.answer("📸 أرسل صورة إثبات الدفع:")


# ─── Store Wallet Shortcut & Store VIP Subscriptions ───

@seller_router.callback_query(F.data.startswith("st_wallet:"))
async def store_wallet_shortcut(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await view_wallet_for_user(cb.message, cb.from_user.id, back_cb=f"mngstore:{sid}")
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_vip:"))
async def store_vip_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        st = await s.get(Store, sid)
        u = await ensure_user(s, cb.from_user.id, lang)
        await s.commit()
    if not st:
        return await cb.answer("Not found", show_alert=True)
    vip_status = (
        f"✅ مفعل حتى <b>{st.vip_until.strftime('%Y-%m-%d')}</b>"
        if is_store_vip(st)
        else "❌ غير مفعل حالياً"
    )
    text = (
        f"👑 <b>باقة VIP للمتجر — {esc(st.name)}</b>\n\n"
        f"📌 الحالة الحالية: {vip_status}\n"
        f"💳 رصيد محفظتك: <b>{float(u.ad_credits or 0):g} {DEFAULT_CURRENCY}</b>\n\n"
        f"✨ <b>مميزات باقة VIP:</b>\n"
        f"• 👑 شارة التاج والتوثيق تلقائياً\n"
        f"• ⚡ نشر المنتجات مباشرة بدون انتظار موافقة الإدارة\n"
        f"• 🏆 أولوية الظهور في أعلى قائمة المتاجر المميزة\n"
        f"• 🏪 فتح حتى <b>{MAX_STORES_VIP} متاجر</b> بدلاً من {MAX_STORES_PER_USER}\n\n"
        f"اختر الباقة المناسبة:"
    )
    rows = [
        [InlineKeyboardButton(text=info["label"], callback_data=f"vip_buy:{sid}:{key}")]
        for key, info in VIP_PLANS.items()
    ]
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}")])
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("vip_buy:"))
async def store_vip_choose_payment(cb: CallbackQuery):
    _, sid_str, plan_key = cb.data.split(":")
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    plan = VIP_PLANS.get(plan_key)
    if not plan:
        return await cb.answer("❌ باقة غير صالحة.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        u = await ensure_user(s, cb.from_user.id, lang)
        await s.commit()
        credits = float(u.ad_credits or 0.0)
    price = float(plan["price"])
    text = (
        f"👑 <b>{esc(plan['label'])}</b>\n\n"
        f"💳 رصيد محفظتك الحالي: <b>{credits:g} {DEFAULT_CURRENCY}</b>\n\n"
        f"{t(lang, 'ad_payment_instructions')}"
    )
    rows = []
    if credits >= price:
        rows.append([
            InlineKeyboardButton(
                text=f"💳 الدفع من المحفظة ({price:g} {DEFAULT_CURRENCY}) — تفعيل فوري ⚡",
                callback_data=f"vip_wallet:{sid}:{plan_key}",
            )
        ])
    rows.append([InlineKeyboardButton(text="📸 إرسال وصل دفع (CCP / BaridiMob)", callback_data=f"vip_proof:{sid}:{plan_key}")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"st_vip:{sid}")])
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("vip_wallet:"))
async def store_vip_wallet_pay(cb: CallbackQuery):
    _, sid_str, plan_key = cb.data.split(":")
    sid = int(sid_str)
    uid = cb.from_user.id
    if not await is_store_owner(uid, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    plan = VIP_PLANS.get(plan_key)
    if not plan:
        return await cb.answer("❌ باقة غير صالحة.", show_alert=True)
    price = float(plan["price"])
    days = int(plan["days"])
    lang = await get_lang(uid)

    async with Session() as s:
        res = await s.execute(
            update(User)
            .where(User.tg_id == uid, User.ad_credits >= price)
            .values(ad_credits=User.ad_credits - price)
        )
        if res.rowcount == 0:
            return await cb.answer("❌ رصيد المحفظة غير كافٍ.", show_alert=True)
        st = await s.get(Store, sid)
        if not st:
            await s.rollback()
            return await cb.answer("❌ المتجر غير موجود.", show_alert=True)
        base_dt = st.vip_until if (st.vip_until and st.vip_until > utcnow()) else utcnow()
        st.vip_until = base_dt + timedelta(days=days)
        st.verified = True
        st.auto_approve = True
        until_str = st.vip_until.strftime("%Y-%m-%d")
        st_name = st.name
        await s.commit()

    try:
        await cb.message.edit_text(
            f"👑 <b>مبروك! تم تفعيل باقة VIP لمتجر {esc(st_name)} فوراً!</b>\n\n"
            f"📅 صالح حتى: <b>{until_str}</b>\n"
            f"⚡ تم تفعيل التوثيق والنشر المباشر تلقائياً.",
            reply_markup=back_kb(lang, f"mngstore:{sid}"),
        )
    except Exception:
        await cb.message.answer(f"👑 تم تفعيل VIP لمتجر {esc(st_name)} حتى {until_str}!")
    await cb.answer("👑 تم التفعيل بنجاح!", show_alert=True)


@seller_router.callback_query(F.data.startswith("vip_proof:"))
async def store_vip_proof_prompt(cb: CallbackQuery, state: FSMContext):
    _, sid_str, plan_key = cb.data.split(":")
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid) or plan_key not in VIP_PLANS:
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(vip_sid=sid, vip_plan=plan_key)
    await state.set_state(StoreVipFSM.payment_proof)
    await cb.message.answer("📸 أرسل صورة وصل الدفع لتفعيل باقة VIP الآن (أو /cancel للإلغاء):")
    await cb.answer()


@seller_router.message(StoreVipFSM.payment_proof, F.photo)
async def store_vip_receive_proof(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    sid, plan_key = data.get("vip_sid"), data.get("vip_plan")
    await state.clear()
    if not (sid and plan_key in VIP_PLANS) or not await is_store_owner(message.from_user.id, sid):
        return await message.answer("انتهت الجلسة، ابدأ من جديد.")
    plan = VIP_PLANS[plan_key]
    proof = message.photo[-1].file_id
    async with Session() as s:
        st = await s.get(Store, sid)
        st_name = st.name if st else f"#{sid}"
        areq = AdRequest(
            user_tg_id=message.from_user.id,
            ad_type="store_vip",
            target_id=sid,
            package_name=plan_key,
            price=float(plan["price"]),
            payment_proof=proof,
            status="pending",
        )
        s.add(areq)
        await s.commit()
        await s.refresh(areq)
        areq_id = areq.id
    await message.answer(t(lang, "payment_proof_received"), reply_markup=await get_main_kb(message.from_user.id, lang))
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تأكيد وتفعيل VIP", callback_data=f"admin:confirm_payment:{areq_id}"),
        InlineKeyboardButton(text="❌ رفض الطلب", callback_data=f"admin:reject_payment:{areq_id}"),
    ]])
    await notify_admins(
        message.bot,
        f"👑 <b>طلب اشتراك VIP جديد #{areq_id}</b>\n"
        f"🏪 المتجر: <b>{esc(st_name)}</b> (#{sid})\n"
        f"👤 البائع: <code>{message.from_user.id}</code>\n"
        f"📦 الباقة: <b>{esc(plan['label'])}</b>",
        reply_markup=admin_kb,
        photo=proof,
    )


@seller_router.message(StoreVipFSM.payment_proof, ~F.photo)
async def store_vip_proof_invalid(message: Message):
    await message.answer("📸 يرجى إرسال صورة وصل الدفع (أو /cancel للإلغاء).")


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
    posted_ch = await publish_product_to_channel(cb.bot, pid)
    if followers:
        async def _notify_approved_followers():
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
        asyncio.create_task(_notify_approved_followers())
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=None)
    ch_note = "\n📢 تم النشر تلقائياً في القناة." if posted_ch else ""
    await cb.message.answer("✅ " + t("ar", "approved") + ch_note)
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


@seller_router.callback_query((F.data == "admin:gstats") | F.data.startswith("admin:gstats:"))
async def admin_gstats(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    parts = cb.data.split(":")
    days = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 30
    if days not in (0, 7, 30):
        days = 30
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        text = await _build_analytics_report(s, None, days, lang)
    kb = _analytics_kb("admin:gstats", "admin:gstats_csv", days, "menu:admin", lang)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:gstats_csv:"))
async def admin_gstats_csv(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    parts = cb.data.split(":")
    days = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 30
    if days not in (0, 7, 30):
        days = 30
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        csv_bytes = await _build_analytics_csv(s, None, days, lang)
    period_tag = f"{days}d" if days else "all"
    fname = f"platform_analytics_{period_tag}_{utcnow().strftime('%Y%m%d')}.csv"
    caption = t(
        lang,
        "analytics_csv_caption",
        period=_analytics_period_name(days, lang),
        date=utcnow().strftime("%Y-%m-%d %H:%M"),
    )
    await cb.message.answer_document(BufferedInputFile(csv_bytes, filename=fname), caption=caption)
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
    vip_str = (
        f"👑 مفعل حتى {st.vip_until.strftime('%Y-%m-%d')}"
        if is_store_vip(st)
        else "❌ غير مفعل"
    )
    auto_str = "⚡ مفعل" if (st.auto_approve or is_store_vip(st)) else "❌ متوقف"
    text = (
        f"🏪 <b>{esc(st.name)}</b>\n\n"
        f"👤 المالك: <code>{st.owner_tg_id}</code>\n"
        f"📦 المنتجات: {pcount}\n"
        f"📌 التوثيق: {'✅ موثق' if st.verified else '❌ غير موثق'}\n"
        f"👑 VIP: {vip_str}\n"
        f"⚡ النشر المباشر: {auto_str}\n"
        f"📝 {esc(st.bio or '-')}"
    )
    action_btn = (
        InlineKeyboardButton(text=t(lang, "btn_unverify"), callback_data=f"admin:unverify_store:{sid}")
        if st.verified
        else InlineKeyboardButton(text=t(lang, "btn_verify"), callback_data=f"admin:verify_store:{sid}")
    )
    auto_btn = InlineKeyboardButton(
        text="⚡ إيقاف النشر المباشر" if st.auto_approve else "⚡ تفعيل النشر المباشر",
        callback_data=f"admin:toggle_auto:{sid}",
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [action_btn],
        [InlineKeyboardButton(text="👑 منح/تمديد VIP (+30 يوم)", callback_data=f"admin:vip_store:{sid}")],
        [auto_btn],
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


@seller_router.callback_query(F.data.startswith("admin:vip_store:"))
async def admin_vip_store(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    sid = int(cb.data.split(":")[2])
    owner_id, st_name, until_str = None, "", ""
    async with Session() as s:
        st = await s.get(Store, sid)
        if st:
            base = st.vip_until if (st.vip_until and st.vip_until > utcnow()) else utcnow()
            st.vip_until = base + timedelta(days=30)
            st.verified = True
            st.auto_approve = True
            owner_id, st_name, until_str = st.owner_tg_id, st.name, st.vip_until.strftime("%Y-%m-%d")
            await s.commit()
    if owner_id:
        with suppress(Exception):
            await cb.bot.send_message(
                owner_id,
                f"👑 <b>تهانينا! تم تفعيل/تمديد باقة VIP لمتجرك {esc(st_name)} من قِبل الإدارة!</b>\n📅 صالح حتى: <b>{until_str}</b>",
            )
    await cb.answer("👑 تم منح/تمديد VIP لمدة 30 يوماً.", show_alert=True)
    await admin_store_view(cb)


@seller_router.callback_query(F.data.startswith("admin:toggle_auto:"))
async def admin_toggle_auto_approve(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    sid = int(cb.data.split(":")[2])
    new_val = False
    async with Session() as s:
        st = await s.get(Store, sid)
        if st:
            st.auto_approve = not bool(st.auto_approve)
            new_val = st.auto_approve
            await s.commit()
    await cb.answer("⚡ تم تفعيل النشر المباشر." if new_val else "⏸️ تم إيقاف النشر المباشر.", show_alert=True)
    await admin_store_view(cb)


# ─── Admin Broadcast (Background Task) ───

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
        users = list((await s.execute(select(User.tg_id))).scalars().all())
    _BROADCAST_COOLDOWN[message.from_user.id] = time.time()
    status = await message.answer(f"{t('ar', 'broadcast_started')} ({len(users)} مستخدم — يعمل في الخلفية)")
    done_tpl = t("ar", "broadcast_done", count="{count}")
    asyncio.create_task(_run_broadcast_task(message, users, status, done_tpl))


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


# ─── Admin Payment Requests (Product Ads, Wallet Top-up, Store VIP) ───

@seller_router.callback_query(F.data == "admin:adreqs")
async def admin_adreqs(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        reqs = (await s.execute(select(AdRequest).where(AdRequest.status == "pending").order_by(AdRequest.created_at.desc()))).scalars().all()
    if not reqs:
        return await cb.answer("لا توجد طلبات دفع معلقة.", show_alert=True)
    type_labels = {"product": "📢 تمييز منتج", "wallet_topup": "💳 شحن محفظة", "store_vip": "👑 باقة VIP"}
    text = t(lang, "ad_requests_pending") + "\n\n"
    kb = []
    for r in reqs:
        tl = type_labels.get(r.ad_type, r.ad_type)
        text += f"#{r.id} • {tl} • user <code>{r.user_tg_id}</code>\nالباقة: {esc(r.package_name)} • {r.price:.0f} {DEFAULT_CURRENCY}\n\n"
        kb.append([
            InlineKeyboardButton(text=f"💰 تأكيد #{r.id}", callback_data=f"admin:confirm_payment:{r.id}"),
            InlineKeyboardButton(text=f"❌ رفض #{r.id}", callback_data=f"admin:reject_payment:{r.id}"),
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

    async with Session() as s:
        areq = (await s.execute(select(AdRequest).where(AdRequest.id == areq_id))).scalar_one_or_none()
        if not areq or areq.status != "pending":
            return await cb.answer("Not found أو تمت معالجته.", show_alert=True)

        areq.status = "approved"
        user_id = areq.user_tg_id
        user_msg = ""
        admin_alert = "✅ تم التأكيد."

        if areq.ad_type == "product":
            pkg = AD_PACKAGES.get(areq.package_name, AD_PACKAGES["basic"])
            days = int(pkg["days"])
            label = pkg["label"]
            prod = (await s.execute(select(Product).where(Product.id == areq.target_id, Product.is_deleted.is_(False)))).scalar_one_or_none()
            if prod:
                now = utcnow()
                base = prod.featured_until if (prod.featured_until and prod.featured_until > now) else now
                prod.featured_until = base + timedelta(days=days)
                user_msg = (
                    f"✅ تم تأكيد دفعك! (باقة {label})\n"
                    f"⭐ منتجك <b>{esc(prod.title)}</b> أصبح مميزاً لمدة <b>{days}</b> أيام، حتى <b>{prod.featured_until.strftime('%Y-%m-%d')}</b>."
                )
            else:
                user_msg = f"✅ تم تأكيد دفعك لباقة {label}."
            admin_alert = f"✅ تم تأكيد تمييز المنتج ({days} يوم)."

        elif areq.ad_type == "store_vip":
            plan = VIP_PLANS.get(areq.package_name, VIP_PLANS["vip_30"])
            days = int(plan["days"])
            st = await s.get(Store, areq.target_id)
            if st:
                now = utcnow()
                base = st.vip_until if (st.vip_until and st.vip_until > now) else now
                st.vip_until = base + timedelta(days=days)
                st.verified = True
                st.auto_approve = True
                user_msg = (
                    f"👑 <b>مبروك! تم تأكيد وتفعيل باقة VIP لمتجرك {esc(st.name)}!</b>\n"
                    f"📅 صالح حتى: <b>{st.vip_until.strftime('%Y-%m-%d')}</b>\n"
                    f"⚡ تم تفعيل التوثيق والنشر المباشر تلقائياً."
                )
            else:
                user_msg = "👑 تم تأكيد اشتراك VIP الخاص بك."
            admin_alert = f"👑 تم تفعيل VIP للمتجر ({days} يوم)."

        else:
            # wallet_topup
            u = await ensure_user(s, areq.user_tg_id, DEFAULT_LANG)
            u.ad_credits = float(u.ad_credits or 0.0) + float(areq.price)
            new_bal = u.ad_credits
            user_msg = (
                f"💳 <b>تم شحن محفظتك بنجاح!</b>\n"
                f"➕ المبلغ المضاف: <b>{areq.price:g} {DEFAULT_CURRENCY}</b>\n"
                f"💰 رصيدك الحالي: <b>{new_bal:g} {DEFAULT_CURRENCY}</b>"
            )
            admin_alert = f"💳 تم شحن {areq.price:g} {DEFAULT_CURRENCY} لمحفظة المستخدم."

        await s.commit()

    if user_id and user_msg:
        with suppress(Exception):
            await cb.bot.send_message(user_id, user_msg)

    await cb.answer(admin_alert, show_alert=True)
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


# ─── Admin Auto-Post Channel Management ───

@seller_router.callback_query(F.data == "admin:channel")
async def admin_channel_menu(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.clear()
    lang = await get_lang(cb.from_user.id)
    ch = (await get_setting("auto_channel_id", "")).strip()
    status_line = f"📌 القناة الحالية: <code>{esc(ch)}</code>" if ch else "📌 القناة الحالية: <b>غير مفعّلة</b>"
    text = (
        f"📢 <b>إعدادات قناة النشر التلقائي</b>\n\n"
        f"{status_line}\n\n"
        f"💡 عند ربط قناة (مع رفع البوت كمشرف فيها)، سيتم نشر كل منتج جديد يُوافق عليه تلقائياً مع صورته وسعره وزر للطلب المباشر داخل البوت!"
    )
    rows = [
        [InlineKeyboardButton(text="✏️ تعيين / تغيير القناة", callback_data="admin:channel_set")],
    ]
    if ch:
        rows.append([InlineKeyboardButton(text="🧪 إرسال رسالة تجريبية للقناة", callback_data="admin:channel_test")])
        rows.append([InlineKeyboardButton(text="🗑️ إيقاف النشر التلقائي", callback_data="admin:channel_clear")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")])
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@seller_router.callback_query(F.data == "admin:channel_set")
async def admin_channel_set_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.set_state(AdminChannelFSM.channel_id)
    await cb.message.answer(
        "📢 أرسل معرف القناة (مثال: <code>@MyMarketChannel</code> أو <code>-1001234567890</code>).\n"
        "⚠️ تأكد من إضافة البوت كمشرف في القناة أولاً."
    )
    await cb.answer()


@seller_router.message(AdminChannelFSM.channel_id)
async def admin_channel_set_save(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    raw = (message.text or "").strip()
    if not (raw.startswith("@") or (raw.startswith("-100") and raw[1:].isdigit())):
        return await message.answer("❌ صيغة غير صحيحة. أرسل معرفاً مثل <code>@MyChannel</code> أو <code>-1001234567890</code>.")
    await set_setting("auto_channel_id", raw)
    await state.clear()
    await message.answer(
        f"✅ تم ربط قناة النشر التلقائي بنجاح: <code>{esc(raw)}</code>",
        reply_markup=back_kb(await get_lang(message.from_user.id), "admin:channel"),
    )


@seller_router.callback_query(F.data == "admin:channel_test")
async def admin_channel_test(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    ch = (await get_setting("auto_channel_id", "")).strip()
    if not ch:
        return await cb.answer("لا توجد قناة مربوطة.", show_alert=True)
    try:
        await cb.bot.send_message(ch, "✅ <b>رسالة تجريبية:</b> تم ربط القناة بنجاح بنظام النشر التلقائي للمتجر!")
        await cb.answer("✅ تم إرسال الرسالة التجريبية بنجاح!", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ فشل الإرسال: تأكد أن البوت مشرف في القناة ({str(e)[:80]})", show_alert=True)


@seller_router.callback_query(F.data == "admin:channel_clear")
async def admin_channel_clear(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await set_setting("auto_channel_id", "")
    await cb.answer("🗑️ تم إيقاف النشر التلقائي في القناة.", show_alert=True)
    await admin_channel_menu(cb, state)


# ─── Admin Manual Database Backup ───

@seller_router.message(Command("backup"))
async def cmd_admin_backup(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("⏳ جاري إنشاء نسخة احتياطية آمنة من قاعدة البيانات...")
    ok = await send_backup_to_admins(message.bot, target_chat_id=message.from_user.id, auto=False)
    if not ok:
        await message.answer("❌ تعذر إنشاء النسخة الاحتياطية.")


@seller_router.callback_query(F.data == "admin:backup")
async def admin_backup_cb(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await cb.answer("⏳ جاري إنشاء وإرسال النسخة الاحتياطية...", show_alert=True)
    ok = await send_backup_to_admins(cb.bot, target_chat_id=cb.from_user.id, auto=False)
    if not ok:
        await cb.message.answer("❌ تعذر إنشاء النسخة الاحتياطية.")


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


async def daily_backup_task(bot: Bot) -> None:
    """Automatically send a safe SQLite WAL backup to admins once every 24 hours."""
    while True:
        try:
            await asyncio.sleep(86400)
            logger.info("Running daily automatic database backup...")
            await send_backup_to_admins(bot, auto=True)
        except asyncio.CancelledError:
            logger.info("daily_backup_task cancelled")
            raise
        except Exception:
            logger.exception("Unexpected error in daily_backup_task")


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
    bg_tasks: list[asyncio.Task] = []

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

        bg_tasks.append(asyncio.create_task(abandoned_cart_task(bot)))
        bg_tasks.append(asyncio.create_task(daily_backup_task(bot)))
        await dp.start_polling(bot)

    finally:
        for task in bg_tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
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
