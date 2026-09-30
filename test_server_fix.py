#!/usr/bin/env python3
"""Test if server accepts all 6 professions"""
import requests
import json

SERVER_URL = "http://localhost:8000"

# First, register a user
print("1️⃣ Регистрация пользователя...")
register_response = requests.post(
    f"{SERVER_URL}/api/auth/register",
    json={"username": "testuser_fix", "password": "test123"}
)
print(f"   Status: {register_response.status_code}")
if register_response.status_code in [200, 201]:
    print("   ✅ Регистрация успешна")
    user_data = register_response.json()
    token = user_data.get("token")
else:
    print(f"   ❌ Ошибка: {register_response.text}")
    exit(1)

# Test all 6 professions
professions = ["warrior", "archer", "assassin", "battle_mage", "support_mage", "harmonist"]

print("\n2️⃣ Тестирование всех 6 классов...")
for prof in professions:
    char_name = f"test_{prof}_fix"
    response = requests.post(
        f"{SERVER_URL}/api/characters/create",
        json={
            "name": char_name,
            "profession_type": prof
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    status = "✅" if response.status_code == 201 else "❌"
    print(f"{status} {prof:15} - Status: {response.status_code}")

    if response.status_code != 201:
        try:
            error_data = response.json()
            print(f"   Error: {error_data}")
        except:
            print(f"   Error: {response.text}")

print("\n✅ Тест завершен!")
