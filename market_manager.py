import json
import os
from datetime import datetime
from typing import List, Dict, Optional

MARKET_FILE = 'market_data.json'

class MarketManager:
    def __init__(self, data_file: str = MARKET_FILE):
        self.data_file = data_file
        self.market_data = self._load_data()
        
    def _load_data(self) -> Dict:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
        
    def _save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.market_data, f, indent=2)
            
    def update_price(self, species_id: int, price: int, pet_name: str = "Unknown"):
        """
        Update price history for a pet.
        price: Price in copper (or gold, assuming consistent units)
        """
        sid = str(species_id)
        if sid not in self.market_data:
            self.market_data[sid] = {
                "name": pet_name,
                "history": [],
                "current_price": 0,
                "last_updated": None
            }
            
        # Update metadata
        self.market_data[sid]["name"] = pet_name
        self.market_data[sid]["current_price"] = price
        self.market_data[sid]["last_updated"] = datetime.now().isoformat()
        
        # Add to history (keep last 10 entries)
        history_entry = {
            "price": price,
            "timestamp": datetime.now().isoformat()
        }
        self.market_data[sid]["history"].append(history_entry)
        if len(self.market_data[sid]["history"]) > 10:
            self.market_data[sid]["history"] = self.market_data[sid]["history"][-10:]
            
        self._save_data()
        
    def get_market_value(self, species_id: int) -> float:
        """Calculate market value based on history average"""
        sid = str(species_id)
        if sid not in self.market_data:
            return 0.0
            
        history = self.market_data[sid]["history"]
        if not history:
            return 0.0
            
        total = sum(entry["price"] for entry in history)
        return total / len(history)
        
    def get_deals(self, threshold_percent: float = 0.5) -> List[Dict]:
        """
        Find pets listed below (1 - threshold_percent) of market value.
        e.g. threshold 0.5 means 50% off (Price <= 0.5 * MarketValue)
        """
        deals = []
        for sid, data in self.market_data.items():
            current = data["current_price"]
            market_value = self.get_market_value(int(sid))
            
            if market_value > 0 and current <= (market_value * threshold_percent):
                discount = int((1 - (current / market_value)) * 100)
                deals.append({
                    "speciesId": int(sid),
                    "name": data["name"],
                    "price": current,
                    "marketValue": int(market_value),
                    "discount": discount,
                    "lastUpdated": data["last_updated"]
                })
                
        # Sort by highest discount
        deals.sort(key=lambda x: x["discount"], reverse=True)
        return deals
        
    def get_all_data(self) -> Dict:
        return self.market_data
