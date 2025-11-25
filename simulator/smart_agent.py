from typing import Optional, List, Dict
from .battle_state import BattleState, TurnAction, Pet, Ability, BuffType, PetFamily
from .damage_calculator import DamageCalculator
from .special_encounters import SpecialEncounterHandler

class SmartAgent:
    """
    Advanced AI Agent using a 3-Level Decision Tree.
    
    Level 1: Survival & Gimmick Override (Rocko, Howl Bomb, Supercharge)
    Level 2: Strategic Control (Counter-CC, Damage Stacking, Execute)
    Level 3: Damage Priority (Score-based selection)
    """
    
    def __init__(self, difficulty: float = 1.0):
        self.difficulty = difficulty
        self.damage_calc = DamageCalculator()

    def decide(self, state: BattleState) -> TurnAction:
        # Level 1: Survival & Gimmick Override
        action = self._level_1_survival(state)
        if action: return action

        # Level 2: Strategic Control
        action = self._level_2_strategy(state)
        if action: return action

        # Level 3: Damage Priority
        return self._level_3_damage(state)

    def _level_1_survival(self, state: BattleState) -> Optional[TurnAction]:
        """
        Level 1: Survival & Gimmick Override
        - Swap if active pet is dead
        - Rocko: Smash spam
        - Howl Bomb / Supercharge combos
        """
        active_pet = state.enemy_team.get_active_pet()
        
        # 1. Survival: Swap if dead
        if not active_pet or not active_pet.stats.is_alive():
            return self._swap_to_best_pet(state)
            
        # 2. Gimmick: Rocko (Smash Spam)
        if active_pet.name == "Rocko":
            smash = next((ab for ab in active_pet.abilities if ab.name == "Smash"), None)
            if smash and active_pet.can_use_ability(smash):
                return TurnAction('enemy', 'ability', ability=smash)
                
        # 3. Gimmick: Howl Bomb / Supercharge
        # Check if enemy has Howl (damage_taken +100%)
        enemy_active = state.player_team.get_active_pet()
        howl_active = any(b.name == "Howl" for b in enemy_active.active_buffs) if enemy_active else False
        
        # Check if we have Supercharge (damage_dealt +100% next turn)
        supercharge_active = any(b.name == "Supercharge" for b in active_pet.active_buffs)
        
        if howl_active or supercharge_active:
            # Prioritize highest damage ability
            best_ability = self._find_highest_damage_ability(active_pet, enemy_active)
            if best_ability:
                return TurnAction('enemy', 'ability', ability=best_ability)
                
        return None

    def _level_2_strategy(self, state: BattleState) -> Optional[TurnAction]:
        """
        Level 2: Strategic Control
        - Counter-CC (Cleanse)
        - Damage Stacking (Black Claw)
        - Execute (Kill low HP enemy)
        """
        active_pet = state.enemy_team.get_active_pet()
        enemy_active = state.player_team.get_active_pet()
        if not enemy_active: return None
        
        # 1. Counter-CC (Cleanse)
        # Check if we are CC'd (Stun, Root, Sleep)
        is_cc = any(b.type in [BuffType.STUN, BuffType.ROOT, BuffType.SLEEP] for b in active_pet.active_buffs)
        if is_cc:
            # Look for cleanse ability (not implemented in Ability class explicitly, but maybe by name/effect)
            # For now, we skip as we don't have 'cleanse' tag.
            pass
            
        # 2. Damage Stacking (Black Claw / Shattered Defenses)
        # If we have Black Claw and enemy doesn't have it, use it.
        black_claw = next((ab for ab in active_pet.abilities if ab.name == "Black Claw"), None)
        if black_claw and active_pet.can_use_ability(black_claw):
            has_debuff = any(b.name == "Black Claw" for b in enemy_active.active_buffs)
            if not has_debuff:
                return TurnAction('enemy', 'ability', ability=black_claw)
                
        # 3. Execute (Kill low HP enemy)
        # If enemy HP < 30% or absolute value low, try to kill
        if enemy_active.stats.current_hp < enemy_active.stats.max_hp * 0.3:
            kill_ability = self._find_kill_ability(active_pet, enemy_active)
            if kill_ability:
                return TurnAction('enemy', 'ability', ability=kill_ability)
                
        return None

    def _level_3_damage(self, state: BattleState) -> TurnAction:
        """
        Level 3: Damage Priority
        - Score-based selection
        """
        active_pet = state.enemy_team.get_active_pet()
        enemy_active = state.player_team.get_active_pet()
        
        best_score = -1
        best_ability = None
        
        available_abilities = [ab for ab in active_pet.abilities if active_pet.can_use_ability(ab)]
        
        if not available_abilities:
             return TurnAction('enemy', 'pass')
             
        for ability in available_abilities:
            score = 0
            
            # Base Score: Damage
            # Estimate damage
            damage, _ = self.damage_calc.calculate_damage(ability, active_pet, enemy_active, state.weather)
            score += damage
            
            # Multipliers
            
            # Type Advantage (already in damage, but boost slightly to prefer it over neutral high dmg if close)
            fam_mult = self.damage_calc.get_family_multiplier(ability.family, enemy_active.family)
            if fam_mult > 1.0:
                score *= 1.2
                
            # High Cooldown Bonus (Don't waste big spells)
            if ability.cooldown > 0:
                score += (ability.cooldown * 50) # +50 score per turn of cooldown
                
            # Accuracy Penalty
            score *= (ability.accuracy / 100.0)
            
            # Penalty for active buffs (don't re-apply)
            if any(b.name == ability.name for b in enemy_active.active_buffs) or \
               any(b.name == ability.name for b in active_pet.active_buffs):
                score -= 1000
            
            if score > best_score:
                best_score = score
                best_ability = ability
                
        if best_ability:
            return TurnAction('enemy', 'ability', ability=best_ability)
            
        # Fallback to first available (Pass if none, handled above)
        return TurnAction('enemy', 'ability', ability=available_abilities[0])

    def _swap_to_best_pet(self, state: BattleState) -> TurnAction:
        """Find best pet to swap to (Highest HP%)"""
        best_idx = -1
        best_hp = -1
        
        for i, pet in enumerate(state.enemy_team.pets):
            if pet.stats.is_alive() and i != state.enemy_team.active_pet_index:
                hp_pct = pet.stats.current_hp / pet.stats.max_hp
                if hp_pct > best_hp:
                    best_hp = hp_pct
                    best_idx = i
                    
        if best_idx != -1:
            return TurnAction('enemy', 'swap', target_pet_index=best_idx)
            
        return TurnAction('enemy', 'pass')

    def _find_highest_damage_ability(self, attacker: Pet, defender: Pet) -> Optional[Ability]:
        best_dmg = -1
        best_ab = None
        for ab in attacker.abilities:
            if attacker.can_use_ability(ab):
                dmg, _ = self.damage_calc.calculate_damage(ab, attacker, defender)
                if dmg > best_dmg:
                    best_dmg = dmg
                    best_ab = ab
        return best_ab

    def _find_kill_ability(self, attacker: Pet, defender: Pet) -> Optional[Ability]:
        """Find an ability that will kill the defender"""
        for ab in attacker.abilities:
            if attacker.can_use_ability(ab):
                dmg, _ = self.damage_calc.calculate_damage(ab, attacker, defender)
                if dmg >= defender.stats.current_hp:
                    return ab
        return None
