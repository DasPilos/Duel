import sqlite3

conn = sqlite3.connect('server_data.sqlite3')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check users
print('=== ПОЛЬЗОВАТЕЛИ ===')
users = cursor.execute('SELECT id, username FROM users').fetchall()
for user in users:
    print(f'ID: {user["id"]}, Username: {user["username"]}')

# Check characters
print('\n=== ПЕРСОНАЖИ ===')
chars = cursor.execute('SELECT id, user_id, name, type FROM characters').fetchall()
for char in chars:
    print(f'ID: {char["id"]}, User: {char["user_id"]}, Name: {char["name"]}, Type: {char["type"]}')

conn.close()
