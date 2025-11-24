"""
Special Encounter Handler for Pet Battle Simulator

Handles unique gimmick fight mechanics that are specific to certain encounters.
These are NOT racial passives - they are fight-specific mechanics.

Examples:
- Rocko: Immune for 10 rounds, then dies
- Life Exchange: Swap health percentages
- Gore Stacks: Increasing DoT
- Mind Games: 5-round stun + % health damage
"""

from typing import Optional
from .battle_state import Pet, Team, Buff, BuffType, PetFamily


class SpecialEncounterHandler:
    """Handles gimmick fight mechanics"""
    
    # Encounter registry: Maps species IDs to their special mechanics
    SPECIAL_MECHANICS = {
        1811: 'rocko_immunity',  # Rocko species ID
        # Add more as we implement them
    }
    
    @staticmethod
    def has_special_mechanic(pet: Pet) -> Optional[str]:
        """Check if a pet has a special mechanic"""
        return SpecialEncounterHandler.SPECIAL_MECHANICS.get(pet.species_id)
    
    @staticmethod
    def apply_rocko_immunity(pet: Pet, turn: int) -> bool:
        """
        Rocko: Immune to all damage for 10 rounds, then dies automatically
        
        Args:
            pet: Rocko pet
            turn: Current battle turn number
            
        Returns:
            True if Rocko is immune this turn, False otherwise
        """
        if turn <= 10:
            return True  # Immune
        else:
            # Auto-die on turn 11
            pet.stats.current_hp = 0
            return False
    
    @staticmethod
    def apply_gorespine_gore(pet: Pet, turn: int):
        """
        Gorespine: Gore Stacks - Increasing DoT each round
        
        Applies or increases a stacking DoT buff
        """
        # Find existing Gore Stack buff
        gore_buff = None
        for buff in pet.active_buffs:
            if buff.type == BuffType.DOT and buff.source_ability == 99999:  # Special Gore ID
                gore_buff = buff
                break
        
        if gore_buff:
            # Increase stacks
            gore_buff.stacks += 1
            gore_buff.magnitude += 10  # +10 damage per stack
        else:
            # Create new Gore Stack
            gore_buff = Buff(
                type=BuffType.DOT,
                duration=999,  # Permanent (until pet dies)
                magnitude=10,  # 10 damage base
                source_ability=99999,  # Special Gore ID
                stacks=1
            )
            pet.active_buffs.append(gore_buff)
    
    @staticmethod
    def apply_life_exchange(attacker: Pet, defender: Pet):
        """
        Dah'da (Wrathion encounter): Life Exchange - Swap health percentages
        
        Args:
            attacker: Pet casting Life Exchange
            defender: Target pet
        """
        # Calculate current health percentages
        attacker_pct = attacker.stats.current_hp / attacker.stats.max_hp
        defender_pct = defender.stats.current_hp / defender.stats.max_hp
        
        # Swap them
        attacker.stats.current_hp = int(attacker.stats.max_hp * defender_pct)
        defender.stats.current_hp = int(defender.stats.max_hp * attacker_pct)
    
    @staticmethod
    def apply_mind_games(team: Team, active_pet: Pet):
        """
        Mind Games of Addius: Damage entire team for % of current HP + 5-round stun
        
        Args:
            team: Team to damage
            active_pet: Pet to stun
        """
        # Damage all pets for 25% of their current HP
        for pet in team.pets:
            if pet.stats.is_alive():
                damage = int(pet.stats.current_hp * 0.25)
                pet.stats.take_damage(damage)
        
        # Apply 5-round stun to active pet
        stun_buff = Buff(
            type=BuffType.STUN,
            duration=5,
            magnitude=1.0,
            source_ability=88888  # Special Mind Games ID
        )
        active_pet.active_buffs.append(stun_buff)
    
    @staticmethod
    def apply_bone_prison(pet: Pet):
        """
        Jawbone (Bastion): Bone Prison - Stun target
        
        Args:
            pet: Pet to stun
        """
        stun_buff = Buff(
            type=BuffType.STUN,
            duration=2,  # 2 rounds
            magnitude=1.0,
            source_ability=77777  # Special Bone Prison ID
        )
        pet.active_buffs.append(stun_buff)
    
    @staticmethod
    def apply_toxic_skin(attacker: Pet, damage_dealt: int) -> int:
        """
        Glitterdust (Ardenweald): Toxic Skin - Reflect damage back to attacker
        
        Args:
            attacker: Pet that dealt damage
            damage_dealt: Amount of damage dealt
            
        Returns:
            Reflected damage amount
        """
        reflected = int(damage_dealt * 0.25)  # 25% reflection
        actual_reflected = attacker.stats.take_damage(reflected)
        return actual_reflected
    
    @staticmethod
    def apply_shell_shield(pet: Pet, duration: int = 3):
        """
        Diamond (Seeker Zusshi): Shell Shield - Reduce damage by 50% for 3 rounds
        
        Args:
            pet: Pet to shield
            duration: Duration in rounds
        """
        shield_buff = Buff(
            type=BuffType.STAT_MOD,
            duration=duration,
            magnitude=0.5,  # 50% damage reduction
            stat_affected='damage_taken',
            source_ability=66666  # Special Shell Shield ID
        )
        pet.active_buffs.append(shield_buff)
