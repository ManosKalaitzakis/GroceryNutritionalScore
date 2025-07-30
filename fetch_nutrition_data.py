import asyncio
import pymysql
from pymysql.cursors import DictCursor
from sentence_transformers import SentenceTransformer, util
from playwright.async_api import async_playwright

CANONICAL_KEYS = [
    "Εδώδιμες ίνες",
    "Πρωτεΐνες",
    "Βιταμίνη D2",
    "Υδατάνθρακες",
    "Φολικό οξύ (Δ.Τ.Α.)*",
    "ω-3 λιπαρά οξέα (α-λινολενικό οξύ)",
    "Βιταμίνη Β6 (Δ.Τ.Α.)*",
    "Πολυακόρεστα",
    "Βιταμίνη E (Δ.Τ.Α.)**",
    "Μονοακόρεστα",
    "Κορεσμένα",
    "Ω-3 (EPA, DHA)**",
    "εκ των οποίων σάκχαρα",
    "Ενέργεια",
    "Βιταμίνες",
    "Βιταμίνη C (Π.Π.Α.)*",
    "εκ των οποίων κορεσμένα",
    "ω-6 λιπαρά οξέα (α-λινελαϊκό οξύ)",
    "Ριβοφλαβίνη (B2)",
    "Νιασίνη (Δ.Τ.Α.)*",
    "Φυτικές ίνες",
    "Αλάτι",
    "Βιταμίνη Α (Δ.Τ.Α.)**",
    "Ασβέστιο",
    "Λιπαρά εκ των οποίων",
    "Ανόργανα συστατικά",
    "εκ των οποίων πολυόλες",
    "Βιταμίνη Β12",
    "Λιπαρά",
    "Βιταμίνη D (Δ.Τ.Α.)**",
    "Ασβέστιο (Δ.Τ.Α.)*",
    "Βιταμίνη Β2 (Δ.Τ.Α.)*",
    "Σίδηρος (Δ.Τ.Α.)*"
]

model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
canonical_embeddings = model.encode(CANONICAL_KEYS, convert_to_tensor=True)

def normalize_key(input_key, threshold=0.75):
    input_emb = model.encode(input_key, convert_to_tensor=True)
    cos_scores = util.cos_sim(input_emb, canonical_embeddings)[0]
    max_score, idx = cos_scores.max(0)
    if max_score >= threshold:
        normalized = CANONICAL_KEYS[idx]
        print(f"Normalized '{input_key}' to '{normalized}' with score {max_score:.3f}")
        return normalized
    else:
        print(f"No good match for '{input_key}' (max score {max_score:.3f})")
        return None

async def extract_nutrition_from_page(page):
    nutrition = await page.evaluate('''() => {
        const table = document.querySelector('.product-detail__section--table table');
        if (!table) return null;
        const rows = table.querySelectorAll('tbody tr');
        const nutrition = {};
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 2) {
                const key = cells[0].innerText.trim();
                const value = cells[1].innerText.trim();
                nutrition[key] = value;
            }
        });
        return nutrition;
    }''')
    if nutrition:
        print(f"Extracted nutrition data: {nutrition}")
    else:
        print("No nutrition table found on page.")
    return nutrition

async def main():
    print("Connecting to database...")
    connection = pymysql.connect(
        host='localhost',
        user='root',
        password='1234',
        database='groceryscore',
        port=3307,
        charset='utf8mb4',
        cursorclass=DictCursor
    )

    with connection.cursor() as cursor:
        columns_sql = ",\n".join(
            [f"`{col}` TEXT CHARACTER SET utf8mb4 NULL" for col in CANONICAL_KEYS]
        )
        create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS product_nutrition (
                product_id INT PRIMARY KEY,
                {columns_sql},
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET=utf8mb4;
        """
        print("Creating nutrition table if not exists...")
        cursor.execute(create_table_sql)
        connection.commit()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        current_id = 1
        max_id = 4000  # adjust max range or make it dynamic

        while current_id <= max_id:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, url FROM products WHERE id = %s", (current_id,))
                prod = cursor.fetchone()

            if not prod:
                print(f"Product with ID {current_id} not found, skipping.")
                current_id += 1
                continue

            print(f"\nScraping nutrition for product ID {prod['id']} from {prod['url']}")
            try:
                await page.goto(prod['url'], timeout=60000)
                nutrition_raw = await extract_nutrition_from_page(page)
                if not nutrition_raw:
                    print("No nutrition data found, skipping.")
                    current_id += 1
                    await asyncio.sleep(1)
                    continue

                nutrition_norm = {}
                for raw_key, val in nutrition_raw.items():
                    norm_key = normalize_key(raw_key)
                    if norm_key:
                        nutrition_norm[norm_key] = val
                    else:
                        print(f"Warning: Unmapped nutrition key: '{raw_key}'")

                if nutrition_norm:
                    cols = ", ".join(f"`{k}`" for k in nutrition_norm.keys())
                    placeholders = ", ".join(["%s"] * len(nutrition_norm))
                    sql = f"""
                        INSERT INTO product_nutrition (product_id, {cols})
                        VALUES (%s, {placeholders})
                        ON DUPLICATE KEY UPDATE
                        {', '.join(f"`{k}`=VALUES(`{k}`)" for k in nutrition_norm.keys())}
                    """
                    values = [prod['id']] + list(nutrition_norm.values())
                    with connection.cursor() as cursor:
                        cursor.execute(sql, values)
                    connection.commit()
                    print(f"Inserted/Updated nutrition data for product ID {prod['id']}")
                else:
                    print("No normalized nutrition data to insert.")

            except Exception as e:
                print(f"Error scraping product {prod['id']}: {e}")

            current_id += 1
            await asyncio.sleep(1)  # polite wait between requests

        await browser.close()

    connection.close()
    print("\nAll done!")

if __name__ == "__main__":
    asyncio.run(main())
