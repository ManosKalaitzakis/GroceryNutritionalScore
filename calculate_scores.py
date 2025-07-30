import pymysql
import re
from pymysql.cursors import DictCursor

# Safe float conversion from string values
def safe_float(text):
    if not text:
        return 0.0
    num = re.findall(r"[\d.,]+", text.replace("\u202f", ""))
    if not num:
        return 0.0
    s = num[0].replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0

# Nutri-score inspired function
def nutri_score(product):
    energy = safe_float(product.get('Ενέργεια'))  # in kJ
    sugar = safe_float(product.get('εκ των οποίων σάκχαρα'))
    satfat = safe_float(product.get('εκ των οποίων κορεσμένα') or product.get('Κορεσμένα'))
    salt = safe_float(product.get('Αλάτι')) * 1000  # convert to mg
    fiber = safe_float(product.get('Εδώδιμες ίνες') or product.get('Φυτικές ίνες'))
    protein = safe_float(product.get('Πρωτεΐνες'))

    # Normalize negative nutrients (capped at 1)
    e_s = min(energy / 3350, 1.0)
    su_s = min(sugar / 45, 1.0)
    sf_s = min(satfat / 10, 1.0)
    salt_s = min(salt / 900, 1.0)

    # Normalize positive nutrients
    fib_s = min(fiber / 4.7, 1.0)
    pro_s = min(protein / 8.0, 1.0)

    # Combine for final score
    neg = (e_s + su_s + sf_s + salt_s) / 4
    pos = (fib_s + pro_s) / 2
    score = int((1 - neg + pos) / 2 * 100)
    return max(0, min(100, score))

def assign_grade(score):
    if score >= 80:
        return "A"
    elif score >= 60:
        return "B"
    elif score >= 40:
        return "C"
    elif score >= 20:
        return "D"
    else:
        return "E"

def main():
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
        # Create score table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_score (
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
        """)
        connection.commit()

        # Fetch all nutrition entries
        cursor.execute("SELECT * FROM product_nutrition")
        rows = cursor.fetchall()
        print(f"Fetched {len(rows)} nutrition entries")

        for row in rows:
            pid = row['product_id']
            score = nutri_score(row)
            grade = assign_grade(score)
            print(f"Product {pid}: Score={score}, Grade={grade}")

            cursor.execute("""
                INSERT INTO product_score (product_id, nutrition_id, score, grade)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE score=%s, grade=%s
            """, (pid, pid, score, grade, score, grade))

        connection.commit()
    connection.close()
    print("Done calculating and storing nutrition scores.")

if __name__ == "__main__":
    main()
