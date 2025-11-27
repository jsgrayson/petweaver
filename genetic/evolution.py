import random
import copy
from typing import List, Dict, Callable, Optional
from .genome import TeamGenome, PetGene, StrategyGene
from .fitness import FitnessEvaluator

try:
    from simulator import PetFamily
except ImportError:
    class PetFamily:
        HUMANOID=0; DRAGONKIN=1; FLYING=2; UNDEAD=3; CRITTER=4
        MAGIC=5; ELEMENTAL=6; BEAST=7; AQUATIC=8; MECHANICAL=9

class EvolutionEngine:
    def __init__(
        self, 
        fitness_evaluator: FitnessEvaluator,
        population_size: int = 50,
        mutation_rate: float = 0.3,
        elitism_rate: float = 0.2
    ):
        self.evaluator = fitness_evaluator
        self.pop_size = population_size
        self.mutation_rate = mutation_rate
        self.elitism_count = int(population_size * elitism_rate)
        self.population: List[TeamGenome] = []
        self.generation = 0
        self.best_genome: TeamGenome = None
        self.stagnation_counter = 0
        self.last_best_fitness = 0.0
        self.locked_slots = [False, False, False]
        self.slot_pools = [[], [], []]

    def get_type_effectiveness(self, attack_family, defend_family):
        strong_against = {
            0: {1, 3}, 1: {5, 2}, 2: {8, 4}, 3: {0, 4}, 4: {3},
            5: {2, 9}, 6: {9, 4}, 7: {4, 9}, 8: {6, 3}, 9: {7, 6}
        }
        if hasattr(attack_family, 'value'): attack_family = attack_family.value
        if hasattr(defend_family, 'value'): defend_family = defend_family.value
        if defend_family in strong_against.get(attack_family, {}): return 1.5
        return 1.0

    def build_slot_pools(self, available_species, ability_db):
        enemy_team = getattr(self.evaluator, 'target_team', None)
        species_db = getattr(self.evaluator, 'species_db', {})
        ability_info_db = getattr(self.evaluator, 'ability_db', {})
        
        if not enemy_team: return
        self.slot_pools = [[], [], []]
        print("    [AI] Building optimized counter pools...")
        
        for i, enemy_pet in enumerate(enemy_team.pets):
            counters = []
            candidates = available_species if len(available_species) < 2000 else random.sample(available_species, 2000)
            for sid in candidates:
                score = 0
                my_ability_ids = ability_db.get(sid, [])
                if not my_ability_ids: continue

                # 1. Strong Attack
                for aid in my_ability_ids:
                    ainfo = ability_info_db.get(str(aid)) or ability_info_db.get(aid)
                    if ainfo and isinstance(ainfo, dict):
                        atk_type = ainfo.get('family_id', 7)
                        if self.get_type_effectiveness(atk_type, enemy_pet.family) > 1.0:
                            score += 10; break
                
                # 2. Resist
                s_data = species_db.get(str(sid)) or species_db.get(sid)
                if s_data:
                    if isinstance(s_data, list):
                        print(f"DEBUG CRASH: s_id={sid}, type={type(s_data)}, content={s_data}")
                    
                    my_fam = s_data.get('family_id', 7)
                    if self.get_type_effectiveness(enemy_pet.family, my_fam) < 1.0: score += 5

                if score >= 10: counters.append(sid)
            
            if not counters: counters = available_species 
            self.slot_pools[i] = counters
            print(f"    [AI] Slot {i+1} Pool: {len(counters)} counters.")

    def initialize_population(self, available_species, ability_db, npc_name=None, strategy_manager=None, capture_mode=False, seed_teams=None, strategy_file=None):
        self.ability_db = ability_db
        self.population = []
        self.build_slot_pools(available_species, ability_db)
        self.locked_slots = [False, False, False]
        
        # 1. Load strategies from file if provided
        loaded_seeds = []
        if strategy_file:
            try:
                import json
                with open(strategy_file) as f:
                    strategies_data = json.load(f)
                
                # Find strategies for this specific NPC
                for enc_id, enc_data in strategies_data.items():
                    if npc_name and npc_name.lower() in enc_data.get('name', '').lower():
                        print(f"    [AI] Found {len(enc_data.get('strategies', []))} strategies for {npc_name}")
                        for strategy in enc_data.get('strategies', []):
                            team_ids = [p['species_id'] for p in strategy['pets'] if p['species_id'] > 0]
                            if len(team_ids) == 3:
                                loaded_seeds.append(team_ids)
                        break
            except Exception as e:
                print(f"    [!] Could not load strategy file: {e}")
        
        # Combine manual seeds with loaded seeds
        all_seeds = (seed_teams or []) + loaded_seeds
        
        # 2. Inject Seeds (if available)
        if all_seeds:
            print(f"    [AI] Seeding population with {len(all_seeds)} known strategies...")
            for seed in all_seeds:
                # seed is expected to be a list of species_ids [id1, id2, id3]
                try:
                    genome = TeamGenome.from_team_ids(seed, ability_db)
                    # Evaluate immediately to see if they are good
                    genome.fitness = self.evaluator.evaluate(genome)
                    self.population.append(genome)
                except Exception as e:
                    print(f"    [!] Failed to inject seed {seed}: {e}")

        # 3. Fill remaining with Smart Draft
        while len(self.population) < self.pop_size:
            p1 = random.choice(self.slot_pools[0])
            p2 = random.choice(available_species)
            p3 = random.choice(available_species)
            genome = TeamGenome.from_team_ids([p1, p2, p3], ability_db)
            self.population.append(genome)
            
        self.generation = 0

    def evolve_generation(self, available_species: List[int]):
        # 1. Evaluate
        for genome in self.population:
            if genome.fitness == 0:
                genome.fitness = self.evaluator.evaluate(genome)
        
        self.population.sort(key=lambda g: g.fitness, reverse=True)
        current_best = self.population[0].fitness
        
        if not self.best_genome or current_best > self.best_genome.fitness:
            self.best_genome = copy.deepcopy(self.population[0])
            self.stagnation_counter = 0
        else:
            self.stagnation_counter += 1

        # 2. Update Locks
        status = getattr(self.best_genome, 'win_status', "LLL")
        while len(status) < 3: status += "L"
        
        if status[0] == "W": self.locked_slots[0] = True
        if status[1] == "W" and self.locked_slots[0]: self.locked_slots[1] = True
        if status[2] == "W" and self.locked_slots[1]: self.locked_slots[2] = True
        
        # Identify Active Slot
        active_slot = 3 # Default to "Optimization Mode" (All Locked)
        for i, locked in enumerate(self.locked_slots):
            if not locked:
                active_slot = i
                break

        # 3. Reproduction (Alien Injection)
        new_pop = []
        new_pop.append(copy.deepcopy(self.best_genome)) # Elitism (Keep #1)
        
        # Dynamic Alien Rate: Base 10%, +5% per stagnant generation (Max 80%)
        alien_rate = 0.10 + (self.stagnation_counter * 0.05)
        if alien_rate > 0.8: alien_rate = 0.8
        
        pool = self.slot_pools[active_slot] if active_slot < 3 else available_species
        
        while len(new_pop) < self.pop_size:
            # ALIEN INJECTION: Introduce fresh blood to break local optima
            if random.random() < alien_rate:
                # Create a completely new random team using SMART POOLS
                # Use the specific counter pools for each slot to ensure higher quality
                p1 = random.choice(self.slot_pools[0])
                p2 = random.choice(self.slot_pools[1]) if self.slot_pools[1] else random.choice(available_species)
                p3 = random.choice(self.slot_pools[2]) if self.slot_pools[2] else random.choice(available_species)
                
                alien = TeamGenome.from_team_ids([p1, p2, p3], self.ability_db)
                alien.fitness = 0
                new_pop.append(alien)
                continue

            # Clone Best Genome (Stability)
            child = copy.deepcopy(self.best_genome)
            
            # MUTATE ONLY ACTIVE SLOT
            target_slot = active_slot
            
            # OPTIMIZATION MODE: If all slots locked (WWW), pick random slot to optimize
            if active_slot == 3:
                target_slot = random.randint(0, 2)
                pool = self.slot_pools[target_slot]

            if target_slot < 3:
                # Force mutation on the target problem
                new_id = random.choice(pool)
                
                possible_abs = self.ability_db.get(new_id, [])
                selected_abs = []
                if possible_abs:
                    if isinstance(possible_abs, list):
                        selected_abs = possible_abs[:3] if len(possible_abs)>=3 else possible_abs
                
                child.pets[target_slot] = PetGene(
                    species_id=new_id, 
                    abilities=selected_abs, 
                    strategy=StrategyGene()
                )
            
            child.fitness = 0
            new_pop.append(child)
            
        # FITNESS DECAY: If stuck for 20+ gens, decay the best genome's fitness
        # This forces it to eventually be dethroned by a fresh candidate ("Cycling")
        if self.stagnation_counter > 20:
            self.best_genome.fitness *= 0.95
            
        avg_fitness = sum(g.fitness for g in self.population) / self.pop_size
        self.population = new_pop
        self.generation += 1
        
        return {
            "generation": self.generation,
            "best_fitness": self.best_genome.fitness,
            "win_status": status,
            "avg_fitness": avg_fitness,
            "top_genomes": self.population[:3]
        }

    def _tournament_select(self, k=3):
        contestants = random.sample(self.population, k)
        return max(contestants, key=lambda g: g.fitness)