import multiprocessing
import json
import time
import argparse
import os
from typing import List, Dict, Any
from tqdm import tqdm

# Import core simulator components
from simulator.simulator import BattleSimulator
from simulator.battle_state import BattleState, Team, Pet, PetStats, PetFamily, PetQuality, Ability
from simulator.npc_ai import create_npc_agent
from genetic.fitness import FitnessEvaluator
from genetic.evolution import EvolutionEngine
from simulator.strategy_manager import StrategyManager

def load_data():
    """Load necessary data for simulation"""
    try:
        with open('encounters.json', 'r') as f:
            encounters = json.load(f)
        
        with open('abilities.json', 'r') as f:
            abilities = json.load(f)
            
        # Load manual overrides
        if os.path.exists('ability_stats_manual.json'):
            with open('ability_stats_manual.json', 'r') as f:
                manual_stats = json.load(f)
                for aid, data in manual_stats.items():
                    abilities[aid] = data
        
        species_data = {}
        if os.path.exists('species_data.json'):
            with open('species_data.json', 'r') as f:
                species_raw = json.load(f)
                species_data = {int(k): v for k, v in species_raw.items()}
                
        # Load my pets
        my_pets = []
        if os.path.exists('my_pets.json'):
            with open('my_pets.json', 'r') as f:
                my_pets = json.load(f)
                
        return encounters, abilities, species_data, my_pets
    except Exception as e:
        print(f"Error loading data: {e}")
        return {}, {}, {}, []

def solve_encounter_worker(args):
    """Worker function to solve a single encounter"""
    encounter_key, encounter_data, abilities, species_data, my_pets, config = args
    
    try:
        target_name = encounter_data.get('name', encounter_key)
        
        # 1. Setup Target Team
        npc_pets_data = encounter_data.get('pets') or encounter_data.get('npc_pets')
        if not npc_pets_data:
            return {'key': encounter_key, 'status': 'SKIPPED', 'reason': 'No pet data'}
            
        target_pets = []
        for p_data in npc_pets_data:
            # Construct pet object (simplified for brevity, similar to app.py)
            p_abilities = []
            for ab in p_data.get('abilities', []):
                try:
                    if isinstance(ab, int):
                        ab_info = abilities.get(str(ab)) or abilities.get(ab)
                        if ab_info and isinstance(ab_info, dict):
                            fam_val = ab_info.get('family_id', 7)
                            try: fam = PetFamily(fam_val)
                            except: fam = PetFamily.BEAST
                            p_abilities.append(Ability(
                                id=ab, name=ab_info.get('name', 'Unknown'), 
                                power=ab_info.get('power', 20), accuracy=ab_info.get('accuracy', 100), 
                                speed=ab_info.get('speed', 0), cooldown=ab_info.get('cooldown', 0), 
                                family=fam
                            ))
                        else:
                            # Handle case where ab_info is missing or not a dict (e.g. list from old format)
                            p_abilities.append(Ability(id=ab, name=f"Ability {ab}", power=20, accuracy=100, speed=0, cooldown=0, family=PetFamily.BEAST))
                    elif isinstance(ab, dict):
                         # Already a dict object
                         p_abilities.append(Ability(
                            id=ab.get('id', 0), name=ab.get('name', 'Unknown'),
                            power=ab.get('power', 20), accuracy=ab.get('accuracy', 100),
                            speed=ab.get('speed', 0), cooldown=ab.get('cooldown', 0),
                            family=PetFamily.BEAST # Simplified
                         ))
                    else:
                        # Fallback for unknown types (e.g. strings)
                        p_abilities.append(Ability(id=0, name=f"Unknown {ab}", power=20, accuracy=100, speed=0, cooldown=0, family=PetFamily.BEAST))
                except Exception as e:
                    print(f"Error processing ability {ab}: {e}")
                    p_abilities.append(Ability(id=0, name="Error Ability", power=20, accuracy=100, speed=0, cooldown=0, family=PetFamily.BEAST))
            
            stats_data = p_data.get('stats', {'health': 1000, 'power': 200, 'speed': 200})
            stats = PetStats(
                max_hp=stats_data.get('health', 1000), current_hp=stats_data.get('health', 1000),
                power=stats_data.get('power', 200), speed=stats_data.get('speed', 200)
            )
            
            fam_str = p_data.get('family', 'Beast').upper()
            try: fam = PetFamily[fam_str]
            except: fam = PetFamily.BEAST
            
            target_pets.append(Pet(
                species_id=p_data.get('species_id', 0), name=p_data.get('name', 'Unknown'),
                family=fam, quality=PetQuality.RARE, stats=stats, abilities=p_abilities
            ))
            
        target_team = Team(pets=target_pets)
        
        # 2. Setup Evaluator & Engine
        evaluator = FitnessEvaluator(
            target_team=target_team,
            ability_db=abilities,
            species_db=species_data,
            target_name=target_name
        )
        
        # Inject real stats if available (simplified)
        # In a full implementation, we'd pass this in properly
        
        strategy_manager = StrategyManager(strategies_path='strategies_master.json')
        
        engine = EvolutionEngine(
            fitness_evaluator=evaluator,
            population_size=config['pop_size'],
            mutation_rate=0.5,
            elitism_rate=0.1
        )
        
        # 3. Initialize Population
        # Filter available species based on my_pets if needed
        available_species = list(species_data.keys())
        if config['my_pets_only'] and my_pets:
             # my_pets is the raw JSON from Blizzard API
             # Structure: {'pets': [{'species': {'id': 123}, ...}, ...]}
             pets_list = my_pets.get('pets', []) if isinstance(my_pets, dict) else my_pets
             
             my_species_ids = set()
             for p in pets_list:
                 if isinstance(p, dict):
                     # Try nested species.id first (Blizzard API)
                     if 'species' in p and 'id' in p['species']:
                         my_species_ids.add(int(p['species']['id']))
                     # Fallback to direct speciesId (PetTracker/Simple format)
                     elif 'speciesId' in p:
                         my_species_ids.add(int(p['speciesId']))
             
             if my_species_ids:
                available_species = [sid for sid in available_species if sid in my_species_ids]
        
        # Seeding
        seed_teams = []
        try:
            rec = strategy_manager.get_recommended_team(target_name)
            if rec: seed_teams.append(rec)
        except: pass
        
        engine.initialize_population(
            available_species, abilities, 
            npc_name=target_name, strategy_manager=strategy_manager
        )
        
        # Manually inject seeds if any
        if seed_teams:
            # Convert seed team IDs to Genome
            for seed_ids in seed_teams:
                try:
                    # seed_ids is [id1, id2, id3]
                    from genetic.genome import TeamGenome
                    seed_genome = TeamGenome.from_team_ids(seed_ids, abilities)
                    # Replace a random genome in population with seed
                    if engine.population:
                        engine.population[0] = seed_genome # Put seed in front
                except Exception as e:
                    print(f"Error injecting seed {seed_ids}: {e}")
        
        # 4. Evolve
        best_fitness = 0
        best_genome = None
        
        for gen in range(config['generations']):
            stats = engine.evolve_generation(available_species)
            if stats['best_fitness'] > best_fitness:
                best_fitness = stats['best_fitness']
                best_genome = stats['top_genomes'][0]
                
            # Early exit if good enough
            if best_fitness > 50000: # Win threshold
                break
                
        # 5. Result
        if best_genome:
            team_str = f"team:{','.join(str(p.species_id) for p in best_genome.pets)}"
            return {
                'key': encounter_key,
                'name': target_name,
                'status': 'SOLVED' if best_fitness > 10000 else 'FAILED', # Arbitrary threshold
                'fitness': best_fitness,
                'team_string': team_str,
                'generations': gen + 1
            }
        else:
            return {'key': encounter_key, 'name': target_name, 'status': 'FAILED', 'reason': 'No genome found'}

    except Exception as e:
        import traceback
        return {'key': encounter_key, 'name': encounter_data.get('name', encounter_key), 'status': 'ERROR', 'reason': f"{str(e)}\n{traceback.format_exc()}"}

def run_batch(filter_str=None, pop_size=20, generations=10, processes=4, my_pets_only=True):
    print(f"🚀 Starting Batch Solver (Processes: {processes})")
    
    encounters, abilities, species_data, my_pets = load_data()
    
    # Filter encounters
    tasks = []
    for key, data in encounters.items():
        if filter_str and filter_str.lower() not in key.lower() and filter_str.lower() not in data.get('name', '').lower():
            continue
        
        config = {
            'pop_size': pop_size,
            'generations': generations,
            'my_pets_only': my_pets_only
        }
        tasks.append((key, data, abilities, species_data, my_pets, config))
        
    print(f"📋 Found {len(tasks)} encounters to solve.")
    
    results = []
    with multiprocessing.Pool(processes=processes) as pool:
        for result in tqdm(pool.imap_unordered(solve_encounter_worker, tasks), total=len(tasks)):
            results.append(result)
            
    # Save results
    with open('batch_results.json', 'w') as f:
        json.dump(results, f, indent=2)
        
    # Summary
    solved = sum(1 for r in results if r['status'] == 'SOLVED')
    print(f"\n✅ Batch Complete!")
    print(f"Solved: {solved}/{len(tasks)}")
    print(f"Results saved to batch_results.json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='PetWeaver Batch Solver')
    parser.add_argument('--filter', type=str, help='Filter encounters by name (e.g., "Pandaria")')
    parser.add_argument('--pop', type=int, default=20, help='Population size')
    parser.add_argument('--gen', type=int, default=10, help='Generations')
    parser.add_argument('--cores', type=int, default=multiprocessing.cpu_count(), help='Number of processes')
    parser.add_argument('--all-pets', action='store_true', help='Use all pets (ignore my_pets.json)')
    
    args = parser.parse_args()
    
    run_batch(
        filter_str=args.filter,
        pop_size=args.pop,
        generations=args.gen,
        processes=args.cores,
        my_pets_only=not args.all_pets
    )
