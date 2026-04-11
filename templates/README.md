# CSV Import Templates

Use these CSV files to set up companies and users in ERPNext.
Fill them in, then give the file to Claude or run the import script.

## Quick start

1. Edit `users_import_template.csv` with your users
2. Edit `companies_import_template.csv` with your companies
3. Provide both files — they will be used to configure ERPNext

## Files

| File | Purpose |
|---|---|
| `companies_import_template.csv` | Create companies with country settings + branding |
| `users_import_template.csv` | Create users with roles, company access, employee records |

## Column reference

### companies_import_template.csv

| Column | Required | Description | Example |
|---|---|---|---|
| company_name | yes | Company display name | ALI Capital |
| abbreviation | yes | 3-4 letter code | ALI |
| country_template | yes | Country config key: `cameroon`, `ireland`, `germany`, `france` | cameroon |
| parent_company | no | Parent company name (for EoR partners) | skyengpro Sarl |
| letterhead_image | no | Path to letterhead logo for printed docs | /files/ALI_Capital_Letterhead.png |
| company_logo | no | Path to company logo | /files/ALI_Capital_Logo.png |

### users_import_template.csv

| Column | Required | Description | Example |
|---|---|---|---|
| email | yes | Login email | john@acme.com |
| first_name | yes | First name | John |
| last_name | yes | Last name | Doe |
| profile | yes | Access profile (see below) | Company Admin |
| company | yes | Company to restrict to | ALI Capital |
| password | no | Initial password (default: must reset via email) | Secure@2026 |
| designation | no | Job title | CEO |
| gender | no | Male / Female / Other | Male |
| date_of_birth | no | YYYY-MM-DD | 1985-03-15 |
| date_of_joining | no | YYYY-MM-DD (default: today) | 2026-01-01 |

## Available profiles

| Profile name | Use for | What they see |
|---|---|---|
| `Platform Admin` | SkyEngPro super admin | Everything |
| `SkyEngPro Finance` | SkyEngPro internal finance | Accounting, HR, Payroll, Buying, Selling |
| `SkyEngPro Project Manager` | SkyEngPro internal PM | Projects, HR |
| `SkyEngPro Tech Support` | SkyEngPro internal support | Support, Projects |
| `SkyEngPro Employee` | SkyEngPro internal employee | Self-service only |
| `Company Admin` | Independent company admin (ALI/MC) | Full business within their company |
| `Company Finance` | Independent company finance | Accounting, Buying, Selling |
| `Partner HR Manager` | EoR partner HR manager | HR, Payroll, Projects |
| `Partner Employee` | EoR partner employee | Self-service + CRM + Support |
| `Employee Self Service Profile` | Any employee (self-service) | Leave, Expenses, Payslip, Timesheet |
