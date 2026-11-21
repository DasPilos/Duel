extends "res://scripts/material_contribution_dialog.gd"

# Диалог монет казны из ui/castle_window.py (_draw_treasury_transfer): та же шкала, подписи монет, без веса и заметки.
const CURRENCY_SCRIPT := preload("res://scripts/currency_format.gd")
const TREASURY_TITLES := {"deposit": "Внести монеты в казну", "withdraw": "Забрать монеты из казны"}
const TREASURY_AVAILABLE_Y := 60.0
const TREASURY_CHOSEN_Y := 88.0
const TREASURY_CONFIRM_TEXT := "ПЕРЕВЕСТИ"


func _refresh() -> void:
	_title.text = str(TREASURY_TITLES.get(_mode, TREASURY_TITLES["deposit"]))
	_available_label.text = "Доступно: %s" % CURRENCY_SCRIPT.format_amount(_available)
	_available_label.position.y = TREASURY_AVAILABLE_Y
	_chosen_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	_chosen_label.position.y = TREASURY_CHOSEN_Y
	_chosen_label.text = "Перевести: %s / %s" % [
		CURRENCY_SCRIPT.format_amount(_quantity), CURRENCY_SCRIPT.format_amount(_maximum)]
	_weight_label.visible = false
	_note_label.visible = false
	_confirm_button.text = TREASURY_CONFIRM_TEXT
	_confirm_button.disabled = _quantity <= 0
	_frame.queue_redraw()
