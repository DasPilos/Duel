extends Node

const MAIN_SCRIPT = preload("res://scripts/main.gd")
const LOBBY_FORMAT := preload("res://scripts/lobby_format.gd")
const WORLD_DIALOG_SCRIPT := preload("res://scripts/world_create_dialog.gd")
const AVATAR_CROP_DIALOG_SCRIPT := preload("res://scripts/avatar_crop_dialog.gd")
const PREFERENCES_PATH := "user://login_preferences_smoke.cfg"


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var lobby = MAIN_SCRIPT.new()
	lobby._login_preferences_path = PREFERENCES_PATH
	lobby.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(lobby)
	var worlds: Array[Dictionary] = [{
		"id": 7,
		"name": "Тестовый мир Башни 64",
		"mode": "economy",
		"is_open": true,
		"server_url": "http://127.0.0.1:8801",
		"started_at": 1700000000.0,
		"closes_at": null,
		"online_players": 4,
		"test_only": false,
	}]
	var players: Array[Dictionary] = [{"user_id": 1, "username": "Игрок"}]
	var messages: Array[Dictionary] = [
		{"id": 1, "sender_user_id": 2, "username": "Игрок", "recipient_user_id": null, "text": "Привет!", "created_at": 1700000000.0},
		{"id": 2, "sender_user_id": 2, "username": "Игрок", "recipient_user_id": 3, "recipient_username": "Гость", "text": "Личное", "created_at": 1700000001.0},
	]
	lobby._worlds = worlds
	lobby._lobby_players = players
	lobby._lobby_chat_messages = messages
	lobby._show_worlds()
	if DisplaySettings._open_button.visible:
		push_error("Кнопка настроек видна вне титульного экрана.")
		_finish(lobby, 1)
		return
	lobby._show_login()
	if not DisplaySettings._open_button.visible:
		push_error("Кнопка настроек скрыта на титульном экране.")
		_finish(lobby, 1)
		return
	if lobby._remember_username_check.get_parent() != lobby._username_input.get_parent():
		push_error("Кнопка запоминания имени не стоит рядом с его полем.")
		_finish(lobby, 1)
		return
	if lobby._remember_password_check.get_parent() != lobby._password_input.get_parent():
		push_error("Кнопка запоминания пароля не стоит рядом с его полем.")
		_finish(lobby, 1)
		return
	if lobby._remember_username_check.custom_minimum_size != Vector2(27, 27) or lobby._remember_password_check.custom_minimum_size != Vector2(27, 27):
		push_error("Кнопки запоминания не квадратные.")
		_finish(lobby, 1)
		return
	if lobby._screen_panel.custom_minimum_size.x != 329:
		push_error("Рамка экрана входа не увеличена до масштаба 58.8%%: %s." % str(lobby._screen_panel.custom_minimum_size))
		_finish(lobby, 1)
		return
	if lobby._username_input.custom_minimum_size.y != 27 or lobby._password_input.custom_minimum_size.y != 27:
		push_error("Поля ввода экрана входа не увеличены до масштаба 58.8%.")
		_finish(lobby, 1)
		return
	if lobby._username_input.get_theme_font_size("font_size") != 14 or lobby._password_input.get_theme_font_size("font_size") != 14:
		push_error("Шрифт в полях входа не увеличен независимо от масштаба формы.")
		_finish(lobby, 1)
		return
	var login_button: Button
	var register_button: Button
	for child in lobby._content.get_children():
		if child is Button and child.text == "Войти":
			login_button = child
		elif child is Button and child.text == "Создать аккаунт":
			register_button = child
	if login_button == null or register_button == null or login_button.custom_minimum_size.y != 28 or register_button.custom_minimum_size.y != 28:
		push_error("Кнопки входа и регистрации не увеличены до масштаба 58.8%.")
		_finish(lobby, 1)
		return
	if login_button.get_theme_font_size("font_size") != 15 or register_button.get_theme_font_size("font_size") != 15:
		push_error("Шрифт кнопок входа не увеличен независимо от масштаба формы.")
		_finish(lobby, 1)
		return
	if lobby._remember_username_check.get_parent() != lobby._username_input.get_parent() or lobby._remember_password_check.get_parent() != lobby._password_input.get_parent():
		push_error("Кнопки запоминания не встроены в строки полей ввода.")
		_finish(lobby, 1)
		return
	lobby._remember_password_check.button_pressed = false
	lobby._update_remember_button_style(lobby._remember_password_check, false)
	var inactive_style := lobby._remember_password_check.get_theme_stylebox("normal") as StyleBoxFlat
	lobby._remember_password_check.button_pressed = true
	lobby._update_remember_button_style(lobby._remember_password_check, true)
	var active_style := lobby._remember_password_check.get_theme_stylebox("normal") as StyleBoxFlat
	if active_style.bg_color.g <= inactive_style.bg_color.g:
		push_error("Активная кнопка запоминания не подсвечивается зелёным.")
		_finish(lobby, 1)
		return
	lobby._show_worlds()
	if DisplaySettings._open_button.visible:
		push_error("Кнопка настроек видна в лобби.")
		_finish(lobby, 1)
		return

	await get_tree().process_frame
	await get_tree().process_frame
	if not _check_lobby_layout(lobby):
		_finish(lobby, 1)
		return
	if not _contains_text(lobby._worlds_list, "Тестовый мир Башни 64 · Economy") or not _contains_fragment(lobby._worlds_list, "Онлайн: 4 · бессрочный") or not _contains_text(lobby._worlds_list, "работает"):
		push_error("Список серверов не показывает название, режим, онлайн и срок доступного сервера.")
		_finish(lobby, 1)
		return
	if not _contains_text(lobby._worlds_list, "Войти") or _contains_text(lobby._worlds_list, "Запустить"):
		push_error("У работающего сервера должна быть кнопка входа и не должно быть запуска для игрока.")
		_finish(lobby, 1)
		return
	if lobby._worlds_scroll.horizontal_scroll_mode != ScrollContainer.SCROLL_MODE_DISABLED:
		push_error("Список миров не должен обрезаться по горизонтали.")
		_finish(lobby, 1)
		return
	var world_card: Control = lobby._worlds_list.get_child(0)
	if world_card.get_global_rect().size.x > lobby._worlds_scroll.get_global_rect().size.x + 1.0:
		push_error("Карточка мира выходит за ширину списка.")
		_finish(lobby, 1)
		return
	var world_card_layout: VBoxContainer = world_card.get_child(0).get_child(0)
	var world_title: Label = world_card_layout.get_child(0).get_child(0)
	if world_title.tooltip_text != "Тестовый мир Башни 64 · Economy":
		push_error("Полное название мира должно оставаться доступным во всплывающей подсказке.")
		_finish(lobby, 1)
		return
	var enter_button := _find_button(world_card, "Войти")
	if enter_button == null or not lobby._worlds_panel.get_global_rect().encloses(enter_button.get_global_rect()):
		push_error("Кнопка входа должна целиком помещаться в карточке мира.")
		_finish(lobby, 1)
		return
	if lobby._lobby_chat._players_box.get_child_count() != 1 or lobby._lobby_chat._players_title.text != "Лобби · онлайн 1":
		push_error("Счётчик онлайн-игроков лобби неверен.")
		_finish(lobby, 1)
		return
	if not lobby._lobby_chat._log.text.contains("Привет!") or lobby._lobby_chat._log.text.contains("Личное"):
		push_error("Общий чат лобби показывает личные сообщения или не показывает общие.")
		_finish(lobby, 1)
		return
	if not _contains_text(lobby._lobby_root, "Уровень 0") or not _contains_text(lobby._lobby_root, "Настройка аккаунта") or not _contains_text(lobby._lobby_root, "Игровые миры"):
		push_error("Аккаунт не показывает уровень и кнопку настройки или панель миров не названа «Игровые миры».")
		_finish(lobby, 1)
		return
	if _contains_text(lobby._lobby_root, "Редактор карт") or _contains_text(lobby._lobby_root, "Запустить новый мир"):
		push_error("Игрок видит кнопки модератора в лобби.")
		_finish(lobby, 1)
		return
	var nick_row: Button = lobby._lobby_chat._players_box.get_child(0)
	var right_press := InputEventMouseButton.new()
	right_press.button_index = MOUSE_BUTTON_RIGHT
	right_press.pressed = true
	nick_row.gui_input.emit(right_press)
	if not lobby._lobby_context_menu.visible or _menu_items(lobby._lobby_context_menu) != [
		["Отправить личное сообщение", true, false],
		["Пригласить в команду", true, true],
		["Предложить обмен", true, true],
	]:
		push_error("Меню ника не содержит личного сообщения, команды и обмена или серые пункты активны.")
		_finish(lobby, 1)
		return
	var whisper_button := _find_menu_button(lobby._lobby_context_menu, "Отправить личное сообщение")
	if whisper_button == null or whisper_button.disabled:
		push_error("Пункт «Отправить личное сообщение» не найден или неактивен.")
		_finish(lobby, 1)
		return
	whisper_button.pressed.emit()
	if lobby._lobby_context_menu.visible or lobby._lobby_chat._input.text != "/w Игрок " or lobby._lobby_chat._tab != "Личный":
		push_error("Пункт «Отправить личное сообщение» не переключает чат на личный диалог с /w.")
		_finish(lobby, 1)
		return
	lobby._lobby_chat._on_tab_pressed("Общий")
	lobby._lobby_chat.clear_input()
	var avatar_press := InputEventMouseButton.new()
	avatar_press.button_index = MOUSE_BUTTON_RIGHT
	avatar_press.pressed = true
	lobby._account_card.gui_input.emit(avatar_press)
	if not lobby._lobby_context_menu.visible or _menu_items(lobby._lobby_context_menu) != [
		["Можно поставить PNG 150 × 150 px", false, false],
		["Сменить аватар", true, false],
	]:
		push_error("Меню фото не показывает размер PNG и пункт смены аватара.")
		_finish(lobby, 1)
		return
	var outside_press := InputEventMouseButton.new()
	outside_press.button_index = MOUSE_BUTTON_LEFT
	outside_press.pressed = true
	outside_press.position = Vector2(1200, 700)
	lobby._lobby_context_menu._input(outside_press)
	if lobby._lobby_context_menu.visible:
		push_error("Меню не закрывается кликом мимо него.")
		_finish(lobby, 1)
		return
	lobby._account_card.gui_input.emit(avatar_press)
	var escape_press := InputEventKey.new()
	escape_press.keycode = KEY_ESCAPE
	escape_press.pressed = true
	lobby._lobby_context_menu._input(escape_press)
	if lobby._lobby_context_menu.visible:
		push_error("Клавиша Esc не закрывает меню.")
		_finish(lobby, 1)
		return
	lobby._show_map_editor_menu()
	if not _contains_text(lobby._content, "Создать новую карту") or not _contains_text(lobby._content, "Загрузить карту для редактирования"):
		push_error("Меню редактора карт не предлагает создание и загрузку карты.")
		_finish(lobby, 1)
		return
	lobby._show_new_map_setup()
	if lobby._new_map_name_input == null or lobby._new_map_width.value != 64 or lobby._new_map_height.value != 64:
		push_error("Форма новой карты не показывает название и размер по умолчанию.")
		_finish(lobby, 1)
		return
	if lobby._new_map_tile_size.item_count != 2 or not lobby._new_map_tile_size.is_item_disabled(1):
		push_error("В форме 32×32 должно быть видно, но недоступно.")
		_finish(lobby, 1)
		return
	if lobby._new_map_mode.item_count != 3 \
		or str(lobby._new_map_mode.get_item_metadata(0)) != "front_line":
		push_error("В форме новой карты должны быть режимы Front Line, Economy и Deck.")
		_finish(lobby, 1)
		return
	if LOBBY_FORMAT.world_end_text({"mode": "front_line"}) != "до исхода матча":
		push_error("Front Line должен показывать конечность матча, а не бессрочный сервер.")
		_finish(lobby, 1)
		return
	lobby._saved_maps.clear()
	lobby._saved_maps.append({
		"id": 12,
		"name": "Тестовая карта",
		"mode": "economy",
		"map_w": 64,
		"map_h": 32,
	})
	lobby._saved_maps.append({
		"id": 13,
		"name": "Коридор",
		"mode": "front_line",
		"map_w": 96,
		"map_h": 32,
	})
	lobby._show_editor_saved_maps()
	if not _contains_text(lobby._content, "Тестовая карта · Economy · 64×32") \
		or not _contains_text(lobby._content, "Коридор · Front Line · 96×32"):
		push_error("В меню загрузки должны отображаться названия и режимы сохранённых карт.")
		_finish(lobby, 1)
		return

	lobby._worlds[0]["server_url"] = null
	lobby._show_worlds()
	if not _contains_text(lobby._worlds_list, "не запущен") or _contains_text(lobby._worlds_list, "Войти"):
		push_error("Мир без URL сервера отображается как доступный.")
		_finish(lobby, 1)
		return

	lobby._worlds.clear()
	lobby._show_worlds()
	if lobby._worlds_list.get_child_count() != 0 or _contains_fragment(lobby._lobby_root, "Список пуст"):
		push_error("Пустой список серверов должен оставаться пустым меню без текста.")
		_finish(lobby, 1)
		return

	GameSession.user = {"id": 9, "username": "Модератор", "role": "moderator"}
	lobby._worlds.clear()
	lobby._worlds.append({
		"id": 8,
		"name": "Тестовый мир",
		"mode": "economy",
		"is_open": true,
		"server_url": "",
		"started_at": null,
		"closes_at": 1800000000.0,
		"online_players": 0,
		"test_only": true,
	})
	lobby._show_worlds()
	if not _contains_text(lobby._lobby_root, "Редактор карт") or not _contains_text(lobby._lobby_root, "Запустить новый мир"):
		push_error("Модератор не видит редактор карт и кнопку запуска нового мира.")
		_finish(lobby, 1)
		return
	if not _contains_text(lobby._worlds_list, "Запустить") or not _contains_fragment(lobby._worlds_list, "до ") or not _contains_fragment(lobby._worlds_list, "тестовый"):
		push_error("Модератор не может запустить свой тестовый мир или срок и тип не показаны.")
		_finish(lobby, 1)
		return
	lobby._worlds[0]["test_only"] = false
	lobby._show_worlds()
	if _contains_text(lobby._worlds_list, "Запустить"):
		push_error("Модератор видит кнопку запуска публичного мира.")
		_finish(lobby, 1)
		return
	GameSession.user = {"id": 1, "username": "Администратор", "role": "admin"}
	lobby._show_worlds()
	if not _contains_text(lobby._worlds_list, "Запустить"):
		push_error("Администратор не видит кнопку запуска публичного мира.")
		_finish(lobby, 1)
		return

	var png_source := Image.create(150, 150, false, Image.FORMAT_RGBA8)
	png_source.fill(Color(0.2, 0.6, 0.3, 1.0))
	var decoded: Image = lobby._decode_avatar(Marshalls.raw_to_base64(png_source.save_png_to_buffer()))
	if decoded == null or decoded.get_width() != 150 or decoded.get_height() != 150:
		push_error("Фото аккаунта не декодируется в 150×150.")
		_finish(lobby, 1)
		return
	lobby._apply_avatar(ImageTexture.create_from_image(decoded))
	var avatar_area := lobby._account_card.get_child(0) as Control
	if avatar_area.custom_minimum_size != Vector2(100, 100) or lobby._account_card._texture_rect.texture == null:
		push_error("Фото не отображается в рамке 100×100 базовых единиц (150 px при 1920×1080).")
		_finish(lobby, 1)
		return
	if not await _check_avatar_flow(lobby):
		_finish(lobby, 1)
		return

	var parsed: Dictionary = LOBBY_FORMAT.parse_whisper("/w Кир привет всем", [
		{"user_id": 2, "username": "Кир"}, {"user_id": 3, "username": "Ки"}, {"user_id": 1, "username": "Себя"},
	], 1)
	if str(parsed["error"]) != "" or int(parsed["user_id"]) != 2 or str(parsed["message"]) != "привет всем":
		push_error("Команда /w не выбирает самое длинное имя игрока.")
		_finish(lobby, 1)
		return
	var whisper_players := [{"user_id": 2, "username": "Кир"}, {"user_id": 3, "username": "Ки"}, {"user_id": 1, "username": "Себя"}]
	if LOBBY_FORMAT.parse_whisper("/w", whisper_players, 1)["error"] != "Формат: /w <имя> текст":
		push_error("Пустая команда /w не объясняет формат.")
		_finish(lobby, 1)
		return
	if LOBBY_FORMAT.parse_whisper("/w Ки", whisper_players, 1)["error"] != "Введите текст сообщения после имени":
		push_error("Команда /w без текста не просит текст сообщения.")
		_finish(lobby, 1)
		return
	if LOBBY_FORMAT.parse_whisper("/w Себя привет", whisper_players, 1)["error"] != "Игрок не найден в лобби: Себя":
		push_error("Команда /w допускает сообщение самому себе.")
		_finish(lobby, 1)
		return
	if LOBBY_FORMAT.parse_whisper("/w Киров привет", whisper_players, 1)["error"] != "Игрок не найден в лобби: Киров":
		push_error("Команда /w принимает часть имени вместо полного совпадения.")
		_finish(lobby, 1)
		return

	lobby._lobby_chat.set_identity(1)
	lobby._lobby_chat.set_messages([
		{"sender_user_id": 1, "username": "Я", "recipient_user_id": null, "text": "общий текст", "created_at": 1700000000.0},
		{"sender_user_id": 1, "username": "Я", "recipient_user_id": 3, "recipient_username": "Ки", "text": "секрет", "created_at": 1700000001.0},
	])
	if lobby._lobby_chat._log.text.contains("секрет") or not lobby._lobby_chat._log.text.contains("общий текст") or not lobby._lobby_chat._log.text.contains("Вы:"):
		push_error("Общая вкладка чата показывает личные сообщения или не показывает свои общие.")
		_finish(lobby, 1)
		return
	lobby._lobby_chat._on_tab_pressed("Личный")
	if not lobby._lobby_chat._log.text.contains("секрет") or lobby._lobby_chat._log.text.contains("общий текст"):
		push_error("Вкладка «Личный» не показывает личные сообщения.")
		_finish(lobby, 1)
		return

	var dialog = WORLD_DIALOG_SCRIPT.new()
	dialog.setup(false, MAIN_SCRIPT.MODE_NAMES)
	if dialog._test_check != null or not _contains_text(dialog, "Запустить мир"):
		push_error("Окно модератора должно создавать только тестовые миры и содержать кнопку запуска.")
		_finish(lobby, 1)
		return
	if dialog._mode_buttons.has("front_line") \
		or MAIN_SCRIPT.MODE_NAMES.get("front_line", "") != "Front Line" \
		or WorldModeRegistry.describe("front_line").get("module_ready", true):
		push_error("Front Line доступен для карт, но не должен запускаться до подключения игрового модуля.")
		_finish(lobby, 1)
		return
	lobby._show_new_map_setup()
	if lobby._new_map_mode.item_count != 3 \
		or lobby._new_map_mode.get_item_metadata(0) != "front_line" \
		or lobby._new_map_mode.get_item_text(0) != "Front Line":
		push_error("Front Line должен быть доступен при создании карты.")
		_finish(lobby, 1)
		return
	lobby._new_map_mode.select(0)
	lobby._update_new_map_mode_note(0)
	if not lobby._new_map_mode_note.text.contains("Front Line") \
		or not lobby._new_map_mode_note.text.contains("волны"):
		push_error("Настройка новой карты должна объяснять статус режима Front Line.")
		_finish(lobby, 1)
		return
	var selected_mode := ["front_line"]
	dialog.mode_selected.connect(func(mode: String) -> void: selected_mode[0] = mode)
	var launches := []
	dialog.launch_requested.connect(func(saved_id: int, world_name: String, test: bool) -> void: launches.append([saved_id, world_name, test]))
	dialog.show_maps([{"id": 21, "name": "Долина", "map_w": 32, "map_h": 24}])
	if not _contains_text(dialog, "Долина · 32×24"):
		push_error("Окно создания мира не показывает карты выбранного режима.")
		_finish(lobby, 1)
		return
	dialog._launch_button.pressed.emit()
	if launches.size() != 0 or not dialog._status.text.contains("Выберите карту"):
		push_error("Без выбранной карты мир не должен запускаться.")
		_finish(lobby, 1)
		return
	(dialog._map_list.get_child(0) as Button).pressed.emit()
	if dialog._launch_button.disabled:
		push_error("Кнопка запуска не активна после выбора карты.")
		_finish(lobby, 1)
		return
	dialog._launch_button.pressed.emit()
	if launches.size() != 1 or launches[0] != [21, "", true]:
		push_error("Окно создания мира не передаёт выбранную карту и тестовый флаг модератора.")
		_finish(lobby, 1)
		return
	(dialog._mode_buttons["economy"] as Button).pressed.emit()
	if selected_mode[0] != "economy" or not _contains_text(dialog, "Загружаем карты…"):
		push_error("Выбор режима в окне создания мира не запрашивает карты этого режима.")
		_finish(lobby, 1)
		return
	dialog.queue_free()

	lobby._show_account()
	if lobby._account_current_password.placeholder_text != "Текущий пароль":
		push_error("Управление аккаунтом не показывает поле текущего пароля.")
		_finish(lobby, 1)
		return
	if lobby._account_new_password.placeholder_text != "Новый пароль (6–128 символов)":
		push_error("Управление аккаунтом не показывает поле нового пароля.")
		_finish(lobby, 1)
		return

	lobby._show_login()
	lobby._remember_username_check.set_block_signals(true)
	lobby._remember_password_check.set_block_signals(true)
	lobby._remember_username_check.button_pressed = true
	lobby._remember_password_check.button_pressed = true
	lobby._username_input.text = "remembered-player"
	lobby._password_input.text = "remembered-password"
	lobby._save_login_preferences()
	lobby._username_input.text = ""
	lobby._password_input.text = ""
	lobby._remember_username_check.button_pressed = false
	lobby._remember_password_check.button_pressed = false
	lobby._load_login_preferences()
	if not _login_fields_match(lobby, "remembered-player", "remembered-password"):
		_fail_preferences(lobby, "Сохранённые имя пользователя и пароль не восстановились.")
		return
	# Выход и сброс сессии сервером возвращают на экран входа с сохранёнными данными и не стирают их.
	lobby._show_worlds()
	await get_tree().process_frame
	lobby._finish_logout()
	if not _login_fields_match(lobby, "remembered-player", "remembered-password"):
		_fail_preferences(lobby, "После выхода сохранённые имя пользователя и пароль не вернулись на экран входа.")
		return
	lobby._show_worlds()
	await get_tree().process_frame
	lobby._on_session_invalid("Сессия на сервере завершилась. Войдите в аккаунт снова.")
	if not _login_fields_match(lobby, "remembered-player", "remembered-password"):
		_fail_preferences(lobby, "После сброса сессии сохранённые имя пользователя и пароль не вернулись на экран входа.")
		return
	if not _stored_login_matches("remembered-player", "remembered-password"):
		_fail_preferences(lobby, "Выход или сброс сессии стёрли сохранённые данные входа.")
		return
	# Перезапуск клиента: новый экран входа заполняет поля из сохранённых настроек.
	var restarted = MAIN_SCRIPT.new()
	restarted._login_preferences_path = PREFERENCES_PATH
	add_child(restarted)
	await get_tree().process_frame
	var restored := _login_fields_match(restarted, "remembered-player", "remembered-password")
	restarted.queue_free()
	if not restored:
		_fail_preferences(lobby, "После перезапуска клиента поля входа не заполнились сохранёнными данными.")
		return
	lobby._remember_password_check.button_pressed = false
	lobby._save_login_preferences()
	var preferences := ConfigFile.new()
	if preferences.load(PREFERENCES_PATH) != OK:
		_fail_preferences(lobby, "Не удалось прочитать сохранённые настройки входа.")
		return
	if bool(preferences.get_value("login", "remember_password", true)) or not str(preferences.get_value("login", "password", "")).is_empty():
		_fail_preferences(lobby, "Отключение сохранения пароля не удалило его из настроек.")
		return
	_cleanup_preferences(PREFERENCES_PATH)

	print("Lobby UI smoke tests passed.")
	_finish(lobby, 0)


func _check_lobby_layout(lobby) -> bool:
	var worlds_panel: Control = lobby._worlds_list.get_parent().get_parent().get_parent()
	var account_block: Control = lobby._account_card.get_parent().get_parent()
	var top_bar: Control = lobby._lobby_status.get_parent()
	var chat: Control = lobby._lobby_chat
	var viewport: Vector2 = lobby.get_viewport_rect().size
	var panel_rect := worlds_panel.get_global_rect()
	var chat_rect := chat.get_global_rect()
	var block_rect := account_block.get_global_rect()
	var expected_panel_width := minf(333.0, maxf(180.0, viewport.x - 14.0))
	var expected_panel_height := minf(533.0, maxf(170.0, 72.0 + float(lobby._worlds.size()) * 76.0))
	var panel_ok := absf(panel_rect.size.x - expected_panel_width) < 1.0 \
		and absf(panel_rect.size.y - expected_panel_height) < 1.0 \
		and absf(panel_rect.end.x - (viewport.x - 7.0)) < 1.0 and absf(panel_rect.position.y - 7.0) < 1.0
	var chat_ok := absf(chat_rect.size.x - 580.0) < 1.0 and absf(chat_rect.size.y - 260.0) < 1.0 \
		and absf(chat_rect.end.y - (viewport.y - 7.0)) < 1.0 and absf(chat_rect.get_center().x - viewport.x * 0.5) < 1.0
	var no_overlap := chat_rect.end.x <= panel_rect.position.x and top_bar.get_global_rect().end.x <= panel_rect.position.x
	var account_ok := absf(block_rect.position.x - 7.0) < 1.0 and absf(block_rect.position.y - 7.0) < 1.0
	if not (panel_ok and chat_ok and no_overlap and account_ok):
		push_error("Адаптивная геометрия лобби неверна: панель %s, чат %s, аккаунт %s." % [
			panel_rect, chat_rect, block_rect,
		])
		return false
	return true


func _check_avatar_flow(lobby) -> bool:
	if lobby._avatar_size_message(149, 300).is_empty() or not lobby._avatar_size_message(150, 150).is_empty() \
		or not lobby._avatar_size_message(400, 200).is_empty():
		push_error("Размер фото: меньше 150 px по любой стороне должен отклоняться, 150 и больше — приниматься.")
		return false
	var source := Image.create(300, 200, false, Image.FORMAT_RGBA8)
	for x in range(300):
		for y in range(200):
			source.set_pixel(x, y, Color(1.0, 0.0, 0.0, 1.0) if x < 150 else Color(0.0, 0.0, 1.0, 1.0))
	var holder := CenterContainer.new()
	holder.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	lobby.add_child(holder)
	var dialog = AVATAR_CROP_DIALOG_SCRIPT.new()
	dialog.setup(source)
	holder.add_child(dialog)
	await get_tree().process_frame
	await get_tree().process_frame
	if dialog._crop_origin != Vector2i(75, 25) or dialog._result_image().get_size() != Vector2i(150, 150):
		push_error("По умолчанию рамка 150×150 должна стоять по центру фото 300×200.")
		holder.queue_free()
		return false
	dialog._center_crop_at(Vector2(0.0, 0.0))
	if dialog._crop_origin != Vector2i.ZERO:
		push_error("Рамка обрезки должна останавливаться у левого верхнего края фото.")
		holder.queue_free()
		return false
	dialog._center_crop_at(Vector2(9999.0, 9999.0))
	var picked: Image = dialog._result_image()
	if dialog._crop_origin != Vector2i(150, 50) or picked.get_pixel(0, 0).b < 0.9:
		push_error("Обрезка должна брать ту часть фото, которая попала в рамку.")
		holder.queue_free()
		return false
	dialog._set_scale_mode(true)
	var scaled: Image = dialog._result_image()
	if scaled.get_size() != Vector2i(150, 150) or scaled.get_pixel(0, 0).a > 0.01 or scaled.get_pixel(75, 75).a < 0.99:
		push_error("Масштабирование должно вписать всё фото в 150×150 с прозрачными полями по краям.")
		holder.queue_free()
		return false
	var confirmed_images: Array = []
	dialog.confirmed.connect(func(image: Image) -> void: confirmed_images.append(image))
	dialog._on_confirm_pressed()
	if confirmed_images.size() != 1 or (confirmed_images[0] as Image).get_size() != Vector2i(150, 150):
		push_error("Подтверждение диалога должно отдавать готовое фото 150×150.")
		holder.queue_free()
		return false
	var decoded := Image.new()
	if decoded.load_png_from_buffer((confirmed_images[0] as Image).save_png_to_buffer()) != OK or decoded.get_size() != Vector2i(150, 150):
		push_error("Готовое фото не кодируется в PNG 150×150.")
		holder.queue_free()
		return false
	holder.queue_free()
	return true


func _find_menu_button(menu, text: String) -> Button:
	for child in menu._entries_box.get_children():
		if child is Button and child.text == text:
			return child
	return null


func _find_button(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and child.text == text:
			return child
		var found := _find_button(child, text)
		if found != null:
			return found
	return null


func _menu_items(menu) -> Array:
	var items: Array = []
	for child in menu._entries_box.get_children():
		if child is Button:
			items.append([child.text, true, child.disabled])
		elif child is Label:
			items.append([child.text, false, false])
	return items


func _contains_text(node: Node, expected: String) -> bool:
	if node is Label and node.text == expected:
		return true
	if node is Button and node.text == expected:
		return true
	for child in node.get_children():
		if _contains_text(child, expected):
			return true
	return false


func _contains_fragment(node: Node, fragment: String) -> bool:
	if (node is Label or node is Button) and str(node.text).contains(fragment):
		return true
	for child in node.get_children():
		if _contains_fragment(child, fragment):
			return true
	return false


func _finish(lobby: Node, exit_code: int) -> void:
	lobby._lobby_timer.stop()
	lobby.queue_free()
	get_tree().quit(exit_code)


func _login_fields_match(lobby, username: String, password: String) -> bool:
	return is_instance_valid(lobby._username_input) and is_instance_valid(lobby._password_input) \
		and lobby._username_input.text == username and lobby._password_input.text == password


func _stored_login_matches(username: String, password: String) -> bool:
	var stored := ConfigFile.new()
	if stored.load(PREFERENCES_PATH) != OK:
		return false
	return bool(stored.get_value("login", "remember_username", false)) \
		and bool(stored.get_value("login", "remember_password", false)) \
		and str(stored.get_value("login", "username", "")) == username \
		and str(stored.get_value("login", "password", "")) == password


func _fail_preferences(lobby: Node, message: String) -> void:
	push_error(message)
	_cleanup_preferences(PREFERENCES_PATH)
	_finish(lobby, 1)


func _cleanup_preferences(path: String) -> void:
	var absolute_path := ProjectSettings.globalize_path(path)
	if FileAccess.file_exists(absolute_path):
		DirAccess.remove_absolute(absolute_path)
