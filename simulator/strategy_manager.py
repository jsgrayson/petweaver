import json
import os
import difflib

class StrategyManager:
    def __init__(self, strategies_path):
        self.strategies_path = strategies_path
        self.strategies = self._load_strategies()
        self.lookup_cache = {} # Cache for fuzzy matches

    def _load_strategies(self):
        """Loads strategies from the JSON file."""
        if not os.path.exists(self.strategies_path):
            print(f"Warning: Strategy file not found at {self.strategies_path}")
            return {}
        
        try:
            with open(self.strategies_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading strategies: {e}")
            return {}

    def get_strategy(self, npc_name):
        """
        Finds the best matching strategy for a given NPC name.
        Returns a dictionary with strategy details or None.
        """
        if not npc_name:
            return None
            
        # Check cache first
        if npc_name in self.lookup_cache:
            return self.lookup_cache[npc_name]

        # Flatten the structure to search
        # Structure: Expansion -> Category -> List of Encounters
        best_match = None
        highest_ratio = 0.0
        
        # Direct match check first (optimization)
        for expansion, categories in self.strategies.items():
            for category, encounters in categories.items():
                for encounter in encounters:
                    enc_name = encounter.get('encounter_name', '')
                    if enc_name.lower() == npc_name.lower():
                        result = self._process_encounter(encounter)
                        self.lookup_cache[npc_name] = result
                        return result
                        
        # Fuzzy match
        for expansion, categories in self.strategies.items():
            for category, encounters in categories.items():
                for encounter in encounters:
                    enc_name = encounter.get('encounter_name', '')
                    ratio = difflib.SequenceMatcher(None, npc_name.lower(), enc_name.lower()).ratio()
                    
                    if ratio > highest_ratio:
                        highest_ratio = ratio
                        best_match = encounter

        if best_match and highest_ratio > 0.7: # Threshold for fuzzy match
            result = self._process_encounter(best_match)
            self.lookup_cache[npc_name] = result
            return result
            
        return None

    def _process_encounter(self, encounter):
        """Extracts the default strategy from an encounter object."""
        if not encounter.get('strategies'):
            return None
            
        # Default to the first strategy
        strategy = encounter['strategies'][0]
        
        return {
            'encounter_name': encounter.get('encounter_name'),
            'url': encounter.get('url'),
            'strategy_name': strategy.get('name'),
            'script': strategy.get('script'),
            'pet_slots': strategy.get('pet_slots', []),
            'rematch_string': self.generate_rematch_string(encounter['encounter_name'], strategy)
        }

    def generate_rematch_string(self, encounter_name, strategy):
        """
        Generates a Rematch import string.
        Format: Name:ID:Pet1ID:Pet2ID:Pet3ID:Script
        Note: Rematch strings are complex. A simpler format often supported is:
        Title:Script:Pet1:Pet2:Pet3 (This is pseudo-code, real Rematch strings are often base64 encoded or specific format)
        
        Actually, Rematch import strings usually look like:
        Rematch String for [Name]: [Pet1ID]:[Pet2ID]:[Pet3ID]
        
        However, for automation, we might just want to return the Script and Pets 
        so the USER can manually build it or we use a specific format if known.
        
        Let's try to construct a standard Rematch export string format if possible, 
        or at least a readable format the user can use.
        
        Standard Rematch Export (Single Team):
        Name:Pet1ID:Pet2ID:Pet3ID:Script
        """
        # Extract Pet IDs (use the first option for each slot)
        pet_ids = [0, 0, 0]
        for i, slot in enumerate(strategy.get('pet_slots', [])):
            if i < 3 and slot:
                # Slot is a list of options, pick first
                if isinstance(slot, list) and len(slot) > 0:
                    pet_ids[i] = slot[0].get('id', 0)
        
        # Clean script (remove newlines for single line format if needed, but Rematch supports multiline)
        # But for the string format "Name:ID:..." it usually expects specific delimiters.
        
        # Let's stick to a simple representation for now that the UI can display.
        # The user asked for "Rematch-compatible import string".
        # A common format is: "Name:Pet1:Pet2:Pet3:Script"
        
        script = strategy.get('script', '')
        return f"{encounter_name}:{pet_ids[0]}:{pet_ids[1]}:{pet_ids[2]}:{script}"

    def get_recommended_team(self, npc_name):
        """
        Returns a list of recommended pet IDs for the given NPC.
        Format: [Pet1ID, Pet2ID, Pet3ID] (0 for empty slots)
        """
        strategy_data = self.get_strategy(npc_name)
        if not strategy_data:
            return None
            
        pet_ids = [0, 0, 0]
        for i, slot in enumerate(strategy_data.get('pet_slots', [])):
            if i < 3 and slot:
                # Slot is a list of options, pick first
                if isinstance(slot, list) and len(slot) > 0:
                    pet_ids[i] = slot[0].get('id', 0)
        
        return pet_ids
