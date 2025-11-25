
import unittest
from simulator.battle_state import Pet, PetStats, Ability, PetFamily, PetQuality, Buff, BuffType, BattleState, Team, TurnAction
from simulator.simulator import BattleSimulator

class TestHighRisk(unittest.TestCase):
    def setUp(self):
        self.sim = BattleSimulator()
        
        self.attacker = Pet(
            species_id=1, name="Attacker", 
            stats=PetStats(100, 100, 10, 10),
            family=PetFamily.HUMANOID, quality=PetQuality.RARE, abilities=[]
        )
        self.defender = Pet(
            species_id=2, name="Defender", 
            stats=PetStats(100, 100, 10, 10),
            family=PetFamily.BEAST, quality=PetQuality.RARE, abilities=[]
        )
        
        self.state = BattleState(Team([self.attacker]), Team([self.defender]))

    def test_explode_dies_on_miss(self):
        """Test that Explode kills the user even if it misses"""
        # Explode Ability
        explode = Ability(
            id=1, name="Explode", power=40, accuracy=100, speed=0, 
            family=PetFamily.MECHANICAL, cooldown=0, effect_type='explode'
        )
        self.attacker.abilities = [explode]
        
        # Force Miss (Defender uses Dodge)
        # Duration 2 because buffs tick at start of turn
        dodge_buff = Buff(type=BuffType.STAT_MOD, duration=2, magnitude=100.0, stat_affected='dodge')
        self.defender.active_buffs.append(dodge_buff)
        
        action_p = TurnAction('player', 'ability', ability=explode)
        action_e = TurnAction('enemy', 'pass')
        
        # Execute
        new_state = self.sim.execute_turn(self.state, action_p, action_e, turn_number=1)
        
        # Attacker should be dead
        attacker_after = new_state.player_team.pets[0]
        self.assertEqual(attacker_after.stats.current_hp, 0, "Exploder should die even on miss")
        
        # Log should show miss AND suicide
        events = [e['type'] for e in self.sim.log.events]
        self.assertIn('miss', events)
        self.assertIn('suicide', events)

    def test_haunt_survives_on_miss(self):
        """Test that Haunt does NOT kill the user if it misses"""
        # Haunt Ability
        haunt = Ability(
            id=2, name="Haunt", power=20, accuracy=100, speed=0, 
            family=PetFamily.UNDEAD, cooldown=0, effect_type='haunt'
        )
        self.attacker.abilities = [haunt]
        
        # Force Miss (Defender uses Dodge)
        # Duration 2 because buffs tick at start of turn (simulating end of previous turn)
        dodge_buff = Buff(type=BuffType.STAT_MOD, duration=2, magnitude=100.0, stat_affected='dodge')
        self.defender.active_buffs.append(dodge_buff)
        
        action_p = TurnAction('player', 'ability', ability=haunt)
        action_e = TurnAction('enemy', 'pass')
        
        # Execute
        new_state = self.sim.execute_turn(self.state, action_p, action_e, turn_number=1)
        
        # Attacker should be ALIVE
        attacker_after = new_state.player_team.pets[0]
        self.assertGreater(attacker_after.stats.current_hp, 0, "Haunter should survive on miss")
        
        # Log should show miss but NO suicide
        events = [e['type'] for e in self.sim.log.events]
        self.assertIn('miss', events)
        self.assertNotIn('suicide', events)

    def test_burrow_invulnerability(self):
        """Test that Burrow makes the user invulnerable"""
        # Attacker uses Burrow
        burrow = Ability(
            id=3, name="Burrow", power=20, accuracy=100, speed=0, 
            family=PetFamily.BEAST, cooldown=0, effect_type='burrow'
        )
        self.attacker.abilities = [burrow]
        
        # Defender attacks
        attack = Ability(id=4, name="Attack", power=10, accuracy=100, speed=0, family=PetFamily.HUMANOID, cooldown=0)
        self.defender.abilities = [attack]
        
        # Case 1: Attacker is Faster (Burrows first)
        self.attacker.stats.speed = 20
        self.defender.stats.speed = 10
        
        action_p = TurnAction('player', 'ability', ability=burrow)
        action_e = TurnAction('enemy', 'ability', ability=attack)
        
        # Execute
        new_state = self.sim.execute_turn(self.state, action_p, action_e, turn_number=1)
        
        # Defender's attack should MISS (Invulnerable)
        # Check log for 'immunity_block' or 'miss' due to invulnerability
        # My implementation returns False in check_hit -> 'miss'
        # But wait, check_hit returns False, so it logs 'miss'.
        # I should verify the reason or just that damage is 0.
        
        attacker_after = new_state.player_team.pets[0]
        
        # Attacker HP should be full (100)
        self.assertEqual(attacker_after.stats.current_hp, 100, "Attacker should take no damage while burrowed")
        
        # Verify Invulnerability Buff exists
        invuln = next((b for b in attacker_after.active_buffs if b.type == BuffType.INVULNERABILITY), None)
        self.assertIsNotNone(invuln)

if __name__ == '__main__':
    unittest.main()
