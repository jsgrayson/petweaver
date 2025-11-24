import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime

class XuFuScraperEnhanced:
    def __init__(self):
        self.base_url = "https://www.wow-petguide.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.data = {}
        self.request_count = 0
        self.start_time = None
        
    def respectful_delay(self):
        """Add 1-2 second delay between requests to be respectful"""
        time.sleep(1.5)  # 1.5 second delay between requests
        self.request_count += 1
        if self.request_count % 10 == 0:
            elapsed = time.time() - self.start_time if self.start_time else 0
            print(f"Progress: {self.request_count} requests in {elapsed:.1f}s (avg {elapsed/self.request_count:.2f}s per request)")
    
    def get_soup(self, url):
        try:
            self.respectful_delay()
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def extract_strategy_from_page(self, soup):
        """Enhanced extraction that properly parses pet slots with alternatives"""
        strategy_name = "Default Strategy"
        active_tab = soup.find('div', class_='nav-link active')
        if active_tab:
            strategy_name = active_tab.get_text().strip()
        
        strategy = {
            'name': strategy_name,
            'pet_slots': [],
            'script': ''
        }
        
        # Find the main strategy container
        # Look for the row containing pet cards
        pet_rows = soup.find_all('div', class_='row')
        
        current_slot_pets = []
        slot_count = 0
        
        # Parse pets more intelligently
        # Each strategy typically has 3 slots, and the page shows them with their alternatives
        all_pet_links = soup.find_all('a', class_='bt_petdetails')
        
        # Group pets into slots (assuming 3 slots per team)
        # We'll look for visual separators or use a heuristic
        seen_pet_names = set()
        
        for link in all_pet_links:
            pet_name = link.get_text().strip()
            pet_href = link.get('href', '')
            
            # Extract pet ID
            pet_id = 0
            if pet_href:
                match = re.search(r'/Pet/(\d+)/', pet_href)
                if match:
                    pet_id = int(match.group(1))
            
            pet_data = {
                'name': pet_name,
                'id': pet_id
            }
            
            # Add to current slot
            # Use a heuristic: if we've seen this exact pet already in a different slot,
            # it's likely a new instance (some pets appear in multiple slots)
            current_slot_pets.append(pet_data)
            seen_pet_names.add(pet_name)
        
        # Now intelligently group into 3 slots
        # Strategy: The first few pets are likely the main team
        # Then alternatives for each slot follow
        # For now, we'll use a simpler approach: divide pets into 3 equal groups
        total_pets = len(current_slot_pets)
        
        if total_pets >= 3:
            # If we have many pets, they're likely including alternatives
            # Put the first pet in slot 1, second in slot 2, third in slot 3
            # Then distribute the rest evenly
            
            # Take first 3 as the main team slots
            slot1 = [current_slot_pets[0]] if len(current_slot_pets) > 0 else []
            slot2 = [current_slot_pets[1]] if len(current_slot_pets) > 1 else []
            slot3 = [current_slot_pets[2]] if len(current_slot_pets) > 2 else []
            
            # Add remaining pets as alternatives, distributing them
            # This is a heuristic - ideally we'd parse the HTML structure more carefully
            remaining = current_slot_pets[3:]
            for i, pet in enumerate(remaining):
                slot_idx = i % 3
                if slot_idx == 0:
                    # Check for duplicates before adding
                    if not any(p['name'] == pet['name'] for p in slot1):
                        slot1.append(pet)
                elif slot_idx == 1:
                    if not any(p['name'] == pet['name'] for p in slot2):
                        slot2.append(pet)
                else:
                    if not any(p['name'] == pet['name'] for p in slot3):
                        slot3.append(pet)
            
            strategy['pet_slots'] = [s for s in [slot1, slot2, slot3] if s]
        else:
            # Few pets, just treat each as its own slot
            strategy['pet_slots'] = [[pet] for pet in current_slot_pets]
        
        # Extract script
        tooltip = soup.find(id='td_tooltip')
        if tooltip:
            script_text = tooltip.get_text().strip()
            lines = script_text.split('\n')
            clean_lines = [l for l in lines if "Click the button" not in l and "wow-petsim" not in l]
            strategy['script'] = '\n'.join(clean_lines).strip()
        
        return strategy

    def scrape_encounter(self, encounter_url, url_suffix):
        """Scrape strategies for a single encounter"""
        print(f"Fetching: {encounter_url}")
        
        # Check if URL is already absolute
        if url_suffix.startswith('http'):
            full_url = url_suffix
        else:
            full_url = f"{self.base_url}{url_suffix}"
            
        soup = self.get_soup(full_url)
        if not soup:
            return []

        strategies = []
        strategy = self.extract_strategy_from_page(soup)
        if strategy and (strategy.get('pet_slots') or strategy['script']):
            strategies.append(strategy)
            
        return strategies

    def scrape_category(self, category_url, category_suffix):
        """Scrape all encounters in a category"""
        print(f"Fetching: {category_url}")
        soup = self.get_soup(category_url)
        if not soup:
            return []

        encounters = []
        
        # Find links that point to encounters or strategies
        links = soup.find_all('a', href=re.compile(r'/(Strategy|Encounter)/\d+'))
        
        for link in links:
            href = link.get('href')
            encounter_name = link.get_text().strip()
            
            if href and encounter_name:
                encounter_url = f"{self.base_url}{href}" if not href.startswith('http') else href
                encounters.append({
                    'name': encounter_name,
                    'url': encounter_url,
                    'url_suffix': href
                })
        
        # Deduplicate by URL
        seen_urls = set()
        unique_encounters = []
        for enc in encounters:
            if enc['url'] not in seen_urls:
                seen_urls.add(enc['url'])
                unique_encounters.append(enc)
        
        return unique_encounters

    def scrape_all(self):
        """Main scraping method"""
        self.start_time = time.time()
        print(f"Starting enhanced scrape at {datetime.now().strftime('%H:%M:%S')}")
        print("Being respectful with 1.5s delays between requests...")
        
        # Categories from all expansions
        categories = {
            "The War Within": {
                "World Quests": "/Section/104/World_Quests",
                "The Undermine": "/Section/110/The_Undermine"
            },
            "Dragonflight": {
                "World Quests": "/Section/97/World_Quests",
                "The Forbidden Reach": "/Section/99/The_Forbidden_Reach",
                "Zaralek Cavern": "/Section/100/Zaralek_Cavern"
            },
            "Shadowlands": {
                "World Quests": "/Section/80/World_Quests",
                "Covenant Adventures": "/Section/85/Covenant_Adventures",
                "Torghast": "/Section/87/Torghast_Tower_of_the_Damned",
                "Family Exorcist": "/Section/89/Family_Exorcist"
            },
            "BfA": {
                "World Quests": "/Section/64/World_Quests",
                "Island Expeditions": "/Section/68/Island_Expeditions",
                "Warfronts": "/Section/69/Warfronts",
                "Family Battler": "/Section/71/Battle_for_Azeroth_Family_Battler",
                "Nazjatar & Mechagon": "/Section/72/Nazjatar_and_Mechagon"
            },
            "Legion": {
                "World Quests": "/Section/49/World_Quests",
                "Family Familiar": "/Section/51/Family_Familiar",
                "Broken Isles": "/Section/48/Broken_Isles_Tamers"
            },
            "Draenor": {
                "Garrison": "/Section/36/Garrison",
                "The Menagerie": "/Section/37/The_Menagerie",
                "Tamers": "/Section/38/Draenor_Tamers"
            },
            "Pandaria": {
                "Spirit Tamers": "/Section/19/Pandaren_Spirit_Tamers",
                "Beasts of Fable": "/Section/20/Beasts_of_Fable",
                "Tamers": "/Section/21/Tamers",
                "Celestial Tournament": "/Section/22/Celestial_Tournament"
            },
            "Dungeons": {
                "Wailing Caverns": "/Section/54/Wailing_Caverns",
                "Deadmines": "/Section/55/Deadmines",
                "Stratholme": "/Section/73/Stratholme",
                "Blackrock Depths": "/Section/74/Blackrock_Depths",
                "Gnomeregan": "/Section/75/Gnomeregan"
            },
            "Misc": {
                "Darkmoon Faire": "/Section/25/Darkmoon_Faire"
            }
        }
        
        total_categories = sum(len(cats) for cats in categories.values())
        print(f"Scraping {total_categories} categories...")
        
        for expansion, cats in categories.items():
            self.data[expansion] = {}
            
            for category_name, category_suffix in cats.items():
                category_url = f"{self.base_url}{category_suffix}"
                print(f"\nProcessing {expansion} - {category_name}")
                
                encounters_list = self.scrape_category(category_url, category_suffix)
                print(f"Found {len(encounters_list)} encounters in {category_name}")
                
                category_data = []
                for encounter in encounters_list:
                    strategies = self.scrape_encounter(encounter['url'], encounter['url_suffix'])
                    
                    if strategies:
                        category_data.append({
                            'encounter_name': encounter['name'],
                            'url': encounter['url'],
                            'strategies': strategies
                        })
                
                self.data[expansion][category_name] = category_data
        
        elapsed = time.time() - self.start_time
        print(f"\nScraping complete! {self.request_count} requests in {elapsed/60:.1f} minutes")
        print(f"Average: {elapsed/self.request_count:.2f}s per request (respectful ✅)")

    def save_data(self, filename='strategies_enhanced.json'):
        with open(filename, 'w') as f:
            json.dump(self.data, f, indent=2)
        print(f"Saved data to {filename}")

def main():
    scraper = XuFuScraperEnhanced()
    scraper.scrape_all()
    scraper.save_data()

if __name__ == "__main__":
    main()
