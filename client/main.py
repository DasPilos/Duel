import argparse
import getpass

from client.network import GameClient, ServerError


def run():
    parser = argparse.ArgumentParser(description="Локальный клиент игрового сервера")
    parser.add_argument("--username", help="Имя пользователя")
    parser.add_argument("--password", help="Пароль")
    parser.add_argument("--character", help="Имя персонажа")
    parser.add_argument("--server", default="http://127.0.0.1:8765")
    args = parser.parse_args()

    username = args.username or input("Пользователь: ").strip()
    password = args.password or getpass.getpass("Пароль: ")
    character_name = args.character or input("Персонаж: ").strip()
    client = GameClient(args.server)

    try:
        try:
            client.register(username, password)
            print("Пользователь создан")
        except ServerError as error:
            if "уже существует" not in str(error):
                raise

        user = client.login(username, password)
        character = client.load_character()
        if character is None:
            character = client.create_character(character_name)
            print("Персонаж создан")
        else:
            print("Персонаж загружен")

        print(f"Подключено: {user['username']}, персонаж: {character['name']}")
        print(f"Уровень: {character['level']}, HP: {character['hp']}/{character['max_hp']}")
        client.disconnect(character)
        print("Состояние сохранено, клиент отключён")
    except ServerError as error:
        print(f"Ошибка сервера: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    run()
