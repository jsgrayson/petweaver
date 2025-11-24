"""
Battle Simulator - Main orchestrator for pet battles

Runs turn-by-turn simulations using all the component systems
(battle state, damage calculator, turn order, buff tracking).
"""

from typing import List, Dict, Optional, Tuple, Union, Callable
from .battle_state import BattleState, Team, Pet, Ability, TurnAction, Buff, BuffType, PetFamily
from .damage_calculator import DamageCalculator
from .turn_system import TurnSystem
from .buff_tracker import BuffTracker
from .racial_passives import RacialPassives


class BattleLog:
    """Stores detailed log of battle events"""
    
    def __init__(self):
        self.events: List[Dict] = []
        self.turn_summaries: List[str] = []
    
    def add_event(self, event: Dict):
        """Add an event to the log"""
        self.events.append(event)
    
    def add_turn_summary(self, turn: int, summary: str):
        """Add a turn summary"""
        self.turn_summaries.append(f"Turn {turn}: {summary}")
    
    def get_full_log(self) -> str:
        """Get complete battle log as string"""
        return "\n".join(self.turn_summaries)


class BattleSimulator:
    """Main battle simulation engine"""
    
    def __init__(self, rng_seed: Optional[int] = None):
        """Initialize simulator with optional RNG seed"""
        self.damage_calc = DamageCalculator(rng_seed)
        self.turn_system = TurnSystem(rng_seed)
        self.buff_tracker = BuffTracker()
        self.log = BattleLog()
    
    def simulate_battle(
        self,
        initial_state: BattleState,
        player_script: Union[List[TurnAction], Callable[['BattleState'], TurnAction]],
        enemy_script: Union[List[TurnAction], Callable[['BattleState'], TurnAction]],
        max_turns: int = 50
    ) -> Dict:
        """
        Run a complete battle simulation
        
        Args:
            initial_state: Starting battle state
            player_script: List of actions OR function(state) -> TurnAction
            enemy_script: List of actions OR function(state) -> TurnAction
            max_turns: Maximum turns before draw
        
        Returns:
            {
                'winner': 'player'|'enemy'|'draw',
                'turns': turn_count,
                'log': battle_log,
                'final_state': BattleState
            }
        """
        state = initial_state.copy()
        self.log = BattleLog()  # Fresh log
        
        turn = 0
        while not state.is_battle_over() and turn < max_turns:
            turn += 1
            self.log.add_turn_summary(turn, f"Turn {turn} begins")
            
            # Get actions for this turn
            player_action = self._get_action(player_script, state, turn, 'player')
            enemy_action = self._get_action(enemy_script, state, turn, 'enemy')
            
            # Execute the turn
            state = self.execute_turn(state, player_action, enemy_action, turn)
            
            # Check for battle end
            if state.is_battle_over():
                break
        
        winner = state.get_winner() or 'draw'
        
        return {
            'winner': winner,
            'turns': turn,
            'log': self.log,
            'final_state': state,
            'events': self.log.events
        }
    
    def _get_action(
        self, 
        script: Union[List[TurnAction], Callable[['BattleState'], TurnAction]], 
        state: BattleState, 
        turn: int,
        actor: str
    ) -> TurnAction:
        """Helper to get action from list or agent function"""
        if callable(script):
            try:
                action = script(state)
                # print(f"DEBUG: {actor} agent returned {action}")
                return action
            except Exception as e:
                # Fallback if agent fails
                print(f"Agent error ({actor}): {e}")
                import traceback
                traceback.print_exc()
                return TurnAction(actor=actor, action_type='pass')
        else:
            # List script
            idx = min(turn - 1, len(script) - 1)
            return script[idx]
    
    def execute_turn(
        self,
        state: BattleState,
        player_action: TurnAction,
        enemy_action: TurnAction,
        turn_number: int
    ) -> BattleState:
        """
        Execute a single turn of battle
        """
        # Make a copy to avoid mutating input
        new_state = state.copy()
        new_state = state.copy()
        
        # Get active pets
        player_pet = new_state.player_team.get_active_pet()
        enemy_pet = new_state.enemy_team.get_active_pet()
        
        if not player_pet or not enemy_pet:
            return new_state
        
        # Determine action order
        action_order = self.turn_system.determine_turn_order(
            player_pet, player_action,
            enemy_pet, enemy_action
        )
        
        # Execute actions in order
        for actor, action in action_order:
            if actor == 'player':
                attacker = player_pet
                defender = enemy_pet
                attacker_team = new_state.player_team
            else:
                attacker = enemy_pet
                defender = player_pet
                attacker_team = new_state.enemy_team
            
            # Skip if attacker is dead (unless it's a swap, which is allowed for dead pets to switch out? 
            # No, dead pets can't swap themselves, the trainer swaps them. But the action comes from the trainer.)
            # Skip if attacker is dead, UNLESS it's a swap (trainer action)
            if not attacker.stats.is_alive() and action.action_type != 'swap':
                self.log.add_event({'type': 'skip_turn', 'actor': actor, 'reason': 'dead'})
                continue

            # Execute the action
            self.execute_action(action, attacker, defender, attacker_team, new_state)
            
            # Check if battle ended
            if new_state.is_battle_over():
                break
        
        # End of turn: process DoTs/HoTs and tick buffs
        self.process_end_of_turn(new_state, player_pet, enemy_pet)
        
        # Tick cooldowns
        if player_pet:
            player_pet.tick_cooldowns()
        if enemy_pet:
            enemy_pet.tick_cooldowns()
        
        # Increment turn counter
        new_state.turn_number = turn_number + 1
        
        return new_state
    
    def execute_action(
        self,
        action: TurnAction,
        attacker: Pet,
        defender: Pet,
        attacker_team: Team,
        state: BattleState
    ):
        """Execute a single action (ability, swap, etc.)"""
        if action.action_type == 'swap':
            # Handle pet swap
            if action.target_pet_index is not None:
                attacker_team.active_pet_index = action.target_pet_index
                self.log.add_event({
                    'type': 'swap',
                    'actor': action.actor,
                    'new_pet_index': action.target_pet_index
                })
        
        elif action.action_type == 'ability' and action.ability:
            # Use ability
            ability = action.ability
            
            # Set cooldown
            attacker.use_ability(ability)
            
            if ability.is_heal:
                # Healing ability
                heal_amount = self.damage_calc.calculate_healing(ability, attacker)
                actual_heal = attacker.stats.heal(heal_amount)
                
                self.log.add_event({
                    'type': 'heal',
                    'actor': action.actor,
                    'ability': ability.name,
                    'amount': actual_heal
                })
            else:
                # Damage ability
                # Check for bonus damage condition
                bonus_mult = 1.0
                if ability.bonus_condition:
                    if self._check_condition(ability.bonus_condition, attacker, defender, state):
                        bonus_mult += ability.bonus_damage_percent
                        self.log.add_event({
                            'type': 'bonus_triggered',
                            'condition': ability.bonus_condition
                        })

                damage, details = self.damage_calc.calculate_damage(
                    ability, attacker, defender, state.weather
                )
                
                # Apply bonus multiplier
                damage = int(damage * bonus_mult)
                details['final_damage'] = damage

                # Immunity check: if defender has immunity buff, damage is nullified
                immunity_active = any(
                    buff.type == BuffType.IMMUNITY for buff in defender.active_buffs
                )
                if immunity_active:
                    damage = 0
                    details['final_damage'] = 0
                    self.log.add_event({
                        'type': 'immunity_block',
                        'actor': action.actor,
                        'ability': ability.name,
                        'target': defender.name
                    })
                
                if details['hit']:
                    # Check shields first
                    remaining_damage = self.buff_tracker.consume_shield(defender, damage)
                    
                    # Store previous HP for Dragonkin passive detection
                    previous_hp = defender.stats.current_hp
                    
                    # Apply remaining damage
                    actual_damage = defender.stats.take_damage(remaining_damage)
                    
                    # Apply Humanoid passive (heal 4% max HP after dealing damage)
                    if attacker.family == PetFamily.HUMANOID and actual_damage > 0:
                        humanoid_heal = RacialPassives.apply_humanoid_passive(attacker, actual_damage)
                        if humanoid_heal > 0:
                            self.log.add_event({
                                'type': 'racial_passive',
                                'passive': 'humanoid_heal',
                                'pet': attacker.name,
                                'amount': humanoid_heal
                            })
                    
                    # Check if Dragonkin passive should trigger (fell below 50% HP)
                    if defender.family == PetFamily.DRAGONKIN:
                        if RacialPassives.check_dragonkin_trigger(defender, previous_hp):
                            defender.dragonkin_buff_ready = True
                            self.log.add_event({
                                'type': 'racial_passive',
                                'passive': 'dragonkin_buff_ready',
                                'pet': defender.name
                            })
                    
                    self.log.add_event({
                        'type': 'damage',
                        'actor': action.actor,
                        'ability': ability.name,
                        'damage': actual_damage,
                        'crit': details['crit'],
                        'defender_hp': defender.stats.current_hp
                    })
                    
                    # Apply secondary effects (stun, etc.)
                    if ability.effect_type and ability.effect_chance > 0:
                        import random
                        if random.randint(1, 100) <= ability.effect_chance:
                            self._apply_effect(ability.effect_type, attacker, defender, state)
                    
                    # Check if defender died
                    if not defender.stats.is_alive():
                        # Check for Undead racial passive (revive for 1 turn)
                        if defender.family == PetFamily.UNDEAD:
                            if RacialPassives.apply_undead_passive(defender):
                                self.log.add_event({
                                    'type': 'racial_passive',
                                    'passive': 'undead_revive',
                                    'pet': defender.name
                                })
                        # Check for Mechanical racial passive (revive to 20% HP once)
                        elif defender.family == PetFamily.MECHANICAL:
                            if RacialPassives.apply_mechanical_passive(defender):
                                self.log.add_event({
                                    'type': 'racial_passive',
                                    'passive': 'mechanical_revive',
                                    'pet': defender.name,
                                    'hp': defender.stats.current_hp
                                })
                        
                        if not defender.stats.is_alive():
                            self.log.add_event({
                                'type': 'death',
                                'pet': defender.name
                            })
                else:
                    self.log.add_event({
                        'type': 'miss',
                        'actor': action.actor,
                        'ability': ability.name
                    })
            
            # Apply buffs from ability
            if ability.stat_buffs:
                for stat, (multiplier, duration) in ability.stat_buffs.items():
                    buff = Buff(
                        type=BuffType.STAT_MOD,
                        duration=duration,
                        magnitude=multiplier,
                        stat_affected=stat,
                        source_ability=ability.id
                    )
                    self.buff_tracker.add_buff(attacker, buff)
                    
                    self.log.add_event({
                        'type': 'buff_applied',
                        'target': action.actor,
                        'buff': stat,
                        'duration': duration
                    })
    
    def process_end_of_turn(self, state: BattleState, player_pet: Optional[Pet], enemy_pet: Optional[Pet]):
        """Process end-of-turn effects (DoTs, HoTs, buff expiration)"""
        # Process Undead revive turns
        for pet in [player_pet, enemy_pet]:
            if pet and pet.has_undead_revive:
                pet.revive_turns_remaining -= 1
                if pet.revive_turns_remaining <= 0:
                    # Undead revive expired, pet truly dies
                    pet.stats.current_hp = 0
                    pet.has_undead_revive = False
                    self.log.add_event({
                        'type': 'undead_revive_expired',
                        'pet': pet.name
                    })
        
        # Process weather DoT damage
        if state.weather and state.weather.type == BuffType.WEATHER:
            weather_name = getattr(state.weather, 'stat_affected', None)  # Using stat_affected to store weather name
            
            # Weather DoT effects
            weather_dots = {
                'scorched_earth': {'damage': 35, 'family': 'Dragonkin', 'immune': PetFamily.ELEMENTAL},
                'call_lightning': {'damage': 30, 'family': 'Elemental', 'immune': None},
            }
            
            if weather_name in weather_dots:
                weather_info = weather_dots[weather_name]
                
                for pet, target_name in [(player_pet, 'player'), (enemy_pet, 'enemy')]:
                    if pet and pet.stats.is_alive():
                        # Check if pet is immune (Elemental racial passive)
                        is_immune = False
                        if weather_info['immune'] and pet.family == weather_info['immune']:
                            is_immune = True
                        elif pet.family == PetFamily.ELEMENTAL:
                            # Elementals immune to all weather damage
                            is_immune = RacialPassives.apply_elemental_passive()
                        
                        if not is_immune:
                            damage = weather_info['damage']
                            actual_damage = pet.stats.take_damage(damage)
                            self.log.add_event({
                                'type': 'weather_dot',
                                'weather': weather_name,
                                'target': target_name,
                                'pet': pet.name,
                                'damage': actual_damage
                            })
        
        if player_pet:
            events = self.buff_tracker.tick_all_buffs(player_pet)
            for event in events:
                self.log.add_event({**event, 'target': 'player'})
        
        if enemy_pet:
            events = self.buff_tracker.tick_all_buffs(enemy_pet)
            for event in events:
                self.log.add_event({**event, 'target': 'enemy'})
        
        # Tick weather duration
        if state.weather:
            still_active = state.weather.tick()
            if not still_active:
                state.weather = None
                self.log.add_event({'type': 'weather_ended'})

    def _check_condition(self, condition: str, attacker: Pet, defender: Pet, state: BattleState) -> bool:
        """Check if a bonus condition is met"""
        if condition == 'weather_sunny':
            return state.weather and state.weather.source_ability == 592 # Sunny Day ID (simplified)
        elif condition == 'target_webbed':
            for buff in defender.active_buffs:
                if buff.type.value == 'webbed': # Need to add this type
                    return True
        elif condition == 'target_blind':
             for buff in defender.active_buffs:
                if buff.type.value == 'blind':
                    return True
        return False

    def _apply_effect(self, effect_type: str, attacker: Pet, defender: Pet, state: BattleState):
        """Apply a secondary effect"""
        if effect_type == 'stun':
            # Apply stun buff
            buff = Buff(
                type=BuffType.STUN,
                duration=1,
                magnitude=0,
                source_ability=0
            )
            self.buff_tracker.add_buff(defender, buff)
            self.log.add_event({'type': 'stun_applied', 'target': defender.name})
        elif effect_type == 'swap':
            # Force swap (simplified, just logs for now)
            self.log.add_event({'type': 'force_swap', 'target': defender.name})
