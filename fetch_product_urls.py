import asyncio
from playwright.async_api import async_playwright
import pymysql

async def scroll_to_load_all_products(page):
    last_height = 0
    same_height_count = 0
    while same_height_count < 5:
        current_height = await page.evaluate("document.body.scrollHeight")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        print(f"Scrolled to height: {current_height}")

        if current_height != last_height:
            last_height = current_height
            same_height_count = 0
        else:
            same_height_count += 1

        await asyncio.sleep(0.8)  # increased wait time here
    print("Finished scrolling.")


async def scrape_products_from_url(page, url):
    print(f"Opening page: {url}")
    await page.goto(url, timeout=60000)

    print("Scrolling to load all products...")
    await scroll_to_load_all_products(page)

    try:
        await page.wait_for_selector(".product", timeout=10000)
    except Exception:
        print("Warning: No products found or timeout.")

    count = await page.evaluate('document.querySelectorAll(".product").length')
    print(f"Found {count} products")

    products = await page.evaluate('''() => {
        const prods = [...document.querySelectorAll(".product")];
        return prods.map(product => {
            const nameElem = product.querySelector("h4.product__title a");
            const name = nameElem?.innerText.trim() || null;

            const urlPart = nameElem?.getAttribute("href") || null;
            const fullUrl = urlPart ? new URL(urlPart, "https://www.sklavenitis.gr").href : null;

            const priceElem = product.querySelector(".price[data-price]") || product.querySelector(".main-price .price");
            const price = priceElem?.innerText.trim() || null;

            const imgElem = product.querySelector("figure.product__figure a img");
            const imgSrc = imgElem?.getAttribute("src") || null;
            const fullImgUrl = imgSrc ? (imgSrc.startsWith("http") ? imgSrc : new URL(imgSrc, "https://www.sklavenitis.gr").href) : null;

            return (name && fullUrl && price) ? {name, price, url: fullUrl, image_url: fullImgUrl} : null;
        }).filter(Boolean);
    }''')
    return products

async def main():
    # Connect to DB
    connection = pymysql.connect(
        host='localhost',
        user='root',
        password='1234',
        database='groceryscore',
        port=3307,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    with connection.cursor() as cursor:
        # Create products table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name TEXT CHARACTER SET utf8mb4 NOT NULL,
                price VARCHAR(255) CHARACTER SET utf8mb4 NOT NULL,
                url TEXT CHARACTER SET utf8mb4 NOT NULL,
                image_url TEXT CHARACTER SET utf8mb4 DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        connection.commit()

        # Fetch all categories URLs from your table
        cursor.execute("SELECT id, parent_category, sub_category, url FROM categories")
        categories = cursor.fetchall()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for cat in categories:
            print(f"\nScraping category {cat['id']}: {cat['parent_category']} > {cat['sub_category']}")
            products = await scrape_products_from_url(page, cat['url'])
            print(f"Extracted {len(products)} products from category {cat['sub_category']}")

            with connection.cursor() as cursor:
                for i, product in enumerate(products, start=1):
                    cursor.execute(
                        """
                        INSERT INTO products (name, price, url, image_url)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (product['name'], product['price'], product['url'], product['image_url'])
                    )
                    if i % 10 == 0 or i == len(products):
                        print(f"Inserted {i}/{len(products)} products")

                connection.commit()

        await browser.close()

    connection.close()
    print("\n✅ All categories scraped and products inserted.")

asyncio.run(main())
