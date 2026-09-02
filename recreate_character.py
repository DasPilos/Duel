import sqlite3
from server.database import Database

# Create database instance
db = Database('server_data.sqlite3')

# Get the existing user
conn = sqlite3.connect('server_data.sqlite3')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
user = cursor.execute("SELECT * FROM users WHERE username = ?", ("Das Pilos",)).fetchone()
conn.close()

if user:
    print("[OK] Found existing user: {} (ID: {})".format(user['username'], user['id']))
    
    # Create Warrior character
    print("\nCreating Warrior character...")
    warrior = db.create_character(user['id'], 'DasPilos', 'warrior')
    print("[OK] Character created: {}".format(warrior['name']))
    print("  - Type: {}".format(warrior['type']))
    print("  - Level: {}".format(warrior['level']))
    print("  - HP: {}/{}".format(warrior['hp'], warrior['max_hp']))
    print("  - Stats: {}".format(warrior['stats']))
    print("  - Money: {}c, {}s, {}g".format(warrior['copper'], warrior['silver'], warrior['gold']))
    
    print("\n" + "="*50)
    print("Done! You can login now!")
    print("="*50)
else:
    print("[ERROR] User not found")
