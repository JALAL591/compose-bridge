# -*- coding: utf-8 -*-


def render_section_title(props):
    text = props.get("text", "")

    return f"""SectionTitle(
    text = "{text}",
)
"""
