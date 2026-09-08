# J-Noon Flooring Specialist

Marketing and customer-account website for a floor-laying business serving
Chelmsford, Essex. Built with Django 6.1 and PostgreSQL.

The codebase is structured so the same foundation — accounts, security,
admin, page framework — can be re-skinned and re-used for other flooring
firms with only branding, content and configuration changes.

---

## Contents

- [Overview](#overview)
- [Technology](#technology)
- [Features](#features)
- [Security](#security)
- [Project structure](#project-structure)
- [Local development setup](#local-development-setup)
- [Configuration](#configuration)
- [Database](#database)
- [Email](#email)
- [Running the test suite](#running-the-test-suite)
- [Production deployment](#production-deployment)
- [Re-using this design for another firm](#re-using-this-design-for-another-firm)
- [Roadmap](#roadmap)
- [Licence](#licence)

---

## Overview

A multi-page Django site with:

- Public pages (home, work gallery, bookings — currently placeholders being
  built out).
- A full customer account system: registration, login, logout, password
  reset by email, and an editable user profile with avatar upload.
- The Django admin for staff.

Customer data is held in a managed PostgreSQL database (Neon). All
configuration and secrets are supplied through environment variables — no
credentials live in the repository.

---

## Technology

| Layer | Choice |
| --- | --- |
| Language | Python 3.12 |
| Framework | Django 6.1 |
| Database | PostgreSQL (Neon, free tier) in all environments; SQLite fallback for offline local work |
| DB driver | psycopg 3 |
| Config | `.env` via `python-dotenv` (`override=True`) + `dj-database-url` |
| Images | Pillow (upload validation) |
| Email | Provider-agnostic SMTP via Django 6.1 `MAILERS` (`EMAIL_HOST` / `PORT` / `USER` / `PASSWORD`); console backend when unconfigured |
| Front end | Server-rendered Django templates, hand-written CSS/JS per app, no build step |

Dependencies are pinned in `requirements.txt`.

---

## Features

### Public site (`core`, `gallery`, `bookings`)

- Shared `base.html` layout: walnut header with a collapsible navigation
  menu, centred site title, user badge, and footer.
- Context-aware navigation — the current page is hidden from the menu, and
  the menu shows *Login / Register* or *Logout* depending on auth state.
- Per-page CSS and JS, namespaced by app.
- `gallery` and `bookings` are wired routes with placeholder content,
  ready to be built out.

### Accounts (`accounts`)

| Route | Purpose |
| --- | --- |
| `/accounts/register/` | Create an account — email, username, password, confirm password |
| `/accounts/login/` | Log in with **username or email** |
| `/accounts/logout/` | Log out (POST only) |
| `/accounts/profile/` | Edit your own profile |
| `/accounts/password-reset/` | Request a reset link by email |
| `/accounts/reset/<uidb64>/<token>/` | Set a new password from an emailed link |

- **Custom user model** (`accounts.User`) with a unique, required email
  address.
- **Show / hide password** toggle on the registration form.
- **Profile**: display name (username), profile image, pronouns, contact
  phone and email, an "about me" section, and social links
  (Facebook, Instagram, LinkedIn, website). One profile per user, created
  automatically on registration.
- The uploaded avatar replaces the default icon beside the username in the
  site header.

### Admin

- Django admin at `/admin/` with the custom user and an inline profile
  editor.

---

## Security

Security is a primary design goal of this project. What is implemented
today, grouped by concern:

### Secrets and configuration

- `SECRET_KEY`, database URL and email credentials are read from the
  environment. The app refuses to start if `DJANGO_SECRET_KEY` is missing.
- `.env` is git-ignored; `.env.example` documents the required keys without
  values.
- In development the `.env` file is the single source of truth (loaded with
  `override=True`). Production ships no `.env` file, so the host's real
  environment variables are used directly.

### Authentication and sessions

- Custom user model with a unique, required email — one account per email
  address, enforced at the database level.
- Login accepts a username **or** an email address, resolved by a custom
  authentication backend (`accounts.backends.UsernameOrEmailBackend`).
- The backend runs a dummy password hash when the account is not found, so
  response timing does not reveal whether a username/email exists.
- Sessions use Django's signed, server-side session store. The session
  cookie is `HttpOnly` and `SameSite=Lax`.
- Logout is **POST only** and CSRF-protected — it cannot be triggered by a
  link, image, or third-party page.

### Passwords

- Hashed with PBKDF2-SHA256 (Django's default, hundreds of thousands of
  iterations) with a per-user salt. Plain-text passwords are never stored
  or logged.
- Four validators run on every password set or change:
  1. not too similar to the username or email;
  2. not a known common password;
  3. not entirely numeric;
  4. **project policy** (`accounts.validators.SixToTwelvePasswordValidator`):
     6–12 characters, at least one number, at least one special character.
- The same policy is enforced on registration, on password change, and on
  password reset.

### Account enumeration

- **Login**: a wrong username/email *or* password returns a single generic
  message — "Username/email or password is incorrect." — and clears both
  fields. It never reveals which was wrong.
- **Password reset**: the "check your email" page is shown for every
  submission, whether or not the address is registered. Email send failures
  are swallowed (and logged server-side) so they cannot leak information
  either.
- **Registration**: a duplicate email is reported so the user can recover
  their account, but the message is deliberately neutral.

### Access control / authorisation

- The profile page is `@login_required` and **always operates on
  `request.user`**. There is no user id, primary key, username or other
  identifier anywhere in a profile URL, form field, or hidden input —
  so one account cannot view or modify another (no IDOR / horizontal
  privilege escalation).
- Profiles are private: there are no public profile pages.

### Input handling and injection

- **SQL injection**: all database access goes through the Django ORM. There
  is no raw SQL, string-formatted query, or `.extra()` / `.raw()` anywhere
  in the codebase.
- **Cross-site scripting (XSS)**: Django template auto-escaping is on for
  all user-supplied content. The one `autoescape off` block is a plain-text
  password-reset email that contains no user input.
- **Cross-site request forgery (CSRF)**: `CsrfViewMiddleware` is enabled and
  every state-changing form (`register`, `login`, `logout`, `profile`,
  password reset) submits a `{% csrf_token %}`.
- **Mass assignment**: forms declare an explicit field list; the profile
  form separates the editable `username` from account-security concerns.
- Request body size is capped (`DATA_UPLOAD_MAX_MEMORY_SIZE`,
  `FILE_UPLOAD_MAX_MEMORY_SIZE`).

### File uploads (profile images)

- **Type is verified by parsing the file with Pillow**, not by trusting the
  file extension or the browser-supplied content type. Only real PNG and
  JPEG images are accepted; a renamed `.png`, a BMP, a GIF, or a text file
  are all rejected.
- Hard **1 MB size limit**, checked before the file is parsed.
- Stored under a random UUID filename (`profile_images/<uuid>.png`), so the
  media path exposes no user identifier and images cannot be enumerated.
- Client-side pre-check and live preview for fast feedback; the server-side
  validation is always authoritative.

### Transport and headers

- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` (clickjacking
  protection) and `Cross-Origin-Opener-Policy: same-origin` are sent on
  every response (Django 6.1 defaults, middleware enabled).
- The Neon PostgreSQL connection string uses `sslmode=require`, so all
  database traffic is encrypted in transit.

### Production hardening checklist

The following are **not** enabled in the committed settings because
`DEBUG=True` is the local-development default. They must be applied before
the site is public — see [Production deployment](#production-deployment):

- `DEBUG = False`
- `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` set to the real domain(s)
- `SECURE_SSL_REDIRECT = True`
- `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`
- `SECURE_HSTS_SECONDS` (with `SECURE_HSTS_INCLUDE_SUBDOMAINS`,
  `SECURE_HSTS_PRELOAD`)
- Move the admin off the default `/admin/` path
- Serve `/media/` from a dedicated file store, not Django
- Shorten `PASSWORD_RESET_TIMEOUT` from the 3-day default if desired

`python manage.py check --deploy` reports on most of these.

---

## Project structure

```
J-Flooring-Specialist/
├── config/                 # project settings, root URLconf, WSGI/ASGI
│   ├── settings.py
│   └── urls.py
├── core/                   # shared base template, home page, site chrome
│   ├── templates/core/     # base.html, _avatar.html, home.html
│   └── static/core/        # base.css / base.js, home.css / home.js
├── accounts/               # user model, auth, profiles
│   ├── models.py           # User, Profile
│   ├── backends.py         # username-or-email authentication
│   ├── validators.py       # password policy + profile-image validation
│   ├── forms.py            # RegisterForm, LoginForm, ProfileForm
│   ├── signals.py          # auto-create Profile for new users
│   ├── views.py
│   ├── migrations/
│   ├── templates/accounts/ # login, register, logout, profile, reset flow
│   └── static/accounts/    # auth.css, profile.css, page JS
├── gallery/                # work gallery (placeholder route)
├── bookings/               # bookings (placeholder route)
├── manage.py
├── requirements.txt
├── .env.example
└── README.md
```

Uploaded files live in `media/` (git-ignored). Collected static files go to
`staticfiles/` on deploy (git-ignored).

---

## Local development setup

Prerequisites: Python 3.12 and Git.

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd J-Flooring-Specialist

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file
copy .env.example .env      # Windows
# cp .env.example .env      # macOS / Linux
```

Then edit `.env` (see [Configuration](#configuration)). At minimum you need a
`DJANGO_SECRET_KEY`:

```bash
python -c "import secrets; print('django-insecure-' + secrets.token_urlsafe(50))"
```

```bash
# 5. Apply migrations
python manage.py migrate

# 6. Create an admin account
python manage.py createsuperuser

# 7. Run the development server
python manage.py runserver
```

The site is at http://127.0.0.1:8000/ and the admin at
http://127.0.0.1:8000/admin/.

> `.env` is read at startup (and on every code reload) — restart `runserver`
> after changing it. It is loaded with `override=True`, so its values always
> win over anything already in the shell environment.

---

## Configuration

All configuration is via environment variables, loaded from `.env` in
development. See `.env.example` for the template.

| Variable | Required | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Yes | Django cryptographic signing key. The app will not start without it. |
| `DATABASE_URL` | No | PostgreSQL connection string (Neon). If unset, a local SQLite file is used. |
| `EMAIL_HOST` | No | SMTP server. Default `smtp.gmail.com`. |
| `EMAIL_PORT` | No | SMTP port. Default `587` (STARTTLS). |
| `EMAIL_USE_SSL` | No | Set to `1` only for providers that need implicit SSL (port 465). |
| `EMAIL_HOST_USER` | No | SMTP login. For Gmail, the full address; for other providers, the login they give you. |
| `EMAIL_HOST_PASSWORD` | No | SMTP password / key. For Gmail, a 16-char **App Password** (needs 2-Step Verification). |
| `DEFAULT_FROM_EMAIL` | No | "From" address on outgoing email, e.g. `J-Noon Flooring Specialist <name@example.com>` (angle brackets required). |

If `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` are both set, email is sent
via SMTP; otherwise it is printed to the `runserver` console.

---

## Database

Local development works out of the box on SQLite. For shared/production
data, use **Neon** (free managed PostgreSQL):

1. Create a project at <https://neon.tech> — region **AWS Europe (London)**.
2. Copy the **pooled** connection string (host contains `-pooler`), which
   ends with `?sslmode=require`.
3. Put it in `.env` as `DATABASE_URL=...`.
4. Run `python manage.py migrate`, then `python manage.py createsuperuser`
   (the new database starts empty).

Connection pooling and health checks are configured in `settings.py`
(`conn_max_age=600`, `conn_health_checks=True`).

---

## Email

Password-reset links are the only transactional email today. The SMTP
settings are provider-agnostic — set `EMAIL_HOST` / `EMAIL_PORT` /
`EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` in `.env` and restart the server.
Leave the user/password blank and email prints to the `runserver` console.

**Current dev setup:** Gmail SMTP (`smtp.gmail.com:587`) from an established
Google account, using a 16-character **App Password**
(<https://myaccount.google.com/apppasswords>, needs 2-Step Verification).
`EMAIL_HOST_USER` must be the address the Google account signs in as, not an
alias; brand-new Gmail accounts can be blocked from App Password use for
24–72 hours.

**Other providers** (Brevo, SMTP2GO, Mailjet, Resend, Mailgun) are a pure
`.env` change, e.g. Brevo:

```
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_HOST_USER=<login from the provider>
EMAIL_HOST_PASSWORD=<SMTP key>
```

**Verify credentials** without sending:

```bash
python -c "import os,smtplib; from dotenv import load_dotenv; load_dotenv('.env'); s=smtplib.SMTP(os.environ.get('EMAIL_HOST','smtp.gmail.com'), int(os.environ.get('EMAIL_PORT','587'))); s.starttls(); s.login(os.environ['EMAIL_HOST_USER'], os.environ['EMAIL_HOST_PASSWORD']); print('AUTH OK'); s.quit()"
```

**Deliverability:** mail sent "from" a free-domain address
(`@gmail.com`, `@live.co.uk`, …) that you don't control fails the Gmail /
Yahoo / Microsoft sender rules and may be spam-foldered. The fix is to send
from a domain you own and authenticate (SPF, DKIM, DMARC) — see the roadmap.

---

## Running the test suite

```bash
python manage.py test
```

Automated test coverage is being built out (see [Roadmap](#roadmap)). Every
feature added so far has been manually verified end-to-end — registration,
login (by username and by email), logout, the password-reset flow including
real SMTP delivery, and the profile / avatar-upload flow — along with all of
the security behaviours described above.

Also run, before any deploy:

```bash
python manage.py check --deploy
```

---

## Production deployment

1. Set environment variables on the host: `DJANGO_SECRET_KEY` (a fresh one),
   `DATABASE_URL`, and the email variables (`EMAIL_HOST`, `EMAIL_PORT`,
   `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`). No `.env`
   file is deployed.
2. Apply the [production hardening checklist](#production-hardening-checklist)
   in `settings.py` — gate the `SECURE_*` settings on `DEBUG` being `False`.
3. `python manage.py collectstatic`
4. `python manage.py migrate`
5. Serve through a WSGI server (e.g. Gunicorn) behind HTTPS.
6. Serve `/static/` and `/media/` from the host or a CDN/object store —
   Django only serves them in `DEBUG` mode.
7. Run `python manage.py check --deploy` and resolve every warning.

---

## Re-using this design for another firm

The reusable foundation is everything in `accounts/`, `core/`, the security
configuration, and the page/CSS/JS structure. To rebrand:

- **Business identity** — company name in templates and `DEFAULT_FROM_EMAIL`.
- **Content** — home/gallery/bookings templates.
- **Palette** — the CSS custom properties in `core/static/core/css/base.css`
  and the per-page stylesheets.
- **Configuration** — a fresh `.env` (new secret key, new database, new
  email account).

No customer data, credentials, or firm-specific logic is embedded in the
shared code.

---

## Roadmap

- [ ] Build out the work gallery (upload, categories, lightbox)
- [ ] Bookings: real enquiry form, availability, confirmation emails
- [ ] Contact / quote request pages
- [ ] Rewards scheme
- [ ] **Authenticate a sending domain** (SPF / DKIM / DMARC) for reliable
      deliverability — password reset currently sends via Gmail SMTP from a
      free-domain address, which risks spam-foldering. Switching to a real
      domain (or another provider) is a `.env` change only.
- [ ] Automated test suite (unit + integration) and CI
- [ ] Production settings split and hardening
- [ ] Media storage backend for uploads
- [ ] Cookie / privacy notice and GDPR data-export/delete tooling

---

## Licence

Proprietary. © J-Noon Flooring Specialist. All rights reserved.

This codebase is not open source. It may not be copied, distributed, or used
to build a derivative site without the written permission of the owner, jodesius the dev.
