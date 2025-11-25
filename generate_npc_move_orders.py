# generate_npc_move_orders.py
"""
Generate a markdown file that lists, for each NPC (tamer), the *deterministic* sequence of
abilities each of its pets will use across rounds.  The ordering follows the same
priority rules used elsewhere (Swap > Priority > Speed > Coin‑flip).  Because we
don't model cooldowns or dynamic buffs here, we simply sort the abilities once
and then cycle through that list round‑by‑round.

Output: `npc_move_orders.md`

Structure per NPC:
```
## <NPC Name> (ID <id>)
| Round | Pet (Species ID) | Ability |
|------|------------------|--------|
| 1    | Pet 1234         | Bite   |
| 2    | Pet 1234         | Hiss   |
| …    | …                | …      |
```
The script repeats the sorted ability list if the number of rounds exceeds the
ability count (so a pet with 3 abilities will show the same three abilities
repeating).  This provides a static move order that the simulator can consume
when running NPC‑only battles.
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ENC_PATH = PROJECT_ROOT / "encounters_full.json"
OUTPUT_MD = PROJECT_ROOT / "npc_move_orders.md"

# Number of rounds to display – can be adjusted as needed.
MAX_ROUNDS = 12

def load_encounters():
    with open(ENC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def effective_speed(pet, ability):
    # Approximate speed: pet's own speed field (often 0) + ability.speed.
    base = pet.get("speed", 0)
    return base + ability.get("speed", 0)

def sort_abilities(pet):
    abilities = pet.get("abilities", [])
    def key(ab):
        prio = ab.get("priority", 0)
        if ab.get("name", "").lower() == "swap":
            prio = 9999
        spd = effective_speed(pet, ab)
        return (-prio, -spd)
    return sorted(abilities, key=key)

def generate_markdown(encounters):
    lines = ["# NPC Move‑Order Tables (Static)\n\n"]
    for npc in encounters:
        name = npc.get("name", "Unknown")
        npc_id = npc.get("npc_id")
        lines.append(f"## {name} (ID {npc_id})\n")
        lines.append("| Round | Pet (Species ID) | Ability |\n|------|------------------|--------|\n")
        for pet in npc.get("pets", []):
            species_id = pet.get("species_id")
            pet_label = f"Pet {species_id}"
            sorted_abs = sort_abilities(pet)
            if not sorted_abs:
                continue
            for rnd in range(1, MAX_ROUNDS + 1):
                ability = sorted_abs[(rnd - 1) % len(sorted_abs)]
                ability_name = ability.get("name", "?")
                lines.append(f"| {rnd} | {pet_label} | {ability_name} |\n")
        lines.append("\n")
    return "".join(lines)

def main():
    encounters = load_encounters()
    md = generate_markdown(encounters)
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"✅ Generated {OUTPUT_MD} with move orders for {len(encounters)} NPCs (up to {MAX_ROUNDS} rounds each).")

if __name__ == "__main__":
    main()
