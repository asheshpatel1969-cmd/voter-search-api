import os
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import fuzz

app = FastAPI(title="Voter Search Engine API via Firestore")

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

# Initialize Firebase Admin SDK
# Ensure 'firebase_credentials.json' is placed in the root folder of your project
cred = credentials.Certificate("firebase_credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def load_firestore_data():
    """Dynamically loads specified collections or all known voter collections from Firestore into RAM"""
    print("Fetching dynamic data from Firestore collections...")
    
    # ⚠️ List down your active Firestore collections here so the server knows what to pre-load into RAM
    collections_to_load = [
        "nikol-master-voterslist", 
        "raopura-master-voterslist"
    ]
    
    for coll_name in collections_to_load:
        # Convert dashes or names to match your FlutterFlow key names if necessary
        # We replace '-' with '_' to keep your working logic exact
        db_key = coll_name.replace("-", "_").strip()
        records = []
        
        try:
            docs = db.collection(coll_name).stream()
            for doc in docs:
                records.append(doc.to_dict())
                
            CONSTITUENCY_DATABASES[db_key] = records
            print(f" Loaded Firestore collection '{coll_name}' as key '{db_key}' with {len(records)} voters into RAM.")
        except Exception as e:
            print(f"❌ Error loading Firestore collection {coll_name}: {e}")

# Load all Firestore databases instantly when the server launches
print("Initializing databases into server RAM from Firestore...")
load_firestore_data()


@app.get("/search")
def search_voters(
    constituency_collection: str = Query(..., description="The name of the database collection"),
    search_query: str = Query(..., description="The text input typed by the user")
):
    # Standardize incoming key name to match our database key
    standardized_key = constituency_collection.replace("-", "_").strip()
    target_db = CONSTITUENCY_DATABASES.get(standardized_key)
    
    if not target_db:
        return {"error": f"Database collection '{constituency_collection}' not found on server.", "results": []}
        
    user_query = search_query.strip()
    if not user_query:
        return {"results": []}

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
        return {"results": [exact_epic_record]}

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
    return {"results": final_output[:40]}
