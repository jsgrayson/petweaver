from flask import Flask, render_template, jsonify, request
import os
import json
import threading
import time
from datetime import datetime
import automate
import requests
from simulator.strategy_manager import StrategyManager

# Load .env manually
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

app = Flask(__name__)

# Global state
state = {
    "status": "IDLE", # IDLE, RUNNING, COMPLETED, ERROR
    "log": [],
    "last_update": None,
    "stats": {
        "pets": 0,
        "strategies": 0,
        "ready": 0
    }
}

from blizzard_oauth import BlizzardOAuth

app = Flask(__name__)

# Global state
state = {
    "status": "IDLE", # IDLE, RUNNING, COMPLETED, ERROR
    "log": [],
    "last_update": None,
    "stats": {
        "pets": 0,
        "strategies": 0,
        "ready": 0
    }
}

# Initialize Strategy Manager
strategy_manager = StrategyManager(os.path.join(os.path.dirname(__file__), "strategies_cleaned.json"))

def get_blizzard_client():
    """Returns a requests session with authentication headers, refreshing token if needed"""
    client_id = os.getenv('BLIZZARD_CLIENT_ID')
    client_secret = os.getenv('BLIZZARD_CLIENT_SECRET')
    
    # Fallback to dummy if env vars missing (assuming token exists and is valid/refreshable)
    if not client_id or not client_secret:
        if os.path.exists('token.json'):
            client_id = "dummy"
            client_secret = "dummy"
        else:
            raise Exception("Missing credentials and no token found")
            
    oauth = BlizzardOAuth(client_id, client_secret)
    try:
        access_token = oauth.get_access_token()
    except Exception as e:
        raise Exception(f"Failed to get access token: {e}")
        
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {access_token}",
        "Battlenet-Namespace": "static-us",
        "Locale": "en_US"
    })
    return session

def log_message(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    state["log"].append(entry)
    # Keep log size manageable
    if len(state["log"]) > 1000:
        state["log"] = state["log"][-1000:]
    print(entry)

def update_stats():
    try:
        if os.path.exists('my_pets.json'):
            with open('my_pets.json', 'r') as f:
                data = json.load(f)
                state["stats"]["pets"] = len(data.get('pets', []))
        
        if os.path.exists('strategies.json'):
            with open('strategies.json', 'r') as f:
                data = json.load(f)
                # Rough count of strategies
                count = 0
                for exp in data.values():
                    for cat in exp.values():
                        for enc in cat:
                            count += len(enc.get('strategies', []))
                state["stats"]["strategies"] = count

        if os.path.exists('my_ready_strategies.json'):
             with open('my_ready_strategies.json', 'r') as f:
                data = json.load(f)
                count = 0
                for exp in data.values():
                    for cat in exp.values():
                        count += len(cat)
                state["stats"]["ready"] = count
                
    except Exception as e:
        log_message(f"Error updating stats: {e}")

def run_automation_thread(skip_fetch, force_scrape, addon_path):
    global state
    state["status"] = "RUNNING"
    state["log"] = [] # Clear log on new run
    log_message("🚀 Starting PetWeaver Automation...")
    
    try:
        # Capture stdout/stderr? For now, let's just manually log key steps
        # We need to adapt automate.py to be more library-friendly or just call its functions
        
        # 1. Auth/Fetch
        if not skip_fetch:
            log_message("🔐 Authenticating with Blizzard...")
            client_id = os.getenv('BLIZZARD_CLIENT_ID')
            client_secret = os.getenv('BLIZZARD_CLIENT_SECRET')
            
            if not client_id or not client_secret:
                if os.path.exists('token.json'):
                    log_message("⚠️  Using cached token (Env vars missing)")
                    client_id = "dummy"
                    client_secret = "dummy"
                else:
                    raise Exception("Missing Credentials")
            
            oauth = automate.BlizzardOAuth(client_id, client_secret)
            token = oauth.get_access_token()
            
            log_message("📥 Fetching Pet Collection...")
            fetcher = automate.PetCollectionFetcher(token)
            collection = fetcher.get_pet_collection()
            fetcher.save_collection(collection)
            log_message(f"✅ Fetched {len(collection.get('pets', []))} pets")
        else:
            log_message("⏭️  Skipping Fetch (Using local data)")

        # 2. Scrape
        if force_scrape or not os.path.exists('strategies.json'):
            log_message("🔄 Scraping Strategies (This may take time)...")
            scraper = automate.RobustXuFuScraper()
            scraper.scrape_all()
            if os.path.exists('strategies_final.json'):
                os.rename('strategies_final.json', 'strategies.json')
            log_message("✅ Scraping Complete")
        else:
            log_message("⏭️  Skipping Scrape (Data exists)")

        # 3. Match
        log_message("🎯 Matching Strategies...")
        matcher = automate.StrategyMatcher()
        matches = matcher.match_strategies()
        matcher.save_matches(matches)
        
        # 4. Export
        log_message(f"💾 Exporting to Addon: {addon_path}")
        lua_path = os.path.join(addon_path, 'PetWeaverData.lua')
        matcher.export_to_lua(matches, output_path=lua_path)
        
        state["status"] = "COMPLETED"
        state["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message("✅ Automation Successfully Completed!")
        update_stats()
        
    except Exception as e:
        state["status"] = "ERROR"
        log_message(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

CONFIG_FILE = 'config.json'

def load_config():
    default_path = automate.get_default_addon_path()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('addon_path', default_path)
        except:
            pass
    return default_path

def save_config(addon_path):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({'addon_path': addon_path}, f)
    except Exception as e:
        print(f"Error saving config: {e}")

@app.route('/')
def index():
    update_stats()
    current_path = load_config()
    return render_template('index.html', default_path=current_path)

@app.route('/api/status')
def get_status():
    return jsonify(state)

@app.route('/api/run', methods=['POST'])
def run_automation():
    if state["status"] == "RUNNING":
        return jsonify({"error": "Already running"}), 400
        
    data = request.json
    skip_fetch = data.get('skip_fetch', False)
    force_scrape = data.get('force_scrape', False)
    addon_path = data.get('addon_path', './PetWeaver')
    
    # Save the path for next time
    save_config(addon_path)
    
    thread = threading.Thread(target=run_automation_thread, args=(skip_fetch, force_scrape, addon_path))
    thread.start()
    
    return jsonify({"message": "Started"})

@app.route('/dashboard')
def dashboard():
    """Progress dashboard with charts and analytics"""
    return render_template('dashboard.html')

@app.route('/strategies')
def strategies():
    """Browse all strategies (mobile-optimized)"""
    return render_template('strategies.html')

@app.route('/hunting')
def hunting():
    """Pet hunting guide"""
    return render_template('hunting.html')

@app.route('/wizard')
def wizard():
    """Strategy Wizard for creating new strategies"""
    return render_template('wizard.html')

@app.route('/api/simulate/wizard', methods=['POST'])
def simulate_wizard_strategy():
    """Test a strategy from the wizard using Virtual Dojo"""
    try:
        from simulator import (
            BattleSimulator, BattleState, Team, Pet, Ability, 
            PetStats, PetFamily, PetQuality, TurnAction
        )
        
        data = request.json
        actions = data.get('actions', [])
        
        # 1. Create Dummy Teams (since we don't have full pet data yet)
        # Player: 3 Generic Pets
        player_pets = [
            Pet(
                species_id=1, name="My Pet 1", family=PetFamily.BEAST, quality=PetQuality.RARE,
                stats=PetStats(max_hp=1500, current_hp=1500, power=300, speed=280),
                abilities=[
                    Ability(id=1, name="Slot 1", power=20, accuracy=100, speed=0, cooldown=0, family=PetFamily.BEAST),
                    Ability(id=2, name="Slot 2", power=25, accuracy=100, speed=0, cooldown=3, family=PetFamily.BEAST),
                    Ability(id=3, name="Slot 3", power=0, accuracy=100, speed=0, cooldown=0, family=PetFamily.BEAST, is_heal=True)
                ]
            ),
            Pet(
                species_id=2, name="My Pet 2", family=PetFamily.FLYING, quality=PetQuality.RARE,
                stats=PetStats(max_hp=1400, current_hp=1400, power=280, speed=320),
                abilities=[Ability(id=4, name="Peck", power=20, accuracy=100, speed=0, cooldown=0, family=PetFamily.FLYING)]
            ),
            Pet(
                species_id=3, name="My Pet 3", family=PetFamily.MECHANICAL, quality=PetQuality.RARE,
                stats=PetStats(max_hp=1600, current_hp=1600, power=320, speed=260),
                abilities=[Ability(id=5, name="Zap", power=20, accuracy=100, speed=0, cooldown=0, family=PetFamily.MECHANICAL)]
            )
        ]
        
        # Enemy: 3 Generic Pets (Target Dummies)
        enemy_pets = [
            Pet(
                species_id=101, name="Enemy Beast", family=PetFamily.BEAST, quality=PetQuality.RARE,
                stats=PetStats(max_hp=1500, current_hp=1500, power=280, speed=270),
                abilities=[Ability(id=10, name="Bite", power=20, accuracy=100, speed=0, cooldown=0, family=PetFamily.BEAST)]
            ),
            Pet(
                species_id=102, name="Enemy Flyer", family=PetFamily.FLYING, quality=PetQuality.RARE,
                stats=PetStats(max_hp=1400, current_hp=1400, power=260, speed=300),
                abilities=[Ability(id=11, name="Swoop", power=20, accuracy=100, speed=0, cooldown=0, family=PetFamily.FLYING)]
            ),
            Pet(
                species_id=103, name="Enemy Mech", family=PetFamily.MECHANICAL, quality=PetQuality.RARE,
                stats=PetStats(max_hp=1600, current_hp=1600, power=300, speed=250),
                abilities=[Ability(id=12, name="Laser", power=20, accuracy=100, speed=0, cooldown=0, family=PetFamily.MECHANICAL)]
            )
        ]
        
        player_team = Team(pets=player_pets)
        enemy_team = Team(pets=enemy_pets)
        
        initial_state = BattleState(
            player_team=player_team,
            enemy_team=enemy_team,
            turn_number=1,
            rng_seed=42
        )
        
        # 2. Create Agent Function from Wizard Actions
        def wizard_agent(state):
            # Simple interpreter for wizard actions
            # It tries actions in order until one is valid
            
            active_pet = state.player_team.get_active_pet()
            if not active_pet:
                return TurnAction(actor='player', action_type='pass')
            
            for action in actions:
                atype = action.get('type')
                
                if atype == 'ability':
                    slot = int(action.get('slot', 1)) - 1
                    if 0 <= slot < len(active_pet.abilities):
                        ability = active_pet.abilities[slot]
                        if active_pet.can_use_ability(ability):
                            return TurnAction(actor='player', action_type='ability', ability=ability)
                            
                elif atype == 'swap':
                    pet_idx = int(action.get('pet', 1)) - 1
                    if 0 <= pet_idx < len(state.player_team.pets):
                        target = state.player_team.pets[pet_idx]
                        if target.stats.is_alive() and pet_idx != state.player_team.active_pet_index:
                            return TurnAction(actor='player', action_type='swap', target_pet_index=pet_idx)
                            
                elif atype == 'conditional':
                    # Check condition
                    cond_type = action.get('condition_type')
                    cond_val = float(action.get('condition_value', 0))
                    
                    met = False
                    if cond_type == 'enemy_hp':
                        enemy = state.enemy_team.get_active_pet()
                        if enemy:
                            hp_pct = (enemy.stats.current_hp / enemy.stats.max_hp) * 100
                            if hp_pct < cond_val:
                                met = True
                    elif cond_type == 'my_hp':
                        hp_pct = (active_pet.stats.current_hp / active_pet.stats.max_hp) * 100
                        if hp_pct < cond_val:
                            met = True
                    elif cond_type == 'round':
                        if state.turn_number >= cond_val:
                            met = True
                            
                    # Execute Then or Else
                    chosen_slot = int(action.get('then_slot' if met else 'else_slot', 1)) - 1
                    if 0 <= chosen_slot < len(active_pet.abilities):
                        ability = active_pet.abilities[chosen_slot]
                        if active_pet.can_use_ability(ability):
                            return TurnAction(actor='player', action_type='ability', ability=ability)
            
            # Default fallback
            return TurnAction(actor='player', action_type='ability', ability=active_pet.abilities[0])

        # Enemy Agent (Simple AI)
        def enemy_agent(state):
            pet = state.enemy_team.get_active_pet()
            if pet:
                # Just use first available ability
                for ability in pet.abilities:
                    if pet.can_use_ability(ability):
                        return TurnAction(actor='enemy', action_type='ability', ability=ability)
            return TurnAction(actor='enemy', action_type='pass')

        # 3. Run Simulation
        simulator = BattleSimulator(rng_seed=42)
        result = simulator.simulate_battle(initial_state, wizard_agent, enemy_agent)
        
        # 4. Format Output
        log_lines = result['log'].get_full_log().split('\n')
        
        return jsonify({
            "winner": result['winner'],
            "turns": result['turns'],
            "log": log_lines,
            "message": f"Simulation complete! Winner: {result['winner'].upper()} in {result['turns']} turns."
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Genetic Evolution State
genetic_state = {
    "status": "IDLE",
    "generation": 0,
    "max_generations": 0,
    "best_fitness": 0,
    "avg_fitness": 0,
    "top_teams": [],
    "stop_flag": False,
    "log": []
}

def run_evolution_thread(target_name, pop_size, generations, my_pets_only=True, leveling_mode=0):
    global genetic_state
    genetic_state["status"] = "RUNNING"
    genetic_state["generation"] = 0
    genetic_state["max_generations"] = generations
    genetic_state["stop_flag"] = False
    genetic_state["log"] = []
    genetic_state["target_encounter"] = target_name  # Store target name for export
    genetic_state["leveling_mode"] = leveling_mode
    
    try:
        from genetic.evolution import EvolutionEngine
        from genetic.fitness import FitnessEvaluator
        from simulator import Team, Pet, PetStats, PetFamily, PetQuality, Ability
        
        # 1. Setup Target Team - Load real encounter data from encounters_full.json
        try:
            # Load from new complete encounters API endpoint
            # This merges encounters_full.json abilities with species stats
            import requests
            response = requests.get('http://127.0.0.1:5000/api/encounters')
            if response.status_code == 200:
                encounters = response.json()
                encounter_data = encounters.get(target_name)
            else:
                raise FileNotFoundError(f"API returned {response.status_code}")
            
            # Build target team from complete encounter data
            target_pets = []
            for npc_pet in encounter_data['npc_pets']:
                family_map = {
                    'Magic': PetFamily.MAGIC,
                    'Humanoid': PetFamily.HUMANOID,
                    'Undead': PetFamily.UNDEAD,
                    'Beast': PetFamily.BEAST,
                    'Aquatic': PetFamily.AQUATIC,
                    'Mechanical': PetFamily.MECHANICAL,
                    'Elemental': PetFamily.ELEMENTAL,
                    'Flying': PetFamily.FLYING,
                    'Dragonkin': PetFamily.DRAGONKIN,
                    'Critter': PetFamily.CRITTER,
                }
                family = family_map.get(npc_pet['family'], PetFamily.BEAST)
                
                abilities = []
                for ab_data in npc_pet['abilities']:
                    abilities.append(Ability(
                        id=ab_data['id'],
                        name=ab_data['name'],
                        power=ab_data['power'],
                        accuracy=ab_data['accuracy'],
                        speed=ab_data['speed'],
                        cooldown=ab_data['cooldown'],
                        family=family
                    ))
                
                quality_map = {
                    'poor': PetQuality.POOR,
                    'common': PetQuality.COMMON,
                    'uncommon': PetQuality.UNCOMMON,
                    'rare': PetQuality.RARE,
                    'epic': PetQuality.EPIC,
                    'legendary': PetQuality.LEGENDARY
                }
                quality = quality_map.get(npc_pet.get('quality', 'rare').lower(), PetQuality.RARE)

                target_pets.append(Pet(
                    species_id=npc_pet['species_id'],
                    name=npc_pet['name'],
                    family=family,
                    quality=quality,
                    stats=PetStats(
                        max_hp=npc_pet['health'],
                        current_hp=npc_pet['health'],
                        power=npc_pet['power'],
                        speed=npc_pet['speed']
                    ),
                    abilities=abilities
                ))
            
            target_team = Team(pets=target_pets)
            genetic_state["log"].append(f"Loaded encounter: {encounter_data['name']}")
            
        except FileNotFoundError:
            # NO MOCK DATA - require real encounters.json
            genetic_state["log"].append("❌ ERROR: encounters.json not found!")
            genetic_state["log"].append("This is a SIMULATION - requires REAL encounter data.")
            genetic_state["log"].append("Run: ./venv/bin/python convert_lua_to_encounters.py")
            genetic_state["status"] = "ERROR"
            raise FileNotFoundError("encounters.json is required - no mock data allowed")
        
        # 2. Setup Data (Real Data + Manual Overrides)
        try:
            # Load Abilities from API (Base data)
            with open('abilities.json', 'r') as f:
                ability_data = json.load(f)
                real_abilities = ability_data.get('abilities', {})
                species_abilities = ability_data.get('species_abilities', {})
                
            # NEW: Load PetTracker Decoded Data (Primary Source)
            pt_species_abilities = {}
            pt_breeds = {}
            pt_base_stats = {}
            
            if os.path.exists('pettracker_decoded.json'):
                try:
                    with open('pettracker_decoded.json', 'r') as f:
                        pt_data = json.load(f)
                        pt_species_abilities = pt_data.get('species', {})
                        pt_breeds = pt_data.get('breeds', {})
                        pt_base_stats = pt_data.get('stats', {})
                        
                    genetic_state["log"].append(f"Loaded PetTracker data for {len(pt_species_abilities)} species")
                    
                    # Merge PetTracker abilities into species_abilities (Priority)
                    # PetTracker format: "species_id": {"1": [id], "2": [id]...}
                    # Target format: "species_id": [id1, id2, id3, id4, id5, id6]
                    for sid_str, slots in pt_species_abilities.items():
                        # Convert slots dict to list
                        ability_list = [0] * 6
                        for slot_idx, ability_ids in slots.items():
                            # PetTracker might have multiple options per slot? 
                            # The decoder returns a list of IDs. Usually it's just one.
                            # We'll take the first one for now as the default choice for that slot
                            if ability_ids:
                                idx = int(slot_idx) - 1
                                if 0 <= idx < 6:
                                    ability_list[idx] = ability_ids[0]
                        
                        # Only update if we have valid abilities
                        if any(aid > 0 for aid in ability_list):
                            species_abilities[sid_str] = ability_list
                            
                except Exception as e:
                    genetic_state["log"].append(f"Error loading PetTracker data: {e}")
            
            # Load manual ability stats override (since Blizzard API doesn't provide power/accuracy)
            try:
                with open('ability_stats_manual.json', 'r') as f:
                    manual_stats = json.load(f)
                    # Merge manual stats into real_abilities
                    for ab_id, stats in manual_stats.get('abilities', {}).items():
                        if ab_id in real_abilities:
                            # Override with manual stats
                            real_abilities[ab_id].update(stats)
                        genetic_state["log"].append(f"Loaded {len(manual_stats.get('abilities', {}))} manual ability stats")
            except FileNotFoundError:
                genetic_state["log"].append("WARNING: ability_stats_manual.json not found, using API defaults")
                
            # Load User Collection
            with open('my_pets.json', 'r') as f:
                collection_data = json.load(f)
                
            # Extract available species IDs
            available_species = []
            for pet in collection_data.get('pets', []):
                if 'species' in pet:
                    sid = pet['species']['id']
                    # Only include if we have ability data for it
                    if str(sid) in species_abilities:
                        # Apply my_pets_only filter
                        if my_pets_only:
                            # Only include pets the user actually owns
                            available_species.append(sid)
                        elif str(sid) in species_abilities:
                            # Include all pets with ability data
                            available_species.append(sid)
            
            # Remove duplicates
            available_species = list(set(available_species))
            
            genetic_state["log"].append(f"Available species pool: {len(available_species)} pets")
            if my_pets_only:
                genetic_state["log"].append("Using ONLY your pets")
            
            # Load species data for display
            species_info_map = {}
            if os.path.exists('species_data.json'):
                with open('species_data.json', 'r') as f:
                    species_data = json.load(f)
                    for sid_str, data in species_data.items():
                        species_info_map[int(sid_str)] = data
            
            if not available_species:
                raise Exception("No species data found. Please run fetch_ability_data.py first.")
                
            # Load NPC AI Priorities
            npc_priorities = {}
            try:
                if os.path.exists('npc_ai_priorities.json'):
                    with open('npc_ai_priorities.json', 'r') as f:
                        all_priorities = json.load(f)
                        # Find priorities for current target
                        # Try exact match first
                        if target_name in all_priorities:
                            npc_priorities = all_priorities[target_name]
                        else:
                            # Try fuzzy match
                            norm_target = target_name.lower().replace("'", "").replace(":", "").strip()
                            for tamer_name, priorities in all_priorities.items():
                                norm_tamer = tamer_name.lower().replace("'", "").replace(":", "").strip()
                                if norm_tamer in norm_target or norm_target in norm_tamer:
                                    npc_priorities = priorities
                                    genetic_state["log"].append(f"Loaded AI priorities for {tamer_name}")
                                    break
            except Exception as e:
                genetic_state["log"].append(f"Error loading AI priorities: {e}")

        except Exception as e:
            genetic_state["log"].append(f"Data load error: {str(e)}")
            print(f"Data load error: {e}")
            # Fallback or re-raise? Let's re-raise to be caught by main loop or just continue with what we have
            # For now, let's allow it to fall through to the main except if critical
            raise e

        # 3. Initialize Engine and build real pet stats map
        # Fix keys to be integers for the engine
        formatted_ability_db = {int(k): v for k, v in species_abilities.items()}
        
        # Build real pet stats map {species_id: {health, power, speed}}
        real_pet_stats = {}
        try:
            with open('my_pets.json') as f:
                collection = json.load(f)
                for pet in collection.get('pets', []):
                    if 'species' in pet and 'stats' in pet:
                        sid = pet['species']['id']
                        sid_str = str(sid)
                        
                        # Priority 1: Use actual stats from my_pets.json (if owned)
                        if sid not in real_pet_stats:  # Use first found (highest level)
                            real_pet_stats[sid] = {
                                'health': pet['stats'].get('health', 1400),
                                'power': pet['stats'].get('power', 280),
                                'speed': pet['stats'].get('speed', 280)
                            }
                        
                        # Priority 2: Calculate from PetTracker Base Stats + Breed (if available)
                        # This is useful if we want to simulate optimal breeds or if my_pets stats are missing
                        # For now, we stick to my_pets stats for owned pets.
                        
            # Fill in missing stats for species we don't own (if my_pets_only=False)
            # using PetTracker base stats assuming a standard breed (e.g. B/B or P/P)
            for sid in available_species:
                if sid not in real_pet_stats and str(sid) in pt_base_stats:
                    base = pt_base_stats[str(sid)]
                    # Assume Rare quality (1.3 multiplier approx? No, formula is different)
                    # Formula: (Base + Breed) * Level * Quality ...
                    # Simplified approximation for L25 Rare:
                    # Health = (Base + 0.5) * 25 * 1.3 + 100 ?? 
                    # Let's use a standard L25 Rare approximation:
                    # Power/Speed ~= Base * 12.5 ?
                    # Health ~= Base * 12.5 + 100 ?
                    # Actually, let's just use the raw multipliers scaled up to typical L25 values
                    # Typical Base is 8. 8 * X = 280 => X = 35
                    
                    real_pet_stats[sid] = {
                        'health': int(base['health'] * 180 + 100), # Approx
                        'power': int(base['power'] * 35),
                        'speed': int(base['speed'] * 35)
                    }
                    
        except Exception as e:
            print(f"Error building pet stats: {e}")
            pass  # Fallback to mock stats if file missing
        
        # Build species_db with family information for type advantage calculations
        species_db = {}
        # Initialize Fitness Evaluator
        evaluator = FitnessEvaluator(
            target_team=target_team,
            ability_db=real_abilities,
            species_db=species_info_map,
            npc_priorities=npc_priorities,
            target_name=target_name
        )
        
        # Monkey-patch real data into evaluator
        evaluator.real_abilities = real_abilities
        evaluator.real_pet_stats = real_pet_stats
        evaluator.pt_base_stats = pt_base_stats # Pass PetTracker base stats
        
        engine = EvolutionEngine(evaluator, population_size=pop_size)
        engine.initialize_population(available_species, formatted_ability_db)
        
        print(f"DEBUG: Starting loop. Generations: {generations}")
        
        # 4. Evolution Loop
        for gen in range(generations):
            if genetic_state["stop_flag"]:
                break
                
            stats = engine.evolve_generation(available_species)
            
            # Update State
            genetic_state["generation"] = gen + 1
            genetic_state["best_fitness"] = stats["best_fitness"]
            genetic_state["avg_fitness"] = stats["avg_fitness"]
            
            # Enhanced logging: show top 3 teams with win rates
            top_genomes = stats.get("top_genomes", [])
            
            # Build summary of top 3 teams
            team_summaries = []
            for i, genome in enumerate(top_genomes[:3]):
                species_ids = ",".join([str(p.species_id) for p in genome.pets])
                
                # Calculate wins and losses (5 battles per genome)
                num_battles = 5
                if hasattr(genome, 'stats') and genome.stats:
                    win_rate = genome.stats.get("win_rate", 0)
                    wins = int(win_rate * num_battles)
                    losses = num_battles - wins
                    record = f"{wins}W-{losses}L"
                else:
                    record = "0W-3L"
                
                team_summaries.append(f"#{i+1}:[{species_ids}] {record}")
            
            teams_str = " | ".join(team_summaries) if team_summaries else "No teams"
            
            # Log with detailed team info
            genetic_state["log"].append(
                f"Gen {gen+1}: Fitness {stats['best_fitness']:.0f} | {teams_str}"
            )
                
            time.sleep(0.1) # Yield to main thread
            
        # 5. Finish
        genetic_state["status"] = "COMPLETED"
        if 'stats' not in locals():
            genetic_state["log"].append("ERROR: Evolution loop did not run")
            return

        print(f"DEBUG: stats keys: {stats.keys()}")
        
        genetic_state["top_teams"] = [
            {
                "fitness": genome.fitness,
                "pets": [
                    {
                        "species_id": p.species_id, 
                        "name": species_info_map.get(p.species_id, {}).get('name', f"Species {p.species_id}"),
                        "family_id": species_info_map.get(p.species_id, {}).get('family_id', 0),
                        "abilities": p.abilities,  # List of ability IDs
                        "priority": p.strategy.priority  # Ability priority order
                    }
                    for p in genome.pets
                ],
                "stats": genome.stats
            }
            for genome in stats.get("top_genomes", [])
        ]
        
    except Exception as e:
        import traceback
        error_msg = f"Evolution error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)  # Print to server console
        genetic_state["log"].append(f"ERROR: {str(e)}")
        genetic_state["status"] = "ERROR"

@app.route('/test')
def test_page():
    return render_template('test.html')

@app.route('/api/encounters')
def get_encounters():
    """
    Serve encounters with complete ability data from encounters_full.json
    merged with species stats and family information.
    """
    try:
        # Load encounters_full.json with complete ability data
        with open('encounters_full.json', 'r') as f:
            encounters_full = json.load(f)
        
        # Load species data for stats and family
        species_data = {}
        if os.path.exists('species_data.json'):
            with open('species_data.json', 'r') as f:
                species_raw = json.load(f)
                species_data = {int(k): v for k, v in species_raw.items()}
        
        # Convert to old format for compatibility
        encounters_dict = {}
        for tamer in encounters_full:
            # Create key from name (lowercase, replace spaces with hyphens)
            key = tamer['name'].lower().replace(' ', '-').replace("'", "")
            
            encounters_dict[key] = {
                'id': tamer.get('npc_id', 0),
                'name': tamer['name'],
                'npc_pets': []
            }
            
            for pet in tamer['pets']:
                species_id = pet['species_id']
                
                # Get species info for family and stats
                species_info = species_data.get(species_id, {})
                family_name = species_info.get('family_name', 'Beast')
                
                # Calculate L25 Rare stats (using simplified formula)
                level = pet.get('level', 25)
                quality = pet.get('quality', 4)  # 4 = Rare
                
                # Base stats approximation (will be more accurate with real species base stats)
                base_health = 100
                base_power = 10
                base_speed = 10
                
                if 'base_stats' in species_info:
                    base_stats = species_info['base_stats']
                    base_health = base_stats.get('health', 10)
                    base_power = base_stats.get('power', 10)
                    base_speed = base_stats.get('speed', 10)
                
                # Level 25 Rare approximation
                health = int(base_health * 18 + 100) if level == 25 else 1400
                power = int(base_power * 35) if level == 25 else 280
                speed = int(base_speed * 35) if level == 25 else 280
                
                npc_pet = {
                    'species_id': species_id,
                    'name': species_info.get('name', f'Pet {species_id}'),
                    'family': family_name,
                    'quality': ['Poor', 'Common', 'Uncommon', 'Rare', 'Epic', 'Legendary'][quality] if quality < 6 else 'Rare',
                    'health': health,
                    'power': power,
                    'speed': speed,
                    'abilities': pet.get('abilities', [])
                }
                
                encounters_dict[key]['npc_pets'].append(npc_pet)
        
        return jsonify(encounters_dict)
    
    except FileNotFoundError as e:
        return jsonify({'error': f'Data file not found: {str(e)}'}), 404
    except Exception as e:
        return jsonify({'error': f'Failed to load encounters: {str(e)}'}), 500


@app.route('/genetic')
def genetic_dashboard():
    # Load encounters from the new API endpoint which has complete ability data
    encounters = {}
    try:
        # Call our own API endpoint to get complete encounters
        import requests
        response = requests.get('http://127.0.0.1:5000/api/encounters')
        if response.status_code == 200:
            encounters = response.json()
    except:
        # Fallback to direct file loading if API not available
        if os.path.exists('encounters.json'):
            with open('encounters.json', 'r') as f:
                encounters = json.load(f)
    return render_template('genetic.html', encounters=encounters)

@app.route('/genetic-simple')
def genetic_simple():
    return render_template('genetic_simple.html')

@app.route('/api/genetic/start', methods=['POST'])
def start_evolution():
    data = request.json
    if genetic_state["status"] == "RUNNING":
        return jsonify({"error": "Already running"}), 400
        
    # Reset state
    genetic_state["log"] = []
    genetic_state["top_teams"] = []
    genetic_state["stop_flag"] = False
    genetic_state["status"] = "RUNNING"
    
    thread = threading.Thread(target=run_evolution_thread, args=(
        data.get('target', 'squirt'),
        int(data.get('pop_size', 50)),
        int(data.get('generations', 20))
    ))
    thread.start()
    return jsonify({"message": "Started"})

@app.route('/api/genetic/status')
def get_evolution_status():
    # Return status and new logs
    offset = int(request.args.get('offset', 0))
    
    response = genetic_state.copy()
    # Send only new logs
    if offset < len(genetic_state["log"]):
        response["new_logs"] = genetic_state["log"][offset:]
        response["log_offset"] = len(genetic_state["log"])
    else:
        response["new_logs"] = []
        response["log_offset"] = offset
        
    # Don't send the full log in the response to save bandwidth
    del response["log"]
    
    return jsonify(response)

@app.route('/api/genetic/stop', methods=['POST'])
def stop_evolution():
    genetic_state["stop_flag"] = True
    return jsonify({"message": "Stopping..."})

@app.route('/api/goblin/protected')
def get_protected_pets():
    """Generate list of pets to protect (do not sell) for Goblin integration"""
    try:
        protected_pets = {} # pet_id -> reason
        
        # 1. Protect all pets used in strategies
        if os.path.exists('strategies_enhanced.json'):
            with open('strategies_enhanced.json', 'r') as f:
                strategies_data = json.load(f)
                
                for expansion, categories in strategies_data.items():
                    for category, encounters in categories.items():
                        for encounter in encounters:
                            for strategy in encounter.get('strategies', []):
                                for slot in strategy.get('pet_slots', []):
                                    for pet_option in slot:
                                        pet_id = pet_option.get('id')
                                        pet_name = pet_option.get('name', 'Unknown')
                                        
                                        if pet_id and pet_id != 0:
                                            if pet_id not in protected_pets:
                                                protected_pets[pet_id] = {
                                                    "name": pet_name,
                                                    "reasons": set()
                                                }
                                            protected_pets[pet_id]["reasons"].add("Used in strategy")

        # 2. Protect favorites (if we had a favorites system fully persisted)
        # For now, let's just stick to strategies
        
        # Convert sets to lists for JSON serialization
        export_list = []
        for pid, data in protected_pets.items():
            export_list.append({
                "id": pid,
                "name": data["name"],
                "reason": ", ".join(data["reasons"])
            })
            
        # Save to file for external access
        with open('protected_pets.json', 'w') as f:
            json.dump({"protected": export_list, "generated_at": datetime.now().isoformat()}, f, indent=2)
            
        return jsonify({
            "count": len(export_list),
            "file_path": os.path.abspath('protected_pets.json'),
            "protected_pets": export_list
        })
        
    except Exception as e:
        print(f"Error generating protected list: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/maintenance/fetch-species')
def trigger_species_fetch():
    """Fetch species data from Blizzard API to populate family info"""
    try:
        if not os.path.exists('my_pets.json'):
            return jsonify({"error": "my_pets.json not found"}), 404
            
        with open('my_pets.json', 'r') as f:
            pets_data = json.load(f)
            
        unique_species_ids = set()
        for pet in pets_data.get('pets', []):
            if 'species' in pet and 'id' in pet['species']:
                unique_species_ids.add(pet['species']['id'])
        
        # Load existing cache
        species_cache = {}
        if os.path.exists('species_data.json'):
            with open('species_data.json', 'r') as f:
                species_cache = json.load(f)
        
        # Identify missing
        missing_ids = [sid for sid in unique_species_ids if str(sid) not in species_cache]
        
        if not missing_ids:
            return jsonify({"message": "All species data already cached", "count": len(species_cache)})
            
        # Fetch missing (limit to 50 to avoid timeout/rate limits for now)
        client = get_blizzard_client()
        count = 0
        for sid in missing_ids[:50]: 
            try:
                # Fetch pet info
                # We need to use the Battle.net API client
                # Using the client directly if possible, or constructing the URL
                # The client object from OAuth2Session might not be enough if token expired
                # But let's assume it works or use a helper
                
                # We can use the token from the session if available, or get a new one
                # For simplicity, let's assume we have a valid token or client
                
                # Actually, get_blizzard_client returns an OAuth2Session. 
                # We need to make sure we have a token.
                
                resp = client.get(f"https://us.api.blizzard.com/data/wow/pet/{sid}?namespace=static-us&locale=en_US")
                if resp.status_code == 200:
                    data = resp.json()
                    species_cache[str(sid)] = {
                        "name": data.get("name"),
                        "family_id": data.get("battle_pet_type", {}).get("id"),
                        "family_name": data.get("battle_pet_type", {}).get("name")
                    }
                    count += 1
                    print(f"Fetched species {sid}: {data.get('name')}")
                else:
                    print(f"Failed to fetch species {sid}: {resp.status_code}")
                    
            except Exception as e:
                print(f"Error fetching species {sid}: {e}")
        
        # Save cache
        with open('species_data.json', 'w') as f:
            json.dump(species_cache, f, indent=2)
            
        return jsonify({
            "message": f"Fetched {count} new species", 
            "total_cached": len(species_cache),
            "remaining": len(missing_ids) - count
        })
        
    except Exception as e:
        print(f"Error in species fetch: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analytics/collection-health')
def get_collection_health():
    """Analyze pet collection for strategic gaps and coverage"""
    try:
        # Pet family mapping
        families = {
            1: "Humanoid", 2: "Dragonkin", 3: "Flying", 4: "Undead",
            5: "Critter", 6: "Magic", 7: "Elemental", 8: "Beast",
            9: "Aquatic", 10: "Mechanical"
        }
        
        # Load species cache
        species_cache = {}
        if os.path.exists('species_data.json'):
            with open('species_data.json', 'r') as f:
                species_cache = json.load(f)
        
        # Initialize coverage tracking
        family_coverage = {name: {"owned": 0, "needed": 0, "missing_roles": []} for name in families.values()}
        strategic_value = {}  # pet_id -> number of strategies it unlocks
        
        # Load data
        owned_pets = {}
        if os.path.exists('my_pets.json'):
            with open('my_pets.json', 'r') as f:
                pets_data = json.load(f)
                for pet in pets_data.get('pets', []):
                    # Safe access
                    species = pet.get('species', {})
                    if not species: continue
                    
                    pet_id = species.get('id')
                    pet_name = species.get('name', 'Unknown')
                    if isinstance(pet_name, dict):
                        pet_name = pet_name.get('en_US', 'Unknown')
                    
                    # Try to get family from cache first, then stats
                    family_id = None
                    if str(pet_id) in species_cache:
                        family_id = species_cache[str(pet_id)].get('family_id')
                    
                    if not family_id:
                        family_id = pet.get('stats', {}).get('pet_type_id')
                    
                    owned_pets[pet_name] = {
                        'family_id': family_id,
                        'level': pet.get('level', 1),
                        'quality': pet.get('quality', {}).get('name', 'Unknown')
                    }
                    
                    # Count owned by family
                    if family_id in families:
                        family_coverage[families[family_id]]["owned"] += 1
        
        # Analyze strategies to find needed pets
        if os.path.exists('strategies_enhanced.json'):
            with open('strategies_enhanced.json', 'r') as f:
                strategies_data = json.load(f)
                
                # Iterate through expansions and categories
                for expansion, categories in strategies_data.items():
                    for category, encounters in categories.items():
                        for encounter in encounters:
                            for strategy in encounter.get('strategies', []):
                                for slot in strategy.get('pet_slots', []):
                                    for pet_option in slot:
                                        pet_name = pet_option.get('name', 'Unknown')
                                        pet_id = pet_option.get('id')
                                        
                                        # Track strategic value
                                        if pet_id and pet_id != 0 and str(pet_id) != "0":
                                            # Filter out numeric names (often placeholders like "1", "2")
                                            if pet_name.isdigit():
                                                continue
                                            
                                            # Filter out unattainable pets
                                            unattainable_pets = {118572, 79792, 128494, 115589}
                                            if pet_id in unattainable_pets:
                                                continue
                                                
                                            if pet_id not in strategic_value:
                                                strategic_value[pet_id] = {"name": pet_name, "unlocks": 0}
                                            
                                            if pet_name not in owned_pets:
                                                strategic_value[pet_id]["unlocks"] += 1
        
        
        # Helper to build WarcraftPets URL
        def get_warcraftpets_url(pet_id, pet_name):
            family_map = {
                1: "humanoid", 2: "dragonkin", 3: "flying", 4: "undead",
                5: "critter", 6: "magic", 7: "elemental", 8: "beast",
                9: "aquatic", 10: "mechanical"
            }
            rarity_slug = "rare"
            name_slug = pet_name.lower().replace("'", "").replace(" ", "-").replace(":", "")
            name_slug = ''.join(c for c in name_slug if c.isalnum() or c == '-')
            family_slug = family_map.get(pet_id, "battle")
            return f"https://www.warcraftpets.com/wow-pets/{family_slug}/{rarity_slug}/{name_slug}/"

        # Find high-value missing pets with URLs
        missing_high_value = sorted(
            [{"id": pid, "name": data["name"], "unlocks": data["unlocks"], "warcraftpets_url": get_warcraftpets_url(pid, data["name"])} 
             for pid, data in strategic_value.items() if data["unlocks"] > 0],
            key=lambda x: x["unlocks"],
            reverse=True
        )[:10]
        
        # Calculate overall health score (0-100)
        total_families = len(families)
        families_with_pets = sum(1 for f in family_coverage.values() if f["owned"] > 0)
        diversity_score = (families_with_pets / total_families) * 100
        
        # Calculate completeness (based on strategic needs)
        total_strategic_pets = len(strategic_value)
        owned_strategic_pets = sum(1 for pet_id, data in strategic_value.items() if data["unlocks"] == 0)
        completeness_score = (owned_strategic_pets / total_strategic_pets * 100) if total_strategic_pets > 0 else 100
        
        overall_score = (diversity_score * 0.3 + completeness_score * 0.7)
        
        return jsonify({
            "overall_score": round(overall_score, 1),
            "diversity_score": round(diversity_score, 1),
            "completeness_score": round(completeness_score, 1),
            "family_coverage": family_coverage,
            "missing_high_value": missing_high_value,
            "total_owned": len(owned_pets),
            "total_unique_species": len(strategic_value)
        })
        
    except Exception as e:
        print(f"Error in collection health: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/leveling')
def leveling():
    """Leveling queue planner"""
    return render_template('leveling.html')

@app.route('/xp-encounters')
def xp_encounters():
    """Best XP encounters"""
    return render_template('xp_encounters.html')

@app.route('/api/progress')
def get_progress():
    """Get user progress data from saved files"""
    progress = {
        "favorites": [],
        "completed": {},
        "statistics": {
            "totalBattles": 0,
            "totalWins": 0,
            "totalLosses": 0,
            "winRate": 0
        }
    }
    
    # Would typically read from PetWeaverProgressDB if we had a sync
    # For now, return mock data or empty structure
    return jsonify(progress)

@app.route('/api/recommendations')
def get_recommendations():
    """Get smart "Do These Next" recommendations"""
    try:
        recommendations = []
        
        # Load ready strategies
        if os.path.exists('my_ready_strategies.json'):
            with open('my_ready_strategies.json', 'r') as f:
                data = json.load(f)
                
                # Prioritize by various factors
                for exp_name, expansions in data.items():
                    for cat_name, encounters in expansions.items():
                        for encounter in encounters:
                            # Score based on: expansion recency, category value
                            score = 0
                            if "War Within" in exp_name or "Dragonflight" in exp_name:
                                score += 10
                            if "World Quest" in cat_name:
                                score += 5
                            
                            recommendations.append({
                                "name": encounter.get('encounter_name', 'Unknown'),
                                "expansion": exp_name,
                                "category": cat_name,
                                "score": score,
                                "reason": f"High priority {cat_name} in {exp_name}"
                            })
                
                # Sort by score and take top 10
                recommendations.sort(key=lambda x: x['score'], reverse=True)
                recommendations = recommendations[:10]
        
        return jsonify(recommendations)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/strategies/all')
def get_all_strategies():
    """Get all strategies for browsing"""
    try:
        if os.path.exists('my_ready_strategies.json'):
            with open('my_ready_strategies.json', 'r') as f:
                data = json.load(f)
                
                # Flatten for easier browsing
                all_strategies = []
                for exp_name, expansions in data.items():
                    for cat_name, encounters in expansions.items():
                        for encounter in encounters:
                            all_strategies.append({
                                "name": encounter.get('encounter_name', 'Unknown'),
                                "expansion": exp_name,
                                "category": cat_name,
                                "teams": encounter.get('strategies', [])
                            })
                
                return jsonify(all_strategies)
        
        return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hunting/missing')
def get_missing_pets():
    """Get list of missing pets needed for ready strategies"""
    try:
        missing_pets = {}
        
        # WarcraftPets URL builder
        def get_warcraftpets_url(pet_id, pet_name):
            # Pet family mapping (pet_type_id -> URL slug)
            family_map = {
                1: "humanoid", 2: "dragonkin", 3: "flying", 4: "undead",
                5: "critter", 6: "magic", 7: "elemental", 8: "beast",
                9: "aquatic", 10: "mechanical"
            }
            
            # Rarity tier mapping (approximate - using common pets as "common", most as "uncommon/rare")
            # Since we don't have rarity in strategies data, we'll default to "rare" as most battle pets are
            rarity_slug = "rare"  # Default to rare as it's most common for battle pets
            
            # For specific known pets, override rarity
            mythical_pets = {150381, 150385, 154832}  # Known mythical/special pets
            if pet_id in mythical_pets:
                rarity_slug = "mythical"
            
            # Get family slug (default to "battle" if unknown)
            # We'll need to look this up from the pet data
            family_slug = "battle"  # Default fallback
            
            # Try to get family from my_pets.json if available
            if os.path.exists('my_pets.json'):
                try:
                    with open('my_pets.json', 'r') as f:
                        pets_data = json.load(f)
                        for pet in pets_data.get('pets', []):
                            if pet.get('species', {}).get('id') == pet_id:
                                family_id = pet.get('stats', {}).get('pet_type_id')
                                if family_id in family_map:
                                    family_slug = family_map[family_id]
                                break
                except: pass
            
            # Also check strategies_enhanced.json for family hints
            if family_slug == "battle" and os.path.exists('strategies_enhanced.json'):
                # family_slug will stay as fallback if not found
                pass
            
            # Build name slug
            name_slug = pet_name.lower().replace("'", "").replace(" ", "-").replace(":", "")
            name_slug = ''.join(c for c in name_slug if c.isalnum() or c == '-')
            
            return f"https://www.warcraftpets.com/wow-pets/{family_slug}/{rarity_slug}/{name_slug}/"
        
        
        # Pet location database (ID -> Location Info)
        pet_locations = {
            115146: {"zone": "Maldraxxus", "source": "Wild Battle", "coords": "Various locations"},
            86447: {"zone": "Spires of Arak", "source": "Wild Battle", "coords": "Throughout zone"},
            143564: {"zone": "Drustvar", "source": "Wild Battle", "coords": "Throughout zone"},
            55367: {"zone": "Darkmoon Faire", "source": "Vendor (Lhara)", "coords": "Darkmoon Island"},
            64899: {"zone": "Vale of Eternal Blossoms", "source": "Wild Battle", "coords": "Throughout zone"},
            68819: {"zone": "Timeless Isle", "source": "Wild Battle", "coords": "Various locations"},
            68820: {"zone": "Dread Wastes", "source": "Wild Battle", "coords": "Throughout zone"},
            116155: {"zone": "Un'Goro Crater", "source": "Vendor", "coords": "Marshal's Stand"},
            39896: {"zone": "Deepholm", "source": "Wild Battle", "coords": "Throughout zone"},
            71033: {"zone": "Vale of Eternal Blossoms", "source": "Quest Reward", "coords": "Mogu'shan Palace"},
            88134: {"zone": "Draenor", "source": "Engineering", "coords": "Crafted"},
            143796: {"zone": "Drustvar", "source": "Vendor", "coords": "Arom's Stand"},
            88577: {"zone": "Draenor", "source": "Archaeology", "coords": "Fossil Solve"},
            97324: {"zone": "Tanaan Jungle", "source": "Drop (Bleeding Hollow)", "coords": "Zeth'Gol"},
            154814: {"zone": "Nazjatar", "source": "Wild Battle", "coords": "Throughout zone"},
            115148: {"zone": "Maldraxxus", "source": "Wild Battle", "coords": "Throughout zone"},
            113440: {"zone": "Azsuna", "source": "World Quest", "coords": "Seabrine Coves"},
            69748: {"zone": "Throne of Thunder", "source": "Drop (Sand Elementals)", "coords": "Raid"},
            68846: {"zone": "Kun-Lai Summit", "source": "Wild Battle", "coords": "Throughout zone"},
            68805: {"zone": "Feralas", "source": "Wild Battle", "coords": "Throughout zone"},
            68654: {"zone": "Duskwood", "source": "Vendor", "coords": "Darkshire"},
            172148: {"zone": "Mechagon", "source": "Drop", "coords": "Operation: Mechagon"},
            61080: {"zone": "Various", "source": "Wild Battle", "coords": "Starting Zones"},
            90206: {"zone": "Black Temple", "source": "Drop (Reliquary)", "coords": "Raid"},
            68666: {"zone": "Molten Core", "source": "Drop (Golemagg)", "coords": "Raid"},
            86081: {"zone": "Netherstorm", "source": "Wild Battle", "coords": "Throughout zone"},
            25706: {"zone": "Mount Hyjal", "source": "Wild Battle", "coords": "Throughout zone"},
            68664: {"zone": "Molten Core", "source": "Drop (Magmadar)", "coords": "Raid"},
            32791: {"zone": "Noblegarden", "source": "Event Vendor", "coords": "Holiday Event"},
            61366: {"zone": "Various", "source": "Wild Battle", "coords": "Starting Zones"},
            54227: {"zone": "Darkmoon Faire", "source": "Achievement", "coords": "Darkmoon Island"},
            62818: {"zone": "Grizzly Hills", "source": "Wild Battle", "coords": "Throughout zone"},
            61081: {"zone": "Various", "source": "Wild Battle", "coords": "Starting Zones"},
            61826: {"zone": "Western Plaguelands", "source": "Wild Battle", "coords": "Andorhal"},
            90203: {"zone": "Black Temple", "source": "Drop (Reliquary)", "coords": "Raid"},
            90204: {"zone": "Black Temple", "source": "Drop (Reliquary)", "coords": "Raid"},
            127863: {"zone": "Stormheim", "source": "Wild Battle", "coords": "Throughout zone"},
            127862: {"zone": "Silithus", "source": "Wild Battle", "coords": "Throughout zone"},
            68467: {"zone": "Vale of Eternal Blossoms", "source": "Wild Battle", "coords": "Throughout zone"},
            90212: {"zone": "Isle of Quel'Danas", "source": "Drop", "coords": "Sunwell Plateau"},
            149205: {"zone": "Drustvar", "source": "Wild Battle", "coords": "Throughout zone"},
            143041: {"zone": "Nazmir", "source": "Wild Battle", "coords": "Throughout zone"},
            29726: {"zone": "Account", "source": "Promotion", "coords": "Merge Account"},
            32595: {"zone": "Northrend", "source": "Reputation", "coords": "Kalu'ak"},
            21010: {"zone": "Exodar", "source": "Vendor", "coords": "Crystal Hall"},
            62050: {"zone": "Various", "source": "Wild Battle", "coords": "Starting Zones"},
            65187: {"zone": "Dread Wastes", "source": "Wild Battle", "coords": "Throughout zone"},
            90201: {"zone": "Black Temple", "source": "Drop (Supremus)", "coords": "Raid"},
            62922: {"zone": "Deepholm", "source": "Wild Battle", "coords": "Throughout zone"},
            62182: {"zone": "Deepholm", "source": "Wild Battle", "coords": "Throughout zone"},
            62246: {"zone": "Darkshore", "source": "Wild Battle", "coords": "Throughout zone"},
            98463: {"zone": "Class Hall", "source": "Order Hall", "coords": "Druid"},
            71488: {"zone": "Hyjal", "source": "Vendor", "coords": "Guardians of Hyjal"},
            154832: {"zone": "Nazjatar", "source": "Drop: Elderspawn Nalaada", "coords": "Unknown"},
            46898: {"zone": "Profession", "source": "Enchanting (Horde)", "coords": "N/A"},
            127850: {"zone": "Blackwing Descent", "source": "Drop: Omnotron Defense System", "coords": "Raid"},
            96404: {"zone": "Profession", "source": "Enchanting", "coords": "N/A"},
            62317: {"zone": "Felwood", "source": "Wild Pet (Shatter Scar Vale)", "coords": "39, 44"},
            65313: {"zone": "Black Market Auction House", "source": "Auction", "coords": "N/A"},
            173990: {"zone": "The Maw", "source": "Wild Pet", "coords": "Various"},
            161921: {"zone": "Ny'alotha", "source": "Drop: Ra-den", "coords": "Raid"},
            163646: {"zone": "Uldum", "source": "Quest: Shadowbarb Hatchling", "coords": "Ramkahen"},
            179179: {"zone": "The Maw", "source": "Wild Pet", "coords": "Various"},
            173850: {"zone": "Torghast", "source": "Drop: Decayspeaker", "coords": "Dungeon"},
            128159: {"zone": "Argus (Eredath)", "source": "Drop: Ataxon", "coords": "Unknown"},
            179166: {"zone": "Tazavesh", "source": "Drop: Postmaster", "coords": "Dungeon"},
            154777: {"zone": "Mechagon", "source": "Wild Pet (Rare Spawn)", "coords": "Various"},
            179239: {"zone": "Torghast", "source": "Drop: Adamant Vaults Bosses", "coords": "Dungeon"},
            161946: {"zone": "Ny'alotha", "source": "Drop: N'Zoth", "coords": "Raid"},
            29147: {"zone": "Dalaran (Northrend)", "source": "Vendor: Darahir", "coords": "Underbelly"},
            15358: {"zone": "Unavailable", "source": "Collector's Edition (EU)", "coords": "N/A"},
            88692: {"zone": "Shadowmoon Valley (Draenor)", "source": "Drop: Demidos", "coords": "Socrethar's Rise"},
            175203: {"zone": "Unavailable", "source": "BlizzConline 2021", "coords": "N/A"},
            154720: {"zone": "Nazjatar", "source": "Wild Pet", "coords": "Various"},
            150381: {"zone": "Revendreth", "source": "Wild Pet", "coords": "Various"},
            150385: {"zone": "Revendreth", "source": "Wild Pet", "coords": "Various"},
            61703: {"zone": "Arathi Highlands", "source": "Wild Pet", "coords": "Various"},
            182768: {"zone": "Zereth Mortis", "source": "Wild Pet", "coords": "Various"},
            73352: {"zone": "Siege of Orgrimmar", "source": "Drop: Siegecrafter Blackfuse", "coords": "Raid"},
            231454: {"zone": "Hallow's End", "source": "Event Drop", "coords": "N/A"},
            208637: {"zone": "Dragonflight", "source": "Vendor/Reputation", "coords": "Unknown"},
            97206: {"zone": "Val'sharah", "source": "Drop: Dreamweaver Cache", "coords": "N/A"},
            143464: {"zone": "Nazmir", "source": "Wild Pet", "coords": "Various"},
            115785: {"zone": "Stormheim", "source": "World Quest: Falcosaur Swarm", "coords": "N/A"},
            154855: {"zone": "Mechagon", "source": "Crafting/Drop", "coords": "N/A"},
            154856: {"zone": "Mechagon", "source": "Drop: HK-8 Aerial Oppression Unit", "coords": "Dungeon"},
            115784: {"zone": "Highmountain", "source": "World Quest: Falcosaur Swarm", "coords": "N/A"},
            128388: {"zone": "Antoran Wastes", "source": "Drop: Mother Rosula", "coords": "Unknown"},
            51090: {"zone": "Hillsbrad Foothills", "source": "Quest: Lawn of the Dead", "coords": "Brazie's Farmstead"},
            71033: {"zone": "Karazhan", "source": "Drop: Terestian Illhoof", "coords": "Raid"},
            143197: {"zone": "Vol'dun", "source": "Drop: Jenafur (Secret)", "coords": "Unknown"},
            9662: {"zone": "Feralas", "source": "Drop: Sprite Darter Egg", "coords": "Unknown"},
            67319: {"zone": "Darkmoon Island", "source": "Vendor: Lhara", "coords": "Darkmoon Faire"},
            96405: {"zone": "Profession", "source": "Enchanting", "coords": "N/A"},
            62555: {"zone": "Hellfire Peninsula", "source": "Wild Pet", "coords": "Various"},
            128137: {"zone": "Argus", "source": "Wild Pet", "coords": "Various"},
            183772: {"zone": "Torghast", "source": "Drop", "coords": "Dungeon"},
            106232: {"zone": "Azsuna", "source": "Vendor/Reputation", "coords": "Unknown"},
            28883: {"zone": "Icecrown", "source": "Collector's Edition (WotLK)", "coords": "N/A"},
            171242: {"zone": "Drustvar", "source": "Wild Pet", "coords": "Various"},
            143798: {"zone": "Nazjatar", "source": "Wild Pet", "coords": "Various"},
            73542: {"zone": "Timeless Isle", "source": "Wild Pet", "coords": "Various"},
            62669: {"zone": "Howling Fjord", "source": "Wild Pet", "coords": "Various"}
        }
        
        if os.path.exists('my_ready_strategies.json') and os.path.exists('my_pets.json'):
            # Load user's current pets and map by name (since IDs might mismatch between Species/NPC)
            with open('my_pets.json', 'r') as f:
                pet_data = json.load(f)
                owned_names = set()
                for pet in pet_data.get('pets', []):
                    if 'species' in pet and 'name' in pet['species']:
                        # Handle localized names
                        name_data = pet['species']['name']
                        if isinstance(name_data, dict):
                            name = name_data.get('en_US')
                        else:
                            name = name_data
                        if name:
                            owned_names.add(name)
            
            # Load strategies to see which pets are needed
            # Use strategies_enhanced.json for the full list of strategies (including those we don't have pets for)
            strategy_file = 'strategies_enhanced.json' if os.path.exists('strategies_enhanced.json') else 'my_ready_strategies.json'
            
            with open(strategy_file, 'r') as f:
                data = json.load(f)
                
                for exp_name, expansions in data.items():
                    if not isinstance(expansions, dict): continue
                    for cat_name, encounters in expansions.items():
                        for encounter in encounters:
                            for strategy in encounter.get('strategies', []):
                                for slot in strategy.get('pet_slots', []):
                                    if not slot: continue
                                    
                                    # Check if we own ANY pet in this slot (alternatives)
                                    slot_filled = False
                                    for option in slot:
                                        opt_name = option.get('name', 'Unknown')
                                        if opt_name in owned_names:
                                            slot_filled = True
                                            break
                                    
                                    if slot_filled:
                                        continue
                                        
                                    # If slot is not filled, find the first available pet to hunt
                                    target_pet = None
                                    for option in slot:
                                        pid = int(option.get('id', 0))
                                        pname = option.get('name', 'Unknown')
                                        
                                        # Skip invalid
                                        if pid == 0 or pname.isdigit(): continue
                                        
                                        # Check if unavailable/unattainable
                                        is_unattainable = pid in {118572, 79792, 128494, 115589}
                                        loc_info = pet_locations.get(pid)
                                        is_unavailable = loc_info and loc_info.get('zone') == 'Unavailable'
                                        
                                        if not is_unattainable and not is_unavailable:
                                            target_pet = option
                                            break
                                    
                                    if target_pet:
                                        pet_id = int(target_pet.get('id'))
                                        pet_name = target_pet.get('name', 'Unknown')
                                        
                                        if pet_id not in missing_pets:
                                            location = pet_locations.get(pet_id, {
                                                "zone": "Unknown",
                                                "source": "Check WarcraftPets",
                                                "coords": "N/A"
                                            })
                                            
                                            missing_pets[pet_id] = {
                                                "id": pet_id,
                                                "name": pet_name,
                                                "zone": location["zone"],
                                                "source": location["source"],
                                                "coords": location["coords"],
                                                "warcraftpets_url": get_warcraftpets_url(pet_id, pet_name),
                                                "needed_for": []
                                            }
                                        
                                        if encounter.get('encounter_name') not in missing_pets[pet_id]['needed_for']:
                                            missing_pets[pet_id]['needed_for'].append(encounter.get('encounter_name', 'Unknown'))
        
        # Convert to list and sort by how many encounters need them
        result = sorted(missing_pets.values(), key=lambda x: len(x['needed_for']), reverse=True)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/leveling/queue')
def get_leveling_queue():
    """Get priority list of pets to level"""
    try:
        pets_to_level = {}
        
        if os.path.exists('my_pets.json') and os.path.exists('my_ready_strategies.json'):
            # Load owned pets and their levels, mapped by NAME
            with open('my_pets.json', 'r') as f:
                pet_data = json.load(f)
                owned_pets = {}
                for pet in pet_data.get('pets', []):
                    if 'species' not in pet:
                        continue
                    
                    # Get name
                    name_data = pet['species'].get('name')
                    if isinstance(name_data, dict):
                        name = name_data.get('en_US')
                    else:
                        name = name_data
                        
                    if not name:
                        continue
                        
                    level = pet.get('level', 1)
                    quality = pet.get('quality', 0)
                    
                    # Track highest level/quality of each species (by name)
                    if name not in owned_pets or level > owned_pets[name]['level']:
                        owned_pets[name] = {
                            'level': level,
                            'quality': quality,
                            'name': name,
                            'id': pet['species'].get('id')
                        }
            
            # Find which owned pets are used in ready strategies but not max level
            with open('my_ready_strategies.json', 'r') as f:
                data = json.load(f)
                
                for exp_name, expansions in data.items():
                    for cat_name, encounters in expansions.items():
                        for encounter in encounters:
                            for strategy in encounter.get('strategies', []):
                                for slot in strategy.get('pet_slots', []):
                                    if slot and slot[0]:
                                        pet = slot[0]
                                        pet_id = int(pet.get('id'))
                                        pet_name = pet.get('name', 'Unknown')
                                        
                                        # Check if owned (by name) but needs work (Level < 25 OR Quality != RARE)
                                        if pet_name in owned_pets:
                                            pet_data = owned_pets[pet_name]
                                            current_level = pet_data['level']
                                            
                                            # Check quality
                                            quality_info = pet_data.get('quality')
                                            is_rare = False
                                            if isinstance(quality_info, dict):
                                                is_rare = quality_info.get('type') == 'RARE'
                                            
                                            needs_level = current_level < 25
                                            needs_rarity = not is_rare
                                            
                                            if needs_level or needs_rarity:
                                                if pet_id not in pets_to_level:
                                                    pets_to_level[pet_id] = {
                                                        'id': pet_id,
                                                        'name': pet_name,
                                                        'current_level': current_level,
                                                        'quality': quality_info,
                                                        'needs_level': needs_level,
                                                        'needs_rarity': needs_rarity,
                                                        'needed_for': [],
                                                        'priority': 0
                                                    }
                                                
                                                pets_to_level[pet_id]['needed_for'].append(encounter.get('encounter_name', 'Unknown'))
                                                pets_to_level[pet_id]['priority'] = len(pets_to_level[pet_id]['needed_for'])
        
        # Convert to list and sort by priority (most needed first)
        result = sorted(pets_to_level.values(), key=lambda x: x['priority'], reverse=True)
        return jsonify(result[:30])  # Top 30 pets to level
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analytics')
def get_analytics():
    """Get analytics data for charts"""
    try:
        analytics = {
            "readyByExpansion": {},
            "readyByCategory": {},
            "totalEncounters": 0,
            "readyEncounters": 0
        }
        
        if os.path.exists('my_ready_strategies.json'):
            with open('my_ready_strategies.json', 'r') as f:
                data = json.load(f)
                
                for exp_name, expansions in data.items():
                    exp_count = 0
                    for cat_name, encounters in expansions.items():
                        count = len(encounters)
                        exp_count += count
                        analytics["readyByCategory"][cat_name] = analytics["readyByCategory"].get(cat_name, 0) + count
                    
                    analytics["readyByExpansion"][exp_name] = exp_count
                    analytics["readyEncounters"] += exp_count
        
        # Get total strategies count
        if os.path.exists('strategies.json'):
            with open('strategies.json', 'r') as f:
                data = json.load(f)
                total = 0
                for exp in data.values():
                    for cat in exp.values():
                        total += len(cat)
                analytics["totalEncounters"] = total
        
        return jsonify(analytics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/xp-encounters')
def get_xp_encounters():
    """Get best XP encounters (fast, repeatable)"""
    try:
        xp_encounters = []
        
        if os.path.exists('my_ready_strategies.json'):
            with open('my_ready_strategies.json', 'r') as f:
                data = json.load(f)
                
                for exp_name, expansions in data.items():
                    for cat_name, encounters in expansions.items():
                        for encounter in encounters:
                            if not encounter.get('strategies'):
                                continue
                            
                            strategy = encounter['strategies'][0]
                            script = strategy.get('script', '')
                            pet_slots = strategy.get('pet_slots', [])
                            
                            # Score for XP farming (fast battles, carry slots, repeatability)
                            xp_score = 0
                            carry_slot = None
                            
                            # Check for carry mechanics
                            if 'standby' in script:
                                xp_score += 15
                                carry_slot = 3
                            elif 'change(next)' in script and script.count('use(') < 8:
                                xp_score += 10
                                carry_slot = 3
                            
                            # Prefer short scripts (fast battles)
                            if len(script) < 150:
                                xp_score += 10
                            elif len(script) < 250:
                                xp_score += 5
                            
                            # Repeatability
                            if 'World Quest' in cat_name or 'Tamer' in cat_name:
                                xp_score += 8
                            
                            # Only include high XP encounters
                            if xp_score >= 15:
                                carry_name = 'Slot 3'
                                if carry_slot == 3 and len(pet_slots) >= 3 and pet_slots[2] and pet_slots[2][0]:
                                    carry_name = pet_slots[2][0].get('name', 'Slot 3')
                                
                                xp_encounters.append({
                                    'encounter': encounter.get('encounter_name', 'Unknown'),
                                    'expansion': exp_name,
                                    'category': cat_name,
                                    'carry_slot': carry_name,
                                    'xp_score': xp_score,
                                    'speed': 'Fast' if len(script) < 150 else 'Medium'
                                })
                
                # Sort by XP score
                xp_encounters.sort(key=lambda x: x['xp_score'], reverse=True)
        
        return jsonify(xp_encounters[:25])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/calendar')

def calendar():
    """Calendar page showing Squirt and Pet Battle Weeks"""
    return render_template('calendar.html')

@app.route('/api/calendar')
def get_calendar():
    """Return dates for a given month (default to current month) with Squirt and Pet Battle Week flags"""
    try:
        import datetime, calendar, flask
        # Get month param (format YYYY-MM) or default to current month
        month_str = flask.request.args.get('month')
        if month_str:
            year, month = map(int, month_str.split('-'))
        else:
            now = datetime.date.today()
            year, month = now.year, now.month
        # First day of month
        first_day = datetime.date(year, month, 1)
        _, days_in_month = calendar.monthrange(year, month)
        # Base squirt date for schedule
        base_squirt = datetime.date(2025, 12, 3)
        # Pet Battle Week start
        pbw_start = datetime.date(2025, 12, 16)
        result = []
        for day in range(days_in_month):
            d = first_day + datetime.timedelta(days=day)
            days_since_base = (d - base_squirt).days
            is_squirt = (days_since_base % 15) == 0
            
            # Pet Battle Week repeats every 6 weeks (42 days)
            # This is an estimate; the actual rotation can vary slightly with patch cycles
            days_since_pbw = (d - pbw_start).days
            is_pbw = (days_since_pbw % 42) < 7 and days_since_pbw >= 0
            result.append({
                'date': d.isoformat(),
                'weekday': d.strftime('%A'),
                'is_squirt': is_squirt,
                'is_pet_battle_week': is_pbw
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/squirt-status')
def get_squirt_status():
    """Check if it's Squirt day (based on updated schedule)"""
    try:
        import datetime
        
        # Updated base date so that 2025-12-03 is a Squirt day and repeats every 15 days
        base_squirt_date = datetime.datetime(2025, 12, 3)
        now = datetime.datetime.now()
        days_since_base = (now - base_squirt_date).days
        
        # Squirt appears every 15 days
        is_squirt_day = (days_since_base % 15) == 0
        
        days_until_squirt = 15 - (days_since_base % 15) if not is_squirt_day else 0
        
        return jsonify({
            'is_squirt_day': is_squirt_day,
            'days_until_squirt': days_until_squirt,
            'location': 'WoD Garrison',
            'message': '🎉 SQUIRT DAY! Check your Garrison!' if is_squirt_day else f'Squirt in {days_until_squirt} days',
            'note': 'Check if Pet Battle Week is active for SUPER SQUIRT bonus!'
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/strategy/fetch')
def fetch_strategy():
    """Fetch a strategy for a given NPC"""
    npc_name = request.args.get('npc_name')
    if not npc_name:
        return jsonify({"error": "Missing npc_name parameter"}), 400
        
    strategy = strategy_manager.get_strategy(npc_name)
    
    if strategy:
        return jsonify({
            "found": True,
            "strategy": strategy
        })
    else:
        return jsonify({
            "found": False,
            "message": "Strategy not found in local database."
        })

if __name__ == '__main__':
    update_stats()
    print("🌐 Starting PetWeaver Desktop App on http://127.0.0.1:5001")
    app.run(debug=False, port=5001)
