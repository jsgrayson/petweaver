import json
import time
from genetic.evolution import EvolutionEngine
from genetic.fitness import FitnessEvaluator
from genetic.genome import TeamGenome
from simulator import Team, Pet, Ability, PetFamily, PetQuality, PetStats

# Load data
with open('my_pets.json') as f:
    my_pets = json.load(f)

with open('abilities.json') as f:
    ability_data = json.load(f)

species_abilities = ability_data.get('species_abilities', {})
abilities = ability_data.get('abilities', {})

# Build a dummy target team (use first pet from collection as opponent)
first_pet_entry = my_pets['pets'][0]
first_species_id = first_pet_entry['species']['id']
# Build a simple Team with one pet using its first 3 abilities
pet_abilities_ids = species_abilities.get(str(first_species_id), [])[:3]
pet_abilities = []
fam_map = {
    0: PetFamily.HUMANOID, 1: PetFamily.DRAGONKIN, 2: PetFamily.FLYING,
    3: PetFamily.UNDEAD, 4: PetFamily.CRITTER, 5: PetFamily.MAGIC,
    6: PetFamily.ELEMENTAL, 7: PetFamily.BEAST, 8: PetFamily.AQUATIC,
    9: PetFamily.MECHANICAL
}
for aid in pet_abilities_ids:
    info = abilities.get(str(aid), {})
    fam = fam_map.get(info.get('family_id', 0), PetFamily.BEAST)
    pet_abilities.append(Ability(
        id=int(info['id']),
        name=info['name'],
        power=info.get('power', 20),
        accuracy=info.get('accuracy', 100),
        speed=info.get('speed', 0),
        cooldown=info.get('cooldown', 0),
        family=fam
    ))

stats = PetStats(max_hp=1400, current_hp=1400, power=280, speed=280)
target_pet = Pet(
    species_id=first_species_id,
    name=f"Pet {first_species_id}",
    family=PetFamily.BEAST,
    quality=PetQuality.RARE,
    stats=stats,
    abilities=pet_abilities
)

target_team = Team(pets=[target_pet])

# Prepare evaluator with real ability db (species_abilities mapping) and empty species db (not used yet)
evaluator = FitnessEvaluator(target_team, {int(k): v for k, v in species_abilities.items()}, {})
# Monkey‑patch real abilities for the evaluator (used by fitness)
evaluator.real_abilities = abilities

engine = EvolutionEngine(evaluator, population_size=30)
# Convert species keys to ints for initialization
available_species_ints = [int(k) for k in species_abilities.keys()]
engine.initialize_population(available_species_ints, {int(k): v for k, v in species_abilities.items()})

print("Running 5 generations for a quick test…")
for gen in range(5):
    result = engine.evolve_generation(available_species_ints)
    print(f"Gen {gen+1}: Best fitness = {result['best_fitness']:.2f}, Avg fitness = {result['avg_fitness']:.2f}")
    time.sleep(0.2)

print("Done.")
