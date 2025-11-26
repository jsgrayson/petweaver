# Move Order Generation Issues

## Problem Summary
The "Black Claw spam" bug exists in the enhanced AI move orders because `regenerate_move_orders.py` doesn't properly handle cooldowns when generating move sequences from AI scripts.

## Root Cause

###encounters.json Data Issue
- **All pets have empty `abilities: []` arrays**
- Species IDs in encounters.json: 1, 872, 873, 890...
- Species IDs in abilities.json: 2051, 2062, 2446...
- **The databases are completely incompatible**

### Failed Approaches

1. **`generate_final_npc_move_orders.py`**
   - Tries to load abilities from encounters.json
   - encounters.json has no abilities  
   - Result: Generates 153 NPCs with 0 moves each

2. **`fix_encounters.py`** (hydration attempt)
   - Tries to map species IDs from abilities.json
   - Species IDs don't match between files
   - Result: 0 pets hydrated successfully

3. **`regenerate_move_orders.py`** (current enhanced AI)
   - Generates moves from enhanced AI scripts
   - **Bug:** Doesn't track cooldowns properly
   - Result: Black Claw spam (uses same move every turn)

## Current Status

**Working File:** `npc_move_orders_enhanced.json` (123 encounters)
**Issue:** Has cooldown bugs (spam issue)
**Why We Use It:** Only data source available

## The Real Solution Needed

To fix the Black Claw spam in `regenerate_move_orders.py`:

1. Load `enhanced_enemy_npc_scripts.json` for AI logic
2. Load `abilities.json` to get cooldown data for each ability ID
3. When simulating moves, track cooldowns properly:
   - After using ability with CD=3, mark it unavailable for 3 turns
   - Only allow abilities with CD=0 currently
   - Use filler move (CD=0) when everything on cooldown

## Why encounters.json Can't Be Fixed

- Empty abilities arrays
- Incompatible species ID mappings  
- No way to hydrate without correct species-to-abilities database
- Different data sources (game data vs community data)

## Recommendation

**Accept the enhanced AI data as-is** or **fix `regenerate_move_orders.py`** to properly track cooldowns when generating from AI scripts.

Don't try to fix encounters.json - it's fundamentally incompatible with abilities.json.
