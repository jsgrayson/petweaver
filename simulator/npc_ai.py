from typing import Callable, Optional
from .battle_state import BattleState, TurnAction
from .npc_move_loader import get_move_orders
from .smart_agent import SmartAgent

def create_npc_agent(npc_name: str, default_ai: Optional[Callable[[BattleState], TurnAction]] = None) -> Callable[[BattleState], TurnAction]:
    """
    Creates an AI agent function that prioritizes deterministic move orders.
    
    Args:
        npc_name: The name of the NPC (must match npc_move_orders.md)
        default_ai: The fallback AI function. If None, uses SmartAgent.
        
    Returns:
        A function that takes BattleState and returns a TurnAction.
    """
    move_orders = get_move_orders()
    npc_moves = move_orders.get(npc_name, {})
    
    # Initialize fallback agent if not provided
    if default_ai is None:
        smart_agent = SmartAgent(difficulty=1.0)
        default_ai = smart_agent.decide

    def npc_agent(state: BattleState) -> TurnAction:
        # 1. Identify current context
        enemy_team = state.enemy_team
        active_pet_idx = enemy_team.active_pet_index
        active_pet = enemy_team.get_active_pet()
        
        if not active_pet:
            return TurnAction(actor='enemy', action_type='pass')

        # Round number. Note: BattleState turn_number starts at 1.
        # npc_move_orders.md is 1-based.
        current_round = state.turn_number
        
        # 2. Check for deterministic move
        pet_moves = npc_moves.get(active_pet_idx, {})
        predicted_ability_name = pet_moves.get(current_round)
        
        if predicted_ability_name:
            # 3. Try to find and use the ability
            # We need to find the ability in the pet's ability list by name
            matching_ability = next((ab for ab in active_pet.abilities if ab.name == predicted_ability_name), None)
            
            if matching_ability:
                # Check if usable (cooldown)
                # If the prediction says use it, but it's on cooldown, we have a desync.
                # In that case, we should probably fall back to default AI to avoid crashing/passing.
                if active_pet.can_use_ability(matching_ability):
                    return TurnAction(actor='enemy', action_type='ability', ability=matching_ability)
                else:
                    # print(f"Warning: Deterministic move {predicted_ability_name} for {npc_name} on round {current_round} is on cooldown. Falling back to AI.")
                    pass
            else:
                # print(f"Warning: Deterministic move {predicted_ability_name} not found in pet abilities. Falling back.")
                pass
                
        # 4. Fallback
        return default_ai(state)

    return npc_agent
