# SkyEngPro — Test Users

**URL:** https://erp.homelab.local

> **WARNING:** These are test/dev credentials. Rotate ALL passwords before
> any production use. Never commit production credentials to git.

---

## Platform Super Admin

| Field | Value |
|---|---|
| Email | `yannick.siewe@gmail.com` |
| Password | `changeit` *(bootstrap — rotate immediately)* |
| Full name | Yannick Siewe |
| Profile | Platform Admin (no restrictions) |
| Company access | ALL companies |
| Employee record | No |

---

## EoR Partner: adorsys

### HR Manager

| Field | Value |
|---|---|
| Email | `lausonobase.odine@adorsys.com` |
| Password | `Adorsys@2026` |
| Full name | Lausonobase Odine |
| Profile | Partner HR Manager |
| Company access | adorsys only |
| Employee record | Yes (HR Manager, adorsys) |
| Roles | HR Manager, HR User, Leave Approver, Expense Approver, Employee |

### Employee

| Field | Value |
|---|---|
| Email | `ysi@adorsys.com` |
| Password | `Adorsys@2026` |
| Full name | Yannick Siewe |
| Profile | Employee Self Service Profile |
| Company access | adorsys only |
| Employee record | Yes (Software Engineer, adorsys) |
| Roles | Employee, Projects User |

---

## Independent Companies

### ALI Capital

| Status | Created (no users yet) |
|---|---|
| Company | ALI Capital |
| Country | Cameroon |
| Currency | XAF |

*To add an admin user:*
```python
from skyengpro_brand.onboarding import add_user, add_employee
add_user("admin@alicapital.com", "FirstName", "LastName",
         profile="Company Admin", company="ALI Capital", password="Secure@2026")
add_employee("admin@alicapital.com", "ALI Capital", designation="CEO")
```

### MC Capital

| Status | Created (no users yet) |
|---|---|
| Company | MC Capital |
| Country | Cameroon |
| Currency | XAF |

*To add an admin user:*
```python
from skyengpro_brand.onboarding import add_user, add_employee
add_user("admin@mccapital.com", "FirstName", "LastName",
         profile="Company Admin", company="MC Capital", password="Secure@2026")
add_employee("admin@mccapital.com", "MC Capital", designation="CEO")
```

---

## What each user can test

| Login as | Test these features |
|---|---|
| `yannick.siewe@gmail.com` | Full admin: see all companies, all data, all settings |
| `lausonobase.odine@adorsys.com` | HR Manager view: manage adorsys employees, approve leaves/expenses, run payroll, manage projects. Verify: cannot see SkyEngPro/ALI/MC data |
| `ysi@adorsys.com` | Employee self-service: apply for leave, submit expenses, view own payslip, log timesheets. Verify: cannot see other employees' data |

---

## Password policy

All test passwords follow the pattern: `<CompanyName>@2026`

For production:
- Minimum 12 characters
- Must contain uppercase, lowercase, number, special character
- Enforce via ERPNext: Settings → System Settings → Password Policy
- Enable 2FA: Settings → System Settings → Enable Two Factor Auth

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-09 | Created admin user during ERPNext setup |
| 2026-04-10 | Created adorsys HR Manager + Employee |
| 2026-04-11 | Created ALI Capital + MC Capital companies (no users yet) |
