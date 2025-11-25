import json
import re
from pathlib import Path
from collections import defaultdict

ENCOUNTERS_FILE = Path(__file__).resolve().parent / "encounters_full.json"
STRATEGIES_FILE = Path(__file__).resolve().parent / "strategies_enhanced.json"
OUTPUT_FILE = Path(__file__).resolve().parent / "npc_move_orders.md"

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_npc_data(encounters):
    """
    Organize encounter data by name for easy lookup.
    Returns: dict[npc_name] -> {pet_index: {name, abilities: [id, id, id]}}
    """
    npc_lookup = {}
    
    # Helper to process a list of encounters
    def process_list(enc_list):
        for enc in enc_list:
            name = enc.get('name')
            if not name: continue
            
            pets = {}
            # The key is 'pets', not 'npc_pets'
            for i, pet in enumerate(enc.get('pets', []), 1):
                # Get ability objects with details if available, otherwise just IDs
                abilities = []
                for ab in pet.get('abilities', []):
                    # If ab is a dict, it has details. If int, it's just ID.
                    if isinstance(ab, dict):
                        abilities.append(ab)
                    else:
                        abilities.append({'id': ab, 'name': f"Ability {ab}", 'cooldown': 0})
                
                pets[i] = {
                    # Pet name might not be explicit, use species_id or generic
                    'name': pet.get('name', f"Pet {i}"),
                    'abilities': abilities
                }
            npc_lookup[name] = pets

    # Iterate through the structure of encounters_full.json
    # It is a list of encounter objects
    if isinstance(encounters, list):
        process_list(encounters)
    elif isinstance(encounters, dict):
        # Fallback if it's a dict (e.g. by expansion)
        for key, val in encounters.items():
            if isinstance(val, list):
                process_list(val)
                
    return npc_lookup

def analyze_strategies(strategies_data):
    """
    Extract round-specific player actions from strategies.
    Returns: dict[npc_name] -> {pet_idx: {round: [actions]}}
    """
    npc_observations = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    
    for expansion, content in strategies_data.items():
        if isinstance(content, dict):
            for category, encounter_list in content.items():
                if isinstance(encounter_list, list):
                    for enc in encounter_list:
                        npc_name = enc.get("encounter_name")
                        if not npc_name: continue
                        
                        for strat in enc.get("strategies", []):
                            script = strat.get("script", "")
                            lines = script.replace("\r", "\n").split("\n")
                            current_pet_idx = 1
                            
                            for line in lines:
                                line = line.strip().lower()
                                if not line or line.startswith("--"): continue
                                
                                # Check for active enemy pet
                                active_match = re.search(r'enemy\(#(\d)\)\.active', line)
                                if active_match:
                                    current_pet_idx = int(active_match.group(1))
                                
                                # Check for round conditions
                                round_matches = re.findall(r'\[.*?(?:round|turn)[=~](\d+(?:,\d+)*).*?\]', line)
                                
                                # Extract action
                                action = "Unknown"
                                if "change" in line:
                                    action = "swap"
                                elif "use" in line or "ability" in line:
                                    # Try to identify defensive moves
                                    if any(x in line for x in ['dodge', 'deflect', 'block', 'barrier', 'bubble', 'decoy']):
                                        action = "defensive"
                                    else:
                                        action = "attack"
                                
                                for rounds in round_matches:
                                    for r in rounds.split(','):
                                        try:
                                            r_num = int(r)
                                            npc_observations[npc_name][current_pet_idx][r_num].append(action)
                                        except: pass
                                        
    return npc_observations

def simulate_npc_move_order(pet_data, observations, max_rounds=15):
    """
    Generate the move order for a single NPC pet.
    """
    move_order = []
    abilities = pet_data['abilities']
    
    # Initialize cooldown trackers
    cooldowns = {ab['id']: 0 for ab in abilities}
    
    for r in range(1, max_rounds + 1):
        # 1. Check if we have a forced move based on observations
        # (This is tricky without knowing WHICH ability corresponds to the threat)
        # For now, we will use the standard priority logic, but we could prioritize
        # high-cooldown abilities on rounds where the player uses defensives.
        
        obs = observations.get(r, [])
        player_is_defensive = "defensive" in obs
        
        selected_ability = None
        
        # LOGIC:
        # 1. Filter available abilities (cooldown == 0)
        available = [ab for ab in abilities if cooldowns[ab['id']] == 0]
        
        if not available:
            move_order.append("Pass")
            continue
            
        # 2. Sort by priority
        # Priority 1: If player is defensive, maybe we wasted a big cooldown? 
        # Actually, if the player IS defensive, it means the NPC IS using a big move.
        # So we should pick the highest cooldown/highest damage move.
        
        # Heuristic: Sort by cooldown (descending) then ID (arbitrary stability)
        # Assuming higher cooldown = stronger move
        available.sort(key=lambda x: (x.get('cooldown', 0), x['id']), reverse=True)
        
        selected_ability = available[0]
        
        # 3. Execute
        move_order.append(selected_ability['name'])
        
        # 4. Update cooldowns
        # Tick down all
        for ab_id in cooldowns:
            if cooldowns[ab_id] > 0:
                cooldowns[ab_id] -= 1
                
        # Set cooldown for used ability
        cooldowns[selected_ability['id']] = selected_ability.get('cooldown', 0)
        
    return move_order

def generate_markdown(npc_lookup, npc_observations):
    lines = ["# Final NPC Move Orders\n\n"]
    lines.append("Generated by combining Xufu strategy analysis with internal cooldown logic.\n\n")
    
    # Sort NPCs by name
    for npc_name in sorted(npc_lookup.keys()):
        pets = npc_lookup[npc_name]
        
        # Skip if no pets found (shouldn't happen for valid encounters)
        if not pets: continue
        
        lines.append(f"## {npc_name}\n\n")
        
        for i in range(1, 4):
            if i not in pets: continue
            pet = pets[i]
            
            lines.append(f"### Pet {i}: {pet['name']}\n")
            
            # Get observations for this pet
            obs = npc_observations.get(npc_name, {}).get(i, {})
            
            # Simulate
            moves = simulate_npc_move_order(pet, obs)
            
            # Table
            lines.append("| Round | Predicted Move | Player Observation |\n")
            lines.append("| :--- | :--- | :--- |\n")
            
            for r, move in enumerate(moves, 1):
                player_action = ", ".join(set(obs.get(r, [])))
                if not player_action: player_action = "-"
                lines.append(f"| {r} | **{move}** | {player_action} |\n")
            
            lines.append("\n")
            
    return "".join(lines)

def main():
    print("Loading data...")
    encounters = load_json(ENCOUNTERS_FILE)
    strategies = load_json(STRATEGIES_FILE)
    
    print("Processing NPC data...")
    npc_lookup = get_npc_data(encounters)
    
    print("Analyzing strategies...")
    npc_observations = analyze_strategies(strategies)
    
    print("Generating move orders...")
    md_content = generate_markdown(npc_lookup, npc_observations)
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print(f"✅ Generated {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
