
import json
from config import MUSLIM_JSON_PATH

with open(MUSLIM_JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

print(type(data))
if isinstance(data, dict):
    print("Keys:", list(data.keys())) 
elif isinstance(data, list):
    print(f"Loaded a list with {len(data)} items. First item:", data[0])