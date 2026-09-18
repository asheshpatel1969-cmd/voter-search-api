import csv
import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import fuzz

app = FastAPI(title="Nikol Voter Search API - Pure Aligned Production")

# Enable CORS so your FlutterFlow app can securely talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CSV_FILENAME = "nikol-master-voterslist.csv"
VOTER_DATABASE = []

def load_nikol_data():
    """Server initialization loading dataset cleanly into RAM memory"""
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
            print(f"❌ Error loading CSV data: {e}")
    else:
        print(f"❌ Critical Error: '{CSV_FILENAME}' not found.")

load_nikol_data()


@app.get("/")
def search_voters(
    search_query: str = Query(..., description="The text input typed by the user")
):
    user_query = search_query.strip()
    if not user_query or not VOTER_DATABASE:
        return []

    results = []
    # Break query into individual clean words - fully matching your local environment
    query_words = [w.lower() for w in user_query.split() if w]
    query_clean_single = "".join(query_words)

    exact_epic_found = False
    exact_epic_record = None

    # FIRST PASS: Absolute 100% exact EPIC number match
    for record in VOTER_DATABASE:
        if not record:
            continue
        epic_val = str(record.get('epicnumber', '')).strip().lower()
        epic_clean = epic_val.replace("/", "").replace(" ", "")
        user_clean = query_clean_single.replace("/", "").replace(" ", "")
        
        if epic_val == query_clean_single or epic_clean == user_clean:
            exact_epic_found = True
            exact_epic_record = record
            break

    # If an exact EPIC match is discovered, bypass all fuzzy logic entirely
    if exact_epic_found:
        return [exact_epic_record]
        
    # SECOND PASS: Full text / fuzzy token parsing (Your Local logic)
    for record in VOTER_DATABASE:
        if not record:
            continue
        try:
            name_en = f"{str(record.get('votersname', ''))} {str(record.get('fatherhusbandname', ''))}".lower()
            name_gj = f"{str(record.get('votersnameguj', ''))} {str(record.get('fatherhusbandnameguj', ''))}".lower()
            epic = str(record.get('epicnumber', '')).lower()
            area = str(record.get('voterarea', '')).lower()
            
            # Substring lookahead for partial EPIC inputs using query_words[0]
            if len(query_words) == 1 and query_words[0] in epic:
                score = fuzz.ratio(query_words[0], epic)
                results.append((max(score, 85), record))
                continue

            all_words_matched = True
            total_score = 0
            
            for word in query_words:
                word_matched = False
                best_word_score = 0
                
                if word in name_en or word in name_gj or word in area:
                    word_matched = True
                    best_word_score = 100
                else:
                    all_voter_words = name_en.split() + name_gj.split() + area.split()
                    for v_word in all_voter_words:
                        fuzz_score = fuzz.ratio(word, v_word)
                        if fuzz_score >= 75:
                            word_matched = True
                            if fuzz_score > best_word_score:
                                best_word_score = fuzz_score
                
                if not word_matched:
                    all_words_matched = False
                    break
                else:
                    total_score += best_word_score

            if all_words_matched and query_words:
                final_score = total_score / len(query_words)
                results.append((final_score, record))
        except Exception:
            continue

    # 💡 માસ્ટર સોર્ટિંગ ફિક્સ: આખો ભાગ લૂપની બિલકુલ બહાર (Outside Loop) આવી ગયો છે
    clean_list = [voter for score, voter in results]

    # 💡 ક્યારેય ક્રેશ ન થાય તેવું સેફ ઈન્ટિજર કન્વર્ઝન ફંક્શન
    def safe_int(value):
        if not value:
            return 0
        try:
            return int(float(str(value).strip()))
        except ValueError:
            return 0

    # બૂથ નંબર અને સીરીયલ નંબર પ્રમાણે એકદમ સુંદર ચડતો ક્રમ (૧, ૨, ૩)
    clean_list.sort(
        key=lambda x: (
            safe_int(x.get('votingboothno')), 
            safe_int(x.get('srno'))
        )
    )

    # Return top 40 sorted records safely back to FlutterFlow
    return clean_list[:40]
