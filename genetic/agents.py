"""
AI Agents for Pet Battle Simulation

This module contains strategic AI agents used in battle simulations,
particularly for the genetic algorithm fitness evaluation.
"""

from typing import Optional
from simulator import BattleState, TurnAction, Pet, Ability


class SmartEnemyAgent:
    """
    Strategic enemy AI that makes competent decisions.
    
    This agent is designed to be challenging but fair, forcing the genetic
    algorithm to evolve genuinely effective strategies rather than exploiting
    trivial opponent behavior.
    
    Can be customized with specific ability priorities per encounter for
    realistic NPC tamer behavior.
    """
    
    def __init__(self, difficulty: float = 1.0, ability_priorities: dict = None):
        """
        Initialize the smart enemy agent.
        
        Args:
            difficulty: Multiplier for strategic behavior (0.0-1.0)
                       1.0 = full strategic capability
                       0.5 = makes some suboptimal choices
            ability_priorities: Dict mapping pet index to ability priority list
                              e.g. {0: [593, 489, 287]} means pet 0 prioritizes
                              ability 593 first, then 489, then 287
        """
        self.difficulty = max(0.0, min(1.0, difficulty))
        self.ability_priorities = ability_priorities or {}
    
    def decide(self, state: BattleState) -> TurnAction:
        """
        Make a strategic decision for the enemy team.
        
        Priority:
        1. Swap if active pet is dead
        2. Swap if active pet is critically low HP and better option exists
        3. Use custom ability priority (if configured for this encounter)
        4. Use buff abilities early in battle (if available)
        5. Use highest-power available ability
        6. Fallback to first available ability
        """
        active_pet = state.enemy_team.get_active_pet()
        
        # Handle forced swaps (dead pet)
        if active_pet and not active_pet.stats.is_alive():
            return self._swap_to_best_pet(state)
        
        if not active_pet:
            return TurnAction('enemy', 'pass')
        
        # Consider strategic swap (low HP)
        if self._should_swap_for_health(state, active_pet):
            swap_action = self._swap_to_best_pet(state)
            if swap_action.action_type == 'swap':
                return swap_action
        
        # Use custom ability priority if configured for this pet
        active_pet_index = state.enemy_team.active_pet_index
        if active_pet_index in self.ability_priorities:
            priority_ability = self._choose_priority_ability(active_pet, self.ability_priorities[active_pet_index])
            if priority_ability:
                return TurnAction('enemy', 'ability', ability=priority_ability)
        
        # Early battle: use buff abilities
        if state.turn_number <= 3:
            buff_ability = self._find_buff_ability(active_pet)
            if buff_ability and active_pet.can_use_ability(buff_ability):
                return TurnAction('enemy', 'ability', ability=buff_ability)
        
        # Use highest-power ability
        best_ability = self._choose_best_ability(active_pet)
        if best_ability:
            return TurnAction('enemy', 'ability', ability=best_ability)
        
        # Fallback
        return TurnAction('enemy', 'pass')
    
    def _should_swap_for_health(self, state: BattleState, active_pet: Pet) -> bool:
        """Check if active pet should swap due to low health."""
        if not active_pet or not active_pet.stats.is_alive():
            return True
        
        hp_percent = active_pet.stats.current_hp / active_pet.stats.max_hp
        
        # Swap threshold scales with difficulty
        swap_threshold = 0.2 + (0.1 * (1.0 - self.difficulty))  # 0.2-0.3
        
        if hp_percent < swap_threshold:
            # Only swap if we have a healthier pet available
            for pet in state.enemy_team.pets:
                if pet != active_pet and pet.stats.is_alive():
                    other_hp_percent = pet.stats.current_hp / pet.stats.max_hp
                    if other_hp_percent > hp_percent + 0.2:  # At least 20% healthier
                        return True
        
        return False
    
    def _swap_to_best_pet(self, state: BattleState) -> TurnAction:
        """Find the best pet to swap to (highest HP%)."""
        best_pet_idx = None
        best_hp_percent = 0.0
        
        for i, pet in enumerate(state.enemy_team.pets):
            if pet.stats.is_alive() and i != state.enemy_team.active_pet_index:
                hp_percent = pet.stats.current_hp / pet.stats.max_hp
                if hp_percent > best_hp_percent:
                    best_hp_percent = hp_percent
                    best_pet_idx = i
        
        if best_pet_idx is not None:
            return TurnAction('enemy', 'swap', target_pet_index=best_pet_idx)
        
        # No living pets to swap to
        return TurnAction('enemy', 'pass')
    
    def _choose_priority_ability(self, pet: Pet, priority_list: list) -> Optional[Ability]:
        \"\"\"
        Choose ability based on encounter-specific priority list.
        
        Args:
            pet: The active pet
            priority_list: List of ability IDs in priority order
            
        Returns:
            First usable ability from priority list, or None
        \"\"\"
        for ability_id in priority_list:
            for ability in pet.abilities:
                if ability.id == ability_id and pet.can_use_ability(ability):
                    return ability
        return None
    
    def _find_buff_ability(self, pet: Pet) -> Optional[Ability]:
        """Find a buff/debuff ability (power=0 or low damage)."""
        for ability in pet.abilities:
            # Heuristic: buffs often have 0 or very low power
            if ability.power <= 10 and ability.cooldown > 0:
                return ability
        return None
    
    def _choose_best_ability(self, pet: Pet) -> Optional[Ability]:
        """Choose the highest-power usable ability."""
        best_ability = None
        best_power = -1
        
        for ability in pet.abilities:
            if pet.can_use_ability(ability):
                # Factor in accuracy (expected damage)
                expected_damage = ability.power * (ability.accuracy / 100.0)
                
                if expected_damage > best_power:
                    best_power = expected_damage
                    best_ability = ability
        
        return best_ability


# Convenience function for backward compatibility
def create_smart_enemy_agent(difficulty: float = 1.0):
    """Create a smart enemy agent callable."""
    agent = SmartEnemyAgent(difficulty=difficulty)
    return lambda state: agent.decide(state)
