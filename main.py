import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import fuzz

app = FastAPI(title="Dynamic On-Demand Voter Search API")

# Enable CORS so your FlutterFlow app can securely talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global dictionary to store voter lists in memory ONLY when requested
CONSTITUENCY_DATABASES = {}

# Initialize Firebase Admin SDK using Render's Environment Variable
# This keeps your credentials secure and avoids GitHub security alerts!
try:
    service_account_info = json.loads(os.environ.get("FIREBASE_KEY_JSON"))
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("🚀 Firebase Admin SDK initialized successfully via Environment Variables.")
except Exception as e:
    print(f"❌ Critical Error initializing Firebase: {e}")
    print("Ensure you have set the 'FIREBASE_KEY_JSON' variable in Render Environment settings.")

@app.get("/search")
def search_voters(
    constituency_collection: str = Query(..., description="The name of the database collection"),
    search_query: str = Query(..., description="The text input typed by the user")
):
    user_query = search_query.strip()
    coll_name = constituency_collection.strip()
    
    if not user_query or not coll_name:
        return {"results": []}
        
    # Standardize the collection key name for our dictionary cache lookup
    db_key = coll_name.replace("-", "_").strip()
    
    # 💡 ON-DEMAND LOADING LOGIC
    # If this constituency's data is NOT in memory yet, pull it from Firestore right now!
    if db_key not in CONSTITUENCY_DATABASES:
        print(f"📥 Cache Miss! Fetching '{coll_name}' dynamically from Firestore...")
        try:
            coll_ref = db.collection(coll_name)
            docs = coll_ref.get() # Blazing fast chunk fetch (Takes ~2-3 seconds for 3 lac rows)
            
            records = []
            for doc in docs:
                records.append(doc.to_dict())
                
            # Save into our RAM cache dictionary for instant future lookups
            CONSTITUENCY_DATABASES[db_key] = records
            print(f"💾 Cache Loaded! '{coll_name}' with {len(records)} voters is now safely stored in RAM.")
            
        except Exception as e:
            print(f"❌ Failed to fetch collection '{coll_name}' from Firestore: {e}")
            return {"error": f"Constituency database connection failed.", "results": []}

    # Pull the targeted data dataset instantly from our RAM cache dictionary
    target_db = CONSTITUENCY_DATABASES.get(db_key)
    if not target_db:
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

    # 2. SECOND PASS: Multi-Word Substring Token Filtering & Fuzzy Logic Fallback
    for record in target_db:
        name_en = f"{str(record.get('votersname', ''))} {str(record.get('fatherhusbandname', ''))}".lower()
        name_gj = f"{str(record.get('votersnameguj', ''))} {str(record.get('fatherhusbandnameguj', ''))}".lower()
        epic = str(record.get('epicnumber', '')).lower()
        area = str(record.get('voterarea', '')).lower()
        
        if len(query_words) == 1 and query_words[0] in epic:
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
