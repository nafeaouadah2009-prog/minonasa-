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
import importlib
import importlib.util
import io
import json
import logging
import math
import os
import re
import secrets
import site
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Final, Optional


with suppress(Exception):
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)


def _ensure_runtime_deps() -> None:
    """Auto-install missing core runtime dependencies on minimal Python-only hosts."""
    required = (
        ("aiogram", "aiogram"),
        ("sqlalchemy", "sqlalchemy"),
        ("greenlet", "greenlet"),
        ("aiosqlite", "aiosqlite"),
        ("qrcode", "qrcode"),
    )
    missing = [pkg for mod, pkg in required if importlib.util.find_spec(mod) is None]
    if not missing:
        return
    print(f"[bootstrap] Installing missing dependencies: {' '.join(missing)}", flush=True)
    install_cmds = (
        [sys.executable, "-m", "pip", "install", "--no-cache-dir", *missing],
        [sys.executable, "-m", "pip", "install", "--user", "--no-cache-dir", *missing],
        [sys.executable, "-m", "pip", "install", "--user", "--break-system-packages", "--no-cache-dir", *missing],
    )
    for cmd in install_cmds:
        try:
            subprocess.check_call(cmd)
            break
        except Exception:
            continue
    with suppress(Exception):
        user_site = site.getusersitepackages()
        if user_site and user_site not in sys.path:
            sys.path.append(user_site)
    importlib.invalidate_caches()


_ensure_runtime_deps()

import aiosqlite  # noqa: F401, E402
import greenlet  # noqa: F401, E402
import qrcode  # noqa: E402
from aiogram import Bot, Dispatcher, F, Router  # noqa: E402
try:
    from aiogram import BaseMiddleware
except ImportError:
    from aiogram.dispatcher.middlewares.base import BaseMiddleware
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
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    TelegramObject,
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
MAX_STORES_FREE: Final[int] = 1
MAX_STORES_PRO: Final[int] = 2
MAX_STORES_PER_USER: Final[int] = 3
MAX_STORES_VIP: Final[int] = 5
MAX_PRODUCTS_FREE: Final[int] = 15
MAX_PRODUCTS_PRO: Final[int] = 50
MAX_PRODUCT_PHOTOS: Final[int] = 3
SUB_GRACE_HOURS: Final[int] = 48
TRIAL_DAYS: Final[int] = 7

AD_PACKAGES: Final[dict[str, dict[str, Any]]] = {
    "basic": {"days": 3, "price": 1000.0, "label": "أساسية (3 أيام)"},
    "pro": {"days": 7, "price": 2000.0, "label": "احترافية (7 أيام)"},
    "vip": {"days": 30, "price": 7000.0, "label": "VIP (30 يوم)"},
}

VIP_PLANS: Final[dict[str, dict[str, Any]]] = {
    "pro_30": {"tier": "pro", "days": 30, "price": 1500.0, "bonus": 0.0, "label": "⭐ باقة Pro شهرية (30 يوم)"},
    "vip_30": {"tier": "vip", "days": 30, "price": 3000.0, "bonus": 500.0, "label": "👑 باقة VIP شهرية (30 يوم)"},
    "vip_90": {"tier": "vip", "days": 90, "price": 7500.0, "bonus": 1500.0, "label": "👑 باقة VIP ربع سنوية (90 يوم)"},
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


# ─── Top 5 Algerian E-Commerce Delivery Companies Catalog & 58-Wilaya Regional Grids ───

_WILAYA_ZONE_CENTER: Final[frozenset[str]] = frozenset({"09", "16", "35", "42"})
_WILAYA_ZONE_HIGHLANDS: Final[frozenset[str]] = frozenset({
    "04", "05", "12", "14", "17", "19", "20", "28", "32", "34", "38", "40", "41", "43", "45",
})
_WILAYA_ZONE_MID_SOUTH: Final[frozenset[str]] = frozenset({
    "03", "07", "08", "30", "39", "47", "51", "52", "55", "57", "58",
})
_WILAYA_ZONE_DEEP_SOUTH: Final[frozenset[str]] = frozenset({
    "01", "11", "33", "37", "49", "50", "53", "54", "56",
})


def get_wilaya_zone(code: str) -> str:
    c = str(code).zfill(2)
    if c in _WILAYA_ZONE_CENTER:
        return "center"
    if c in _WILAYA_ZONE_DEEP_SOUTH:
        return "deep_south"
    if c in _WILAYA_ZONE_MID_SOUTH:
        return "mid_south"
    if c in _WILAYA_ZONE_HIGHLANDS:
        return "highlands"
    return "north"


DELIVERY_COMPANIES: Final[dict[str, dict[str, Any]]] = {
    "yalidine": {
        "code": "yalidine",
        "emoji": "🟡",
        "name": "Yalidine Express",
        "name_ar": "ياليدين إكسبريس",
        "tagline": "الرائدة في التوصيل السريع وأكبر شبكة مكاتب Stop Desk في الجزائر",
        "coverage": "58 ولاية (أكبر شبكة وكالات ومكاتب استلام في الوطن)",
        "speed_north": "24 – 48 ساعة",
        "speed_south": "3 – 5 أيام",
        "price_summary": (
            "✦ 🏠 <b>للمنزل:</b> الشمال 600–850 دج | الهضاب 850–950 دج | الجنوب 1000–1700 دج\n"
            "✦ 🏢 <b>مكتب (Stop Desk):</b> الشمال 350–500 دج | الجنوب 700–1300 دج"
        ),
        "extra_kg": "+50 دج/كغ (الشمال) إلى +100 دج/كغ (الجنوب) بعد 5 كغ",
        "cod_info": "تحصيل الدفع عند الاستلام (COD) + تحويل منتظم عبر البنك أو CCP",
        "return_info": "إرجاع منظّم للطرود غير المستلمة عبر أقرب مكتب",
        "features": [
            "أوسع شبكة مكاتب Stop Desk في أغلب الدوائر والبلديات",
            "نظام تتبع رقمي دقيق لحظة بلحظة + إشعارات SMS للزبائن",
            "واجهة API احترافية للمتاجر (api.yalidine.app/v1)",
            "دعم التوصيل مع إمكانية التبديل (Echange)",
        ],
        "best_for": "المتاجر التي تعتمد بكثرة على التوصيل للمكتب (Stop Desk) والوصول لكل البلديات",
        "website": "https://yalidine.com",
        "portal_url": "https://yalidine.app",
        "tracking_url": "https://yalidine.com/suivre-un-colis",
        "api_info": "متوفر (REST API — https://api.yalidine.app/v1)",
        "phone": "+213 0982 30 80 80",
        "email": "contact@yalidine.com",
        "hq": "الجزائر العاصمة",
        "zone_rates": {
            "center": (600.0, 350.0),
            "north": (750.0, 450.0),
            "highlands": (850.0, 500.0),
            "mid_south": (1050.0, 700.0),
            "deep_south": (1600.0, 1200.0),
        },
    },
    "zr_express": {
        "code": "zr_express",
        "emoji": "🔵",
        "name": "ZR Express",
        "name_ar": "زد آر إكسبريس",
        "tagline": "سرعة عالية في الشحن بين الولايات وتحويل سريع لمستحقات التجار",
        "coverage": "58 ولاية (ربط سريع بين الشرق والغرب والجنوب)",
        "speed_north": "24 – 48 ساعة",
        "speed_south": "2 – 4 أيام",
        "price_summary": (
            "✦ 🏠 <b>للمنزل:</b> الشمال 600–800 دج | الهضاب 800–900 دج | الجنوب 950–1550 دج\n"
            "✦ 🏢 <b>مكتب (Stop Desk):</b> الشمال 400–500 دج | الجنوب 650–1150 دج"
        ),
        "extra_kg": "+50 دج/كغ (الشمال) إلى +100 دج/كغ (الجنوب) بعد 5 كغ",
        "cod_info": "تحصيل COD سريع + عقود تجارية وتخفيضات للمتاجر ذات الحجم الكبير (50+ طرد/أسبوع)",
        "return_info": "إدارة سريعة للمرتجعات مع متابعة عبر تطبيق ZR Marchand",
        "features": [
            "سرعة فائقة في نقل الطرود بين المحاور الرئيسية",
            "تطبيق مخصص للتجار (ZR Marchand) + منصة ويب سلسة",
            "أسعار تفضيلية وعقود خاصة للمتاجر ذات المبيعات المرتفعة",
            "نسبة تأكيد وتسليم ممتازة مع متابعة هاتفية للزبائن",
        ],
        "best_for": "التجار الباحثين عن سرعة التسليم وتحويل سريع للأموال وأسعار ممتازة للكميات",
        "website": "https://zrexpress.dz",
        "portal_url": "https://app.zrexpress.dz",
        "tracking_url": "https://zrexpress.dz/",
        "api_info": "متوفر عبر بوابة التجار (app.zrexpress.dz)",
        "phone": "+213 23 00 00 00",
        "email": "contact@zrexpress.dz",
        "hq": "الجزائر العاصمة",
        "zone_rates": {
            "center": (600.0, 400.0),
            "north": (700.0, 450.0),
            "highlands": (800.0, 500.0),
            "mid_south": (950.0, 650.0),
            "deep_south": (1450.0, 1100.0),
        },
    },
    "maystro": {
        "code": "maystro",
        "emoji": "🟣",
        "name": "Maystro Delivery",
        "name_ar": "مايسترو ديليفري",
        "tagline": "حلول لوجستية ذكية للتجارة الإلكترونية مع التخزين والتغليف (Fulfillment)",
        "coverage": "50+ ولاية (مستودعات ذكية ومراكز توزيع حديثة)",
        "speed_north": "24 – 48 ساعة",
        "speed_south": "2 – 5 أيام",
        "price_summary": (
            "✦ 🏠 <b>للمنزل:</b> الشمال 600–800 دج | الهضاب 800–900 دج | الجنوب 1000–1500 دج\n"
            "✦ 🏢 <b>مكتب (Stop Desk):</b> الشمال 400–500 دج | الجنوب 700–1150 دج"
        ),
        "extra_kg": "+50 إلى +100 دج/كغ حسب المنطقة وباقة التاجر",
        "cod_info": "تحصيل COD + باقات أعمال مرنة (Starter / Business / Premium)",
        "return_info": "تتبع فوري للمرتجعات ومحاولة إعادة الاتصال بالزبون",
        "features": [
            "خدمة التخزين والتغليف والشحن الكامل (Fulfillment)",
            "تطبيق ذكي للتجار ولوحة تحكم تقنية متطورة",
            "خيارات متقدمة لتأكيد الطلبات ورفع نسبة التسليم",
            "ربط سلس مع منصات التجارة الإلكترونية عبر API",
        ],
        "best_for": "المتاجر الإلكترونية الحديثة التي تحتاج تغليفاً وتخزيناً وإدارة ذكية عبر الهاتف",
        "website": "https://maystro-delivery.com",
        "portal_url": "https://maystro-delivery.com",
        "tracking_url": "https://maystro-delivery.com",
        "api_info": "متوفر (API + ربط مباشر مع المتاجر الإلكترونية)",
        "phone": "+213 0982 482 483 / +213 0770 008 158",
        "email": "support@maystro-delivery.com",
        "hq": "القبة / واد السمار — الجزائر العاصمة",
        "zone_rates": {
            "center": (600.0, 400.0),
            "north": (750.0, 450.0),
            "highlands": (850.0, 500.0),
            "mid_south": (1000.0, 700.0),
            "deep_south": (1500.0, 1150.0),
        },
    },
    "guepex": {
        "code": "guepex",
        "emoji": "🟠",
        "name": "GuepEX Express",
        "name_ar": "غيبيكس إكسبريس",
        "tagline": "تغطية 58 ولاية بأسعار اقتصادية ودعم الطرود العادية والثقيلة",
        "coverage": "58 ولاية (مئات الوكالات المحلية عبر كامل التراب الوطني)",
        "speed_north": "24 – 48 ساعة",
        "speed_south": "3 – 5 أيام",
        "price_summary": (
            "✦ 🏠 <b>للمنزل:</b> الشمال ~600 دج | الوسط والجنوب المتوسط ~750–900 دج | أقصى الجنوب 1250–1450 دج\n"
            "✦ 🏢 <b>مكتب (Stop Desk):</b> الشمال ~450 دج | الوسط ~550 دج | الجنوب 900–1100 دج"
        ),
        "extra_kg": "+50 دج/كغ (المناطق العادية) و +100 دج/كغ (أقصى الجنوب) بعد 5 كغ",
        "cod_info": "تحصيل COD بسقف يصل إلى 150,000 دج للطرد الواحد مع تحويل بنكي/شيك",
        "return_info": "عروض دورية بإرجاع مجاني (0 دج) للتجار المتعاقدين",
        "features": [
            "أسعار تنافسية جداً خاصة للشمال والجنوب المتوسط",
            "دعم شحن البضائع الثقيلة والكبيرة إلى جانب طرود الإيكومرس",
            "سقف تحصيل COD مرتفع يصل إلى 150,000 دج للطرد",
            "تغطية شاملة لـ 58 ولاية بخدمتي المنزل والـ Stop Desk",
        ],
        "best_for": "المنتجات الثقيلة أو مرتفعة السعر، والتجار الباحثين عن أسعار اقتصادية لـ 58 ولاية",
        "website": "https://www.guepex.dz",
        "portal_url": "https://www.guepex.dz",
        "tracking_url": "https://www.guepex.dz",
        "api_info": "متوفر عبر حساب التاجر",
        "phone": "0541 01 01 01",
        "email": "Contact@Guepex.dz",
        "hq": "المنطقة الصناعية دار البيضاء — الجزائر العاصمة",
        "zone_rates": {
            "center": (550.0, 400.0),
            "north": (600.0, 450.0),
            "highlands": (700.0, 500.0),
            "mid_south": (850.0, 600.0),
            "deep_south": (1350.0, 1000.0),
        },
    },
    "noest": {
        "code": "noest",
        "emoji": "🟢",
        "name": "Noest Express",
        "name_ar": "نويست إكسبريس (Nord & Ouest)",
        "tagline": "شبكة محطات جهوية قوية وأسعار مرنة للتجارة الإلكترونية وB2B",
        "coverage": "58 ولاية (محطات جهوية ومكاتب استلام في المدن الكبرى)",
        "speed_north": "24 – 48 ساعة",
        "speed_south": "2 – 5 أيام",
        "price_summary": (
            "✦ 🏠 <b>للمنزل:</b> الشمال 600–800 دج | الهضاب 750–900 دج | الجنوب 1000–1550 دج\n"
            "✦ 🏢 <b>مكتب (Stop Desk):</b> الشمال 400–500 دج | الجنوب 700–1150 دج"
        ),
        "extra_kg": "+50 إلى +100 دج/كغ حسب الوزن والمنطقة",
        "cod_info": "تحصيل COD مدمج في منصة التجار مع تحويل دوري منتظم",
        "return_info": "معالجة سريعة للطرود الراجعة عبر المحطات الجهوية",
        "features": [
            "أسطول نقل خاص ومحطات توزيع قوية في الشمال والغرب والشرق",
            "مرونة عالية في التعامل مع التجار الجدد وأصحاب المتاجر الصغيرة والكبيرة",
            "دعم التوصيل للمنزل وللمكتب (Stop Desk) عبر 58 ولاية",
            "منصة سهلة لرفع الطلبات بملف Excel/CSV وتتبع الطرود",
        ],
        "best_for": "المتاجر الناشئة والمتوسطة وتجارة الجملة/التجزئة الباحثة عن مرونة وسهولة الاشتراك",
        "website": "https://noest-dz.com",
        "portal_url": "https://noest-dz.com",
        "tracking_url": "https://noest-dz.com/",
        "api_info": "متوفر (API + استيراد ملفات Excel/CSV)",
        "phone": "+213 561 62 35 25",
        "email": "s.client@noest-dz.com",
        "hq": "أولاد موسى (بومرداس) / الشراقة (الجزائر)",
        "zone_rates": {
            "center": (600.0, 400.0),
            "north": (700.0, 450.0),
            "highlands": (800.0, 500.0),
            "mid_south": (1000.0, 700.0),
            "deep_south": (1500.0, 1100.0),
        },
    },
}


def get_delivery_company(code: str) -> Optional[dict[str, Any]]:
    return DELIVERY_COMPANIES.get((code or "").strip().lower())


def get_company_wilaya_rate(company_code: str, wilaya_code: str) -> tuple[float, float]:
    co = get_delivery_company(company_code)
    if not co:
        return (700.0, 450.0)
    zone = get_wilaya_zone(wilaya_code)
    return co["zone_rates"].get(zone, (700.0, 450.0))


# ─── Seller Website Creation Studio Catalog ───

WEBSITE_PACKAGES: Final[dict[str, dict[str, Any]]] = {
    "landing": {
        "code": "landing",
        "emoji": "⚡",
        "title": "صفحة هبوط احترافية (Landing Page)",
        "price_hint": "ابتداءً من 10,000 دج",
        "days_hint": "2 – 4 أيام",
        "desc": "صفحة سريعة عالية التحويل لإعلانات Facebook و TikTok مع استمارة طلب مباشرة لـ 58 ولاية وربط Pixel.",
    },
    "ecommerce": {
        "code": "ecommerce",
        "emoji": "🛍️",
        "title": "متجر إلكتروني متكامل (Full Store)",
        "price_hint": "ابتداءً من 25,000 دج",
        "days_hint": "5 – 10 أيام",
        "desc": "متجر متكامل بمنتجات غير محدودة، سلة مشتريات، لوحة تحكم، أسعار توصيل 58 ولاية، كوبونات خصم وإحصائيات.",
    },
    "custom_pro": {
        "code": "custom_pro",
        "emoji": "👑",
        "title": "موقع فاخر مخصص + ربط ذكي (VIP Pro)",
        "price_hint": "حسب المواصفات والاتفاق",
        "days_hint": "7 – 15 يوماً",
        "desc": "هوية بصرية حصرية، دفع إلكتروني (EDAHABIA / CIB)، ربط تلقائي مع بوت تيليجرام وشركات التوصيل ودعم أولوي.",
    },
}

WEBSITE_FEATURES: Final[dict[str, str]] = {
    "wilayas58": "🚚 توصيل 58 ولاية + Stop Desk",
    "chargily": "⚡ دفع إلكتروني EDAHABIA / CIB",
    "pixel": "📊 ربط Facebook & TikTok Pixel",
    "domain": "🌍 دومين احترافي (.com / .dz)",
    "multilang": "🌐 متعدد اللغات (عربي / فرنسي)",
    "bot_sync": "🤖 ربط مباشر مع بوت تيليجرام",
}

WEBSITE_BUDGETS: Final[list[str]] = [
    "💵 أقل من 15,000 دج",
    "💰 15,000 – 35,000 دج",
    "💎 35,000 – 70,000 دج",
    "👑 أكثر من 70,000 دج",
    "🤝 حسب الاتفاق مع المطور",
]

WEBSITE_STATUS_LABELS: Final[dict[str, str]] = {
    "pending": "⏳ قيد المراجعة",
    "negotiating": "💬 قيد النقاش والتسعير",
    "in_progress": "🛠️ جاري التنفيذ",
    "completed": "✅ مكتمل ومسلّم",
    "cancelled": "❌ ملغي",
}


# ─── Legendary Achievements, Missions & Badges System (Sellers & Buyers) ───

BADGE_CATALOG: Final[dict[str, dict[str, Any]]] = {
    # 🏪 Seller Badges (16 Missions)
    "seller_starter": {
        "code": "seller_starter",
        "role": "seller",
        "emoji": "🌱",
        "title": "البائع الطموح",
        "desc": "افتح متجرك وانشر أول منتج معتمد في المنصة",
        "target": 1,
        "xp": 50,
        "reward_dzd": 0.0,
    },
    "seller_brand": {
        "code": "seller_brand",
        "role": "seller",
        "emoji": "🎨",
        "title": "صاحب الهوية",
        "desc": "أضف شعاراً (Logo) + وصفاً + شركة توصيل معتمدة لمتجرك",
        "target": 3,
        "xp": 150,
        "reward_dzd": 0.0,
    },
    "seller_first_sale": {
        "code": "seller_first_sale",
        "role": "seller",
        "emoji": "🎉",
        "title": "أول صفقة ناجحة",
        "desc": "أتمم أول طلب مكتمل بنجاح في متجرك",
        "target": 1,
        "xp": 100,
        "reward_dzd": 0.0,
    },
    "seller_promo_master": {
        "code": "seller_promo_master",
        "role": "seller",
        "emoji": "🎟️",
        "title": "صانع العروض",
        "desc": "أنشئ أول كود خصم ترويجي لجذب الزبائن لمتجرك",
        "target": 1,
        "xp": 90,
        "reward_dzd": 0.0,
    },
    "seller_flash_king": {
        "code": "seller_flash_king",
        "role": "seller",
        "emoji": "⚡",
        "title": "برق التخفيضات",
        "desc": "أطلق عرضاً سريعاً (Flash Sale) على منتج أو أكثر",
        "target": 1,
        "xp": 100,
        "reward_dzd": 0.0,
    },
    "seller_58_wilayas": {
        "code": "seller_58_wilayas",
        "role": "seller",
        "emoji": "🗺️",
        "title": "تغطية وطنية شاملة",
        "desc": "اضبط أسعار التوصيل لـ 30 ولاية جزائرية أو أكثر",
        "target": 30,
        "xp": 120,
        "reward_dzd": 0.0,
    },
    "seller_catalog": {
        "code": "seller_catalog",
        "role": "seller",
        "emoji": "📦",
        "title": "صانع التشكيلة",
        "desc": "اعرض 10 منتجات معتمدة أو أكثر في متجرك",
        "target": 10,
        "xp": 120,
        "reward_dzd": 0.0,
    },
    "seller_mega_catalog": {
        "code": "seller_mega_catalog",
        "role": "seller",
        "emoji": "🏬",
        "title": "المعرض الكبير",
        "desc": "انشر 30 منتجاً معتمداً أو أكثر (+هدية 50 دج!)",
        "target": 30,
        "xp": 220,
        "reward_dzd": 50.0,
    },
    "seller_views_star": {
        "code": "seller_views_star",
        "role": "seller",
        "emoji": "👁️",
        "title": "جاذب الأنظار",
        "desc": "احصل على 500 مشاهدة أو أكثر لمنتجات متجرك",
        "target": 500,
        "xp": 160,
        "reward_dzd": 0.0,
    },
    "seller_pro": {
        "code": "seller_pro",
        "role": "seller",
        "emoji": "🏅",
        "title": "البائع البارع",
        "desc": "أتمم 10 طلبات مكتملة بنجاح (+هدية 100 دج!)",
        "target": 10,
        "xp": 250,
        "reward_dzd": 100.0,
    },
    "seller_loved": {
        "code": "seller_loved",
        "role": "seller",
        "emoji": "⭐",
        "title": "محبوب الزبائن",
        "desc": "احصل على 5 تقييمات بمتوسط 4.5⭐ أو أعلى",
        "target": 5,
        "xp": 200,
        "reward_dzd": 0.0,
    },
    "seller_five_star": {
        "code": "seller_five_star",
        "role": "seller",
        "emoji": "🌟",
        "title": "نجم الخمس نجوم",
        "desc": "احصل على 10 تقييمات بـ 5 نجوم كاملة (+هدية 80 دج!)",
        "target": 10,
        "xp": 260,
        "reward_dzd": 80.0,
    },
    "seller_influencer": {
        "code": "seller_influencer",
        "role": "seller",
        "emoji": "🔥",
        "title": "النجم الصاعد",
        "desc": "اجمع 25 متابعاً أو أكثر لمتجرك",
        "target": 25,
        "xp": 220,
        "reward_dzd": 0.0,
    },
    "seller_verified_pro": {
        "code": "seller_verified_pro",
        "role": "seller",
        "emoji": "💎",
        "title": "التاجر المعتمد",
        "desc": "متجر موثّق ✅ أو مشترك PRO/VIP أو يمتلك طلب موقع إلكتروني",
        "target": 1,
        "xp": 200,
        "reward_dzd": 0.0,
    },
    "seller_master": {
        "code": "seller_master",
        "role": "seller",
        "emoji": "💼",
        "title": "التاجر المخضرم",
        "desc": "أتمم 25 طلباً مكتملاً بنجاح (+هدية 150 دج!)",
        "target": 25,
        "xp": 350,
        "reward_dzd": 150.0,
    },
    "seller_legend": {
        "code": "seller_legend",
        "role": "seller",
        "emoji": "👑",
        "title": "أسطورة التجارة",
        "desc": "أتمم 50 طلباً مكتملاً بنجاح (+هدية 300 دج رصيد ترويج!)",
        "target": 50,
        "xp": 600,
        "reward_dzd": 300.0,
    },
    # 🛍️ Buyer Badges (16 Missions)
    "buyer_complete": {
        "code": "buyer_complete",
        "role": "buyer",
        "emoji": "🪪",
        "title": "الملف الذهبي",
        "desc": "أكمل بيانات ملفك الشخصي (الاسم + الهاتف + العنوان)",
        "target": 3,
        "xp": 60,
        "reward_dzd": 0.0,
    },
    "buyer_first": {
        "code": "buyer_first",
        "role": "buyer",
        "emoji": "🛍️",
        "title": "المشتري المبادر",
        "desc": "أتمم أول طلب ناجح لك داخل المنصة",
        "target": 1,
        "xp": 80,
        "reward_dzd": 0.0,
    },
    "buyer_explorer": {
        "code": "buyer_explorer",
        "role": "buyer",
        "emoji": "❤️",
        "title": "مستكشف العروض",
        "desc": "احفظ 5 منتجات أو أكثر في قائمة المفضلة",
        "target": 5,
        "xp": 75,
        "reward_dzd": 0.0,
    },
    "buyer_collector": {
        "code": "buyer_collector",
        "role": "buyer",
        "emoji": "💖",
        "title": "عاشق التسوق",
        "desc": "احفظ 20 منتجاً أو أكثر في قائمة المفضلة",
        "target": 20,
        "xp": 140,
        "reward_dzd": 0.0,
    },
    "buyer_fan": {
        "code": "buyer_fan",
        "role": "buyer",
        "emoji": "🔔",
        "title": "داعم المتاجر",
        "desc": "تابع 3 متاجر أو أكثر لتصلك أحدث عروضها",
        "target": 3,
        "xp": 75,
        "reward_dzd": 0.0,
    },
    "buyer_superfan": {
        "code": "buyer_superfan",
        "role": "buyer",
        "emoji": "📣",
        "title": "سفير المتاجر",
        "desc": "تابع 10 متاجر أو أكثر داخل المنصة",
        "target": 10,
        "xp": 160,
        "reward_dzd": 0.0,
    },
    "buyer_multi_store": {
        "code": "buyer_multi_store",
        "role": "buyer",
        "emoji": "🧭",
        "title": "الرحّالة الذكي",
        "desc": "اشترِ بنجاح من 3 متاجر مختلفة أو أكثر",
        "target": 3,
        "xp": 150,
        "reward_dzd": 0.0,
    },
    "buyer_critic": {
        "code": "buyer_critic",
        "role": "buyer",
        "emoji": "✍️",
        "title": "الناقد الخبير",
        "desc": "قيّم 3 متاجر أو أكثر لمساعدة باقي المشترين",
        "target": 3,
        "xp": 120,
        "reward_dzd": 0.0,
    },
    "buyer_super_critic": {
        "code": "buyer_super_critic",
        "role": "buyer",
        "emoji": "📝",
        "title": "خبير التقييمات",
        "desc": "قيّم 10 متاجر أو أكثر (+هدية 50 دج!)",
        "target": 10,
        "xp": 220,
        "reward_dzd": 50.0,
    },
    "buyer_trusted": {
        "code": "buyer_trusted",
        "role": "buyer",
        "emoji": "🛡️",
        "title": "المشتري الموثوق",
        "desc": "أتمم 3 طلبات مكتملة بنسبة 0% إلغاء",
        "target": 3,
        "xp": 200,
        "reward_dzd": 0.0,
    },
    "buyer_loyal": {
        "code": "buyer_loyal",
        "role": "buyer",
        "emoji": "💎",
        "title": "الزبون الوفي",
        "desc": "أتمم 5 طلبات مكتملة بنجاح (+هدية 50 دج!)",
        "target": 5,
        "xp": 180,
        "reward_dzd": 50.0,
    },
    "buyer_patron": {
        "code": "buyer_patron",
        "role": "buyer",
        "emoji": "⚡",
        "title": "المشتري الذهبي",
        "desc": "أتمم 10 طلبات مكتملة بنجاح (+هدية 100 دج!)",
        "target": 10,
        "xp": 300,
        "reward_dzd": 100.0,
    },
    "buyer_variety": {
        "code": "buyer_variety",
        "role": "buyer",
        "emoji": "🌍",
        "title": "مستكشف الأسواق",
        "desc": "اشترِ بنجاح من 7 متاجر مختلفة (+هدية 75 دج!)",
        "target": 7,
        "xp": 260,
        "reward_dzd": 75.0,
    },
    "buyer_big_spender": {
        "code": "buyer_big_spender",
        "role": "buyer",
        "emoji": "💰",
        "title": "راعي المتاجر",
        "desc": "تجاوزت قيمة مشترياتك المكتملة 50,000 دج (+هدية 120 دج!)",
        "target": 50000,
        "xp": 320,
        "reward_dzd": 120.0,
    },
    "buyer_vip": {
        "code": "buyer_vip",
        "role": "buyer",
        "emoji": "🏆",
        "title": "المشتري الأسطوري",
        "desc": "أتمم 20 طلباً مكتملاً (+هدية 200 دج رصيد محفظة!)",
        "target": 20,
        "xp": 450,
        "reward_dzd": 200.0,
    },
    "buyer_emperor": {
        "code": "buyer_emperor",
        "role": "buyer",
        "emoji": "👑",
        "title": "إمبراطور السوق",
        "desc": "أتمم 50 طلباً مكتملاً بنجاح (+هدية 500 دج رصيد محفظة!)",
        "target": 50,
        "xp": 800,
        "reward_dzd": 500.0,
    },
}

USER_RANKS: Final[list[tuple[int, str, str]]] = [
    (0, "🌱", "مبتدئ"),
    (150, "⚡", "نشيط"),
    (400, "🥉", "محترف"),
    (800, "🥈", "خبير"),
    (1400, "🥇", "نجم المنصة"),
    (2200, "💎", "بطل ماسي"),
    (3200, "🔥", "زعيم السوق"),
    (4500, "👑", "أسطورة Market Bot"),
]


def get_badge_info(code: str) -> Optional[dict[str, Any]]:
    return BADGE_CATALOG.get((code or "").strip())


def get_user_rank(xp: int) -> tuple[int, str, str, Optional[int]]:
    level = 1
    emoji, name = USER_RANKS[0][1], USER_RANKS[0][2]
    next_xp: Optional[int] = None
    for idx, (req_xp, em, nm) in enumerate(USER_RANKS):
        if xp >= req_xp:
            level = idx + 1
            emoji, name = em, nm
            next_xp = USER_RANKS[idx + 1][0] if idx + 1 < len(USER_RANKS) else None
        else:
            break
    return level, emoji, name, next_xp


def _badge_progress_bar(current: int, target: int, width: int = 8) -> str:
    if target <= 0:
        return "▓" * width
    ratio = max(0.0, min(1.0, float(current) / float(target)))
    filled = int(round(ratio * width))
    return ("▓" * filled) + ("░" * (width - filled))

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
    stream=sys.stdout,
    force=True,
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
        "choose_lang": "🌐✨ <b>اختر لغتك المفضّلة</b>\n━━━━━━━━━━━━━━━\nاختر اللغة التي تناسبك لتصفّح المنصّة بكل راحة:",
        "lang_set": "✅✨ تم تعيين اللغة إلى <b>العربية</b> بنجاح!",
        "welcome": (
            "✨🛍️ <b>أهلاً بك في عالم Market Bot</b> 🛍️✨\n"
            "━━━━━━━━━━━━━━━\n"
            "منصّتك الذكية والمتكاملة للتسوّق والتجارة الإلكترونية داخل تيليجرام — تجمع بين البساطة، الأمان، والسرعة! ⚡\n\n"
            "✦ 🛍️ <b>للمشتري:</b> اكتشف أفضل العروض، أضف للسلة، وتابع طلباتك خطوة بخطوة.\n"
            "✦ 🚀 <b>للبائع:</b> أطلق متجرك الاحترافي مجاناً، اعرض منتجاتك، وضاعف مبيعاتك من مكان واحد.\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 <i>اختر وجهتك من القائمة أدناه وابدأ رحلتك الآن:</i>"
        ),
        "main_menu": "🏠✨ <b>القائمة الرئيسية</b>\n━━━━━━━━━━━━━━━",
        "btn_buyer_section": "🛍️ التسوّق (المشتري)",
        "btn_seller_section": "🏪 متجري (البائع)",
        "btn_profile_section": "👤 حسابي",
        "btn_admin": "🛡️ لوحة الإدارة",
        "buyer_menu_title": (
            "🛍️✨ <b>قسم المشتري — عالم التسوّق</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "اكتشف أجود المنتجات، قارن الأسعار، وتسوّق بثقة من أفضل المتاجر الموثّقة 👇"
        ),
        "seller_menu_title": (
            "🏪✨ <b>قسم البائع — مركز أعمالك</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "أدر متجرك، منتجاتك، وطلبات زبائنك بكل احترافية وسهولة 👇"
        ),
        "choose_store": "\n━━━━━━━━━━━━━━━\n🏬 <b>لديك عدة متاجر — اختر المتجر الذي ترغب بإدارته:</b>",
        "add_new_store": "➕✨ فتح متجر جديد",
        "max_stores_reached": "⚠️ وصلت للحد الأقصى المسموح به (3 متاجر)",
        "btn_browse": "🛍️ تصفّح المنتجات",
        "btn_browse_cats": "🗂️ التصنيفات",
        "btn_search": "🔍 بحث عن منتج",
        "btn_search_store": "🏪 بحث عن متجر",
        "btn_cart": "🛒 سلة المشتريات",
        "btn_my_orders": "📦 طلباتي",
        "btn_mystore": "🏪 متجري",
        "btn_become_seller": "🚀 افتح متجرك الآن",
        "btn_account": "👤 حسابي",
        "btn_profile": "🪪 ملفي الشخصي",
        "btn_favorites": "❤️ المفضلة",
        "btn_top_stores": "🏆 دليل المتاجر",
        "btn_support": "🎧 الدعم الفني",
        "btn_lang": "🌐 اللغة",
        "account_menu": (
            "⚙️✨ <b>حسابي والإعدادات</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "تحكّم في ملفك الشخصي، محفظتك، مفضلتك، وتذاكر الدعم من مكان واحد 👇"
        ),
        "sponsored_ad": "📣✨ <b>إعلان مموّل</b>",
        "btn_ads_section": "📣 الإعلانات والترويج",
        "ads_menu_title": (
            "📣✨ <b>مركز الإعلانات والعروض المميزة</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "تصفّح أبرز المنتجات المميزة، أو ضاعف وصول منتجك وبوتك لآلاف المستخدمين 🚀"
        ),
        "btn_browse_featured": "🌟 المنتجات المميزة",
        "btn_browse_bot_ads": "🤖 دليل البوتات",
        "btn_create_bot_ad": "➕ أعلن عن بوتك",
        "btn_buy_product_ad": "🚀 تمييز منتج",
        "featured_products_title": (
            "🌟✨ <b>المنتجات المميزة</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "نخبة من العروض المروّجة خصيصاً لتظهر لك أولاً:"
        ),
        "bot_ads_title": (
            "🤖✨ <b>دليل إعلانات البوتات</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "اكتشف أفضل البوتات والخدمات المفيدة على تيليجرام:"
        ),
        "no_bot_ads": "📭 لا توجد إعلانات بوتات منشورة حالياً.",
        "bot_ad_name": "🤖✨ أدخل <b>اسم البوت</b> الذي تريد الإعلان عنه:",
        "bot_ad_username": "🔗 أدخل <b>معرّف البوت</b> (بدون @) — مثال: <code>MyAwesomeBot</code>",
        "bot_ad_desc": "📝 اكتب <b>وصفاً جذاباً</b> للبوت يوضّح مميزاته للمستخدمين:",
        "bot_ad_photo": "🖼️ أرسل <b>صورة أو شعار (Logo)</b> للبوت (إلزامي):",
        "bot_ad_review": (
            "📋✨ <b>مراجعة إعلان البوت</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 🤖 <b>الاسم:</b> {name}\n"
            "✦ 🔗 <b>المعرّف:</b> @{username}\n"
            "✦ 📝 <b>الوصف:</b> {desc}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ سيُرسل طلبك للإدارة للمراجعة والموافقة."
        ),
        "bot_ad_submitted": "✅🎉 تم إرسال إعلان البوت للمراجعة بنجاح! سيظهر للمستخدمين فور موافقة الإدارة.",
        "ad_packages_title": (
            "💎✨ <b>باقات تمييز وترويج المنتجات</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "اختر الباقة المناسبة لإبراز منتجك في الصدارة ومضاعفة المشاهدات والطلبات 🚀"
        ),
        "ad_pkg_basic": "🥉 الباقة الأساسية (3 أيام) — 1000 دج",
        "ad_pkg_pro": "🥈 الباقة الاحترافية (7 أيام) — 2000 دج",
        "ad_pkg_vip": "🥇 باقة VIP (30 يوماً) — 7000 دج",
        "ad_payment_instructions": (
            "💳✨ <b>تعليمات الدفع والتحويل</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ قم بتحويل المبلغ إلى الحساب البريدي: <code>0000000000</code>\n"
            "2️⃣ أرسل <b>صورة إثبات الدفع (لقطة شاشة)</b> في هذه المحادثة.\n"
            "3️⃣ فور التحقق، سيتم تفعيل طلبك مباشرة ⚡"
        ),
        "btn_send_payment_proof": "📸 إرسال إثبات الدفع",
        "payment_proof_received": "✅✨ تم استلام إثبات الدفع بنجاح! سيتم مراجعته وتفعيله في أقرب وقت.",
        "btn_manage_bot_ads": "🤖 إعلانات البوتات",
        "btn_manage_ad_requests": "💰 طلبات الدفع",
        "bot_ads_pending": "⏳🤖 <b>إعلانات البوتات قيد المراجعة:</b>",
        "ad_requests_pending": "⏳💰 <b>طلبات الدفع قيد المراجعة:</b>",
        "btn_approve_bot_ad": "✅ موافقة",
        "btn_reject_bot_ad": "❌ رفض",
        "btn_confirm_payment": "💰 تأكيد الدفع",
        "admin_bot_ad_view": (
            "🤖✨ <b>مراجعة إعلان بوت</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 🏷️ <b>الاسم:</b> {name}\n"
            "✦ 🔗 <b>المعرّف:</b> @{username}\n"
            "✦ 📝 <b>الوصف:</b> {desc}\n"
        ),
        "admin_ad_req_view": (
            "💰✨ <b>طلب دفع جديد</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 👤 <b>المستخدم:</b> <code>{user_id}</code>\n"
            "✦ 📦 <b>الباقة:</b> {package}\n"
            "✦ 💵 <b>المبلغ:</b> {price}\n"
            "✦ 🏷️ <b>النوع:</b> {type}\n"
            "━━━━━━━━━━━━━━━\n"
            "🔍 يرجى التحقق من وصل الدفع ثم تأكيده."
        ),
        "btn_back": "↩️ رجوع",
        "btn_cancel": "✖️ إلغاء",
        "btn_confirm": "✅ تأكيد",
        "btn_approve": "✅ موافقة",
        "btn_reject": "❌ رفض",
        "no_products": "📭 لا توجد منتجات متاحة حالياً.",
        "all_products": "🛍️✨ <b>جميع المنتجات</b>\n━━━━━━━━━━━━━━━\nتصفّح أحدث المنتجات المضافة في المنصّة:",
        "cats_browse_title": "🗂️✨ <b>التصنيفات</b>\n━━━━━━━━━━━━━━━\nاختر التصنيف الذي يهمّك لاستعراض منتجاته:",
        "product": (
            "✨📦 <b>{title}</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "{desc}\n\n"
            "✦ 💰 <b>السعر:</b> {price} {currency}\n"
            "✦ 🚚 <b>التوصيل:</b> {delivery}\n"
            "✦ 🏪 <b>المتجر:</b> {store}\n"
            "✦ ⭐ <b>التقييم:</b> {rating}{stock}{review}{vars}{flash}"
        ),
        "out_of_stock_warn": "\n\n🚫 <b>نفدت الكمية حالياً</b>",
        "stock_left": "\n✦ 📦 <b>المتبقي:</b> {qty}",
        "vars_list": "\n✦ 🎨 <b>الخيارات:</b> {vars}",
        "flash_sale_warn": "\n\n🔥⚡ <b>عرض خاطف حصري!</b> السعر السابق: <s>{old_price}</s> — ينتهي خلال {time}",
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
        "store_welcome": (
            "🏪✨ <b>لوحة متجرك — {name} {badge}</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 📦 <b>المنتجات:</b> {products}\n"
            "✦ 👁️ <b>المشاهدات:</b> {views}\n"
            "✦ 👥 <b>المتابعون:</b> {followers}\n"
            "✦ ⭐ <b>التقييم:</b> {rating}"
        ),
        "verified_badge": "✅",
        "btn_seller_guide": "📖 دليل البائع",
        "seller_guide_text": (
            "📖✨ <b>دليل البائع الذكي</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ <b>إضافة منتج:</b> اضغط «➕ إضافة منتج» واملأ تفاصيل وصور منتجك.\n"
            "2️⃣ <b>مشاركة المتجر:</b> استخدم «🔗 مشاركة المتجر» لنشر رابطك ورمز QR في قنواتك.\n"
            "3️⃣ <b>متابعة الطلبات:</b> ستصلك إشعارات فورية فور وصول أي طلب جديد 🔔\n"
            "4️⃣ <b>العروض الخاطفة:</b> أطلق تخفيضات مؤقتة لمضاعفة مبيعاتك 🔥\n"
            "━━━━━━━━━━━━━━━\n"
            "💡 <i>نصيحة ذهبية: أضف شعاراً (Logo) احترافياً ووصفاً واضحاً لتكسب ثقة المشترين!</i>"
        ),
        "btn_add_product": "➕ إضافة منتج",
        "btn_my_products": "📦 منتجاتي",
        "btn_my_stats": "📊 إحصائياتي",
        "btn_seller_orders": "🛒 طلبات متجري",
        "btn_promos": "🎟️ أكواد الخصم",
        "btn_seller_broadcast": "📣 مراسلة المتابعين",
        "btn_share": "🔗 مشاركة المتجر",
        "btn_settings": "⚙️ إعدادات المتجر",
        "btn_flash_sale": "🔥 عرض خاطف",
        "store_create_prompt": "🏪✨ أدخل <b>اسم متجرك الجديد</b> الذي سيظهر للمشترين:",
        "store_created": "🎉✅ <b>مبارك لك!</b> تم إنشاء متجرك بنجاح، يمكنك الآن إضافة منتجاتك والبدء بالبيع 🚀",
        "share_menu": (
            "🔗✨ <b>مشاركة وتسويق متجرك</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "اختر الأسلوب الأنسب لجذب زبائن جدد:\n\n"
            "✦ 1️⃣ <b>منشور جاهز:</b> بطاقة تسويقية أنيقة بالشعار وزر دخول مباشر.\n"
            "✦ 2️⃣ <b>رمز QR:</b> صورة QR Code جاهزة للطباعة والمشاركة.\n"
            "✦ 3️⃣ <b>تخصيص الرابط:</b> رابط مميز يحمل اسم متجرك.\n"
            "✦ 4️⃣ <b>تخصيص نص المنشور:</b> اكتب رسالتك الترويجية الخاصة."
        ),
        "btn_share_post": "📝 منشور جاهز",
        "btn_share_qr": "📸 رمز QR للمتجر",
        "btn_custom_slug": "🔗 تخصيص الرابط",
        "btn_custom_text": "✏️ تخصيص النص",
        "qr_caption": "📸✨ <b>رمز QR لمتجر {name}</b>\n━━━━━━━━━━━━━━━\nامسح الكود بكاميرا هاتفك للدخول مباشرة وتصفّح المنتجات 🛍️",
        "inline_share_text": (
            "🛍️✨ <b>مرحباً بك في متجر {name}!</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "{store_bio}\n\n"
            "✦ ⭐ <b>التقييم:</b> {rating}\n"
            "✦ 👥 <b>المتابعون:</b> {followers}\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 اضغط على الزر أدناه لتصفّح منتجاتنا مباشرة:"
        ),
        "inline_share_btn": "🛍️ دخول المتجر الآن",
        "enter_custom_slug": "🔗✨ أدخل <b>اسماً مخصصاً للرابط</b> (حروف إنجليزية وأرقام و _ فقط، ولا يكون أرقاماً فقط).\nمثال: <code>my_store_2026</code>",
        "slug_taken": "❌ هذا الاسم محجوز مسبقاً، جرّب اسماً فريداً آخر.",
        "slug_success": "✅🎉 تم تخصيص رابط متجرك بنجاح!\n🔗 https://t.me/{bot_username}?start=store_{slug}",
        "enter_custom_share_text": "✏️ أرسل الرسالة الترويجية التي تريد أن ترافق رابط متجرك:",
        "share_text_success": "✅✨ تم حفظ نص المشاركة بنجاح!",
        "top_stores_title": "🏆✨ <b>دليل أفضل المتاجر</b>\n━━━━━━━━━━━━━━━\nتصفّح المتاجر الأكثر تميّزاً وثقة في المنصّة:",
        "top_stores_empty": "📭 لا توجد متاجر نشطة حالياً.",
        "store_welcome_deeplink": (
            "👋✨ أهلاً بك في متجر <b>{name} {badge}</b>!\n"
            "━━━━━━━━━━━━━━━\n"
            "{store_bio}\n\n"
            "⭐ <b>التقييم:</b> {rating}\n"
            "━━━━━━━━━━━━━━━\n"
            "🛍️ تصفّح منتجاتنا أدناه:"
        ),
        "settings_menu": "⚙️✨ <b>إعدادات المتجر</b>\n━━━━━━━━━━━━━━━\nاختر القسم الذي ترغب بتعديله:",
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
        "profile_menu": (
            "🪪✨ <b>ملفك الشخصي</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 👤 <b>الاسم:</b> {name}\n"
            "✦ 📞 <b>الهاتف:</b> {phone}\n"
            "✦ 📍 <b>العنوان:</b> {address}\n"
            "━━━━━━━━━━━━━━━\n"
            "💡 <i>حدّث بياناتك هنا لإتمام طلباتك القادمة بضغطة زر واحدة!</i>"
        ),
        "btn_edit_profile_name": "✏️ تعديل الاسم",
        "btn_edit_profile_phone": "📞 تعديل الهاتف",
        "btn_edit_profile_address": "📍 تعديل العنوان",
        "enter_p_name": "👤 أدخل اسمك الكامل:",
        "enter_p_phone": "📞 أدخل رقم هاتفك:",
        "enter_p_address": "📍 أدخل عنوانك بالتفصيل:",
        "profile_updated": "✅✨ تم حفظ بياناتك بنجاح!",
        "buyer_orders_list": "📦✨ <b>سجل طلباتك</b>\n━━━━━━━━━━━━━━━\nاضغط على أي طلب لعرض كامل تفاصيله:",
        "buyer_orders_empty": "📭 ليس لديك أي طلبات سابقة حتى الآن.",
        "buyer_order_details": (
            "🧾✨ <b>طلبك رقم #{id}</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 📦 <b>المنتج:</b> {product}\n"
            "✦ 🎨 <b>الخيار:</b> {variation}\n"
            "✦ 💰 <b>السعر:</b> {price}\n"
            "✦ 🚚 <b>التوصيل:</b> {delivery}\n"
            "✦ 📌 <b>الحالة:</b> {status}\n"
            "✦ 📅 <b>التاريخ:</b> {date}"
        ),
        "order_status_notify": (
            "🔔✨ <b>تحديث جديد على طلبك #{id}</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "مرحباً <b>{name}</b>، تم تحديث حالة طلبك الآن إلى:\n"
            "📌 <b>{status}</b>"
        ),
        "btn_use_saved": "✅ استخدام بياناتي المحفوظة",
        "btn_change_status": "🔄 تحديث الحالة",
        "status_pending": "⏳ قيد المراجعة",
        "status_shipped": "🚚 قيد الشحن",
        "status_completed": "✅ مكتمل",
        "status_cancelled": "❌ ملغي",
        "status_updated": "✅✨ تم تحديث حالة الطلب بنجاح.",
        "orders_list": "🛒✨ <b>طلبات متجرك</b>\n━━━━━━━━━━━━━━━\nاضغط على أي طلب لعرض تفاصيله وإدارته:",
        "order_details": (
            "🧾✨ <b>تفاصيل الطلب #{id}</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 📦 <b>المنتج:</b> {product}\n"
            "✦ 🎨 <b>الخيار:</b> {variation}\n"
            "✦ 👤 <b>المشتري:</b> {name}\n"
            "✦ 📞 <b>الهاتف:</b> {phone}\n"
            "✦ 📍 <b>العنوان:</b> {address}\n"
            "✦ 📝 <b>ملاحظة:</b> {note}\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 💰 <b>السعر:</b> {price}\n"
            "✦ 🚚 <b>التوصيل:</b> {delivery}\n"
            "✦ 📌 <b>الحالة:</b> {status}"
        ),
        "orders_empty": "📭 لا توجد طلبات حتى الآن.",
        "btn_export_orders": "📥 تصدير الطلبات (Excel)",
        "export_success": "✅📊 تم تصدير طلباتك بنجاح!",
        "order_name": "🛒✨ خطوة سريعة لإتمام الطلب — أدخل <b>اسمك الكامل</b>:",
        "order_phone": "📞 أدخل <b>رقم هاتفك</b> للتواصل عند التوصيل:",
        "order_address": "📍 أدخل <b>عنوانك بالتفصيل</b>:",
        "order_note": "📝 هل لديك ملاحظة للبائع؟ (أرسلها الآن أو اضغط تخطي):",
        "btn_skip_note": "⏭️ تخطي الملاحظات",
        "order_promo": "🎟️ هل تملك <b>كود خصم</b>؟ أرسله الآن أو اضغط تخطي:",
        "btn_skip_promo": "⏭️ تخطي (بدون كود)",
        "invalid_promo": "❌ كود الخصم غير صالح أو غير مطبّق على هذه المنتجات. جرّب كوداً آخر أو اضغط تخطي:",
        "promo_applied": "🎉✅ تم تطبيق الخصم بنجاح! السعر الجديد: <b>{price}</b>",
        "order_success": "🎉✅ <b>تم إرسال طلبك بنجاح!</b>\n━━━━━━━━━━━━━━━\nسيتواصل معك البائع قريباً لتأكيد التوصيل 🚚✨",
        "new_order_notify": (
            "🔔🎉 <b>مبارك! وصلك طلب جديد</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 📦 <b>المنتج:</b> {product}\n"
            "✦ 🎨 <b>الخيار:</b> {variation}\n"
            "✦ 👤 <b>الاسم:</b> {name}\n"
            "✦ 📞 <b>الهاتف:</b> {phone}\n"
            "✦ 📍 <b>العنوان:</b> {address}\n"
            "✦ 📝 <b>ملاحظة:</b> {note}\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 💰 <b>السعر:</b> {price}\n"
            "✦ 🚚 <b>التوصيل:</b> {delivery}"
        ),
        "public_store": (
            "🏪✨ <b>متجر {name} {badge}</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "📝 {bio}\n\n"
            "✦ ⭐ <b>التقييم:</b> {rating}\n"
            "✦ 👥 <b>المتابعون:</b> {followers}\n"
            "━━━━━━━━━━━━━━━\n"
            "🛍️ اختر منتجاً للتفاصيل:"
        ),
        "btn_follow": "🔔 متابعة المتجر",
        "btn_unfollow": "🔕 إلغاء المتابعة",
        "followed": "✅🔔 تمت متابعة المتجر! ستصلك إشعارات بكل جديد.",
        "unfollowed": "🔕 تم إلغاء متابعة المتجر.",
        "new_prod_follower_notify": (
            "✨🔔 <b>منتج جديد وصل الآن!</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "متجر <b>{store}</b> أضاف منتجاً جديداً:\n"
            "✦ 📦 {product}\n"
            "✦ 💰 <b>{price}</b>"
        ),
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
        "add_review": (
            "📋✨ <b>مراجعة تفاصيل المنتج</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 📦 <b>الاسم:</b> {title}\n"
            "✦ 🗂️ <b>التصنيف:</b> {category}\n"
            "✦ 💰 <b>السعر:</b> {price}\n"
            "✦ 🚚 <b>التوصيل:</b> {delivery}\n"
            "✦ 📊 <b>الكمية:</b> {stock}\n"
            "✦ 🎨 <b>الخيارات:</b> {vars}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ سيُرسل المنتج للمراجعة والنشر."
        ),
        "product_submitted": "✅✨ تم إرسال منتجك للمراجعة بنجاح! سيظهر للمشترين فور الموافقة.",
        "product_approved_notify": "🎉✅ تمت الموافقة على منتجك <b>{title}</b> وأصبح معروضاً الآن في المتجر!",
        "product_rejected_notify": "❌ لم تتم الموافقة على منتجك: <b>{title}</b>\n📝 <b>السبب:</b> {reason}",
        "flash_sale_menu": "🔥⚡ <b>العروض الخاطفة</b>\n━━━━━━━━━━━━━━━\nاختر منتجاً لإطلاق تخفيض مؤقت وجذب المشترين بسرعة:",
        "flash_sale_select_prod": "📦 اختر المنتج:",
        "flash_sale_enter_price": "💰 أدخل <b>سعر العرض الخاطف</b> (أكبر من 0 وأقل من السعر الأصلي):",
        "flash_sale_enter_hours": "⏱️ أدخل <b>مدة العرض بالساعات</b> (من 1 إلى 720 ساعة):",
        "flash_sale_created": "🔥🎉 تم تفعيل العرض الخاطف بنجاح!",
        "flash_sale_active": "🔥 عرض خاطف",
        "stats": (
            "📊✨ <b>إحصائيات وأداء متجرك</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 👁️ <b>المشاهدات:</b> {views}\n"
            "✦ 📦 <b>المنتجات:</b> {products}\n"
            "✦ 🛒 <b>إجمالي الطلبات:</b> {orders}\n"
            "✦ 💵 <b>إجمالي المبيعات:</b> {revenue}\n"
            "✦ ⭐ <b>التقييم:</b> {rating}\n"
            "━━━━━━━━━━━━━━━\n"
            "🏆 <b>الأكثر مبيعاً:</b>\n{top}"
        ),
        "top_prod_line": "✦ {name} — <b>{count}</b> طلبات\n",
        "ads_info": "📣✨ <b>الإعلانات المميزة</b>",
        "admin_panel": "🛡️✨ <b>لوحة تحكّم الإدارة</b>\n━━━━━━━━━━━━━━━\nاختر القسم المطلوب إدارته:",
        "btn_pending": "⏳ منتجات قيد المراجعة",
        "btn_broadcast": "📣 رسالة جماعية (إذاعة)",
        "btn_manage_cats": "🗂️ إدارة التصنيفات",
        "btn_global_stats": "📊 إحصائيات المنصّة",
        "btn_reports": "🚨 البلاغات",
        "btn_tickets": "🎫 تذاكر الدعم",
        "btn_manage_stores": "🏪 إدارة المتاجر",
        "btn_verify": "✅ توثيق المتجر",
        "btn_unverify": "❌ إلغاء التوثيق",
        "admin_stores_list": "🏪✨ <b>قائمة المتاجر</b>\n━━━━━━━━━━━━━━━\nاضغط على المتجر لإدارته:",
        "admin_store_view": (
            "🏪✨ <b>إدارة متجر: {name}</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 👤 <b>المالك:</b> <code>{owner_id}</code>\n"
            "✦ 📦 <b>المنتجات:</b> {products}\n"
            "✦ ✅ <b>الحالة:</b> {status}"
        ),
        "pending_empty": "✅✨ لا توجد منتجات معلّقة حالياً.",
        "reject_reason": "📝 أدخل سبب الرفض:",
        "approved": "✅ تمت الموافقة بنجاح.",
        "rejected": "❌ تم الرفض.",
        "search_prompt": "🔍✨ اكتب كلمة البحث للعثور على منتجك المفضّل:",
        "search_empty": "📭 لم نعثر على نتائج مطابقة لبحثك.",
        "my_products_empty": "📭 لم تضف أي منتجات بعد — ابدأ الآن بإضافة أول منتج!",
        "cancelled": "✖️ تم إلغاء العملية.",
        "not_admin": "⛔ غير مصرح لك بهذا الإجراء.",
        "search_results": "🔍✨ <b>نتائج البحث:</b>",
        "share_text": "🛍️ تصفّح أحدث منتجاتي عبر متجري:",
        "page_info": "📄 صفحة {current} من {total}",
        "btn_next": "التالي ⬅️",
        "btn_prev": "➡️ السابق",
        "broadcast_prompt": "📣 أرسل الرسالة التي تريد إذاعتها لجميع المستخدمين:",
        "broadcast_started": "⏳ جاري الإرسال...",
        "broadcast_done": "✅🎉 تمت الإذاعة بنجاح إلى <b>{count}</b> مستخدم.",
        "seller_broadcast_prompt": "📣 أرسل الرسالة التي تريد إيصالها لمتابعي متجرك:",
        "seller_broadcast_done": "✅🎉 تم إرسال رسالتك إلى <b>{count}</b> متابع.",
        "cats_manage": "🗂️✨ <b>إدارة التصنيفات</b>\n━━━━━━━━━━━━━━━",
        "btn_add_cat": "➕ إضافة تصنيف",
        "cat_add_prompt": "🗂️ أدخل اسم التصنيف بالترتيب (عربي, إنجليزي, فرنسي) مفصولة بفاصلة:\nمثال: <code>سيارات,Cars,Voitures</code>",
        "cat_added": "✅✨ تم إضافة التصنيف بنجاح.",
        "cat_deleted": "🗑️ تم حذف التصنيف (المنتجات أصبحت بدون تصنيف).",
        "cat_del_confirm": "⚠️ هل أنت متأكد من حذف هذا التصنيف؟",
        "global_stats": (
            "📊✨ <b>إحصائيات المنصّة الشاملة</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "✦ 👥 <b>المستخدمون:</b> {users}\n"
            "✦ 🏪 <b>المتاجر:</b> {stores}\n"
            "✦ 📦 <b>المنتجات:</b> {products}\n"
            "✦ 🛒 <b>الطلبات:</b> {orders}"
        ),
        "reports_list": "🚨✨ <b>البلاغات المعلّقة:</b>",
        "reports_empty": "✅✨ لا توجد بلاغات معلّقة حالياً.",
        "report_resolved": "✅ تم حل البلاغ وإغلاقه.",
        "support_msg": (
            "🎧✨ <b>مركز الدعم الفني</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "نحن هنا لمساعدتك دائماً! افتح تذكرة جديدة وسيردّ عليك فريق الإدارة مباشرة داخل البوت 💬"
        ),
        "btn_new_ticket": "📝 فتح تذكرة جديدة",
        "btn_my_tickets": "📋 تذاكري السابقة",
        "ticket_subject": "📝 اكتب <b>عنوان المشكلة</b> باختصار:",
        "ticket_body": "✍️ الآن اشرح <b>تفاصيل استفسارك</b> (نص أو صورة):",
        "ticket_created": "✅🎫 تم فتح التذكرة رقم <b>#{id}</b> بنجاح! سيردّ عليك الدعم في أقرب وقت.",
        "ticket_reply_from_admin": "💬✨ <b>ردّ الدعم الفني على تذكرتك #{id}</b>\n━━━━━━━━━━━━━━━\n{text}",
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
        "btn_admin_blacklist": "🛡️ القائمة السوداء",
        "btn_report_fake_order": "🚨 تبليغ عن طلب وهمي / حظر",
        "order_blocked_blacklist": "🚫 <b>عذراً، لا يمكنك إتمام الطلب.</b>\nحسابك أو رقم هاتفك مدرج في القائمة السوداء بسبب إلغاءات متكررة أو مخالفات.\nإذا كنت تعتقد أن هذا خطأ، تواصل مع الدعم الفني.",
        "order_rate_limited": "⏳ يرجى الانتظار {wait} ثانية قبل إرسال طلب جديد (حماية ضد التكرار والطلبات الوهمية).",
        "flood_warn": "⏳ أبطئ قليلاً! عدد طلباتك سريع جداً، حاول مرة أخرى بعد ثوانٍ.",
        "trust_label": "🛡️ موثوقية المشتري",
        "trust_blacklisted": "🚫 محظور (القائمة السوداء)",
        "trust_new": "🆕 زبون جديد (أول طلب)",
        "trust_high_risk": "🔴 تحذير عالٍ: {done} مستلمة | {cancel} ملغاة ({rate:.0f}% إلغاء)",
        "trust_medium": "🟡 متوسط: {done} مستلمة | {cancel} ملغاة",
        "trust_good": "🟢 زبون موثوق: {done} مستلمة | 0 ملغاة",
        "trust_active": "🔵 قيد المتابعة: {total} طلبات ({pending} انتظار)",
        "fake_report_sent": "✅ تم إرسال بلاغ الطلب الوهمي إلى الإدارة للمراجعة والحظر.",
        "bl_menu_title": "🛡️ <b>إدارة القائمة السوداء والحماية من الطلبات الوهمية</b>\n\nإجمالي المحظورين: <b>{count}</b>\nاضغط على أي عنصر لإزالة الحظر عنه:",
        "bl_empty": "🛡️ <b>القائمة السوداء فارغة حالياً.</b>\nلا توجد حسابات أو أرقام هواتف محظورة.",
        "bl_btn_add": "➕ إضافة للقائمة السوداء",
        "bl_btn_check": "🔎 فحص رقم أو مستخدم",
        "bl_add_prompt": "🛡️ أرسل معرّف تيليجرام (ID) أو رقم الهاتف للحظر، أو كليهما معاً:\nمثال رقم فقط: <code>0555123456</code>\nمثال ID فقط: <code>123456789</code>\nمثال كليهما: <code>123456789 0555123456</code>",
        "bl_reason_prompt": "📝 أدخل سبب الحظر (أو اضغط تخطي):",
        "bl_added": "✅ تمت الإضافة إلى القائمة السوداء بنجاح.",
        "bl_removed": "✅ تمت إزالة الحظر بنجاح.",
        "bl_check_prompt": "🔎 أرسل معرّف تيليجرام (ID) أو رقم الهاتف لفحص سجل المشتري وموثوقيته:",
        "btn_admin_paymethods": "💳 طرق الدفع والبوابات",
        "btn_admin_vouchers": "🎟️ أكواد الشحن",
        "btn_admin_plans": "👑 الباقات وكوبوناتها",
        "btn_wallet_voucher": "🎟️ شحن بكود بطاقة",
        "btn_wallet_history": "📜 سجل المعاملات",
        "btn_wallet_stars": "⭐ شحن بنجوم تيليجرام",
        "btn_pay_chargily": "⚡ دفع فوري EDAHABIA / CIB",
        "btn_store_deposit": "💵 إعدادات العربون (COD)",
        "btn_store_plans": "👑 باقات الاشتراك (Pro / VIP)",
        "btn_delivery_companies": "🚚 شركات التوصيل",
        "btn_request_website": "🌐 طلب إنشاء موقع",
        "btn_admin_websites": "🌐 طلبات المواقع",
        "btn_badges": "🏅 الشارات والمهام",
        "btn_seller_badges": "🏅 شارات البائع",
        "dup_receipt_err": "⚠️ <b>تم استخدام صورة هذا الإيصال مسبقاً!</b>\nيرجى إرسال صورة إيصال دفع جديد وصالح.",
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
        "btn_admin_blacklist": "🛡️ Blacklist",
        "btn_report_fake_order": "🚨 Report fake order / Ban",
        "order_blocked_blacklist": "🚫 <b>Sorry, you cannot place this order.</b>\nYour account or phone number is blacklisted due to repeated cancellations or violations.\nContact support if you believe this is a mistake.",
        "order_rate_limited": "⏳ Please wait {wait} seconds before placing another order (anti-spam protection).",
        "flood_warn": "⏳ Slow down! Too many requests — please try again in a few seconds.",
        "trust_label": "🛡️ Buyer Trust",
        "trust_blacklisted": "🚫 Blacklisted",
        "trust_new": "🆕 New customer (first order)",
        "trust_high_risk": "🔴 High Risk: {done} delivered | {cancel} cancelled ({rate:.0f}% cancel)",
        "trust_medium": "🟡 Moderate: {done} delivered | {cancel} cancelled",
        "trust_good": "🟢 Trusted buyer: {done} delivered | 0 cancelled",
        "trust_active": "🔵 In progress: {total} orders ({pending} pending)",
        "fake_report_sent": "✅ Fake order report sent to admins for review and blacklisting.",
        "bl_menu_title": "🛡️ <b>Blacklist & Anti-Fake Order Protection</b>\n\nTotal blocked entries: <b>{count}</b>\nTap an entry to unban:",
        "bl_empty": "🛡️ <b>The blacklist is currently empty.</b>\nNo blocked users or phone numbers.",
        "bl_btn_add": "➕ Add to Blacklist",
        "bl_btn_check": "🔎 Check Phone / User",
        "bl_add_prompt": "🛡️ Send a Telegram ID, a phone number, or both to block:\nPhone: <code>0555123456</code>\nID: <code>123456789</code>\nBoth: <code>123456789 0555123456</code>",
        "bl_reason_prompt": "📝 Enter the ban reason (or tap skip):",
        "bl_added": "✅ Added to blacklist successfully.",
        "bl_removed": "✅ Entry removed from blacklist.",
        "bl_check_prompt": "🔎 Send a Telegram ID or phone number to inspect buyer history & trust:",
        "btn_admin_paymethods": "💳 Payment Methods",
        "btn_admin_vouchers": "🎟️ Recharge Vouchers",
        "btn_admin_plans": "👑 Plans & Coupons",
        "btn_wallet_voucher": "🎟️ Redeem Voucher",
        "btn_wallet_history": "📜 Transaction History",
        "btn_wallet_stars": "⭐ Top-up with Telegram Stars",
        "btn_pay_chargily": "⚡ Instant Pay (EDAHABIA / CIB)",
        "btn_store_deposit": "💵 Deposit Settings (COD)",
        "btn_store_plans": "👑 Subscription Plans (Pro/VIP)",
        "btn_delivery_companies": "🚚 Delivery Companies",
        "btn_request_website": "🌐 Request a Website",
        "btn_admin_websites": "🌐 Website Requests",
        "btn_badges": "🏅 Badges & Missions",
        "btn_seller_badges": "🏅 Seller Badges",
        "dup_receipt_err": "⚠️ <b>This payment receipt was already submitted!</b>\nPlease send a new valid receipt screenshot.",
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
        "btn_admin_blacklist": "🛡️ Liste noire",
        "btn_report_fake_order": "🚨 Signaler fausse commande",
        "order_blocked_blacklist": "🚫 <b>Désolé, impossible de valider votre commande.</b>\nVotre compte ou numéro de téléphone est sur la liste noire suite à des annulations répétées.\nContactez le support en cas d'erreur.",
        "order_rate_limited": "⏳ Veuillez patienter {wait} secondes avant de passer une nouvelle commande (protection anti-spam).",
        "flood_warn": "⏳ Doucement ! Trop de requêtes, veuillez réessayer dans quelques secondes.",
        "trust_label": "🛡️ Fiabilité acheteur",
        "trust_blacklisted": "🚫 Bloqué (Liste noire)",
        "trust_new": "🆕 Nouveau client (1re commande)",
        "trust_high_risk": "🔴 Risque élevé : {done} livrées | {cancel} annulées ({rate:.0f}%)",
        "trust_medium": "🟡 Moyen : {done} livrées | {cancel} annulées",
        "trust_good": "🟢 Client fiable : {done} livrées | 0 annulée",
        "trust_active": "🔵 En cours : {total} commandes ({pending} en attente)",
        "fake_report_sent": "✅ Signalement de fausse commande envoyé à l'administration.",
        "bl_menu_title": "🛡️ <b>Liste Noire & Protection Anti-Fausses Commandes</b>\n\nTotal bloqués : <b>{count}</b>\nAppuyez sur une entrée pour débloquer :",
        "bl_empty": "🛡️ <b>La liste noire est vide.</b>\nAucun compte ni numéro bloqué.",
        "bl_btn_add": "➕ Ajouter à la liste noire",
        "bl_btn_check": "🔎 Vérifier numéro / ID",
        "bl_add_prompt": "🛡️ Envoyez un ID Telegram, un numéro de téléphone ou les deux :\nTéléphone : <code>0555123456</code>\nID : <code>123456789</code>\nLes deux : <code>123456789 0555123456</code>",
        "bl_reason_prompt": "📝 Entrez le motif du blocage (ou passez) :",
        "bl_added": "✅ Ajouté à la liste noire avec succès.",
        "bl_removed": "✅ Retiré de la liste noire.",
        "bl_check_prompt": "🔎 Envoyez un ID Telegram ou un numéro de téléphone pour vérifier la fiabilité de l'acheteur :",
        "btn_admin_paymethods": "💳 Moyens de paiement",
        "btn_admin_vouchers": "🎟️ Codes de recharge",
        "btn_admin_plans": "👑 Abonnements & Coupons",
        "btn_wallet_voucher": "🎟️ Utiliser un code recharge",
        "btn_wallet_history": "📜 Historique des transactions",
        "btn_wallet_stars": "⭐ Recharger par Telegram Stars",
        "btn_pay_chargily": "⚡ Paiement EDAHABIA / CIB",
        "btn_store_deposit": "💵 Paramètres d'acompte (COD)",
        "btn_store_plans": "👑 Forfaits (Pro / VIP)",
        "btn_delivery_companies": "🚚 Sociétés de livraison",
        "btn_request_website": "🌐 Demander un site web",
        "btn_admin_websites": "🌐 Demandes de sites web",
        "btn_badges": "🏅 Badges & Missions",
        "btn_seller_badges": "🏅 Badges Vendeur",
        "dup_receipt_err": "⚠️ <b>Ce reçu de paiement a déjà été utilisé !</b>\nVeuillez envoyer une nouvelle capture de paiement valide.",
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
    equipped_badge: Mapped[str] = mapped_column(String(50), default="")
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
    plan_tier: Mapped[str] = mapped_column(String(20), default="free")
    plan_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False)
    expiry_reminded_3d: Mapped[bool] = mapped_column(Boolean, default=False)
    expiry_reminded_1d: Mapped[bool] = mapped_column(Boolean, default=False)
    deposit_threshold: Mapped[float] = mapped_column(Float, default=0.0)
    deposit_amount: Mapped[float] = mapped_column(Float, default=0.0)
    delivery_company: Mapped[str] = mapped_column(String(40), default="")
    featured_badge: Mapped[str] = mapped_column(String(50), default="")
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
    deposit_proof: Mapped[str] = mapped_column(String(200), default="")
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
    proof_unique_id: Mapped[str] = mapped_column(String(200), default="", index=True)
    ref_code: Mapped[str] = mapped_column(String(40), default="", index=True)
    external_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BlacklistedEntry(Base):
    __tablename__ = "blacklisted_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_tg_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    phone_norm: Mapped[str] = mapped_column(String(40), index=True, default="")
    reason: Mapped[str] = mapped_column(String(300), default="")
    added_by: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    details: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Voucher(Base):
    __tablename__ = "vouchers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    amount: Mapped[float] = mapped_column(Float)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class VoucherRedemption(Base):
    __tablename__ = "voucher_redemptions"
    __table_args__ = (
        UniqueConstraint("voucher_id", "user_tg_id", name="uq_voucher_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    voucher_id: Mapped[int] = mapped_column(ForeignKey("vouchers.id", ondelete="CASCADE"), index=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tx_type: Mapped[str] = mapped_column(String(30), index=True)
    amount: Mapped[float] = mapped_column(Float)
    balance_after: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str] = mapped_column(String(300), default="")
    ref_code: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SubCoupon(Base):
    __tablename__ = "sub_coupons"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    discount_percent: Mapped[int] = mapped_column(Integer)
    max_uses: Mapped[int] = mapped_column(Integer, default=100)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WebsiteRequest(Base):
    __tablename__ = "website_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(Integer, index=True)
    seller_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    store_name: Mapped[str] = mapped_column(String(120), default="")
    package_code: Mapped[str] = mapped_column(String(30), default="ecommerce")
    features: Mapped[str] = mapped_column(Text, default="")
    budget: Mapped[str] = mapped_column(String(80), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    contact_phone: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    quoted_price: Mapped[float] = mapped_column(Float, default=0.0)
    delivery_days: Mapped[int] = mapped_column(Integer, default=0)
    live_url: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    messages = relationship("WebsiteMessage", back_populates="request", cascade="all, delete-orphan")


class WebsiteMessage(Base):
    __tablename__ = "website_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("website_requests.id", ondelete="CASCADE"), index=True)
    sender_role: Mapped[str] = mapped_column(String(20), default="seller")  # "seller" | "developer"
    sender_tg_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text, default="")
    photo_file_id: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    request = relationship("WebsiteRequest", back_populates="messages")


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (
        UniqueConstraint("user_tg_id", "badge_code", name="uq_user_badge"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    badge_code: Mapped[str] = mapped_column(String(50), index=True)
    role: Mapped[str] = mapped_column(String(15), default="buyer")  # "seller" | "buyer"
    store_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


async def _ensure_schema_columns(conn) -> None:
    """Safely add new columns to existing tables BEFORE/AFTER create_all so upgrades never fail on new indexes."""
    migrations = [
        ("users", "saved_wilaya", "VARCHAR(60) DEFAULT ''"),
        ("users", "equipped_badge", "VARCHAR(50) DEFAULT ''"),
        ("stores", "default_desk_fee", "FLOAT DEFAULT 0.0"),
        ("stores", "vip_until", "DATETIME"),
        ("stores", "auto_approve", "BOOLEAN DEFAULT 0"),
        ("stores", "plan_tier", "VARCHAR(20) DEFAULT 'free'"),
        ("stores", "plan_expires_at", "DATETIME"),
        ("stores", "auto_renew", "BOOLEAN DEFAULT 0"),
        ("stores", "trial_used", "BOOLEAN DEFAULT 0"),
        ("stores", "expiry_reminded_3d", "BOOLEAN DEFAULT 0"),
        ("stores", "expiry_reminded_1d", "BOOLEAN DEFAULT 0"),
        ("stores", "deposit_threshold", "FLOAT DEFAULT 0.0"),
        ("stores", "deposit_amount", "FLOAT DEFAULT 0.0"),
        ("stores", "delivery_company", "VARCHAR(40) DEFAULT ''"),
        ("stores", "featured_badge", "VARCHAR(50) DEFAULT ''"),
        ("products", "is_deleted", "BOOLEAN DEFAULT 0"),
        ("cart_items", "quantity", "INTEGER DEFAULT 1"),
        ("orders", "store_id", "INTEGER"),
        ("orders", "product_title", "VARCHAR(200) DEFAULT ''"),
        ("orders", "product_currency", f"VARCHAR(10) DEFAULT '{DEFAULT_CURRENCY}'"),
        ("orders", "quantity", "INTEGER DEFAULT 1"),
        ("orders", "buyer_wilaya", "VARCHAR(60) DEFAULT ''"),
        ("orders", "delivery_type", "VARCHAR(20) DEFAULT 'home'"),
        ("orders", "tracking_info", "VARCHAR(300) DEFAULT ''"),
        ("orders", "deposit_proof", "VARCHAR(200) DEFAULT ''"),
        ("ad_requests", "payment_proof", "VARCHAR(200) DEFAULT ''"),
        ("ad_requests", "proof_unique_id", "VARCHAR(200) DEFAULT ''"),
        ("ad_requests", "ref_code", "VARCHAR(40) DEFAULT ''"),
        ("ad_requests", "external_id", "VARCHAR(120) DEFAULT ''"),
    ]
    for table, col, ddl in migrations:
        res = await conn.execute(sql_text(f"PRAGMA table_info({table})"))
        rows = res.fetchall()
        if not rows:
            # Table does not exist yet; create_all will create it with all columns.
            continue
        cols = {row[1] for row in rows}
        if col not in cols:
            await conn.execute(sql_text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
    # Sync legacy vip_until into plan_tier/plan_expires_at on upgrade
    with suppress(Exception):
        await conn.execute(
            sql_text(
                "UPDATE stores SET plan_tier = 'vip', plan_expires_at = vip_until "
                "WHERE vip_until IS NOT NULL AND (plan_expires_at IS NULL OR plan_tier = 'free')"
            )
        )


async def init_db() -> async_sessionmaker:
    global Session, _engine

    if _engine is not None:
        with suppress(Exception):
            await _engine.dispose()

    _engine = create_async_engine(DB_URL, echo=False)

    @event.listens_for(_engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        for pragma in (
            "PRAGMA journal_mode=WAL",
            "PRAGMA synchronous=NORMAL",
            "PRAGMA busy_timeout=5000",
            "PRAGMA foreign_keys=ON",
        ):
            try:
                cursor.execute(pragma)
            except Exception:
                pass
        cursor.close()

    async with _engine.begin() as conn:
        # 1) Migrate missing columns on existing tables BEFORE create_all builds new indexes!
        await _ensure_schema_columns(conn)
        # 2) Create new tables and indexes cleanly
        await conn.run_sync(Base.metadata.create_all)
        # 3) Safety pass
        await _ensure_schema_columns(conn)

    Session = async_sessionmaker(_engine, expire_on_commit=False)
    return Session


async def seed_categories(session_factory: async_sessionmaker) -> None:
    async with session_factory() as s:
        existing = (await s.execute(select(Category).limit(1))).scalar_one_or_none()
        if not existing:
            s.add_all([
                Category(name_ar="إلكترونيات", name_en="Electronics", name_fr="Électronique"),
                Category(name_ar="أزياء", name_en="Fashion", name_fr="Mode"),
                Category(name_ar="منزل", name_en="Home", name_fr="Maison"),
                Category(name_ar="رياضة", name_en="Sports", name_fr="Sport"),
                Category(name_ar="كتب", name_en="Books", name_fr="Livres"),
            ])
        pm_existing = (await s.execute(select(PaymentMethod).limit(1))).scalar_one_or_none()
        if not pm_existing:
            s.add_all([
                PaymentMethod(
                    name="BaridiMob (RIP)",
                    details="RIP: 00799999000000000000\nأرسل المبلغ ثم أرفق صورة الوصل.",
                    is_active=True,
                    sort_order=1,
                ),
                PaymentMethod(
                    name="CCP (بريد الجزائر)",
                    details="الحساب: 00000000 المفتاح: 00\nالاسم: يحدده الأدمن من لوحة التحكم.",
                    is_active=True,
                    sort_order=2,
                ),
                PaymentMethod(
                    name="USDT (TRC20)",
                    details="العنوان: يحدده الأدمن من لوحة التحكم.",
                    is_active=False,
                    sort_order=3,
                ),
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


class AdminBlacklistFSM(StatesGroup):
    add_target = State()
    add_reason = State()
    check_target = State()


class VoucherRedeemFSM(StatesGroup):
    code = State()


class AdminPayMethodFSM(StatesGroup):
    add_name = State()
    add_details = State()
    edit_details = State()
    chargily_key = State()
    stars_rate = State()


class AdminVoucherFSM(StatesGroup):
    create_spec = State()


class AdminPlanConfigFSM(StatesGroup):
    set_value = State()


class AdminSubCouponFSM(StatesGroup):
    create_spec = State()


class SubCouponApplyFSM(StatesGroup):
    code = State()


class StoreDepositFSM(StatesGroup):
    threshold = State()
    amount = State()


class OrderDepositFSM(StatesGroup):
    proof = State()


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


class DeliveryCalcFSM(StatesGroup):
    dims = State()


class WebsiteReqFSM(StatesGroup):
    details = State()
    phone = State()


class WebsiteChatFSM(StatesGroup):
    message = State()


class AdminWebDevFSM(StatesGroup):
    reply = State()
    quote = State()
    deliver_url = State()
    dev_username = State()


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


def _store_expiry_dt(store: Optional[Store]) -> Optional[datetime]:
    if not store:
        return None
    if store.plan_expires_at:
        return store.plan_expires_at
    return store.vip_until


def effective_store_tier(store: Optional[Store], include_grace: bool = True) -> str:
    """Return active tier ('vip', 'pro', or 'free'), respecting the 48h grace period."""
    if not store:
        return "free"
    now = utcnow()
    grace = timedelta(hours=SUB_GRACE_HOURS) if include_grace else timedelta(0)
    exp = _store_expiry_dt(store)
    tier = (store.plan_tier or "free").lower()
    if exp and (exp + grace) > now:
        if tier in ("vip", "pro"):
            return tier
        if store.vip_until and (store.vip_until + grace) > now:
            return "vip"
    return "free"


def store_in_grace_period(store: Optional[Store]) -> bool:
    if not store:
        return False
    exp = _store_expiry_dt(store)
    now = utcnow()
    return bool(exp and exp <= now < (exp + timedelta(hours=SUB_GRACE_HOURS)) and (store.plan_tier in ("pro", "vip") or store.vip_until))


def is_store_vip(store: Optional[Store]) -> bool:
    return effective_store_tier(store) == "vip"


def is_store_pro_or_vip(store: Optional[Store]) -> bool:
    return effective_store_tier(store) in ("pro", "vip")


def store_can_auto_approve(store: Optional[Store]) -> bool:
    return bool(store and (store.auto_approve or is_store_pro_or_vip(store)))


def store_max_products(store: Optional[Store]) -> Optional[int]:
    """Return max allowed products for store tier, or None for unlimited (VIP)."""
    tier = effective_store_tier(store)
    if tier == "vip":
        return None
    if tier == "pro":
        return MAX_PRODUCTS_PRO
    return MAX_PRODUCTS_FREE


def store_tier_label(store: Optional[Store], lang: str = "ar") -> str:
    tier = effective_store_tier(store)
    if tier == "vip":
        return "👑 VIP"
    if tier == "pro":
        return "⭐ Pro"
    return "🆓 Free"


def store_badges(store: Optional[Store], lang: str) -> str:
    if not store:
        return ""
    parts = []
    tier = effective_store_tier(store)
    if tier == "vip":
        parts.append("👑")
    elif tier == "pro":
        parts.append("⭐")
    if store.verified or tier == "vip":
        parts.append(t(lang, "verified_badge"))
    fb = get_badge_info(getattr(store, "featured_badge", "") or "")
    if fb and fb["emoji"] not in parts:
        parts.append(fb["emoji"])
    return " ".join(parts)


async def user_max_stores(tg_id: int) -> int:
    stores = await get_stores_by_owner(tg_id)
    if any(effective_store_tier(st) == "vip" for st in stores):
        return MAX_STORES_VIP
    if any(effective_store_tier(st) == "pro" for st in stores):
        return MAX_STORES_PRO
    return MAX_STORES_FREE


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


async def get_dynamic_plans(s=None) -> dict[str, dict[str, Any]]:
    """Return subscription plans with admin-configured overrides from AppSetting."""
    plans = {k: dict(v) for k, v in VIP_PLANS.items()}
    keys = [f"plan_price_{k}" for k in plans] + [f"plan_bonus_{k}" for k in plans]
    if s is not None:
        rows = (await s.execute(select(AppSetting).where(AppSetting.key.in_(keys)))).scalars().all()
    else:
        async with Session() as s2:
            rows = (await s2.execute(select(AppSetting).where(AppSetting.key.in_(keys)))).scalars().all()
    kv = {r.key: r.value for r in rows}
    for k, info in plans.items():
        raw_p = kv.get(f"plan_price_{k}")
        if raw_p:
            with suppress(ValueError):
                v = float(raw_p)
                if v > 0:
                    info["price"] = v
        raw_b = kv.get(f"plan_bonus_{k}")
        if raw_b is not None and raw_b != "":
            with suppress(ValueError):
                b = float(raw_b)
                if b >= 0:
                    info["bonus"] = b
    return plans


def generate_pay_ref() -> str:
    return f"PAY-{secrets.token_hex(3).upper()}"


async def is_duplicate_receipt(s, file_unique_id: str) -> bool:
    if not file_unique_id:
        return False
    exists = (
        await s.execute(
            select(AdRequest.id)
            .where(AdRequest.proof_unique_id == file_unique_id, AdRequest.status != "rejected")
            .limit(1)
        )
    ).scalar_one_or_none()
    return exists is not None


async def format_payment_instructions(s, lang: str, ref_code: str = "", amount: float = 0.0) -> str:
    methods = (
        await s.execute(
            select(PaymentMethod)
            .where(PaymentMethod.is_active.is_(True))
            .order_by(PaymentMethod.sort_order.asc(), PaymentMethod.id.asc())
        )
    ).scalars().all()
    lines = [
        "💳✨ <b>طرق الدفع المتاحة</b>",
        "━━━━━━━━━━━━━━━",
    ]
    if methods:
        for idx, pm in enumerate(methods, 1):
            lines.append(f"\n✦ <b>{idx}) {esc(pm.name)}</b>\n{esc(pm.details)}")
    else:
        lines.append(t(lang, "ad_payment_instructions"))
    lines.append("\n━━━━━━━━━━━━━━━")
    if amount > 0:
        lines.append(f"💰 <b>المبلغ المطلوب:</b> <code>{amount:g} {DEFAULT_CURRENCY}</code>")
    if ref_code:
        lines.append(f"🏷️ <b>الرمز المرجعي (أضفه في ملاحظة التحويل):</b> <code>{esc(ref_code)}</code>")
    lines.append("📸 <i>بعد إتمام التحويل، أرسل صورة وصل الدفع هنا مباشرة للمراجعة السريعة ⚡</i>")
    return "\n".join(lines)


async def record_wallet_tx(
    s,
    user: User,
    amount: float,
    tx_type: str,
    description: str,
    ref_code: str = "",
) -> WalletTransaction:
    """Apply delta to user.ad_credits and insert an immutable WalletTransaction ledger entry."""
    user.ad_credits = round(float(user.ad_credits or 0.0) + float(amount), 2)
    tx = WalletTransaction(
        user_tg_id=user.tg_id,
        tx_type=tx_type,
        amount=round(float(amount), 2),
        balance_after=float(user.ad_credits),
        description=description[:300],
        ref_code=ref_code[:50],
    )
    s.add(tx)
    return tx


async def activate_store_plan(
    s,
    store: Store,
    plan_key: str,
    user: Optional[User] = None,
) -> tuple[str, float, str]:
    """Activate or extend a Pro/VIP plan on a store and credit any VIP ad bonus."""
    plans = await get_dynamic_plans(s)
    plan = plans.get(plan_key) or plans["vip_30"]
    tier = str(plan.get("tier", "vip"))
    days = int(plan.get("days", 30))
    bonus = float(plan.get("bonus", 0.0))

    now = utcnow()
    current_exp = _store_expiry_dt(store)
    base_dt = current_exp if (current_exp and current_exp > now and store.plan_tier == tier) else now
    new_exp = base_dt + timedelta(days=days)

    store.plan_tier = tier
    store.plan_expires_at = new_exp
    store.expiry_reminded_3d = False
    store.expiry_reminded_1d = False
    store.auto_approve = True
    if tier == "vip":
        store.vip_until = new_exp
        store.verified = True
    else:
        if store.vip_until and store.vip_until <= now:
            store.vip_until = None

    bonus_awarded = 0.0
    if bonus > 0:
        target_user = user or await ensure_user(s, store.owner_tg_id, DEFAULT_LANG)
        await record_wallet_tx(
            s,
            target_user,
            bonus,
            "bonus",
            f"🎁 رصيد إعلانات هدية مع باقة {plan['label']} ({store.name})",
        )
        bonus_awarded = bonus

    return new_exp.strftime("%Y-%m-%d"), bonus_awarded, tier


# ─── Chargily Pay v2 (EDAHABIA / CIB) & Telegram Stars Helpers ───

async def get_chargily_config() -> tuple[str, str]:
    key = (await get_setting("chargily_api_key", "")).strip()
    mode = (await get_setting("chargily_mode", "test")).strip().lower()
    if mode not in ("test", "live"):
        mode = "test"
    return key, mode


async def get_stars_config() -> tuple[bool, float]:
    enabled = (await get_setting("stars_enabled", "0")).strip() == "1"
    raw_rate = (await get_setting("stars_dzd_rate", "5")).strip()
    try:
        rate = float(raw_rate)
        if rate <= 0:
            rate = 5.0
    except ValueError:
        rate = 5.0
    return enabled, rate


def _chargily_base_url(mode: str) -> str:
    return "https://pay.chargily.net/api/v2" if mode == "live" else "https://pay.chargily.net/test/api/v2"


def _chargily_create_checkout_sync(api_key: str, mode: str, amount_dzd: float, description: str, metadata: dict) -> dict:
    url = f"{_chargily_base_url(mode)}/checkouts"
    payload = {
        "amount": int(round(amount_dzd)),
        "currency": "dzd",
        "success_url": f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else "https://t.me",
        "failure_url": f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else "https://t.me",
        "description": description[:250],
        "metadata": metadata,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MarketBot/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        with suppress(Exception):
            body = e.read().decode("utf-8", errors="ignore")[:300]
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}


def _chargily_get_checkout_sync(api_key: str, mode: str, checkout_id: str) -> dict:
    url = f"{_chargily_base_url(mode)}/checkouts/{checkout_id}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "MarketBot/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        with suppress(Exception):
            body = e.read().decode("utf-8", errors="ignore")[:300]
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}


async def chargily_create_checkout(amount_dzd: float, description: str, metadata: dict) -> dict:
    api_key, mode = await get_chargily_config()
    if not api_key:
        return {"error": "Chargily API key not configured"}
    return await asyncio.to_thread(_chargily_create_checkout_sync, api_key, mode, amount_dzd, description, metadata)


async def chargily_verify_checkout(checkout_id: str) -> dict:
    api_key, mode = await get_chargily_config()
    if not api_key:
        return {"error": "Chargily API key not configured"}
    return await asyncio.to_thread(_chargily_get_checkout_sync, api_key, mode, checkout_id)


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
        [InlineKeyboardButton(text=t(lang, "btn_badges"), callback_data="badges:hub:buyer:0"),
         InlineKeyboardButton(text=t(lang, "btn_browse_bot_ads"), callback_data="nav:bot_ads")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")],
    ])


def _account_menu_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_profile"), callback_data="nav:profile"),
         InlineKeyboardButton(text=t(lang, "btn_wallet"), callback_data="nav:wallet")],
        [InlineKeyboardButton(text=t(lang, "btn_badges"), callback_data="badges:hub:buyer:0"),
         InlineKeyboardButton(text=t(lang, "btn_my_orders"), callback_data="nav:orders")],
        [InlineKeyboardButton(text=t(lang, "btn_favorites"), callback_data="nav:favs"),
         InlineKeyboardButton(text=t(lang, "btn_support"), callback_data="nav:support")],
        [InlineKeyboardButton(text=t(lang, "btn_lang"), callback_data="nav:lang")],
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
    tier = effective_store_tier(store)
    max_allowed = await user_max_stores(store.owner_tg_id)
    max_prods = store_max_products(store)
    prod_quota = f"{pcount}/{max_prods}" if max_prods is not None else f"{pcount}/∞"
    badge = store_badges(store, lang)
    exp = _store_expiry_dt(store)
    tier_line = f"\n✦ 🏷️ <b>الباقة:</b> {store_tier_label(store, lang)} | 📦 <b>الحصة:</b> {prod_quota}"
    if tier in ("pro", "vip") and exp:
        grace_tag = " (⏳ فترة سماح 48 ساعة)" if store_in_grace_period(store) else ""
        ar_tag = " | ♻️ تجديد تلقائي" if store.auto_renew else ""
        tier_line += f"\n✦ 📅 <b>صالح حتى:</b> {exp.strftime('%Y-%m-%d')}{grace_tag}{ar_tag}"
    elif store.auto_approve:
        tier_line += "\n✦ ⚡ <b>النشر المباشر مفعّل</b>"
    dc_obj = get_delivery_company(store.delivery_company or "")
    dc_line = (
        f"\n✦ 🚚 <b>شركة التوصيل:</b> {dc_obj['emoji']} <b>{dc_obj['name']}</b>"
        if dc_obj
        else ""
    )
    fb_obj = get_badge_info(getattr(store, "featured_badge", "") or "")
    fb_line = (
        f"\n✦ 🏅 <b>شارة المتجر:</b> {fb_obj['emoji']} <b>{fb_obj['title']}</b>"
        if fb_obj
        else ""
    )
    text = (
        t(lang, "store_welcome", name=esc(store.name), badge=badge, products=pcount, views=vcount, followers=fcount, rating=rating)
        + "\n━━━━━━━━━━━━━━━"
        + f"\n✦ 💳 <b>رصيد المحفظة:</b> <b>{credits:g} {DEFAULT_CURRENCY}</b>"
        + tier_line
        + dc_line
        + fb_line
    )
    kb = [
        [InlineKeyboardButton(text=t(lang, "btn_add_product"), callback_data=f"st_add:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_my_products"), callback_data=f"st_list:{store.id}:1"),
         InlineKeyboardButton(text=t(lang, "btn_seller_orders"), callback_data=f"st_orders:{store.id}:1")],
        [InlineKeyboardButton(text=t(lang, "btn_delivery_companies"), callback_data=f"st_deliv_co:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_seller_badges"), callback_data=f"badges:hub:seller:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_flash_sale"), callback_data=f"st_flash:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_promos"), callback_data=f"st_promos:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_buy_product_ad"), callback_data=f"st_buy_ad:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_store_plans"), callback_data=f"st_vip:{store.id}")],
        [InlineKeyboardButton(text=f"{t(lang, 'btn_wallet')} ({credits:g} {DEFAULT_CURRENCY})", callback_data=f"st_wallet:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_my_stats"), callback_data=f"st_stats:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_share"), callback_data=f"st_share:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_seller_broadcast"), callback_data=f"st_broadcast:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_settings"), callback_data=f"st_settings:{store.id}"),
         InlineKeyboardButton(text=t(lang, "btn_request_website"), callback_data=f"st_web_hub:{store.id}")],
        [InlineKeyboardButton(text=t(lang, "btn_seller_guide"), callback_data=f"st_guide:{store.id}")],
    ]
    if total_stores < max_allowed:
        kb.append([InlineKeyboardButton(text=t(lang, "add_new_store"), callback_data="nav:become_seller")])
    else:
        kb.append([InlineKeyboardButton(text=f"⚠️ الحد الأقصى للمتاجر ({max_allowed}) — رقّي باقتك", callback_data=f"st_vip:{store.id}")])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")])
    await msg_obj.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


async def _build_admin_panel_kb(lang: str) -> InlineKeyboardMarkup:
    async with Session() as s:
        c = (await s.execute(select(func.count(Product.id)).where(Product.status == "pending", Product.is_deleted.is_(False)))).scalar()
        r = (await s.execute(select(func.count(Report.id)).where(Report.status == "pending"))).scalar()
        tck = (await s.execute(select(func.count(SupportTicket.id)).where(SupportTicket.status == "open"))).scalar()
        bads = (await s.execute(select(func.count(BotAd.id)).where(BotAd.status == "pending"))).scalar()
        adreqs = (await s.execute(select(func.count(AdRequest.id)).where(AdRequest.status == "pending"))).scalar()
        bl_cnt = (await s.execute(select(func.count(BlacklistedEntry.id)))).scalar()
        web_cnt = (
            await s.execute(
                select(func.count(WebsiteRequest.id)).where(
                    WebsiteRequest.status.in_(("pending", "negotiating", "in_progress"))
                )
            )
        ).scalar() or 0
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{t(lang, 'btn_pending')} ({c})", callback_data="admin:pending"),
         InlineKeyboardButton(text=f"{t(lang, 'btn_reports')} ({r})", callback_data="admin:reports")],
        [InlineKeyboardButton(text=f"{t(lang, 'btn_tickets')} ({tck})", callback_data="admin:tickets"),
         InlineKeyboardButton(text=f"{t(lang, 'btn_admin_websites')} ({web_cnt})", callback_data="admin:webreqs")],
        [InlineKeyboardButton(text=t(lang, "btn_manage_stores"), callback_data="admin:stores"),
         InlineKeyboardButton(text=t(lang, "btn_manage_cats"), callback_data="admin:cats")],
        [InlineKeyboardButton(text=t(lang, "btn_global_stats"), callback_data="admin:gstats"),
         InlineKeyboardButton(text=f"{t(lang, 'btn_manage_bot_ads')} ({bads})", callback_data="admin:botads")],
        [InlineKeyboardButton(text=f"{t(lang, 'btn_manage_ad_requests')} ({adreqs})", callback_data="admin:adreqs"),
         InlineKeyboardButton(text=t(lang, "btn_admin_paymethods"), callback_data="admin:paymethods")],
        [InlineKeyboardButton(text=t(lang, "btn_admin_vouchers"), callback_data="admin:vouchers"),
         InlineKeyboardButton(text=t(lang, "btn_admin_plans"), callback_data="admin:plans")],
        [InlineKeyboardButton(text=f"{t(lang, 'btn_admin_blacklist')} ({bl_cnt})", callback_data="admin:blacklist"),
         InlineKeyboardButton(text=t(lang, "btn_admin_channel"), callback_data="admin:channel")],
        [InlineKeyboardButton(text=t(lang, "btn_admin_backup"), callback_data="admin:backup"),
         InlineKeyboardButton(text=t(lang, "btn_broadcast"), callback_data="admin:broadcast")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:home")],
    ])


# ─── Anti-Fake Orders, Buyer Trust Score, Blacklist & Rate Limiting ───

_FLOOD_WINDOW_SEC: Final[float] = 10.0
_FLOOD_MAX_EVENTS: Final[int] = 20
_FLOOD_BUCKETS: dict[int, list[float]] = {}
_FLOOD_LAST_WARN: dict[int, float] = {}

_ORDER_MIN_GAP_SEC: Final[float] = 20.0
_ORDER_WINDOW_SEC: Final[float] = 600.0
_ORDER_MAX_PER_WINDOW: Final[int] = 3
_ORDER_SUBMISSIONS: dict[int, list[float]] = {}


def _normalize_phone(raw: str) -> str:
    """Normalize phone number so +213555123456, 00213 555 123 456, and 0555123456 match identically."""
    digits = re.sub(r"\D+", "", str(raw or ""))
    if not digits:
        return ""
    if digits.startswith("00213") and len(digits) == 14:
        return "0" + digits[5:]
    if digits.startswith("213") and len(digits) == 12:
        return "0" + digits[3:]
    if len(digits) == 9 and digits[0] in ("5", "6", "7"):
        return "0" + digits
    return digits[:30]


def _check_order_rate_limit(user_id: int) -> int:
    """Return remaining cooldown seconds if user exceeded order rate limits, else 0."""
    if user_id in ADMIN_IDS:
        return 0
    now = time.time()
    hist = [ts for ts in _ORDER_SUBMISSIONS.get(user_id, []) if now - ts < _ORDER_WINDOW_SEC]
    _ORDER_SUBMISSIONS[user_id] = hist
    if hist:
        gap = now - hist[-1]
        if gap < _ORDER_MIN_GAP_SEC:
            return max(1, int(math.ceil(_ORDER_MIN_GAP_SEC - gap)))
    if len(hist) >= _ORDER_MAX_PER_WINDOW:
        wait = _ORDER_WINDOW_SEC - (now - hist[0])
        return max(1, int(math.ceil(wait)))
    return 0


def _record_order_submission(user_id: int) -> None:
    if user_id in ADMIN_IDS:
        return
    now = time.time()
    hist = [ts for ts in _ORDER_SUBMISSIONS.get(user_id, []) if now - ts < _ORDER_WINDOW_SEC]
    hist.append(now)
    _ORDER_SUBMISSIONS[user_id] = hist


async def is_blacklisted(s, user_tg_id: Optional[int] = None, phone: str = "") -> Optional[BlacklistedEntry]:
    """Return matching BlacklistedEntry if user_tg_id or normalized phone is banned."""
    conds = []
    if user_tg_id and user_tg_id not in ADMIN_IDS:
        conds.append(BlacklistedEntry.user_tg_id == user_tg_id)
    pnorm = _normalize_phone(phone)
    if pnorm and len(pnorm) >= 6:
        conds.append(BlacklistedEntry.phone_norm == pnorm)
    if not conds:
        return None
    return (await s.execute(select(BlacklistedEntry).where(or_(*conds)).limit(1))).scalar_one_or_none()


async def get_buyer_trust_summary(
    s,
    buyer_tg_id: Optional[int],
    phone: str = "",
    lang: str = "ar",
    exclude_order_id: Optional[int] = None,
) -> tuple[str, dict[str, Any]]:
    """Compute buyer reliability badge & stats across all historical orders matching TG ID or phone."""
    bl = await is_blacklisted(s, buyer_tg_id, phone)
    pnorm = _normalize_phone(phone)

    rows_by_id: dict[int, tuple[str, str]] = {}
    if buyer_tg_id:
        q = select(Order.id, Order.status, Order.buyer_phone).where(Order.buyer_tg_id == buyer_tg_id)
        for oid, st, ph in (await s.execute(q)).all():
            rows_by_id[oid] = (st, ph or "")

    if pnorm and len(pnorm) >= 8:
        tail = pnorm[-8:]
        q2 = select(Order.id, Order.status, Order.buyer_phone).where(Order.buyer_phone.like(f"%{tail}%"))
        for oid, st, ph in (await s.execute(q2)).all():
            if _normalize_phone(ph) == pnorm:
                rows_by_id[oid] = (st, ph or "")

    if exclude_order_id and exclude_order_id in rows_by_id:
        del rows_by_id[exclude_order_id]

    statuses = [st for st, _ in rows_by_id.values()]
    total = len(statuses)
    done = sum(1 for st in statuses if st == "completed")
    cancel = sum(1 for st in statuses if st == "cancelled")
    pending = sum(1 for st in statuses if st == "pending")
    shipped = sum(1 for st in statuses if st == "shipped")
    cancel_rate = (cancel / total * 100.0) if total else 0.0

    info = {
        "blacklisted": bl is not None,
        "bl_reason": bl.reason if bl else "",
        "total": total,
        "completed": done,
        "cancelled": cancel,
        "pending": pending,
        "shipped": shipped,
        "cancel_rate": cancel_rate,
    }

    if bl is not None:
        badge = t(lang, "trust_blacklisted")
    elif total == 0:
        badge = t(lang, "trust_new")
    elif cancel >= 3 or (total >= 3 and cancel_rate >= 50.0):
        badge = t(lang, "trust_high_risk", done=done, cancel=cancel, rate=cancel_rate)
    elif cancel >= 1:
        badge = t(lang, "trust_medium", done=done, cancel=cancel)
    elif done >= 1:
        badge = t(lang, "trust_good", done=done)
    else:
        badge = t(lang, "trust_active", total=total, pending=pending)

    return badge, info


class AntiFloodMiddleware(BaseMiddleware):
    """Lightweight sliding-window anti-spam middleware for messages and callback queries."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None or user.id in ADMIN_IDS:
            return await handler(event, data)
        uid = user.id
        now = time.time()
        bucket = [ts for ts in _FLOOD_BUCKETS.get(uid, []) if now - ts < _FLOOD_WINDOW_SEC]
        if len(bucket) >= _FLOOD_MAX_EVENTS:
            _FLOOD_BUCKETS[uid] = bucket
            last_w = _FLOOD_LAST_WARN.get(uid, 0.0)
            if now - last_w >= 5.0:
                _FLOOD_LAST_WARN[uid] = now
                warn_txt = t(DEFAULT_LANG, "flood_warn")
                with suppress(Exception):
                    if isinstance(event, CallbackQuery):
                        await event.answer(warn_txt, show_alert=True)
                    elif isinstance(event, Message):
                        await event.answer(warn_txt)
            return None
        bucket.append(now)
        _FLOOD_BUCKETS[uid] = bucket
        return await handler(event, data)


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
                .where(BotAd.status == "approved", BotAd.expires_at.is_not(None), BotAd.expires_at > utcnow())
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
                    Product.featured_until.is_not(None),
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
                .where(BotAd.status == "approved", BotAd.expires_at.is_not(None), BotAd.expires_at > utcnow())
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
        unlocked_codes = (
            await s.execute(select(UserBadge.badge_code).where(UserBadge.user_tg_id == uid))
        ).scalars().all()
        await s.commit()
    name = esc(u.saved_name) if u.saved_name else "غير محدد"
    phone = esc(u.saved_phone) if u.saved_phone else "غير محدد"
    addr = esc(u.saved_address) if u.saved_address else "غير محدد"
    total_xp = sum((get_badge_info(c) or {}).get("xp", 0) for c in unlocked_codes)
    lvl, r_em, r_nm, _ = get_user_rank(total_xp)
    eq = get_badge_info(getattr(u, "equipped_badge", "") or "")
    eq_line = f"{eq['emoji']} <b>{eq['title']}</b>" if eq else "<i>لم تُحدَّد بعد</i>"
    badge_summary = (
        f"\n━━━━━━━━━━━━━━━\n"
        f"✦ 🎖️ <b>المرتبة:</b> {r_em} <b>{r_nm}</b> (المستوى {lvl} • {total_xp} XP)\n"
        f"✦ 🏅 <b>شارتك المعروضة:</b> {eq_line}\n"
        f"✦ 🏆 <b>الشارات المفتوحة:</b> {len(unlocked_codes)} / {len(BADGE_CATALOG)}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_badges"), callback_data="badges:hub:buyer:0")],
        [InlineKeyboardButton(text=t(lang, "btn_edit_profile_name"), callback_data="prof_edit:name")],
        [InlineKeyboardButton(text=t(lang, "btn_edit_profile_phone"), callback_data="prof_edit:phone")],
        [InlineKeyboardButton(text=t(lang, "btn_edit_profile_address"), callback_data="prof_edit:address")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:account")],
    ])
    await target_msg.answer(
        t(lang, "profile_menu", name=name, phone=phone, address=addr) + badge_summary,
        reply_markup=kb,
    )


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
    stars_enabled, _ = await get_stars_config()
    pending_line = f"\n✦ ⏳ <b>طلبات قيد المراجعة:</b> {pending_topups}" if pending_topups else ""
    text = (
        f"💳✨ <b>محفظتي الذكية</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✦ 💰 <b>الرصيد المتاح:</b> <b>{bal:g} {DEFAULT_CURRENCY}</b>{pending_line}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💡 <i>استخدم رصيدك لتفعيل إعلاناتك وباقات <b>Pro / VIP</b> فورياً وبضغطة زر، أو للتجديد التلقائي دون انقطاع!</i> ⚡"
    )
    rows = [
        [InlineKeyboardButton(text="➕💳 شحن الرصيد الآن", callback_data="wallet:topup")],
        [InlineKeyboardButton(text=t(lang, "btn_wallet_voucher"), callback_data="wallet:voucher")],
    ]
    if stars_enabled:
        rows.append([InlineKeyboardButton(text=t(lang, "btn_wallet_stars"), callback_data="wallet:stars")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_wallet_history"), callback_data="wallet:history")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=back_cb)])
    await target_msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@buyer_router.callback_query(F.data == "wallet:topup")
async def wallet_topup_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_lang(cb.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"💵 1000 {DEFAULT_CURRENCY}", callback_data="wallet:amt:1000"),
            InlineKeyboardButton(text=f"💵 2000 {DEFAULT_CURRENCY}", callback_data="wallet:amt:2000"),
        ],
        [
            InlineKeyboardButton(text=f"💎 5000 {DEFAULT_CURRENCY}", callback_data="wallet:amt:5000"),
            InlineKeyboardButton(text=f"👑 10000 {DEFAULT_CURRENCY}", callback_data="wallet:amt:10000"),
        ],
        [InlineKeyboardButton(text="✏️ مبلغ مخصص", callback_data="wallet:amt:custom")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:wallet")],
    ])
    text = (
        "💳✨ <b>شحن رصيد المحفظة</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "اختر المبلغ المناسب لك أدناه:\n"
        "✦ ⚡ يدعم الدفع الإلكتروني الفوري (<b>EDAHABIA / CIB</b>)\n"
        "✦ 🏦 يدعم التحويل اليدوي (<b>BaridiMob / CCP</b>) مع رمز مرجعي فريد"
    )
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


async def _send_topup_instructions(target_msg: Message, state: FSMContext, lang: str, amt: float):
    ref_code = generate_pay_ref()
    await state.update_data(topup_amount=amt, topup_ref=ref_code)
    await state.set_state(WalletTopupFSM.proof)
    async with Session() as s:
        instr = await format_payment_instructions(s, lang, ref_code=ref_code, amount=amt)
    chg_key, _ = await get_chargily_config()
    rows = []
    if chg_key:
        rows.append([InlineKeyboardButton(text=t(lang, "btn_pay_chargily"), callback_data=f"chg_pay:wallet_topup:0:{int(round(amt))}")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:wallet")])
    await target_msg.answer(
        f"💳 <b>شحن رصيد: {amt:g} {DEFAULT_CURRENCY}</b>\n\n{instr}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@buyer_router.callback_query(F.data.startswith("wallet:amt:"))
async def wallet_topup_amount_cb(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[2]
    lang = await get_lang(cb.from_user.id)
    if val == "custom":
        await state.set_state(WalletTopupFSM.custom_amount)
        await cb.message.answer(f"✏️ أرسل المبلغ الذي تريد شحنه ({DEFAULT_CURRENCY}) — الحد الأدنى 500:")
        return await cb.answer()
    amt = float(val)
    await _send_topup_instructions(cb.message, state, lang, amt)
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
    await _send_topup_instructions(message, state, lang, amt)


@buyer_router.message(WalletTopupFSM.proof, F.photo)
async def wallet_topup_receive_proof(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    amt = float(data.get("topup_amount", 0))
    ref_code = str(data.get("topup_ref") or generate_pay_ref())
    if amt <= 0:
        await state.clear()
        return await message.answer(t(lang, "cancelled"), reply_markup=await get_main_kb(message.from_user.id, lang))
    photo_id = message.photo[-1].file_id
    uniq_id = message.photo[-1].file_unique_id
    async with Session() as s:
        if await is_duplicate_receipt(s, uniq_id):
            return await message.answer(t(lang, "dup_receipt_err"))
        req = AdRequest(
            user_tg_id=message.from_user.id,
            ad_type="wallet_topup",
            target_id=0,
            package_name=f"topup_{int(amt)}",
            price=amt,
            payment_proof=photo_id,
            proof_unique_id=uniq_id,
            ref_code=ref_code,
            status="pending",
        )
        s.add(req)
        await s.commit()
        await s.refresh(req)
        req_id = req.id
    await state.clear()
    await message.answer(
        f"✅ <b>تم إرسال طلب شحن المحفظة (#{req_id}) بنجاح!</b>\n"
        f"🏷️ الرمز المرجعي: <code>{esc(ref_code)}</code>\n"
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
        f"🏷️ المرجع: <code>{esc(ref_code)}</code>\n"
        f"👤 المستخدم: {esc(message.from_user.full_name)} (<code>{message.from_user.id}</code>)\n"
        f"💰 المبلغ المطلوب: <b>{amt:g} {DEFAULT_CURRENCY}</b>",
        reply_markup=admin_kb,
        photo=photo_id,
    )


@buyer_router.message(WalletTopupFSM.proof, ~F.photo)
async def wallet_topup_proof_invalid(message: Message):
    await message.answer("📸 يرجى إرسال صورة وصل الدفع (أو /cancel للإلغاء).")


# ─── Prepaid Recharge Vouchers (Gift Cards) ───

@buyer_router.callback_query(F.data == "wallet:voucher")
async def wallet_voucher_prompt(cb: CallbackQuery, state: FSMContext):
    await state.set_state(VoucherRedeemFSM.code)
    await cb.message.answer("🎟️ <b>شحن بكود بطاقة مسبقة الدفع</b>\n\nأرسل كود البطاقة الآن (أو /cancel للإلغاء):")
    await cb.answer()


@buyer_router.message(VoucherRedeemFSM.code)
async def wallet_voucher_redeem(message: Message, state: FSMContext):
    uid = message.from_user.id
    lang = await get_lang(uid)
    code = (message.text or "").strip().upper()
    if not code or len(code) > 50:
        return await message.answer("❌ كود غير صالح. أعد إدخال الكود أو أرسل /cancel:")
    async with Session() as s:
        v = (await s.execute(select(Voucher).where(Voucher.code == code))).scalar_one_or_none()
        if not v or not v.is_active or v.used_count >= v.max_uses:
            return await message.answer("❌ الكود غير صحيح أو منتهي الصلاحية أو مستنفد الاستخدام.")
        already = (
            await s.execute(
                select(VoucherRedemption.id).where(
                    VoucherRedemption.voucher_id == v.id,
                    VoucherRedemption.user_tg_id == uid,
                )
            )
        ).scalar_one_or_none()
        if already:
            return await message.answer("⚠️ لقد استخدمت هذا الكود مسبقاً!")
        u = await ensure_user(s, uid, lang)
        v.used_count += 1
        if v.used_count >= v.max_uses:
            v.is_active = False
        s.add(VoucherRedemption(voucher_id=v.id, user_tg_id=uid))
        await record_wallet_tx(
            s,
            u,
            v.amount,
            "voucher",
            f"🎟️ شحن عبر بطاقة كود {v.code}",
            ref_code=v.code,
        )
        new_bal = float(u.ad_credits or 0.0)
        v_amt = float(v.amount)
        await s.commit()
    await state.clear()
    await message.answer(
        f"🎉 <b>تم شحن محفظتك بنجاح!</b>\n\n"
        f"🎟️ الكود: <code>{esc(code)}</code>\n"
        f"➕ المبلغ المضاف: <b>+{v_amt:g} {DEFAULT_CURRENCY}</b>\n"
        f"💰 رصيدك الحالي: <b>{new_bal:g} {DEFAULT_CURRENCY}</b>",
        reply_markup=await get_main_kb(uid, lang),
    )


# ─── Wallet Transaction History (Ledger) ───

async def _render_wallet_history(msg_obj: Message, uid: int, page: int, edit: bool = True):
    lang = await get_lang(uid)
    per_page = 8
    async with Session() as s:
        total = (
            await s.execute(select(func.count(WalletTransaction.id)).where(WalletTransaction.user_tg_id == uid))
        ).scalar() or 0
        total_pages = max(1, math.ceil(total / per_page))
        page = max(1, min(page, total_pages))
        rows = (
            await s.execute(
                select(WalletTransaction)
                .where(WalletTransaction.user_tg_id == uid)
                .order_by(WalletTransaction.id.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        ).scalars().all()
    icons = {
        "topup": "💳",
        "voucher": "🎟️",
        "stars": "⭐",
        "chargily": "⚡",
        "subscription": "👑",
        "ad": "📢",
        "bonus": "🎁",
        "refund": "↩️",
    }
    if not rows:
        text = "📜 <b>سجل معاملات المحفظة</b>\n\nلا توجد معاملات مسجلة بعد."
    else:
        lines = [f"📜 <b>سجل معاملات المحفظة</b> (صفحة {page}/{total_pages} — إجمالي {total}):\n"]
        for tx in rows:
            ic = icons.get(tx.tx_type, "💰")
            sign = "+" if tx.amount >= 0 else ""
            dt_str = tx.created_at.strftime("%Y-%m-%d %H:%M") if tx.created_at else ""
            ref_str = f" | <code>{esc(tx.ref_code)}</code>" if tx.ref_code else ""
            lines.append(
                f"{ic} <b>{sign}{tx.amount:g} {DEFAULT_CURRENCY}</b> → الرصيد: {tx.balance_after:g}\n"
                f"   {esc(tx.description)}{ref_str}\n"
                f"   <i>{dt_str}</i>"
            )
        text = "\n".join(lines)
    kb = []
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text=t(lang, "btn_prev"), callback_data=f"wallet:hist_pg:{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text=t(lang, "btn_next"), callback_data=f"wallet:hist_pg:{page + 1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:wallet")])
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    if edit:
        try:
            await msg_obj.edit_text(text[:4000], reply_markup=markup)
            return
        except Exception:
            pass
    await msg_obj.answer(text[:4000], reply_markup=markup)


@buyer_router.callback_query(F.data == "wallet:history")
async def wallet_history_cb(cb: CallbackQuery):
    await _render_wallet_history(cb.message, cb.from_user.id, 1, edit=True)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("wallet:hist_pg:"))
async def wallet_history_page_cb(cb: CallbackQuery):
    page = int(cb.data.split(":")[2])
    await _render_wallet_history(cb.message, cb.from_user.id, page, edit=True)
    await cb.answer()


# ─── Telegram Stars (XTR) Native In-App Top-Up ───

@buyer_router.callback_query(F.data == "wallet:stars")
async def wallet_stars_menu(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    enabled, rate = await get_stars_config()
    if not enabled:
        return await cb.answer("⭐ شحن نجوم تيليجرام غير مفعّل حالياً.", show_alert=True)
    packs = [50, 100, 250, 500, 1000]
    rows = []
    for st_cnt in packs:
        dzd = int(round(st_cnt * rate))
        rows.append([
            InlineKeyboardButton(
                text=f"⭐ {st_cnt} Stars → {dzd:g} {DEFAULT_CURRENCY}",
                callback_data=f"wallet:stars_buy:{st_cnt}",
            )
        ])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:wallet")])
    text = (
        f"⭐ <b>شحن المحفظة بنجوم تيليجرام (Telegram Stars)</b>\n\n"
        f"💱 سعر الصرف الحالي: <b>1 ⭐ = {rate:g} {DEFAULT_CURRENCY}</b>\n"
        f"⚡ يتم شحن الرصيد في محفظتك <b>فوراً وتلقائياً</b> بعد الدفع!"
    )
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("wallet:stars_buy:"))
async def wallet_stars_send_invoice(cb: CallbackQuery):
    enabled, rate = await get_stars_config()
    if not enabled:
        return await cb.answer("⭐ غير مفعّل حالياً.", show_alert=True)
    stars = int(cb.data.split(":")[2])
    if stars < 1 or stars > 50000:
        return await cb.answer("❌ باقة غير صالحة.", show_alert=True)
    dzd = int(round(stars * rate))
    payload = f"stars_topup:{cb.from_user.id}:{stars}:{dzd}"
    try:
        await cb.message.answer_invoice(
            title=f"شحن المحفظة ({dzd} {DEFAULT_CURRENCY})",
            description=f"شحن فوري لرصيد محفظة Market Bot بقيمة {dzd} {DEFAULT_CURRENCY} مقابل {stars} نجمة تيليجرام.",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=f"{dzd} {DEFAULT_CURRENCY}", amount=stars)],
        )
    except Exception as e:
        logger.warning(f"Stars invoice error: {e}")
        return await cb.answer("❌ تعذّر إنشاء فاتورة النجوم.", show_alert=True)
    await cb.answer()


@buyer_router.pre_checkout_query()
async def stars_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@buyer_router.message(F.successful_payment)
async def stars_successful_payment(message: Message):
    sp = message.successful_payment
    if not sp or sp.currency != "XTR":
        return
    uid = message.from_user.id
    lang = await get_lang(uid)
    payload = sp.invoice_payload or ""
    parts = payload.split(":")
    if len(parts) < 4 or parts[0] != "stars_topup":
        return
    stars = int(sp.total_amount or 0)
    _, rate = await get_stars_config()
    dzd_amt = round(stars * rate, 2)
    charge_id = (sp.telegram_payment_charge_id or f"XTR-{int(time.time())}")[:50]
    async with Session() as s:
        dup = (
            await s.execute(select(WalletTransaction.id).where(WalletTransaction.ref_code == charge_id).limit(1))
        ).scalar_one_or_none()
        if dup:
            return
        u = await ensure_user(s, uid, lang)
        await record_wallet_tx(
            s,
            u,
            dzd_amt,
            "stars",
            f"⭐ شحن تلقائي عبر {stars} Telegram Stars",
            ref_code=charge_id,
        )
        new_bal = float(u.ad_credits or 0.0)
        await s.commit()
    await message.answer(
        f"⭐ <b>تم الدفع بنجوم تيليجرام وشحن محفظتك فوراً!</b>\n\n"
        f"➕ المبلغ المضاف: <b>+{dzd_amt:g} {DEFAULT_CURRENCY}</b> ({stars} ⭐)\n"
        f"💰 رصيدك الحالي: <b>{new_bal:g} {DEFAULT_CURRENCY}</b>",
        reply_markup=await get_main_kb(uid, lang),
    )
    await notify_admins(
        message.bot,
        f"⭐ <b>شحن فوري بنجوم تيليجرام</b>\n"
        f"👤 المستخدم: <code>{uid}</code>\n"
        f"⭐ النجوم: <b>{stars}</b> → <b>{dzd_amt:g} {DEFAULT_CURRENCY}</b>",
    )


# ─── Chargily Pay v2 (EDAHABIA / CIB) Instant Checkout & Verify ───

@buyer_router.callback_query(F.data.startswith("chg_pay:"))
async def chargily_start_checkout(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    if len(parts) < 4:
        return await cb.answer("❌ طلب غير صالح.", show_alert=True)
    ad_type, target_id_str, extra = parts[1], parts[2], parts[3]
    target_id = int(target_id_str)
    uid = cb.from_user.id
    lang = await get_lang(uid)

    chg_key, chg_mode = await get_chargily_config()
    if not chg_key:
        return await cb.answer("⚠️ بوابة Chargily Pay غير مفعّلة حالياً.", show_alert=True)

    amount = 0.0
    desc = "Market Bot Payment"
    pkg_name = extra
    if ad_type == "wallet_topup":
        amount = float(extra)
        pkg_name = f"topup_{int(round(amount))}"
        desc = f"Wallet Top-up {int(round(amount))} DZD (User {uid})"
    elif ad_type == "store_vip":
        if not await is_store_owner(uid, target_id):
            return await cb.answer("⛔ غير مصرح.", show_alert=True)
        plans = await get_dynamic_plans()
        plan = plans.get(extra)
        if not plan:
            return await cb.answer("❌ باقة غير صالحة.", show_alert=True)
        amount = float(plan["price"])
        st_data = await state.get_data()
        disc = int(st_data.get("sub_coupon_pct", 0) or 0)
        if 1 <= disc <= 95:
            amount = max(100.0, round(amount * (1.0 - disc / 100.0), 2))
        desc = f"Store #{target_id} Subscription {plan['label']}"
    elif ad_type == "product":
        if not await is_product_owner(uid, target_id):
            return await cb.answer("⛔ غير مصرح.", show_alert=True)
        pkg = AD_PACKAGES.get(extra)
        if not pkg:
            return await cb.answer("❌ باقة غير صالحة.", show_alert=True)
        amount = float(pkg["price"])
        desc = f"Featured Product #{target_id} ({pkg['label']})"
    else:
        return await cb.answer("❌ نوع غير مدعوم.", show_alert=True)

    if amount < 75:
        return await cb.answer("⚠️ الحد الأدنى للدفع عبر Chargily هو 75 دج.", show_alert=True)

    ref_code = generate_pay_ref()
    resp = await chargily_create_checkout(
        amount_dzd=amount,
        description=desc,
        metadata={"user_id": uid, "ad_type": ad_type, "target_id": target_id, "pkg": pkg_name, "ref": ref_code},
    )
    checkout_url = resp.get("checkout_url")
    checkout_id = resp.get("id")
    if not checkout_url or not checkout_id:
        err = esc(str(resp.get("error") or resp)[:200])
        return await cb.message.answer(f"❌ تعذّر إنشاء رابط الدفع عبر Chargily:\n<code>{err}</code>")

    async with Session() as s:
        req = AdRequest(
            user_tg_id=uid,
            ad_type=ad_type,
            target_id=target_id,
            package_name=pkg_name,
            price=amount,
            payment_proof="",
            ref_code=ref_code,
            external_id=str(checkout_id),
            status="pending",
        )
        s.add(req)
        await s.commit()
        await s.refresh(req)
        req_id = req.id

    await state.clear()
    mode_tag = "🧪 وضع تجريبي (Test)" if chg_mode == "test" else "🟢 وضع مباشر (Live)"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 ادفع الآن (EDAHABIA / CIB)", url=checkout_url)],
        [InlineKeyboardButton(text="✅ تحقّق من الدفع وتفعيل فوري", callback_data=f"chg_verify:{req_id}")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:wallet")],
    ])
    await cb.message.answer(
        f"⚡ <b>فاتورة Chargily Pay جاهزة!</b> ({mode_tag})\n\n"
        f"🏷️ المرجع: <code>{esc(ref_code)}</code>\n"
        f"💰 المبلغ: <b>{amount:g} {DEFAULT_CURRENCY}</b>\n\n"
        f"1️⃣ اضغط على <b>«ادفع الآن»</b> وأكمل الدفع ببطاقة الذهبية أو CIB.\n"
        f"2️⃣ عُد هنا واضغط <b>«تحقّق من الدفع وتفعيل فوري»</b> لتفعيل طلبك تلقائياً خلال ثوانٍ!",
        reply_markup=kb,
    )
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("chg_verify:"))
async def chargily_verify_cb(cb: CallbackQuery):
    req_id = int(cb.data.split(":")[1])
    uid = cb.from_user.id
    lang = await get_lang(uid)

    async with Session() as s:
        req = await s.get(AdRequest, req_id)
        if not req:
            return await cb.answer("❌ الفاتورة غير موجودة.", show_alert=True)
        if req.user_tg_id != uid and uid not in ADMIN_IDS:
            return await cb.answer("⛔ غير مصرح.", show_alert=True)
        if req.status == "approved":
            return await cb.answer("✅ تم تفعيل هذه الفاتورة مسبقاً!", show_alert=True)
        if req.status != "pending" or not req.external_id:
            return await cb.answer("⚠️ هذه الفاتورة غير صالحة للتحقق.", show_alert=True)
        ext_id = req.external_id

    data = await chargily_verify_checkout(ext_id)
    if data.get("error"):
        return await cb.answer("⚠️ تعذّر الاتصال بـ Chargily حالياً، حاول بعد لحظات.", show_alert=True)

    status = str(data.get("status", "")).lower()
    if status != "paid":
        if status in ("failed", "canceled", "expired"):
            async with Session() as s:
                req = await s.get(AdRequest, req_id)
                if req and req.status == "pending":
                    req.status = "rejected"
                    await s.commit()
            return await cb.answer(f"❌ حالة الفاتورة: {status}. يرجى إنشاء فاتورة جديدة.", show_alert=True)
        return await cb.answer("⏳ لم يتم تأكيد الدفع بعد. أكمل الدفع في الرابط ثم اضغط تحقق مجدداً.", show_alert=True)

    # Paid! Atomically fulfill
    msg_out = ""
    async with Session() as s:
        res = await s.execute(
            update(AdRequest)
            .where(AdRequest.id == req_id, AdRequest.status == "pending")
            .values(status="approved")
        )
        if res.rowcount == 0:
            return await cb.answer("✅ تم تفعيل هذه الفاتورة مسبقاً!", show_alert=True)
        req = await s.get(AdRequest, req_id)
        u = await ensure_user(s, req.user_tg_id, lang)

        if req.ad_type == "wallet_topup":
            await record_wallet_tx(
                s,
                u,
                req.price,
                "chargily",
                f"⚡ شحن فوري عبر Chargily Pay ({req.ref_code})",
                ref_code=req.ref_code,
            )
            msg_out = (
                f"⚡ <b>تم التحقق من الدفع وشحن محفظتك فوراً!</b>\n\n"
                f"➕ المبلغ المضاف: <b>+{req.price:g} {DEFAULT_CURRENCY}</b>\n"
                f"💰 رصيدك الحالي: <b>{float(u.ad_credits or 0):g} {DEFAULT_CURRENCY}</b>"
            )
        elif req.ad_type == "store_vip":
            st = await s.get(Store, req.target_id)
            if st:
                until_str, bonus, tier = await activate_store_plan(s, st, req.package_name, user=u)
                b_line = f"\n🎁 تم إضافة رصيد هدية: <b>+{bonus:g} {DEFAULT_CURRENCY}</b>" if bonus > 0 else ""
                msg_out = (
                    f"⚡ <b>تم الدفع وتفعيل اشتراك {tier.upper()} لمتجر {esc(st.name)} فوراً!</b>\n"
                    f"📅 صالح حتى: <b>{until_str}</b>{b_line}"
                )
        elif req.ad_type == "product":
            pkg = AD_PACKAGES.get(req.package_name, AD_PACKAGES["basic"])
            days = int(pkg["days"])
            prod = await s.get(Product, req.target_id)
            if prod and not prod.is_deleted:
                now = utcnow()
                base = prod.featured_until if (prod.featured_until and prod.featured_until > now) else now
                prod.featured_until = base + timedelta(days=days)
                msg_out = (
                    f"⚡ <b>تم الدفع وتمييز منتجك {esc(prod.title)} فوراً!</b>\n"
                    f"📅 مميز حتى: <b>{prod.featured_until.strftime('%Y-%m-%d')}</b>"
                )
        await s.commit()

    with suppress(Exception):
        await cb.message.edit_text(msg_out or "✅ تم التفعيل بنجاح!", reply_markup=back_kb(lang, "menu:home"))
    await notify_admins(
        cb.bot,
        f"⚡ <b>دفع إلكتروني مؤكد عبر Chargily Pay</b>\n"
        f"👤 المستخدم: <code>{req.user_tg_id}</code>\n"
        f"📦 النوع: <b>{esc(req.ad_type)}</b> ({esc(req.package_name)})\n"
        f"💰 المبلغ: <b>{req.price:g} {DEFAULT_CURRENCY}</b> | <code>{esc(req.ref_code)}</code>",
    )
    await cb.answer("✅ تم التحقق والتفعيل الفوري!", show_alert=True)


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
    wait = _check_order_rate_limit(user_id)
    if wait > 0:
        await state.clear()
        return await msg_obj.answer(t(lang, "order_rate_limited", wait=wait))
    async with Session() as s:
        if await is_blacklisted(s, user_tg_id=user_id):
            await state.clear()
            return await msg_obj.answer(t(lang, "order_blocked_blacklist"))
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
    phone_val = message.text.strip()[:MAX_PROFILE_PHONE_LEN]
    async with Session() as s:
        if await is_blacklisted(s, user_tg_id=message.from_user.id, phone=phone_val):
            await state.clear()
            return await message.answer(
                t(lang, "order_blocked_blacklist"),
                reply_markup=await get_main_kb(message.from_user.id, lang),
            )
    await state.update_data(p_phone=phone_val)
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

    wait = _check_order_rate_limit(user_id)
    if wait > 0:
        await state.clear()
        return await message_obj.answer(
            t(lang, "order_rate_limited", wait=wait),
            reply_markup=await get_main_kb(user_id, lang),
        )

    pairs: list[tuple[Product, str, int]] = []
    async with Session() as s:
        if await is_blacklisted(s, user_tg_id=user_id, phone=phone):
            await state.clear()
            return await message_obj.answer(
                t(lang, "order_blocked_blacklist"),
                reply_markup=await get_main_kb(user_id, lang),
            )
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
        deposit_prompts: list[tuple[int, str, float, str]] = []
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
                await s.flush()
                orders_created += 1
                total_charged += final_price
                total_delivery += computed_delivery

                order_total = final_price + computed_delivery
                if float(store.deposit_amount or 0.0) > 0 and (
                    float(store.deposit_threshold or 0.0) <= 0 or order_total >= float(store.deposit_threshold or 0.0)
                ):
                    contact_hint = store.contact_phone or store.contact or ""
                    deposit_prompts.append((order.id, store.name, float(store.deposit_amount), contact_hint))

                sl = await get_lang(store.owner_tg_id)
                trust_badge, _trust_info = await get_buyer_trust_summary(s, user_id, phone, sl)
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
                    + f"\n🔢 الكمية: <b>{qty}</b>\n🗺️ الولاية: <b>{esc(wilaya_label(wilaya_code, sl) if wilaya_code else '—')}</b>\n🚚 التوصيل: {dtype_label}"
                    + f"\n{t(sl, 'trust_label')}: <b>{trust_badge}</b>"
                )
                seller_notifications.append((store.owner_tg_id, seller_text))

        if not is_direct_order:
            await s.execute(delete(CartItem).where(CartItem.user_tg_id == user_id))
        await s.commit()

    if orders_created > 0:
        _record_order_submission(user_id)
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

    if deposit_prompts:
        oid, sname, dep_amt, contact_hint = deposit_prompts[0]
        contact_line = f"\n📞 للتواصل مع البائع: <b>{esc(contact_hint)}</b>" if contact_hint else ""
        dep_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 إرسال وصل العربون الآن", callback_data=f"ord_dep_send:{oid}")],
            [InlineKeyboardButton(text="⏭️ لاحقاً / تخطي", callback_data="ord_dep_skip")],
        ])
        await message_obj.answer(
            f"💵 <b>طلب عربون لتأكيد الطلب (#{oid})</b>\n\n"
            f"🏪 المتجر <b>{esc(sname)}</b> يطلب عربوناً بقيمة <b>{dep_amt:g} {DEFAULT_CURRENCY}</b> لتأكيد الشحن السريع.{contact_line}\n\n"
            f"يمكنك إرسال صورة وصل العربون الآن لتصل مباشرة للبائع:",
            reply_markup=dep_kb,
        )


@buyer_router.callback_query(F.data.startswith("ord_dep_send:"))
async def order_deposit_prompt(cb: CallbackQuery, state: FSMContext):
    oid = int(cb.data.split(":")[1])
    async with Session() as s:
        order = await s.get(Order, oid)
        if not order or order.buyer_tg_id != cb.from_user.id:
            return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(dep_order_id=oid)
    await state.set_state(OrderDepositFSM.proof)
    await cb.message.answer(f"📸 أرسل صورة وصل العربون للطلب #{oid} الآن (أو /cancel للإلغاء):")
    await cb.answer()


@buyer_router.callback_query(F.data == "ord_dep_skip")
async def order_deposit_skip(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    with suppress(Exception):
        await cb.message.edit_text("⏭️ تم التخطي. يمكنك التواصل مع البائع لاحقاً.")
    await cb.answer()


@buyer_router.message(OrderDepositFSM.proof, F.photo)
async def order_deposit_receive(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    oid = int(data.get("dep_order_id") or 0)
    await state.clear()
    photo_id = message.photo[-1].file_id
    async with Session() as s:
        order = await s.get(Order, oid)
        if not order or order.buyer_tg_id != message.from_user.id:
            return await message.answer("❌ الطلب غير موجود.", reply_markup=await get_main_kb(message.from_user.id, lang))
        order.deposit_proof = photo_id
        seller_uid = order.seller_tg_id
        buyer_name = order.buyer_name
        await s.commit()
    await message.answer(
        f"✅ تم إرسال وصل العربون للطلب <b>#{oid}</b> إلى البائع بنجاح!",
        reply_markup=await get_main_kb(message.from_user.id, lang),
    )
    with suppress(Exception):
        await message.bot.send_photo(
            seller_uid,
            photo=photo_id,
            caption=f"💵 <b>وصل عربون للطلب #{oid}</b>\n👤 المشتري: <b>{esc(buyer_name)}</b>",
        )


@buyer_router.message(OrderDepositFSM.proof, ~F.photo)
async def order_deposit_invalid(message: Message):
    await message.answer("📸 يرجى إرسال صورة وصل العربون (أو /cancel للإلغاء).")


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
            base_conds.append(Product.flash_sale_price.is_not(None))
            base_conds.append(Product.flash_sale_ends_at.is_not(None))
            base_conds.append(Product.flash_sale_ends_at > now)

        count_q = select(func.count(Product.id)).where(*base_conds)
        list_q = select(Product).where(*base_conds)

        if flt == "verified":
            verified_cond = or_(Store.verified.is_(True), and_(Store.vip_until.is_not(None), Store.vip_until > now))
            count_q = count_q.join(Store, Store.id == Product.store_id).where(verified_cond)
            list_q = list_q.join(Store, Store.id == Product.store_id).where(verified_cond)

        if flt == "cheap":
            eff_price = case(
                (
                    and_(
                        Product.flash_sale_price.is_not(None),
                        Product.flash_sale_ends_at.is_not(None),
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
    vip_rank = case((and_(Store.vip_until.is_not(None), Store.vip_until > now), 1), else_=0)
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
    rev_sid = data.get("rev_store_id")
    owner_uid = None
    if rev_sid:
        try:
            async with Session() as s:
                s.add(Review(store_id=rev_sid, buyer_tg_id=cb.from_user.id, rating=data["rev_rating"], comment=""))
                st_obj = await s.get(Store, rev_sid)
                owner_uid = st_obj.owner_tg_id if st_obj else None
                await s.commit()
        except IntegrityError:
            pass
    await state.clear()
    with suppress(Exception):
        await cb.message.edit_text(t(lang, "rating_thanks"))
    with suppress(Exception):
        await evaluate_user_badges(cb.bot, cb.from_user.id, notify=True)
        if owner_uid:
            await evaluate_user_badges(cb.bot, owner_uid, notify=True)
    await cb.answer()


@buyer_router.message(ReviewFSM.comment)
async def review_comment(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    rev_sid = data.get("rev_store_id")
    owner_uid = None
    if rev_sid:
        try:
            async with Session() as s:
                s.add(
                    Review(
                        store_id=rev_sid,
                        buyer_tg_id=message.from_user.id,
                        rating=data["rev_rating"],
                        comment=(message.text or "").strip()[:500],
                    )
                )
                st_obj = await s.get(Store, rev_sid)
                owner_uid = st_obj.owner_tg_id if st_obj else None
                await s.commit()
        except IntegrityError:
            pass
    await state.clear()
    await message.answer(t(lang, "rating_thanks"), reply_markup=await get_main_kb(message.from_user.id, lang))
    with suppress(Exception):
        await evaluate_user_badges(message.bot, message.from_user.id, notify=True)
        if owner_uid:
            await evaluate_user_badges(message.bot, owner_uid, notify=True)


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
        return await message.answer(
            f"❌ وصلت للحد الأقصى للمتاجر في باقتك الحالية ({max_stores}). يمكنك ترقية باقتك إلى Pro أو VIP لفتح المزيد من المتاجر!",
            reply_markup=await get_main_kb(message.from_user.id, lang),
        )
    grant_trial = len(stores) == 0
    async with Session() as s:
        st = Store(
            owner_tg_id=message.from_user.id,
            name=message.text.strip()[:MAX_STORE_NAME_LEN],
            contact=message.from_user.username or "",
        )
        if grant_trial:
            st.plan_tier = "pro"
            st.plan_expires_at = utcnow() + timedelta(days=TRIAL_DAYS)
            st.auto_approve = True
            st.trial_used = True
        s.add(st)
        u = await ensure_user(s, message.from_user.id, lang)
        u.role = "seller"
        await s.commit()
    await state.clear()
    trial_note = (
        f"\n\n🎁 <b>هدية الترحيب!</b> تم تفعيل <b>تجربة باقة Pro المجانية لمدة {TRIAL_DAYS} أيام</b> لمتجرك (نشر مباشر + حتى {MAX_PRODUCTS_PRO} منتج + إحصائيات كاملة)!"
        if grant_trial
        else ""
    )
    await message.answer(t(lang, "store_created") + trial_note, reply_markup=await get_main_kb(message.from_user.id, lang))


# ─── Top 5 Algerian Delivery Companies Hub (Seller Section) ───

async def _render_delivery_companies_hub(msg_obj: Message, sid: int, lang: str, edit: bool = True):
    async with Session() as s:
        st = await s.get(Store, sid)
    if not st:
        return
    active_code = (st.delivery_company or "").strip().lower()
    active_co = get_delivery_company(active_code)
    active_str = (
        f"{active_co['emoji']} <b>{active_co['name']}</b> ({active_co['name_ar']}) ✅"
        if active_co
        else "<i>لم يتم اختيار شركة بعد</i>"
    )
    text = (
        f"🚚✨ <b>شركات التوصيل في الجزائر — {esc(st.name)}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✦ 📌 <b>الشركة المعتمدة لمتجرك:</b> {active_str}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"اختر إحدى أفضل <b>5 شركات توصيل في الجزائر</b> لعرض كامل تفاصيلها وأسعارها، أو:\n"
        f"✦ ✅ اعتمادها لمتجرك (يُرفق رابط التتبع تلقائياً للمشترين)\n"
        f"✦ ⚡ تطبيق جدول أسعار الـ <b>58 ولاية</b> بضغطة زر\n"
        f"✦ 📥 تصدير طلباتك بملف <b>CSV جاهز للرفع</b> لمنصة التوصيل\n"
        f"✦ 🧮 حساب الوزن الحجمي وتكلفة الطرد"
    )
    rows = []
    for code, co in DELIVERY_COMPANIES.items():
        mark = " ✅" if code == active_code else ""
        rows.append([
            InlineKeyboardButton(
                text=f"{co['emoji']} {co['name']} — {co['name_ar']}{mark}",
                callback_data=f"st_dc_view:{sid}:{code}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text="📊 مقارنة سريعة بين الشركات", callback_data=f"st_dc_compare:{sid}"),
    ])
    rows.append([
        InlineKeyboardButton(text="🧮 حاسبة الوزن الحجمي", callback_data=f"st_dc_calc:{sid}"),
        InlineKeyboardButton(text="💰 أسعار 58 ولاية", callback_data=f"st_delivery:{sid}"),
    ])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=kb)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=kb)


@seller_router.callback_query(F.data.startswith("st_deliv_co:"))
async def seller_delivery_companies_hub(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    await _render_delivery_companies_hub(cb.message, sid, lang, edit=True)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_dc_view:"))
async def seller_delivery_company_detail(cb: CallbackQuery):
    _, sid_str, code = cb.data.split(":", 2)
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    co = get_delivery_company(code)
    if not co:
        return await cb.answer("❌ الشركة غير موجودة.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        st = await s.get(Store, sid)
    if not st:
        return await cb.answer("Not found", show_alert=True)
    is_selected = (st.delivery_company or "").strip().lower() == code
    feats_txt = "\n".join(f"   • {f}" for f in co["features"])
    status_badge = "\n✅ <b>هذه هي الشركة المعتمدة حالياً لمتجرك</b>" if is_selected else ""
    text = (
        f"{co['emoji']}✨ <b>{co['name']} — {co['name_ar']}</b>{status_badge}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>{co['tagline']}</i>\n\n"
        f"🗺️ <b>التغطية:</b> {co['coverage']}\n"
        f"⏱️ <b>مدة التوصيل:</b> الشمال {co['speed_north']} | الجنوب {co['speed_south']}\n\n"
        f"💰 <b>متوسط الأسعار (حتى 5 كغ):</b>\n"
        f"{co['price_summary']}\n"
        f"✦ ⚖️ <b>الوزن الإضافي:</b> {co['extra_kg']}\n\n"
        f"💵 <b>الدفع عند الاستلام (COD):</b> {co['cod_info']}\n"
        f"🔄 <b>المرتجعات:</b> {co['return_info']}\n\n"
        f"🌟 <b>أبرز المميزات:</b>\n{feats_txt}\n\n"
        f"🎯 <b>الأنسب لـ:</b> {co['best_for']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📞 <b>الهاتف:</b> <code>{co['phone']}</code>\n"
        f"📧 <b>البريد:</b> <code>{co['email']}</code>\n"
        f"📍 <b>المقر:</b> {co['hq']}\n"
        f"🔌 <b>الربط التقني (API):</b> {co['api_info']}"
    )
    rows = []
    if is_selected:
        rows.append([
            InlineKeyboardButton(
                text="❌ إلغاء اعتماد هذه الشركة لمتجري",
                callback_data=f"st_dc_select:{sid}:none",
            )
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text=f"✅ اعتماد {co['name']} كشركة لمتجري",
                callback_data=f"st_dc_select:{sid}:{code}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="⚡ تطبيق أسعار 58 ولاية تلقائياً",
            callback_data=f"st_dc_apply:{sid}:{code}",
        )
    ])
    rows.append([
        InlineKeyboardButton(
            text=f"📥 تصدير الطلبات المعلّقة لـ {co['name']} (CSV)",
            callback_data=f"st_dc_export:{sid}:{code}",
        )
    ])
    rows.append([
        InlineKeyboardButton(text="🌐 الموقع الرسمي", url=co["website"]),
        InlineKeyboardButton(text="🔎 تتبع طرد", url=co["tracking_url"]),
    ])
    rows.append([InlineKeyboardButton(text="↩️ قائمة شركات التوصيل", callback_data=f"st_deliv_co:{sid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await cb.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        await cb.message.answer(text, reply_markup=kb, disable_web_page_preview=True)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_dc_select:"))
async def seller_delivery_company_select(cb: CallbackQuery):
    _, sid_str, code = cb.data.split(":", 2)
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    new_code = "" if code == "none" else code
    if new_code and not get_delivery_company(new_code):
        return await cb.answer("❌ شركة غير صالحة.", show_alert=True)
    async with Session() as s:
        st = await s.get(Store, sid)
        if not st:
            return await cb.answer("Not found", show_alert=True)
        st.delivery_company = new_code
        await s.commit()
    if new_code:
        co = get_delivery_company(new_code)
        await cb.answer(f"✅ تم اعتماد {co['name']} لمتجرك بنجاح!", show_alert=True)
    else:
        await cb.answer("✅ تم إلغاء اختيار شركة التوصيل.", show_alert=True)
    await _render_delivery_companies_hub(cb.message, sid, lang, edit=True)


@seller_router.callback_query(F.data.startswith("st_dc_apply:"))
async def seller_delivery_company_apply_rates(cb: CallbackQuery):
    _, sid_str, code = cb.data.split(":", 2)
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    co = get_delivery_company(code)
    if not co:
        return await cb.answer("❌ الشركة غير موجودة.", show_alert=True)
    async with Session() as s:
        st = await s.get(Store, sid)
        if not st:
            return await cb.answer("Not found", show_alert=True)
        existing_rows = (
            await s.execute(select(StoreDeliveryRate).where(StoreDeliveryRate.store_id == sid))
        ).scalars().all()
        existing_map = {r.wilaya_code: r for r in existing_rows}
        for wcode in ALGERIA_WILAYAS:
            h_fee, d_fee = get_company_wilaya_rate(code, wcode)
            if wcode in existing_map:
                existing_map[wcode].home_fee = h_fee
                existing_map[wcode].desk_fee = d_fee
            else:
                s.add(StoreDeliveryRate(store_id=sid, wilaya_code=wcode, home_fee=h_fee, desk_fee=d_fee))
        north_h, north_d = co["zone_rates"]["north"]
        st.delivery_fee = north_h
        st.default_desk_fee = north_d
        if not st.delivery_company:
            st.delivery_company = code
        await s.commit()
    zr = co["zone_rates"]
    text = (
        f"⚡✅ <b>تم تطبيق أسعار 58 ولاية تلقائياً بنجاح!</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🚚 <b>الشركة:</b> {co['emoji']} {co['name']}\n\n"
        f"✦ 🏙️ <b>الوسط (الجزائر، البليدة، بومرداس، تيبازة):</b>\n"
        f"   منزل: <b>{zr['center'][0]:g} دج</b> | مكتب: <b>{zr['center'][1]:g} دج</b>\n"
        f"✦ 🌊 <b>الشمال:</b>\n"
        f"   منزل: <b>{zr['north'][0]:g} دج</b> | مكتب: <b>{zr['north'][1]:g} دج</b>\n"
        f"✦ ⛰️ <b>الهضاب العليا:</b>\n"
        f"   منزل: <b>{zr['highlands'][0]:g} دج</b> | مكتب: <b>{zr['highlands'][1]:g} دج</b>\n"
        f"✦ 🌴 <b>الجنوب المتوسط:</b>\n"
        f"   منزل: <b>{zr['mid_south'][0]:g} دج</b> | مكتب: <b>{zr['mid_south'][1]:g} دج</b>\n"
        f"✦ 🏜️ <b>أقصى الجنوب (أدرار، تمنراست، إليزي، تندوف...):</b>\n"
        f"   منزل: <b>{zr['deep_south'][0]:g} دج</b> | مكتب: <b>{zr['deep_south'][1]:g} دج</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💡 <i>يمكنك تعديل سعر أي ولاية يدوياً في أي وقت من «💰 أسعار التوصيل (58 ولاية)».</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ تخصيص ولاية معيّنة", callback_data=f"st_delivery:{sid}")],
        [InlineKeyboardButton(text="↩️ رجوع لتفاصيل الشركة", callback_data=f"st_dc_view:{sid}:{code}")],
    ])
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer("⚡ تم تحديث 58 ولاية!", show_alert=True)


@seller_router.callback_query(F.data.startswith("st_dc_export:"))
async def seller_delivery_company_export_csv(cb: CallbackQuery):
    _, sid_str, code = cb.data.split(":", 2)
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    co = get_delivery_company(code)
    if not co:
        return await cb.answer("❌ الشركة غير موجودة.", show_alert=True)
    async with Session() as s:
        pending_rows = (
            await s.execute(
                select(Order, Product)
                .outerjoin(Product, Order.product_id == Product.id)
                .where(or_(Order.store_id == sid, Product.store_id == sid), Order.status == "pending")
                .order_by(Order.created_at.desc())
            )
        ).all()
        used_fallback = False
        rows = pending_rows
        if not rows:
            used_fallback = True
            rows = (
                await s.execute(
                    select(Order, Product)
                    .outerjoin(Product, Order.product_id == Product.id)
                    .where(or_(Order.store_id == sid, Product.store_id == sid))
                    .order_by(Order.created_at.desc())
                    .limit(100)
                )
            ).all()
    if not rows:
        return await cb.answer("📭 لا توجد طلبات في متجرك لتصديرها حالياً.", show_alert=True)
    await cb.answer("⏳ جاري تجهيز ملف الشحن...", show_alert=False)
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "Order_ID", "Transporteur", "Nom_Complet", "Telephone", "Wilaya_Code", "Wilaya",
        "Adresse_Commune", "Stop_Desk", "Produit", "Variante", "Quantite",
        "Prix_Produit", "Frais_Livraison", "Montant_COD_Total", "Remarque", "Statut",
    ])
    for o, p in rows:
        p_title = p.title if p else (o.product_title or "Produit")
        w_code = (o.buyer_wilaya or "").strip().zfill(2) if (o.buyer_wilaya or "").strip().isdigit() else ""
        w_name = ALGERIA_WILAYAS_FR.get(w_code, o.buyer_wilaya or "-")
        total_cod = float(o.price or 0.0) + float(o.delivery_fee or 0.0)
        is_desk = "OUI" if o.delivery_type == "desk" else "NON"
        writer.writerow([
            o.id,
            co["name"],
            csv_safe(o.buyer_name),
            csv_safe(o.buyer_phone),
            w_code or "-",
            csv_safe(w_name),
            csv_safe(o.buyer_address),
            is_desk,
            csv_safe(p_title),
            csv_safe(o.variation or "-"),
            str(o.quantity or 1),
            f"{float(o.price or 0.0):.0f}",
            f"{float(o.delivery_fee or 0.0):.0f}",
            f"{total_cod:.0f}",
            csv_safe(o.buyer_note or ""),
            o.status,
        ])
    csv_bytes = output.getvalue().encode("utf-8")
    scope_note = (
        f"آخر <b>{len(rows)}</b> طلب (لا توجد طلبات قيد الانتظار حالياً)"
        if used_fallback
        else f"<b>{len(rows)}</b> طلب قيد الانتظار (جاهز للشحن)"
    )
    caption = (
        f"📥✨ <b>ملف شحن جاهز لمنصة {co['emoji']} {co['name']}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✦ 📦 المحتوى: {scope_note}\n"
        f"✦ 🧾 يشمل: الاسم، الهاتف، كود الولاية، Stop Desk، المبلغ الإجمالي COD.\n"
        f"💡 <i>ارفع الملف مباشرة في لوحة تاجر {co['name']} (Excel / CSV Import).</i>"
    )
    await cb.message.answer_document(
        BufferedInputFile(csv_bytes, filename=f"{code}_shipping_store_{sid}.csv"),
        caption=caption,
    )


@seller_router.callback_query(F.data.startswith("st_dc_compare:"))
async def seller_delivery_companies_compare(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    text = (
        "📊✨ <b>مقارنة سريعة بين أفضل 5 شركات توصيل في الجزائر</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "🟡 <b>Yalidine Express</b>\n"
        "   ✦ التغطية: 58 ولاية | الشمال: 600–850 دج | Stop Desk: 350–500 دج\n"
        "   ✦ الأقوى في: <b>أكبر شبكة مكاتب Stop Desk وتتبع دقيق</b>\n\n"
        "🔵 <b>ZR Express</b>\n"
        "   ✦ التغطية: 58 ولاية | الشمال: 600–800 دج | Stop Desk: 400–500 دج\n"
        "   ✦ الأقوى في: <b>سرعة الشحن وتحويل COD وعقود الكميات</b>\n\n"
        "🟣 <b>Maystro Delivery</b>\n"
        "   ✦ التغطية: 50+ ولاية | الشمال: 600–800 دج | Stop Desk: 400–500 دج\n"
        "   ✦ الأقوى في: <b>التغليف والتخزين (Fulfillment) وتطبيق التاجر</b>\n\n"
        "🟠 <b>GuepEX Express</b>\n"
        "   ✦ التغطية: 58 ولاية | الشمال: ~600 دج | الجنوب: 850–1450 دج\n"
        "   ✦ الأقوى في: <b>أسعار اقتصادية + طرود ثقيلة + COD حتى 150 ألف دج</b>\n\n"
        "🟢 <b>Noest Express</b>\n"
        "   ✦ التغطية: 58 ولاية | الشمال: 600–800 دج | Stop Desk: 400–500 دج\n"
        "   ✦ الأقوى في: <b>مرونة الاشتراك ومحطات جهوية قوية (B2B و B2C)</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "💡 <i>نصيحة: معظم الشركات تحسب الوزن الحجمي عبر المعادلة (الطول × العرض × الارتفاع ÷ 5000) وتطبّق زيادة +50 إلى +100 دج لكل كغ إضافي بعد 5 كغ.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧮 افتح حاسبة الوزن الحجمي", callback_data=f"st_dc_calc:{sid}")],
        [InlineKeyboardButton(text="↩️ رجوع لقائمة الشركات", callback_data=f"st_deliv_co:{sid}")],
    ])
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_dc_calc:"))
async def seller_delivery_calc_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(dc_calc_sid=sid)
    await state.set_state(DeliveryCalcFSM.dims)
    text = (
        "🧮✨ <b>حاسبة الوزن الحجمي وتكلفة الشحن</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "أرسل أبعاد الطرد بالسنتيمتر <b>(الطول العرض الارتفاع)</b>، ويمكنك إضافة الوزن الحقيقي (كغ) ورقم الولاية اختيارياً:\n\n"
        "✦ مثال 1 (الأبعاد فقط): <code>40 30 20</code>\n"
        "✦ مثال 2 (الأبعاد + الوزن كغ): <code>40 30 20 6</code>\n"
        "✦ مثال 3 (الأبعاد + الوزن + كود الولاية): <code>40 30 20 6 31</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ إلغاء ورجوع", callback_data=f"st_deliv_co:{sid}")],
    ])
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@seller_router.message(DeliveryCalcFSM.dims)
async def seller_delivery_calc_compute(message: Message, state: FSMContext):
    data = await state.get_data()
    sid = int(data.get("dc_calc_sid") or 0)
    raw = (message.text or "").replace("x", " ").replace("X", " ").replace("×", " ").replace("*", " ").replace(",", " ")
    parts = [p for p in raw.split() if p]
    try:
        nums = [float(p) for p in parts]
        if len(nums) < 3 or any(n <= 0 for n in nums[:3]):
            raise ValueError
    except ValueError:
        return await message.answer(
            "❌ صيغة غير صحيحة.\nأرسل 3 أرقام موجبة للأبعاد بالسنتيمتر (الطول العرض الارتفاع)، مثال: <code>40 30 20</code>"
        )
    length, width, height = nums[0], nums[1], nums[2]
    real_kg = nums[3] if len(nums) >= 4 and nums[3] > 0 else 0.0
    w_code = ""
    if len(nums) >= 5:
        wc_int = int(nums[4])
        if 1 <= wc_int <= 58:
            w_code = str(wc_int).zfill(2)
    vol_kg = round((length * width * height) / 5000.0, 2)
    billable_kg = max(vol_kg, real_kg)
    extra_kg = max(0.0, math.ceil(billable_kg - 5.0)) if billable_kg > 5.0 else 0.0
    extra_north = int(extra_kg * 50)
    extra_south = int(extra_kg * 100)
    await state.clear()

    lines = [
        "🧮✨ <b>نتيجة حساب الوزن الحجمي والشحن</b>",
        "━━━━━━━━━━━━━━━",
        f"✦ 📐 <b>الأبعاد:</b> {length:g} × {width:g} × {height:g} سم",
        f"✦ 📦 <b>الوزن الحجمي:</b> <b>{vol_kg:g} كغ</b>",
    ]
    if real_kg > 0:
        lines.append(f"✦ ⚖️ <b>الوزن الحقيقي:</b> <b>{real_kg:g} كغ</b>")
    lines.append(f"✦ 🏷️ <b>الوزن المعتمد للفوترة:</b> <b>{billable_kg:g} كغ</b>")
    if extra_kg > 0:
        lines.append(
            f"✦ ⚠️ <b>زيادة فوق 5 كغ ({int(extra_kg)} كغ إضافي):</b>\n"
            f"   الشمال: <b>+{extra_north} دج</b> | الجنوب: <b>+{extra_south} دج</b>"
        )
    else:
        lines.append("✦ ✅ <b>ضمن الحد المجاني (≤ 5 كغ)</b> — بدون رسوم وزن إضافي!")

    if w_code:
        zone = get_wilaya_zone(w_code)
        extra_add = extra_south if zone == "deep_south" else extra_north
        lines.append(f"\n🗺️ <b>التكلفة التقديرية لولاية {wilaya_label(w_code, 'ar')}:</b>")
        for code, co in DELIVERY_COMPANIES.items():
            h, d = get_company_wilaya_rate(code, w_code)
            lines.append(
                f"   {co['emoji']} <b>{co['name']}:</b> منزل <b>{int(h + extra_add)} دج</b> | مكتب <b>{int(d + extra_add)} دج</b>"
            )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 حساب طرد آخر", callback_data=f"st_dc_calc:{sid}")],
        [InlineKeyboardButton(text="↩️ قائمة شركات التوصيل", callback_data=f"st_deliv_co:{sid}")],
    ])
    await message.answer("\n".join(lines), reply_markup=kb)


# ─── Store Settings & 58-Wilaya Delivery Rates & COD Deposit ───

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
        [InlineKeyboardButton(text=t(lang, "btn_delivery_companies"), callback_data=f"st_deliv_co:{store_id}")],
        [InlineKeyboardButton(text="🚚 أسعار التوصيل (58 ولاية)", callback_data=f"st_delivery:{store_id}")],
        [InlineKeyboardButton(text=t(lang, "btn_store_deposit"), callback_data=f"st_deposit:{store_id}")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{store_id}")],
    ])
    try:
        await cb.message.edit_text(t(lang, "settings_menu"), reply_markup=kb)
    except Exception:
        await cb.message.answer(t(lang, "settings_menu"), reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_deposit:"))
async def store_deposit_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        st = await s.get(Store, sid)
    if not st:
        return await cb.answer("Not found", show_alert=True)
    dep_amt = float(st.deposit_amount or 0.0)
    dep_thr = float(st.deposit_threshold or 0.0)
    status = (
        f"✅ مفعّل — طلب عربون <b>{dep_amt:g} {DEFAULT_CURRENCY}</b> للطلبات التي تفوق <b>{dep_thr:g} {DEFAULT_CURRENCY}</b>"
        if dep_amt > 0
        else "❌ معطّل (الدفع الكامل عند الاستلام بدون عربون)"
    )
    text = (
        f"💵 <b>إعدادات العربون (للطلبات الدفع عند الاستلام) — {esc(st.name)}</b>\n\n"
        f"📌 الحالة الحالية: {status}\n\n"
        f"💡 عند تفعيل العربون، سيُعرض للمشتري خيار إرسال صورة وصل العربون فور تأكيد الطلب لحمايتك من الطلبات غير الجادة."
    )
    rows = [
        [InlineKeyboardButton(text="✏️ تفعيل / تعديل قيمة العربون", callback_data=f"st_dep_set:{sid}")],
    ]
    if dep_amt > 0:
        rows.append([InlineKeyboardButton(text="🚫 إيقاف طلب العربون", callback_data=f"st_dep_off:{sid}")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"st_settings:{sid}")])
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_dep_set:"))
async def store_deposit_set_start(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(dep_sid=sid)
    await state.set_state(StoreDepositFSM.threshold)
    await cb.message.answer(
        f"💵 أرسل الحد الأدنى لقيمة الطلب الذي يتطلب عربوناً ({DEFAULT_CURRENCY})\n"
        f"مثال: <code>5000</code> (أو أرسل <code>0</code> لطلب عربون على كل الطلبات):"
    )
    await cb.answer()


@seller_router.message(StoreDepositFSM.threshold)
async def store_deposit_set_threshold(message: Message, state: FSMContext):
    thr = _parse_positive_float(message.text or "", allow_zero=True)
    if thr is None:
        return await message.answer("❌ يرجى إدخال رقم صحيح (مثال: 5000 أو 0).")
    await state.update_data(dep_threshold=thr)
    await state.set_state(StoreDepositFSM.amount)
    await message.answer(f"💰 أرسل مبلغ العربون المطلوب ({DEFAULT_CURRENCY}) — مثال: <code>500</code>:")


@seller_router.message(StoreDepositFSM.amount)
async def store_deposit_set_amount(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    amt = _parse_positive_float(message.text or "", allow_zero=False)
    if amt is None:
        return await message.answer("❌ يرجى إدخال مبلغ عربون صحيح أكبر من 0.")
    data = await state.get_data()
    sid = int(data.get("dep_sid") or 0)
    thr = float(data.get("dep_threshold") or 0.0)
    await state.clear()
    async with Session() as s:
        st = await s.get(Store, sid)
        if st and (st.owner_tg_id == message.from_user.id or message.from_user.id in ADMIN_IDS):
            st.deposit_threshold = thr
            st.deposit_amount = amt
            await s.commit()
    await message.answer(
        f"✅ تم تفعيل إعدادات العربون بنجاح!\n"
        f"💰 العربون: <b>{amt:g} {DEFAULT_CURRENCY}</b> للطلبات ≥ <b>{thr:g} {DEFAULT_CURRENCY}</b>.",
        reply_markup=back_kb(lang, f"st_deposit:{sid}"),
    )


@seller_router.callback_query(F.data.startswith("st_dep_off:"))
async def store_deposit_disable(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    async with Session() as s:
        st = await s.get(Store, sid)
        if st:
            st.deposit_amount = 0.0
            st.deposit_threshold = 0.0
            await s.commit()
    await cb.answer("🚫 تم إيقاف طلب العربون.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    with suppress(Exception):
        await cb.message.edit_text("🚫 تم إيقاف طلب العربون لهذا المتجر.", reply_markup=back_kb(lang, f"st_settings:{sid}"))


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
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(share_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        bio = io.BytesIO()
        img.save(bio, "PNG")
        bio.seek(0)
        photo = BufferedInputFile(bio.read(), filename=f"qr_{store.id}.png")
        await cb.message.answer_photo(photo=photo, caption=t(lang, "qr_caption", name=esc(store.name)))
    except Exception as e:
        logger.warning(f"QR generation fallback: {e}")
        await cb.message.answer(
            f"🔗 <b>{esc(store.name)}</b>\n<code>{esc(share_url)}</code>"
        )
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
    async with Session() as s:
        store = await s.get(Store, sid)
        pcount = (
            await s.execute(
                select(func.count(Product.id)).where(Product.store_id == sid, Product.is_deleted.is_(False))
            )
        ).scalar() or 0
        max_prods = store_max_products(store)
        if max_prods is not None and pcount >= max_prods:
            tier_lbl = store_tier_label(store, lang)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👑 ترقية الباقة الآن (Pro / VIP)", callback_data=f"st_vip:{sid}")],
                [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}")],
            ])
            await cb.message.answer(
                f"⚠️ <b>وصلت للحد الأقصى للمنتجات في باقتك ({tier_lbl})</b>\n\n"
                f"📦 عدد منتجاتك الحالي: <b>{pcount} / {max_prods}</b>\n\n"
                f"💡 رقّي متجرك إلى <b>⭐ Pro (50 منتج)</b> أو <b>👑 VIP (منتجات غير محدودة)</b> للاستمرار في الإضافة!",
                reply_markup=kb,
            )
            return await cb.answer()
        cats = (await s.execute(select(Category).order_by(Category.id.asc()))).scalars().all()
    await state.clear()
    await state.update_data(active_store_id=sid, category_id=None, category_name="-")
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
        auto_live = store_can_auto_approve(store)
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
        trust_badge, _tinfo = await get_buyer_trust_summary(
            s, order.buyer_tg_id, order.buyer_phone, lang, exclude_order_id=oid
        )
    p_title = esc(p.title if p else (order.product_title or "منتج محذوف"))
    p_curr = esc(p.currency if p else (order.product_currency or DEFAULT_CURRENCY))
    sid = order.store_id or (p.store_id if p else 0)
    sm = {
        "pending": t(lang, "status_pending"),
        "shipped": t(lang, "status_shipped"),
        "completed": t(lang, "status_completed"),
        "cancelled": t(lang, "status_cancelled"),
    }
    dtype_label = t(lang, "analytics_desk_lbl") if order.delivery_type == "desk" else t(lang, "analytics_home_lbl")
    extras = [f"🔢 الكمية: <b>{order.quantity or 1}</b>"]
    if order.buyer_wilaya:
        extras.append(f"🗺️ الولاية: <b>{esc(wilaya_label(order.buyer_wilaya, lang))}</b>")
    extras.append(f"🚚 طريقة التوصيل: {dtype_label}")
    extras.append(f"{t(lang, 'trust_label')}: <b>{trust_badge}</b>")
    if order.tracking_info:
        extras.append(f"🔎 معلومات التتبع: <code>{esc(order.tracking_info)}</code>")
    if order.deposit_proof:
        extras.append("💵 العربون: <b>✅ تم إرسال وصل العربون</b>")
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
    kb_rows = [
        [InlineKeyboardButton(text=t(lang, "status_pending"), callback_data=f"ord_st:{oid}:pending"),
         InlineKeyboardButton(text=t(lang, "status_shipped"), callback_data=f"ord_st:{oid}:shipped")],
        [InlineKeyboardButton(text=t(lang, "status_completed"), callback_data=f"ord_st:{oid}:completed"),
         InlineKeyboardButton(text=t(lang, "status_cancelled"), callback_data=f"ord_st:{oid}:cancelled")],
    ]
    if order.deposit_proof:
        kb_rows.append([InlineKeyboardButton(text="📸 عرض وصل العربون", callback_data=f"ord_view_dep:{oid}")])
    kb_rows.append([InlineKeyboardButton(text=t(lang, "btn_report_fake_order"), callback_data=f"ord_fake_rep:{oid}")])
    kb_rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=back_cb)])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=kb)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=kb)


@seller_router.callback_query(F.data.startswith("ord_view_dep:"))
async def seller_view_order_deposit(cb: CallbackQuery):
    oid = int(cb.data.split(":")[1])
    if not await is_order_seller(cb.from_user.id, oid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    async with Session() as s:
        order = await s.get(Order, oid)
    if not order or not order.deposit_proof:
        return await cb.answer("❌ لا يوجد وصل عربون لهذا الطلب.", show_alert=True)
    await cb.message.answer_photo(order.deposit_proof, caption=f"💵 وصل العربون للطلب <b>#{oid}</b>")
    await cb.answer()


@seller_router.callback_query(F.data.startswith("ord_fake_rep:"))
async def seller_report_fake_order(cb: CallbackQuery):
    oid = int(cb.data.split(":")[1])
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        order = (await s.execute(select(Order).where(Order.id == oid))).scalar_one_or_none()
        if not order:
            return await cb.answer("❌ الطلب غير موجود.", show_alert=True)
        if not (order.seller_tg_id == cb.from_user.id or cb.from_user.id in ADMIN_IDS):
            return await cb.answer("⛔ غير مصرح.", show_alert=True)
        trust_badge, _tinfo = await get_buyer_trust_summary(s, order.buyer_tg_id, order.buyer_phone, "ar")
        pnorm = _normalize_phone(order.buyer_phone)
        buyer_uid = int(order.buyer_tg_id or 0)
        rep = Report(
            reporter_tg_id=cb.from_user.id,
            target_type="fake_order",
            target_id=oid,
            reason=f"Fake order #{oid} | buyer_id={buyer_uid} | phone={order.buyer_phone}",
        )
        s.add(rep)
        await s.commit()

    admin_msg = (
        f"🚨 <b>بلاغ طلب وهمي من بائع!</b>\n\n"
        f"📦 رقم الطلب: <b>#{oid}</b>\n"
        f"👤 المشتري: {esc(order.buyer_name)}\n"
        f"🆔 معرّف تيليجرام: <code>{buyer_uid}</code>\n"
        f"📞 الهاتف: <code>{esc(order.buyer_phone)}</code>\n"
        f"🛡️ السجل: <b>{trust_badge}</b>\n"
        f"🏪 المبلّغ (البائع): <code>{cb.from_user.id}</code>"
    )
    bl_buttons = []
    if buyer_uid and pnorm:
        bl_buttons.append([InlineKeyboardButton(
            text="🚫 حظر الحساب + الرقم",
            callback_data=f"admin:bl_quick:{buyer_uid}:{pnorm}",
        )])
    if pnorm:
        bl_buttons.append([InlineKeyboardButton(
            text="📵 حظر الرقم فقط",
            callback_data=f"admin:bl_quick:0:{pnorm}",
        )])
    if buyer_uid:
        bl_buttons.append([InlineKeyboardButton(
            text="⛔ حظر الحساب فقط",
            callback_data=f"admin:bl_quick:{buyer_uid}:",
        )])
    bl_buttons.append([InlineKeyboardButton(text="✅ تجاهل", callback_data="admin:bl_dismiss")])
    kb = InlineKeyboardMarkup(inline_keyboard=bl_buttons)
    for aid in ADMIN_IDS:
        with suppress(Exception):
            await cb.bot.send_message(aid, admin_msg, reply_markup=kb)
    await cb.answer(t(lang, "fake_report_sent"), show_alert=True)


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
        store_dc_code = ""
        seller_tg_id = order.seller_tg_id
        if order.store_id:
            st_row = await s.get(Store, order.store_id)
            if st_row and st_row.delivery_company:
                store_dc_code = st_row.delivery_company
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
            dc_obj = get_delivery_company(store_dc_code) if new_status == "shipped" else None
            reply_kb = None
            if new_status == "shipped" and dc_obj:
                txt += f"\n\n🚚 <b>شركة التوصيل:</b> {dc_obj['emoji']} <b>{dc_obj['name']}</b>"
                reply_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"🔎 تتبع طردك عبر {dc_obj['name']}", url=dc_obj["tracking_url"])]
                ])
            if new_status == "shipped" and saved_tracking:
                txt += f"\n🔎 <b>رقم التتبع:</b> <code>{esc(saved_tracking)}</code>"
            await bot.send_message(buyer_tg_id, txt, reply_markup=reply_kb)
    if new_status == "completed":
        with suppress(Exception):
            await evaluate_user_badges(bot, buyer_tg_id, notify=True)
            if seller_tg_id:
                await evaluate_user_badges(bot, seller_tg_id, notify=True)
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
        dc_hint = ""
        async with Session() as s:
            ord_row = await s.get(Order, oid)
            if ord_row and ord_row.store_id:
                st_row = await s.get(Store, ord_row.store_id)
                if st_row and st_row.delivery_company:
                    dc_obj = get_delivery_company(st_row.delivery_company)
                    if dc_obj:
                        dc_hint = (
                            f"\n🚚 شركتك المعتمدة: {dc_obj['emoji']} <b>{dc_obj['name']}</b> "
                            f"(سيتم إرفاق اسمها ورابط التتبع تلقائياً للمشتري!)\n"
                        )
        await state.update_data(ship_oid=oid)
        await state.set_state(OrderShipFSM.tracking)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ تخطي بدون رقم تتبع", callback_data=f"ord_ship_skip:{oid}")],
        ])
        await cb.message.answer(
            f"🚚✨ <b>شحن الطلب #{oid}</b>\n"
            f"━━━━━━━━━━━━━━━{dc_hint}\n"
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
    ref_code = generate_pay_ref()
    await state.update_data(pad_pkg=pkg, pad_ref=ref_code)
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        u = await ensure_user(s, cb.from_user.id, lang)
        await s.commit()
        credits = float(u.ad_credits or 0.0)
        instr = await format_payment_instructions(s, lang, ref_code=ref_code, amount=price)
    chg_key, _ = await get_chargily_config()
    text = (
        f"⭐ <b>ترويج المنتج — {esc(pkg_info['label'])}</b>\n"
        f"💰 السعر: <b>{price:g} {DEFAULT_CURRENCY}</b>\n"
        f"💳 رصيد محفظتك الحالي: <b>{credits:g} {DEFAULT_CURRENCY}</b>\n\n"
        f"{instr}"
    )
    rows = []
    if credits >= price:
        rows.append([
            InlineKeyboardButton(
                text=f"💳 الدفع من المحفظة ({price:g} {DEFAULT_CURRENCY}) — تفعيل فوري ⚡",
                callback_data=f"pad_wallet_pay:{pkg}:{pid}",
            )
        ])
    if chg_key:
        rows.append([
            InlineKeyboardButton(
                text=t(lang, "btn_pay_chargily"),
                callback_data=f"chg_pay:product:{pid}:{pkg}",
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
        u = await ensure_user(s, uid, lang)
        s.add(WalletTransaction(
            user_tg_id=uid,
            tx_type="ad",
            amount=-round(price, 2),
            balance_after=float(u.ad_credits or 0.0),
            description=f"📢 إعلان مميز للمنتج #{pid} ({pkg_info['label']})",
        ))
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
    ref_code = str(data.get("pad_ref") or generate_pay_ref())
    if not (pid and sid and pkg) or not await is_product_owner(message.from_user.id, pid):
        await state.clear()
        return await message.answer("انتهت الجلسة، ابدأ من جديد.")
    proof = message.photo[-1].file_id
    uniq_id = message.photo[-1].file_unique_id
    price = float(AD_PACKAGES.get(pkg, AD_PACKAGES["basic"])["price"])
    async with Session() as s:
        if await is_duplicate_receipt(s, uniq_id):
            return await message.answer(t(lang, "dup_receipt_err"))
        areq = AdRequest(
            user_tg_id=message.from_user.id,
            ad_type="product",
            target_id=pid,
            package_name=pkg,
            price=price,
            payment_proof=proof,
            proof_unique_id=uniq_id,
            ref_code=ref_code,
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
    admin_text = (
        t(
            "ar",
            "admin_ad_req_view",
            user_id=message.from_user.id,
            package=esc(pkg),
            price=f"{price:g} {DEFAULT_CURRENCY}",
            type=f"product #{pid} ({esc(ptitle)})",
        )
        + f"\n🏷️ المرجع: <code>{esc(ref_code)}</code>"
    )
    await notify_admins(message.bot, admin_text, reply_markup=admin_kb, photo=proof)


@seller_router.message(ProductAdFSM.payment_proof, ~F.photo)
async def product_ad_receive_proof_invalid(message: Message):
    await message.answer("📸 أرسل صورة إثبات الدفع:")


# ─── Store Wallet Shortcut & Store Subscriptions (Free / Pro / VIP) ───

@seller_router.callback_query(F.data.startswith("st_wallet:"))
async def store_wallet_shortcut(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await view_wallet_for_user(cb.message, cb.from_user.id, back_cb=f"mngstore:{sid}")
    await cb.answer()


async def _render_store_plans_view(msg_obj: Message, uid: int, sid: int, state: FSMContext, edit: bool = True):
    lang = await get_lang(uid)
    st_data = await state.get_data()
    coupon_code = st_data.get("sub_coupon_code", "")
    coupon_pct = int(st_data.get("sub_coupon_pct", 0) or 0)
    async with Session() as s:
        st = await s.get(Store, sid)
        u = await ensure_user(s, uid, lang)
        plans = await get_dynamic_plans(s)
        await s.commit()
    if not st:
        return
    tier = effective_store_tier(st)
    exp = _store_expiry_dt(st)
    if tier in ("pro", "vip") and exp:
        grace_str = " (⏳ فترة سماح 48 ساعة)" if store_in_grace_period(st) else ""
        status_str = f"{store_tier_label(st, lang)} — صالح حتى <b>{exp.strftime('%Y-%m-%d')}</b>{grace_str}"
    else:
        status_str = "🆓 Free (الباقة المجانية)"
    coupon_line = f"\n🎟️ كوبون الخصم المطبق: <code>{esc(coupon_code)}</code> (<b>-{coupon_pct}%</b>)" if coupon_pct > 0 else ""

    p_pro = plans["pro_30"]
    p_vip30 = plans["vip_30"]
    p_vip90 = plans["vip_90"]

    text = (
        f"👑✨ <b>باقات الاشتراك — {esc(st.name)}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✦ 📌 <b>باقتك الحالية:</b> {status_str}\n"
        f"✦ 💳 <b>رصيد محفظتك:</b> <b>{float(u.ad_credits or 0):g} {DEFAULT_CURRENCY}</b>{coupon_line}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🆓 <b>Free (مجاني):</b>\n"
        f"   ✦ {MAX_STORES_FREE} متجر • {MAX_PRODUCTS_FREE} منتج • مراجعة يدوية\n\n"
        f"⭐ <b>Pro ({p_pro['price']:g} {DEFAULT_CURRENCY}/شهر):</b>\n"
        f"   ✦ {MAX_STORES_PRO} متاجر • {MAX_PRODUCTS_PRO} منتج • نشر مباشر ⚡ • إحصائيات كاملة\n\n"
        f"👑 <b>VIP ({p_vip30['price']:g} {DEFAULT_CURRENCY}/شهر):</b>\n"
        f"   ✦ {MAX_STORES_VIP} متاجر • منتجات غير محدودة ∞ • شارة التاج والتوثيق ✓\n"
        f"   ✦ أولوية الظهور + 🎁 هدية <b>{p_vip30['bonus']:g} {DEFAULT_CURRENCY}</b> رصيد إعلانات شهرياً!\n\n"
        f"💎 <b>VIP ربع سنوي (90 يوماً):</b>\n"
        f"   ✦ {p_vip90['price']:g} {DEFAULT_CURRENCY} + 🎁 <b>{p_vip90['bonus']:g} {DEFAULT_CURRENCY}</b> هدية!\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🛡️ <i>فترة سماح {SUB_GRACE_HOURS} ساعة بعد الانتهاء دون حذف أي منتج.</i>"
    )
    rows = []
    if not st.trial_used and tier == "free":
        rows.append([
            InlineKeyboardButton(
                text=f"🎁 تفعيل تجربة Pro المجانية ({TRIAL_DAYS} أيام)",
                callback_data=f"vip_trial:{sid}",
            )
        ])
    for key in ("pro_30", "vip_30", "vip_90"):
        info = plans[key]
        base_p = float(info["price"])
        final_p = max(100.0, round(base_p * (1.0 - coupon_pct / 100.0), 2)) if coupon_pct > 0 else base_p
        price_lbl = f"{final_p:g} {DEFAULT_CURRENCY}" + (f" (بدل {base_p:g})" if coupon_pct > 0 else "")
        rows.append([
            InlineKeyboardButton(
                text=f"{info['label']} — {price_lbl}",
                callback_data=f"vip_buy:{sid}:{key}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="🎟️ إدخال كود خصم اشتراك",
            callback_data=f"st_sub_coupon:{sid}",
        )
    ])
    ar_lbl = "♻️ التجديد التلقائي من المحفظة: مفعّل ✅" if st.auto_renew else "♻️ التجديد التلقائي من المحفظة: معطّل ❌"
    rows.append([InlineKeyboardButton(text=ar_lbl, callback_data=f"vip_autorenew:{sid}")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}")])
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=markup)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=markup)


@seller_router.callback_query(F.data.startswith("st_vip:"))
async def store_vip_menu(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await _render_store_plans_view(cb.message, cb.from_user.id, sid, state, edit=True)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("vip_trial:"))
async def store_vip_activate_trial(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    async with Session() as s:
        st = await s.get(Store, sid)
        if not st:
            return await cb.answer("❌ المتجر غير موجود.", show_alert=True)
        if st.trial_used:
            return await cb.answer("⚠️ تم استخدام التجربة المجانية لهذا المتجر مسبقاً.", show_alert=True)
        st.trial_used = True
        st.plan_tier = "pro"
        st.plan_expires_at = utcnow() + timedelta(days=TRIAL_DAYS)
        st.auto_approve = True
        st.expiry_reminded_3d = False
        st.expiry_reminded_1d = False
        until_str = st.plan_expires_at.strftime("%Y-%m-%d")
        await s.commit()
    await cb.answer(f"🎁 تم تفعيل تجربة Pro المجانية حتى {until_str}!", show_alert=True)
    await _render_store_plans_view(cb.message, cb.from_user.id, sid, state, edit=True)


@seller_router.callback_query(F.data.startswith("vip_autorenew:"))
async def store_vip_toggle_autorenew(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    async with Session() as s:
        st = await s.get(Store, sid)
        if not st:
            return await cb.answer("❌ المتجر غير موجود.", show_alert=True)
        st.auto_renew = not bool(st.auto_renew)
        new_val = st.auto_renew
        await s.commit()
    await cb.answer("♻️ تم تفعيل التجديد التلقائي من المحفظة." if new_val else "⏸️ تم إيقاف التجديد التلقائي.", show_alert=True)
    await _render_store_plans_view(cb.message, cb.from_user.id, sid, state, edit=True)


@seller_router.callback_query(F.data.startswith("st_sub_coupon:"))
async def store_sub_coupon_prompt(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(sub_coupon_sid=sid)
    await state.set_state(SubCouponApplyFSM.code)
    await cb.message.answer("🎟️ أرسل كود خصم الاشتراك الآن (أو /cancel للإلغاء):")
    await cb.answer()


@seller_router.message(SubCouponApplyFSM.code)
async def store_sub_coupon_apply(message: Message, state: FSMContext):
    uid = message.from_user.id
    data = await state.get_data()
    sid = int(data.get("sub_coupon_sid") or 0)
    code = (message.text or "").strip().upper()
    async with Session() as s:
        sc = (await s.execute(select(SubCoupon).where(SubCoupon.code == code))).scalar_one_or_none()
        if not sc or not sc.is_active or sc.used_count >= sc.max_uses or not (1 <= sc.discount_percent <= 95):
            return await message.answer("❌ كود الخصم غير صحيح أو منتهي الصلاحية. جرّب كوداً آخر أو أرسل /cancel:")
        pct = int(sc.discount_percent)
    await state.set_state(None)
    await state.update_data(sub_coupon_code=code, sub_coupon_pct=pct)
    await message.answer(f"🎉 تم تطبيق كود الخصم <code>{esc(code)}</code> بنسبة <b>-{pct}%</b>!")
    if sid:
        await _render_store_plans_view(message, uid, sid, state, edit=False)


@seller_router.callback_query(F.data.startswith("vip_buy:"))
async def store_vip_choose_payment(cb: CallbackQuery, state: FSMContext):
    _, sid_str, plan_key = cb.data.split(":")
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    st_data = await state.get_data()
    coupon_code = st_data.get("sub_coupon_code", "")
    coupon_pct = int(st_data.get("sub_coupon_pct", 0) or 0)
    ref_code = generate_pay_ref()

    async with Session() as s:
        plans = await get_dynamic_plans(s)
        plan = plans.get(plan_key)
        if not plan:
            return await cb.answer("❌ باقة غير صالحة.", show_alert=True)
        u = await ensure_user(s, cb.from_user.id, lang)
        await s.commit()
        credits = float(u.ad_credits or 0.0)
        base_price = float(plan["price"])
        price = max(100.0, round(base_price * (1.0 - coupon_pct / 100.0), 2)) if coupon_pct > 0 else base_price
        instr = await format_payment_instructions(s, lang, ref_code=ref_code, amount=price)

    await state.update_data(vip_ref=ref_code, vip_final_price=price)
    chg_key, _ = await get_chargily_config()
    bonus_line = f"\n🎁 هدية إعلانات مجانية: <b>+{float(plan.get('bonus', 0)):g} {DEFAULT_CURRENCY}</b>" if float(plan.get("bonus", 0)) > 0 else ""
    disc_line = f"\n🎟️ بعد خصم الكوبون <code>{esc(coupon_code)}</code> (-{coupon_pct}%): <b>{price:g} {DEFAULT_CURRENCY}</b>" if coupon_pct > 0 else f"\n💰 السعر: <b>{price:g} {DEFAULT_CURRENCY}</b>"
    text = (
        f"👑 <b>{esc(plan['label'])}</b>"
        f"{disc_line}{bonus_line}\n"
        f"💳 رصيد محفظتك الحالي: <b>{credits:g} {DEFAULT_CURRENCY}</b>\n\n"
        f"{instr}"
    )
    rows = []
    if credits >= price:
        rows.append([
            InlineKeyboardButton(
                text=f"💳 الدفع من المحفظة ({price:g} {DEFAULT_CURRENCY}) — تفعيل فوري ⚡",
                callback_data=f"vip_wallet:{sid}:{plan_key}",
            )
        ])
    if chg_key:
        rows.append([
            InlineKeyboardButton(
                text=t(lang, "btn_pay_chargily"),
                callback_data=f"chg_pay:store_vip:{sid}:{plan_key}",
            )
        ])
    rows.append([InlineKeyboardButton(text="📸 إرسال وصل دفع يدوي", callback_data=f"vip_proof:{sid}:{plan_key}")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"st_vip:{sid}")])
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("vip_wallet:"))
async def store_vip_wallet_pay(cb: CallbackQuery, state: FSMContext):
    _, sid_str, plan_key = cb.data.split(":")
    sid = int(sid_str)
    uid = cb.from_user.id
    if not await is_store_owner(uid, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(uid)
    st_data = await state.get_data()
    coupon_code = st_data.get("sub_coupon_code", "")
    coupon_pct = int(st_data.get("sub_coupon_pct", 0) or 0)

    async with Session() as s:
        plans = await get_dynamic_plans(s)
        plan = plans.get(plan_key)
        if not plan:
            return await cb.answer("❌ باقة غير صالحة.", show_alert=True)
        base_price = float(plan["price"])
        applied_sc = None
        if coupon_code and coupon_pct > 0:
            sc = (await s.execute(select(SubCoupon).where(SubCoupon.code == coupon_code))).scalar_one_or_none()
            if sc and sc.is_active and sc.used_count < sc.max_uses:
                applied_sc = sc
                coupon_pct = int(sc.discount_percent)
            else:
                coupon_pct = 0
        price = max(100.0, round(base_price * (1.0 - coupon_pct / 100.0), 2)) if coupon_pct > 0 else base_price

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
        u = await ensure_user(s, uid, lang)
        s.add(WalletTransaction(
            user_tg_id=uid,
            tx_type="subscription",
            amount=-round(price, 2),
            balance_after=float(u.ad_credits or 0.0),
            description=f"👑 اشتراك {plan['label']} لمتجر {st.name}",
            ref_code=coupon_code,
        ))
        if applied_sc:
            applied_sc.used_count += 1
            if applied_sc.used_count >= applied_sc.max_uses:
                applied_sc.is_active = False
        until_str, bonus, tier = await activate_store_plan(s, st, plan_key, user=u)
        st_name = st.name
        await s.commit()

    await state.clear()
    bonus_line = f"\n🎁 تم إضافة <b>+{bonus:g} {DEFAULT_CURRENCY}</b> هدية رصيد إعلانات إلى محفظتك!" if bonus > 0 else ""
    try:
        await cb.message.edit_text(
            f"👑 <b>مبروك! تم تفعيل باقة {tier.upper()} لمتجر {esc(st_name)} فوراً!</b>\n\n"
            f"💳 المخصوم: <b>{price:g} {DEFAULT_CURRENCY}</b>\n"
            f"📅 صالح حتى: <b>{until_str}</b>{bonus_line}",
            reply_markup=back_kb(lang, f"mngstore:{sid}"),
        )
    except Exception:
        await cb.message.answer(f"👑 تم تفعيل {tier.upper()} لمتجر {esc(st_name)} حتى {until_str}!{bonus_line}")
    await cb.answer("👑 تم التفعيل بنجاح!", show_alert=True)


@seller_router.callback_query(F.data.startswith("vip_proof:"))
async def store_vip_proof_prompt(cb: CallbackQuery, state: FSMContext):
    _, sid_str, plan_key = cb.data.split(":")
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid) or plan_key not in VIP_PLANS:
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(vip_sid=sid, vip_plan=plan_key)
    await state.set_state(StoreVipFSM.payment_proof)
    await cb.message.answer("📸 أرسل صورة وصل الدفع لتفعيل الاشتراك الآن (أو /cancel للإلغاء):")
    await cb.answer()


@seller_router.message(StoreVipFSM.payment_proof, F.photo)
async def store_vip_receive_proof(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    sid, plan_key = data.get("vip_sid"), data.get("vip_plan")
    ref_code = str(data.get("vip_ref") or generate_pay_ref())
    if not (sid and plan_key in VIP_PLANS) or not await is_store_owner(message.from_user.id, sid):
        await state.clear()
        return await message.answer("انتهت الجلسة، ابدأ من جديد.")
    proof = message.photo[-1].file_id
    uniq_id = message.photo[-1].file_unique_id
    async with Session() as s:
        if await is_duplicate_receipt(s, uniq_id):
            return await message.answer(t(lang, "dup_receipt_err"))
        plans = await get_dynamic_plans(s)
        plan = plans[plan_key]
        final_price = float(data.get("vip_final_price") or plan["price"])
        st = await s.get(Store, sid)
        st_name = st.name if st else f"#{sid}"
        areq = AdRequest(
            user_tg_id=message.from_user.id,
            ad_type="store_vip",
            target_id=sid,
            package_name=plan_key,
            price=final_price,
            payment_proof=proof,
            proof_unique_id=uniq_id,
            ref_code=ref_code,
            status="pending",
        )
        s.add(areq)
        await s.commit()
        await s.refresh(areq)
        areq_id = areq.id
    await state.clear()
    await message.answer(t(lang, "payment_proof_received"), reply_markup=await get_main_kb(message.from_user.id, lang))
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تأكيد وتفعيل الاشتراك", callback_data=f"admin:confirm_payment:{areq_id}"),
        InlineKeyboardButton(text="❌ رفض الطلب", callback_data=f"admin:reject_payment:{areq_id}"),
    ]])
    await notify_admins(
        message.bot,
        f"👑 <b>طلب اشتراك متجر جديد #{areq_id}</b>\n"
        f"🏷️ المرجع: <code>{esc(ref_code)}</code>\n"
        f"🏪 المتجر: <b>{esc(st_name)}</b> (#{sid})\n"
        f"👤 البائع: <code>{message.from_user.id}</code>\n"
        f"📦 الباقة: <b>{esc(plan['label'])}</b> — <b>{final_price:g} {DEFAULT_CURRENCY}</b>",
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
        with suppress(Exception):
            await evaluate_user_badges(cb.bot, owner_id, notify=True)
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


@seller_router.callback_query(F.data == "admin:gstats")
@seller_router.callback_query(F.data.startswith("admin:gstats:"))
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
            st = await s.get(Store, areq.target_id)
            if st:
                until_str, bonus, tier = await activate_store_plan(s, st, areq.package_name)
                b_line = f"\n🎁 تم إضافة <b>+{bonus:g} {DEFAULT_CURRENCY}</b> رصيد إعلانات هدية لمحفظتك!" if bonus > 0 else ""
                user_msg = (
                    f"👑 <b>مبروك! تم تأكيد وتفعيل باقة {tier.upper()} لمتجرك {esc(st.name)}!</b>\n"
                    f"📅 صالح حتى: <b>{until_str}</b>{b_line}"
                )
                admin_alert = f"👑 تم تفعيل {tier.upper()} للمتجر حتى {until_str}."
            else:
                user_msg = "👑 تم تأكيد اشتراك متجرك بنجاح."
                admin_alert = "👑 تم تفعيل الاشتراك."

        else:
            # wallet_topup
            u = await ensure_user(s, areq.user_tg_id, DEFAULT_LANG)
            await record_wallet_tx(
                s,
                u,
                float(areq.price),
                "topup",
                f"💳 شحن رصيد مؤكد من الإدارة (#{areq.id})",
                ref_code=areq.ref_code or "",
            )
            new_bal = float(u.ad_credits or 0.0)
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


# ─── Admin Blacklist & Buyer Trust Inspector ───

async def _render_admin_blacklist(msg_obj: Message, lang: str, page: int = 1, edit: bool = True):
    async with Session() as s:
        total = (await s.execute(select(func.count(BlacklistedEntry.id)))).scalar() or 0
        total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
        page = max(1, min(page, total_pages))
        entries = (
            await s.execute(
                select(BlacklistedEntry)
                .order_by(BlacklistedEntry.created_at.desc())
                .limit(ITEMS_PER_PAGE)
                .offset((page - 1) * ITEMS_PER_PAGE)
            )
        ).scalars().all()

    top_rows = [[
        InlineKeyboardButton(text=t(lang, "bl_btn_add"), callback_data="admin:bl_add"),
        InlineKeyboardButton(text=t(lang, "bl_btn_check"), callback_data="admin:bl_check"),
    ]]
    items: list[tuple[str, str]] = []
    for e in entries:
        parts = []
        if e.user_tg_id:
            parts.append(f"ID:{e.user_tg_id}")
        if e.phone_norm:
            parts.append(f"📞{e.phone_norm}")
        label = " | ".join(parts) or f"#{e.id}"
        if e.reason:
            label += f" ({e.reason[:20]})"
        items.append((f"🗑️ {label}", f"admin:bl_del:{e.id}:{page}"))

    text = t(lang, "bl_menu_title", count=total) if total > 0 else t(lang, "bl_empty")
    kb = build_sql_pagination_kb(
        items,
        page,
        total,
        "admin:bl_pg",
        lang,
        top_rows=top_rows,
        extra_buttons=[InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")],
    )
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=kb)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=kb)


@seller_router.callback_query(F.data == "admin:blacklist")
async def admin_blacklist_menu(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.clear()
    lang = await get_lang(cb.from_user.id)
    await _render_admin_blacklist(cb.message, lang, page=1, edit=True)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:bl_pg:"))
async def admin_blacklist_page(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    page = int(cb.data.split(":")[2])
    await _render_admin_blacklist(cb.message, lang, page=page, edit=True)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:bl_del:"))
async def admin_blacklist_delete(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    parts = cb.data.split(":")
    eid = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
    lang = await get_lang(cb.from_user.id)
    async with Session() as s:
        entry = await s.get(BlacklistedEntry, eid)
        if entry:
            await s.delete(entry)
            await s.commit()
    await cb.answer(t(lang, "bl_removed"), show_alert=True)
    await _render_admin_blacklist(cb.message, lang, page=page, edit=True)


def _parse_blacklist_target(raw: str) -> tuple[Optional[int], str]:
    """Parse admin input into (user_tg_id, phone_norm)."""
    tokens = [tok.strip() for tok in (raw or "").replace(",", " ").split() if tok.strip()]
    uid: Optional[int] = None
    pnorm = ""
    for tok in tokens:
        digits = re.sub(r"\D+", "", tok)
        if not digits:
            continue
        is_phone_like = (
            tok.startswith("+")
            or tok.startswith("0")
            or digits.startswith("00213")
            or (digits.startswith("213") and len(digits) == 12)
        )
        if is_phone_like and not pnorm:
            pnorm = _normalize_phone(tok)
        elif uid is None and digits.isdigit():
            uid = int(digits)
        elif not pnorm:
            pnorm = _normalize_phone(tok)
    return uid, pnorm


@seller_router.callback_query(F.data == "admin:bl_add")
async def admin_blacklist_add_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    await state.set_state(AdminBlacklistFSM.add_target)
    await cb.message.answer(t(lang, "bl_add_prompt"), reply_markup=back_kb(lang, "admin:blacklist"))
    await cb.answer()


@seller_router.message(AdminBlacklistFSM.add_target)
async def admin_blacklist_add_target(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    lang = await get_lang(message.from_user.id)
    uid, pnorm = _parse_blacklist_target(message.text or "")
    if not uid and not pnorm:
        return await message.answer(t(lang, "bl_add_prompt"))
    if uid and uid in ADMIN_IDS:
        return await message.answer("❌ لا يمكن حظر حساب أدمن.")
    await state.update_data(bl_uid=uid, bl_phone=pnorm)
    await state.set_state(AdminBlacklistFSM.add_reason)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_skip_note"), callback_data="admin:bl_skip_reason")],
        [InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="admin:blacklist")],
    ])
    await message.answer(t(lang, "bl_reason_prompt"), reply_markup=kb)


async def _commit_blacklist_entry(admin_id: int, uid: Optional[int], pnorm: str, reason: str) -> None:
    async with Session() as s:
        existing = await is_blacklisted(s, user_tg_id=uid, phone=pnorm)
        if existing:
            if uid and not existing.user_tg_id:
                existing.user_tg_id = uid
            if pnorm and not existing.phone_norm:
                existing.phone_norm = pnorm
            if reason:
                existing.reason = reason[:300]
        else:
            s.add(BlacklistedEntry(
                user_tg_id=uid,
                phone_norm=pnorm,
                reason=reason[:300],
                added_by=admin_id,
            ))
        await s.commit()


@seller_router.callback_query(F.data == "admin:bl_skip_reason")
async def admin_blacklist_skip_reason(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    data = await state.get_data()
    uid = data.get("bl_uid")
    pnorm = data.get("bl_phone", "")
    await state.clear()
    if uid or pnorm:
        await _commit_blacklist_entry(cb.from_user.id, uid, pnorm, "")
    await cb.answer(t(lang, "bl_added"), show_alert=True)
    await _render_admin_blacklist(cb.message, lang, page=1, edit=False)


@seller_router.message(AdminBlacklistFSM.add_reason)
async def admin_blacklist_add_reason(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    uid = data.get("bl_uid")
    pnorm = data.get("bl_phone", "")
    reason = (message.text or "").strip()[:300]
    await state.clear()
    if uid or pnorm:
        await _commit_blacklist_entry(message.from_user.id, uid, pnorm, reason)
    await message.answer(t(lang, "bl_added"))
    await _render_admin_blacklist(message, lang, page=1, edit=False)


@seller_router.callback_query(F.data == "admin:bl_check")
async def admin_blacklist_check_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    await state.set_state(AdminBlacklistFSM.check_target)
    await cb.message.answer(t(lang, "bl_check_prompt"), reply_markup=back_kb(lang, "admin:blacklist"))
    await cb.answer()


@seller_router.message(AdminBlacklistFSM.check_target)
async def admin_blacklist_check_run(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    lang = await get_lang(message.from_user.id)
    uid, pnorm = _parse_blacklist_target(message.text or "")
    if not uid and not pnorm:
        return await message.answer(t(lang, "bl_check_prompt"))
    await state.clear()
    async with Session() as s:
        badge, info = await get_buyer_trust_summary(s, uid, pnorm, lang)
    reason_line = f"\n📝 السبب: {esc(info['bl_reason'])}" if info["bl_reason"] else ""
    summary = (
        f"🔎 <b>نتيجة الفحص</b>\n\n"
        f"🆔 ID: <code>{uid or '-'}</code>\n"
        f"📞 الهاتف: <code>{pnorm or '-'}</code>\n"
        f"{t(lang, 'trust_label')}: <b>{badge}</b>{reason_line}\n\n"
        f"📊 السجل الكامل:\n"
        f"• الإجمالي: <b>{info['total']}</b>\n"
        f"• ✅ مكتملة: <b>{info['completed']}</b> | 🚚 مشحونة: <b>{info['shipped']}</b>\n"
        f"• ⏳ انتظار: <b>{info['pending']}</b> | ❌ ملغاة: <b>{info['cancelled']}</b> ({info['cancel_rate']:.1f}%)"
    )
    kb_rows = []
    if not info["blacklisted"]:
        kb_rows.append([InlineKeyboardButton(
            text="🚫 حظر الآن",
            callback_data=f"admin:bl_quick:{uid or 0}:{pnorm}",
        )])
    kb_rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="admin:blacklist")])
    await message.answer(summary, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


@seller_router.callback_query(F.data.startswith("admin:bl_quick:"))
async def admin_blacklist_quick_ban(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    parts = cb.data.split(":", 3)
    uid_val = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() and int(parts[2]) > 0 else None
    pnorm = parts[3] if len(parts) > 3 else ""
    if uid_val and uid_val in ADMIN_IDS:
        return await cb.answer("❌ لا يمكن حظر أدمن.", show_alert=True)
    if not uid_val and not pnorm:
        return await cb.answer("❌ بيانات غير صالحة.", show_alert=True)
    await _commit_blacklist_entry(cb.from_user.id, uid_val, pnorm, "بلاغ طلب وهمي")
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("🚫 تمت الإضافة إلى القائمة السوداء بنجاح!", show_alert=True)


@seller_router.callback_query(F.data == "admin:bl_dismiss")
async def admin_blacklist_dismiss(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("✅ تم تجاهل البلاغ.")


# ─── Admin Payment Methods, Chargily Pay v2 & Telegram Stars Panel ───

async def _render_admin_paymethods(msg_obj: Message, lang: str, edit: bool = True):
    async with Session() as s:
        methods = (
            await s.execute(select(PaymentMethod).order_by(PaymentMethod.sort_order.asc(), PaymentMethod.id.asc()))
        ).scalars().all()
    chg_key, chg_mode = await get_chargily_config()
    stars_on, stars_rate = await get_stars_config()

    chg_status = f"✅ مفعّل ({'🟢 Live' if chg_mode == 'live' else '🧪 Test'})" if chg_key else "❌ غير مفعّل"
    stars_status = f"✅ مفعّل (1 ⭐ = {stars_rate:g} {DEFAULT_CURRENCY})" if stars_on else f"❌ معطّل (1 ⭐ = {stars_rate:g} {DEFAULT_CURRENCY})"

    lines = [
        "💳 <b>إدارة طرق الدفع وبوابات الشحن</b>\n",
        f"⚡ <b>Chargily Pay (EDAHABIA / CIB):</b> {chg_status}",
        f"⭐ <b>Telegram Stars (XTR):</b> {stars_status}\n",
        "📋 <b>طرق التحويل اليدوي:</b>",
    ]
    kb = []
    if not methods:
        lines.append("— لا توجد طرق تحويل يدوي مضافة بعد —")
    for pm in methods:
        st_ic = "✅" if pm.is_active else "⏸️"
        lines.append(f"{st_ic} <b>#{pm.id} {esc(pm.name)}</b>\n   <code>{esc(pm.details[:80])}</code>")
        kb.append([
            InlineKeyboardButton(text=f"{st_ic} {pm.name[:18]}", callback_data=f"admin:pm_toggle:{pm.id}"),
            InlineKeyboardButton(text="✏️ تعديل", callback_data=f"admin:pm_edit:{pm.id}"),
            InlineKeyboardButton(text="🗑️", callback_data=f"admin:pm_del:{pm.id}"),
        ])
    kb.append([InlineKeyboardButton(text="➕ إضافة طريقة دفع يدوية جديدة", callback_data="admin:pm_add")])
    kb.append([
        InlineKeyboardButton(text="⚡ مفتاح Chargily API", callback_data="admin:chg_cfg"),
        InlineKeyboardButton(text=f"🔄 وضع Chargily ({chg_mode.upper()})", callback_data="admin:chg_mode"),
    ])
    if chg_key:
        kb.append([InlineKeyboardButton(text="🗑️ إزالة مفتاح Chargily", callback_data="admin:chg_clear")])
    kb.append([
        InlineKeyboardButton(text=f"⭐ نجوم تيليجرام: {'إيقاف' if stars_on else 'تفعيل'}", callback_data="admin:stars_toggle"),
        InlineKeyboardButton(text="💱 سعر النجمة (دج)", callback_data="admin:stars_cfg"),
    ])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")])
    text = "\n".join(lines)[:4000]
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=markup)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=markup)


@seller_router.callback_query(F.data == "admin:paymethods")
async def admin_paymethods_menu(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.clear()
    await _render_admin_paymethods(cb.message, await get_lang(cb.from_user.id), edit=True)
    await cb.answer()


@seller_router.callback_query(F.data == "admin:pm_add")
async def admin_pm_add_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.set_state(AdminPayMethodFSM.add_name)
    await cb.message.answer("💳 أرسل اسم طريقة الدفع الجديدة (مثال: <code>BaridiMob</code> أو <code>Wise</code> أو <code>USDT TRC20</code>):")
    await cb.answer()


@seller_router.message(AdminPayMethodFSM.add_name)
async def admin_pm_add_name(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    name = (message.text or "").strip()[:80]
    if not name:
        return await message.answer("❌ يرجى إدخال اسم صحيح.")
    await state.update_data(pm_name=name)
    await state.set_state(AdminPayMethodFSM.add_details)
    await message.answer(f"📝 أرسل تفاصيل/بيانات الدفع لـ <b>{esc(name)}</b> (مثل رقم RIP أو الحساب واسم المستلم):")


@seller_router.message(AdminPayMethodFSM.add_details)
async def admin_pm_add_details(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    details = (message.text or "").strip()[:1000]
    if not details:
        return await message.answer("❌ يرجى إدخال التفاصيل.")
    data = await state.get_data()
    name = str(data.get("pm_name", "Payment"))
    await state.clear()
    async with Session() as s:
        s.add(PaymentMethod(name=name, details=details, is_active=True, sort_order=10))
        await s.commit()
    await message.answer(f"✅ تمت إضافة طريقة الدفع <b>{esc(name)}</b> بنجاح!")
    await _render_admin_paymethods(message, await get_lang(message.from_user.id), edit=False)


@seller_router.callback_query(F.data.startswith("admin:pm_toggle:"))
async def admin_pm_toggle(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    pm_id = int(cb.data.split(":")[2])
    async with Session() as s:
        pm = await s.get(PaymentMethod, pm_id)
        if not pm:
            return await cb.answer("❌ غير موجود.", show_alert=True)
        pm.is_active = not bool(pm.is_active)
        await s.commit()
    await cb.answer("✅ تم تحديث الحالة.")
    await _render_admin_paymethods(cb.message, await get_lang(cb.from_user.id), edit=True)


@seller_router.callback_query(F.data.startswith("admin:pm_edit:"))
async def admin_pm_edit_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    pm_id = int(cb.data.split(":")[2])
    await state.update_data(edit_pm_id=pm_id)
    await state.set_state(AdminPayMethodFSM.edit_details)
    await cb.message.answer(f"✏️ أرسل التفاصيل الجديدة لطريقة الدفع #{pm_id} (أو /cancel للإلغاء):")
    await cb.answer()


@seller_router.message(AdminPayMethodFSM.edit_details)
async def admin_pm_edit_save(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    details = (message.text or "").strip()[:1000]
    if not details:
        return await message.answer("❌ يرجى إدخال تفاصيل صالحة.")
    data = await state.get_data()
    pm_id = int(data.get("edit_pm_id") or 0)
    await state.clear()
    async with Session() as s:
        pm = await s.get(PaymentMethod, pm_id)
        if pm:
            pm.details = details
            await s.commit()
    await message.answer("✅ تم تحديث تفاصيل طريقة الدفع.")
    await _render_admin_paymethods(message, await get_lang(message.from_user.id), edit=False)


@seller_router.callback_query(F.data.startswith("admin:pm_del:"))
async def admin_pm_delete(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    pm_id = int(cb.data.split(":")[2])
    async with Session() as s:
        pm = await s.get(PaymentMethod, pm_id)
        if pm:
            await s.delete(pm)
            await s.commit()
    await cb.answer("🗑️ تم الحذف.", show_alert=True)
    await _render_admin_paymethods(cb.message, await get_lang(cb.from_user.id), edit=True)


@seller_router.callback_query(F.data == "admin:chg_cfg")
async def admin_chargily_cfg_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.set_state(AdminPayMethodFSM.chargily_key)
    await cb.message.answer(
        "⚡ <b>إعداد Chargily Pay v2 (الذهبية / CIB)</b>\n\n"
        "أرسل مفتاح <b>Secret API Key</b> من لوحة تحكم Chargily Pay (مثال: <code>test_sk_...</code> أو <code>live_sk_...</code>):\n"
        "(سيُحفظ بشكل آمن في قاعدة البيانات)"
    )
    await cb.answer()


@seller_router.message(AdminPayMethodFSM.chargily_key)
async def admin_chargily_cfg_save(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    key = (message.text or "").strip()
    if len(key) < 10:
        return await message.answer("❌ المفتاح قصير جداً أو غير صالح. أعد الإرسال أو /cancel:")
    await state.clear()
    await set_setting("chargily_api_key", key)
    if key.startswith("live_"):
        await set_setting("chargily_mode", "live")
    elif key.startswith("test_"):
        await set_setting("chargily_mode", "test")
    with suppress(Exception):
        await message.delete()
    await message.answer("✅ تم حفظ مفتاح Chargily Pay بنجاح (وتم حذف الرسالة لحماية المفتاح).")
    await _render_admin_paymethods(message, await get_lang(message.from_user.id), edit=False)


@seller_router.callback_query(F.data == "admin:chg_mode")
async def admin_chargily_toggle_mode(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    _, mode = await get_chargily_config()
    new_mode = "live" if mode == "test" else "test"
    await set_setting("chargily_mode", new_mode)
    await cb.answer(f"🔄 تم التبديل إلى وضع {new_mode.upper()}.", show_alert=True)
    await _render_admin_paymethods(cb.message, await get_lang(cb.from_user.id), edit=True)


@seller_router.callback_query(F.data == "admin:chg_clear")
async def admin_chargily_clear(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await set_setting("chargily_api_key", "")
    await cb.answer("🗑️ تم إيقاف Chargily Pay وإزالة المفتاح.", show_alert=True)
    await _render_admin_paymethods(cb.message, await get_lang(cb.from_user.id), edit=True)


@seller_router.callback_query(F.data == "admin:stars_toggle")
async def admin_stars_toggle(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    enabled, _ = await get_stars_config()
    await set_setting("stars_enabled", "0" if enabled else "1")
    await cb.answer("⭐ تم تحديث حالة نجوم تيليجرام.", show_alert=True)
    await _render_admin_paymethods(cb.message, await get_lang(cb.from_user.id), edit=True)


@seller_router.callback_query(F.data == "admin:stars_cfg")
async def admin_stars_rate_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.set_state(AdminPayMethodFSM.stars_rate)
    await cb.message.answer(f"⭐ أرسل قيمة النجمة الواحدة بالدينار ({DEFAULT_CURRENCY}) — مثال: <code>5</code> (يعني 100 ⭐ = 500 {DEFAULT_CURRENCY}):")
    await cb.answer()


@seller_router.message(AdminPayMethodFSM.stars_rate)
async def admin_stars_rate_save(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    rate = _parse_positive_float(message.text or "", allow_zero=False)
    if rate is None or rate > 10000:
        return await message.answer("❌ يرجى إدخال رقم صحيح أكبر من 0.")
    await state.clear()
    await set_setting("stars_dzd_rate", str(rate))
    await message.answer(f"✅ تم ضبط سعر النجمة: <b>1 ⭐ = {rate:g} {DEFAULT_CURRENCY}</b>.")
    await _render_admin_paymethods(message, await get_lang(message.from_user.id), edit=False)


# ─── Admin Prepaid Recharge Vouchers Panel ───

async def _render_admin_vouchers(msg_obj: Message, lang: str, edit: bool = True):
    async with Session() as s:
        vouchers = (
            await s.execute(select(Voucher).order_by(Voucher.id.desc()).limit(15))
        ).scalars().all()
    lines = ["🎟️ <b>إدارة بطاقات وأكواد الشحن المسبقة (Vouchers)</b>\n"]
    kb = [
        [
            InlineKeyboardButton(text="⚡ توليد 1000 دج", callback_data="admin:vch_quick:1000"),
            InlineKeyboardButton(text="⚡ توليد 3000 دج", callback_data="admin:vch_quick:3000"),
            InlineKeyboardButton(text="⚡ توليد 5000 دج", callback_data="admin:vch_quick:5000"),
        ],
        [InlineKeyboardButton(text="➕ إنشاء كود مخصص", callback_data="admin:vch_add")],
    ]
    if not vouchers:
        lines.append("لا توجد أكواد شحن بعد.")
    for v in vouchers:
        ic = "✅" if (v.is_active and v.used_count < v.max_uses) else "🔒"
        lines.append(f"{ic} <code>{esc(v.code)}</code> — <b>{v.amount:g} {DEFAULT_CURRENCY}</b> ({v.used_count}/{v.max_uses})")
        kb.append([InlineKeyboardButton(text=f"🗑️ حذف {v.code}", callback_data=f"admin:vch_del:{v.id}")])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")])
    text = "\n".join(lines)[:4000]
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=markup)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=markup)


@seller_router.callback_query(F.data == "admin:vouchers")
async def admin_vouchers_menu(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.clear()
    await _render_admin_vouchers(cb.message, await get_lang(cb.from_user.id), edit=True)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:vch_quick:"))
async def admin_voucher_quick_gen(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    amt = float(cb.data.split(":")[2])
    code = f"MKT-{secrets.token_hex(4).upper()}"
    async with Session() as s:
        s.add(Voucher(code=code, amount=amt, max_uses=1, created_by=cb.from_user.id))
        await s.commit()
    await cb.message.answer(
        f"🎟️ <b>تم توليد كود شحن جديد!</b>\n\n"
        f"🔑 الكود: <code>{code}</code>\n"
        f"💰 القيمة: <b>{amt:g} {DEFAULT_CURRENCY}</b>\n"
        f"🔢 الاستخدام: مرة واحدة (1)"
    )
    await _render_admin_vouchers(cb.message, await get_lang(cb.from_user.id), edit=False)
    await cb.answer("✅ تم التوليد!")


@seller_router.callback_query(F.data == "admin:vch_add")
async def admin_voucher_add_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.set_state(AdminVoucherFSM.create_spec)
    await cb.message.answer(
        "🎟️ أرسل بيانات كود الشحن بالصيغة:\n"
        "<code>الكود المبلغ عدد_الاستخدامات</code>\n\n"
        "مثال: <code>RAMADAN500 500 50</code>\n"
        "أو اكتب <code>AUTO 2000 1</code> لتوليد كود عشوائي:"
    )
    await cb.answer()


@seller_router.message(AdminVoucherFSM.create_spec)
async def admin_voucher_add_save(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        return await message.answer("❌ الصيغة غير صحيحة. مثال: <code>VIP2026 1000 10</code>")
    raw_code = parts[0].upper()
    code = f"MKT-{secrets.token_hex(4).upper()}" if raw_code == "AUTO" else raw_code[:50]
    amt = _parse_positive_float(parts[1], allow_zero=False)
    max_uses = _parse_int_range(parts[2], 1, 100000) if len(parts) >= 3 else 1
    if amt is None or max_uses is None:
        return await message.answer("❌ تأكد من صحة المبلغ وعدد الاستخدامات.")
    async with Session() as s:
        exists = (await s.execute(select(Voucher.id).where(Voucher.code == code))).scalar_one_or_none()
        if exists:
            return await message.answer("⚠️ هذا الكود موجود مسبقاً، اختر اسماً آخر.")
        s.add(Voucher(code=code, amount=amt, max_uses=max_uses, created_by=message.from_user.id))
        await s.commit()
    await state.clear()
    await message.answer(f"✅ تم إنشاء الكود <code>{esc(code)}</code> بقيمة <b>{amt:g} {DEFAULT_CURRENCY}</b> ({max_uses} استخدام).")
    await _render_admin_vouchers(message, await get_lang(message.from_user.id), edit=False)


@seller_router.callback_query(F.data.startswith("admin:vch_del:"))
async def admin_voucher_delete(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    vid = int(cb.data.split(":")[2])
    async with Session() as s:
        v = await s.get(Voucher, vid)
        if v:
            await s.delete(v)
            await s.commit()
    await cb.answer("🗑️ تم حذف الكود.", show_alert=True)
    await _render_admin_vouchers(cb.message, await get_lang(cb.from_user.id), edit=True)


# ─── Admin Subscription Plans & Sub Coupons Panel ───

async def _render_admin_plans(msg_obj: Message, lang: str, edit: bool = True):
    async with Session() as s:
        plans = await get_dynamic_plans(s)
        sc_cnt = (await s.execute(select(func.count(SubCoupon.id)).where(SubCoupon.is_active.is_(True)))).scalar() or 0
        pro_cnt = (await s.execute(select(func.count(Store.id)).where(Store.plan_tier == "pro"))).scalar() or 0
        vip_cnt = (await s.execute(select(func.count(Store.id)).where(Store.plan_tier == "vip"))).scalar() or 0
    lines = [
        "👑 <b>إدارة باقات الاشتراك وكوبوناتها</b>\n",
        f"📊 المشتركون حالياً: ⭐ Pro: <b>{pro_cnt}</b> | 👑 VIP: <b>{vip_cnt}</b>\n",
    ]
    kb = []
    for key in ("pro_30", "vip_30", "vip_90"):
        info = plans[key]
        lines.append(
            f"• <b>{esc(info['label'])}</b>: <b>{info['price']:g} {DEFAULT_CURRENCY}</b>"
            + (f" | 🎁 هدية إعلانات: <b>{info['bonus']:g} {DEFAULT_CURRENCY}</b>" if info["tier"] == "vip" else "")
        )
        row = [InlineKeyboardButton(text=f"✏️ سعر {key}", callback_data=f"admin:plan_edit:price:{key}")]
        if info["tier"] == "vip":
            row.append(InlineKeyboardButton(text=f"🎁 هدية {key}", callback_data=f"admin:plan_edit:bonus:{key}"))
        kb.append(row)
    kb.append([InlineKeyboardButton(text=f"🎟️ كوبونات خصم الاشتراكات ({sc_cnt})", callback_data="admin:sub_coupons")])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin")])
    text = "\n".join(lines)
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=markup)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=markup)


@seller_router.callback_query(F.data == "admin:plans")
async def admin_plans_menu(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.clear()
    await _render_admin_plans(cb.message, await get_lang(cb.from_user.id), edit=True)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:plan_edit:"))
async def admin_plan_edit_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    _, _, field, plan_key = cb.data.split(":")
    if plan_key not in VIP_PLANS or field not in ("price", "bonus"):
        return await cb.answer("❌ غير صالح.", show_alert=True)
    await state.update_data(plan_edit_field=field, plan_edit_key=plan_key)
    await state.set_state(AdminPlanConfigFSM.set_value)
    lbl = "السعر الجديد" if field == "price" else "قيمة رصيد الإعلانات الهدية (أو 0 لإلغائه)"
    await cb.message.answer(f"✏️ أرسل {lbl} للباقة <b>{plan_key}</b> ({DEFAULT_CURRENCY}):")
    await cb.answer()


@seller_router.message(AdminPlanConfigFSM.set_value)
async def admin_plan_edit_save(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    field = data.get("plan_edit_field")
    plan_key = data.get("plan_edit_key")
    allow_zero = field == "bonus"
    val = _parse_positive_float(message.text or "", allow_zero=allow_zero)
    if val is None:
        return await message.answer("❌ يرجى إدخال رقم صحيح.")
    await state.clear()
    await set_setting(f"plan_{field}_{plan_key}", str(val))
    await message.answer(f"✅ تم تحديث {field} للباقة <b>{plan_key}</b> إلى <b>{val:g} {DEFAULT_CURRENCY}</b>.")
    await _render_admin_plans(message, await get_lang(message.from_user.id), edit=False)


async def _render_admin_sub_coupons(msg_obj: Message, lang: str, edit: bool = True):
    async with Session() as s:
        coupons = (await s.execute(select(SubCoupon).order_by(SubCoupon.id.desc()).limit(15))).scalars().all()
    lines = ["🎟️ <b>كوبونات خصم اشتراكات المتاجر (Pro / VIP)</b>\n"]
    kb = [[InlineKeyboardButton(text="➕ إنشاء كوبون اشتراك جديد", callback_data="admin:sc_add")]]
    if not coupons:
        lines.append("لا توجد كوبونات اشتراك بعد.")
    for sc in coupons:
        ic = "✅" if (sc.is_active and sc.used_count < sc.max_uses) else "🔒"
        lines.append(f"{ic} <code>{esc(sc.code)}</code> — خصم <b>{sc.discount_percent}%</b> ({sc.used_count}/{sc.max_uses})")
        kb.append([InlineKeyboardButton(text=f"🗑️ حذف {sc.code}", callback_data=f"admin:sc_del:{sc.id}")])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="admin:plans")])
    text = "\n".join(lines)[:4000]
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=markup)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=markup)


@seller_router.callback_query(F.data == "admin:sub_coupons")
async def admin_sub_coupons_menu(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.clear()
    await _render_admin_sub_coupons(cb.message, await get_lang(cb.from_user.id), edit=True)
    await cb.answer()


@seller_router.callback_query(F.data == "admin:sc_add")
async def admin_sub_coupon_add_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.set_state(AdminSubCouponFSM.create_spec)
    await cb.message.answer(
        "🎟️ أرسل بيانات كوبون الاشتراك بالصيغة:\n"
        "<code>الكود نسبة_الخصم عدد_الاستخدامات</code>\n\n"
        "مثال: <code>PRO30 30 100</code> (خصم 30% لـ 100 متجر):"
    )
    await cb.answer()


@seller_router.message(AdminSubCouponFSM.create_spec)
async def admin_sub_coupon_add_save(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        return await message.answer("❌ الصيغة غير صحيحة. مثال: <code>VIP25 25 50</code>")
    code = parts[0].upper()[:50]
    pct = _parse_int_range(parts[1], 1, 95)
    max_uses = _parse_int_range(parts[2], 1, 100000) if len(parts) >= 3 else 100
    if pct is None or max_uses is None:
        return await message.answer("❌ نسبة الخصم يجب أن تكون بين 1 و 95.")
    async with Session() as s:
        exists = (await s.execute(select(SubCoupon.id).where(SubCoupon.code == code))).scalar_one_or_none()
        if exists:
            return await message.answer("⚠️ هذا الكوبون موجود مسبقاً.")
        s.add(SubCoupon(code=code, discount_percent=pct, max_uses=max_uses))
        await s.commit()
    await state.clear()
    await message.answer(f"✅ تم إنشاء كوبون الاشتراك <code>{esc(code)}</code> بخصم <b>{pct}%</b> ({max_uses} استخدام).")
    await _render_admin_sub_coupons(message, await get_lang(message.from_user.id), edit=False)


@seller_router.callback_query(F.data.startswith("admin:sc_del:"))
async def admin_sub_coupon_delete(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    sc_id = int(cb.data.split(":")[2])
    async with Session() as s:
        sc = await s.get(SubCoupon, sc_id)
        if sc:
            await s.delete(sc)
            await s.commit()
    await cb.answer("🗑️ تم حذف الكوبون.", show_alert=True)
    await _render_admin_sub_coupons(cb.message, await get_lang(cb.from_user.id), edit=True)


# ════════════════════════════════════════════════════════════════════
# 8.5 SELLER WEBSITE CREATION STUDIO & DIRECT DEVELOPER CHAT
# ════════════════════════════════════════════════════════════════════

def _format_web_features_list(raw_codes: str) -> str:
    codes = [c.strip() for c in (raw_codes or "").split(",") if c.strip()]
    if not codes:
        return "لم يتم تحديد إضافات خاصة"
    labels = [WEBSITE_FEATURES.get(c, c) for c in codes]
    return "\n".join(f"   • {lbl}" for lbl in labels)


def _format_web_req_card(req: WebsiteRequest, msg_count: int = 0, for_dev: bool = False) -> str:
    pkg = WEBSITE_PACKAGES.get(req.package_code) or WEBSITE_PACKAGES["ecommerce"]
    st_lbl = WEBSITE_STATUS_LABELS.get(req.status, req.status)
    quote_block = ""
    if req.quoted_price and req.quoted_price > 0:
        days_part = f" | ⏱️ المدة: <b>{req.delivery_days} أيام</b>" if req.delivery_days else ""
        quote_block = f"\n✦ 💎 <b>عرض سعر المطور:</b> <b>{req.quoted_price:g} {DEFAULT_CURRENCY}</b>{days_part}"
    url_block = f"\n✦ 🌍 <b>رابط الموقع الجاهز:</b> {esc(req.live_url)}" if req.live_url else ""
    dev_meta = (
        f"\n✦ 👤 <b>البائع (ID):</b> <code>{req.seller_tg_id}</code>"
        if for_dev
        else ""
    )
    return (
        f"🌐✨ <b>طلب إنشاء موقع إلكتروني #{req.id}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✦ 🏪 <b>المتجر:</b> {esc(req.store_name)}{dev_meta}\n"
        f"✦ 📌 <b>الحالة:</b> {st_lbl}\n"
        f"✦ 📦 <b>الباقة:</b> {pkg['emoji']} <b>{pkg['title']}</b>\n"
        f"✦ 💰 <b>الميزانية المقترحة:</b> {esc(req.budget or '-')}\n"
        f"✦ 📞 <b>هاتف التواصل:</b> <code>{esc(req.contact_phone or '-')}</code>{quote_block}{url_block}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✨ <b>المميزات المطلوبة:</b>\n{_format_web_features_list(req.features)}\n\n"
        f"📝 <b>ملاحظات وتفاصيل الدومين/الألوان:</b>\n<i>{esc(req.notes or 'لا توجد ملاحظات إضافية')}</i>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💬 <b>عدد رسائل المحادثة:</b> {msg_count} | 📅 {req.created_at.strftime('%Y-%m-%d %H:%M')}"
    )


DEFAULT_DEVELOPER_USERNAME: Final[str] = "nafeaouadah"


async def _get_dev_username() -> str:
    raw = (await get_setting("developer_username", "")).strip()
    if raw == "__off__":
        return ""
    val = raw.lstrip("@")
    return val or DEFAULT_DEVELOPER_USERNAME


def _build_dev_dm_url(dev_user: str, prefill: str = "") -> str:
    clean = (dev_user or DEFAULT_DEVELOPER_USERNAME).strip().lstrip("@")
    if prefill:
        return f"https://t.me/{clean}?text={urllib.parse.quote(prefill)}"
    return f"https://t.me/{clean}"


async def _render_seller_web_hub(msg_obj: Message, uid: int, sid: int, lang: str, edit: bool = True):
    async with Session() as s:
        st = await s.get(Store, sid)
        reqs = (
            await s.execute(
                select(WebsiteRequest)
                .where(WebsiteRequest.store_id == sid, WebsiteRequest.seller_tg_id == uid)
                .order_by(WebsiteRequest.id.desc())
            )
        ).scalars().all()
    if not st:
        return
    dev_user = await _get_dev_username()
    pkg_lines = []
    for p in WEBSITE_PACKAGES.values():
        pkg_lines.append(
            f"{p['emoji']} <b>{p['title']}</b>\n"
            f"   ✦ {p['price_hint']} • ⏱️ {p['days_hint']}\n"
            f"   <i>{p['desc']}</i>"
        )
    active_reqs = [r for r in reqs if r.status in ("pending", "negotiating", "in_progress")]
    latest_active = active_reqs[0] if active_reqs else None
    dev_mention = f" (@{dev_user})" if dev_user else ""
    text = (
        f"🌐✨ <b>استوديو إنشاء المواقع الإلكترونية — {esc(st.name)}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"امتلك <b>موقعاً إلكترونياً احترافياً خاصاً بمتجرك</b> يرفع ثقة زبائنك ويضاعف مبيعاتك، وتواصل مباشرة مع <b>المطور{dev_mention}</b> خطوة بخطوة! 🚀\n\n"
        + "\n\n".join(pkg_lines)
        + "\n━━━━━━━━━━━━━━━\n"
        + f"📊 <b>طلباتك الحالية:</b> {len(reqs)} (نشطة: {len(active_reqs)})"
    )
    rows = [
        [InlineKeyboardButton(text="🚀 طلب إنشاء موقع جديد الآن", callback_data=f"st_web_new:{sid}")],
    ]
    if dev_user:
        dm_prefill = (
            f"السلام عليكم، أستفسر بخصوص طلب إنشاء موقع إلكتروني #{latest_active.id} لمتجر {st.name}"
            if latest_active
            else f"السلام عليكم، أريد الاستفسار عن إنشاء موقع إلكتروني لمتجري ({st.name})"
        )
        rows.append([
            InlineKeyboardButton(
                text=f"💬 التحدث مع المطور مباشرة (@{dev_user})",
                url=_build_dev_dm_url(dev_user, dm_prefill),
            )
        ])
    if reqs:
        rows.append([
            InlineKeyboardButton(
                text=f"📋 طلباتي السابقة ({len(reqs)})",
                callback_data=f"st_web_list:{sid}",
            )
        ])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"mngstore:{sid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=kb)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=kb)


@seller_router.callback_query(F.data.startswith("st_web_hub:"))
async def seller_web_hub(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    lang = await get_lang(cb.from_user.id)
    await _render_seller_web_hub(cb.message, cb.from_user.id, sid, lang, edit=True)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_web_new:"))
async def seller_web_new_start(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(web_sid=sid, web_feats=[])
    text = (
        "🚀✨ <b>طلب إنشاء موقع إلكتروني — الخطوة 1 من 5</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "اختر <b>نوع الموقع / الباقة</b> التي تناسب مشروعك:"
    )
    rows = []
    for code, p in WEBSITE_PACKAGES.items():
        rows.append([
            InlineKeyboardButton(
                text=f"{p['emoji']} {p['title']} ({p['price_hint']})",
                callback_data=f"st_web_pkg:{sid}:{code}",
            )
        ])
    rows.append([InlineKeyboardButton(text="↩️ إلغاء ورجوع", callback_data=f"st_web_hub:{sid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


def _build_web_features_kb(sid: int, selected: list[str]) -> InlineKeyboardMarkup:
    rows = []
    sel_set = set(selected)
    for fkey, flbl in WEBSITE_FEATURES.items():
        mark = "✅" if fkey in sel_set else "⬜"
        rows.append([
            InlineKeyboardButton(text=f"{mark} {flbl}", callback_data=f"st_web_feat:{sid}:{fkey}")
        ])
    rows.append([
        InlineKeyboardButton(
            text=f"➡️ التالي ({len(sel_set)} ميزة مختارة)",
            callback_data=f"st_web_feats_done:{sid}",
        )
    ])
    rows.append([InlineKeyboardButton(text="↩️ رجوع للباقات", callback_data=f"st_web_new:{sid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@seller_router.callback_query(F.data.startswith("st_web_pkg:"))
async def seller_web_pick_package(cb: CallbackQuery, state: FSMContext):
    _, sid_str, pkg_code = cb.data.split(":", 2)
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    pkg = WEBSITE_PACKAGES.get(pkg_code)
    if not pkg:
        return await cb.answer("❌ باقة غير صالحة.", show_alert=True)
    default_feats = ["wilayas58", "pixel"] if pkg_code == "landing" else ["wilayas58", "domain"]
    await state.update_data(web_sid=sid, web_pkg=pkg_code, web_feats=default_feats)
    text = (
        f"✨⚙️ <b>الخطوة 2 من 5 — اختر المميزات الإضافية</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📦 الباقة المختارة: {pkg['emoji']} <b>{pkg['title']}</b>\n\n"
        f"اضغط على أي ميزة لتحديدها أو إلغائها، ثم اضغط <b>«➡️ التالي»</b>:"
    )
    kb = _build_web_features_kb(sid, default_feats)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_web_feat:"))
async def seller_web_toggle_feature(cb: CallbackQuery, state: FSMContext):
    _, sid_str, fkey = cb.data.split(":", 2)
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    if fkey not in WEBSITE_FEATURES:
        return await cb.answer()
    data = await state.get_data()
    feats = list(data.get("web_feats") or [])
    if fkey in feats:
        feats.remove(fkey)
    else:
        feats.append(fkey)
    await state.update_data(web_sid=sid, web_feats=feats)
    with suppress(Exception):
        await cb.message.edit_reply_markup(reply_markup=_build_web_features_kb(sid, feats))
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_web_feats_done:"))
async def seller_web_choose_budget(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    text = (
        "💰✨ <b>الخطوة 3 من 5 — الميزانية التقريبية</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "اختر الميزانية التقريبية التي تناسبك ليقترح عليك المطور أفضل تصميم وحل ممكن:"
    )
    rows = [
        [InlineKeyboardButton(text=b, callback_data=f"st_web_bgt:{sid}:{idx}")]
        for idx, b in enumerate(WEBSITE_BUDGETS)
    ]
    rows.append([InlineKeyboardButton(text="↩️ إلغاء", callback_data=f"st_web_hub:{sid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_web_bgt:"))
async def seller_web_pick_budget(cb: CallbackQuery, state: FSMContext):
    _, sid_str, idx_str = cb.data.split(":", 2)
    sid = int(sid_str)
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    idx = int(idx_str)
    budget = WEBSITE_BUDGETS[idx] if 0 <= idx < len(WEBSITE_BUDGETS) else WEBSITE_BUDGETS[-1]
    await state.update_data(web_sid=sid, web_budget=budget)
    await state.set_state(WebsiteReqFSM.details)
    text = (
        "🎨✨ <b>الخطوة 4 من 5 — فكرة الموقع والألوان والدومين</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "أرسل رسالة واحدة تشرح فيها أي تفاصيل ترغب بها:\n"
        "✦ نوع منتجاتك أو نشاط متجرك\n"
        "✦ الألوان المفضّلة أو رابط موقع أعجبك تصميمه\n"
        "✦ اسم الدومين المقترح (مثال: <code>myshop.dz</code>)\n\n"
        "أو اضغط <b>تخطي</b> لمناقشة كل شيء مباشرة مع المطور 👇"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ تخطي (سأناقش التفاصيل مع المطور)", callback_data=f"st_web_skip_notes:{sid}")],
        [InlineKeyboardButton(text="✖️ إلغاء", callback_data=f"st_web_hub:{sid}")],
    ])
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


async def _ask_web_phone_step(target_msg: Message, uid: int, sid: int, state: FSMContext):
    saved_phone = ""
    async with Session() as s:
        st = await s.get(Store, sid)
        u = (await s.execute(select(User).where(User.tg_id == uid))).scalar_one_or_none()
        saved_phone = (st.contact_phone or st.contact_whatsapp if st else "") or (u.saved_phone if u else "")
    await state.update_data(web_saved_phone=saved_phone)
    await state.set_state(WebsiteReqFSM.phone)
    rows = []
    if saved_phone:
        rows.append([
            InlineKeyboardButton(
                text=f"✅ استخدام رقمي المحفوظ ({saved_phone})",
                callback_data=f"st_web_use_phone:{sid}",
            )
        ])
    rows.append([InlineKeyboardButton(text="⏭️ تواصل عبر تيليجرام فقط", callback_data=f"st_web_skip_phone:{sid}")])
    await target_msg.answer(
        "📞✨ <b>الخطوة 5 من 5 — رقم الهاتف / الواتساب</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "أرسل رقم هاتفك أو واتساب للتواصل السريع مع المطور، أو اختر من الأزرار أدناه:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@seller_router.callback_query(F.data.startswith("st_web_skip_notes:"))
async def seller_web_skip_notes(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(web_sid=sid, web_notes="")
    await _ask_web_phone_step(cb.message, cb.from_user.id, sid, state)
    await cb.answer()


@seller_router.message(WebsiteReqFSM.details)
async def seller_web_save_notes(message: Message, state: FSMContext):
    data = await state.get_data()
    sid = int(data.get("web_sid") or 0)
    notes = (message.text or message.caption or "").strip()[:1500]
    await state.update_data(web_notes=notes)
    await _ask_web_phone_step(message, message.from_user.id, sid, state)


async def _finalize_website_request(target_msg: Message, uid: int, state: FSMContext, phone: str):
    data = await state.get_data()
    await state.clear()
    sid = int(data.get("web_sid") or 0)
    pkg_code = data.get("web_pkg") or "ecommerce"
    feats = ",".join(data.get("web_feats") or [])
    budget = data.get("web_budget") or WEBSITE_BUDGETS[-1]
    notes = data.get("web_notes") or ""
    async with Session() as s:
        st = await s.get(Store, sid)
        st_name = st.name if st else f"Store #{sid}"
        req = WebsiteRequest(
            store_id=sid,
            seller_tg_id=uid,
            store_name=st_name[:120],
            package_code=pkg_code,
            features=feats,
            budget=budget[:80],
            notes=notes[:1500],
            contact_phone=(phone or "تيليجرام فقط")[:60],
            status="pending",
        )
        s.add(req)
        await s.commit()
        await s.refresh(req)
        req_id = req.id

    seller_card = (
        f"🎉✅ <b>تم إرسال طلب إنشاء موقعك بنجاح! (طلب #{req_id})</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        + _format_web_req_card(req, msg_count=0, for_dev=False)
        + "\n\n💬 <i>سيتواصل معك المطور قريباً هنا داخل البوت، ويمكنك بدء المحادثة معه الآن مباشرة 👇</i>"
    )
    dev_user = await _get_dev_username()
    pkg_info = WEBSITE_PACKAGES.get(pkg_code) or WEBSITE_PACKAGES["ecommerce"]
    seller_rows = []
    if dev_user:
        prefill = f"السلام عليكم، أرسلت طلب إنشاء موقع #{req_id} ({pkg_info['title']}) لمتجر {st_name}"
        seller_rows.append([
            InlineKeyboardButton(
                text=f"💬 التحدث مع المطور مباشرة (@{dev_user})",
                url=_build_dev_dm_url(dev_user, prefill),
            )
        ])
    seller_rows.append([InlineKeyboardButton(text="📩 إرسال رسالة داخل البوت", callback_data=f"st_web_chat:{req_id}")])
    seller_rows.append([InlineKeyboardButton(text="📋 عرض طلبي", callback_data=f"st_web_view:{req_id}")])
    seller_rows.append([InlineKeyboardButton(text="↩️ العودة لمتجري", callback_data=f"mngstore:{sid}")])
    await target_msg.answer(seller_card, reply_markup=InlineKeyboardMarkup(inline_keyboard=seller_rows))

    # Instant rich notification to Developer (ADMIN_IDS)
    dev_card = (
        f"🔔🌐 <b>طلب إنشاء موقع إلكتروني جديد #{req_id}!</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        + _format_web_req_card(req, msg_count=0, for_dev=True)
    )
    dev_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 التحدث / الرد على البائع", callback_data=f"admin:web_reply:{req_id}")],
        [InlineKeyboardButton(text="💰 إرسال عرض سعر ومدة", callback_data=f"admin:web_quote:{req_id}"),
         InlineKeyboardButton(text="🛠️ بدء التنفيذ", callback_data=f"admin:web_st:{req_id}:in_progress")],
        [InlineKeyboardButton(text="📋 فتح لوحة الطلب كاملة", callback_data=f"admin:web_view:{req_id}")],
    ])
    for aid in ADMIN_IDS:
        with suppress(Exception):
            await target_msg.bot.send_message(aid, dev_card, reply_markup=dev_kb)


@seller_router.callback_query(F.data.startswith("st_web_use_phone:"))
async def seller_web_use_saved_phone(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    phone = data.get("web_saved_phone") or "تيليجرام فقط"
    await _finalize_website_request(cb.message, cb.from_user.id, state, phone)
    await cb.answer("✅ تم إرسال الطلب!")


@seller_router.callback_query(F.data.startswith("st_web_skip_phone:"))
async def seller_web_skip_phone(cb: CallbackQuery, state: FSMContext):
    await _finalize_website_request(cb.message, cb.from_user.id, state, "تيليجرام فقط")
    await cb.answer("✅ تم إرسال الطلب!")


@seller_router.message(WebsiteReqFSM.phone)
async def seller_web_save_phone(message: Message, state: FSMContext):
    phone = (message.text or "").strip()[:60]
    await _finalize_website_request(message, message.from_user.id, state, phone)


@seller_router.callback_query(F.data.startswith("st_web_list:"))
async def seller_web_list(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    if not await is_store_owner(cb.from_user.id, sid):
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    async with Session() as s:
        reqs = (
            await s.execute(
                select(WebsiteRequest)
                .where(WebsiteRequest.store_id == sid, WebsiteRequest.seller_tg_id == cb.from_user.id)
                .order_by(WebsiteRequest.id.desc())
                .limit(20)
            )
        ).scalars().all()
    if not reqs:
        return await cb.answer("📭 لا توجد طلبات إنشاء موقع بعد.", show_alert=True)
    rows = []
    for r in reqs:
        pkg = WEBSITE_PACKAGES.get(r.package_code) or WEBSITE_PACKAGES["ecommerce"]
        st_lbl = WEBSITE_STATUS_LABELS.get(r.status, r.status)
        rows.append([
            InlineKeyboardButton(
                text=f"#{r.id} {pkg['emoji']} {st_lbl} — {r.created_at.strftime('%m-%d')}",
                callback_data=f"st_web_view:{r.id}",
            )
        ])
    rows.append([InlineKeyboardButton(text="🚀 طلب موقع جديد", callback_data=f"st_web_new:{sid}")])
    rows.append([InlineKeyboardButton(text="↩️ رجوع", callback_data=f"st_web_hub:{sid}")])
    text = "📋✨ <b>طلبات إنشاء المواقع الخاصة بمتجرك</b>\n━━━━━━━━━━━━━━━\nاختر طلباً لعرض تفاصيله ومحادثة المطور:"
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


async def _render_seller_web_view(msg_obj: Message, uid: int, req_id: int, edit: bool = True):
    async with Session() as s:
        req = await s.get(WebsiteRequest, req_id)
        if not req or (req.seller_tg_id != uid and uid not in ADMIN_IDS):
            return
        msg_cnt = (
            await s.execute(select(func.count(WebsiteMessage.id)).where(WebsiteMessage.request_id == req_id))
        ).scalar() or 0
    text = _format_web_req_card(req, msg_count=msg_cnt, for_dev=False)
    dev_user = await _get_dev_username()
    rows = []
    if req.live_url and req.live_url.startswith(("http://", "https://")):
        rows.append([InlineKeyboardButton(text="🌍 فتح موقعك الجاهز الآن", url=req.live_url)])
    if dev_user and req.status != "cancelled":
        prefill = f"السلام عليكم، أستفسر بخصوص طلب إنشاء موقع #{req.id} لمتجر {req.store_name}"
        rows.append([
            InlineKeyboardButton(
                text=f"💬 التحدث مع المطور مباشرة (@{dev_user})",
                url=_build_dev_dm_url(dev_user, prefill),
            )
        ])
    if req.status != "cancelled":
        rows.append([InlineKeyboardButton(text="📩 رسالة سريعة داخل البوت", callback_data=f"st_web_chat:{req.id}")])
    if msg_cnt > 0:
        rows.append([InlineKeyboardButton(text=f"📜 سجل المحادثة ({msg_cnt})", callback_data=f"st_web_hist:{req.id}")])
    if req.status == "pending":
        rows.append([InlineKeyboardButton(text="❌ إلغاء الطلب", callback_data=f"st_web_cancel:{req.id}")])
    rows.append([InlineKeyboardButton(text="↩️ رجوع لطلباتي", callback_data=f"st_web_list:{req.store_id}")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=kb, disable_web_page_preview=True)


@seller_router.callback_query(F.data.startswith("st_web_view:"))
async def seller_web_view(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    req_id = int(cb.data.split(":")[1])
    await _render_seller_web_view(cb.message, cb.from_user.id, req_id, edit=True)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("st_web_cancel:"))
async def seller_web_cancel(cb: CallbackQuery):
    req_id = int(cb.data.split(":")[1])
    async with Session() as s:
        req = await s.get(WebsiteRequest, req_id)
        if not req or req.seller_tg_id != cb.from_user.id:
            return await cb.answer("⛔ غير مصرح.", show_alert=True)
        if req.status != "pending":
            return await cb.answer("⚠️ لا يمكن إلغاء الطلب بعد بدء العمل عليه، تواصل مع المطور.", show_alert=True)
        req.status = "cancelled"
        req.updated_at = utcnow()
        await s.commit()
    await cb.answer("✅ تم إلغاء الطلب.", show_alert=True)
    await _render_seller_web_view(cb.message, cb.from_user.id, req_id, edit=True)


@seller_router.callback_query(F.data.startswith("st_web_chat:"))
async def seller_web_chat_start(cb: CallbackQuery, state: FSMContext):
    req_id = int(cb.data.split(":")[1])
    async with Session() as s:
        req = await s.get(WebsiteRequest, req_id)
    if not req or req.seller_tg_id != cb.from_user.id:
        return await cb.answer("⛔ غير مصرح.", show_alert=True)
    await state.update_data(web_chat_req_id=req_id)
    await state.set_state(WebsiteChatFSM.message)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ إنهاء / رجوع للطلب", callback_data=f"st_web_view:{req_id}")],
    ])
    await cb.message.answer(
        f"💬✨ <b>محادثة مباشرة مع المطور — طلب موقع #{req_id}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"أرسل رسالتك الآن (نص أو صورة لشعارك / مثال تصميم) وستصل فوراً للمطور 👇",
        reply_markup=kb,
    )
    await cb.answer()


@seller_router.message(WebsiteChatFSM.message)
async def seller_web_chat_send(message: Message, state: FSMContext):
    data = await state.get_data()
    req_id = int(data.get("web_chat_req_id") or 0)
    await state.clear()
    txt = (message.text or message.caption or "").strip()[:2000]
    photo_id = message.photo[-1].file_id if message.photo else ""
    if not txt and not photo_id:
        return await message.answer("❌ يرجى إرسال رسالة نصية أو صورة.")
    async with Session() as s:
        req = await s.get(WebsiteRequest, req_id)
        if not req or req.seller_tg_id != message.from_user.id:
            return await message.answer("⛔ الطلب غير موجود.")
        s.add(WebsiteMessage(
            request_id=req_id,
            sender_role="seller",
            sender_tg_id=message.from_user.id,
            text=txt,
            photo_file_id=photo_id,
        ))
        req.updated_at = utcnow()
        await s.commit()
        st_name = req.store_name

    # Forward instantly to Developer (ADMIN_IDS)
    dev_header = (
        f"💬🌐 <b>رسالة جديدة من البائع — طلب موقع #{req_id}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✦ 🏪 <b>المتجر:</b> {esc(st_name)}\n"
        f"✦ 👤 <b>البائع:</b> <code>{message.from_user.id}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{esc(txt) if txt else '📸 [صورة مرفقة]'}"
    )
    dev_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ ردّ على البائع الآن", callback_data=f"admin:web_reply:{req_id}")],
        [InlineKeyboardButton(text="📋 فتح الطلب", callback_data=f"admin:web_view:{req_id}")],
    ])
    for aid in ADMIN_IDS:
        with suppress(Exception):
            if photo_id:
                await message.bot.send_photo(aid, photo_id, caption=dev_header[:1000], reply_markup=dev_kb)
            else:
                await message.bot.send_message(aid, dev_header, reply_markup=dev_kb)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 إرسال رسالة أخرى للمطور", callback_data=f"st_web_chat:{req_id}")],
        [InlineKeyboardButton(text="📋 عرض الطلب", callback_data=f"st_web_view:{req_id}")],
    ])
    await message.answer("✅✨ تم إرسال رسالتك إلى المطور بنجاح! سيصلك الرد هنا فورياً.", reply_markup=kb)


@seller_router.callback_query(F.data.startswith("st_web_hist:"))
async def seller_web_chat_history(cb: CallbackQuery):
    req_id = int(cb.data.split(":")[1])
    async with Session() as s:
        req = await s.get(WebsiteRequest, req_id)
        if not req or (req.seller_tg_id != cb.from_user.id and cb.from_user.id not in ADMIN_IDS):
            return await cb.answer("⛔ غير مصرح.", show_alert=True)
        msgs = (
            await s.execute(
                select(WebsiteMessage)
                .where(WebsiteMessage.request_id == req_id)
                .order_by(WebsiteMessage.id.asc())
                .limit(30)
            )
        ).scalars().all()
    if not msgs:
        return await cb.answer("📭 لا توجد رسائل بعد.", show_alert=True)
    lines = [f"📜✨ <b>سجل المحادثة — طلب موقع #{req_id}</b>", "━━━━━━━━━━━━━━━"]
    for m in msgs:
        who = "👨‍💻 <b>المطور</b>" if m.sender_role == "developer" else "🏪 <b>البائع</b>"
        body = esc(m.text) if m.text else ""
        if m.photo_file_id:
            body = ("📸 [صورة] " + body).strip()
        lines.append(f"{who} <i>({m.created_at.strftime('%m-%d %H:%M')})</i>:\n{body}\n")
    back_cb = f"st_web_view:{req_id}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 إرسال رسالة", callback_data=f"st_web_chat:{req_id}")],
        [InlineKeyboardButton(text="↩️ رجوع للطلب", callback_data=back_cb)],
    ])
    full_txt = "\n".join(lines)[:3900]
    try:
        await cb.message.edit_text(full_txt, reply_markup=kb)
    except Exception:
        await cb.message.answer(full_txt, reply_markup=kb)
    await cb.answer()


# ─── Developer (Admin) Website Requests Management ───

async def _render_admin_webreqs(msg_obj: Message, lang: str, edit: bool = True):
    async with Session() as s:
        reqs = (
            await s.execute(select(WebsiteRequest).order_by(WebsiteRequest.id.desc()).limit(25))
        ).scalars().all()
    dev_user = await _get_dev_username()
    dev_lbl = f"@{dev_user}" if dev_user else "غير محدد"
    rows = []
    for r in reqs:
        pkg = WEBSITE_PACKAGES.get(r.package_code) or WEBSITE_PACKAGES["ecommerce"]
        st_lbl = WEBSITE_STATUS_LABELS.get(r.status, r.status)
        rows.append([
            InlineKeyboardButton(
                text=f"#{r.id} {pkg['emoji']} {r.store_name[:18]} | {st_lbl}",
                callback_data=f"admin:web_view:{r.id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text=f"⚙️ معرّف المطور ({dev_lbl})", callback_data="admin:web_devuser")
    ])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:admin")])
    text = (
        f"🌐✨ <b>إدارة طلبات إنشاء المواقع الإلكترونية (لوحة المطور)</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✦ 📊 إجمالي الطلبات: <b>{len(reqs)}</b>\n"
        f"✦ ✈️ معرّف التواصل المباشر: <code>{esc(dev_lbl)}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        + ("اضغط على أي طلب لمراسلة البائع أو تحديد السعر أو تسليم الموقع:" if reqs else "📭 لا توجد طلبات إنشاء مواقع حالياً.")
    )
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=kb)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=kb)


@seller_router.callback_query(F.data == "admin:webreqs")
async def admin_webreqs_list(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.clear()
    await _render_admin_webreqs(cb.message, await get_lang(cb.from_user.id), edit=True)
    await cb.answer()


@seller_router.callback_query(F.data == "admin:web_devuser")
async def admin_web_devuser_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.set_state(AdminWebDevFSM.dev_username)
    await cb.message.answer(
        "✈️ أرسل معرّف تيليجرام الخاص بك كمطور (بدون @ أو معه، مثال: <code>MyDevHandle</code>) ليظهر زر مراسلتك المباشرة للبائعين، أو أرسل <code>off</code> لإخفائه:"
    )
    await cb.answer()


@seller_router.message(AdminWebDevFSM.dev_username)
async def admin_web_devuser_save(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    val = (message.text or "").strip().lstrip("@")
    if val.lower() in ("off", "none", "0", "-"):
        await set_setting("developer_username", "__off__")
        await message.answer("✅ تم إخفاء زر المعرّف المباشر (المحادثة تبقى داخل البوت).")
    else:
        await set_setting("developer_username", val[:64])
        await message.answer(f"✅ تم حفظ معرّف المطور: <code>@{esc(val)}</code>")
    await _render_admin_webreqs(message, await get_lang(message.from_user.id), edit=False)


async def _render_admin_web_view(msg_obj: Message, req_id: int, edit: bool = True):
    async with Session() as s:
        req = await s.get(WebsiteRequest, req_id)
        if not req:
            return
        msg_cnt = (
            await s.execute(select(func.count(WebsiteMessage.id)).where(WebsiteMessage.request_id == req_id))
        ).scalar() or 0
    text = _format_web_req_card(req, msg_count=msg_cnt, for_dev=True)
    rows = [
        [InlineKeyboardButton(text="💬 الرد / محادثة البائع", callback_data=f"admin:web_reply:{req_id}")],
        [InlineKeyboardButton(text="💰 تحديد عرض السعر والمدة", callback_data=f"admin:web_quote:{req_id}"),
         InlineKeyboardButton(text="🌍 تسليم رابط الموقع", callback_data=f"admin:web_deliver:{req_id}")],
        [InlineKeyboardButton(text="💬 قيد النقاش", callback_data=f"admin:web_st:{req_id}:negotiating"),
         InlineKeyboardButton(text="🛠️ جاري التنفيذ", callback_data=f"admin:web_st:{req_id}:in_progress")],
        [InlineKeyboardButton(text="✅ مكتمل", callback_data=f"admin:web_st:{req_id}:completed"),
         InlineKeyboardButton(text="❌ ملغي", callback_data=f"admin:web_st:{req_id}:cancelled")],
    ]
    if msg_cnt > 0:
        rows.append([InlineKeyboardButton(text=f"📜 سجل المحادثة ({msg_cnt})", callback_data=f"admin:web_hist:{req_id}")])
    rows.append([InlineKeyboardButton(text="↩️ قائمة طلبات المواقع", callback_data="admin:webreqs")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if edit:
        try:
            await msg_obj.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            return
        except Exception:
            pass
    await msg_obj.answer(text, reply_markup=kb, disable_web_page_preview=True)


@seller_router.callback_query(F.data.startswith("admin:web_view:"))
async def admin_web_view(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    await state.clear()
    req_id = int(cb.data.split(":")[2])
    await _render_admin_web_view(cb.message, req_id, edit=True)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:web_hist:"))
async def admin_web_hist(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    req_id = int(cb.data.split(":")[2])
    async with Session() as s:
        msgs = (
            await s.execute(
                select(WebsiteMessage)
                .where(WebsiteMessage.request_id == req_id)
                .order_by(WebsiteMessage.id.asc())
                .limit(30)
            )
        ).scalars().all()
    if not msgs:
        return await cb.answer("📭 لا توجد رسائل بعد.", show_alert=True)
    lines = [f"📜✨ <b>سجل محادثة طلب الموقع #{req_id}</b>", "━━━━━━━━━━━━━━━"]
    for m in msgs:
        who = "👨‍💻 <b>أنت (المطور)</b>" if m.sender_role == "developer" else "🏪 <b>البائع</b>"
        body = esc(m.text) if m.text else ""
        if m.photo_file_id:
            body = ("📸 [صورة] " + body).strip()
        lines.append(f"{who} <i>({m.created_at.strftime('%m-%d %H:%M')})</i>:\n{body}\n")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 ردّ على البائع", callback_data=f"admin:web_reply:{req_id}")],
        [InlineKeyboardButton(text="↩️ رجوع للطلب", callback_data=f"admin:web_view:{req_id}")],
    ])
    try:
        await cb.message.edit_text("\n".join(lines)[:3900], reply_markup=kb)
    except Exception:
        await cb.message.answer("\n".join(lines)[:3900], reply_markup=kb)
    await cb.answer()


@seller_router.callback_query(F.data.startswith("admin:web_reply:"))
async def admin_web_reply_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    req_id = int(cb.data.split(":")[2])
    await state.update_data(dev_reply_req_id=req_id)
    await state.set_state(AdminWebDevFSM.reply)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ إلغاء", callback_data=f"admin:web_view:{req_id}")],
    ])
    await cb.message.answer(
        f"👨‍💻💬 <b>الرد على البائع — طلب موقع #{req_id}</b>\n"
        f"أرسل ردك الآن (نص أو صورة نموذج/تصميم) وسيصل للبائع فوراً:",
        reply_markup=kb,
    )
    await cb.answer()


@seller_router.message(AdminWebDevFSM.reply)
async def admin_web_reply_send(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    req_id = int(data.get("dev_reply_req_id") or 0)
    await state.clear()
    txt = (message.text or message.caption or "").strip()[:2000]
    photo_id = message.photo[-1].file_id if message.photo else ""
    if not txt and not photo_id:
        return await message.answer("❌ يرجى إرسال نص أو صورة.")
    async with Session() as s:
        req = await s.get(WebsiteRequest, req_id)
        if not req:
            return await message.answer("❌ الطلب غير موجود.")
        s.add(WebsiteMessage(
            request_id=req_id,
            sender_role="developer",
            sender_tg_id=message.from_user.id,
            text=txt,
            photo_file_id=photo_id,
        ))
        if req.status == "pending":
            req.status = "negotiating"
        req.updated_at = utcnow()
        seller_id = req.seller_tg_id
        await s.commit()

    dev_user = await _get_dev_username()
    seller_msg = (
        f"👨‍💻✨ <b>ردّ المطور على طلب موقعك #{req_id}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{esc(txt) if txt else '📸 [صورة مرفقة من المطور]'}"
    )
    s_kb_rows = []
    if dev_user:
        s_kb_rows.append([
            InlineKeyboardButton(
                text=f"💬 التحدث مع المطور مباشرة (@{dev_user})",
                url=_build_dev_dm_url(dev_user, f"السلام عليكم، بخصوص طلب الموقع #{req_id}"),
            )
        ])
    s_kb_rows.append([InlineKeyboardButton(text="↩️ ردّ داخل البوت", callback_data=f"st_web_chat:{req_id}")])
    s_kb_rows.append([InlineKeyboardButton(text="📋 عرض طلبي", callback_data=f"st_web_view:{req_id}")])
    seller_kb = InlineKeyboardMarkup(inline_keyboard=s_kb_rows)
    with suppress(Exception):
        if photo_id:
            await message.bot.send_photo(seller_id, photo_id, caption=seller_msg[:1000], reply_markup=seller_kb)
        else:
            await message.bot.send_message(seller_id, seller_msg, reply_markup=seller_kb)

    await message.answer(
        f"✅ تم إرسال ردّك إلى البائع (طلب #{req_id}).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 إرسال رسالة أخرى", callback_data=f"admin:web_reply:{req_id}")],
            [InlineKeyboardButton(text="📋 فتح الطلب", callback_data=f"admin:web_view:{req_id}")],
        ]),
    )


@seller_router.callback_query(F.data.startswith("admin:web_quote:"))
async def admin_web_quote_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    req_id = int(cb.data.split(":")[2])
    await state.update_data(dev_quote_req_id=req_id)
    await state.set_state(AdminWebDevFSM.quote)
    await cb.message.answer(
        f"💰✨ <b>إرسال عرض سعر — طلب موقع #{req_id}</b>\n"
        f"أرسل <b>السعر ({DEFAULT_CURRENCY})</b> و<b>مدة التسليم بالأيام</b> مفصولين بمسافة.\n"
        f"مثال: <code>25000 7</code>"
    )
    await cb.answer()


@seller_router.message(AdminWebDevFSM.quote)
async def admin_web_quote_save(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    req_id = int(data.get("dev_quote_req_id") or 0)
    parts = (message.text or "").strip().split()
    try:
        price = float(parts[0])
        days = int(parts[1]) if len(parts) >= 2 else 7
        if price <= 0 or days <= 0:
            raise ValueError
    except (ValueError, IndexError):
        return await message.answer("❌ صيغة غير صحيحة. مثال صحيح: <code>25000 7</code>")
    await state.clear()
    async with Session() as s:
        req = await s.get(WebsiteRequest, req_id)
        if not req:
            return await message.answer("❌ الطلب غير موجود.")
        req.quoted_price = price
        req.delivery_days = days
        if req.status == "pending":
            req.status = "negotiating"
        req.updated_at = utcnow()
        seller_id = req.seller_tg_id
        await s.commit()

    dev_user = await _get_dev_username()
    quote_msg = (
        f"💎✨ <b>عرض سعر رسمي من المطور — طلب موقع #{req_id}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✦ 💰 <b>التكلفة المقترحة:</b> <b>{price:g} {DEFAULT_CURRENCY}</b>\n"
        f"✦ ⏱️ <b>مدة التنفيذ والتسليم:</b> <b>{days} أيام</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💬 يمكنك مراسلة المطور مباشرة للتأكيد أو مناقشة أي تعديل 👇"
    )
    q_rows = []
    if dev_user:
        q_rows.append([
            InlineKeyboardButton(
                text=f"💬 التحدث مع المطور مباشرة (@{dev_user})",
                url=_build_dev_dm_url(dev_user, f"السلام عليكم، أوافق/أستفسر عن عرض السعر لطلب الموقع #{req_id}"),
            )
        ])
    q_rows.append([InlineKeyboardButton(text="📩 ردّ داخل البوت", callback_data=f"st_web_chat:{req_id}")])
    q_rows.append([InlineKeyboardButton(text="📋 تفاصيل الطلب", callback_data=f"st_web_view:{req_id}")])
    seller_kb = InlineKeyboardMarkup(inline_keyboard=q_rows)
    with suppress(Exception):
        await message.bot.send_message(seller_id, quote_msg, reply_markup=seller_kb)
    await message.answer(f"✅ تم إرسال عرض السعر ({price:g} {DEFAULT_CURRENCY} / {days} أيام) للبائع!")
    await _render_admin_web_view(message, req_id, edit=False)


@seller_router.callback_query(F.data.startswith("admin:web_deliver:"))
async def admin_web_deliver_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    req_id = int(cb.data.split(":")[2])
    await state.update_data(dev_deliver_req_id=req_id)
    await state.set_state(AdminWebDevFSM.deliver_url)
    await cb.message.answer(
        f"🌍✨ <b>تسليم الموقع الجاهز — طلب #{req_id}</b>\n"
        f"أرسل رابط الموقع النهائي (مثال: <code>https://mystore.dz</code>) وسيُغلق الطلب كمكتمل ويصل الرابط للبائع فوراً:"
    )
    await cb.answer()


@seller_router.message(AdminWebDevFSM.deliver_url)
async def admin_web_deliver_save(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    req_id = int(data.get("dev_deliver_req_id") or 0)
    url = (message.text or "").strip()[:300]
    if not url.startswith(("http://", "https://")):
        return await message.answer("❌ يرجى إرسال رابط صحيح يبدأ بـ <code>https://</code> أو <code>http://</code>")
    await state.clear()
    async with Session() as s:
        req = await s.get(WebsiteRequest, req_id)
        if not req:
            return await message.answer("❌ الطلب غير موجود.")
        req.live_url = url
        req.status = "completed"
        req.updated_at = utcnow()
        seller_id = req.seller_tg_id
        st_name = req.store_name
        await s.commit()

    dev_user = await _get_dev_username()
    delivery_msg = (
        f"🎉🌍 <b>مبارك لك! موقعك الإلكتروني جاهز ومُسلّم الآن</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✦ 🏪 <b>المتجر:</b> {esc(st_name)}\n"
        f"✦ 🧾 <b>رقم الطلب:</b> #{req_id}\n"
        f"✦ 🔗 <b>الرابط:</b> {esc(url)}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"نتمنى لك مبيعات موفّقة! يمكنك دائماً مراسلة المطور لأي دعم أو تحديث ✨"
    )
    d_rows = [[InlineKeyboardButton(text="🌍 فتح موقعك الآن", url=url)]]
    if dev_user:
        d_rows.append([
            InlineKeyboardButton(
                text=f"💬 التحدث مع المطور مباشرة (@{dev_user})",
                url=_build_dev_dm_url(dev_user, f"السلام عليكم، شكراً على تسليم الموقع للطلب #{req_id}"),
            )
        ])
    else:
        d_rows.append([InlineKeyboardButton(text="💬 مراسلة المطور", callback_data=f"st_web_chat:{req_id}")])
    seller_kb = InlineKeyboardMarkup(inline_keyboard=d_rows)
    with suppress(Exception):
        await message.bot.send_message(seller_id, delivery_msg, reply_markup=seller_kb, disable_web_page_preview=True)
    await message.answer(f"🎉 تم تسليم الموقع وإشعار البائع بنجاح!")
    await _render_admin_web_view(message, req_id, edit=False)


@seller_router.callback_query(F.data.startswith("admin:web_st:"))
async def admin_web_change_status(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("غير مصرح", show_alert=True)
    _, _, req_id_str, new_st = cb.data.split(":", 3)
    req_id = int(req_id_str)
    if new_st not in WEBSITE_STATUS_LABELS:
        return await cb.answer("❌ حالة غير صالحة.", show_alert=True)
    async with Session() as s:
        req = await s.get(WebsiteRequest, req_id)
        if not req:
            return await cb.answer("Not found", show_alert=True)
        req.status = new_st
        req.updated_at = utcnow()
        seller_id = req.seller_tg_id
        await s.commit()
    st_lbl = WEBSITE_STATUS_LABELS[new_st]
    dev_user = await _get_dev_username()
    st_rows = []
    if dev_user:
        st_rows.append([
            InlineKeyboardButton(
                text=f"💬 التحدث مع المطور مباشرة (@{dev_user})",
                url=_build_dev_dm_url(dev_user, f"السلام عليكم، بخصوص تحديث طلب الموقع #{req_id}"),
            )
        ])
    st_rows.append([InlineKeyboardButton(text="📋 عرض الطلب", callback_data=f"st_web_view:{req_id}")])
    with suppress(Exception):
        await cb.bot.send_message(
            seller_id,
            f"🔔🌐 <b>تحديث حالة طلب موقعك #{req_id}</b>\n━━━━━━━━━━━━━━━\n📌 الحالة الجديدة: <b>{st_lbl}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=st_rows),
        )
    await cb.answer(f"✅ تم تحديث الحالة إلى: {st_lbl}", show_alert=True)
    await _render_admin_web_view(cb.message, req_id, edit=True)


# ════════════════════════════════════════════════════════════════════
# 8.6 LEGENDARY BADGES, MISSIONS & LEADERBOARD ENGINE (SELLERS & BUYERS)
# ════════════════════════════════════════════════════════════════════

async def _compute_user_mission_progress(s, uid: int) -> tuple[dict[str, tuple[int, int, bool]], Optional[int]]:
    """Return {badge_code: (current_value, target_value, is_achieved)} and primary store_id."""
    u = (await s.execute(select(User).where(User.tg_id == uid))).scalar_one_or_none()
    stores = (await s.execute(select(Store).where(Store.owner_tg_id == uid).order_by(Store.id.asc()))).scalars().all()
    store_ids = [st.id for st in stores]
    primary_sid = store_ids[0] if store_ids else None

    # Seller metrics
    approved_prods = 0
    seller_done_orders = 0
    seller_followers = 0
    seller_rev_cnt = 0
    seller_rev_avg = 0.0
    seller_five_star_cnt = 0
    seller_promos = 0
    seller_flash_cnt = 0
    seller_wilayas_cnt = 0
    seller_views_total = 0
    seller_verified_or_pro = 0
    brand_steps = 0
    if store_ids:
        approved_prods = (
            await s.execute(
                select(func.count(Product.id)).where(
                    Product.store_id.in_(store_ids),
                    Product.status == "approved",
                    Product.is_deleted.is_(False),
                )
            )
        ).scalar() or 0
        seller_views_total = int(
            (
                await s.execute(
                    select(func.coalesce(func.sum(Product.views), 0)).where(
                        Product.store_id.in_(store_ids),
                        Product.is_deleted.is_(False),
                    )
                )
            ).scalar()
            or 0
        )
        seller_flash_cnt = (
            await s.execute(
                select(func.count(Product.id)).where(
                    Product.store_id.in_(store_ids),
                    Product.flash_sale_price.is_not(None),
                    Product.is_deleted.is_(False),
                )
            )
        ).scalar() or 0
        seller_promos = (
            await s.execute(select(func.count(PromoCode.id)).where(PromoCode.store_id.in_(store_ids)))
        ).scalar() or 0
        seller_wilayas_cnt = (
            await s.execute(
                select(func.count(func.distinct(StoreDeliveryRate.wilaya_code))).where(
                    StoreDeliveryRate.store_id.in_(store_ids)
                )
            )
        ).scalar() or 0
        seller_done_orders = (
            await s.execute(
                select(func.count(Order.id)).where(
                    or_(Order.seller_tg_id == uid, Order.store_id.in_(store_ids)),
                    Order.status == "completed",
                )
            )
        ).scalar() or 0
        seller_followers = (
            await s.execute(select(func.count(StoreFollower.id)).where(StoreFollower.store_id.in_(store_ids)))
        ).scalar() or 0
        rev_row = (
            await s.execute(
                select(func.count(Review.id), func.coalesce(func.avg(Review.rating), 0.0)).where(
                    Review.store_id.in_(store_ids)
                )
            )
        ).one()
        seller_rev_cnt = int(rev_row[0] or 0)
        seller_rev_avg = float(rev_row[1] or 0.0)
        seller_five_star_cnt = (
            await s.execute(
                select(func.count(Review.id)).where(Review.store_id.in_(store_ids), Review.rating == 5)
            )
        ).scalar() or 0
        web_req_cnt = (
            await s.execute(select(func.count(WebsiteRequest.id)).where(WebsiteRequest.seller_tg_id == uid))
        ).scalar() or 0
        for st in stores:
            steps = (
                (1 if (st.logo_file_id or "").strip() else 0)
                + (1 if (st.bio or "").strip() else 0)
                + (1 if (st.delivery_company or "").strip() else 0)
            )
            if steps > brand_steps:
                brand_steps = steps
            if st.verified or effective_store_tier(st) in ("pro", "vip"):
                seller_verified_or_pro = 1
        if web_req_cnt >= 1:
            seller_verified_or_pro = 1

    # Buyer metrics
    buyer_done = (
        await s.execute(
            select(func.count(Order.id)).where(Order.buyer_tg_id == uid, Order.status == "completed")
        )
    ).scalar() or 0
    buyer_cancelled = (
        await s.execute(
            select(func.count(Order.id)).where(Order.buyer_tg_id == uid, Order.status == "cancelled")
        )
    ).scalar() or 0
    buyer_distinct_stores = (
        await s.execute(
            select(func.count(func.distinct(Order.store_id))).where(
                Order.buyer_tg_id == uid,
                Order.status == "completed",
            )
        )
    ).scalar() or 0
    buyer_total_spent = int(
        (
            await s.execute(
                select(func.coalesce(func.sum(Order.price * Order.quantity), 0.0)).where(
                    Order.buyer_tg_id == uid,
                    Order.status == "completed",
                )
            )
        ).scalar()
        or 0
    )
    buyer_favs = (
        await s.execute(select(func.count(Favorite.id)).where(Favorite.user_tg_id == uid))
    ).scalar() or 0
    buyer_follows = (
        await s.execute(select(func.count(StoreFollower.id)).where(StoreFollower.user_tg_id == uid))
    ).scalar() or 0
    buyer_reviews = (
        await s.execute(select(func.count(Review.id)).where(Review.buyer_tg_id == uid))
    ).scalar() or 0
    profile_steps = 0
    if u:
        profile_steps = (
            (1 if (u.saved_name or "").strip() else 0)
            + (1 if (u.saved_phone or "").strip() else 0)
            + (1 if (u.saved_address or "").strip() else 0)
        )

    progress: dict[str, tuple[int, int, bool]] = {
        # Seller (16)
        "seller_starter": (min(1, approved_prods), 1, bool(store_ids and approved_prods >= 1)),
        "seller_brand": (brand_steps, 3, bool(store_ids and brand_steps >= 3)),
        "seller_first_sale": (min(1, seller_done_orders), 1, seller_done_orders >= 1),
        "seller_promo_master": (min(1, seller_promos), 1, seller_promos >= 1),
        "seller_flash_king": (min(1, seller_flash_cnt), 1, seller_flash_cnt >= 1),
        "seller_58_wilayas": (min(30, seller_wilayas_cnt), 30, seller_wilayas_cnt >= 30),
        "seller_catalog": (min(10, approved_prods), 10, approved_prods >= 10),
        "seller_mega_catalog": (min(30, approved_prods), 30, approved_prods >= 30),
        "seller_views_star": (min(500, seller_views_total), 500, seller_views_total >= 500),
        "seller_pro": (min(10, seller_done_orders), 10, seller_done_orders >= 10),
        "seller_loved": (
            min(5, seller_rev_cnt),
            5,
            seller_rev_cnt >= 5 and seller_rev_avg >= 4.5,
        ),
        "seller_five_star": (min(10, seller_five_star_cnt), 10, seller_five_star_cnt >= 10),
        "seller_influencer": (min(25, seller_followers), 25, seller_followers >= 25),
        "seller_verified_pro": (seller_verified_or_pro, 1, seller_verified_or_pro >= 1),
        "seller_master": (min(25, seller_done_orders), 25, seller_done_orders >= 25),
        "seller_legend": (min(50, seller_done_orders), 50, seller_done_orders >= 50),
        # Buyer (16)
        "buyer_complete": (profile_steps, 3, profile_steps >= 3),
        "buyer_first": (min(1, buyer_done), 1, buyer_done >= 1),
        "buyer_explorer": (min(5, buyer_favs), 5, buyer_favs >= 5),
        "buyer_collector": (min(20, buyer_favs), 20, buyer_favs >= 20),
        "buyer_fan": (min(3, buyer_follows), 3, buyer_follows >= 3),
        "buyer_superfan": (min(10, buyer_follows), 10, buyer_follows >= 10),
        "buyer_multi_store": (min(3, buyer_distinct_stores), 3, buyer_distinct_stores >= 3),
        "buyer_critic": (min(3, buyer_reviews), 3, buyer_reviews >= 3),
        "buyer_super_critic": (min(10, buyer_reviews), 10, buyer_reviews >= 10),
        "buyer_trusted": (
            min(3, buyer_done) if buyer_cancelled == 0 else 0,
            3,
            buyer_done >= 3 and buyer_cancelled == 0,
        ),
        "buyer_loyal": (min(5, buyer_done), 5, buyer_done >= 5),
        "buyer_patron": (min(10, buyer_done), 10, buyer_done >= 10),
        "buyer_variety": (min(7, buyer_distinct_stores), 7, buyer_distinct_stores >= 7),
        "buyer_big_spender": (min(50000, buyer_total_spent), 50000, buyer_total_spent >= 50000),
        "buyer_vip": (min(20, buyer_done), 20, buyer_done >= 20),
        "buyer_emperor": (min(50, buyer_done), 50, buyer_done >= 50),
    }
    return progress, primary_sid


async def evaluate_user_badges(bot: Optional[Bot], uid: int, notify: bool = True) -> list[dict[str, Any]]:
    """Evaluate all 32 Seller & Buyer missions, unlock new badges, award DZD bonuses, and celebrate!"""
    if not uid:
        return []
    newly_unlocked: list[dict[str, Any]] = []
    async with Session() as s:
        u = await ensure_user(s, uid, DEFAULT_LANG)
        existing = set(
            (await s.execute(select(UserBadge.badge_code).where(UserBadge.user_tg_id == uid))).scalars().all()
        )
        progress, primary_sid = await _compute_user_mission_progress(s, uid)
        for code, meta in BADGE_CATALOG.items():
            if code in existing:
                continue
            _cur, _tgt, achieved = progress.get(code, (0, 1, False))
            if not achieved:
                continue
            s.add(
                UserBadge(
                    user_tg_id=uid,
                    badge_code=code,
                    role=meta["role"],
                    store_id=primary_sid if meta["role"] == "seller" else None,
                )
            )
            reward = float(meta.get("reward_dzd") or 0.0)
            if reward > 0:
                await record_wallet_tx(
                    s,
                    u,
                    reward,
                    "badge_reward",
                    f"مكافأة شارة {meta['emoji']} {meta['title']}",
                    ref_code=code,
                )
            if not u.equipped_badge and meta["role"] == "buyer":
                u.equipped_badge = code
            if primary_sid and meta["role"] == "seller":
                st = await s.get(Store, primary_sid)
                if st and not st.featured_badge:
                    st.featured_badge = code
            newly_unlocked.append(meta)
        if newly_unlocked:
            await s.commit()

    if notify and bot and newly_unlocked:
        for meta in newly_unlocked:
            reward = float(meta.get("reward_dzd") or 0.0)
            reward_line = f"\n🎁 <b>مكافأة فورية:</b> +{reward:g} {DEFAULT_CURRENCY} أُضيفت لمحفظتك!" if reward > 0 else ""
            role_lbl = "شارة بائع 🏪" if meta["role"] == "seller" else "شارة مشتري 🛍️"
            msg = (
                f"🏆🎉 <b>مبارك! حصلت على شارة جديدة!</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"{meta['emoji']} <b>{meta['title']}</b> ({role_lbl})\n"
                f"<i>{meta['desc']}</i>\n"
                f"✦ ⚡ <b>+{meta['xp']} XP</b>{reward_line}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"✨ يمكنك الآن إظهار هذه الشارة في ملفك أو بجانب اسم متجرك!"
            )
            cb_target = f"badges:hub:{meta['role']}:0:1"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏅 عرض شاراتي وتفعيلها", callback_data=cb_target)]
            ])
            with suppress(Exception):
                await bot.send_message(uid, msg, reply_markup=kb)
    return newly_unlocked


BADGES_PER_PAGE: Final[int] = 8


async def _render_badges_hub(
    msg_obj: Message,
    bot: Bot,
    uid: int,
    role: str = "buyer",
    sid: int = 0,
    page: int = 1,
    edit: bool = True,
):
    if role not in ("buyer", "seller"):
        role = "buyer"
    newly = await evaluate_user_badges(bot, uid, notify=False)
    async with Session() as s:
        u = await ensure_user(s, uid, DEFAULT_LANG)
        unlocked_set = set(
            (await s.execute(select(UserBadge.badge_code).where(UserBadge.user_tg_id == uid))).scalars().all()
        )
        progress, primary_sid = await _compute_user_mission_progress(s, uid)
        if role == "seller" and not sid and primary_sid:
            sid = primary_sid
        st = await s.get(Store, sid) if sid else None
        await s.commit()

    total_xp = sum((get_badge_info(c) or {}).get("xp", 0) for c in unlocked_set)
    lvl, r_em, r_nm, next_xp = get_user_rank(total_xp)
    next_str = f" (المستوى القادم عند {next_xp} XP)" if next_xp else " (أعلى مستوى في المنصة! 👑)"

    if role == "seller" and st:
        active_code = st.featured_badge or ""
        active_label = "شارة المتجر البارزة"
    else:
        active_code = u.equipped_badge or ""
        active_label = "شارتك المعروضة"
    eq_meta = get_badge_info(active_code)
    eq_str = f"{eq_meta['emoji']} <b>{eq_meta['title']}</b>" if eq_meta else "<i>غير محددة بعد</i>"

    role_badges = [m for m in BADGE_CATALOG.values() if m["role"] == role]
    role_unlocked_cnt = sum(1 for m in role_badges if m["code"] in unlocked_set)
    total_pages = max(1, (len(role_badges) + BADGES_PER_PAGE - 1) // BADGES_PER_PAGE)
    page = max(1, min(page, total_pages))
    page_slice = role_badges[(page - 1) * BADGES_PER_PAGE : page * BADGES_PER_PAGE]

    title_hdr = (
        f"🏪🏅 <b>شارات ومهام البائع — {esc(st.name)}</b> (صفحة {page}/{total_pages})"
        if role == "seller" and st
        else f"🛍️🏅 <b>شارات ومهام المشتري</b> (صفحة {page}/{total_pages})"
    )
    unlock_banner = ""
    if newly:
        names = "، ".join(f"{m['emoji']} {m['title']}" for m in newly)
        unlock_banner = f"\n🎉 <b>تم فتح شارة جديدة الآن:</b> {names}!\n"

    mission_lines = []
    for m in page_slice:
        cur, tgt, _ach = progress.get(m["code"], (0, m["target"], False))
        rew = f" + 🎁 {m['reward_dzd']:g} دج" if m["reward_dzd"] > 0 else ""
        if m["code"] in unlocked_set:
            mission_lines.append(
                f"✅ {m['emoji']} <b>{m['title']}</b> <i>(+{m['xp']} XP{rew})</i>\n"
                f"   └ {m['desc']}"
            )
        else:
            bar = _badge_progress_bar(cur, tgt)
            mission_lines.append(
                f"🔒 {m['emoji']} <b>{m['title']}</b> <i>(+{m['xp']} XP{rew})</i>\n"
                f"   └ {m['desc']}\n"
                f"   └ <code>{bar}</code> ({cur:,}/{tgt:,})"
            )

    text = (
        f"{title_hdr}\n"
        f"━━━━━━━━━━━━━━━{unlock_banner}"
        f"✦ 🎖️ <b>المرتبة:</b> {r_em} <b>{r_nm}</b> (Lv.{lvl} • <b>{total_xp} XP</b>){next_str}\n"
        f"✦ ✨ <b>{active_label}:</b> {eq_str}\n"
        f"✦ 📊 <b>الإنجاز:</b> {role_unlocked_cnt}/{len(role_badges)} في هذا القسم | الإجمالي: {len(unlocked_set)}/{len(BADGE_CATALOG)}\n"
        f"━━━━━━━━━━━━━━━\n"
        + "\n\n".join(mission_lines)
    )

    other_role = "buyer" if role == "seller" else "seller"
    other_lbl = "🛍️ عرض شارات المشتري (16)" if role == "seller" else "🏪 عرض شارات البائع (16)"
    rows = []
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(text="◀️ الصفحة السابقة", callback_data=f"badges:hub:{role}:{sid}:{page - 1}"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton(text="الصفحة التالية ▶️", callback_data=f"badges:hub:{role}:{sid}:{page + 1}"))
        if nav_row:
            rows.append(nav_row)
    rows.append([InlineKeyboardButton(text=other_lbl, callback_data=f"badges:hub:{other_role}:{sid}:1")])
    if role_unlocked_cnt > 0:
        equip_lbl = "✨ اختيار شارة المتجر البارزة" if (role == "seller" and st) else "✨ اختيار شارتي المعروضة"
        rows.append([InlineKeyboardButton(text=equip_lbl, callback_data=f"badges:equip_menu:{role}:{sid}")])
    rows.append([
        InlineKeyboardButton(text="🔄 تحديث المهام", callback_data=f"badges:hub:{role}:{sid}:{page}"),
        InlineKeyboardButton(text="🏆 لوحة الأبطال", callback_data=f"badges:lb:{role}:{sid}"),
    ])
    back_cb = f"mngstore:{sid}" if (role == "seller" and sid) else "nav:account"
    rows.append([InlineKeyboardButton(text="↩️ رجوع", callback_data=back_cb)])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if edit:
        try:
            await msg_obj.edit_text(text[:4000], reply_markup=kb)
            return
        except Exception:
            pass
    await msg_obj.answer(text[:4000], reply_markup=kb)


@buyer_router.callback_query(F.data.startswith("badges:hub:"))
async def badges_hub_cb(cb: CallbackQuery):
    parts = cb.data.split(":")
    role = parts[2] if len(parts) > 2 else "buyer"
    sid = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 1
    await _render_badges_hub(cb.message, cb.bot, cb.from_user.id, role=role, sid=sid, page=page, edit=True)
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("badges:equip_menu:"))
async def badges_equip_menu_cb(cb: CallbackQuery):
    parts = cb.data.split(":")
    role = parts[2] if len(parts) > 2 else "buyer"
    sid = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    uid = cb.from_user.id
    async with Session() as s:
        unlocked = (
            await s.execute(select(UserBadge.badge_code).where(UserBadge.user_tg_id == uid))
        ).scalars().all()
        u = await ensure_user(s, uid, DEFAULT_LANG)
        st = await s.get(Store, sid) if (role == "seller" and sid) else None
    current_eq = (st.featured_badge if st else u.equipped_badge) or ""
    role_unlocked = [c for c in unlocked if (get_badge_info(c) or {}).get("role") == role]
    if not role_unlocked:
        return await cb.answer("🔒 لم تفتح أي شارة في هذا القسم بعد! أكمل مهمة أولاً.", show_alert=True)
    rows = []
    cur_row: list[InlineKeyboardButton] = []
    for c in role_unlocked:
        m = get_badge_info(c)
        if not m:
            continue
        mark = " ✅" if c == current_eq else ""
        cur_row.append(
            InlineKeyboardButton(
                text=f"{m['emoji']} {m['title']}{mark}",
                callback_data=f"badges:equip:{role}:{sid}:{c}",
            )
        )
        if len(cur_row) == 2:
            rows.append(cur_row)
            cur_row = []
    if cur_row:
        rows.append(cur_row)
    rows.append([InlineKeyboardButton(text="↩️ رجوع للشارات", callback_data=f"badges:hub:{role}:{sid}:1")])
    target_desc = f"متجر <b>{esc(st.name)}</b> (ستظهر أمام جميع المشترين!)" if st else "ملفك الشخصي"
    text = f"✨🏅 <b>اختر الشارة التي تريد إبرازها في {target_desc}:</b>"
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@buyer_router.callback_query(F.data.startswith("badges:equip:"))
async def badges_equip_apply_cb(cb: CallbackQuery):
    parts = cb.data.split(":")
    role = parts[2]
    sid = int(parts[3]) if parts[3].isdigit() else 0
    code = parts[4]
    uid = cb.from_user.id
    m = get_badge_info(code)
    if not m:
        return await cb.answer("❌ شارة غير صالحة.", show_alert=True)
    async with Session() as s:
        has_it = (
            await s.execute(
                select(UserBadge.id).where(UserBadge.user_tg_id == uid, UserBadge.badge_code == code)
            )
        ).scalar_one_or_none()
        if not has_it:
            return await cb.answer("🔒 هذه الشارة غير مفتوحة بعد.", show_alert=True)
        if role == "seller" and sid:
            st = await s.get(Store, sid)
            if not st or st.owner_tg_id != uid:
                return await cb.answer("⛔ غير مصرح.", show_alert=True)
            st.featured_badge = code
        else:
            u = await ensure_user(s, uid, DEFAULT_LANG)
            u.equipped_badge = code
        await s.commit()
    await cb.answer(f"✅ تم تفعيل شارة {m['emoji']} {m['title']}!", show_alert=True)
    await _render_badges_hub(cb.message, cb.bot, uid, role=role, sid=sid, edit=True)


@buyer_router.callback_query(F.data.startswith("badges:lb:"))
async def badges_leaderboard_cb(cb: CallbackQuery):
    parts = cb.data.split(":")
    role = parts[2] if len(parts) > 2 else "buyer"
    sid = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    async with Session() as s:
        all_rows = (await s.execute(select(UserBadge.user_tg_id, UserBadge.badge_code))).all()
        xp_by_user: dict[int, int] = {}
        cnt_by_user: dict[int, int] = {}
        for u_id, b_code in all_rows:
            xp_by_user[u_id] = xp_by_user.get(u_id, 0) + int((get_badge_info(b_code) or {}).get("xp", 0))
            cnt_by_user[u_id] = cnt_by_user.get(u_id, 0) + 1
        top_uids = sorted(xp_by_user.keys(), key=lambda x: (xp_by_user[x], cnt_by_user[x]), reverse=True)[:10]
        users_map: dict[int, User] = {}
        stores_map: dict[int, str] = {}
        if top_uids:
            u_objs = (await s.execute(select(User).where(User.tg_id.in_(top_uids)))).scalars().all()
            users_map = {u.tg_id: u for u in u_objs}
            st_objs = (await s.execute(select(Store).where(Store.owner_tg_id.in_(top_uids)))).scalars().all()
            for st in st_objs:
                stores_map.setdefault(st.owner_tg_id, st.name)

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = ["🏆✨ <b>لوحة الشرف — أبطال Market Bot</b>", "━━━━━━━━━━━━━━━"]
    if not top_uids:
        lines.append("📭 لم يفتح أحد شارات بعد — كن أول بطل يعتلي الصدارة! 🚀")
    else:
        for idx, u_id in enumerate(top_uids):
            u = users_map.get(u_id)
            disp_name = stores_map.get(u_id) or (u.saved_name if u and u.saved_name else f"عضو #{str(u_id)[-4:]}")
            eq = get_badge_info(u.equipped_badge) if u and u.equipped_badge else None
            eq_em = f" {eq['emoji']}" if eq else ""
            lvl, r_em, r_nm, _ = get_user_rank(xp_by_user[u_id])
            you_tag = " <b>(أنت)</b>" if u_id == cb.from_user.id else ""
            lines.append(
                f"{medals[idx]} <b>{esc(disp_name)}</b>{eq_em}{you_tag}\n"
                f"   ✦ {r_em} {r_nm} • <b>{xp_by_user[u_id]} XP</b> • 🏅 {cnt_by_user[u_id]} شارة"
            )
    lines.append("━━━━━━━━━━━━━━━\n💡 <i>أكمل المهام لترفع مستواك وتتصدر القائمة!</i>")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ رجوع إلى شاراتي", callback_data=f"badges:hub:{role}:{sid}")],
    ])
    try:
        await cb.message.edit_text("\n".join(lines), reply_markup=kb)
    except Exception:
        await cb.message.answer("\n".join(lines), reply_markup=kb)
    await cb.answer()


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


async def subscription_lifecycle_task(bot: Bot) -> None:
    """Handle 3d/24h expiry reminders, wallet auto-renewals, and 48h grace downgrades."""
    await asyncio.sleep(60)
    while True:
        try:
            now = utcnow()
            grace_delta = timedelta(hours=SUB_GRACE_HOURS)
            notifications: list[tuple[int, str, Optional[InlineKeyboardMarkup]]] = []

            async with Session() as s:
                plans = await get_dynamic_plans(s)
                stores = (
                    await s.execute(
                        select(Store).where(
                            Store.plan_tier.in_(["pro", "vip"]),
                            Store.plan_expires_at.is_not(None),
                        )
                    )
                ).scalars().all()

                changed = False
                for st in stores:
                    exp = st.plan_expires_at
                    if not exp:
                        continue
                    rem = exp - now
                    renew_kb = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="👑 تجديد الاشتراك الآن", callback_data=f"st_vip:{st.id}")
                    ]])

                    # 1) 3-day reminder
                    if timedelta(days=1) < rem <= timedelta(days=3) and not st.expiry_reminded_3d:
                        st.expiry_reminded_3d = True
                        changed = True
                        notifications.append((
                            st.owner_tg_id,
                            f"⏳ <b>تذكير باشتراك متجرك ({esc(st.name)})</b>\n\n"
                            f"باقة <b>{st.plan_tier.upper()}</b> ستنتهي خلال أقل من 3 أيام (<b>{exp.strftime('%Y-%m-%d')}</b>).\n"
                            f"{'♻️ التجديد التلقائي من المحفظة مفعّل.' if st.auto_renew else '💡 جدد الآن للحفاظ على النشر المباشر ومزايا باقتك.'}",
                            renew_kb,
                        ))
                    # 2) 24-hour reminder
                    elif timedelta(0) < rem <= timedelta(days=1) and not st.expiry_reminded_1d:
                        st.expiry_reminded_1d = True
                        changed = True
                        notifications.append((
                            st.owner_tg_id,
                            f"⚠️ <b>تنبيه عاجل — اشتراك متجر {esc(st.name)}</b>\n\n"
                            f"تبقّى أقل من <b>24 ساعة</b> على انتهاء باقة <b>{st.plan_tier.upper()}</b>!\n"
                            f"{'♻️ سيتم التجديد تلقائياً من محفظتك عند الانتهاء إذا كان الرصيد كافياً.' if st.auto_renew else '💡 جدد الآن أو فعّل التجديد التلقائي من المحفظة.'}",
                            renew_kb,
                        ))
                    # 3) Expired: try auto-renew if enabled
                    elif rem <= timedelta(0) and st.auto_renew:
                        plan_key = "vip_30" if st.plan_tier == "vip" else "pro_30"
                        plan_info = plans[plan_key]
                        price = float(plan_info["price"])
                        res = await s.execute(
                            update(User)
                            .where(User.tg_id == st.owner_tg_id, User.ad_credits >= price)
                            .values(ad_credits=User.ad_credits - price)
                        )
                        if res.rowcount > 0:
                            u = await ensure_user(s, st.owner_tg_id, DEFAULT_LANG)
                            s.add(WalletTransaction(
                                user_tg_id=st.owner_tg_id,
                                tx_type="subscription",
                                amount=-round(price, 2),
                                balance_after=float(u.ad_credits or 0.0),
                                description=f"♻️ تجديد تلقائي لباقة {plan_info['label']} ({st.name})",
                            ))
                            until_str, bonus, tier = await activate_store_plan(s, st, plan_key, user=u)
                            changed = True
                            b_txt = f"\n🎁 هدية إعلانات مضافة: <b>+{bonus:g} {DEFAULT_CURRENCY}</b>" if bonus > 0 else ""
                            notifications.append((
                                st.owner_tg_id,
                                f"♻️ <b>تم التجديد التلقائي لاشتراك متجر {esc(st.name)} بنجاح!</b>\n\n"
                                f"👑 الباقة: <b>{tier.upper()}</b> | 💳 المخصوم: <b>{price:g} {DEFAULT_CURRENCY}</b>\n"
                                f"📅 صالح حتى: <b>{until_str}</b>{b_txt}",
                                None,
                            ))
                        else:
                            st.auto_renew = False
                            changed = True
                            notifications.append((
                                st.owner_tg_id,
                                f"⚠️ <b>فشل التجديد التلقائي لمتجر {esc(st.name)}</b>\n\n"
                                f"رصيد محفظتك غير كافٍ ({price:g} {DEFAULT_CURRENCY}). لديك <b>فترة سماح {SUB_GRACE_HOURS} ساعة</b> لتجديد الاشتراك دون فقدان مزاياك.",
                                renew_kb,
                            ))
                    # 4) Grace period ended -> clean downgrade to Free (NEVER deletes products!)
                    elif (exp + grace_delta) <= now:
                        old_tier = st.plan_tier.upper()
                        st.plan_tier = "free"
                        st.auto_approve = False
                        st.vip_until = None
                        st.expiry_reminded_3d = False
                        st.expiry_reminded_1d = False
                        changed = True
                        notifications.append((
                            st.owner_tg_id,
                            f"📌 <b>انتهت باقة {old_tier} لمتجر {esc(st.name)}</b>\n\n"
                            f"تم تحويل المتجر إلى الباقة المجانية (Free) بعد انتهاء فترة السماح.\n"
                            f"🛡️ جميع منتجاتك الحالية محفوظة ولم يُحذف أي شيء. يمكنك التجديد في أي وقت:",
                            renew_kb,
                        ))

                if changed:
                    await s.commit()

            for uid, txt, kb in notifications:
                with suppress(Exception):
                    await bot.send_message(uid, txt, reply_markup=kb)
                    await asyncio.sleep(0.05)

            await asyncio.sleep(21600)
        except asyncio.CancelledError:
            logger.info("subscription_lifecycle_task cancelled")
            raise
        except Exception:
            logger.exception("Unexpected error in subscription_lifecycle_task")
            await asyncio.sleep(600)


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

    print("[startup] Initializing database...", flush=True)
    await init_db()
    if Session is None:
        raise RuntimeError("Database initialization failed (Session is None)")
    await seed_categories(Session)
    print("[startup] Database ready. Connecting to Telegram...", flush=True)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    bg_tasks: list[asyncio.Task] = []

    try:
        me = await bot.get_me()
        BOT_USERNAME = me.username or ""
        print(f"[startup] Connected as @{BOT_USERNAME} (ID: {me.id})", flush=True)
        logger.info(f"Bot started as @{BOT_USERNAME}")

        await set_bot_commands(bot)
        with suppress(TelegramAPIError):
            await bot.delete_webhook(drop_pending_updates=False)

        dp = Dispatcher(storage=MemoryStorage())
        flood_mw = AntiFloodMiddleware()
        dp.message.outer_middleware.register(flood_mw)
        dp.callback_query.outer_middleware.register(flood_mw)
        dp.include_router(buyer_router)
        dp.include_router(seller_router)
        dp.errors.register(global_error_handler)

        bg_tasks.append(asyncio.create_task(abandoned_cart_task(bot)))
        bg_tasks.append(asyncio.create_task(daily_backup_task(bot)))
        bg_tasks.append(asyncio.create_task(subscription_lifecycle_task(bot)))
        print(f"[startup] Polling started for @{BOT_USERNAME} — ready for /start!", flush=True)
        await dp.start_polling(bot)

    finally:
        print("[shutdown] Shutting down bot...", flush=True)
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
        print("[shutdown] Stopped cleanly.", flush=True)
        logger.info("Stopped")
    except Exception:
        logger.exception("Fatal startup error")
        raise
