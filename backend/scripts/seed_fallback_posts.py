"""
Seed the fallback_posts library with evergreen Russian content.

Run against the DB pointed at by $DATABASE_URL:
    source venv/bin/activate && python scripts/seed_fallback_posts.py

Safe to re-run — skips any post whose title_ru already exists.

After seeding, the watchdog can publish these when the live content pipeline
fails. You can edit, add, or deactivate entries via the admin API:
    GET/POST/PATCH/DELETE /api/health/fallback-posts
"""
import asyncio
import json
import sys
from pathlib import Path

# Make `app.*` imports work when script is run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.fallback_post import FallbackPost


# Evergreen Russian posts. Each one is self-contained and safe to publish at
# any time of day or year. Written to match the brand voice of a Dubai real
# estate / lifestyle channel.
SEED_POSTS = [
    # ---- real_estate ----
    {
        "title_ru": "Почему Дубай остаётся топ-направлением для инвестиций в недвижимость",
        "body_ru": (
            "Дубай год за годом входит в тройку мировых лидеров по доходности "
            "арендной недвижимости. Главные причины:\n\n"
            "• Нулевой налог на доход с аренды\n"
            "• Прозрачная регистрация сделок через DLD\n"
            "• Растущее население и постоянный спрос на жильё\n"
            "• Доходность от 6% до 10% годовых в валюте\n\n"
            "Если вы рассматриваете инвестиции в недвижимость за рубежом — "
            "свяжитесь с нами, подберём подходящий объект под ваш бюджет и цель."
        ),
        "hashtags": ["#Dubai", "#DubaiRealEstate", "#Investment", "#IDIGOV"],
        "content_type": "real_estate",
    },
    {
        "title_ru": "Off-plan в Дубае: преимущества покупки на этапе строительства",
        "body_ru": (
            "Off-plan — это покупка недвижимости у застройщика до сдачи объекта. "
            "Почему это выгодно:\n\n"
            "• Цена ниже готового жилья на 20–30%\n"
            "• Гибкие планы рассрочки — часто до 50% после сдачи\n"
            "• Потенциал роста капитала ко дню передачи ключей\n"
            "• Новые районы с современной инфраструктурой\n\n"
            "Риски минимизирует Escrow-система RERA — деньги покупателя защищены "
            "на специальном счёте до завершения строительства."
        ),
        "hashtags": ["#OffPlan", "#Dubai", "#RealEstate", "#IDIGOV"],
        "content_type": "real_estate",
    },
    {
        "title_ru": "Golden Visa через недвижимость: резиденство ОАЭ на 10 лет",
        "body_ru": (
            "Владельцы недвижимости в ОАЭ стоимостью от 2 млн AED могут получить "
            "Golden Visa — долгосрочную резидентскую визу сроком на 10 лет.\n\n"
            "Что даёт Golden Visa:\n"
            "• 10 лет проживания с правом продления\n"
            "• Спонсорство для членов семьи и домашнего персонала\n"
            "• Возможность находиться вне ОАЭ более 6 месяцев без потери статуса\n"
            "• Доступ к открытию банковских счетов и бизнеса\n\n"
            "Недвижимость можно покупать как готовую, так и off-plan — с "
            "определёнными условиями. Напишите нам, чтобы узнать подробности."
        ),
        "hashtags": ["#GoldenVisa", "#Dubai", "#UAE", "#IDIGOV"],
        "content_type": "real_estate",
    },
    {
        "title_ru": "Downtown Dubai: сердце города и стабильная доходность",
        "body_ru": (
            "Downtown Dubai — район Burj Khalifa и Dubai Mall. Один из самых "
            "востребованных адресов для инвесторов.\n\n"
            "Почему сюда инвестируют:\n"
            "• Высокий спрос на аренду среди экспатов и туристов\n"
            "• Средняя доходность аренды — 5–7% годовых\n"
            "• Цены стабильно растут благодаря ограниченному предложению\n"
            "• Премиум-инфраструктура: метро, рестораны, фонтаны\n\n"
            "Апартаменты в Downtown — это сочетание статуса и предсказуемого дохода."
        ),
        "hashtags": ["#DowntownDubai", "#BurjKhalifa", "#Investment", "#IDIGOV"],
        "content_type": "real_estate",
    },
    {
        "title_ru": "Palm Jumeirah: легендарный остров и элитная недвижимость",
        "body_ru": (
            "Palm Jumeirah — рукотворный остров в форме пальмы. Один из самых "
            "узнаваемых адресов Дубая.\n\n"
            "Что здесь предлагается:\n"
            "• Виллы на частных пляжах с собственным выходом к морю\n"
            "• Апартаменты с видом на Персидский залив и skyline Дубая\n"
            "• Отели мирового класса: Atlantis, One&Only, Waldorf Astoria\n"
            "• Растущий рынок краткосрочной аренды — особенно в высокий сезон\n\n"
            "Недвижимость на Palm — это не только дом, но и ликвидный актив "
            "в одной из самых престижных локаций мира."
        ),
        "hashtags": ["#PalmJumeirah", "#LuxuryRealEstate", "#Dubai", "#IDIGOV"],
        "content_type": "real_estate",
    },
    # ---- general_dubai ----
    {
        "title_ru": "Почему жизнь в Дубае привлекает экспатов со всего мира",
        "body_ru": (
            "Дубай — один из немногих мегаполисов, который одинаково подходит и "
            "для работы, и для отдыха, и для семейной жизни.\n\n"
            "Главные плюсы жизни здесь:\n"
            "• Нулевой подоходный налог\n"
            "• Безопасность — один из самых низких уровней преступности в мире\n"
            "• Современные школы и медицина международного уровня\n"
            "• Круглогодичное солнце и море\n"
            "• Более 200 национальностей — настоящий мультикультурный хаб\n\n"
            "Не случайно Дубай уже десятилетие входит в топ-5 городов для жизни "
            "экспатов по данным InterNations."
        ),
        "hashtags": ["#Dubai", "#ExpatLife", "#UAE", "#IDIGOV"],
        "content_type": "general_dubai",
    },
    {
        "title_ru": "Налоговая система ОАЭ: почему это выгодно для частных лиц",
        "body_ru": (
            "ОАЭ — одна из самых дружелюбных к налогоплательщикам юрисдикций в мире.\n\n"
            "Для физических лиц:\n"
            "• Нет подоходного налога\n"
            "• Нет налога на доход с аренды недвижимости\n"
            "• Нет налога на прирост капитала\n"
            "• Нет налога на наследство\n\n"
            "Для бизнеса:\n"
            "• Корпоративный налог — 9% для дохода свыше 375,000 AED\n"
            "• VAT — 5%, один из самых низких в мире\n"
            "• Полное освобождение от налогов в большинстве Free Zones\n\n"
            "Эта прозрачность — одна из главных причин, почему предприниматели и "
            "инвесторы выбирают ОАЭ для релокации."
        ),
        "hashtags": ["#UAE", "#Taxation", "#Business", "#IDIGOV"],
        "content_type": "general_dubai",
    },
    {
        "title_ru": "Дубай как бизнес-хаб: почему сюда переезжают компании",
        "body_ru": (
            "Дубай уверенно входит в топ-10 мировых финансовых центров по индексу GFCI.\n\n"
            "Что привлекает компании:\n"
            "• Стратегическое расположение — 4 часа полёта до 2 млрд людей\n"
            "• Более 40 Free Zones со 100% иностранным владением\n"
            "• Быстрая регистрация компании — от 3 рабочих дней\n"
            "• Развитая банковская система и доступ к финансированию\n"
            "• Высокий уровень английского языка в деловой среде\n\n"
            "Для многих предпринимателей открытие офиса в Дубае — это ворота "
            "на рынки Ближнего Востока, Африки и Южной Азии."
        ),
        "hashtags": ["#Dubai", "#Business", "#FreeZone", "#IDIGOV"],
        "content_type": "general_dubai",
    },
    {
        "title_ru": "Туризм в Дубае: стабильный рекорд год за годом",
        "body_ru": (
            "Дубай — один из самых посещаемых городов мира, принимающий более "
            "17 миллионов туристов в год.\n\n"
            "Что делает его магнитом для путешественников:\n"
            "• Круглогодичное солнце — более 300 ясных дней в году\n"
            "• Burj Khalifa, Palm Jumeirah, Dubai Mall, Museum of the Future\n"
            "• Развитая инфраструктура — метро, такси, Careem, RTA\n"
            "• Удобный хаб Emirates — прямые рейсы в 150+ стран\n"
            "• Безопасность и высокий уровень сервиса\n\n"
            "Для инвесторов стабильный поток туристов означает устойчивый спрос "
            "на краткосрочную аренду недвижимости."
        ),
        "hashtags": ["#DubaiTourism", "#Travel", "#UAE", "#IDIGOV"],
        "content_type": "general_dubai",
    },
    {
        "title_ru": "Визы в ОАЭ: обзор вариантов для жизни и работы",
        "body_ru": (
            "ОАЭ предлагают несколько путей для долгосрочного проживания — "
            "выбор зависит от ваших целей.\n\n"
            "Основные варианты:\n"
            "• Employment Visa — через работодателя, срок 2 года\n"
            "• Investor Visa — через создание компании, 2–3 года\n"
            "• Property Visa — при покупке недвижимости от 750,000 AED, 2 года\n"
            "• Golden Visa — 10 лет при инвестициях от 2 млн AED\n"
            "• Freelance Visa — для самозанятых специалистов, 1–3 года\n"
            "• Retirement Visa — для людей 55+, 5 лет\n\n"
            "Наши специалисты помогут выбрать оптимальный вариант под вашу "
            "ситуацию и сопроводят весь процесс оформления."
        ),
        "hashtags": ["#UAEVisa", "#Residency", "#Dubai", "#IDIGOV"],
        "content_type": "general_dubai",
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # Load existing titles to stay idempotent
        result = await db.execute(select(FallbackPost.title_ru))
        existing = {row[0] for row in result.fetchall()}

        inserted = 0
        skipped = 0

        for post in SEED_POSTS:
            if post["title_ru"] in existing:
                skipped += 1
                continue

            fb = FallbackPost(
                title_ru=post["title_ru"],
                body_ru=post["body_ru"],
                hashtags=json.dumps(post["hashtags"], ensure_ascii=False),
                content_type=post["content_type"],
                is_active=True,
            )
            db.add(fb)
            inserted += 1

        await db.commit()

        print(f"Seeded fallback_posts: +{inserted} new, {skipped} already present.")
        print(f"Total evergreen posts now available: {inserted + skipped}")


if __name__ == "__main__":
    asyncio.run(main())
