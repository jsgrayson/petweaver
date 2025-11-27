from typing import List, Dict, Optional, Union, Callable
from .battle_state import BattleState, Team, Pet, Ability, Buff, BuffType, PetFamily, TurnAction
from .damage_calculator import DamageCalculator
from .turn_system import TurnSystem
from .buff_tracker import BuffTracker
from .special_encounters import SpecialEncounterHandler
from .racial_passives import RacialPassives

class BattleLog:
    def __init__(self):
        self.events: List[Dict] = []
        self.turn_summaries: List[str] = []
    def add_event(self, event: Dict):
        self.events.append(event)
    def add_turn_summary(self, turn: int, summary: str):
        self.turn_summaries.append(f"Turn {turn}: {summary}")
    def get_full_log(self) -> str:
        log_lines = []
        current_turn = 0
        for event in self.events:
            turn = event.get('turn', 0)
            if turn != current_turn:
                log_lines.append(f"--- Turn {turn} ---")
                current_turn = turn
            
            etype = event.get('type')
            actor = event.get('actor', 'Unknown')
            if etype == 'damage':
                log_lines.append(f"{actor} used {event.get('ability')} for {event.get('amount')} damage")
            elif etype == 'heal':
                log_lines.append(f"{actor} used {event.get('ability')} for {event.get('amount')} healing")
            elif etype == 'buff_applied':
                log_lines.append(f"{event.get('target')} gained {event.get('buff')}")
            elif etype == 'death':
                log_lines.append(f"{event.get('pet')} died!")
            elif etype == 'swap':
                log_lines.append(f"{actor} swapped to {event.get('new_index')}")
            elif etype == 'miss':
                log_lines.append(f"{actor} used {event.get('ability')} but MISSED")
            else:
                log_lines.append(str(event))
        return "\n".join(log_lines)

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
            
            # AUTO-CORRECT: Force swap if dead
            player_action = self._validate_action(state.player_team, player_action, 'player')
            enemy_action = self._validate_action(state.enemy_team, enemy_action, 'enemy')
            
            state = self.execute_turn(state, player_action, enemy_action, turn, special_encounter_id)
            if state.is_battle_over(): break
        
        winner = state.get_winner() or 'draw'
        return {'winner': winner, 'turns': turn, 'log': self.log, 'final_state': state, 'events': self.log.events}
    
    def _validate_action(self, team, action, actor):
        active = team.get_active_pet()
        if not active or not active.stats.is_alive():
            for i, p in enumerate(team.pets):
                if p.stats.is_alive(): return TurnAction(actor=actor, action_type='swap', target_pet_index=i)
            return TurnAction(actor=actor, action_type='pass')
        return action

    def _get_action(self, script, state, turn, actor):
        if callable(script):
            try: return script(state)
            except Exception as e:
                print(f"Agent Error ({actor}): {e}")
                import traceback
                traceback.print_exc()
                return TurnAction(actor=actor, action_type='pass')
        else:
            idx = min(turn - 1, len(script) - 1)
            return script[idx]
    
    def execute_turn(self, state, player_action, enemy_action, turn_number, special_encounter_id=None):
        # self.process_end_of_turn(state, state.player_team.get_active_pet(), state.enemy_team.get_active_pet())
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

            self.execute_action(action, attacker, defender, attacker_team, state, special_encounter_id, turn_number)
            if state.is_battle_over(): break
        
        if player_pet: player_pet.tick_cooldowns()
        if enemy_pet: enemy_pet.tick_cooldowns()
        
        self.process_end_of_turn(state, state.player_team.get_active_pet(), state.enemy_team.get_active_pet())
        
        state.turn_number = turn_number + 1
        return state
    
    def execute_action(self, action, attacker, defender, attacker_team, state, special_encounter_id, turn_number):
        # DEBUG logging disabled for performance
        print(f"DEBUG: Executing {action.actor} {action.action_type} {action.ability.name if action.ability else ''}")
        if action.action_type == 'swap':
            if action.target_pet_index is not None:
                attacker_team.active_pet_index = action.target_pet_index
                self.log.add_event({'type': 'swap', 'actor': action.actor, 'turn': turn_number, 'new_index': action.target_pet_index})
        elif action.action_type == 'ability' and action.ability:
            ability = action.ability
            attacker.use_ability(ability)
            
            # Immunity
            is_immune = False
            if special_encounter_id == 'rocko_immunity' and SpecialEncounterHandler.apply_rocko_immunity(defender, state.turn_number): is_immune = True
            for buff in defender.active_buffs:
                if buff.type in [BuffType.INVULNERABILITY, BuffType.IMMUNITY] or "Decoy" in buff.name: is_immune = True
            
            if is_immune:
                self.log.add_event({'type': 'immune', 'turn': turn_number, 'actor': action.actor, 'ability': ability.name})
                return 

            if ability.is_heal and ability.power > 0:
                heal = self.damage_calc.calculate_healing(ability, attacker)
                attacker.stats.heal(heal)
                self.log.add_event({'type': 'heal', 'actor': action.actor, 'ability': ability.name, 'amount': heal, 'turn': turn_number})
            elif not ability.is_heal:
                print(f"DEBUG: Calling calculate_damage for {ability.name}")
                damage, details = self.damage_calc.calculate_damage(ability, attacker, defender, state.weather)
                if details['hit']:
                    remaining = self.buff_tracker.consume_shield(defender, damage)
                    defender.stats.take_damage(remaining)
                    self.log.add_event({'type': 'damage', 'actor': action.actor, 'ability': ability.name, 'amount': remaining, 'turn': turn_number})
                    self.check_death_with_racials(defender, turn_number)
                else:
                    self.log.add_event({'type': 'miss', 'actor': action.actor, 'ability': ability.name, 'turn': turn_number})
                
                # Special Case: Explode (282) kills the user
                if ability.id == 282 or ability.name == "Explode":
                    attacker.stats.current_hp = 0
                    self.check_death_with_racials(attacker, turn_number, note='self-destruct')
            
            # Apply Buffs/Effects
            self.apply_ability_effects(ability, attacker, defender, turn_number)

    def apply_ability_effects(self, ability, attacker, defender, turn_number):
        """Apply status effects, buffs, and debuffs based on ability"""
        # Dodge (312)
        if ability.name == "Dodge" or ability.id == 312:
            buff = Buff(
                type=BuffType.INVULNERABILITY,
                name="Dodge",
                duration=1,
                magnitude=0,
                source_ability=ability.name,
                stat_affected='none'
            )
            self.buff_tracker.add_buff(attacker, buff)
            self.log.add_event({'type': 'buff_applied', 'target': attacker.name, 'buff': 'Dodge', 'turn': turn_number})

        # Burrow (159)
        elif ability.name == "Burrow" or ability.id == 159:
            # 1. Underground (Invulnerable)
            buff_underground = Buff(
                type=BuffType.INVULNERABILITY,
                name="Underground",
                duration=1,
                magnitude=0,
                source_ability=ability.name,
                stat_affected='none'
            )
            self.buff_tracker.add_buff(attacker, buff_underground)
            
            # 2. Delayed Attack (Damage next turn)
            # Note: Power is in ability.power (20). We need to calculate damage.
            # For simplicity, we store base power or calculated damage?
            # Delayed effects usually calculate damage on impact.
            # We'll store the base power in magnitude for now, or use a fixed value.
            # Burrow usually deals damage equal to the ability power.
            buff_attack = Buff(
                type=BuffType.DELAYED_EFFECT,
                name="Burrow Attack",
                duration=1,
                magnitude=ability.power if ability.power > 0 else 20, # Fallback
                source_ability=ability.name,
                stat_affected='none'
            )
            self.buff_tracker.add_buff(attacker, buff_attack)
            self.log.add_event({'type': 'buff_applied', 'target': attacker.name, 'buff': 'Underground', 'turn': turn_number})

        # Black Claw (919) - Adds damage taken debuff
        elif ability.name == "Black Claw" or ability.id == 919:
            buff = Buff(
                type=BuffType.STAT_MOD, # Or separate type for flat damage add?
                name="Black Claw",
                duration=3,
                magnitude=144, # Flat damage add (approx for level 25)
                source_ability=ability.name,
                stat_affected='damage_taken_flat' # Custom stat for flat add
            )
            # Note: BuffTracker needs to handle 'damage_taken_flat' in damage calc
            # For now, we assume damage_calc handles it or we hack it here.
            # Actually, DamageCalculator needs to check this.
            self.buff_tracker.add_buff(defender, buff)
            self.log.add_event({'type': 'buff_applied', 'target': defender.name, 'buff': 'Black Claw', 'turn': turn_number})

        # Hunting Party (921) - Applies Shattered Defenses (Double Damage)
        elif ability.name == "Hunting Party" or ability.id == 921:
            buff = Buff(
                type=BuffType.STAT_MOD,
                name="Shattered Defenses",
                duration=2,
                magnitude=2.0, # 100% increased damage
                source_ability=ability.name,
                stat_affected='damage_taken_mult'
            )
            self.buff_tracker.add_buff(defender, buff)
            self.log.add_event({'type': 'buff_applied', 'target': defender.name, 'buff': 'Shattered Defenses', 'turn': turn_number})


    def check_death_with_racials(self, pet, turn_number, note=None):
        if not pet.stats.is_alive():
            # Check Mechanical Failsafe
            if pet.family == PetFamily.MECHANICAL:
                if RacialPassives.apply_mechanical_passive(pet):
                    self.log.add_event({'type': 'revive', 'pet': pet.name, 'turn': turn_number, 'note': 'Failsafe'})
                    return

            # If not revived, log death
            self.log.add_event({'type': 'death', 'pet': pet.name, 'turn': turn_number, 'note': note})

    def process_end_of_turn(self, state, p1, p2):
        for p in [p1, p2]:
            if p and p.stats.is_alive():
                self.buff_tracker.process_dots(p)
                self.buff_tracker.process_hots(p)
                self.buff_tracker.decrement_durations(p)