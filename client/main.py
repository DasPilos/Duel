import argparse
import getpass

from client.network import GameClient, ServerError


def run():
    parser = argparse.ArgumentParser(description="Локальный клиент игрового сервера")
    parser.add_argument("--username", help="Имя пользователя")
    parser.add_argument("--password", help="Пароль")
    parser.add_argument("--character", help="Имя персонажа")
    parser.add_argument("--server", default="http://127.0.0.1:8765")
    restart_action = parser.add_mutually_exclusive_group()
    restart_action.add_argument("--schedule-restart", action="store_true",
                                help="Предупредить игроков и перезапустить сервер через 3 минуты")
    restart_action.add_argument("--cancel-restart", action="store_true",
                                help="Отменить запланированный перезапуск")
    parser.add_argument("--restart-minutes", type=int, default=3,
                        help="Задержка перезапуска в минутах (1-30)")
    args = parser.parse_args()

    username = args.username or input("Пользователь: ").strip()
    password = args.password or getpass.getpass("Пароль: ")
    client = GameClient(args.server)

    try:
        if args.schedule_restart or args.cancel_restart:
            client.login(username, password)
            if args.cancel_restart:
                client.cancel_server_restart()
                print("Запланированный перезапуск отменён")
            else:
                notice = client.schedule_server_restart(args.restart_minutes)
                print(f"Игроки уведомлены; перезапуск запланирован через {notice['seconds_remaining']} секунд")
            return

        character_name = args.character or input("Персонаж: ").strip()
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
