import random
import copy
from typing import List
from .genome import TeamGenome, PetGene, StrategyGene
from .fitness import FitnessEvaluator

class EvolutionEngine:
    def __init__(self, fitness_evaluator, population_size=50, mutation_rate=0.3, elitism_rate=0.2):
        self.evaluator = fitness_evaluator
        self.pop_size = population_size
        self.mutation_rate = mutation_rate
        self.elitism_count = int(population_size * elitism_rate)
        self.population = []
        self.generation = 0
        self.best_genome = None
        self.locked_slots = [False, False, False]
        self.slot_pools = [[], [], []]
        self.available_species = []
        self.ability_db = {}

    def get_type_effectiveness(self, attack_family, defend_family):
        strong_against = {
            1: {2, 4}, 2: {6, 3}, 3: {9, 5}, 4: {1, 5}, 5: {4}, 
            6: {3, 10}, 7: {10, 5}, 8: {5, 10}, 9: {7, 4}, 10: {8, 7}
        }
        # Remap values if using Enums or 0-9 scale (User uses 0-9 scale)
        # 0:Humanoid, 1:Dragon, 2:Flying, 3:Undead, 4:Critter, 5:Magic, 6:Elem, 7:Beast, 8:Aquatic, 9:Mech
        # Correct Mapping for 0-9 scale:
        strong_map_09 = {
            0: {1, 3}, 1: {5, 2}, 2: {8, 4}, 3: {0, 4}, 4: {3},
            5: {2, 9}, 6: {9, 4}, 7: {4, 9}, 8: {6, 3}, 9: {7, 6}
        }
        
        att = attack_family.value if hasattr(attack_family, 'value') else attack_family
        defn = defend_family.value if hasattr(defend_family, 'value') else defend_family
        
        if defn in strong_map_09.get(att, {}): return 1.5
        return 1.0

    def build_slot_pools(self, available_species, ability_db):
        """Builds optimized pools for each specific 1v1 fight."""
        enemy_team = getattr(self.evaluator, 'target_team', None)
        species_db = getattr(self.evaluator, 'species_db', {})
        ability_info_db = getattr(self.evaluator, 'ability_db', {})
        
        if not enemy_team: return
        self.slot_pools = [[], [], []]
        
        print("    [AI] Building 1v1 Counter Pools...")
        
        for i, enemy_pet in enumerate(enemy_team.pets):
            counters = []
            candidates = available_species if len(available_species) < 2000 else random.sample(available_species, 2000)
            
            for sid in candidates:
                score = 0
                s_data = species_db.get(str(sid)) or species_db.get(sid)
                my_ability_ids = ability_db.get(sid, [])
                if not my_ability_ids: continue

                # 1. Strong Attack vs This Specific Enemy
                for aid in my_ability_ids:
                    ainfo = ability_info_db.get(str(aid)) or ability_info_db.get(aid)
                    if ainfo and isinstance(ainfo, dict):
                        atk_type = ainfo.get('family_id', 7)
                        if self.get_type_effectiveness(atk_type, enemy_pet.family) > 1.0:
                            score += 10; break
                
                # 2. Resistance vs This Specific Enemy
                if s_data:
                    my_fam = s_data.get('family_id', 7)
                    if self.get_type_effectiveness(enemy_pet.family, my_fam) < 1.0: score += 5

                if score >= 10: counters.append(sid)
            
            if not counters: counters = available_species 
            self.slot_pools[i] = counters
            print(f"    [AI] Fight {i+1} Pool: {len(counters)} candidates.")

    def initialize_population(self, available_species, ability_db, npc_name=None, strategy_manager=None, capture_mode=False):
        self.available_species = available_species
        self.ability_db = ability_db
        self.population = []
        self.build_slot_pools(available_species, ability_db)
        self.locked_slots = [False, False, False]
        
        # Initial Draft: Random picks from the correct pools
        for _ in range(self.pop_size):
            p1 = random.choice(self.slot_pools[0])
            p2 = random.choice(self.slot_pools[1])
            p3 = random.choice(self.slot_pools[2])
            genome = TeamGenome.from_team_ids([p1, p2, p3], ability_db)
            self.population.append(genome)
        self.generation = 0

    def evolve_generation(self, available_species: List[int]):
        # 1. Evaluate
        for genome in self.population:
            if genome.fitness == 0:
                genome.fitness = self.evaluator.evaluate(genome)
        
        self.population.sort(key=lambda g: g.fitness, reverse=True)
        
        # Update Best (Always trust the latest run to catch regressions)
        self.best_genome = copy.deepcopy(self.population[0])
            
        # 2. Check Win Status
        status = getattr(self.best_genome, 'win_status', "LLL")
        while len(status) < 3: status += "L"
        
        # Sequential Locking
        if status[0] == "W": self.locked_slots[0] = True
        if status[1] == "W" and self.locked_slots[0]: self.locked_slots[1] = True
        if status[2] == "W" and self.locked_slots[1]: self.locked_slots[2] = True
        
        # Determine which Fight we are on
        active_slot = 0
        for i, locked in enumerate(self.locked_slots):
            if not locked:
                active_slot = i
                break

        # 3. Reproduction (Focus on the Active Fight)
        new_pop = []
        new_pop.append(copy.deepcopy(self.best_genome))
        
        pool = self.slot_pools[active_slot] if active_slot < 3 else available_species
        
        while len(new_pop) < self.pop_size:
            child = copy.deepcopy(self.best_genome)
            
            # Enforce Locks (Don't change pets that already won)
            for i, is_locked in enumerate(self.locked_slots):
                if is_locked:
                    child.pets[i] = copy.deepcopy(self.best_genome.pets[i])
            
            # Mutate the Active Slot
            if active_slot < 3 and random.random() < self.mutation_rate:
                new_id = random.choice(pool)
                
                possible_abs = self.ability_db.get(new_id, [])
                selected_abs = []
                if possible_abs:
                    if isinstance(possible_abs, list):
                        selected_abs = possible_abs[:3] if len(possible_abs)>=3 else possible_abs
                
                child.pets[active_slot] = PetGene(
                    species_id=new_id, 
                    abilities=selected_abs, 
                    strategy=StrategyGene()
                )
                child.fitness = 0
                
            new_pop.append(child)
            
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
        return random.choice(self.population) # Simplified for slot machine logic