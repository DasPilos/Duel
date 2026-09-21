"""Модальные окна-заглушки зданий города (кнопка 'Вернуться в город')."""
import pygame
from core import settings
from ui.hud import draw_button


class CityModalsMixin:
    """Требует rect/button-атрибуты, созданные в CityScene.__init__ для каждого здания."""

    def _draw_castle_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Главного Замка с кнопкой 'Вернуться в город'."""
        # Полупрозрачное затемнение города
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        # Окно модалки
        rect = self.castle_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (18, 24, 34, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (220, 185, 70), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        # Кнопка закрытия (крестик)
        m_pos = pygame.mouse.get_pos()
        c_hover = self.castle_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.castle_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.castle_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.castle_close_button.center))

        # Заголовок замка
        t_surf = self.large_font.render("🏰 КОРОЛЕВСКИЙ ЗАМОК РАДБУРГА", True, (255, 220, 100))
        screen.blit(t_surf, (rect.left + 30, rect.top + 24))

        sub_surf = self.badge_font.render("[ ГЛАВНАЯ ЦИТАДЕЛЬ СТОЛИЦЫ СВЕТА • 15х15 ТАЙЛОВ • ЦЕНТР: 75/70 ]", True, (130, 200, 255))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (60, 80, 105), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка статуса "Сам замок пока посетить нельзя"
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (40, 28, 22), status_box, border_radius=6)
        pygame.draw.rect(screen, (220, 140, 50), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("🔒 Сам замок пока посетить нельзя — внутренние залы закрыты на реконструкцию", True, (255, 200, 120))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок описания возможностей в будущем
        desc_top = rect.top + 155
        h1 = self.font.render("👑 Возможности при посещении замка в будущем:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, desc_top))

        features = [
            ("👑 Аудиенция у Короля Радбурга:", "Возможность брать личные поручения Короны на самые премиумные, редкие и высокооплачиваемые квесты."),
            ("📊 Жизневажные сведения о городе:", "Полная оперативная сводка: казна, склад ресурсов (дерево, камень, руда, хлеб), гарнизон и обороноспособность стен."),
            ("🏛️ Заседания Королевского Совета:", "Принятие ключевых решений по развитию города, торговле и дипломатии в Великой Войне Света и Тьмы."),
            ("🛡️ Элитная королевская гвардия:", "Возможность нанимать рыцарей света и улучшать экипировку защитников города."),
        ]

        curr_y = desc_top + 34
        for title_line, text_line in features:
            f_title = self.small_font.render(title_line, True, (100, 220, 255))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (205, 215, 225))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 26

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.castle_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.castle_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_barn_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Городского Амбара с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.barn_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (22, 22, 28, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (215, 165, 60), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.barn_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.barn_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.barn_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.barn_close_button.center))

        # Заголовок
        t_surf = self.large_font.render("🌾 ГОРОДСКОЙ АМБАР (УРОВЕНЬ 1)", True, (255, 220, 100))
        screen.blit(t_surf, (rect.left + 30, rect.top + 24))

        sub_surf = self.badge_font.render("[ ХРАНИЛИЩЕ ПРОВИЗИИ РАДБУРГА • 12х10 ТАЙЛОВ • ВХОД: 16/40 ]", True, (130, 200, 255))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (75, 70, 55), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния хранилища
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (34, 38, 26), status_box, border_radius=6)
        pygame.draw.rect(screen, (120, 180, 70), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("🍞 Статус снабжения: В достатке — жители и гарнизон обеспечены едой", True, (160, 240, 120))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок оперативной сводки по провизии
        stats_top = rect.top + 155
        h1 = self.font.render("📦 Запасы провизии города:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("🌾 Зерно и пшеница в закромах:", "650 / 1 000 мешков (заполнено на 65%)"),
            ("🍞 Запас свежего хлеба:", "420 суточных пайков"),
            ("👥 Ежедневное потребление города:", "25 ед. в день (население + ремесленники)"),
            ("🛡️ Снабжение гарнизона армии:", "100% (высокий боевой дух защитников Света)"),
            ("🚜 Источник поступлений:", "Поставки с окрестных пшеничных полей и ферм"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (255, 215, 120))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (215, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 24

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.barn_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.barn_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_warehouse_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Городского Склада с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.warehouse_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (20, 24, 30, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (100, 190, 255), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.warehouse_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.warehouse_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.warehouse_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.warehouse_close_button.center))

        # Заголовок
        t_surf = self.large_font.render("📦 ГОРОДСКОЙ СКЛАД (УРОВЕНЬ 1)", True, (255, 220, 100))
        screen.blit(t_surf, (rect.left + 30, rect.top + 24))

        sub_surf = self.badge_font.render("[ ХРАНИЛИЩЕ МАТЕРИАЛОВ РАДБУРГА • 12х10 ТАЙЛОВ • ВХОД: 16/23 ]", True, (130, 200, 255))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (60, 80, 105), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния склада
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (22, 34, 44), status_box, border_radius=6)
        pygame.draw.rect(screen, (80, 180, 240), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("🔨 Статус склада: Активен — материалы поступают с городских промыслов", True, (140, 220, 255))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок оперативной сводки по материалам
        stats_top = rect.top + 155
        h1 = self.font.render("📦 Запасы материалов города:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("🌲 Древесина строительная:", "850 / 2 000 брёвен (с окрестных лесопилок и вырубок)"),
            ("🪨 Камень тёсаный:", "620 / 2 000 блоков (добыча из каменоломен для стен и башен)"),
            ("⚫ Каменный уголь:", "310 / 1 000 мер (топливо для городских плавилен и кузниц)"),
            ("⛏️ Железная руда сырец:", "190 / 1 000 слитков (поставки с горных рудников)"),
            ("⚔️ Обработанное железо:", "75 / 500 слитков (ковка оружия, щитов и лат армии Света)"),
            ("🛡️ Назначение склада:", "Обеспечение строительства, ремонта стен и вооружения войск"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (130, 200, 255))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (215, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 24

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.warehouse_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.warehouse_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_forge_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Городской Кузницы с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.forge_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (24, 20, 20, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (255, 140, 50), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.forge_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.forge_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.forge_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.forge_close_button.center))

        # Заголовок
        t_surf = self.large_font.render("⚒️ ГОРОДСКАЯ КУЗНИЦА (УРОВЕНЬ 1)", True, (255, 220, 100))
        screen.blit(t_surf, (rect.left + 30, rect.top + 24))

        sub_surf = self.badge_font.render("[ ОРУЖЕЙНАЯ КУЗНИЦА РАДБУРГА • 9х7 ТАЙЛОВ • ВХОД: 23/28 ]", True, (255, 180, 120))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (90, 60, 50), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния кузницы
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (44, 28, 22), status_box, border_radius=6)
        pygame.draw.rect(screen, (240, 120, 40), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("🔥 Горн раскалён: Готов к ковке оружия для героев и городской армии", True, (255, 200, 120))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок описания возможностей
        stats_top = rect.top + 155
        h1 = self.font.render("⚔️ Производство оружия и вооружение города:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("⚔️ Ковка личного оружия для игроков:", "Мечи, секиры, кинжалы, посохи и булавы из добытого железа"),
            ("🛡️ Вооружение гарнизона армии:", "Ковка мечей и копий защитникам Радбурга (+20% к силе отрядов)"),
            ("⛏️ Необходимое сырьё со склада:", "Железная руда, обработанные слитки и каменный уголь"),
            ("🔨 Мастер-кузнец города:", "Готов принимать заказы на перековку и улучшение снаряжения"),
            ("📈 Улучшение кузницы (Ур. 2):", "Откроет ковку закалённой стали, тяжелых двуручников и зачарования"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (255, 170, 90))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (225, 225, 230))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 24

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.forge_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.forge_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_workshop_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Городской Мастерской с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.workshop_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (20, 24, 32, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (100, 190, 255), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.workshop_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.workshop_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.workshop_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.workshop_close_button.center))

        # Заголовок
        t_surf = self.large_font.render("🛡️ ГОРОДСКАЯ МАСТЕРСКАЯ (УРОВЕНЬ 1)", True, (255, 220, 100))
        screen.blit(t_surf, (rect.left + 30, rect.top + 24))

        sub_surf = self.badge_font.render("[ БРОННАЯ МАСТЕРСКАЯ РАДБУРГА • 9х7 ТАЙЛОВ • ВХОД: 23/16 ]", True, (140, 210, 255))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (60, 80, 105), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния мастерской
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (20, 34, 46), status_box, border_radius=6)
        pygame.draw.rect(screen, (80, 180, 240), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("🛡️ Верстаки готовы: Изготовление брони и экипировки для героев и гарнизона", True, (140, 220, 255))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок описания возможностей
        stats_top = rect.top + 155
        h1 = self.font.render("🛡️ Изготовление доспехов и брони города:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("🛡️ Крафт личной брони для игроков:", "Шлемы, кольчуги, кирасы, поножи, перчатки и щиты"),
            ("⚔️ Экипировка гарнизона города:", "Снабжение защитников Света броней (+25% к стойкости и здоровью)"),
            ("📦 Материалы со склада:", "Железо, кожа, заклепки и крепежи со складов города"),
            ("🪓 Ремонт и подгонка доспехов:", "Восстановление прочности экипировки после тяжелых походов"),
            ("📈 Улучшение мастерской (Ур. 2):", "Откроет крафт тяжелых латных комплектов и рунической брони Света"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (130, 200, 255))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (215, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 24

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.workshop_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.workshop_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_barracks_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Городских Казарм с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.barracks_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (22, 26, 32, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (80, 150, 230), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.barracks_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.barracks_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.barracks_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.barracks_close_button.center))

        # Заголовок
        t_surf = self.large_font.render("⚔️ ГОРОДСКИЕ КАЗАРМЫ (УРОВЕНЬ 1)", True, (255, 220, 100))
        screen.blit(t_surf, (rect.left + 30, rect.top + 24))

        sub_surf = self.badge_font.render("[ ВОЕННЫЙ ГАРНИЗОН РАДБУРГА • 9х13 ТАЙЛОВ • ВХОД: 84/43 ]", True, (130, 200, 255))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (60, 80, 105), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния гарнизона
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (24, 34, 46), status_box, border_radius=6)
        pygame.draw.rect(screen, (70, 140, 220), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("🛡️ Гарнизон на боевом дежурстве: Солдаты содержатся и несут службу на стенах", True, (160, 220, 255))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок оперативной сводки по войскам
        stats_top = rect.top + 155
        h1 = self.font.render("⚔️ Содержание и численность солдат гарнизона:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("👥 Регулярные солдаты гарнизона:", "120 / 200 бойцов (пехотинцы, мечники, копейщики)"),
            ("🏹 Стрелки и стражи стен:", "60 / 100 лучников на крепостных стенах и башнях"),
            ("🍞 Снабжение провизией из амбара:", "100% суточного довольствия (боеготовность максимальная)"),
            ("⚔️ Оснащение оружием и броней:", "Кузница и мастерская обеспечивают +20% к боевой мощи"),
            ("🎖️ Назначение казарм:", "Оборона ворот города, отражение штурмов и марш армий Света"),
            ("📈 Улучшение казарм (Ур. 2):", "Увеличит вместимость до 500 бойцов и откроет наём тяжелых рыцарей"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (100, 220, 255))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (215, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 24

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.barracks_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.barracks_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_engineering_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Инженерной палаты с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.engineering_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (20, 26, 28, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (100, 210, 190), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.engineering_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.engineering_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.engineering_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.engineering_close_button.center))

        # Заголовок
        t_surf = self.large_font.render("⚙️ ИНЖЕНЕРНАЯ ПАЛАТА (УРОВЕНЬ 1)", True, (255, 220, 100))
        screen.blit(t_surf, (rect.left + 30, rect.top + 24))

        sub_surf = self.badge_font.render("[ ЦЕХ ОБОРОННЫХ СООРУЖЕНИЙ И ОСАДНЫХ МАШИН • 10х8 ТАЙЛОВ • ВХОД: 44/15 ]", True, (130, 200, 255))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (60, 90, 85), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния цеха
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (22, 36, 36), status_box, border_radius=6)
        pygame.draw.rect(screen, (80, 200, 170), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("🔨 Цех инженеров активен: Чертежи и станки подготовлены к сборке боевых машин", True, (150, 235, 215))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок описания возможностей
        stats_top = rect.top + 155
        h1 = self.font.render("🎯 Производство боевых машин и осадной техники:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("🎯 Катапульта полевая:", "Метание зажигательных снарядов и камней по вражеским укреплениям"),
            ("🪵 Осадный таран:", "Пробитие ворот и укреплений противника в наступлении армий Света"),
            ("🏹 Тяжелый требушет:", "Сверхдальнобойная артиллерия для сокрушения цитаделей Тьмы"),
            ("🧱 Оборонные турели и баллисты:", "Усиление гарнизона и огневой мощи крепостных стен города"),
            ("📦 Требуемые ресурсы со склада:", "Древесина, камень, обработанное железо и канаты"),
            ("📈 Улучшение палаты (Ур. 2):", "Откроет автоматические многозарядные баллисты и бронированные башни"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (120, 225, 210))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (215, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 24

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.engineering_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.engineering_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_university_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Городского Университета с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.university_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (20, 26, 36, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (120, 190, 255), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.university_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.university_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.university_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.university_close_button.center))

        # Заголовок
        t_surf = self.large_font.render("🏛️ ГОРОДСКОЙ УНИВЕРСИТЕТ (УРОВЕНЬ 1)", True, (255, 220, 100))
        screen.blit(t_surf, (rect.left + 30, rect.top + 24))

        sub_surf = self.badge_font.render("[ АКАДЕМИЯ ТЕХНОЛОГИЙ И НАУК РАДБУРГА • 15х11 ТАЙЛОВ • ВХОД: 23/84 ]", True, (130, 200, 255))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (60, 80, 110), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния исследований
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (20, 32, 48), status_box, border_radius=6)
        pygame.draw.rect(screen, (80, 160, 240), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("📖 Академия активна: Учёные и архимаги исследуют новые технологии города", True, (160, 225, 255))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок описания возможностей
        stats_top = rect.top + 155
        h1 = self.font.render("🔬 Изучение новых технологий и научных открытий:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("⛏️ Горное дело и металлургия:", "+15% к добыче железной руды и качеству выплавки слитков"),
            ("🧱 Фортификация и зодчество:", "+20% к прочности крепостных стен, башен и ворот города"),
            ("🌾 Селекция и агрономия:", "Повышение урожайности пшеничных полей и вместимости амбаров"),
            ("⚔️ Военное искусство и тактика:", "Увеличение атаки и защиты гарнизона регулярной армии"),
            ("📜 Свитки древних знаний:", "Открытие редких рецептов крафта, чар и рунических печатей"),
            ("📈 Улучшение университета (Ур. 2):", "Откроет высшую алхимию, зачарование экипировки и магические башни"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (130, 210, 255))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (215, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 24

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.university_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.university_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_academy_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Военной академии с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.academy_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (26, 20, 22, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (220, 90, 70), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.academy_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.academy_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.academy_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.academy_close_button.center))

        # Заголовок
        t_surf = self.large_font.render("⚔️ ВОЕННАЯ АКАДЕМИЯ (УРОВЕНЬ 1)", True, (255, 220, 100))
        screen.blit(t_surf, (rect.left + 30, rect.top + 24))

        sub_surf = self.badge_font.render("[ ЦЕНТР ОБУЧЕНИЯ ВОИНОВ И ПРОКАЧКИ КАРТ • 10х7 ТАЙЛОВ • ВХОД: 19/73 ]", True, (255, 180, 150))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (90, 60, 65), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния академии
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (42, 24, 28), status_box, border_radius=6)
        pygame.draw.rect(screen, (220, 80, 70), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("⚔️ Академия открыта: Место тренировки бойцов, развития талантов и усиления карт", True, (255, 190, 180))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок описания возможностей
        stats_top = rect.top + 155
        h1 = self.font.render("🥋 Обучение воинов и прокачка карт силовой линии:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("⚔️ Прокачка карт силовой линии:", "Повышение урона, снижение стоимости и открытие комбо-эффектов боевых карт"),
            ("🌲 Ветви талантов бойца:", "Развитие направлений: Несокрушимый защитник, Берсерк ярости, Мастер клинка"),
            ("🎴 Открытие новых боевых карт:", "Изучение приёмов: Сокрушительный удар, Парирование, Боевой клич, Раскол брони"),
            ("🥊 Тренировочные спарринги:", "Отработка тактики боя на полигоне с инструкторами академии"),
            ("🛡️ Подготовка элитных командиров:", "Повышение выучки офицеров гарнизона (+15% к дисциплине отрядов)"),
            ("📈 Улучшение академии (Ур. 2):", "Откроет доступ к легендарным картам стоек и ультимативным приёмам"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (255, 160, 140))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 20
            f_desc = self.grid_font.render(text_line, True, (225, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 24

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.academy_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.academy_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))

    def _draw_mage_school_modal(self, screen):
        """Отрисовывает модальное меню-заглушку Школы стихий с кнопкой 'Вернуться в город'."""
        overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 215))
        screen.blit(overlay, (0, 0))

        rect = self.mage_school_modal_rect
        modal_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(modal_surf, (22, 18, 34, 250), (0, 0, rect.width, rect.height), border_radius=12)
        pygame.draw.rect(modal_surf, (180, 110, 255), (0, 0, rect.width, rect.height), width=2, border_radius=12)
        screen.blit(modal_surf, rect.topleft)

        m_pos = pygame.mouse.get_pos()
        c_hover = self.mage_school_close_button.collidepoint(m_pos)
        pygame.draw.rect(screen, (160, 45, 45) if c_hover else (45, 30, 35), self.mage_school_close_button, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.mage_school_close_button, 1, border_radius=4)
        x_surf = self.small_font.render("✕", True, (255, 255, 255))
        screen.blit(x_surf, x_surf.get_rect(center=self.mage_school_close_button.center))

        # Заголовок
        t_surf = self.large_font.render("🔮 ШКОЛА СТИХИЙ (УРОВЕНЬ 1)", True, (255, 220, 100))
        screen.blit(t_surf, (rect.left + 30, rect.top + 24))

        sub_surf = self.badge_font.render("[ ЦЕНТР ОБУЧЕНИЯ МАГИИ И ПРОКАЧКИ МАГИЧЕСКИХ КАРТ • 15х9 ТАЙЛОВ • ВХОД: 44/66 ]", True, (210, 175, 255))
        screen.blit(sub_surf, (rect.left + 30, rect.top + 58))

        pygame.draw.line(screen, (85, 60, 110), (rect.left + 24, rect.top + 84), (rect.right - 24, rect.top + 84), 1)

        # Плашка состояния школы
        status_box = pygame.Rect(rect.left + 30, rect.top + 98, rect.width - 60, 40)
        pygame.draw.rect(screen, (34, 24, 52), status_box, border_radius=6)
        pygame.draw.rect(screen, (180, 100, 255), status_box, 1, border_radius=6)
        notice_txt = self.small_font.render("✨ Школа стихий открыта: Постижение тайных знаний, концентрация маны и усиление заклинаний", True, (225, 195, 255))
        screen.blit(notice_txt, notice_txt.get_rect(center=status_box.center))

        # Блок описания возможностей
        stats_top = rect.top + 155
        h1 = self.font.render("⚡ Обучение магии и развитие стихийных карт:", True, (255, 230, 140))
        screen.blit(h1, (rect.left + 30, stats_top))

        stat_lines = [
            ("🔥 Стихия Огня:", "Прокачка атакующих карт пламени, взрывов, ожогов и огненного шара"),
            ("💧 Стихия Воды:", "Изучение исцеляющих потоков, ледяных оков и очищения разума"),
            ("🌪️ Стихия Воздуха:", "Увеличение скорости каста, молнии, цепные разряды и уклонение"),
            ("🌿 Стихия Земли:", "Каменная кожа, шипы, защитные барьеры и землетрясения"),
            ("✨ Стихия Света:", "Божественные благословения, экзорцизм и рассеивание чар Тьмы"),
            ("🎴 Прокачка магических карт:", "Снижение расхода маны карт заклинаний, увеличение урона и длительности эффектов"),
            ("📈 Улучшение школы (Ур. 2):", "Откроет создание комбинированных стихийных заклинаний и ритуальные круги"),
        ]

        curr_y = stats_top + 34
        for title_line, text_line in stat_lines:
            f_title = self.small_font.render(title_line, True, (200, 160, 255))
            screen.blit(f_title, (rect.left + 40, curr_y))
            curr_y += 19
            f_desc = self.grid_font.render(text_line, True, (225, 225, 235))
            screen.blit(f_desc, (rect.left + 50, curr_y))
            curr_y += 22

        # Кнопка: [ ВЕРНУТЬСЯ В ГОРОД ]
        btn_hover = self.mage_school_back_button.collidepoint(m_pos)
        btn_col = (70, 130, 200) if btn_hover else (45, 85, 140)
        draw_button(screen, self.mage_school_back_button, "ВЕРНУТЬСЯ В ГОРОД", self.font, color=btn_col, text_color=(255, 255, 255))
