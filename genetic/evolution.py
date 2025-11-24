import random
from typing import List, Dict, Callable
from .genome import TeamGenome, PetGene, StrategyGene
from .fitness import FitnessEvaluator

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

    def initialize_population(self, available_species: List[int], ability_db: Dict):
        """Create initial random population"""
        self.ability_db = ability_db  # Store for mutation
        self.population = [
            TeamGenome.random(available_species, ability_db) 
            for _ in range(self.pop_size)
        ]
        self.generation = 0

    def evolve_generation(self, available_species: List[int]):
        """Run one generation of evolution"""
        # 1. Evaluate Fitness
        for genome in self.population:
            if genome.fitness == 0: # Only evaluate if not already cached
                genome.fitness = self.evaluator.evaluate(genome)
        
        # Sort by fitness (descending)
        self.population.sort(key=lambda g: g.fitness, reverse=True)
        
        # Track best
        if not self.best_genome or self.population[0].fitness > self.best_genome.fitness:
            self.best_genome = self.population[0]
            
        # NEW: Identify best individual pet across ALL teams
        pet_fitness_map = {}  # species_id -> total fitness contribution
        for genome in self.population[:10]:  # Check top 10 teams
            for pet in genome.pets:
                if pet.species_id not in pet_fitness_map:
                    pet_fitness_map[pet.species_id] = []
                pet_fitness_map[pet.species_id].append(genome.fitness)
        
        # Average fitness for each species
        avg_fitness_by_species = {sid: sum(fits)/len(fits) for sid, fits in pet_fitness_map.items()}
        best_pet_species = max(avg_fitness_by_species, key=avg_fitness_by_species.get) if avg_fitness_by_species else None
            
        # 2. Selection (Elitism)
        new_pop = self.population[:self.elitism_count]
        
        # 3. Reproduction
        while len(new_pop) < self.pop_size:
            # Tournament Selection
            parent1 = self._tournament_select()
            parent2 = self._tournament_select()
            
            # Crossover
            child = parent1.crossover(parent2)
            
            # NEW: Inject best pet into child (replace worst pet)
            if best_pet_species and random.random() < 0.4:  # 40% chance
                # Find if best pet already in team
                has_best_pet = any(p.species_id == best_pet_species for p in child.pets)
                if not has_best_pet and len(child.pets) == 3:
                    # Replace a random pet with the best pet
                    replace_idx = random.randint(0, 2)
                    
                    # Get valid abilities for this species
                    possible_abilities = self.ability_db.get(best_pet_species, [1, 2, 3, 4, 5, 6])
                    valid_abilities = TeamGenome._select_valid_abilities(possible_abilities)
                    
                    child.pets[replace_idx] = PetGene(
                        species_id=best_pet_species,
                        abilities=valid_abilities,
                        strategy=StrategyGene()
                    )
                    child.fitness = 0  # Force re-evaluation
            
            # Mutation
            # We need ability_db here, but it wasn't stored in __init__
            # We'll assume it was passed to initialize_population and stored
            if hasattr(self, 'ability_db'):
                child.mutate(available_species, self.ability_db, self.mutation_rate)
            else:
                # Fallback if DB missing (shouldn't happen if initialized correctly)
                # We'll just pass an empty dict which will trigger defaults in mutate
                child.mutate(available_species, {}, self.mutation_rate)
            
            new_pop.append(child)
            
        # Capture stats of the EVALUATED population (before replacement)
        best_genome = self.population[0]
        avg_fitness = sum(g.fitness for g in self.population) / self.pop_size
        top_genomes = self.population[:3] # Top 3 for UI
        
        self.population = new_pop
        self.generation += 1
        
        return {
            "generation": self.generation,
            "best_fitness": best_genome.fitness,
            "avg_fitness": avg_fitness,
            "best_pet": best_pet_species,
            "top_genomes": top_genomes
        }

    def _tournament_select(self, k: int = 3) -> TeamGenome:
        """Select best parent from k random individuals"""
        contestants = random.sample(self.population, k)
        return max(contestants, key=lambda g: g.fitness)
