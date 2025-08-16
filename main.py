from flask import Flask, request, jsonify
import pandas as pd
from flask_cors import CORS
import os

app = Flask(_name_)
CORS(app)  # Allow requests from your frontend

# Load datasets with correct file names from your structure
try:
    base_dir = os.path.dirname(os.path.abspath(_file_))
    states_df = pd.read_csv(os.path.join(base_dir, "states_and_union_territories.csv"))
    cities_df = pd.read_csv(os.path.join(base_dir, "cities.csv"))
    budget_duration_df = pd.read_csv(os.path.join(base_dir, "city_budget_duration.csv"))
    cities_type_df = pd.read_csv(os.path.join(base_dir, "cities_type_data.csv"))  # Using cities_type_data.csv
    
    print("All datasets loaded successfully!")
    print(f"States: {len(states_df)} records")
    print(f"Cities: {len(cities_df)} records")
    print(f"Budget/Duration: {len(budget_duration_df)} records")
    print(f"Cities Type Data: {len(cities_type_df)} records")
    
except FileNotFoundError as e:
    print(f"Error: File not found. Please ensure all required datasets are in the same directory as the app.")
    print(f"Missing file: {e}")
    exit(1)
except pd.errors.EmptyDataError:
    print(f"Error: One of the CSV files is empty. Please check the contents of your dataset files.")
    exit(1)
except Exception as e:
    print(f"An unexpected error occurred while loading datasets: {e}")
    exit(1)

@app.route('/api/cities', methods=['POST', 'OPTIONS'])
def get_cities():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200  # Respond to preflight request
    
    try:
        data = request.json
        budget = data['budget']
        duration = data['duration']
        experience_types = data['experience_types']
        
        if not isinstance(budget, (int, float)) or not isinstance(duration, (int, float)):
            return jsonify({"error": "Budget and duration must be numbers."}), 400
        
        # Make a copy to avoid modifying original data
        budget_duration_working = budget_duration_df.copy()
        budget_duration_working['Duration_Range'] = budget_duration_working['Duration_Range'].str.replace(r'[^\d\-]', '', regex=True)
        
        # Filter cities based on budget and duration
        filtered_cities = budget_duration_working[
            (budget_duration_working['Budget_Range'].str.split('-').str[0].astype(int) <= budget) &
            (budget_duration_working['Budget_Range'].str.split('-').str[1].astype(int) >= budget) &
            (budget_duration_working['Duration_Range'].str.split('-').str[0].astype(int) <= duration) &
            (budget_duration_working['Duration_Range'].str.split('-').str[1].astype(int) >= duration)
        ]
        
        # Get cities that match experience types
        city_matches = cities_type_df[cities_type_df['Type_ID'].isin(experience_types)].groupby('City_ID').agg({
            'Type_ID': list,
            'City_Name': 'first'
        }).reset_index()
        
        # Filter cities based on experience types
        final_cities = filtered_cities[filtered_cities['City_ID'].isin(city_matches['City_ID'])]
        
        # Merge to get matching types for each city
        final_cities = final_cities.merge(city_matches[['City_ID', 'Type_ID']], on='City_ID', how='left')
        
        # Calculate match score (percentage of requested types that are present)
        final_cities['match_score'] = final_cities['Type_ID'].apply(lambda x: len(set(x) & set(experience_types)) / len(experience_types) * 100)
        
        # Sort by match score
        final_cities = final_cities.sort_values('match_score', ascending=False)
        
        # Get type names for matching types
        type_names = cities_type_df[['Type_ID', 'Type_Name']].drop_duplicates().set_index('Type_ID')['Type_Name'].to_dict()
        
        # Prepare result
        result = final_cities.apply(lambda row: {
            'name': row['City_Name'],
            'match_score': round(row['match_score'], 2),
            'matching_types': [type_names[type_id] for type_id in set(row['Type_ID']) & set(experience_types)]
        }, axis=1).tolist()
        
        return jsonify(result)
        
    except KeyError as e:
        print(f"Error: Missing key '{e.args[0]}' in request JSON.")
        return jsonify({"error": f"Missing key '{e.args[0]}' in request JSON."}), 400
    except Exception as e:
        print(f"Error: {e}")  # Log the error to the console
        return jsonify({"error": str(e)}), 500  # Return a 500 error with the message

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "Travel Bot API is running!",
        "endpoints": {
            "/api/cities": "POST - Get city recommendations",
            "/health": "GET - Health check"
        }
    })

if _name_ == '_main_':
    port = int(os.environ.get('PORT', 4001))
    app.run(host='0.0.0.0', port=port, debug=False)
