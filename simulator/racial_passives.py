"""
Racial Passive System for Pet Battle Simulator

Implements the racial passive abilities for all 10 pet families.
These are core mechanics that apply to every pet based on their family type.

References:
- Undead: Revive for 1 turn when killed (Shadowlands mechanic)
- Magic: Cannot take more than 35% max HP in one hit
- Mechanical: Revive once per battle to 20% HP
- And 7 others...
"""

from typing import Optional
from .battle_state import Pet, PetFamily


class RacialPassives:
    """Handles racial passive abilities for all 10 pet families"""
    
    @staticmethod
    def apply_beast_passive() -> float:
        """
        Beast: +25% damage dealt (always active)
        
        Returns:
            Damage multiplier (1.25)
        """
        return 1.25
    
    @staticmethod
    def apply_critter_passive(pet: Pet) -> float:
        """
        Critter: +50% damage dealt when above 50% HP
        
        Args:
            pet: The critter pet to check
            
        Returns:
            Damage multiplier (1.5 if above 50% HP, 1.0 otherwise)
        """
        if pet.stats.current_hp > (pet.stats.max_hp * 0.5):
            return 1.5
        return 1.0
    
    @staticmethod
    def check_dragonkin_trigger(pet: Pet, previous_hp: int) -> bool:
        """
        Check if Dragonkin passive should trigger
        
        Dragonkin: +50% damage on next attack after falling below 50% HP
        
        Args:
            pet: The dragonkin pet
            previous_hp: HP before damage was taken
            
        Returns:
            True if pet just fell below 50% HP threshold
        """
        hp_threshold = pet.stats.max_hp * 0.5
        fell_below = previous_hp > hp_threshold and pet.stats.current_hp <= hp_threshold
        return fell_below
    
    @staticmethod
    def apply_dragonkin_passive(pet: Pet) -> float:
        """
        Dragonkin: +50% damage on next attack (if buff is ready)
        
        Args:
            pet: The dragonkin pet
            
        Returns:
            Damage multiplier (1.5 if buff ready, 1.0 otherwise)
        """
        if hasattr(pet, 'dragonkin_buff_ready') and pet.dragonkin_buff_ready:
            return 1.5
        return 1.0
    
    @staticmethod
    def consume_dragonkin_buff(pet: Pet):
        """
        Consume the dragonkin damage buff after it's been used
        
        Args:
            pet: The dragonkin pet
        """
        if hasattr(pet, 'dragonkin_buff_ready'):
            pet.dragonkin_buff_ready = False
    
    @staticmethod
    def apply_flying_passive(pet: Pet) -> float:
        """
        Flying: +50% speed when above 50% HP
        
        Args:
            pet: The flying pet
            
        Returns:
            Speed multiplier (1.5 if above 50% HP, 1.0 otherwise)
        """
        if pet.stats.current_hp > (pet.stats.max_hp * 0.5):
            return 1.5
        return 1.0
    
    @staticmethod
    def apply_humanoid_passive(pet: Pet, damage_dealt: int) -> int:
        """
        Humanoid: Recover 4% of max HP when dealing damage
        
        Args:
            pet: The humanoid pet that dealt damage
            damage_dealt: Amount of damage dealt
            
        Returns:
            Amount of HP healed
        """
        heal_amount = int(pet.stats.max_hp * 0.04)
        actual_heal = pet.stats.heal(heal_amount)
        return actual_heal
    
    @staticmethod
    def apply_magic_passive(pet: Pet, incoming_damage: int) -> int:
        """
        Magic: Cannot take more than 35% of max HP in one hit
        
        Args:
            pet: The magic pet receiving damage
            incoming_damage: Damage before cap
            
        Returns:
            Capped damage amount
        """
        max_damage = int(pet.stats.max_hp * 0.35)
        return min(incoming_damage, max_damage)
    
    @staticmethod
    def apply_aquatic_passive() -> float:
        """
        Aquatic: +25% healing received/dealt
        
        Returns:
            Healing multiplier (1.25)
        """
        return 1.25
    
    @staticmethod
    def apply_elemental_passive() -> bool:
        """
        Elemental: Immune to weather damage (DoTs from weather)
        
        Returns:
            True (immune to weather damage)
        """
        return True
    
    @staticmethod
    def apply_undead_passive(pet: Pet) -> bool:
        """
        Undead: Revive for 1 turn when killed
        
        This is THE SHADOWLANDS MECHANIC - when an Undead pet dies,
        it comes back for one final attack before truly dying.
        
        Args:
            pet: The undead pet that just died
            
        Returns:
            True if pet should revive, False otherwise
        """
        # Check if this pet has already used its revive
        if not hasattr(pet, 'has_used_undead_revive'):
            pet.has_used_undead_revive = False
        
        if not pet.has_used_undead_revive:
            # Mark that we're in revive mode
            pet.has_undead_revive = True
            pet.revive_turns_remaining = 1
            pet.has_used_undead_revive = True
            return True
        
        return False
    
    @staticmethod
    def apply_mechanical_passive(pet: Pet) -> bool:
        """
        Mechanical: Revive once per battle to 20% HP when killed
        
        Args:
            pet: The mechanical pet that just died
            
        Returns:
            True if pet revived, False otherwise
        """
        # Check if this pet has already used its revive
        if not hasattr(pet, 'has_used_mechanical_revive'):
            pet.has_used_mechanical_revive = False
        
        if not pet.has_used_mechanical_revive:
            # Revive to 20% HP
            pet.stats.current_hp = int(pet.stats.max_hp * 0.2)
            pet.has_used_mechanical_revive = True
            return True
        
        return False
    
    @staticmethod
    def get_damage_modifier(pet: Pet) -> float:
        """
        Get the damage modifier for a pet based on its racial passive
        
        Args:
            pet: The attacking pet
            
        Returns:
            Damage multiplier to apply
        """
        if pet.family == PetFamily.BEAST:
            return RacialPassives.apply_beast_passive()
        
        if pet.family == PetFamily.CRITTER:
            return RacialPassives.apply_critter_passive(pet)
        
        if pet.family == PetFamily.DRAGONKIN:
            return RacialPassives.apply_dragonkin_passive(pet)
        
        # Default: no modifier
        return 1.0
    
    @staticmethod
    def get_speed_modifier(pet: Pet) -> float:
        """
        Get the speed modifier for a pet based on its racial passive
        
        Args:
            pet: The pet to check
            
        Returns:
            Speed multiplier to apply
        """
        if pet.family == PetFamily.FLYING:
            return RacialPassives.apply_flying_passive(pet)
        
        # Default: no modifier
        return 1.0
    
    @staticmethod
    def get_healing_modifier(pet: Pet) -> float:
        """
        Get the healing modifier for a pet based on its racial passive
        
        Args:
            pet: The pet receiving/giving healing
            
        Returns:
            Healing multiplier to apply
        """
        if pet.family == PetFamily.AQUATIC:
            return RacialPassives.apply_aquatic_passive()
        
        # Default: no modifier
        return 1.0
