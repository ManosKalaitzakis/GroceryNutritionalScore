import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text
import re
from rapidfuzz import fuzz

# === CSS styling ===
st.markdown(
    """
    <style>
    body {
        background-color: #f7f7f7 !important;
    }
    .stApp {
        background-color: #f7f7f7 !important;
    }
    section[data-testid="stSidebar"] {
        background-color: #f7f5f3;
    }
    h1, h2, h3, h4, h5, h6, .css-10trblm, .css-hxt7ib, .css-1d391kg {
        color: #111 !important;
    }
    .stTextInput > label, .stSlider > label, .stMultiSelect > label {
        color: #111 !important;
        font-weight: 600 !important;
    }
    .product-img {
        width: 100%;
        max-width: 320px;
        height: 240px;
        object-fit: contain;
        transition: transform 0.3s ease;
        cursor: pointer;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .product-img:hover {
        transform: scale(3.3);
        z-index: 310;
        position: relative;
        box-shadow: 0 8px 20px rgba(0,0,0,0.3);
    }
    </style>
    """,
    unsafe_allow_html=True
)

greeklish_to_greek = {
    "galata-rofimata-chymoi-psygeioy": "Γάλατα, Ροφήματα & Χυμοί Ψυγείου",
    "giaoyrtia-kremes-galaktos-epidorpia-psygeioy": "Γιαούρτια, Κρέμες & Γαλακτοκομικά Επιδόρπια",
    "katepsygmena": "Κατεψυγμένα",
    "kava": "Κάβα",
    "mpiskota-sokolates-zacharodi": "Μπισκότα, Σοκολάτες & Ζαχαρώδη",
    "orektika-delicatessen": "Ορεκτικά & Ντελικατέσεν",
    "trofima-pantopoleioy": "Τρόφιμα Παντοπωλείου",
    "turokomika-futika-anapliromata": "Τυροκομικά & Φυτικά Αντικαταστάτες",
    "vrefikes-paidikes-trofes": "Βρεφικές & Παιδικές Τροφές",
    "xiroi-karpoi-snak": "Ξηροί Καρποί & Σνακ",
    "ayga-voytyro-nopes-zymes-zomoi": "Αυγά, Βούτυρο, Νωπές Ζύμες & Ζωμοί",
    "eidi-artozacharoplasteioy": "Είδη Αρτοζαχαροπλαστείου",
    "eidi-proinoy-rofimata": "Είδη Πρωινού & Ροφήματα",
    "etoima-geymata": "Έτοιμα Γεύματα",
    "freska-froyta-lachanika": "Φρέσκα Φρούτα & Λαχανικά",
    "fresko-kreas": "Φρέσκο Κρέας",
    "fresko-psari-thalassina": "Φρέσκο Ψάρι & Θαλασσινά",
    "allantika":"Αλλαντικά",
    "anapsyktika-nera-chymoi":"Χυμοί-Αναψυκτικά !!🍼",
}

st.set_page_config(layout="wide")

# === GLOBAL ENGINE ===
engine = create_engine("mysql+pymysql://root:1234@localhost:3307/groceryscore?charset=utf8mb4")

@st.cache_data(ttl=600)
def load_price_changes():
    query = """
    WITH price_changes AS (
      SELECT
        pr.product_id,
        p.name,
        p.price AS old_price,
        pr.price AS new_price,
        		p.image_url,
        ROUND((
          (
            CAST(REPLACE(REGEXP_REPLACE(TRIM(pr.price), '[^0-9.,]', ''), ',', '.') AS DECIMAL(10, 2)) -
            CAST(REPLACE(REGEXP_REPLACE(TRIM(p.price), '[^0-9.,]', ''), ',', '.') AS DECIMAL(10, 2))
          ) / NULLIF(CAST(REPLACE(REGEXP_REPLACE(TRIM(p.price), '[^0-9.,]', ''), ',', '.') AS DECIMAL(10, 2)), 0)
        ) * 100, 2) AS pct_change
      FROM product_prices pr
      JOIN (
          SELECT product_id, MAX(captured_at) AS max_captured
          FROM product_prices
          GROUP BY product_id
      ) latest ON pr.product_id = latest.product_id AND pr.captured_at = latest.max_captured
      JOIN products p ON p.id = pr.product_id
      WHERE TRIM(REPLACE(p.price, '€', '')) <> TRIM(REPLACE(pr.price, '€', ''))
    )
    SELECT * FROM price_changes
    ORDER BY pct_change ASC;
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    return df

@st.cache_data(ttl=600)
def load_data():
    query = """
    SELECT 
        p.id AS product_id,
        p.name,
        p.price,
        p.url,
        p.image_url,
        ps.score,
        ps.grade,
        pn.Ενέργεια AS energy,
        pn.Πρωτεΐνες AS protein,
        pn.Υδατάνθρακες AS carbs,
        pn.`εκ των οποίων σάκχαρα` AS sugars,
        pn.Αλάτι AS salt,
        pn.`Φυτικές ίνες` AS fiber
    FROM product_score ps
    JOIN products p ON ps.product_id = p.id
    JOIN product_nutrition pn ON ps.nutrition_id = pn.product_id
    ORDER BY ps.score DESC
    LIMIT 4000;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    def convert_image_url(url):
        if not url:
            return url
        return url.replace('/Product/', '/1600x1600/', 1)
    df['image_url'] = df['image_url'].apply(convert_image_url)

    def extract_category(url):
        if not url:
            return ""
        s = url.replace("https://www.sklavenitis.gr/", "")
        parts = s.split('/')
        return parts[0] if parts else ""
    df['main_category'] = df['url'].apply(extract_category)

    def extract_kcal(energy_str):
        if not energy_str:
            return 0
        match = re.search(r"(\d+)\s?kcal", energy_str, re.IGNORECASE)
        return int(match.group(1)) if match else 0
    df['kcal'] = df['energy'].apply(extract_kcal)

    def extract_weight(name):
        if not name:
            return 0
        match = re.search(r"(\d+)\s*(g|gr)", name, re.IGNORECASE)
        return int(match.group(1)) if match else 0
    df['weight_g'] = df['name'].apply(extract_weight)

    df['kcal_total'] = (df['kcal'] * df['weight_g']) / 100
    df['kcal_total'] = df['kcal_total'].round(1).fillna(0)

    return df

# Load main data early to avoid multiple DB calls
df = load_data()

# Use session state to keep toggle state
if 'show_price_changes' not in st.session_state:
    st.session_state.show_price_changes = False

st.title("Nutrition Dashboard")

if st.session_state.show_price_changes:
    if st.button("Back to Product Dashboard"):
        st.session_state.show_price_changes = False

    st.header("Product Price Changes (%)")
    price_changes_df = load_price_changes()
    if price_changes_df.empty:
        st.info("No price changes detected.")
    else:
        price_changes_df['old_price'] = price_changes_df['old_price'].astype(str)
        price_changes_df['new_price'] = price_changes_df['new_price'].astype(str)
        st.dataframe(price_changes_df.rename(columns={
            'product_id': 'Product ID',
            'name': 'Product Name',
            'old_price': 'Old Price',
            'new_price': 'New Price',
            'pct_change': '% Change'
        }), use_container_width=True)

else:
    if st.button("Show % Price Changes"):
        st.session_state.show_price_changes = True

    # Convert price to numeric for filtering (e.g. "4,73 € /τεμ.")
    def price_to_float(price_str):
        if not price_str:
            return 0.0
        price_clean = re.findall(r"[\d.,]+", price_str)
        if not price_clean:
            return 0.0
        price_num = price_clean[0].replace(',', '.')
        try:
            return float(price_num)
        except:
            return 0.0

    df['price_num'] = df['price'].apply(price_to_float)

    # Convert score to numeric and drop invalid rows
    df['score'] = pd.to_numeric(df['score'], errors='coerce')
    df = df.dropna(subset=['score'])

    # --- Sidebar filters ---
    st.sidebar.header("Filters")
    search_text = st.sidebar.text_input("Αναζήτηση με τίτλο προϊόντος (π.χ. γάλα)")

    grades = sorted(df['grade'].dropna().unique())
    selected_grades = st.sidebar.multiselect("Filter by Grade", options=grades, default=grades)

    # Map categories to their Greek names (for display)
    categories = sorted(df['main_category'].dropna().unique())
    category_display_map = {cat: greeklish_to_greek.get(cat, cat) for cat in categories}
    display_to_key = {v: k for k, v in category_display_map.items()}

    # Show dropdown with Greek names
    selected_display = st.sidebar.multiselect("Κατηγορία", options=category_display_map.values(), default=[])

    # Convert back to Greeklish keys for filtering
    selected_categories = [display_to_key[name] for name in selected_display]

    min_price, max_price = float(df['price_num'].min()), float(df['price_num'].max())
    price_range = st.sidebar.slider("Price Range (€)", min_price, max_price, (min_price, max_price))

    min_kcal, max_kcal = int(df['kcal'].min()), int(df['kcal'].max())
    kcal_range = st.sidebar.slider("Energy (kcal)", min_kcal, max_kcal, (min_kcal, max_kcal))

    # --- Apply filters ---
    filtered_df = df[
        (df['grade'].isin(selected_grades)) &
        ((df['main_category'].isin(selected_categories)) | (len(selected_categories) == 0)) &
        (df['price_num'] >= price_range[0]) &
        (df['price_num'] <= price_range[1]) &
        (df['kcal'] >= kcal_range[0]) &
        (df['kcal'] <= kcal_range[1])
    ].copy()

    # Apply fuzzy name filtering only if text is given
    if search_text.strip():
        filtered_df['search_score'] = filtered_df['name'].apply(lambda x: fuzz.partial_ratio(search_text.lower(), x.lower()) if pd.notnull(x) else 0)
        filtered_df = filtered_df[filtered_df['search_score'] >= 85]  # tune threshold as needed
        filtered_df = filtered_df.sort_values(by='search_score', ascending=False)

    st.write(f"Showing {len(filtered_df)} products after filtering")

    # Flag to hide energy when kcal filter is active (non-default range)
    energy_filter_active = (kcal_range[0] != min_kcal or kcal_range[1] != max_kcal)

    def render_product_cards(df_to_render):
        n_cols = 5
        rows = (len(df_to_render) + n_cols - 1) // n_cols

        for row_idx in range(rows):
            cols = st.columns(n_cols, gap="small")
            for col_idx in range(n_cols):
                idx = row_idx * n_cols + col_idx
                if idx >= len(df_to_render):
                    break
                row = df_to_render.iloc[idx]

                price_main = re.findall(r"[\d.,]+", row['price'])
                price_main = price_main[0] if price_main else ""
                price_units = row['price'].replace(price_main, '').strip()

                if row['kcal'] > 0:
                    energy_text = f'<div style="color: #4CAF50; font-weight: 600;">{row["kcal"]} kcal / 100g<br>'
                    if row['kcal_total'] > 0:
                        energy_text += f'~{row["kcal_total"]} kcal για {row["weight_g"]}g'
                    energy_text += '</div>'
                else:
                    energy_text = '<div style="color: #999;">Energy: Null</div>'

                card_html = f"""
                <div style="
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    padding: 10px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    background-color: #fff;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    text-align: center;
                    color: #000;
                    height: 500px;
                    justify-content: space-between;
                    margin-bottom: 20px;
                ">
                    <img src="{row['image_url']}" class="product-img" style="
                        width: 100%;
                        max-width: 320px;
                        height: 240px;
                        object-fit: contain;
                        margin-bottom: 1px;
                    "/>
                    <div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 8px; min-height: 48px;">{row['name']}</div>
                    <div style="font-size: 1rem; color: #555; margin-bottom: 6px;">
                        <span>{price_main}</span>
                        <span style="background: #FFA726; color: #fff; padding: 2px 6px; border-radius: 5px; font-weight: 700; margin-left: 5px;">
                            {price_units}
                        </span>
                    </div>
                    <div style="font-size: 1.3em; color: #4CAF50; font-weight: 700;">
                        Score: {row['score']:.1f} &nbsp;&nbsp; Grade: {row['grade']}
                    </div>
                    {energy_text}
                    <a href="{row['url']}" target="_blank" style="
                        margin-top: 3px;
                        padding: 6px 12px;
                        background-color: #0288D1;
                        color: white;
                        border-radius: 12px;
                        text-decoration: none;
                        font-weight: 1200;
                        font-size:1.1rem;
                    ">View Product</a>
                </div>
                """

                with cols[col_idx]:
                    st.markdown(card_html, unsafe_allow_html=True)

    render_product_cards(filtered_df.head(700))

    # Grade distribution bar chart
    st.subheader("Grade Distribution")
    grade_counts = filtered_df['grade'].value_counts().sort_index()
    st.bar_chart(grade_counts)

    # Score histogram with matplotlib
    st.subheader("Score Histogram")
    fig, ax = plt.subplots()
    ax.hist(filtered_df['score'], bins=10, color='lightgreen', edgecolor='black')
    ax.set_title("Score Histogram")
    ax.set_xlabel("Score")
    ax.set_ylabel("Frequency")
    st.pyplot(fig)
