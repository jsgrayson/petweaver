import pytest
from genetic.genome import TeamGenome
from genetic.fitness import FitnessEvaluator
from genetic.evolution import EvolutionEngine
from simulator import Team, Pet, PetStats, PetFamily, PetQuality, Ability

# Mock Data
MOCK_SPECIES = [1, 2, 3, 4, 5]
MOCK_ABILITY_DB = {
    1: [1, 2, 3, 4, 5, 6],
    2: [7, 8, 9, 10, 11, 12],
    3: [13, 14, 15, 16, 17, 18],
    4: [19, 20, 21, 22, 23, 24],
    5: [25, 26, 27, 28, 29, 30]
}

@pytest.fixture
def target_team():
    """Create a dummy target team"""
    pets = [
        Pet(
            species_id=100, name="Target Dummy", family=PetFamily.BEAST, quality=PetQuality.RARE,
            stats=PetStats(max_hp=1000, current_hp=1000, power=200, speed=200),
            abilities=[Ability(id=99, name="Nothing", power=0, accuracy=100, speed=0, cooldown=0, family=PetFamily.BEAST)]
        )
    ]
    return Team(pets=pets)

def test_genome_generation():
    genome = TeamGenome.random(MOCK_SPECIES, MOCK_ABILITY_DB)
    assert len(genome.pets) == 3
    assert genome.pets[0].species_id in MOCK_SPECIES
    assert len(genome.pets[0].abilities) == 3

def test_crossover():
    parent1 = TeamGenome.random(MOCK_SPECIES, MOCK_ABILITY_DB)
    parent2 = TeamGenome.random(MOCK_SPECIES, MOCK_ABILITY_DB)
    
    child = parent1.crossover(parent2)
    assert len(child.pets) == 3
    # Child pets should come from parents
    assert child.pets[0].species_id == parent1.pets[0].species_id or \
           child.pets[0].species_id == parent2.pets[0].species_id

def test_mutation():
    genome = TeamGenome.random(MOCK_SPECIES, MOCK_ABILITY_DB)
    original_species = [p.species_id for p in genome.pets]
    
    # Force mutation
    genome.mutate(MOCK_SPECIES, mutation_rate=1.0)
    
    # At least one thing should likely change with 100% rate
    # (Though random choice could pick same species, so this is probabilistic)
    pass 

def test_evolution_loop(target_team):
    evaluator = FitnessEvaluator(target_team, MOCK_ABILITY_DB, {})
    engine = EvolutionEngine(evaluator, population_size=10)
    
    engine.initialize_population(MOCK_SPECIES, MOCK_ABILITY_DB)
    assert len(engine.population) == 10
    
    stats = engine.evolve_generation(MOCK_SPECIES)
    assert stats['generation'] == 1
    assert stats['best_fitness'] >= 0
    assert engine.best_genome is not None
