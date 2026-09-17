import csv
import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import fuzz

app = FastAPI(title="Voter Search Engine API - Production Edition")

# Enable CORS so your FlutterFlow app can securely talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global dictionary to store voter lists for all constituencies in memory
CONSTITUENCY_DATABASES = {}

def load_csv_data():
    """Automatically loads any CSV file in this folder into the server's RAM"""
    current_directory = os.getcwd()
    for filename in os.listdir(current_directory):
        if filename.endswith(".csv"):
            db_key = filename.replace(".csv", "").strip()
            records = []
            try:
                with open(filename, mode='r', encoding='utf-8-sig') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        # 💡 100% Safe Original Load: pulling all rows into memory without filtering
                        if row:
                            records.append(row)
                CONSTITUENCY_DATABASES[db_key] = records
                print(f" Loaded database key '{db_key}' with {len(records)} voters.")
            except Exception as e:
                print(f"❌ Error loading file {filename}: {e}")

# Load all CSV databases instantly when the server launches
print("Initializing databases into server RAM...")
load_csv_data()


@app.get("/search")
def search_voters(
    constituency_collection: str = Query(..., description="The name of the database collection"),
    search_query: str = Query(..., description="The text input typed by the user")
):
    target_db = CONSTITUENCY_DATABASES.get(constituency_collection.strip())
    
    if not target_db:
        return []
        
    user_query = search_query.strip()
    if not user_query:
        return []

    results = []
    query_words = [w.lower() for w in user_query.split() if w]
    query_clean_single = "".join(query_words)

    # 1. FIRST PASS: Absolute Exact EPIC Match
    exact_epic_found = False
    exact_epic_record = None

    for record in target_db:
        if not record:
            continue
        try:
            epic_val = str(record.get('epicnumber') or '').strip().lower()
            if not epic_val:
                continue
                
            epic_clean = epic_val.replace("/", "").replace(" ", "")
            user_clean = query_clean_single.replace("/", "").replace(" ", "")
            
            if epic_val == query_clean_single or epic_clean == user_clean:
                exact_epic_found = True
                exact_epic_record = record
                break
        except Exception:
            continue

    if exact_epic_found:
        return [exact_epic_record]

    # 2. SECOND PASS: Multi-Word Substring Token Filtering (Crash-Proofed)
    for record in target_db:
        if not record:
            continue
        try:
            v_name = str(record.get('votersname') or '').strip().lower()
            f_name = str(record.get('fatherhusbandname') or '').strip().lower()
            v_name_gj = str(record.get('votersnameguj') or '').strip().lower()
            f_name_gj = str(record.get('fatherhusbandnameguj') or '').strip().lower()
            epic = str(record.get('epicnumber') or '').strip().lower()
            area = str(record.get('voterarea') or '').strip().lower()
            
            name_en = f"{v_name} {f_name}"
            name_gj = f"{v_name_gj} {f_name_gj}"
            
            if len(query_words) == 1 and epic and query_words in epic:
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
        except Exception:
            continue

    final_output = [record for score, record in results]
    return final_output[:40]
