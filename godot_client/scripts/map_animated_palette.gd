extends ItemList

const BADGE_FONT_SIZE := 10
const BADGE_OUTLINE := Color8(20, 22, 26)


func _draw() -> void:
	var font := get_theme_default_font()
	for index in item_count:
		var item_rect := get_item_rect(index)
		var icon_size := Vector2(fixed_icon_size)
		var icon_position := item_rect.position + Vector2(
			maxf((item_rect.size.x - icon_size.x) * 0.5, 0.0),
			0.0,
		)
		var baseline := icon_position + Vector2(3.0, icon_size.y - 3.0)
		draw_string(font, baseline + Vector2(-1.0, 0.0), "A", HORIZONTAL_ALIGNMENT_LEFT, -1, BADGE_FONT_SIZE, BADGE_OUTLINE)
		draw_string(font, baseline + Vector2(1.0, 0.0), "A", HORIZONTAL_ALIGNMENT_LEFT, -1, BADGE_FONT_SIZE, BADGE_OUTLINE)
		draw_string(font, baseline + Vector2(0.0, -1.0), "A", HORIZONTAL_ALIGNMENT_LEFT, -1, BADGE_FONT_SIZE, BADGE_OUTLINE)
		draw_string(font, baseline + Vector2(0.0, 1.0), "A", HORIZONTAL_ALIGNMENT_LEFT, -1, BADGE_FONT_SIZE, BADGE_OUTLINE)
		draw_string(font, baseline, "A", HORIZONTAL_ALIGNMENT_LEFT, -1, BADGE_FONT_SIZE, Color.WHITE)
