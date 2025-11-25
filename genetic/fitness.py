from typing import List, Dict
from simulator import BattleSimulator, BattleState, Team, Pet, Ability, TurnAction, PetStats, PetFamily, PetQuality
from .genome import TeamGenome

class FitnessEvaluator:
    def __init__(self, target_team: Team, ability_db: Dict, species_db: Dict, npc_priorities: Dict = None, target_name: str = "Unknown"):
        self.target_team = target_team
        self.ability_db = ability_db
        self.species_db = species_db
        self.npc_priorities = npc_priorities or {}
        self.target_name = target_name
        self.simulator = BattleSimulator(rng_seed=None) # Random seed for variety

    def evaluate(self, genome: TeamGenome, num_battles: int = 5) -> float:
        """
        Run simulations to determine fitness score.
        Score = (Win Rate * 1000) + (Survival Bonus) - (Turn Penalty)
        """
        total_score = 0
        
        # Convert Genome to Playable Team
        player_team = self._genome_to_team(genome)
        
        # Define Agent Function from Genome Strategy
        def genome_agent(state: BattleState) -> TurnAction:
            active_pet_idx = state.player_team.active_pet_index
            try:
                pet_gene = genome.pets[active_pet_idx]
                active_pet = state.player_team.pets[active_pet_idx]
            except IndexError:
                print(f"CRITICAL ERROR: active_pet_idx={active_pet_idx} out of range. Genome pets={len(genome.pets)}, Team pets={len(state.player_team.pets)}")
                return TurnAction(actor='player', action_type='pass')
            
            # Check if active pet is dead -> Must Swap
            if not active_pet.stats.is_alive():
                # Find next living pet
                for i, p in enumerate(state.player_team.pets):
                    if p.stats.is_alive():
                        return TurnAction(actor='player', action_type='swap', target_pet_index=i)
                return TurnAction(actor='player', action_type='pass') # No one left
            
            # Check conditions
            for slot, (cond_type, cond_val) in pet_gene.strategy.conditions.items():
                # Simplified condition check
                if cond_type == 'enemy_hp_lt':
                    enemy = state.enemy_team.get_active_pet()
                    if enemy and (enemy.stats.current_hp / enemy.stats.max_hp * 100) < cond_val:
                        # Try to use this slot
                        ability_idx = slot - 1
                        if 0 <= ability_idx < len(active_pet.abilities):
                            ability = active_pet.abilities[ability_idx]
                            if active_pet.can_use_ability(ability):
                                return TurnAction(actor='player', action_type='ability', ability=ability)

            # Fallback to priority list
            for slot in pet_gene.strategy.priority:
                ability_idx = slot - 1
                if 0 <= ability_idx < len(active_pet.abilities):
                    ability = active_pet.abilities[ability_idx]
                    if active_pet.can_use_ability(ability):
                        return TurnAction(actor='player', action_type='ability', ability=ability)
            
            return TurnAction(actor='player', action_type='pass')


        # Enemy Agent - Use SmartEnemyAgent for consistent behavior
        from .agents import create_smart_enemy_agent
        from simulator.npc_ai import create_npc_agent
        
        # Pass priorities if available
        # Note: npc_priorities is Dict[int, List[int]] mapping pet_idx -> ability_ids
        # We need to ensure keys are integers
        priorities = {int(k): v for k, v in self.npc_priorities.items()} if self.npc_priorities else None
        base_agent = create_smart_enemy_agent(difficulty=1.0, ability_priorities=priorities)
        enemy_agent = create_npc_agent(self.target_name, base_agent)

        # Run Battles
        wins = 0
        total_turns = 0
        total_survival = 0
        
        # Track performance even in losses
        total_damage_dealt = 0
        total_enemy_hp_removed = 0
        
        # Accumulate ability stats across all battles for averaging
        total_power = 0
        total_accuracy = 0
        total_speed = 0
        total_cooldown = 0
        ability_count = 0
        
        for _ in range(num_battles):
            # Reset teams for fresh battle
            battle_state = BattleState(
                player_team=player_team.copy(), # Important: fresh copy
                enemy_team=self.target_team.copy(),
                turn_number=1
            )
            
            result = self.simulator.simulate_battle(battle_state, genome_agent, enemy_agent, max_turns=30)
            
            # Track damage dealt to enemy (even in losses)
            enemy_max_hp = sum(p.stats.max_hp for p in self.target_team.pets)
            enemy_remaining_hp = sum(p.stats.current_hp for p in result['final_state'].enemy_team.pets)
            damage_dealt = enemy_max_hp - enemy_remaining_hp
            
            # Debug logging for first battle to diagnose issues
            if _ == 0:
                species_summary = ", ".join([str(p.species_id) for p in genome.pets])
                print(f"[FITNESS] Team [{species_summary}] Battle 1: Winner={result['winner']}, "
                      f"Damage={damage_dealt}/{enemy_max_hp} ({damage_dealt/enemy_max_hp*100:.1f}%), "
                      f"Turns={result['turns']}")

            total_damage_dealt += damage_dealt
            total_enemy_hp_removed += (damage_dealt / enemy_max_hp)  # Normalized 0-1
            
            if result['winner'] == 'player':
                wins += 1
                total_turns += result['turns']
                
                # Calculate survival %
                surviving_hp = sum(p.stats.current_hp for p in result['final_state'].player_team.pets)
                max_hp = sum(p.stats.max_hp for p in result['final_state'].player_team.pets)
                total_survival += (surviving_hp / max_hp)
            
            # Gather ability stats from ALL teams (not just winners)
            for pet in result['final_state'].player_team.pets:
                for ab in pet.abilities:
                    total_power += ab.power
                    total_accuracy += ab.accuracy
                    total_speed += ab.speed
                    total_cooldown += ab.cooldown
                    ability_count += 1
        # Calculate Final Score
        win_rate = wins / num_battles
        avg_turns = total_turns / wins if wins > 0 else 30
        avg_survival = total_survival / wins if wins > 0 else 0
        avg_damage_pct = total_enemy_hp_removed / num_battles  # Average % of enemy HP removed
        
        # Ability-stat averages (guard against division by zero)
        if ability_count > 0:
            avg_power = total_power / ability_count
            avg_accuracy = total_accuracy / ability_count
            avg_speed = total_speed / ability_count
            avg_cooldown = total_cooldown / ability_count
        else:
            avg_power = avg_accuracy = avg_speed = avg_cooldown = 0
        
        # Weighted fitness (tweakable coefficients)
        # Give every genome a minimal baseline so it can be ranked even if it never wins
        score = 1
        
        # Primary win-rate component (huge bonus for wins)
        score += (win_rate * 1000)
        
        # IMPORTANT: Reward damage dealt even in losses (this differentiates losing teams)
        score += (avg_damage_pct * 200)  # Up to 200 points for dealing 100% of enemy HP
        
        if wins > 0:
            # Healthy team bonus
            score += (avg_survival * 500)
            # Slower wins penalty
            score -= (avg_turns * 10)
            
            # Trivial win penalty (suspiciously fast wins suggest broken mechanics)
            if avg_turns < 5:
                score *= 0.5  # Reduce score by 50% for unrealistic wins
        
        # Reward ability quality (applies to all teams)
        score += (avg_power * 2)
        score += (avg_accuracy * 1)
        score += (avg_speed * 0.5)
        # Penalise long cooldowns
        score -= (avg_cooldown * 5)
        
        # Add diversity bonus: reward unique species combinations (BOOSTED)
        unique_families = len(set(p.species_id for p in genome.pets))
        score += unique_families * 10  # Was 2, now 10 for better differentiation
        
        # Type Advantage Bonus: Prefer pets with type advantage, avoid disadvantage
        # WoW Pet Battle type effectiveness: Strong = 1.5x damage, Weak = 0.67x damage
        type_advantage_bonus = self._calculate_type_matchup_bonus(player_team, self.target_team)
        score += type_advantage_bonus
        
        # Add tiny random noise to break ties
        import random
        score += random.uniform(0, 0.5)
        
        # Store detailed stats for UI
        genome.stats = {
            "win_rate": win_rate,
            "avg_damage_pct": avg_damage_pct,
            "avg_turns": avg_turns,
            "avg_survival": avg_survival
        }
        
        return max(0, score)

    def _genome_to_team(self, genome: TeamGenome) -> Team:
        """Convert DNA to actual Team object with REAL individual pet stats"""
        pets = []
        for gene in genome.pets:
            # Use REAL stats from user's collection (breed matters!)
            if hasattr(self, 'real_pet_stats') and gene.species_id in self.real_pet_stats:
                species_stats = self.real_pet_stats[gene.species_id]
                stats = PetStats(
                    max_hp=species_stats['health'],
                    current_hp=species_stats['health'],
                    power=species_stats['power'],
                    speed=species_stats['speed']
                )
            else:
                # Fallback to level 25 rare baseline
                stats = PetStats(
                    max_hp=1400,
                    current_hp=1400,
                    power=280,
                    speed=280
                )
            
            abilities = []
            for i, ab_id in enumerate(gene.abilities):
                # Check if we have real ability data (monkey-patched from app.py)
                if hasattr(self, 'real_abilities') and str(ab_id) in self.real_abilities:
                    info = self.real_abilities[str(ab_id)]
                    
                    # Map API family ID to Enum
                    fam_map = {
                        0: PetFamily.HUMANOID, 1: PetFamily.DRAGONKIN, 2: PetFamily.FLYING,
                        3: PetFamily.UNDEAD, 4: PetFamily.CRITTER, 5: PetFamily.MAGIC,
                        6: PetFamily.ELEMENTAL, 7: PetFamily.BEAST, 8: PetFamily.AQUATIC,
                        9: PetFamily.MECHANICAL
                    }
                    fam = fam_map.get(info.get('family_id', 0), PetFamily.BEAST)
                    
                    # Use real parsed stats from Blizzard API
                    abilities.append(Ability(
                        id=int(info['id']),
                        name=info['name'],
                        power=info.get('power', 20),  # Real power value from API parse
                        accuracy=info.get('accuracy', 100),  # Real accuracy from API parse
                        speed=info.get('speed', 0),  # Real speed modifier from API parse
                        cooldown=info.get('cooldown', 0),
                        family=fam,
                        stat_buffs=info.get('stat_buffs', {})
                    ))
                else:
                    # Fallback to mock
                    abilities.append(Ability(
                        id=ab_id, 
                        name=f"Ability {ab_id}", 
                        power=20, 
                        accuracy=100, 
                        speed=0, 
                        cooldown=0, 
                        family=PetFamily.BEAST
                    ))
                
            # Determine pet family from species_db
            pet_family = PetFamily.BEAST  # Default
            if gene.species_id in self.species_db:
                family_id = self.species_db[gene.species_id].get('family_id', 7)
                # Map family_id to PetFamily enum
                family_map = {
                    0: PetFamily.HUMANOID,
                    1: PetFamily.DRAGONKIN,
                    2: PetFamily.FLYING,
                    3: PetFamily.UNDEAD,
                    4: PetFamily.CRITTER,
                    5: PetFamily.MAGIC,
                    6: PetFamily.ELEMENTAL,
                    7: PetFamily.BEAST,
                    8: PetFamily.AQUATIC,
                    9: PetFamily.MECHANICAL
                }
                pet_family = family_map.get(family_id, PetFamily.BEAST)
                
            pets.append(Pet(
                species_id=gene.species_id,
                name=f"Pet {gene.species_id}",
                family=pet_family,  # Now using correct family from species_db
                quality=PetQuality.RARE,  # Add missing quality parameter
                stats=stats,
                abilities=abilities
            ))
            
        return Team(pets=pets)
    
    def _calculate_type_matchup_bonus(self, player_team: Team, enemy_team: Team) -> float:
        """
        Calculate type advantage bonus based on team composition vs enemy types.
        Returns positive bonus for advantages, negative for disadvantages.
        
        WoW Pet Battle Type Chart (Strong against):
        - Humanoid > Dragonkin, Undead
        - Dragonkin > Magic, Flying
        - Flying > Aquatic, Critter
        - Undead > Humanoid, Critter
        - Critter > Undead
        - Magic > Flying, Mechanical
        - Elemental > Mechanical, Critter
        - Beast > Critter, Mechanical
        - Aquatic > Elemental, Undead
        - Mechanical > Beast, Elemental
        """
        # Type effectiveness matrix: key attacks value
        strong_against = {
            PetFamily.HUMANOID: {PetFamily.DRAGONKIN, PetFamily.UNDEAD},
            PetFamily.DRAGONKIN: {PetFamily.MAGIC, PetFamily.FLYING},
            PetFamily.FLYING: {PetFamily.AQUATIC, PetFamily.CRITTER},
            PetFamily.UNDEAD: {PetFamily.HUMANOID, PetFamily.CRITTER},
            PetFamily.CRITTER: {PetFamily.UNDEAD},
            PetFamily.MAGIC: {PetFamily.FLYING, PetFamily.MECHANICAL},
            PetFamily.ELEMENTAL: {PetFamily.MECHANICAL, PetFamily.CRITTER},
            PetFamily.BEAST: {PetFamily.CRITTER, PetFamily.MECHANICAL},
            PetFamily.AQUATIC: {PetFamily.ELEMENTAL, PetFamily.UNDEAD},
            PetFamily.MECHANICAL: {PetFamily.BEAST, PetFamily.ELEMENTAL}
        }
        
        bonus = 0
        
       # Count advantages and disadvantages
        for player_pet in player_team.pets:
            player_family = player_pet.family
            
            for enemy_pet in enemy_team.pets:
                enemy_family = enemy_pet.family
                
                # Check if player pet has advantage
                if player_family in strong_against:
                    if enemy_family in strong_against[player_family]:
                        bonus += 50  # Reward type advantage
                
                # Check if player pet has disadvantage (enemy strong against player)
                if enemy_family in strong_against:
                    if player_family in strong_against[enemy_family]:
                        bonus -= 30  # Penalize type disadvantage
        
        return bonus
