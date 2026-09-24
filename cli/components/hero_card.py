# -*- coding: utf-8 -*-


def render_hero_card(props):
    title = props.get("title", "")
    subtitle = props.get("subtitle", "")
    progress = props.get("progress", 0.0)
    icon = props.get("icon", "Star")

    return f"""HeroCard(
    title = "{title}",
    subtitle = "{subtitle}",
    progress = {progress}f,
    icon = Icons.Default.{icon},
    modifier = Modifier
        .fillMaxWidth()
        .padding(horizontal = AppDimens.screenPadding),
)
"""
