# adorsys brand assets

This folder is the home for adorsys-Ireland-specific brand assets.

## Currently empty / placeholder

Until adorsys provides its own logo + favicon + letterhead, users mapped to the
adorsys company will fall back to the **SkyEngPro brand** (per the original
COMPANY_DESIGN.md "EoR co-branding" design).

## Drop these files here when ready

| filename                              | size   | purpose                  |
|---------------------------------------|--------|--------------------------|
| `logo_horizontal_color_400px.png`     | ~400×?| navbar (light bg)        |
| `logo_horizontal_white_400px.png`     | ~400×?| navbar (dark bg) — optional, defaults to color logo |
| `icon_mark_32px.png`                  | 32×32  | favicon                  |
| `letterhead_400px.png`                | 400×70 | invoice / payslip header |

## Then update `colors.yaml` (in this same folder)

Replace placeholder hex values with the official adorsys palette.

After dropping assets + updating colors.yaml, no code change needed — the
boot_session hook will automatically pick up adorsys's branding for any user
whose default Company maps to "adorsys Ireland".
