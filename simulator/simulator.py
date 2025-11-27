from typing import List, Dict, Optional, Union, Callable
from .battle_state import BattleState, TurnAction, BuffType
from .damage_calculator import DamageCalculator
from .turn_system import TurnSystem
from .buff_tracker import BuffTracker
from .special_encounters import SpecialEncounterHandler

class BattleLog:
    def __init__(self):
        self.events: List[Dict] = []
        self.turn_summaries: List[str] = []
    def add_event(self, event: Dict):
        self.events.append(event)
    def add_turn_summary(self, turn: int, summary: str):
        self.turn_summaries.append(f"Turn {turn}: {summary}")
    def get_full_log(self) -> str:
        return "\n".join(self.turn_summaries)

class NullLog:
    def __init__(self): self.events = [] 
    def add_event(self, event: Dict):
        if event.get('type') == 'death': self.events.append(event)
    def add_turn_summary(self, turn: int, summary: str): pass 
    def get_full_log(self) -> str: return ""

class BattleSimulator:
    def __init__(self, rng_seed: Optional[int] = None):
        self.damage_calc = DamageCalculator(rng_seed)
        self.turn_system = TurnSystem(rng_seed)
        self.buff_tracker = BuffTracker()
        self.log = BattleLog()
    
    def simulate_battle(self, initial_state: BattleState, player_script, enemy_script, max_turns=50, special_encounter_id=None, enable_logging=True):
        state = initial_state.copy()
        self.log = BattleLog() if enable_logging else NullLog()
        
        turn = 0
        while not state.is_battle_over() and turn < max_turns:
            turn += 1
            if enable_logging: self.log.add_turn_summary(turn, f"Turn {turn}")
            
            player_action = self._get_action(player_script, state, turn, 'player')
            enemy_action = self._get_action(enemy_script, state, turn, 'enemy')
            
            # VALIDATE DEATH SWAPS
            player_action = self._validate_action(state.player_team, player_action, 'player')
            enemy_action = self._validate_action(state.enemy_team, enemy_action, 'enemy')
            
            state = self.execute_turn(state, player_action, enemy_action, turn, special_encounter_id)
            if state.is_battle_over(): break
        
        winner = state.get_winner() or 'draw'
        return {'winner': winner, 'turns': turn, 'log': self.log, 'final_state': state, 'events': self.log.events}
    
    def _validate_action(self, team, action, actor):
        active = team.get_active_pet()
        if not active or not active.stats.is_alive():
            # FORCE SWAP ON DEATH
            for i, p in enumerate(team.pets):
                if p.stats.is_alive():
                    # Log the forced swap so we know WHY it happened
                    if isinstance(self.log, BattleLog):
                        # self.log.add_event({'type': 'info', 'msg': f"{actor} forced to swap (Active Dead)"})
                        pass
                    return TurnAction(actor=actor, action_type='swap', target_pet_index=i)
            return TurnAction(actor=actor, action_type='pass')
        return action

    def _get_action(self, script, state, turn, actor):
        if callable(script):
            try: return script(state)
            except: return TurnAction(actor=actor, action_type='pass')
        else:
            idx = min(turn - 1, len(script) - 1)
            return script[idx]
    
    def execute_turn(self, state, player_action, enemy_action, turn_number, special_encounter_id=None):
        # DO NOT process_end_of_turn here - buffs must persist through the turn!
        if state.is_battle_over(): return state
        
        player_pet = state.player_team.get_active_pet()
        enemy_pet = state.enemy_team.get_active_pet()
        
        # Validate Cooldowns
        if player_action.action_type == 'ability' and player_action.ability:
             if not player_pet.can_use_ability(player_action.ability): player_action = TurnAction('player', 'pass')
        if enemy_action.action_type == 'ability' and enemy_action.ability:
             if not enemy_pet.can_use_ability(enemy_action.ability): enemy_action = TurnAction('enemy', 'pass')

        action_order = self.turn_system.determine_turn_order(player_pet, player_action, enemy_pet, enemy_action)
        
        for actor, action in action_order:
            attacker = player_pet if actor == 'player' else enemy_pet
            defender = enemy_pet if actor == 'player' else player_pet
            attacker_team = state.player_team if actor == 'player' else state.enemy_team
            
            if not attacker.stats.is_alive() and action.action_type != 'swap': continue
            if not defender.stats.is_alive() and action.action_type == 'ability': continue 

            # print(f"\n[EXEC] {actor} action: {action.action_type} {action.ability.name if action.ability else ''}")
            # if actor == 'player':
            #     print(f"  Player buffs BEFORE action: {[b.name for b in attacker.active_buffs]}")
            # else:
            #     enemy_acting_on = player_pet if actor == 'enemy' else enemy_pet
            #     print(f"  Defender ({enemy_acting_on.name}) buffs BEFORE enemy action: {[b.name for b in enemy_acting_on.active_buffs]}")
            
            self.execute_action(action, attacker, defender, attacker_team, state, special_encounter_id, turn_number)
            
            # if actor == 'player':
            #     print(f"  Player buffs AFTER action: {[b.name for b in attacker.active_buffs]}")
            # else:
            #     print(f"  Defender ({enemy_acting_on.name}) buffs AFTER enemy action: {[b.name for b in enemy_acting_on.active_buffs]}")
            if state.is_battle_over(): break
        
        if player_pet: player_pet.tick_cooldowns()
        if enemy_pet: enemy_pet.tick_cooldowns()
        
        # Process end of turn AFTER all actions complete
        self.process_end_of_turn(state, state.player_team.get_active_pet(), state.enemy_team.get_active_pet())
        
        state.turn_number = turn_number + 1
        return state
    
    def execute_action(self, action, attacker, defender, attacker_team, state, special_encounter_id, turn_number):
        if action.action_type == 'swap':
            if action.target_pet_index is not None:
                attacker_team.active_pet_index = action.target_pet_index
                self.log.add_event({'type': 'swap', 'actor': action.actor, 'turn': turn_number, 'new_index': action.target_pet_index})
        elif action.action_type == 'ability' and action.ability:
            ability = action.ability
            attacker.use_ability(ability)
            
            is_immune = False
            if special_encounter_id == 'rocko_immunity' and SpecialEncounterHandler.apply_rocko_immunity(defender, state.turn_number): is_immune = True
            for buff in defender.active_buffs:
                if buff.type in [BuffType.INVULNERABILITY, BuffType.IMMUNITY] or "Decoy" in buff.name: is_immune = True
            
            if is_immune:
                self.log.add_event({'type': 'immune', 'turn': turn_number, 'actor': action.actor, 'ability': ability.name})
                return 

            if ability.is_heal:
                heal = self.damage_calc.calculate_healing(ability, attacker)
                attacker.stats.heal(heal)
                self.log.add_event({'type': 'heal', 'actor': action.actor, 'ability': ability.name, 'amount': heal, 'turn': turn_number})
            else:
                damage, details = self.damage_calc.calculate_damage(ability, attacker, defender, state.weather)
                if details['hit']:
                    remaining = self.buff_tracker.consume_shield(defender, damage)
                    defender.stats.take_damage(remaining)

                    self.log.add_event({'type': 'damage', 'actor': action.actor, 'ability': ability.name, 'amount': remaining, 'turn': turn_number})
                    if not defender.stats.is_alive():
                         self.log.add_event({'type': 'death', 'pet': defender.name, 'turn': turn_number})
                else:
                    self.log.add_event({'type': 'miss', 'actor': action.actor, 'ability': ability.name, 'turn': turn_number})
            
            # Apply ability-specific buffs and effects
            self.apply_ability_effects(ability, attacker, defender, turn_number)

    def apply_ability_effects(self, ability, attacker, defender, turn_number):
        """Apply status effects, buffs, and debuffs based on ability"""
        from simulator.battle_state import Buff
        
        # Dodge (312) - Duration 2 because WoW "lasts 1 round" = current round + next
        if ability.name == "Dodge" or ability.id == 312:
            buff = Buff(
                type=BuffType.INVULNERABILITY,
                name="Dodge",
                duration=2,  # 2 rounds to survive process_end_of_turn and block next attack
                magnitude=0,
                source_ability=ability.name,
                stat_affected='none'
            )
            self.buff_tracker.add_buff(attacker, buff)
            self.log.add_event({'type': 'buff_applied', 'target': attacker.name, 'buff': 'Dodge', 'turn': turn_number})

        # Burrow (159) - Underground lasts 2 rounds, attack triggers next turn
        elif ability.name == "Burrow" or ability.id == 159:
            buff_underground = Buff(
                type=BuffType.INVULNERABILITY,
                name="Underground",
                duration=2,  # 2 rounds to survive end-of-turn and block next attack
                magnitude=0,
                source_ability=ability.name,
                stat_affected='none'
            )
            self.buff_tracker.add_buff(attacker, buff_underground)
            
            buff_attack = Buff(
                type=BuffType.DELAYED_EFFECT,
                name="Burrow Attack",
                duration=2,  # Triggers at start of turn 2 (after 1 decrement)
                magnitude=ability.power if ability.power > 0 else 20,
                source_ability=ability.name,
                stat_affected='none'
            )
            self.buff_tracker.add_buff(attacker, buff_attack)
            self.log.add_event({'type': 'buff_applied', 'target': attacker.name, 'buff': 'Underground', 'turn': turn_number})

        # Black Claw (919)
        elif ability.name == "Black Claw" or ability.id == 919:
            buff = Buff(
                type=BuffType.STAT_MOD,
                name="Black Claw",
                duration=3,
                magnitude=144,
                source_ability=ability.name,
                stat_affected='damage_taken_flat'
            )
            self.buff_tracker.add_buff(defender, buff)
            self.log.add_event({'type': 'buff_applied', 'target': defender.name, 'buff': 'Black Claw', 'turn': turn_number})

        # Hunting Party (921)
        elif ability.name == "Hunting Party" or ability.id == 921:
            buff = Buff(
                type=BuffType.STAT_MOD,
                name="Shattered Defenses",
                duration=2,
                magnitude=2.0,
                source_ability=ability.name,
                stat_affected='damage_taken_mult'
            )
            self.buff_tracker.add_buff(defender, buff)
            self.log.add_event({'type': 'buff_applied', 'target': defender.name, 'buff': 'Shattered Defenses', 'turn': turn_number})

    def process_end_of_turn(self, state, p1, p2):
        for p in [p1, p2]:
            if p and p.stats.is_alive():
                self.buff_tracker.process_dots(p)
                self.buff_tracker.process_hots(p)
                self.buff_tracker.decrement_durations(p)