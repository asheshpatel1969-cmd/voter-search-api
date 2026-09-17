import csv
import sys
import os
from rapidfuzz import fuzz

# Force Windows console environment to fully process Gujarati text encoding
sys.stdout.reconfigure(encoding='utf-8')
os.system('chcp 65001 > nul')

csv_filename = 'nikol-master-voterslist.csv'
voter_records = []

print(f"Loading '{csv_filename}', please wait...")

try:
    with open(csv_filename, mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        for row in reader:
            voter_records.append(row)
    print(f"Successfully loaded {len(voter_records)} voter records from CSV!\n")
except FileNotFoundError:
    print(f"Error: '{csv_filename}' not found.")
    exit()

while True:
    print("=" * 60)
    user_query = input("Enter voter search text (or type 'exit' to quit): ").strip()
    
    if user_query.lower() == 'exit':
        print("Exiting search tool. Goodbye!")
        break
    if not user_query:
        continue

    results = []
    # Break query into individual clean words
    query_words = [w.lower() for w in user_query.split() if w]
    query_clean_single = "".join(query_words)

    # Flag to monitor if we hit an exact unique match
    exact_epic_found = False
    exact_epic_record = None

    # FIRST PASS: Check for an absolute 100% exact EPIC number match
    for record in voter_records:
        epic_val = str(record.get('epicnumber', '')).strip().lower()
        # Strip slashes and spaces for a robust check
        epic_clean = epic_val.replace("/", "").replace(" ", "")
        user_clean = query_clean_single.replace("/", "").replace(" ", "")
        
        if epic_val == query_clean_single or epic_clean == user_clean:
            exact_epic_found = True
            exact_epic_record = record
            break

    # If an exact EPIC match is discovered, bypass all fuzzy logic entirely
    if exact_epic_found:
        results = [(100, exact_epic_record)]
    else:
        # SECOND PASS: Fall back to full text / fuzzy token parsing
        for record in voter_records:
            name_en = f"{str(record.get('votersname', ''))} {str(record.get('fatherhusbandname', ''))}".lower()
            name_gj = f"{str(record.get('votersnameguj', ''))} {str(record.get('fatherhusbandnameguj', ''))}".lower()
            epic = str(record.get('epicnumber', '')).lower()
            area = str(record.get('voterarea', '')).lower()
            
            # Substring lookahead for partial EPIC inputs
            if len(query_words) == 1 and query_words[0] in epic:
                score = fuzz.ratio(query_words[0], epic)
                # Boost score slightly if it's a direct partial match
                results.append((max(score, 85), record))
                continue

            all_words_matched = True
            total_score = 0
            
            for word in query_words:
                word_matched = False
                best_word_score = 0
                
                if word in name_en:
                    word_matched = True
                    best_word_score = 100
                elif word in name_gj:
                    word_matched = True
                    best_word_score = 100
                elif word in area:
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

        # Sort the array strictly by highest match confidence score
        results.sort(key=lambda x: x[0], reverse=True)

    # Show up to top 15 matches
    top_matches = results[:15]
    
    if not top_matches:
        print("\n❌ No matching voter records found.")
    else:
        print(f"\n✨ Found {len(results)} matches! Showing top records:\n")
        for rank, (score, voter) in enumerate(top_matches, 1):
            print(f"--- Match #{rank} (Match Confidence: {round(score)}%) ---")
            print(f"EPIC Number:        {voter.get('epicnumber', 'Not Found')}")
            print(f"Voter Name (EN):    {voter.get('votersname', 'Not Found')}")
            print(f"Voter Name (GJ):    {voter.get('votersnameguj', 'Not Found')}")
            print(f"Father/Husband (EN):{voter.get('fatherhusbandname', 'Not Found')}")
            print(f"Father/Husband (GJ):{voter.get('fatherhusbandnameguj', 'Not Found')}")
            print(f"Voter Area:         {voter.get('voterarea', 'Not Found')}")
            print(f"Voting Booth No:    {voter.get('votingboothno', 'Not Found')}")
            print(f"Serial Number:      {voter.get('srno', 'Not Found')}")
            print("")
