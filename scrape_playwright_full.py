"""
FULL-SCALE Playwright scraper for ALL Xu-Fu encounters.
Fast, respectful, and saves pristine data.
"""

import json
import time
from playwright.sync_api import sync_playwright
from datetime import datetime

class FullXuFuScraper:
    def __init__(self):
        self.base_url = "https://www.wow-petguide.com"
        
        # All categories to scrape - COMPLETE LIST
        self.categories = {
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
    
    def extract_teams(self, page):
        """Extract all teams from encounter page"""
        teams = []
        try:
            page.click('text="Browse all alternatives"', timeout=8000)
            page.wait_for_timeout(500)
            
            # Scroll modal
            page.evaluate("""
                const modal = document.getElementById('alternatives_window');
                if (modal) modal.scrollTop = modal.scrollHeight;
            """)
            page.wait_for_timeout(300)
            
            # Extract teams
            teams_json = page.evaluate("""
                (() => {
                    const table = document.getElementById('alternatives_window');
                    if (!table) return '[]';
                    const rows = table.querySelectorAll('tr');
                    const teams = [];
                    rows.forEach(row => {
                        const petDivs = row.querySelectorAll('td:first-child > div');
                        const team = [];
                        petDivs.forEach(div => {
                            const link = div.querySelector('a');
                            const img = div.querySelector('img');
                            if (link) {
                                const href = link.getAttribute('href');
                                let name = '[Unknown]';
                                let id = 0;
                                const match = href.match(/\\/Pet\\/(\\d+)\\/(.*)/);
                                if (match) {
                                    id = parseInt(match[1]);
                                    name = match[2].replace(/_/g, ' ');
                                }
                                team.push({ name, id });
                            } else if (img && img.getAttribute('alt') === 'Leveling Pet') {
                                team.push({ name: '[Empty/Leveling]', id: 0 });
                            }
                        });
                        if (team.length === 3) teams.push(team);
                    });
                    return JSON.stringify(teams);
                })()
            """)
            
            teams = json.loads(teams_json)
            try:
                page.keyboard.press('Escape')
                page.wait_for_timeout(200)
            except:
                pass
        except Exception as e:
            print(f"    Warning: Alternatives extraction failed")
        
        return teams
    
    def teams_to_slots(self, teams):
        """Convert teams to pet_slots format"""
        if not teams:
            return []
        
        slot1, slot2, slot3 = set(), set(), set()
        
        for team in teams:
            if len(team) >= 3:
                slot1.add((team[0]['name'], team[0]['id']))
                slot2.add((team[1]['name'], team[1]['id']))
                slot3.add((team[2]['name'], team[2]['id']))
        
        return [
            [{'name': n, 'id': i} for n, i in slot1 if i != 0 or n == '[Empty/Leveling]'],
            [{'name': n, 'id': i} for n, i in slot2 if i != 0 or n == '[Empty/Leveling]'],
            [{'name': n, 'id': i} for n, i in slot3 if i != 0 or n == '[Empty/Leveling]']
        ]
    
    def scrape_all(self):
        """Scrape ALL encounters from all expansions"""
        all_data = {}
        total_enc = 0
        total_teams = 0
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            for expansion, categories in self.categories.items():
                print(f"\n{'='*60}\n{expansion}\n{'='*60}")
                all_data[expansion] = {}
                
                for category, url in categories.items():
                    print(f"\n{category}:")
                    
                    # Get encounter list
                    page.goto(self.base_url + url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(1000)
                    
                    encounters = page.evaluate("""
                        (() => {
                            const encs = [];
                            document.querySelectorAll('a[href*="/Encounter/"]').forEach(link => {
                                const href = link.getAttribute('href');
                                const name = link.innerText.trim();
                                if (name && !encs.find(e => e.url === href)) {
                                    encs.push({ name, url: href });
                                }
                            });
                            return JSON.stringify(encs);
                        })()
                    """)
                    
                    encounters = json.loads(encounters)
                    print(f"  Found {len(encounters)} encounters")
                    
                    all_data[expansion][category] = []
                    
                    for i, enc in enumerate(encounters, 1):
                        try:
                            # enc['url'] already has full path, don't prepend base_url
                            enc_url = enc['url'] if enc['url'].startswith('http') else self.base_url + enc['url']
                            page.goto(enc_url, wait_until="domcontentloaded", timeout=45000)
                            page.wait_for_timeout(1000)
                            
                            teams = self.extract_teams(page)
                            pet_slots = self.teams_to_slots(teams)
                            
                            all_data[expansion][category].append({
                                'encounter_name': enc['name'],
                                'url': enc_url,
                                'strategies': [{
                                    'pet_slots': pet_slots
                                }],
                                'team_count': len(teams)
                            })
                            
                            print(f"    [{i}/{len(encounters)}] {enc['name']}: {len(teams)} teams, {sum(len(s) for s in pet_slots)} total alternatives")
                            total_enc += 1
                            total_teams += len(teams)
                            
                            # Respectful delay
                            time.sleep(1.5)
                            
                        except Exception as e:
                            print(f"    [{i}/{len(encounters)}] {enc['name']}: ERROR - {e}")
                    
                    # Save progress after each category
                    with open('strategies_browser_complete.json', 'w') as f:
                        json.dump(all_data, f, indent=2)
                    print(f"  ✓ Saved progress")
            
            browser.close()
        
        print(f"\n{'='*60}")
        print(f"COMPLETE! {total_enc} encounters, {total_teams} teams")
        print(f"Saved to strategies_browser_complete.json")

if __name__ == "__main__":
    print("="*60)
    print("FULL-SCALE XU-FU BROWSER SCRAPER")
    print("="*60)
    print("\nThis will scrape ALL encounters from ALL expansions.")
    print("Estimated time: 15-25 minutes")
    print("Output: strategies_browser_complete.json\n")
    
    scraper = FullXuFuScraper()
    scraper.scrape_all()
