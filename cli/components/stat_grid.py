# -*- coding: utf-8 -*-


def color_to_kotlin(color_name):
    mapping = {
        "primary": "Primary",
        "accent_orange": "AccentOrange",
        "accent_green": "AccentGreen",
        "accent_purple": "AccentPurple",
    }
    return mapping.get(color_name, "Primary")


def render_stat_grid(props):
    columns = props.get("columns", 3)
    items = props.get("items", [])

    rows = [items[i:i + columns] for i in range(0, len(items), columns)]

    rows_code = []
    for row in rows:
        cards = []
        for item in row:
            icon = item.get("icon", "Star")
            color = color_to_kotlin(item.get("color", "primary"))
            value = item.get("value", "")
            label = item.get("label", "")

            cards.append(f"""Box(modifier = Modifier.weight(1f)) {{
    StatCard(
        icon = Icons.Default.{icon},
        accentColor = AppColors.{color},
        value = "{value}",
        label = "{label}",
    )
}}""")

        cards_joined = "\n".join("    " + line for line in "\n".join(cards).split("\n"))
        rows_code.append(f"""Row(
    modifier = Modifier
        .fillMaxWidth()
        .padding(horizontal = AppDimens.screenPadding),
    horizontalArrangement = Arrangement.spacedBy(AppDimens.sm),
) {{
{cards_joined}
}}""")

    separator = "\nSpacer(Modifier.height(AppDimens.sm))\n"
    return separator.join(rows_code) + "\n"
