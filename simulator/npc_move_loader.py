import re
import os
from typing import Dict, Optional

# Structure: { "NPC Name": { pet_index (0-based): { round_num: "Ability Name" } } }
MoveOrderData = Dict[str, Dict[int, Dict[int, str]]]

_LOADED_MOVE_ORDERS: Optional[MoveOrderData] = None

def load_npc_move_orders(filepath: str) -> MoveOrderData:
    """
    Parses the npc_move_orders.md file and returns a structured dictionary.
    """
    move_orders: MoveOrderData = {}
    
    if not os.path.exists(filepath):
        print(f"Warning: NPC move orders file not found at {filepath}")
        return {}

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by NPC sections (## NPC Name)
    npc_sections = re.split(r'^## ', content, flags=re.MULTILINE)
    
    for section in npc_sections:
        if not section.strip():
            continue
            
        lines = section.strip().split('\n')
        npc_name = lines[0].strip()
        
        move_orders[npc_name] = {}
        
        # Split by Pet sections (### Pet X: Name)
        pet_sections = re.split(r'^### ', section, flags=re.MULTILINE)
        
        # Skip the first part which is just the NPC name line
        for pet_section in pet_sections[1:]:
            pet_header_match = re.match(r'Pet (\d+):', pet_section)
            if not pet_header_match:
                continue
                
            # Convert 1-based pet index to 0-based
            pet_index = int(pet_header_match.group(1)) - 1
            move_orders[npc_name][pet_index] = {}
            
            # Parse the table
            # Look for lines starting with | <digit> |
            table_rows = re.findall(r'^\| (\d+) \| \*\*([^\*]+)\*\* \|', pet_section, flags=re.MULTILINE)
            
            for round_str, ability_name in table_rows:
                round_num = int(round_str)
                move_orders[npc_name][pet_index][round_num] = ability_name.strip()
                
    return move_orders

def get_move_orders() -> MoveOrderData:
    """
    Singleton accessor for move orders.
    """
    global _LOADED_MOVE_ORDERS
    if _LOADED_MOVE_ORDERS is None:
        # Assume file is in the root directory relative to execution or hardcoded path
        # For this environment, we know the absolute path
        path = "/Users/jgrayson/Documents/petweaver/npc_move_orders.md"
        _LOADED_MOVE_ORDERS = load_npc_move_orders(path)
    return _LOADED_MOVE_ORDERS
