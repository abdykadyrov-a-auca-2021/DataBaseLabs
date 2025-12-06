from ddgs import DDGS
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
from urllib.parse import urlparse, urlunparse

# --- Настройки подключения к БД ---
PG_HOST = "localhost"
PG_DB = "alumni_db"          
PG_USER = "azamatabdykadyrov"
PG_PASSWORD = "abdy"
PG_PORT = 5432


def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT,
    )


def normalize_linkedin_url(raw_url: str | None) -> str | None:
    """Приводим ссылку к виду https://www.linkedin.com/..."""
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


def find_linkedin_url(full_name: str) -> str | None:
    """Ищем LinkedIn-профиль через DuckDuckGo по ФИО."""
    queries = [
        f'"{full_name}" LinkedIn',
        f'"{full_name}" LinkedIn Kyrgyzstan',
        f'"{full_name}" LinkedIn AUCA',
        f'{full_name} LinkedIn',
    ]

    with DDGS() as ddgs:
        for q in queries:
            print(f"   🔎 DuckDuckGo: {q}")
            try:
                results = ddgs.text(q, max_results=10)
            except Exception as e:
                print(f"   ❌ Ошибка DDGS: {e}")
                continue

            for item in results:
                url = item.get("href") or item.get("url")
                if not url:
                    continue

                if "linkedin.com" in url:
                    clean = normalize_linkedin_url(url)
                    if clean:
                        print(f"   ✅ Найдено: {clean}")
                        return clean

    print("   ⚠ Профиль не найден")
    return None


def main():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    # Берём выпускников без linkedin_profile_id
    cur.execute(
        """
        SELECT id, first_name, last_name
        FROM graduate
        WHERE linkedin_profile_id IS NULL
        ORDER BY id;
        """
    )
    graduates = cur.fetchall()

    if not graduates:
        print("Нет выпускников без LinkedIn профиля. Нечего искать.")
        cur.close()
        conn.close()
        return

    print(f"Найдено выпускников без профиля: {len(graduates)}")

    for row in graduates:
        grad_id = row["id"]
        first_name = row["first_name"]
        last_name = row["last_name"]
        full_name = f"{first_name} {last_name}"

        print(f"\n🎓 Выпускник #{grad_id}: {full_name}")

        url = find_linkedin_url(full_name)

        if url:
            # 1) создаём запись в linkedin_profile
            cur.execute(
                """
                INSERT INTO linkedin_profile (url)
                VALUES (%s)
                RETURNING id;
                """,
                (url,),
            )
            profile_id = cur.fetchone()[0]

            # 2) привязываем профиль к выпускнику
            cur.execute(
                """
                UPDATE graduate
                SET linkedin_profile_id = %s
                WHERE id = %s;
                """,
                (profile_id, grad_id),
            )

            # 3) логируем успешный поиск
            cur.execute(
                """
                INSERT INTO scrape_log (graduate_id, status, message, scraped_at)
                VALUES (%s, 'ok', %s, %s);
                """,
                (grad_id, f"LinkedIn profile found: {url}", datetime.utcnow()),
            )

            conn.commit()
            print(f"   ✅ Сохранено в БД. linkedin_profile_id = {profile_id}")

        else:
            # логируем ошибку (status = 'error', а не 'warning'!)
            cur.execute(
                """
                INSERT INTO scrape_log (graduate_id, status, message, scraped_at)
                VALUES (%s, 'error', %s, %s);
                """,
                (grad_id, "No LinkedIn profile found", datetime.utcnow()),
            )
            conn.commit()
            print("   ❌ Профиль не найден, записали в scrape_log (error).")

    cur.close()
    conn.close()
    print("\n🎉 Готово! Поиск профилей завершён.")


if __name__ == "__main__":
    main()
