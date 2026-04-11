# SkyEngPro — Test Users

**URL:** https://erp.homelab.local

> **WARNING:** These are test/dev credentials. Rotate ALL passwords before
> any production use. Never commit production credentials to git.

---

## Platform Super Admin

| Email | Password | Profile | Company |
|---|---|---|---|
| `yannick.siewe@gmail.com` | `changeit` *(rotate!)* | Platform Admin | ALL |

---

## EoR Partner: adorsys

| Email | Password | Profile | Role |
|---|---|---|---|
| `lausonobase.odine@adorsys.com` | `Adorsys@2026` | Partner HR Manager | HR Manager |
| `ysi@adorsys.com` | `Adorsys@2026` | Employee Self Service | Employee |

---

## ALI Capital (standalone)

| Email | Password | Profile | Role |
|---|---|---|---|
| `admin@alicapital.cm` | `AliCapital@2026` | Company Admin | CEO |
| `finance@alicapital.cm` | `AliCapital@2026` | Company Finance | Finance Manager |
| `employee@alicapital.cm` | `AliCapital@2026` | Employee Self Service | Analyst |

---

## MC Capital (standalone)

| Email | Password | Profile | Role |
|---|---|---|---|
| `admin@mccapital.cm` | `McCapital@2026` | Company Admin | CEO |
| `finance@mccapital.cm` | `McCapital@2026` | Company Finance | Finance Manager |
| `employee@mccapital.cm` | `McCapital@2026` | Employee Self Service | Analyst |

---

## What each profile can test

| Profile | Login as | Test |
|---|---|---|
| **Platform Admin** | `yannick.siewe@gmail.com` | See all companies, all data, all settings |
| **Company Admin** | `admin@alicapital.cm` | Full business: HR, accounting, CRM, projects. Verify: cannot see MC Capital or adorsys data |
| **Company Finance** | `finance@alicapital.cm` | Accounting, buying, selling. Verify: no HR management, no CRM |
| **Partner HR Manager** | `lausonobase.odine@adorsys.com` | HR, payroll, projects. Verify: no accounting, cannot see SkyEngPro/ALI/MC data |
| **Employee** | `employee@alicapital.cm` | Leave, expenses, payslip, timesheets. Verify: sees only own data |

## Data isolation test checklist

- [ ] `admin@alicapital.cm` can see ALI Capital employees but NOT MC Capital or adorsys
- [ ] `admin@mccapital.cm` can see MC Capital employees but NOT ALI Capital or adorsys
- [ ] `lausonobase.odine@adorsys.com` can see adorsys employees but NOT ALI/MC/SkyEngPro
- [ ] `employee@alicapital.cm` can see ONLY their own leave/expenses/payslip
- [ ] `yannick.siewe@gmail.com` can see ALL companies, ALL employees

---

## Password policy

Pattern: `<CompanyName>@2026`

For production:
- Minimum 12 characters
- Enforce via: Settings → System Settings → Password Policy
- Enable 2FA: Settings → System Settings → Enable Two Factor Auth

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-09 | Created admin user during ERPNext setup |
| 2026-04-10 | Created adorsys HR Manager + Employee |
| 2026-04-11 | Created ALI Capital + MC Capital companies + 6 users (admin, finance, employee each) |
