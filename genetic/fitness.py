from typing import List, Dict, Any, Optional
try:
    from simulator import BattleSimulator, BattleState, Team, Pet, Ability, TurnAction, PetStats, PetFamily, PetQuality
except ImportError:
    from simulator import BattleSimulator, BattleState, Team, Pet, Ability, TurnAction, PetStats, PetFamily
    class PetQuality:
        POOR=0; COMMON=1; UNCOMMON=2; RARE=3; EPIC=4; LEGENDARY=5

from .genome import TeamGenome

class FitnessEvaluator:
    def __init__(self, target_team: Team, ability_db: Dict, species_db: Dict, npc_priorities: Dict = None, target_name: str = "Unknown"):
        self.target_team = target_team
        self.ability_db = ability_db
        self.species_db = species_db
        self.npc_priorities = npc_priorities or {}
        self.target_name = target_name
        self.simulator = BattleSimulator(rng_seed=None) 

    def _create_agents(self, genome: TeamGenome):
        player_team = self._genome_to_team(genome)
        
        def genome_agent(state: BattleState) -> TurnAction:
            active_idx = state.player_team.active_pet_index
            if active_idx >= len(state.player_team.pets): return TurnAction(actor='player', action_type='pass')
            active_pet = state.player_team.pets[active_idx]
            enemy_pet = state.enemy_team.get_active_pet()
            
            # 1. Mandatory Swap (Dead)
            if not active_pet.stats.is_alive():
                for i, p in enumerate(state.player_team.pets):
                    if p.stats.is_alive(): return TurnAction(actor='player', action_type='swap', target_pet_index=i)
                return TurnAction(actor='player', action_type='pass')

            if enemy_pet and enemy_pet.stats.is_alive():
                # 2. DEFENSIVE REFLEXES
                danger_buffs = ["Wind-Up", "Supercharge", "Pump", "Lock-On", "Geyser", "Whirlpool"]
                is_danger = False
                for buff in enemy_pet.active_buffs:
                     if any(d in buff.name for d in danger_buffs): is_danger = True
                
                for buff in active_pet.active_buffs:
                    if "Bomb" in buff.name and buff.duration <= 1: is_danger = True

                if is_danger:
                    defensives = ["Dodge", "Decoy", "Deflection", "Burrow", "Lift-Off", "Evanescence", "Bubble"]
                    for ab in active_pet.abilities:
                        if active_pet.can_use_ability(ab) and any(d in ab.name for d in defensives):
                            return TurnAction(actor='player', action_type='ability', ability=ab)
                
                # 3. EXECUTE
                for ab in active_pet.abilities:
                    if active_pet.can_use_ability(ab):
                        if ab.power >= enemy_pet.stats.current_hp:
                            return TurnAction(actor='player', action_type='ability', ability=ab)

                # 4. MATCHUP SWAP
                if enemy_pet.stats.current_hp > 300:
                    incoming_mult = self.simulator.damage_calc.get_family_multiplier(enemy_pet.family, active_pet.family)
                    if incoming_mult > 1.0:
                        best_swap = -1
                        best_score = -100
                        for i, p in enumerate(state.player_team.pets):
                            if i == active_idx or not p.stats.is_alive(): continue
                            def_mod = self.simulator.damage_calc.get_family_multiplier(enemy_pet.family, p.family)
                            off_mod = self.simulator.damage_calc.get_family_multiplier(p.family, enemy_pet.family)
                            score = 0
                            if def_mod < 1.0: score += 10 
                            if def_mod > 1.0: score -= 5
                            if off_mod > 1.0: score += 5
                            if score > best_score and score > 0:
                                best_score = score
                                best_swap = i
                        if best_swap != -1:
                            return TurnAction(actor='player', action_type='swap', target_pet_index=best_swap)

            try:
                pet_gene = genome.pets[active_idx]
                for slot in pet_gene.strategy.priority:
                    idx = slot - 1
                    if 0 <= idx < len(active_pet.abilities):
                        abil = active_pet.abilities[idx]
                        if active_pet.can_use_ability(abil): return TurnAction(actor='player', action_type='ability', ability=abil)
            except: pass
            
            if active_pet.abilities: return TurnAction(actor='player', action_type='ability', ability=active_pet.abilities[0])
            return TurnAction(actor='player', action_type='pass')

        from simulator.npc_ai import create_npc_agent
        from simulator.smart_agent import SmartAgent
        enemy_agent = create_npc_agent(self.target_name, SmartAgent(1.0).decide)
        return player_team, genome_agent, enemy_agent

    def evaluate(self, genome: TeamGenome, num_battles: int = 5) -> float:
        player_team, genome_agent, enemy_agent = self._create_agents(genome)
        if not player_team or not player_team.pets: return 0.0

        total_score = 0
        total_wins = 0
        enemy_max_hp = sum(p.stats.max_hp for p in self.target_team.pets)
        kill_counts = [0, 0, 0]
        valid_kill_counts = [0, 0, 0]

        for _ in range(num_battles):
            battle_state = BattleState(player_team.copy(), self.target_team.copy(), 1)
            result = self.simulator.simulate_battle(battle_state, genome_agent, enemy_agent, max_turns=45, enable_logging=False)
            
            if result['turns'] >= 40:
                return 1.0 # Stalemate penalty

            # Analyze Death Turns for Strict Gauntlet
            p_death_turns = [999, 999, 999] # Default to 999 (survived)
            e_death_turns = [999, 999, 999]
            
            for event in result.get('events', []):
                if event['type'] == 'death':
                    turn = event['turn']
                    pet_name = event['pet']
                    
                    # Find which pet died
                    # We need to map names back to slots. 
                    # This is tricky if names are duplicate, but assuming unique names for now or using index if available.
                    # Simulator events currently store 'pet' name.
                    # Better to check the final state or track IDs.
                    # Heuristic: Check names against initial teams.
                    
                    for i, p in enumerate(player_team.pets):
                        if p.name == pet_name: p_death_turns[i] = turn
                    for i, p in enumerate(self.target_team.pets):
                        if p.name == pet_name: e_death_turns[i] = turn

            if result.get('final_state'):
                enemy_team = result['final_state'].enemy_team
                for i, p in enumerate(enemy_team.pets):
                    if not p.stats.is_alive(): 
                        kill_counts[i] += 1
                        # Strict Gauntlet Check: Did Player I outlive Enemy I?
                        # Or did Player I die on the same turn (Trade)?
                        if p_death_turns[i] >= e_death_turns[i]:
                            valid_kill_counts[i] += 1

            battle_score = 0
            if result.get('final_state'):
                enemy_rem = sum(p.stats.current_hp for p in result['final_state'].enemy_team.pets)
                dmg_pct = (enemy_max_hp - enemy_rem) / max(1, enemy_max_hp)
                battle_score += (dmg_pct * 5000)
                
                for i, enemy_p in enumerate(result['final_state'].enemy_team.pets):
                    if not enemy_p.stats.is_alive():
                         battle_score += 2000 * (2 ** i)

                surviving = sum(1 for p in result['final_state'].player_team.pets if p.stats.is_alive())
                battle_score += (surviving * 500)
            
            if result['winner'] == 'player':
                total_wins += 1
                battle_score += 20000
                battle_score += (40 - min(result['turns'], 40)) * 100

            total_score += battle_score

        # CONSISTENCY CHECK
        if total_wins < num_battles:
            total_score *= 0.5
            
        # Generate Win Status based on Consistency (Majority Rule) AND Strict Gauntlet
        # Rule: Slot I is 'W' only if:
        # 1. Enemy I is dead in >50% of battles.
        # 2. Player I outlived Enemy I (or traded) in those battles.
        
        final_win_status = ["L", "L", "L"]
        threshold = num_battles / 2.0
        
        for i in range(3):
            # Check if Enemy I died consistently
            if kill_counts[i] > threshold:
                # Check if Player I consistently did their job (outlived Enemy I)
                # We track "valid kills" where Player I death >= Enemy I death
                if valid_kill_counts[i] > threshold:
                    final_win_status[i] = "W"

        genome.win_status = "".join(final_win_status)
        return total_score / num_battles

    def play_battle(self, genome: TeamGenome, enable_logging: bool = False) -> Dict:
        player_team, genome_agent, enemy_agent = self._create_agents(genome)
        battle_state = BattleState(player_team.copy(), self.target_team.copy(), 1)
        return self.simulator.simulate_battle(battle_state, genome_agent, enemy_agent, max_turns=50, enable_logging=enable_logging)

    def _genome_to_team(self, genome: TeamGenome) -> Team:
        pets = []
        
        # Load breed stats if not already loaded
        if not hasattr(self, 'breed_stats'):
            try:
                import json
                with open('breed_stats.json') as f:
                    breed_data = json.load(f)
                    self.breed_stats = breed_data['breeds']
            except:
                self.breed_stats = {}
        
        for pet_gene in genome.pets:
            species_data = self.species_db.get(str(pet_gene.species_id)) or self.species_db.get(pet_gene.species_id)
            if species_data and 'base_stats' in species_data:
                base = species_data['base_stats']
                base_hp = base.get('health', 8)
                base_power = base.get('power', 8)
                base_speed = base.get('speed', 8)
                
                # Apply breed modifiers
                breed_id = str(pet_gene.breed_id)
                if breed_id in self.breed_stats:
                    breed = self.breed_stats[breed_id]
                    hp_mod = breed.get('hp_modifier', 0.0)
                    power_mod = breed.get('power_modifier', 0.0)
                    speed_mod = breed.get('speed_modifier', 0.0)
                else:
                    hp_mod = power_mod = speed_mod = 0.0
                
                # Calculate level 25 rare stats with breed modifiers
                # Formula: ((base_stat * 5 + 100) * quality_modifier * breed_modifier) * level + constant
                # Quality modifier for Rare = 1.3
                # Level 25
                hp = int((base_hp * 5 * 25 * 1.3 * (1 + hp_mod)) + 100)
                power = int(base_power * 25 * 1.3 * (1 + power_mod))
                speed = int(base_speed * 25 * 1.3 * (1 + speed_mod))
                
                name = species_data.get('name', f"Pet {pet_gene.species_id}")
                family_id = species_data.get('family_id', 7)
            else:
                hp, power, speed = 1400, 260, 260
                name = f"Unknown {pet_gene.species_id}"
                family_id = 7

            stats = PetStats(max_hp=hp, current_hp=hp, power=power, speed=speed)
            abilities = []
            for ab_id in pet_gene.abilities:
                ab_info = self.ability_db.get(str(ab_id)) or self.ability_db.get(ab_id)
                if ab_info:
                    if isinstance(ab_info, list):
                        ab_info = {'id': ab_id, 'name': str(ab_info[1]) if len(ab_info)>1 else "Unknown", 'family_id': 7, 'power': 20, 'accuracy': 100, 'cooldown': 0, 'speed': 0}
                    fam_val = ab_info.get('family_id', 7)
                    try: fam = PetFamily(fam_val)
                    except: fam = PetFamily.BEAST
                    
                    abilities.append(Ability(
                        id=ab_id, 
                        name=ab_info.get('name', 'Unknown'), 
                        power=ab_info.get('power', 20), 
                        accuracy=ab_info.get('accuracy', 100), 
                        speed=ab_info.get('speed', 0), 
                        cooldown=ab_info.get('cooldown', 0), 
                        family=fam,
                        effect_type=ab_info.get('effect_type'),
                        is_heal=ab_info.get('is_heal', False),
                        priority=ab_info.get('priority', 0)
                    ))
                    if ab_id == 124: # Rampage
                         print(f"DEBUG: Loaded Rampage: is_heal={abilities[-1].is_heal}, power={abilities[-1].power}")
                else:
                    abilities.append(Ability(id=ab_id, name="Unknown", power=20, accuracy=100, speed=0, cooldown=0, family=PetFamily.BEAST))

            try: pet_family = PetFamily(family_id)
            except: pet_family = PetFamily.BEAST
            pets.append(Pet(species_id=pet_gene.species_id, name=name, family=pet_family, stats=stats, abilities=abilities, quality=PetQuality.RARE))
        
        return Team(pets=pets)