"""
Fast Playwright-based scraper for Xu-Fu strategies.
Uses browser automation with JavaScript extraction for speed.
"""

import json
import time
from playwright.sync_api import sync_playwright
from datetime import datetime

class FastXuFuScraper:
    def __init__(self):
        self.base_url = "https://www.wow-petguide.com"
        self.data = {}
        
    def extract_teams_and_script(self, page, encounter_url):
        """Extract all teams and script from an encounter page"""
        print(f"  Loading {encounter_url}")
        page.goto(encounter_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1000)  # Let JavaScript finish
        
        # Click "Browse all alternatives"
        teams = []
        try:
            page.click('text="Browse all alternatives"', timeout=8000)
            page.wait_for_timeout(500)
            
            # Scroll modal to bottom
            page.evaluate("""
                const modal = document.getElementById('alternatives_window');
                if (modal) modal.scrollTop = modal.scrollHeight;
            """)
            page.wait_for_timeout(300)
            
            # Extract all teams
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
                            } else {
                                team.push({ name: '[Unknown]', id: 0 });
                            }
                        });
                        if (team.length === 3) teams.push(team);
                    });
                    return JSON.stringify(teams);
                })()
            """)
            
            teams = json.loads(teams_json)
            
            # Try to close modal (optional - doesn't matter if it fails)
            try:
                page.keyboard.press('Escape')
                page.wait_for_timeout(200)
            except:
                pass
            
        except Exception as e:
            print(f"  Warning: Alternatives extraction failed: {e}")
        
        # Extract script
        script = ""
        try:
            page.click('text="Script"', timeout=5000)
            page.wait_for_timeout(300)
            script = page.evaluate("""
                document.getElementById('td_tooltip') ? 
                document.getElementById('td_tooltip').innerText : 
                ''
            """)
        except Exception as e:
            print(f"  Warning: Script extraction failed: {e}")
        
        return teams, script
    
    def scrape_encounters(self, encounters):
        """Scrape a list of encounters"""
        results = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            for i, enc in enumerate(encounters, 1):
                print(f"[{i}/{len(encounters)}] {enc['name']}")
                try:
                    teams, script = self.extract_teams_and_script(page, enc['url'])
                    
                    results.append({
                        'encounter_name': enc['name'],
                        'url': enc['url'],
                        'teams': teams,
                        'script': script,
                        'team_count': len(teams),
                        'scraped_at': datetime.now().isoformat()
                    })
                    
                    print(f"  ✓ Extracted {len(teams)} teams")
                    
                except Exception as e:
                    print(f"  ✗ Error: {e}")
                    results.append({
                        'encounter_name': enc['name'],
                        'url': enc['url'],
                        'error': str(e)
                    })
                
                # Small delay between encounters to be respectful
                time.sleep(1.5)
            
            browser.close()
        
        return results

# The War Within encounters
TWW_ENCOUNTERS = [
    {"name": "Rock Collector", "url": "https://www.wow-petguide.com/Encounter/1589/Rock_Collector"},
    {"name": "Robot Rumble", "url": "https://www.wow-petguide.com/Encounter/1590/Robot_Rumble"},
    {"name": "The Power of Friendship", "url": "https://www.wow-petguide.com/Encounter/1592/The_Power_of_Friendship"},
    {"name": "Major Malfunction", "url": "https://www.wow-petguide.com/Encounter/1593/Major_Malfunction"},
    {"name": "Miniature Army", "url": "https://www.wow-petguide.com/Encounter/1595/Miniature_Army"},
    {"name": "The Thing from the Swamp", "url": "https://www.wow-petguide.com/Encounter/1596/The_Thing_from_the_Swamp"},
    {"name": "Ziriak", "url": "https://www.wow-petguide.com/Encounter/1598/Ziriak"},
    {"name": "One Hungry Worm", "url": "https://www.wow-petguide.com/Encounter/1599/One_Hungry_Worm"}
]

if __name__ == "__main__":
    print("Fast Playwright Scraper - The War Within Test")
    print(f"Scraping {len(TWW_ENCOUNTERS)} encounters...\n")
    
    scraper = FastXuFuScraper()
    results = scraper.scrape_encounters(TWW_ENCOUNTERS)
    
    # Save results
    output = {
        "expansion": "The War Within",
        "category": "World Quests",
        "encounters": results,
        "total_encounters": len(results),
        "total_teams": sum(r.get('team_count', 0) for r in results),
        "scraped_at": datetime.now().isoformat()
    }
    
    with open('tww_test_fast.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✓ Saved to tww_test_fast.json")
    print(f"  Total encounters: {len(results)}")
    print(f"  Total teams extracted: {output['total_teams']}")
