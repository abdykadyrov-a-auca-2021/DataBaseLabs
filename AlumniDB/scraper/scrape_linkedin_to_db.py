import time
from urllib.parse import urlparse, urlunparse

import psycopg2
from psycopg2.extras import DictCursor

from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


# ===== НАСТРОЙКИ PostgreSQL =====
PG_HOST = "localhost"
PG_DB = "alumni_db"
PG_USER = "azamatabdykadyrov"
PG_PASSWORD = "abdy"   
PG_PORT = 5432


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        database=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT,
    )


def normalize_linkedin_url(raw_url: str | None) -> str | None:
    """
    Делаем из kg.linkedin.com → www.linkedin.com и обрезаем хвосты ?... / #...
    """
    if not isinstance(raw_url, str):
        return None

    raw_url = raw_url.strip()
    if not raw_url:
        return None

    parsed = urlparse(raw_url)
    if "linkedin.com" not in parsed.netloc:
        return None

    parsed = parsed._replace(netloc="www.linkedin.com")
    clean = urlunparse(parsed)
    clean = clean.split("?")[0].split("#")[0]
    return clean


def get_first_text(driver, selectors: list[str]) -> str | None:
    """
    Пробуем несколько CSS-селекторов подряд, возвращаем текст первого найденного.
    """
    for sel in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            txt = el.text.strip()
            if txt:
                return txt
        except Exception:
            continue
    return None


# ===== ОСНОВНАЯ ЛОГИКА =====

def main():
    # 1. Берём из БД всех выпускников с профилем, у кого нет headline/location
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    g.id           AS graduate_id,
                    g.first_name,
                    g.last_name,
                    lp.id          AS profile_id,
                    lp.url         AS profile_url,
                    lp.headline,
                    lp.location
                FROM graduate AS g
                JOIN linkedin_profile AS lp
                    ON g.linkedin_profile_id = lp.id
                WHERE lp.headline IS NULL
                   OR lp.location IS NULL
                ORDER BY g.id;
                """
            )
            rows = cur.fetchall()

    if not rows:
        print("✅ Нет выпускников, которых нужно скрейпить — все профили уже заполнены.")
        return

    print(f"Найдено профилей для скрейпинга: {len(rows)}")

    # 2. Запускаем браузер
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)

    # 3. Логин в LinkedIn вручную
    print("\n🔑 Открываю LinkedIn — авторизуйся вручную.")
    driver.get("https://www.linkedin.com/login")
    print("⚠️ Введи логин/пароль, пройди 2FA/капчу, чтобы открылась главная LinkedIn.")
    input("Когда полностью залогинишься — нажми Enter в ТЕРМИНАЛЕ... ")

    # 4. Скрейпим каждый профиль
    with get_connection() as conn:
        with conn.cursor() as cur:
            for row in rows:
                grad_id = row["graduate_id"]
                full_name = f"{row['first_name']} {row['last_name']}"
                profile_id = row["profile_id"]
                raw_url = row["profile_url"]
                url = normalize_linkedin_url(raw_url)

                print(f"\n🎓 Выпускник #{grad_id}: {full_name}")
                print(f"   URL: {url}")

                if not url:
                    print("   ⚠️ Некорректный URL, пишем в лог как error.")
                    cur.execute(
                        """
                        INSERT INTO scrape_log (graduate_id, status, message, scraped_at)
                        VALUES (%s, 'error', %s, NOW());
                        """,
                        (grad_id, "Invalid LinkedIn URL"),
                    )
                    conn.commit()
                    continue

                try:
                    driver.get(url)
                    time.sleep(5)

                    # лёгкий скролл вниз, чтобы подгрузился профиль
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
                    time.sleep(3)

                    # имя / headline / location
                    profile_name = get_first_text(driver, [
                        "h1.text-heading-xlarge",
                        "h1"
                    ])

                    headline = get_first_text(driver, [
                        "div.text-body-medium.break-words",
                        "div.text-body-medium"
                    ])

                    location = get_first_text(driver, [
                        "span.text-body-small.inline.t-black--light.break-words",
                        "span.t-14.t-normal.t-black--light"
                    ])

                    print(f"   Имя в профиле: {profile_name}")
                    print(f"   Headline     : {headline}")
                    print(f"   Локация      : {location}")

                    if not headline and not location:
                        print("   ⚠️ Не удалось вытащить данные, пишем not_found.")
                        cur.execute(
                            """
                            INSERT INTO scrape_log (graduate_id, status, message, scraped_at)
                            VALUES (%s, 'not_found', %s, NOW());
                            """,
                            (grad_id, "Unable to parse LinkedIn profile"),
                        )
                        conn.commit()
                        continue

                    # 5. Обновляем linkedin_profile
                    cur.execute(
                        """
                        UPDATE linkedin_profile
                        SET headline = COALESCE(%s, headline),
                            location = COALESCE(%s, location),
                            last_scraped_at = NOW()
                        WHERE id = %s;
                        """,
                        (headline, location, profile_id),
                    )

                    # 6. Логируем успех
                    cur.execute(
                        """
                        INSERT INTO scrape_log (graduate_id, status, message, scraped_at)
                        VALUES (%s, 'ok', %s, NOW());
                        """,
                        (grad_id, f"Profile scraped: {url}"),
                    )

                    conn.commit()
                    print("   ✅ Профиль обновлён и залогирован (status = 'ok').")

                except Exception as e:
                    print(f"   ❌ Ошибка при скрейпе: {e}")
                    cur.execute(
                        """
                        INSERT INTO scrape_log (graduate_id, status, message, scraped_at)
                        VALUES (%s, 'error', %s, NOW());
                        """,
                        (grad_id, f"Exception during scraping: {e}"),
                    )
                    conn.commit()

                time.sleep(4)

    driver.quit()
    print("\n🎉 Скрейпинг профилей завершён.")


if __name__ == "__main__":
    main()
