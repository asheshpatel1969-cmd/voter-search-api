import csv
import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import fuzz

app = FastAPI(title="Voter Search Engine API - Safe Dynamic Edition")

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
    """તમારા લોકલ કોડની જેમ જ બધી CSV ફાઇલોને આપમેળે સર્વરના RAM માં લોડ કરશે"""
    global CONSTITUENCY_DATABASES
    current_directory = os.getcwd()
    
    print("🔍 Scanning server directory for constituency CSV files...")
    for filename in os.listdir(current_directory):
        if filename.endswith(".csv"):
            # ફાઇલના નામમાંથી .csv હટાવીને સ્ટાન્ડર્ડ કી (નાના અક્ષરોમાં) લોક કરશે
            db_key = filename.replace(".csv", "").strip().lower()
            records = []
            try:
                with open(filename, mode='r', encoding='utf-8-sig') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        if row:
                            records.append(row)
                CONSTITUENCY_DATABASES[db_key] = records
                print(f" Loaded database key '{db_key}' with {len(records)} voters.")
            except Exception as e:
                print(f"❌ Error loading file {filename}: {e}")

# Load all CSV databases instantly when the server launches
load_csv_data()


@app.get("/search")
def search_voters(
    constituency_collection: str = Query(..., description="The name of the database collection"),
    search_query: str = Query(..., description="The text input typed by the user")
):
    # 💡 માસ્ટર હેક: ફ્લટરફ્લોમાંથી '-' કે '_' ગમે તે આવે, તેને સ્ટાન્ડર્ડ નાના અક્ષરોમાં બદલીને ફાઈલ શોધી કાઢશે!
    incoming_key = constituency_collection.strip().lower().replace("-", "_")
    target_db = CONSTITUENCY_DATABASES.get(incoming_key)
    
    # જો અસલી ફાઈલ મેચ ન થાય તો લિસ્ટમાં બીજી બધી ચાવીઓ ચેક કરશે
    if not target_db:
        for k in CONSTITUENCY_DATABASES.keys():
            if incoming_key in k or k in incoming_key:
                target_db = CONSTITUENCY_DATABASES[k]
                break

    if not target_db:
        print(f"⚠️ Collection matching '{constituency_collection}' not found in RAM memory.")
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
    for record in target_db:
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
