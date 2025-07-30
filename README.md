# GroceryNutritionalScore
🗂️ fetch_categories.py — Discover Product Categories

Role:
Scrapes all main and subcategories from the Sklavenitis website.

How it works:

    Connects to the Sklavenitis category page using requests and BeautifulSoup.

    Extracts:

        Parent category name (e.g., "Γαλακτοκομικά")

        Subcategory name (e.g., "Γάλα φρέσκο")

        Subcategory URL (fully resolved)

    Stores the results in a MySQL table named categories.

Database Table Created:

CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    parent_category VARCHAR(255),
    sub_category VARCHAR(255),
    url TEXT
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

🗂️ fetch_product_urls.py — Scrape Products per Category

Role:
Navigates each product category page, loads all products via infinite scroll, and extracts product info.

How it works:

    Uses Playwright in headless Chromium to fully load category pages.

    Performs automated scrolling to trigger dynamic product loading.

    For each product, it extracts:

        name (title of the product)

        price (as displayed on the site)

        url (link to the product page)

        image_url (main product image)

    Stores results into the MySQL table products.

Database Table Created:

CREATE TABLE products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name TEXT CHARACTER SET utf8mb4 NOT NULL,
    price VARCHAR(255) CHARACTER SET utf8mb4 NOT NULL,
    url TEXT CHARACTER SET utf8mb4 NOT NULL,
    image_url TEXT CHARACTER SET utf8mb4 DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

Input Dependency:
Reads all category URLs from the categories table (populated by fetch_categories.py).

Output:
✅ products table populated with raw product-level metadata.

Special Notes:

    Includes a scroll_to_load_all_products function to handle infinite scrolling behavior.



🗂️ fetch_nutrition_data.py — Extract and Normalize Nutrition Fields

Role:
Extracts nutrition tables from product pages and maps inconsistent keys to standardized field names using semantic similarity.

How it works:

    Loads product pages via Playwright, targeting .product-detail__section--table.

    Extracts raw nutrition data as key-value pairs (e.g., "Ενέργεια": "120 kcal").

    Uses SentenceTransformer (paraphrase-multilingual-MiniLM-L12-v2) to semantically match raw field names to a canonical set like:

        "εκ των οποίων σάκχαρα" → normalized to "εκ των οποίων σάκχαρα"

        "Βιταμίνη C" → normalized to "Βιταμίνη C (Π.Π.Α.)*"

    Populates a product_nutrition table where each canonical nutrient is a column.

Database Table Created:

CREATE TABLE product_nutrition (
    product_id INT PRIMARY KEY,
    `Εδώδιμες ίνες` TEXT,
    `Πρωτεΐνες` TEXT,
    `Βιταμίνη D2` TEXT,
    ...
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET=utf8mb4;

Input Dependency:

    Reads from the products table (created by fetch_product_urls.py).

    Processes product pages based on their url.

Output:
✅ product_nutrition table filled with standardized nutrient values per product.

Highlights:

    ⚙️ Uses multilingual semantic matching instead of brittle keyword matching.

    🔍 Automatically handles fuzzy field names and Greek label variations.

    🔁 ON DUPLICATE KEY UPDATE ensures re-runs won’t duplicate rows.



🗂️ calculate_scores.py — Nutrition-Based Scoring

Role:
Calculates a nutrition score and assigns a letter grade (A–E) to each product that has valid nutritional information.

How it works:

    Connects to the product_nutrition table.

    Uses a Nutri-Score–inspired algorithm, combining:

        Negative factors: energy (kJ), sugar, saturated fat, salt.

        Positive factors: fiber, protein.

    Normalizes values using domain-based upper thresholds.

    Computes a final score on a scale of 0–100.

    Assigns a letter grade:

        A = 80–100 (best)

        B = 60–79

        C = 40–59

        D = 20–39

        E = 0–19 (worst)

Database Table Created:

CREATE TABLE product_score (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    nutrition_id INT NOT NULL,
    score INT NOT NULL,
    grade CHAR(1) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY (product_id, nutrition_id),
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (nutrition_id) REFERENCES product_nutrition(product_id)
) CHARACTER SET=utf8mb4;

Dependencies:

    Requires product_nutrition table to already exist and be populated.

    Relies on proper text-to-float conversion (safe_float) for Greek-labeled nutrition terms.

Output:
✅ product_score table with one row per valid product, including:

    score: integer (0–100)

    grade: letter A–E

Why it matters:
This is the core ranking logic of the system, enabling downstream filtering, recommendation, and health comparison across products.


🗂️ product_statistics.py — Visualize Nutrition Score Insights

Role:
Generates statistical summaries and visualizations based on computed nutrition scores and nutritional values.

How it works:

    Connects to the groceryscore MySQL database via SQLAlchemy.

    Performs SQL queries to join and analyze data from:

        products

        product_score

        product_nutrition

    Visualizes key distributions using matplotlib.

Visualizations Generated:

    Grade Distribution (Bar Chart)
    Shows how products are distributed across grades (A, B, C, etc.).

        Source: product_score.grade

        Useful for seeing if most products are high- or low-rated.

    Nutrition Score Histogram
    Displays a histogram of product scores.

        Useful for understanding score spread and distribution density.

    Top 10 Products (Horizontal Bar Chart)
    Highlights the highest-ranking products based on score.

        Includes product names and score values.

Additional Output:

    df_top40: A Pandas DataFrame of the 40 top-scoring products.

    Printed in the terminal with product name, score, energy, sugar, protein, salt, etc.

Dependencies:

    matplotlib

    pandas

    sqlalchemy

Input Dependency:

    Assumes score data already exists in the product_score table, and nutrition fields are populated in product_nutrition.

Output:
✅ Three clear visualizations + a printed table of top-performing products for evaluation.


🧭 dashboard.py — Streamlit Nutrition & Price Intelligence Dashboard

Role:
An interactive, filterable dashboard that visualizes health scores, nutritional values, and price fluctuations of grocery products scraped from Sklavenitis. Built with Streamlit, it allows real-time exploration of thousands of items using fuzzy search, multivariate filtering, and visualizations.
🧰 Core Features
🔍 Filter Panel (Sidebar):

    Text Search: Fuzzy-matched by product name (RapidFuzz partial_ratio), threshold = 85%.

    Grade Filter: Multiselect dropdown to narrow products by assigned health grade (A–E).

    Category Filter: Mapped from Greeklish URLs to Greek names (e.g., "freska-froyta-lachanika" → "Φρέσκα Φρούτα & Λαχανικά").

    Price Range: Slider dynamically scaled from dataset min/max.

    Energy (kcal): Filter by calories per 100g (numeric slider).

🖼️ Product Cards Grid:

    Rendered in rows of 5 responsive cards using st.columns.

    Each card includes:

        Product image with zoom-on-hover effect via custom CSS.

        Name and price (parsed main number + unit).

        Health Score (0–100) and Grade (A–E).

        kcal per 100g and estimated total kcal per package (if weight detected from name).

        Direct link to product on the retailer’s website.

📉 Price Change Explorer:

    Toggle button to switch view to recent price change (%) analysis.

    Compares most recent prices from product_prices with older snapshots.

    Calculates and visualizes price deltas using SQL WITH clause and joins.

    Clean dataframe presentation of:
    Product ID, Name, Old Price, New Price, % Change.

📊 Visualizations:

    Grade Distribution: Bar chart showing current grade spread (A–E).

    Score Histogram: Custom matplotlib histogram for detailed health score density.

🧠 Logic Highlights

    Image Enhancement: Automatically replaces /Product/ in image URLs with /1600x1600/ for high-res rendering.

    Kcal Extraction: Regex extracts kcal from energy string (e.g. "80 kcal" → 80).

    Weight Parsing: Estimates weight from product name (e.g. "250g" in title).

    Kcal Total: Computes estimated total kcal per package:
    kcal_total = kcal_per_100g × (weight_g / 100)

    Price Parsing: Converts text-formatted prices (e.g., "4,73 € /τεμ.") into floats with safe fallback logic.

    Caching:
    @st.cache_data(ttl=600) used for both:

        Nutrition product dataset.

        Price changes query.
        Keeps app responsive while avoiding stale SQL loads.

    Session Control:
    st.session_state.show_price_changes toggles between nutrition view and price analytics panel.

🧩 Tech Stack
Layer	Tool / Library
UI / Frontend	Streamlit + Custom CSS
Data Analysis	Pandas, Regex, RapidFuzz
Charting	Matplotlib
Database	MySQL via SQLAlchemy
Image Handling	Dynamic URL substitution
Localization	Greek category mapping
🏗️ Output: Interactive Web Dashboard

    Filters over 4000+ scraped Greek grocery items.

    Allows consumers or analysts to:

        Spot high-health, low-price foods

        Detect pricing anomalies over time

        Explore tradeoffs between score, calories, and cost



🗂️ update_prices.py — Track Price Changes Over Time

Role:
Periodically re-scrapes all product listings from Sklavenitis and logs historical price data.

How it works:

    Uses Playwright to fully scroll and load all products in each category page.

    For each product found:

        Checks if it already exists in the products table (by URL).

        If not found, inserts the new product (name, price, image, URL).

        Regardless of existence, appends a price snapshot to product_prices.


CREATE TABLE product_prices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    price VARCHAR(255),
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

Why it matters:
Tracks price evolution over time to enable:

    Inflation analysis

    Discount monitoring

    Price volatility tracking

    Product re-listing alerts

Dependencies:

    playwright

    pymysql

    asyncio

Input Dependency:
Relies on previously populated categories table to iterate through all product categories.

Output:
✅ Inserts new product records and adds a timestamped entry into product_prices on every run.
