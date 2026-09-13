import pygame

from ui.hud import draw_button, draw_text


class AwakeningAltarRenderer:
	def __init__(self, scene):
		self.scene = scene

	def update(self, dt):
		return None

	def draw(self, screen):
		scene = self.scene
		screen.fill((25, 20, 35))
		draw_text(screen, scene.title_font, "РИТУАЛЬНЫЙ АЛТАРЬ ПРОБУЖДЕНИЯ", 560, 60, (200, 150, 255))
		pygame.draw.rect(screen, (40, 35, 50), scene.application_frame, width=2, border_radius=8)
		draw_text(screen, scene.font, "МАГИЧЕСКИЕ ДУЭЛИ", scene.application_frame.x + 25, scene.application_frame.y + 20, (200, 150, 255))
		offers = scene._application_offers()
		if offers:
			for index, offer in enumerate(offers):
				draw_text(screen, scene.small_font, f"{offer.get('sender', 'Маг')} предлагает дуэль", scene.duel_list_rect.x + 12, scene.duel_list_rect.y + 42 + index * 42, (230, 210, 255))
		else:
			draw_text(screen, scene.small_font, "Нет активных вызовов", scene.duel_list_rect.x + 10, scene.duel_list_rect.y + 40, (150, 150, 150))
		draw_text(screen, scene.small_font, "Нет активных групп", scene.group_list_rect.x + 10, scene.group_list_rect.y + 40, (150, 150, 150))
		draw_button(screen, scene.application_button, "ВЫЗВАТЬ", scene.small_font, color=(150, 100, 200))
		draw_button(screen, scene.group_battle_button, "ГРУППА", scene.small_font, color=(150, 100, 200))
		draw_button(screen, scene.accept_application_button, "ПРИНЯТЬ", scene.small_font, color=(100, 180, 120))
