"""Initial database catalog.

Runtime catalog reads always come from SQLAlchemy models. This module is used only
to populate an empty catalog on first startup.
"""

from copy import deepcopy
from typing import Any

CDN_BASE = "https://cdn.prod.website-files.com/694bda815329f22ed324613d/"

SOURCE_LOGOS: tuple[tuple[str, str, str], ...] = (
    ("runpod", "RunPod", "6a844e14682d3ba73fee03fd_6a844d6a4dafb888a5d2f1ea_runpod-logo.svg"),
    ("magnific", "Magnific (ex. Freepik)", "6a844e6d8530980c6a91594d_freepik-logo.svg"),
    ("subscribestar", "SubscribeStar", "6a844d6a19a47c2969805fd2_subscribestar-logo.svg"),
    ("duolingo", "Duolingo", "6a844d6a32fc06f410fb18fc_duolingo-logo.svg"),
    ("capcut", "CapCut", "6a844d6a19a47c2969805f5d_capcut-logo.svg"),
    ("minecraft", "Minecraft", "6a844d69ba2a097fdcb25249_minecraft-logo.svg"),
    ("tiktok", "TikTok", "6a844d69ba2a097fdcb25231_tiktok-logo.svg"),
    ("battle-net", "Battle.net", "6a844d09199d0495e13c5e10_battle-net-logo.svg"),
    ("supercell", "Supercell", "6a844d094f4dbfdba78d0aba_supercell-logo.svg"),
    ("nintendo", "Nintendo", "6a844d0827ae24322cfd63df_nintendo-logo.svg"),
    ("genshin-impact", "Genshin Impact", "6a844d084f4dbfdba78d0a8c_genshin-impact-logo.svg"),
    ("paypal", "PayPal", "6a844d084dafb888a5d2dd3e_paypal-logo.svg"),
    ("hostinger", "Hostinger", "6a844d088530980c6a9121f2_hostinger-logo.svg"),
    ("x-twitter", "X (Twitter)", "6a844d084dafb888a5d2dd3e_x-twitter-logo.svg"),
    ("udio", "Udio", "6a844c6b3b572c51fb77dcfd_udio-logo.svg"),
    ("genspark", "Genspark", "6a844c6b95ec3cc4bb69e94f_genspark-logo.svg"),
    ("lovable", "Lovable", "6a844c6b04ba12b95a1fa26b_lovable-logo.svg"),
    ("abacus-ai", "Abacus.AI", "6a844c6b19d7e42f63957dee_abacus-ai-logo.svg"),
    ("manus-ai", "Manus AI", "6a844c6b5bfb5258553fb105_manus-ai-logo.svg"),
    ("railway", "Railway", "6a844c6b5bfb5258553fb0e2_railway-logo.svg"),
    ("replit", "Replit", "6a844c6b27ae24322cfd2bdd_replit-logo.svg"),
    ("grab", "Grab", "6a844bf677b49031ab482649_grab-logo.svg"),
    ("telegram-premium", "Telegram Premium", "6a844bf677b49031ab482631_telegram-premium-logo.svg"),
    ("higgsfield", "Higgsfield", "6a844bf6ccc4cb18a4f7f32d_higgsfield-logo.svg"),
    ("kimi", "Kimi", "6a844bf65bfb5258553f6fbf_kimi-logo.svg"),
    ("netflix", "Netflix", "6a844bf60797c03817716900_netflix-logo.svg"),
    ("roblox", "Roblox", "6a844bf60ee11f61f03a2318_roblox-logo.svg"),
    ("pubg-mobile", "PUBG Mobile", "6a844bf5199d0495e13be5c7_pubg-mobile-logo.svg"),
    ("github-copilot", "GitHub Copilot", "6a74517eeb481309db21e683_copilot.png"),
    ("openrouter", "OpenRouter", "6a736526c2ff69bd39253949_openrouter.svg"),
    ("steam", "Steam", "6a15531bfb101ce2cab6c246_steam%20logo.svg"),
    ("zoom", "Zoom", "6a155399b24991c7699ba9e7_zoom%20logo.svg"),
    ("spotify", "Spotify", "6a1553f848155bc8e16e3599_Spotify%20logo.svg"),
    ("google-pay", "Google Pay", "6a15547f2cfb42fe2e63fd96_gpay.svg"),
    ("apple-id", "Apple ID", "6a1554e6795fc59fc9b87cd5_apple.svg"),
    ("n8n", "n8n", "69ca75c794c31ea0b0e43cca_whoop%20(1).svg"),
    ("whoop", "Whoop", "69a0a08143eb1b3ed6d514c6_whoop.svg"),
    ("kling-ai", "Kling AI", "69a09fa30297a2984a0c3548_Kling%20AI.svg"),
    ("amazon-prime-video", "Amazon Prime Video", "69a09ed17bb6c5826e3300f5_amazon-prime-video.svg"),
    ("similarweb", "SimilarWeb", "69a09dd07ad82c37acbdbf86_similarweb.svg"),
    ("facebook-ads", "Facebook Ads", "69d3de5a2cb8dde94fcca17c_facebook-ads.svg"),
    ("github", "GitHub", "69a09ab47ed07baca34e998e_github.svg"),
    ("cloudflare", "Cloudflare", "69a099df06590c744ebc2190_cloudflare.svg"),
    ("manychat", "ManyChat", "69a0955006de8b551f563819_manychat.svg"),
    ("icloud", "iCloud", "69a0944758e751274ecf6798_icloud.svg"),
    ("adobe", "Adobe", "69a0938a2dbd604115c145ca_adobe-creative-cloud.svg"),
    ("udemy", "Udemy", "69a092caa95883b60aee5c10_udemy.svg"),
    ("app-store", "App Store", "69a0915f3312e62d8af3cc22_app-store.svg"),
    ("dropbox", "Dropbox", "69a090ae0491f3d6ddfbc310_dropbox.svg"),
    ("envato-elements", "Envato Elements", "69a0901ebfb56fcd3a3f02eb_envato-elements.svg"),
    ("tidal", "Tidal", "69a08f80d3fc3fbb8f9acbfb_tidal.svg"),
    ("airbnb", "Airbnb", "69a08ecdb40cc67978301e7a_airbnb.svg"),
    ("canva", "Canva", "69a08e5e890f6dd07eedfd99_canva.svg"),
    ("youtube-premium", "YouTube Premium", "69a08cf36fd9fb8d8ccab178_youtube-premium.svg"),
    ("discord-nitro", "Discord Nitro", "69a08c58a6db74d329c32b16_discord-nitro.svg"),
    ("claude", "Claude", "69a08b977a6b26e1b62614c5_claude-pro.svg"),
    ("suno", "Suno", "69d3de094a2166314654ac24_suno%20logo.svg"),
    ("figma", "Figma", "69a089c392a75347ccdaae61_figma.svg"),
    ("elevenlabs", "ElevenLabs", "69a088e2eeb2df23c4dcf766_elevenlabs.svg"),
    ("jetbrains", "JetBrains", "69a08852fac0c540c2785715_jetbrains.svg"),
    ("cults-3d", "Cults 3D", "69a0872f94d47851b895af41_cults3d.svg"),
    ("shutterstock", "Shutterstock", "69a08674edc59f5694ad388b_shutterstock.svg"),
    ("grok-ai", "Grok AI", "69a0858b1e0be45c92e8adae_grok.svg"),
    ("patreon", "Patreon", "69a0844e7486f6966cc56e0a_patreon.svg"),
    ("leonardo-ai", "Leonardo AI", "69a08373730e09a2a32cea35_leonardo.ai_.svg"),
    ("airalo", "Airalo", "69a082b8c32d30c77adabdcc_airalo.svg"),
    ("tradingview", "TradingView", "69a081b8466b42a147ee253a_tradingview.svg"),
    ("midjourney", "Midjourney", "69a814febf1737d5b2db6e06_midjourney%20logo.svg"),
    ("fansly", "Fansly", "69a065492e56f66de4f1c3f4_fansly.svg"),
    ("onlyfans", "OnlyFans", "6999edcb79a16ea8a9389aaf_Heygen%20(1).svg"),
    ("booking", "Booking", "6999ec49772b23d51e76152e_booking.com_.svg"),
    ("heygen", "HeyGen", "6999eb3b07b506dbbfba6174_Heygen.svg"),
    ("gumroad", "Gumroad", "6999ed610d00599948f61547_gumroad%20(1).svg"),
    ("gamma", "Gamma", "6999e8dad947320e7cb0097f_gamma.svg"),
    ("anthropic", "Anthropic", "6999e7926eda4aba3f363106_Anthropic.svg"),
    ("openai-api", "OpenAI API", "6999e851d762935571a51474_openai.svg"),
    ("nano-banana", "Nano Banana", "6999e848f11951eae02998bd_nano%20banana.svg"),
    ("trip", "Trip", "6999e84159459248c0ed603f_trip.svg"),
    ("playstation-store", "PlayStation Store", "6995ede20730a20f5d1ca219_ps-store.svg"),
    ("google-one", "Google One", "6995ebf8d6658b8cb3846c08_google-one.svg"),
    ("deepseek-api", "DeepSeek API", "6995e9bf58932f306f40abf3_gemini-logo-brandlogos.net_1bvilwd19%201%20(2).svg"),
    ("perplexity", "Perplexity", "6995e6120663db18fb34ccd0_perplexity-pro.svg"),
    ("gemini-ai", "Gemini AI", "6995e8382030869bda022a86_gemini-logo-brandlogos.net_1bvilwd19%201.svg"),
    ("google-play", "Google Play", "698b6362ebcc4ff59b42dd03_google-play.svg"),
    ("krea-ai", "Krea AI", "6995e83058932f306f402a3d_gemini-logo-brandlogos.net_1bvilwd19%201%20(1).svg"),
    ("cursor", "Cursor", "6985ec46dfa9e19effe5b9d3_cursor-ai.svg"),
    ("runway", "Runway", "6985ec8ead5c6ab9488eca45_runway-ml.svg"),
    ("chatgpt", "ChatGPT", "6985eca2f50a1c3594dcd461_chatgpt.svg"),
)

CORE_SERVICES: list[dict[str, Any]] = [
    {
        "slug": "chatgpt",
        "name": "ChatGPT",
        "description": "Подписки Plus, Team и Pro для работы с ChatGPT.",
        "accent": "#10A37F",
        "currency": "RUB",
        "requires_access_token": True,
        "token_label": "Access token",
        "token_hint": "Токен используется только при отправке формы и не записывается в базу.",
        "instructions": (
            "1. Проверьте выбранный тариф и период.\n"
            "2. Укажите email, на который оформляется подписка.\n"
            "3. Вставьте access token для завершения заказа.\n"
            "4. Подтвердите заказ. Секретные данные не сохраняются в CRM."
        ),
        "fields": [
            {
                "field_name": "email",
                "field_label": "Email аккаунта ChatGPT",
                "field_type": "email",
                "required": True,
                "placeholder": "name@example.com",
                "help_text": "На этот адрес оформляется подписка.",
                "validation_rules": {},
                "options": [],
                "sort_order": 0,
                "sensitive": False,
                "temporary_only": False,
            },
            {
                "field_name": "temporary_session",
                "field_label": "Временные данные сессии",
                "field_type": "secure_textarea",
                "required": True,
                "placeholder": "Вставьте временные данные для активации",
                "help_text": "Используются только во время выполнения и никогда не сохраняются.",
                "validation_rules": {"min_length": 8},
                "options": [],
                "sort_order": 1,
                "sensitive": True,
                "temporary_only": True,
            },
        ],
        "workflow": {
            "execution_type": "browser_session",
            "active": True,
            "requires_manual_action": False,
            "description": "Изолированная временная браузерная сессия.",
        },
        "levels": [
            {"id": "plus", "name": "Plus", "prices": {"1m": "1990.00", "3m": "5490.00", "12m": "18990.00"}},
            {"id": "team", "name": "Team", "prices": {"1m": "3490.00", "3m": "9490.00", "12m": "32990.00"}},
            {"id": "pro", "name": "Pro", "prices": {"1m": "12990.00", "3m": "34990.00", "12m": "119990.00"}},
        ],
        "periods": [
            {"id": "1m", "name": "1 месяц"},
            {"id": "3m", "name": "3 месяца"},
            {"id": "12m", "name": "12 месяцев"},
        ],
    },
    {
        "slug": "claude",
        "name": "Claude",
        "description": "Подписки Pro и Team для Claude.",
        "accent": "#D97757",
        "currency": "RUB",
        "requires_access_token": False,
        "token_label": None,
        "token_hint": None,
        "instructions": "1. Выберите тариф и период.\n2. Укажите рабочий email.\n3. Подтвердите заказ.",
        "fields": [],
        "workflow": {"execution_type": "manual", "active": True, "requires_manual_action": True, "description": "Ручная активация менеджером."},
        "levels": [
            {"id": "pro", "name": "Pro", "prices": {"1m": "2490.00", "3m": "6990.00", "12m": "23990.00"}},
            {"id": "team", "name": "Team", "prices": {"1m": "4490.00", "3m": "12490.00", "12m": "42990.00"}},
        ],
        "periods": [
            {"id": "1m", "name": "1 месяц"},
            {"id": "3m", "name": "3 месяца"},
            {"id": "12m", "name": "12 месяцев"},
        ],
    },
    {
        "slug": "midjourney",
        "name": "Midjourney",
        "description": "Тарифы Standard и Pro для генерации изображений.",
        "accent": "#1E40AF",
        "currency": "RUB",
        "requires_access_token": False,
        "token_label": None,
        "token_hint": None,
        "instructions": "1. Выберите тариф Midjourney.\n2. Укажите email аккаунта.\n3. Подтвердите заказ.",
        "fields": [
            {
                "field_name": "discord_username",
                "field_label": "Discord username",
                "field_type": "text",
                "required": True,
                "placeholder": "username",
                "help_text": "Укажите имя пользователя Discord, связанное с Midjourney.",
                "validation_rules": {"min_length": 2},
                "options": [],
                "sort_order": 0,
                "sensitive": False,
                "temporary_only": False,
            }
        ],
        "workflow": {"execution_type": "manual", "active": True, "requires_manual_action": True, "description": "Ручная активация менеджером."},
        "levels": [
            {"id": "standard", "name": "Standard", "prices": {"1m": "1290.00", "3m": "3490.00", "12m": "11990.00"}},
            {"id": "pro", "name": "Pro", "prices": {"1m": "2490.00", "3m": "6990.00", "12m": "23990.00"}},
        ],
        "periods": [
            {"id": "1m", "name": "1 месяц"},
            {"id": "3m", "name": "3 месяца"},
            {"id": "12m", "name": "12 месяцев"},
        ],
    },
    {
        "slug": "notion",
        "name": "Notion AI",
        "description": "Подписки Plus и Business для Notion AI.",
        "logo": "",
        "accent": "#111111",
        "currency": "RUB",
        "requires_access_token": False,
        "token_label": None,
        "token_hint": None,
        "instructions": "1. Выберите тариф Notion.\n2. Укажите email workspace.\n3. Подтвердите заказ.",
        "fields": [],
        "workflow": {"execution_type": "manual", "active": True, "requires_manual_action": True, "description": "Ручная активация менеджером."},
        "levels": [
            {"id": "plus", "name": "Plus", "prices": {"1m": "1490.00", "3m": "3990.00", "12m": "13990.00"}},
            {"id": "business", "name": "Business", "prices": {"1m": "2290.00", "3m": "6290.00", "12m": "21990.00"}},
        ],
        "periods": [
            {"id": "1m", "name": "1 месяц"},
            {"id": "3m", "name": "3 месяца"},
            {"id": "12m", "name": "12 месяцев"},
        ],
    },
]

ACCENTS = ("#2563EB", "#7C3AED", "#DB2777", "#EA580C", "#0891B2", "#16A34A", "#475569")

CATEGORY_GROUPS: dict[str, set[str]] = {
    "AI": {
        "chatgpt", "claude", "midjourney", "udio", "genspark", "abacus-ai", "manus-ai",
        "higgsfield", "kimi", "kling-ai", "suno", "elevenlabs", "grok-ai", "leonardo-ai",
        "heygen", "gamma", "anthropic", "nano-banana", "perplexity", "gemini-ai", "krea-ai",
        "runway",
    },
    "Gaming": {
        "minecraft", "battle-net", "supercell", "nintendo", "genshin-impact", "roblox",
        "pubg-mobile", "steam", "playstation-store",
    },
    "Software": {
        "notion", "capcut", "zoom", "adobe", "app-store", "dropbox", "envato-elements",
        "canva", "figma", "jetbrains", "shutterstock", "google-one", "google-play",
    },
    "Developer Tools": {
        "runpod", "lovable", "railway", "replit", "github-copilot", "openrouter", "n8n",
        "github", "cloudflare", "openai-api", "deepseek-api", "cursor",
    },
    "Entertainment": {
        "netflix", "spotify", "tidal", "youtube-premium", "discord-nitro",
        "amazon-prime-video",
    },
    "Social": {
        "subscribestar", "tiktok", "x-twitter", "telegram-premium", "facebook-ads", "manychat",
        "patreon", "fansly", "onlyfans",
    },
    "Finance": {"paypal", "google-pay", "apple-id", "tradingview"},
    "Travel": {"grab", "airbnb", "airalo", "booking", "trip"},
    "Education": {"duolingo", "udemy"},
    "Commerce": {"hostinger", "icloud", "cults-3d", "gumroad", "magnific"},
}


def _category_for(slug: str) -> str:
    return next((name for name, slugs in CATEGORY_GROUPS.items() if slug in slugs), "Other")


def _workflow_for(slug: str) -> dict[str, Any]:
    if slug in {"openai-api", "deepseek-api", "openrouter"}:
        return {"execution_type": "api", "active": True, "requires_manual_action": False, "description": "Пополнение через API-исполнитель."}
    if slug in {"genshin-impact", "pubg-mobile", "supercell"}:
        return {"execution_type": "uid_topup", "active": True, "requires_manual_action": True, "description": "Пополнение по UID и региону аккаунта."}
    if slug in {"steam", "playstation-store", "app-store", "google-play", "nintendo", "roblox"}:
        return {"execution_type": "gift_code", "active": True, "requires_manual_action": True, "description": "Выдача или активация цифрового кода."}
    return {"execution_type": "manual", "active": True, "requires_manual_action": True, "description": "Ручное выполнение заказа менеджером."}


def _default_fields(slug: str, name: str) -> list[dict[str, Any]]:
    if slug == "genshin-impact":
        return [
            {
                "field_name": "uid", "field_label": "UID", "field_type": "text", "required": True,
                "placeholder": "700000000", "help_text": "UID игрового аккаунта.",
                "validation_rules": {"pattern": "^[0-9]{6,12}$"}, "options": [], "sort_order": 0,
                "sensitive": False, "temporary_only": False,
            },
            {
                "field_name": "server", "field_label": "Сервер", "field_type": "select", "required": True,
                "placeholder": "Выберите сервер", "help_text": "Регион игрового аккаунта.",
                "validation_rules": {}, "options": ["Europe", "America", "Asia"], "sort_order": 1,
                "sensitive": False, "temporary_only": False,
            },
        ]
    return [
        {
            "field_name": "email", "field_label": f"Email аккаунта {name}", "field_type": "email",
            "required": True, "placeholder": "name@example.com", "help_text": "Email для оформления заказа.",
            "validation_rules": {}, "options": [], "sort_order": 0,
            "sensitive": False, "temporary_only": False,
        }
    ]


def _generic_service(slug: str, name: str, logo: str, index: int) -> dict[str, Any]:
    return {
        "slug": slug,
        "name": name,
        "logo": logo,
        "category": _category_for(slug),
        "description": f"Оплата цифровых продуктов и услуг {name}.",
        "accent": ACCENTS[index % len(ACCENTS)],
        "currency": "RUB",
        "requires_access_token": False,
        "token_label": None,
        "token_hint": None,
        "instructions": (
            "1. Проверьте выбранный тариф и период.\n"
            "2. Укажите email аккаунта.\n"
            "3. Подтвердите заказ — менеджер свяжется с вами для завершения оплаты."
        ),
        "fields": _default_fields(slug, name),
        "workflow": _workflow_for(slug),
        "levels": [{"id": "basic", "name": "Базовый", "prices": {"1m": "0.00"}}],
        "periods": [{"id": "1m", "name": "1 месяц"}],
    }


def build_default_services() -> list[dict[str, Any]]:
    services = deepcopy(CORE_SERVICES)
    by_slug = {service["slug"]: service for service in services}

    for index, (slug, name, path) in enumerate(SOURCE_LOGOS):
        logo = f"{CDN_BASE}{path}"
        if slug in by_slug:
            by_slug[slug]["logo"] = logo
            by_slug[slug]["category"] = _category_for(slug)
            continue
        service = _generic_service(slug, name, logo, index)
        services.append(service)
        by_slug[slug] = service

    for service in services:
        service.setdefault("category", _category_for(service["slug"]))

    return services


DEFAULT_SERVICES = build_default_services()
