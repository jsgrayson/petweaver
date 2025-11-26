"""
Regenerate NPC Move Orders Using Enhanced AI Scripts

Takes the enhanced AI scripts and generates updated move orders for all encounters.
"""

import json
from simulator.npc_ai_loader import get_ai_loader
from simulator.npc_move_simulator import simulate_npc_move_order_enhanced

def main():
    print("Loading enhanced AI scripts...")
    loader = get_ai_loader()
    
    print(f"✅ Loaded {len(loader.ai_scripts)} AI scripts\n")
    
    # Generate move orders for encounters with AI
    updated_move_orders = {}
    
    for encounter_name in sorted(loader.ai_scripts.keys()):
        ai = loader.get_ai_for_encounter(encounter_name)
        
        if not ai:
            continue
        
        # Check if we have abilities
        all_abilities = (ai.get('priority_abilities', []) + 
                        ai.get('hp_conditionals', []) + 
                        ai.get('general_rotation', []))
        
        if not all_abilities:
            continue
        
        # Build mock pet data for simulation
        # Use the abilities from the AI script
        abilities_list = []
        seen_ids = set()
        
        for ability in all_abilities:
            if ability['id'] not in seen_ids:
                abilities_list.append({
                    'id': ability['id'],
                    'name': ability['name'],
                    'cooldown': 0  # Default, would need real data
                })
                seen_ids.add(ability['id'])
        
        if not abilities_list:
            continue
        
        pet_data = {'abilities': abilities_list}
        
        # Simulate move order
        try:
            move_order = simulate_npc_move_order_enhanced(
                pet_data=pet_data,
                enhanced_ai=ai,
                max_rounds=15
            )
            
            if move_order and any(m != "Pass" for m in move_order):
                # Store as pet slot 1 moves (simplified - would need multi-pet support)
                updated_move_orders[encounter_name] = {
                    1: {i+1: move for i, move in enumerate(move_order)}
                }
                
                print(f"✅ {encounter_name}: {len([m for m in move_order if m != 'Pass'])} moves")
        except Exception as e:
            print(f"⚠️  {encounter_name}: {e}")
    
    # Save updated move orders
    output_file = 'npc_move_orders_enhanced.json'
    with open(output_file, 'w') as f:
        json.dump(updated_move_orders, f, indent=2)
    
    print(f"\n✅ Generated move orders for {len(updated_move_orders)} encounters")
    print(f"💾 Saved to: {output_file}")
    
    # Show sample
    if updated_move_orders:
        sample = list(updated_move_orders.items())[0]
        print(f"\n📜 Sample ({sample[0]}):")
        for round_num, move in list(sample[1][1].items())[:5]:
            print(f"  Round {round_num}: {move}")

if __name__ == "__main__":
    main()
