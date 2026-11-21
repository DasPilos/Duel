extends RefCounted

# Чистые функции лобби: даты, статусы миров и разбор «/w имя текст». Без узлов сцены, поэтому тестируются отдельно.


static func local_datetime_text(unix_time: float) -> String:
	var parts := Time.get_datetime_dict_from_unix_time(int(unix_time) + _local_offset_seconds())
	return "%02d.%02d.%04d %02d:%02d" % [parts.day, parts.month, parts.year, parts.hour, parts.minute]


static func local_time_text(unix_time: float) -> String:
	var parts := Time.get_datetime_dict_from_unix_time(int(unix_time) + _local_offset_seconds())
	return "%02d:%02d" % [parts.hour, parts.minute]


static func world_status_text(world: Dictionary) -> String:
	if not bool(world.get("is_open", false)):
		return "закрыт"
	if text_field(world, "server_url").is_empty():
		return "не запущен"
	return "работает"


static func world_started_text(world: Dictionary) -> String:
	var started: Variant = world.get("started_at")
	if is_timestamp(started):
		return "запущен " + local_datetime_text(float(started))
	if text_field(world, "server_url").is_empty():
		return "не запущен"
	return "запущен"


static func world_end_text(world: Dictionary) -> String:
	var closes: Variant = world.get("closes_at")
	if is_timestamp(closes):
		return "до " + local_datetime_text(float(closes))
	if text_field(world, "mode") == "front_line":
		return "до исхода матча"
	return "бессрочный"


static func text_field(data: Dictionary, key: String) -> String:
	var value: Variant = data.get(key)
	return str(value).strip_edges() if value is String else ""


static func is_timestamp(value: Variant) -> bool:
	return value is float or value is int


# Разбирает «/w <имя> текст». Имя ищется среди игроков лобби, самое длинное совпадение побеждает.
# Возвращает словарь с ключами error (пусто при успехе), user_id, username, message.
static func parse_whisper(text: String, players: Array, own_user_id: int) -> Dictionary:
	var body := text.substr(2).strip_edges()
	if body.is_empty():
		return {"error": "Формат: /w <имя> текст"}
	var candidates: Array = []
	for player in players:
		if player is Dictionary and int(player.get("user_id", 0)) != own_user_id:
			candidates.append(player)
	candidates.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return str(a.get("username", "")).length() > str(b.get("username", "")).length()
	)
	for player in candidates:
		var name := str(player.get("username", ""))
		if name.is_empty() or body.substr(0, name.length()).to_lower() != name.to_lower():
			continue
		var rest := body.substr(name.length())
		if not rest.is_empty() and not rest[0] in [" ", "\t"]:
			continue
		var message := rest.strip_edges()
		if message.is_empty():
			return {"error": "Введите текст сообщения после имени"}
		return {
			"error": "",
			"user_id": int(player.get("user_id", 0)),
			"username": name,
			"message": message,
		}
	return {"error": "Игрок не найден в лобби: %s" % body.split(" ", false)[0]}


static func _local_offset_seconds() -> int:
	var utc_parts := Time.get_datetime_dict_from_system(true)
	var local_parts := Time.get_datetime_dict_from_system(false)
	return Time.get_unix_time_from_datetime_dict(local_parts) - Time.get_unix_time_from_datetime_dict(utc_parts)
