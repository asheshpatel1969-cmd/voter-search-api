import csv
import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import fuzz

app = FastAPI(title="Nikol Voter Search API")

# Enable CORS so your FlutterFlow app can securely talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CSV_FILENAME = "nikol_master_voterslist.csv"
VOTER_DATABASE = []

def load_nikol_data():
    """સર્વર ચાલુ થતાં જ નિકોલની CSV ફાઇલને RAM માં લોડ કરશે"""
    global VOTER_DATABASE
    if os.path.exists(CSV_FILENAME):
        try:
            print(f"Loading '{CSV_FILENAME}', please wait...")
            with open(CSV_FILENAME, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row:
                        VOTER_DATABASE.append(row)
            print(f"Successfully loaded {len(VOTER_DATABASE)} voter records from CSV!")
        except Exception as e:
            print(f"❌ Error loading Nikol CSV: {e}")
    else:
        print(f"❌ Critical Error: {CSV_FILENAME} not found!")

# 💡 લાઈવ ઓટોમેટેડ ડેટા લોડ
load_nikol_data()


@app.get("/search")
def search_nikol_voters(
    search_query: str = Query(..., description="The text input typed by the user")
):
    user_query = search_query.strip()
    if not user_query or not VOTER_DATABASE:
        return []

    # --- અહીંથી તમારો જ ઓરિજિનલ ૧૦૦% સક્સેસફુલ સર્ચ કોડ રન થશે ---
    results = []
    query_words = [w.lower() for w in user_query.split() if w]
    query_clean_single = "".join(query_words)

    # 1. FIRST PASS: Absolute Exact EPIC Match
    exact_epic_found = False
    exact_epic_record = None

    for record in VOTER_DATABASE:
        epic_val = str(record.get('epicnumber', '')).strip().lower()
        epic_clean = epic_val.replace("/", "").replace(" ", "")
        user_clean = query_clean_single.replace("/", "").replace(" ", "")
        
        if epic_val == query_clean_single or epic_clean == user_clean:
            exact_epic_found = True
            exact_epic_record = record
            break

    if exact_epic_found:
        return [exact_epic_record]

    # 2. SECOND PASS: Multi-Word Substring Token Filtering
    for record in VOTER_DATABASE:
        name_en = f"{str(record.get('votersname', ''))} {str(record.get('fatherhusbandname', ''))}".lower()
        name_gj = f"{str(record.get('votersnameguj', ''))} {str(record.get('fatherhusbandnameguj', ''))}".lower()
        epic = str(record.get('epicnumber', '')).lower()
        area = str(record.get('voterarea', '')).lower()
        
        if len(query_words) == 1 and query_words in epic:
            results.append((100, record))
            continue

        all_words_matched = True
        for word in query_words:
            word_matched = False
            
            if word in name_en or word in name_gj or word in area:
                word_matched = True
            else:
                all_voter_words = name_en.split() + name_gj.split() + area.split()
                for v_word in all_voter_words:
                    if fuzz.ratio(word, v_word) >= 75:
                        word_matched = True
                        break
            
            if not word_matched:
                all_words_matched = False
                break

        if all_words_matched and query_words:
            results.append((100, record))

    final_output = [record for score, record in results]
    return final_output[:40]
