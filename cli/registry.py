# -*- coding: utf-8 -*-
from components.hero_card import render_hero_card
from components.stat_grid import render_stat_grid
from components.section_title import render_section_title


COMPONENT_REGISTRY = {
    "HeroCard": render_hero_card,
    "StatGrid": render_stat_grid,
    "SectionTitle": render_section_title,
}


def get_renderer(component_type):
    return COMPONENT_REGISTRY.get(component_type)
