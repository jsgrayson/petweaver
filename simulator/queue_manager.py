from typing import List, Dict, Optional
import random
from .battle_state import Team, Pet, PetStats, PetFamily, PetQuality, Ability

class QueueManager:
    def __init__(self, species_db: Dict, ability_db: Dict):
        self.species_db = species_db
        self.ability_db = ability_db
        self.history = [] # List of battle results

    def get_optimal_carry_team(self, leveling_pet_data: Dict, target_encounter: Dict) -> Dict:
        """
        Selects 2 max-level pets to carry the leveling pet.
        Returns a dictionary with the suggested team structure.
        """
        # 1. Analyze Target
        # Simple counter logic: If enemy has Family X, bring Counter Y.
        # We need 2 strong pets.
        
        target_pets = target_encounter.get('npc_pets', [])
        if not target_pets:
            return {"error": "Invalid target encounter"}

        # Find counters for the first 2 enemy pets (primary threats)
        carry_1 = self._find_counter(target_pets[0] if len(target_pets) > 0 else None)
        carry_2 = self._find_counter(target_pets[1] if len(target_pets) > 1 else None)
        
        # Fallback if no specific counter found (use generic strong pets)
        if not carry_1: carry_1 = self._get_generic_strong_pet()
        if not carry_2: carry_2 = self._get_generic_strong_pet()
        
        # Ensure we don't pick the same pet twice if possible (unless we have duplicates)
        # For simulation purposes, we just return species IDs.
        
        return {
            "leveling_slot": 0, # Slot 0 is usually the leveling pet
            "pets": [
                leveling_pet_data, # The user's pet
                carry_1,
                carry_2
            ],
            "strategy_hint": "Swap leveling pet out immediately if it's in slot 1."
        }

    def _find_counter(self, enemy_pet_data: Optional[Dict]) -> Dict:
        """Find a pet species that counters the enemy family."""
        if not enemy_pet_data: return None
        
        enemy_family = enemy_pet_data.get('family', 'Beast')
        
        # Counter Map (Attacker Family -> Strong Against)
        # We want a pet whose attacks are strong against enemy_family
        # AND/OR whose family resists enemy_family attacks.
        
        # Simple Hardcoded Counters for now (Species IDs of strong pets)
        # 0: Humanoid, 1: Dragonkin, 2: Flying, 3: Undead, 4: Critter
        # 5: Magic, 6: Elemental, 7: Beast, 8: Aquatic, 9: Mechanical
        
        # Map Enemy Family Name to Counter Species ID
        counters = {
            'Humanoid': {'id': 339, 'name': 'Unborn Val\'kyr'}, # Undead counters Humanoid
            'Dragonkin': {'id': 339, 'name': 'Unborn Val\'kyr'}, # Undead (generic strong)
            'Flying': {'id': 1155, 'name': 'Iron Starlette'}, # Magic counters Flying? No, Magic > Flying.
            'Undead': {'id': 844, 'name': 'Dah\'da'}, # Critter > Undead
            'Critter': {'id': 118, 'name': 'Worg Pup'}, # Beast > Critter
            'Magic': {'id': 1155, 'name': 'Iron Starlette'}, # Mech > Magic? Dragon > Magic.
            'Elemental': {'id': 383, 'name': 'Snail'}, # Aquatic > Elemental
            'Beast': {'id': 1155, 'name': 'Iron Starlette'}, # Mech > Beast
            'Aquatic': {'id': 1238, 'name': 'Ikky'}, # Flying > Aquatic
            'Mechanical': {'id': 1387, 'name': 'Twilight Clutch-Sister'} # Elemental > Mech
        }
        
        # Default to Iron Starlette (1155) or Ikky (1238) as generic carries
        return counters.get(enemy_family, {'id': 1155, 'name': 'Iron Starlette'})

    def _get_generic_strong_pet(self) -> Dict:
        return {'id': 1155, 'name': 'Iron Starlette'}

    def record_result(self, result: Dict):
        """
        Record the result of a battle to adjust future recommendations.
        result: { 'win': bool, 'turns': int, 'hp_remaining': float }
        """
        self.history.append(result)
        # Logic to adjust difficulty could go here (e.g. if many losses, suggest safer teams)

    def calculate_bandage_efficiency(self) -> float:
        """Returns a score 0-100 representing how 'efficient' recent battles were."""
        if not self.history: return 100.0
        
        total_hp_loss = 0
        for res in self.history[-10:]: # Look at last 10
            if not res.get('win', False):
                total_hp_loss += 100 # Penalty for loss
            else:
                total_hp_loss += (100 - res.get('hp_remaining', 0))
                
        avg_loss = total_hp_loss / len(self.history[-10:])
        return max(0, 100 - avg_loss)
