"""Test profession selection and character creation"""

import tempfile
import os
import sys
import json
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Create temporary database for testing
temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite3')
temp_db_path = temp_db.name
temp_db.close()

try:
    # Import and patch config before importing Database
    from server import config
    original_db_path = config.DATABASE_PATH
    config.DATABASE_PATH = temp_db_path
    
    from server.database import Database
    
    print("Testing profession selection system...")
    print("=" * 60)
    
    db = Database(temp_db_path)
    
    # Test 1: Register user
    print("\n[OK] Test 1: Register user")
    user = db.register("testuser", "password123")
    print("  User created: {} (ID: {})".format(user['username'], user['id']))
    
    # Test 2: Create Warrior
    print("\n[OK] Test 2: Create Warrior character")
    warrior = db.create_character(user['id'], "ArthurWarrior", "warrior")
    print("  Warrior created: {}".format(warrior['name']))
    print("  Type: {}".format(warrior['type']))
    print("  Stats: {}".format(warrior['stats']))
    
    assert warrior['type'] == 'warrior', "Warrior type should be 'warrior'"
    stats = warrior['stats']
    assert 'strength' in stats, "Warrior should have 'strength' stat"
    assert 'agility' in stats, "Warrior should have 'agility' stat"
    assert 'intuition' in stats, "Warrior should have 'intuition' stat"
    assert stats['endurance'] == 4, "Warrior endurance should be 4"
    print("  [OK] Warrior stats validated")
    
    # Test 3: Create Mage
    print("\n[OK] Test 3: Create Mage character")
    mage = db.create_character(user['id'], "MerlinMage", "mage")
    print("  Mage created: {}".format(mage['name']))
    print("  Type: {}".format(mage['type']))
    print("  Stats: {}".format(mage['stats']))
    
    assert mage['type'] == 'mage', "Mage type should be 'mage'"
    stats = mage['stats']
    assert 'wisdom' in stats, "Mage should have 'wisdom' stat"
    assert 'spirituality' in stats, "Mage should have 'spirituality' stat"
    assert 'strength' not in stats, "Mage should NOT have 'strength' stat"
    assert stats['endurance'] == 4, "Mage endurance should be 4"
    print("  [OK] Mage stats validated")
    
    # Test 4: Both characters have separate funds
    print("\n[OK] Test 4: Verify separate funds")
    print("  Warrior funds: {} copper, {} silver".format(warrior['copper'], warrior['silver']))
    print("  Mage funds: {} copper, {} silver".format(mage['copper'], mage['silver']))
    # 1000 copper normalizes to 10 silver + 0 copper
    assert warrior['silver'] == 10 and warrior['copper'] == 0, "Warrior should start with 10 silver (1000 copper normalized)"
    assert mage['silver'] == 10 and mage['copper'] == 0, "Mage should start with 10 silver (1000 copper normalized)"
    print("  [OK] Both characters have correct starting funds")
    
    # Test 5: List all characters
    print("\n[OK] Test 5: List all characters")
    characters = db.get_characters(user['id'])
    print("  Total characters: {}".format(len(characters)))
    for char in characters:
        print("    - {} ({}) - Level {}".format(char['name'], char['type'], char['level']))
    
    assert len(characters) == 2, "Should have 2 characters"
    types = {char['type'] for char in characters}
    assert types == {'warrior', 'mage'}, "Should have both warrior and mage"
    print("  [OK] Both character types present in list")
    
    # Test 6: Invalid profession should fail
    print("\n[OK] Test 6: Test invalid profession handling")
    try:
        invalid = db.create_character(user['id'], "InvalidType", "invalid")
        print("  [FAIL] Should have raised ValueError for invalid profession")
        assert False, "Should reject invalid profession"
    except ValueError as e:
        print("  [OK] Correctly rejected: {}".format(e))
    
    print("\n" + "=" * 60)
    print("SUCCESS: ALL TESTS PASSED!")
    print("=" * 60)
    
finally:
    # Cleanup
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)
    config.DATABASE_PATH = original_db_path
