from sqlalchemy import create_engine
import pandas as pd
import matplotlib.pyplot as plt

# DB connection details
user = 'root'
password = '1234'
host = 'localhost'
port = 3307
db = 'groceryscore'

connection_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4"
engine = create_engine(connection_url)

# Query top 40 products with nutrition info
query_top40 = """
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
LIMIT 40;
"""

df_top40 = pd.read_sql(query_top40, engine)

print("Top 40 Products by Nutrition Score:")
print(df_top40.to_string(index=False))

# Plot 1: Grade distribution for all products
df_grades = pd.read_sql("SELECT grade, COUNT(*) as count FROM product_score GROUP BY grade", engine)

plt.figure(figsize=(8,5))
plt.bar(df_grades['grade'], df_grades['count'], color='skyblue')
plt.title('Distribution of Nutrition Grades (All Products)')
plt.xlabel('Grade')
plt.ylabel('Count')
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.show()

# Plot 2: Nutrition score histogram
df_scores = pd.read_sql("SELECT score FROM product_score", engine)

plt.figure(figsize=(8,5))
plt.hist(df_scores['score'], bins=10, color='orange', edgecolor='black')
plt.title('Histogram of Nutrition Scores')
plt.xlabel('Score')
plt.ylabel('Frequency')
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.show()

# Plot 3: Top 10 products by score horizontal bar chart
top10 = df_top40.head(10).sort_values(by='score', ascending=True)

plt.figure(figsize=(10,6))
plt.barh(top10['name'], top10['score'], color='green')
plt.title('Top 10 Products by Nutrition Score')
plt.xlabel('Score')
plt.tight_layout()
plt.show()

engine.dispose()
