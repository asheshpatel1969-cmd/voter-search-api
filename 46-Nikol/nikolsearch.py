import csv
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import fuzz

app = FastAPI()

# Enable CORS configurations safely for clean live multi-constituency lookups
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⚠️ કન્ફિગરેશન નિયમ: ફાઇલનું નામ જે-તે વિધાનસભા પ્રમાણે નીચે સ્ટેપ-૪ મુજબ બદલવાનું રહેશે
CSV_FILENAME = "nikol-master-voterslist.csv"

voters_db = []

def load_voters_data():
    global voters_db
    voters_db = []
    
    if not os.path.exists(CSV_FILENAME):
        print(f"Error: Target localized voter file '{CSV_FILENAME}' not found inside root runtime.")
        return

    try:
        with open(CSV_FILENAME, mode="r", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            
            # Clean header naming conversions directly upon initialization
            reader.fieldnames = [name.strip().lower() for name in reader.fieldnames] if reader.fieldnames else []
            
            for row in reader:
                voters_db.append({k: (v.strip() if v else "") for k, v in row.items()})
                
        print(f"Successfully loaded {len(voters_db)} voter records from CSV target array!")
    except Exception as e:
        print(f"Critical error structural reading process failure: {e}")

@app.on_event("startup")
def startup_event():
    load_voters_data()

@app.get("/")
def read_root():
    return {
        "status": "online", 
        "total_records": len(voters_db),
        "constituency_scope": CSV_FILENAME.split("-")[0].upper()
    }

@app.get("/search")
def search_voters(search_query: str = ""):
    if not search_query:
        return []
    
    search_query = search_query.strip().upper()
    results = []
    
    # 💡 ડાયરેક્ટ આઇડેન્ટિફાયર: જો સર્ચ ક્વેરીમાં આંકડા (Numbers) હશે તો તે EPIC/Voter ID સ્કેનિંગ ઓટોમેટિક ઓપન કરશે
    if any(char.isdigit() for char in search_query):
        for row in voters_db:
            if search_query in row.get("epicnumber", "").upper():
                results.append(row)
        
        # Sort sequentially by booth number first, then serial hierarchy order
        results.sort(key=lambda x: (int(x.get("boothno", 0) or 0), int(x.get("serialno", 0) or 0)))
        return results[:100]

    # 💡 નામ માટે કડક કાયદો (Fuzzy Threshold Rule): સ્કોર 85 કે તેથી વધુ હોય તો જ ડેટા ફિલ્ટર થશે
    for row in voters_db:
        voter_name = row.get("votersnameeng", "").upper()
        
        # Partial ratio match configuration via RapidFuzz engine
        score = fuzz.partial_ratio(search_query, voter_name)
        
        if score >= 85:  # 🪷 ખોટા અને આડાઅવળા નામો અટકાવવાની અલ્ટીમેટ લિમિટ
            results.append(row)
            
    # Always prioritize clean structural sorting patterns for poll workers
    results.sort(key=lambda x: (int(x.get("boothno", 0) or 0), int(x.get("serialno", 0) or 0)))
    return results[:100]
