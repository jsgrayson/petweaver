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
from .special_encounters import SpecialEncounterHandler


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
        max_turns: int = 50,
        special_encounter_id: Optional[str] = None
    ) -> Dict:
        """
        Run a complete battle simulation
        
        Args:
            initial_state: Starting battle state
            player_script: List of actions OR function(state) -> TurnAction
            enemy_script: List of actions OR function(state) -> TurnAction
            max_turns: Maximum turns before draw
            special_encounter_id: ID of special encounter mechanic (e.g. 'rocko_immunity')
        
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
            state = self.execute_turn(state, player_action, enemy_action, turn, special_encounter_id)
            
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
        turn_number: int,
        special_encounter_id: Optional[str] = None
    ) -> BattleState:
        """
        Execute a single turn of battle
        """
        # Make a copy to avoid mutating input
        new_state = state.copy()
        
        # Get active pets
        player_pet = new_state.player_team.get_active_pet()
        enemy_pet = new_state.enemy_team.get_active_pet()
        
        if not player_pet or not enemy_pet:
            return new_state
            
        # Special Encounter: Start of Turn Checks
        if special_encounter_id:
            # Rocko Immunity (Auto-death check)
            if special_encounter_id == 'rocko_immunity':
                # Check both pets (in case player has Rocko? Unlikely but safe)
                for pet in [player_pet, enemy_pet]:
                    if SpecialEncounterHandler.has_special_mechanic(pet) == 'rocko_immunity':
                        SpecialEncounterHandler.apply_rocko_immunity(pet, turn_number)
            
            # Gorespine Gore (Stack application)
            elif special_encounter_id == 'gore_stacks':
                for pet in [player_pet, enemy_pet]:
                    if SpecialEncounterHandler.has_special_mechanic(pet) == 'gore_stacks':
                        SpecialEncounterHandler.apply_gorespine_gore(pet, turn_number)
        
        # Module 6: Turn Order Update
        # 1. Damage Over Time (DoT) Tick
        # 2. Weather Effect Damage
        # 3. Pet Status Check (Revives)
        # 4. Choose Abilities (Already done outside)
        # 5. Execute Abilities
        
        # Process DoTs/HoTs/Weather at START of turn
        self.process_end_of_turn(new_state, player_pet, enemy_pet)
        
        # Check if anyone died from DoTs
        if new_state.is_battle_over():
            return new_state
            
        # Re-fetch active pets in case of death/swap (though swap shouldn't happen here)
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
            self.execute_action(action, attacker, defender, attacker_team, new_state, special_encounter_id)
            
            # Check if battle ended
            if new_state.is_battle_over():
                break
        
        # End of turn processing MOVED to start of turn (Module 6)
        # But we still need to tick cooldowns at end of turn?
        # The prompt says: "1. DoT... 5. Execute Abilities".
        # It doesn't explicitly say where cooldowns tick.
        # Standard WoW: Cooldowns tick at end of round.
        # We will keep cooldown ticking here.
        
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
        state: BattleState,
        special_encounter_id: Optional[str] = None
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
            
            # Special Encounter Ability Handling
            special_handled = False
            if special_encounter_id:
                if ability.name == "Life Exchange":
                    SpecialEncounterHandler.apply_life_exchange(attacker, defender)
                    self.log.add_event({'type': 'special_ability', 'ability': 'Life Exchange', 'actor': attacker.name})
                    special_handled = True
                elif ability.name == "Mind Games":
                    SpecialEncounterHandler.apply_mind_games(state.player_team if attacker == state.enemy_team.get_active_pet() else state.enemy_team, attacker)
                    self.log.add_event({'type': 'special_ability', 'ability': 'Mind Games', 'actor': attacker.name})
                    special_handled = True
                elif ability.name == "Bone Prison":
                    SpecialEncounterHandler.apply_bone_prison(defender)
                    self.log.add_event({'type': 'special_ability', 'ability': 'Bone Prison', 'actor': attacker.name})
                    special_handled = True
                elif ability.name == "Shell Shield":
                    SpecialEncounterHandler.apply_shell_shield(attacker)
                    self.log.add_event({'type': 'special_ability', 'ability': 'Shell Shield', 'actor': attacker.name})
                    special_handled = True
            
            if special_handled:
                return  # Skip normal processing for special abilities
            
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
                
                # Check for Delayed Effect (Geyser/Whirlpool)
                # Assuming Ability has 'delayed_turns' attribute (will add next)
                if getattr(ability, 'delayed_turns', 0) > 0:
                    # Apply Delayed Effect Buff
                    buff = Buff(
                        type=BuffType.DELAYED_EFFECT,
                        name=f"Delayed: {ability.name}",
                        duration=ability.delayed_turns,
                        magnitude=ability.power, # Store power for later
                        source_ability=ability.name,
                        stat_affected='none'
                    )
                    self.buff_tracker.add_buff(defender, buff, state.weather)
                    self.log.add_event({
                        'type': 'buff_applied',
                        'buff': buff.name,
                        'target': defender.name,
                        'duration': buff.duration
                    })
                    return # Skip immediate damage

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
                
                # Module 6: Level-Based Miss Chance
                # 5% miss chance if Target Level > Attacker Level
                # Assuming default level 25 for now if not set
                attacker_level = getattr(attacker, 'level', 25)
                defender_level = getattr(defender, 'level', 25)
                
                if defender_level > attacker_level:
                    import random
                    if random.random() < 0.05:
                        damage = 0
                        details['hit'] = False
                        details['final_damage'] = 0
                        self.log.add_event({
                            'type': 'miss',
                            'actor': action.actor,
                            'ability': ability.name,
                            'reason': 'level_difference'
                        })
                
                # Apply bonus multiplier
                damage = int(damage * bonus_mult)
                details['final_damage'] = damage

                # Immunity check: if defender has immunity buff, damage is nullified
                immunity_active = any(
                    buff.type == BuffType.IMMUNITY for buff in defender.active_buffs
                )
                
                # Special Encounter: Rocko Immunity Check
                if special_encounter_id == 'rocko_immunity':
                    if SpecialEncounterHandler.has_special_mechanic(defender) == 'rocko_immunity':
                        # Check if currently immune (turns 1-10)
                        # We need the turn number here. 
                        # execute_action doesn't have turn number passed directly, but state has turn_number
                        if SpecialEncounterHandler.apply_rocko_immunity(defender, state.turn_number):
                            immunity_active = True
                
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
                    
                    # Special Encounter: Toxic Skin Reflection
                    if special_encounter_id == 'toxic_skin':
                         if SpecialEncounterHandler.has_special_mechanic(defender) == 'toxic_skin':
                             reflected = SpecialEncounterHandler.apply_toxic_skin(attacker, actual_damage)
                             if reflected > 0:
                                 self.log.add_event({
                                     'type': 'damage_reflection',
                                     'source': defender.name,
                                     'target': attacker.name,
                                     'amount': reflected
                                 })
                    
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
        # Process buff ticks
        if player_pet and player_pet.stats.is_alive():
            events = self.buff_tracker.tick_all_buffs(player_pet)
            for event in events:
                self.log.add_event(event)
                # Handle delayed effects
                if event['type'] == 'delayed_stun':
                    # Apply Stun
                    stun_buff = Buff(type=BuffType.STUN, duration=1, magnitude=1.0, source_ability=999)
                    self.buff_tracker.add_buff(player_pet, stun_buff)
                    self.log.add_event({'type': 'stun_applied', 'target': player_pet.name, 'source': 'Geyser'})
                elif event['type'] == 'delayed_root':
                    # Apply Root
                    root_buff = Buff(type=BuffType.ROOT, duration=2, magnitude=1.0, source_ability=998)
                    self.buff_tracker.add_buff(player_pet, root_buff)
                    self.log.add_event({'type': 'root_applied', 'target': player_pet.name, 'source': 'Whirlpool'})
                elif event['type'] == 'buff_expired':
                    # Module 6: CC Immunity Clock
                    # If Stun/Root/Sleep expired, add 4-round immunity
                    expired_buff = event['buff']
                    if expired_buff.type in [BuffType.STUN, BuffType.ROOT, BuffType.SLEEP]:
                        immunity_buff = Buff(type=BuffType.IMMUNITY, duration=4, magnitude=1.0, source_ability=0, stat_affected=expired_buff.type.value)
                        # Note: We need to handle specific immunity type in buff_tracker or just use generic IMMUNITY type?
                        # BuffType.IMMUNITY usually means "Immune to Damage".
                        # We need "Immune to CC".
                        # Let's use a custom stat_affected for CC immunity.
                        # Actually, let's use a new BuffType or just handle it in add_buff.
                        # We'll use BuffType.IMMUNITY but with stat_affected='cc_immunity' or specific type.
                        # Let's use 'cc_immunity' for now and update add_buff to check it.
                        # Actually, let's just use the specific type name as stat_affected.
                        self.buff_tracker.add_buff(player_pet, immunity_buff)
                        self.log.add_event({'type': 'cc_immunity_applied', 'target': player_pet.name})

        if enemy_pet and enemy_pet.stats.is_alive():
            events = self.buff_tracker.tick_all_buffs(enemy_pet)
            for event in events:
                self.log.add_event(event)
                # Handle delayed effects
                if event['type'] == 'delayed_stun':
                    stun_buff = Buff(type=BuffType.STUN, duration=1, magnitude=1.0, source_ability=999)
                    self.buff_tracker.add_buff(enemy_pet, stun_buff)
                    self.log.add_event({'type': 'stun_applied', 'target': enemy_pet.name, 'source': 'Geyser'})
                elif event['type'] == 'delayed_root':
                    root_buff = Buff(type=BuffType.ROOT, duration=2, magnitude=1.0, source_ability=998)
                    self.buff_tracker.add_buff(enemy_pet, root_buff)
                    self.log.add_event({'type': 'root_applied', 'target': enemy_pet.name, 'source': 'Whirlpool'})
                elif event['type'] == 'buff_expired':
                    # Module 6: CC Immunity Clock
                    expired_buff = event['buff']
                    if expired_buff.type in [BuffType.STUN, BuffType.ROOT, BuffType.SLEEP]:
                        immunity_buff = Buff(type=BuffType.IMMUNITY, duration=4, magnitude=1.0, source_ability=0, stat_affected=expired_buff.type.value)
                        self.buff_tracker.add_buff(enemy_pet, immunity_buff)
                        self.log.add_event({'type': 'cc_immunity_applied', 'target': enemy_pet.name})
        
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
            # Check Critter Immunity
            if defender.family == PetFamily.CRITTER:
                self.log.add_event({'type': 'immune', 'target': defender.name, 'effect': 'stun'})
                return

            buff = Buff(
                type=BuffType.STUN,
                duration=1,
                magnitude=1.0,
                source_ability=0
            )
            self.buff_tracker.add_buff(defender, buff)
            self.log.add_event({'type': 'stun_applied', 'target': defender.name})
        elif effect_type == 'dot':
            # Check Cleansing Rain (reduces DoT duration by 1)
            duration = 3 # Default
            if state.weather and state.weather.stat_affected == 'cleansing_rain':
                duration -= 1
            
            if duration > 0:
                buff = Buff(
                    type=BuffType.DOT,
                    duration=duration,
                    magnitude=10, # Placeholder
                    source_ability=0
                )
                self.buff_tracker.add_buff(defender, buff)
        elif effect_type == 'swap':
            # Force swap (simplified, just logs for now)
            self.log.add_event({'type': 'force_swap', 'target': defender.name})
