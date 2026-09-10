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
- [Media storage](#media-storage)
- [Turning on the bookings features](#turning-on-the-bookings-features)
- [Running the test suite](#running-the-test-suite)
- [Production deployment](#production-deployment)
- [Re-using this design for another firm](#re-using-this-design-for-another-firm)
- [Roadmap](#roadmap)
- [Licence](#licence)

---

## Overview

A multi-page Django site with:

- A built-out **home page** (hero, about, a live "Reviews" strip, a
  "How we work" section, and a "What we do" section), a **work gallery**
  (filterable masonry grid + lightbox, photos managed in the admin), a
  **Contact us** page (admin-managed details, coverage map, enquiry form),
  and two **Bookings** features: an **AI-assisted free quote** (a signed-in
  customer answers a short form and Claude produces a rough estimate, asks
  follow-ups, or refers the job to a call, from an admin-managed rate card)
  and **book a call-back** (name + phone + a day and time → a 30-minute
  event lands on the fitter's Google Calendar with reminders).
- A **client reviews** feature with **full CRUD** (create / read / update /
  delete): signed-in customers post postcard-style reviews with a star
  rating and an optional photo, and can edit or delete their own. Every
  review is **held for admin approval before it goes live**, so spam,
  abuse, and mistaken posts never reach visitors.
- A full customer account system: registration, login, logout, password
  reset by email, and an editable user profile with avatar upload.
- The Django admin for staff, including the review moderation queue.

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
| Media storage | Cloudinary (`django-cloudinary-storage`); local `media/` folder when unconfigured |
| Email | Provider-agnostic SMTP via Django 6.1 `MAILERS` (`EMAIL_HOST` / `PORT` / `USER` / `PASSWORD`); console backend when unconfigured |
| Front end | Server-rendered Django templates, hand-written CSS/JS per app, no build step. One third-party library: Leaflet (from cdnjs) for the Contact page's coverage map, with OpenStreetMap tiles — no API key |
| AI | Anthropic Claude via the official `anthropic` SDK (`claude-sonnet-5` by default) for the bookings quote engine — optional, off until `ANTHROPIC_API_KEY` is set |
| Calendar | Google Calendar API via a service account (`google-auth` + `requests`) for the "book a call" feature — optional, off until a calendar and key are configured |

Dependencies are pinned in `requirements.txt`.

---

## Features

### Public site (`core`, `gallery`, `bookings`, `contact`)

- Shared `base.html` layout: walnut header with a collapsible navigation
  menu, a centred brand wordmark (its badge shows the JN logo image, kept
  inside the framed border), and the user badge; footer carries the company
  logo (served from Cloudinary).
- Context-aware navigation — the current page is hidden from the menu, and
  the menu shows *Login / Register* or *Logout* depending on auth state.
- When signed in, the header avatar + name is a link straight to the
  profile page.
- Per-page CSS and JS, namespaced by app. The home "about" and "how we
  work" sections, the gallery, bookings and contact pages, and the error
  page all share one oak brown (`#6b4423`) background; "reviews" and "what
  we do" sit on the light `#f5efe8` ground for contrast.
- **Home page** (`core`): full-bleed hero with call-to-action buttons over a
  photo of real work (crop tuned with `object-position`), an "About"
  section, a "Reviews" strip showing the six most recent approved review
  postcards with a *See all reviews* link, a **"How we work"** section —
  three equal cards (Supply & Fit / Installation Only / Repairs & Remedials)
  each listing what the client pays for, plus a *Get a quote* button to
  Bookings — and a **"What we do"** section: a card per flooring system
  (Laminate, LVT, Amtico, Engineered & Solid Wood, Vinyl, Carpet & Carpet
  Tiles, Screeding & Floor Prep), each with a one-line summary and a
  numbered "order of works". All static content for now; images can be
  added later.
### Bookings (`bookings`)

- **`/bookings/`** — landing page. Signed out: a *sign in / register* gate.
  Signed in: **Get a free quote** and **Book a call-back** cards (both
  built), plus a greyed-out **Your projects** card (customer portal, next up).

**Book a call-back — `/bookings/call/`** (`@login_required`)

- A short form: name, phone (both prefilled from the profile), a day (within
  the next three weeks), a time picked to the half-hour, and an optional
  message.
- On submit it's saved as a `CallRequest` **and an event is created on the
  fitter's Google Calendar** (via a service account — no OAuth) titled
  "Call <name> — <phone>", a 30-minute slot at the chosen time in the
  configured timezone, with popup reminders (12 h before and 10 min before).
  The business also gets a plain email.
- If the calendar isn't configured (or the API call fails) the request is
  still saved and emailed — nothing errors. Honeypot-guarded, login-gated,
  `CALL_DAILY_LIMIT` per user per day.
- Staff manage requests in the admin (`CallRequest`, read-only, editable
  status + notes, with a "on calendar?" flag).

**Get a free quote — `/bookings/quote/`** (`@login_required`)

- A short form (service option, flooring system or free-text, approximate
  area or "not sure", subfloor type & condition, removal, timescale,
  postcode, extra details; name/phone prefilled from the profile). On submit
  it becomes a `QuoteRequest`, then:
  - Claude reads the answers plus the **rate card** and returns either
    **up to 4 follow-up questions** (rendered on a `/bookings/quote/<uuid>/`
    page), **a rough £ range** with a breakdown and its assumptions, or a
    **"we'll call you"** for anything it shouldn't price blind (repairs,
    damaged subfloor, very large or uncertain jobs).
  - The business gets an **email** for every request; all requests show in
    the admin (`QuoteRequest`, read-only form data + the full AI result +
    an editable status and staff notes).
- **The rate card is admin data.** `QuoteSettings.rate_card` is a single
  free-text field (seeded with J-Noon's real prices — labour rates, pattern
  floors, subfloor prep, how materials work for supply & fit); the AI reads
  it verbatim. `QuoteSettings` also holds a free-text rules box, an
  estimate-headroom %, and a master on/off switch. `FlooringRate` is just
  the picklist of systems on the form. The fitter edits the rate card in the
  admin — no code, no redeploy — and the AI always quotes from it.
- **Graceful states:** with no `ANTHROPIC_API_KEY`, an empty rate card, or
  the master switch off, the quote page invites the customer to **book a
  call** instead — nothing errors. `QUOTING_PREVIEW=1` (DEBUG only) walks the
  whole flow with a canned sample estimate and no API key or cost.
- **Guard rails** — every estimate is a **range, never binding, always
  "subject to a site visit"**; the fitter reviews each one; the server
  independently sanity-checks the AI's numbers (absolute bounds, plus a
  per-m² band when the area is known) and downgrades an implausible quote to
  "we'll call you"; the customer's free
  text is fed to Claude as **data, not instructions** (the system prompt
  says so, and structured JSON output is validated server-side); the form
  is login-gated, honeypot-protected, and capped at `QUOTE_DAILY_LIMIT`
  (default 5) requests per user per day.

### Contact us (`contact`)

- **`SiteContact`** — a single admin-editable record (photo, personal
  intro, phone, email, enquiry recipient, coverage radius, service-area
  town list, response-time line, social links). The page reads it, so the
  business can change any of it without a code change. A placeholder image
  stands in until a real photo is uploaded.
- **Coverage map** — Leaflet + OpenStreetMap (no API key, no billing),
  centred on Chelmsford town centre with a shaded circle at the coverage
  radius and a marker. Leaflet loads from cdnjs; OSM serves the tiles.
- **Enquiry form** — name, email, phone, postcode, message. On submit the
  message is **saved as a `ContactEnquiry`** *and* emailed to the business
  (`reply-to` set to the sender). Email failure is swallowed — the enquiry
  is still captured. A **honeypot field** (hidden from people) blocks the
  common spam bots.
- **No street address** anywhere on the site — a mobile trade doesn't need
  one, and it keeps a home address private. The page shows "Based in
  Chelmsford · N-mile radius" instead.
- Staff see enquiries in the admin (`ContactEnquiry`, read-only, with a
  *handled* toggle); they can't be created there.
- **Custom 404 page** (`core/templates/404.html`): on-theme "page not found"
  with an explanation of the URL error and a link back home. Django serves
  it automatically for any unmatched URL when `DEBUG = False` (in local dev
  with `DEBUG = True` you still get Django's debug page).

### Work gallery (`gallery`)

- A **masonry grid** of completed-work photos. Images keep their real
  proportions and tile like brickwork; the column count steps up with screen
  width — **1** column on phones, **2** on large phones (≥ 425px), **3** on
  tablets (≥ 768px), **4** on desktop (≥ 1024px), **5** on 2K/4K displays
  (≥ 2560px).
- **Category filter bar** — one button per flooring type (Laminate, LVT,
  Amtico, …). Filtering is instant and client-side; only categories that
  actually have a published photo get a button. A starter set of categories
  is seeded by a migration and is fully editable in the admin.
- **Lightbox** — clicking a photo opens it enlarged in an overlay with
  next/prev (scoped to the current filter), a caption, keyboard support
  (`←` `→` `Esc`) and a backdrop-click close. Vanilla JS, no library.
- Photos are **managed entirely in the Django admin** (`GalleryImage`):
  upload, title, alt text, category, a *show on site* toggle, and a
  `sort_order`. A thumbnail preview shows in the change form and the list.
- **Deleting a photo** — the *Delete* button on a photo's change page, or
  the *Delete selected gallery images* bulk action on the list — removes the
  row **and** the underlying file from storage (`GalleryImageAdmin`
  overrides `delete_model` / `delete_queryset`). Django would otherwise
  leave the file orphaned.
- Grid and lightbox images are served at sensible sizes via **Cloudinary
  transformations** (`f_auto,q_auto,c_limit,w_900` / `w_1800`) built onto
  the stored URL — the original upload is never sent to the browser.
- Image dimensions are captured on upload and written as `width`/`height`
  attributes, so the grid does not reflow as photos load.
- `python manage.py prune_gallery_media` is the backstop: it deletes storage
  files with no matching row (from older deletes, replaced images, or direct
  DB edits). `--dry-run` to preview, `--yes` to skip the prompt; works
  against Cloudinary or the local `media/` folder. The shared file-deletion
  helpers live in `gallery/cleanup.py`.

### Client reviews (`reviews`)

Postcard-style customer reviews with **full CRUD**, gated by admin approval.

| Operation | Route | Who |
| --- | --- | --- |
| **Create** | `/reviews/new/` | Any signed-in user (`@login_required`) |
| **Read** | `/reviews/` and the home "Reviews" strip | Everyone — **approved reviews only** |
| **Update** | `/reviews/<uuid>/edit/` | The **author only** |
| **Delete** | `/reviews/<uuid>/delete/` | The **author**, a **Site Administrator**, or the **superuser** |

- A review has a 1–5 **star rating** (required), a headline, the review text,
  and an **optional photo** of the finished work. When no photo is uploaded
  a default image is shown.
- **Approval required before anything is public.** A new *or edited* review
  is saved with `is_approved = False` and stays hidden from the site until a
  staff member approves it in `/admin/`. The submitter sees a "will appear
  once it has been approved" message. This is the project's main defence
  against **review spam, offensive or defamatory content, and link/SEO
  abuse** — nothing a customer types is shown to visitors until a human has
  seen it, and re-editing an approved review pulls it back into the queue.
- **Moderation tools** (`/admin/`): `is_approved` is a one-click toggle on
  the review list, plus bulk *Approve* / *Unapprove* actions. Staff can also
  delete any review. Reviews cannot be *created* in the admin — they only
  come from real signed-in customers through the site.
- Postcards are **light cards with dark text**, matching the home page's
  "What we do" cards (white body, oak-accent title underline, work photo on
  top). The `/reviews/` page shares the same cream (`#f5efe8`) ground as the
  home "Reviews" strip.
- Review URLs use the review's **UUID slug**, never a sequential id.

### Accounts (`accounts`)

| Route | Purpose |
| --- | --- |
| `/accounts/register/` | Create an account — email, username, password, confirm password |
| `/accounts/login/` | Log in with **username or email** |
| `/accounts/logout/` | Log out (POST only) |
| `/accounts/profile/` | View your own profile (`?edit=1` to edit) |
| `/accounts/password-reset/` | Request a reset link by email |
| `/accounts/reset/<uidb64>/<token>/` | Set a new password from an emailed link |
| `/accounts/verify-email/<uidb64>/<token>/` | Confirm an email address from an emailed link |

- **Custom user model** (`accounts.User`) with a unique, required email
  address. Usernames are unique **case-insensitively** — nobody can take
  `Bob` if `bob` exists.
- **Show / hide password** toggle on the registration, login and
  set-new-password forms.
- **Email verification**: a signed, time-limited link is sent at
  registration (and re-sendable from the profile page). The profile shows a
  **Verified / Unverified** badge. The link is token-only, so it works from
  any device without logging in.
- **Profile**: display name (username), profile image, pronouns, contact
  phone and email, an "about me" section, and social links
  (Facebook, Instagram, LinkedIn, website). One profile per user, created
  automatically on registration.
- The profile page is **read-only by default** with an *Edit profile*
  button; saving returns to the read-only view. The registered email is
  shown but never editable there.
- Changing the picture means uploading a new one — it replaces the old
  (no "clear" control). The uploaded avatar replaces the default icon
  beside the username in the site header. Images are stored on Cloudinary.

### Admin & roles

Three access tiers, using Django's built-in auth:

| Tier | How | Can do |
| --- | --- | --- |
| **Superuser** | `is_superuser` — **jodesius only** | Everything; the only tier that can grant superuser, edit raw permissions, or manage groups |
| **Site Administrator** | `is_staff = True` + member of the **Site Administrators** group | Manage all project content and customer accounts in `/admin/` |
| **Regular user** | default | No admin access at all |

- The Django admin is at `/admin/`, with the custom user and an inline
  profile editor. Verified status and account flags are editable there
  (and `email_verified` is a one-click toggle on the user list).
- **Review moderation** lives in the admin: `is_approved` is a one-click
  toggle on the review list, with bulk *Approve* / *Unapprove* actions.
  Reviews cannot be created in the admin (clients post them through the
  site).
- **Gallery photos** are managed in the admin: `GalleryImage` (with a
  thumbnail preview, inline `category` / `is_published` / `sort_order`
  editing) and `Category`.
- **Contact us** is admin-driven: `SiteContact` (a single row — the
  business details and photo shown on the page) and `ContactEnquiry`
  (read-only list of messages sent through the form, with a *handled*
  toggle).
- **Bookings quoting** is admin-driven: `QuoteSettings` (a single row — the
  free-text rate card the AI reads, a rules box, headroom %, master switch),
  `FlooringRate` (the form's system picklist), and `QuoteRequest` (read-only
  form data + full AI result, with an editable status and staff notes).
  `CallRequest` (call-back requests) is read-only too, with status + notes
  and an "on calendar?" indicator.
- The **Site Administrators** group is (re)built automatically after every
  `migrate`, and manually with `python manage.py sync_roles`. It receives
  every permission for the project's own apps and **none** for Django's
  `auth` app, so members cannot create groups or edit permissions.
- A non-superuser in `/admin/` never sees the `is_superuser`, `groups` or
  `user_permissions` fields, and cannot view, edit or delete a superuser
  account — no privilege escalation.
- To promote someone: in the admin, tick **Staff status** and add them to
  the **Site Administrators** group.
- `user.is_site_admin` (superuser or group member) is available for
  template / view checks.

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
- Email-verification and password-reset links use HMAC-signed, time-limited
  tokens (`SECRET_KEY`-derived). A verification token's hash includes the
  address and the verified flag, so it is single-use and dies if the email
  changes.

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

- The profile page (both the read-only view and the `?edit=1` form) is
  `@login_required` and **always operates on `request.user`**. There is no
  user id, primary key, username or other identifier anywhere in a profile
  URL, form field, or hidden input — so one account cannot view or modify
  another (no IDOR / horizontal privilege escalation).
- Profiles are private: there are no public profile pages.
- **Reviews** are addressed by a random **UUID slug**, never a sequential
  id. Editing is scoped to `author=request.user` (a stranger's slug 404s);
  deleting is allowed only for the author, a Site Administrator, or the
  superuser. The review form never accepts an author or id from the request
  — it is set from `request.user` in the view.
- **Vertical privilege escalation** is blocked in the admin: the Site
  Administrators group holds no `auth`-app permissions, and non-superusers
  never see `is_superuser` / `groups` / `user_permissions` and cannot act
  on superuser accounts (see [Admin & roles](#admin--roles)).

### User-generated content / abuse prevention

- The only content a non-staff user can publish is a **review**, and it is
  **not published on submission** — it is queued (`is_approved = False`) and
  a staff member must approve it. This keeps spam, offensive or defamatory
  text, and planted links out of the public site by default (fail-closed).
- **Editing an approved review un-approves it**, so a review cannot be
  approved as harmless and then silently swapped for something else.
- Posting requires a **logged-in account** (`@login_required`); there is no
  anonymous submission path, which ties every review to an auditable user.
- Review text is length-capped (headline 80, body 1500 chars) and rendered
  through Django's auto-escaping — `linebreaksbr` only converts newlines, it
  does not allow HTML — so a review cannot inject markup or script.
- Photos go through the same Pillow content validation as every other upload
  (see [File uploads](#file-uploads-profile-images-review-photos)).
- Delete rights are deliberately broad for staff: a **Site Administrator or
  the superuser can remove any review** from the site UI or the admin, so
  bad content that slips through can be pulled immediately.

### Input handling and injection

- **SQL injection**: all database access goes through the Django ORM. There
  is no raw SQL, string-formatted query, or `.extra()` / `.raw()` anywhere
  in the codebase.
- **Cross-site scripting (XSS)**: Django template auto-escaping is on for
  all user-supplied content. The one `autoescape off` block is a plain-text
  password-reset email that contains no user input.
- **Cross-site request forgery (CSRF)**: `CsrfViewMiddleware` is enabled and
  every state-changing form (`register`, `login`, `logout`, `profile`,
  password reset, review create / edit / delete, and the contact enquiry
  form) submits a `{% csrf_token %}`. Review delete is POST-only with a
  confirmation page.
- **Contact form spam**: a honeypot field (present in the DOM, hidden from
  people with CSS) — a filled-in honeypot fails validation, so the message
  is never saved or emailed. Enquiry text is length-capped and rendered
  through auto-escaping; the notification email is plain text.
- **AI quote engine**: the quote form is `@login_required`, honeypot-guarded
  and rate-limited per user per day. The customer's free text reaches Claude
  as **data, not instructions** (the system prompt states this explicitly);
  Claude's reply is **schema-constrained JSON**, parsed and re-validated
  server-side, and the numbers are sanity-checked (absolute bounds, plus a
  per-m² band when the area is known) before being shown. Every estimate is
  a non-binding range subject to a site visit, and the fitter reviews each
  request — the AI never commits the business to anything.
- **Mass assignment**: forms declare an explicit field list; the profile
  form separates the editable `username` from account-security concerns.
- Request body size is capped (`DATA_UPLOAD_MAX_MEMORY_SIZE`,
  `FILE_UPLOAD_MAX_MEMORY_SIZE`).

### File uploads (profile images, review photos, gallery photos, contact photo)

- **Type is verified by parsing the file with Pillow**, not by trusting the
  file extension or the browser-supplied content type. Profile images accept
  real PNG / JPEG only; review, gallery and contact photos accept real JPEG
  / PNG / WebP only. A renamed `.png`, a BMP, a GIF, or a text file are all
  rejected.
- Hard size limit checked **before** the file is parsed: **1 MB** profile,
  **4 MB** review, **10 MB** gallery, **3 MB** contact photo.
- Stored under a random UUID name
  (`<CLOUDINARY_FOLDER>/profile_images/<uuid>`, `.../reviews/<uuid>`,
  `.../gallery/<uuid>`, `.../contact/<uuid>`), so the path exposes no user
  identifier and images cannot be enumerated. Uploads go to Cloudinary
  (served from its CDN); the local `media/` folder is the fallback when
  Cloudinary is not configured.
- Replacing an image just means uploading a new one — there is no "delete"
  control on the profile or review forms.
- Profile images have a client-side pre-check and live preview for fast
  feedback; the server-side validation is always authoritative.
- Gallery photos are uploaded only by staff through the admin, but they run
  the same Pillow validation as everything else.

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

- `DEBUG = False` (this also switches on the custom `404.html` page)
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
│   ├── templates/404.html  # custom "page not found" page
│   ├── static/core/        # base.css / base.js, home.css / home.js, error.css
│   ├── tests.py            # custom 404 renders for unknown URLs
│   └── views.py            # home view (feeds the recent-reviews strip)
├── accounts/               # user model, auth, profiles, roles
│   ├── models.py           # User, Profile
│   ├── backends.py         # username-or-email authentication
│   ├── validators.py       # password policy + profile-image validation
│   ├── tokens.py           # email-verification token generator
│   ├── roles.py            # Site Administrators group definition
│   ├── forms.py            # RegisterForm, LoginForm, ProfileForm
│   ├── signals.py          # auto-create Profile for new users
│   ├── management/commands/ # sync_roles
│   ├── views.py
│   ├── migrations/
│   ├── templates/accounts/ # login, register, logout, profile, reset + verify
│   └── static/accounts/    # auth.css, profile.css, page JS
├── reviews/                # client review postcards
│   ├── models.py           # Review (UUID slug, rating, moderation flag)
│   ├── forms.py            # ReviewForm
│   ├── validators.py       # review-photo validation (Pillow, 4 MB)
│   ├── admin.py            # moderation queue (approve / unapprove)
│   ├── views.py            # list / create / update / delete
│   ├── tests.py            # listing, moderation, IDOR + delete-permission
│   ├── migrations/
│   ├── templates/reviews/  # list, form, delete confirm, _postcard, _stars
│   └── static/reviews/     # reviews.css
├── gallery/                # filterable work-gallery grid + lightbox
│   ├── models.py           # GalleryImage, Category
│   ├── validators.py       # gallery-photo validation (Pillow, 10 MB)
│   ├── cleanup.py          # storage file list / delete helpers (Cloudinary + local)
│   ├── admin.py            # image + category admin; delete also removes the file
│   ├── views.py            # published images + categories-with-photos
│   ├── tests.py            # views, model rules, admin delete, prune command
│   ├── management/commands/ # prune_gallery_media
│   ├── migrations/         # 0001 initial, 0002 seed starter categories
│   ├── templates/gallery/  # index (grid + filter bar + lightbox markup)
│   └── static/gallery/     # gallery.css (masonry breakpoints), gallery.js
├── bookings/               # bookings landing + AI-assisted quote
│   ├── models.py           # QuoteSettings, FlooringRate, QuoteRequest, CallRequest
│   ├── quoting.py          # rate card -> Claude -> parsed/validated estimate
│   ├── calendar_sync.py    # CallRequest -> Google Calendar event (service account)
│   ├── forms.py            # QuoteStartForm, CallRequestForm (+ honeypots), FollowUpForm
│   ├── admin.py            # rate card + settings + read-only Quote/Call requests
│   ├── views.py            # landing, quote form + follow-up + result, call form
│   ├── tests.py            # gates, flows (mocked AI + calendar), sanity check, limits
│   ├── migrations/         # 0001 initial, 0002 seed rate card, 0003 CallRequest
│   ├── templates/bookings/ # index, quote (+ followup/result/unavailable), call, emails
│   └── static/bookings/    # bookings.css
├── contact/                # Contact us page - details, coverage map, enquiry form
│   ├── models.py           # SiteContact (singleton), ContactEnquiry
│   ├── forms.py            # EnquiryForm (+ honeypot)
│   ├── validators.py       # contact-photo validation (Pillow, 3 MB)
│   ├── admin.py            # SiteContact + read-only ContactEnquiry
│   ├── views.py            # render page + handle enquiry (save + email)
│   ├── tests.py            # page, singleton, form save/email/honeypot
│   ├── migrations/
│   ├── templates/contact/  # index.html + enquiry email templates
│   └── static/contact/     # contact.css, contact.js (Leaflet map)
├── manage.py
├── requirements.txt
├── .env.example
└── README.md
```

Uploaded files go to Cloudinary (or the git-ignored `media/` folder when
`CLOUDINARY_URL` is unset). Collected static files go to `staticfiles/` on
deploy (git-ignored).

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
| `CLOUDINARY_URL` | No | `cloudinary://<key>:<secret>@<cloud_name>` from the Cloudinary dashboard (must include the `@<cloud_name>` part). If unset or malformed, uploads are stored in the local `media/` folder. |
| `CLOUDINARY_FOLDER` | No | Folder inside the Cloudinary account that uploads go into. Default `media`. |
| `ANTHROPIC_API_KEY` | No | From <https://console.anthropic.com/> (pay-as-you-go). Enables the AI quote engine; without it the quote page asks the customer to book a call. |
| `ANTHROPIC_QUOTE_MODEL` | No | Model for quoting. Default `claude-sonnet-5`. |
| `QUOTE_DAILY_LIMIT` | No | Quote requests one signed-in user may send per day. Default `5`. |
| `QUOTING_PREVIEW` | No | `1` (DEBUG only) to demo the quote flow with a canned estimate and no API key / cost. |
| `GOOGLE_CALENDAR_ID` | No | The calendar to add call-backs to — usually your Google account's email address. |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | No | The service-account key: the whole JSON on one line, or a path to the `.json` file. Without this (and `GOOGLE_CALENDAR_ID`), call-backs are just saved + emailed. |
| `BOOKINGS_TIMEZONE` | No | Timezone for calendar events. Default `Europe/London`. |
| `CALL_DAILY_LIMIT` | No | Call-back requests one signed-in user may send per day. Default `3`. |

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

## Media storage

User uploads (profile images, review photos, gallery photos and the contact
photo) go to **Cloudinary** when `CLOUDINARY_URL` is set, otherwise to the
local `media/` folder.

1. Create a free account at <https://cloudinary.com>.
2. On the dashboard, copy the whole **API environment variable** —
   `cloudinary://<api_key>:<api_secret>@<cloud_name>` (it must end with the
   `@<cloud_name>`).
3. Put it in `.env` as `CLOUDINARY_URL=...`, set `CLOUDINARY_FOLDER` to the
   folder you want uploads in, and restart the server.

No code change is needed to switch — `settings.STORAGES["default"]` picks the
backend based on whether a valid `CLOUDINARY_URL` is present. Files keep
their random UUID names inside `CLOUDINARY_FOLDER`; Cloudinary serves them
from its CDN.

Deleting a gallery photo in the admin removes its file too (the admin
overrides `delete_model` / `delete_queryset`). Django does **not** do this
for replaced images or other models, so run `python manage.py
prune_gallery_media` now and then (or `--dry-run` first) to clear any
stragglers out of Cloudinary.

---

## Turning on the bookings features

Both work without their integration configured — a quote request falls back
to "book a call", a call-back is still saved and emailed. To switch the
integrations on:

### AI quotes

1. **Check the rate card.** A starter rate card (J-Noon's real prices) is
   already seeded. Open **Bookings → Quote settings** in the admin to adjust
   the wording, set an estimate-headroom %, and add any behavioural rules
   ("assume 8% wastage", "no stairs", …). The AI reads that text as-is.
   **Bookings → Flooring rates** is just the list of systems shown on the
   form.
2. **Add an API key.** Create one at <https://console.anthropic.com/> and put
   it in `.env` as `ANTHROPIC_API_KEY=...`, then restart the server. It's
   pay-as-you-go — roughly 1–3p per quote on `claude-sonnet-5`.

To preview the flow first, set `QUOTING_PREVIEW=1` in `.env` (with
`DEBUG = True`) — it walks the whole journey with a canned estimate and no
API key or cost. Every request is saved as a `QuoteRequest` and emailed;
review them in **Bookings → Quote requests**.

### Google Calendar for call-backs

1. In the [Google Cloud console](https://console.cloud.google.com/): create
   (or pick) a project, then **APIs & Services → Library → enable "Google
   Calendar API"**.
2. **APIs & Services → Credentials → Create credentials → Service account.**
   Give it a name, skip the optional roles. Open the new service account →
   **Keys → Add key → JSON** → download the file. Note the service account's
   email (`…@….iam.gserviceaccount.com`).
3. In **Google Calendar** (web) → the calendar's **Settings and sharing →
   Share with specific people → Add** → paste the service-account email →
   permission **"Make changes to events"**.
4. In `.env`: `GOOGLE_CALENDAR_ID=your-google-email@gmail.com` and
   `GOOGLE_SERVICE_ACCOUNT_JSON=` the contents of that JSON file on one line
   (or an absolute path to it). Restart the server.

Every call-back is saved as a `CallRequest` and emailed regardless; the
calendar event is a bonus. Review them in **Bookings → Call requests**.

---

## Running the test suite

```bash
python manage.py test           # whole suite
python manage.py test bookings   # just the bookings app
python manage.py test reviews    # just the reviews app
python manage.py test gallery    # just the gallery app
python manage.py test contact    # just the contact app
```

Every feature is checked **both ways** before it is committed: automated
tests where they add lasting value (currently **58**, across `core`,
`bookings`, `contact`, `reviews` and `gallery`), and a manual end-to-end
pass in the browser for the full user journey and the look of each page.
Tests that touch the AI or Google Calendar **mock those calls** — no real
external API is ever
hit from the test suite.

**Automated tests**

- The **`reviews` app has a test suite** (`reviews/tests.py`) covering the
  full CRUD path and its guard rails:
  - only **approved** reviews appear in the list / on the home page;
  - a new review, and an **edited** review, both land as `is_approved = False`;
  - a review is attributed to `request.user`, not to anything in the form;
  - **IDOR guard** — a user cannot edit another user's review (404);
  - **delete-permission matrix** — allowed for the author, a Site
    Administrator and the superuser; refused for an unrelated user.
- The **`gallery` app has a test suite** (`gallery/tests.py`): only
  `is_published` photos are shown, the filter bar lists only categories that
  have a published photo, the empty state renders, category slugs are
  auto-generated, image dimensions are captured on upload, the admin's
  change-page and bulk deletes both remove the row **and** the file, and
  `prune_gallery_media` deletes only files with no database row. (These
  tests use `InMemoryStorage` so nothing is written to Cloudinary.)
- `core/tests.py` checks an unknown URL renders the custom `404.html`.
- The **`contact` app has a test suite** (`contact/tests.py`): the page
  renders with the map container, the `SiteContact` singleton always loads
  one row, a valid enquiry is saved *and* emailed (with `reply-to` set),
  the honeypot blocks spam, required fields are enforced, and a missing
  recipient still saves the enquiry.
- The **`bookings` app has a test suite** (`bookings/tests.py`, AI and
  calendar mocked): the quote page is login-gated and shows "book a call"
  when quoting isn't configured; a valid submission creates a `QuoteRequest`
  and emails the business; the **need-info → follow-up → quote** path works;
  a `QuotingUnavailable` falls back to "we'll call you"; the sanity check
  downgrades an implausible AI quote; and — for call-backs — a booking saves
  a `CallRequest`, creates a calendar event and emails; it still works when
  the calendar isn't configured; past dates, the honeypot and the daily
  limits are all rejected; one user can't open another's quote.
- `python manage.py check` (and `check --deploy` before releasing) is run on
  every change.
- Wider automated coverage of the older apps is still being built out (see
  [Roadmap](#roadmap)).

**Manual verification**

Done end-to-end for every feature so far, most recently:

- Bookings call-back: submitted the form, confirmed the "I'll call you
  <period> on <day>" message, the `CallRequest` row, and the staff email
  (calendar not yet configured, so no event — the fallback path).
- Bookings quote: walked all four outcomes in `QUOTING_PREVIEW` mode (direct
  estimate with breakdown, need-info → follow-up → estimate, refer-to-call,
  and the "book a call" fallback when unconfigured); confirmed the
  `QuoteRequest` rows and the staff email; checked the signed-out gate and
  the greyed-out "coming soon" cards.
- Reviews: post a review, see the "awaiting approval" message, confirm it is
  not visible, approve it in the admin, confirm it appears on `/reviews/` and
  the home strip; edit an own review and confirm it drops back to pending;
  delete as the author, and delete someone else's as an admin; confirm a
  non-owner sees no edit/delete controls.
- Contact: submit the enquiry form and confirm the thank-you message, the
  enquiry in the admin, and (with a recipient set) the email; check the
  Leaflet coverage map draws the radius circle; confirm the page still
  renders cleanly with no `SiteContact` details filled in.
- Accounts: registration, login by username *and* by email, logout,
  password-reset including real SMTP delivery, email verification, and the
  profile / avatar-upload flow.
- Gallery: upload photos of several shapes through the admin, confirm the
  masonry grid stays tidy and the column count changes at each breakpoint
  (1 / 2 / 3 / 4 / 5), the category buttons filter instantly, and the
  lightbox opens, captions, navigates within the current filter, and closes
  on `Esc` / backdrop click.
- All of the security behaviours described above.

> The test runner creates a temporary `test_` database. Against Neon this
> can need a moment between runs while the previous connection closes; add
> `--keepdb` to reuse the test database.

Also run, before any deploy:

```bash
python manage.py check --deploy
```

---

## Production deployment

1. Set environment variables on the host: `DJANGO_SECRET_KEY` (a fresh one),
   `DATABASE_URL`, `CLOUDINARY_URL`, and the email variables (`EMAIL_HOST`,
   `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
   `DEFAULT_FROM_EMAIL`). No `.env` file is deployed.
2. Apply the [production hardening checklist](#production-hardening-checklist)
   in `settings.py` — gate the `SECURE_*` settings on `DEBUG` being `False`.
3. `python manage.py collectstatic`
4. `python manage.py migrate` (this also refreshes the Site Administrators
   permission group; `python manage.py sync_roles` runs it on demand).
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
- **Imagery** — the home hero image (`core/templates/core/home.html`), the
  default review photo (`DEFAULT_REVIEW_IMAGE` in `reviews/models.py`) and
  the default contact photo (`DEFAULT_CONTACT_PHOTO` in
  `contact/models.py`). Gallery photos and their categories, and all the
  Contact us details, are admin data — no code changes.
- **Contact / coverage** — the map centre in `contact/static/contact/js/
  contact.js` (Chelmsford town centre); everything else (radius, area list,
  phone, email) is edited in the admin.
- **Gallery breakpoints** — the `column-count` media queries in
  `gallery/static/gallery/css/gallery.css` if a firm wants a different
  column progression.
- **Configuration** — a fresh `.env` (new secret key, new database, new
  email account).

No customer data, credentials, or firm-specific logic is embedded in the
shared code.

---

## Roadmap

- [ ] Replace the default review photo placeholder (`DEFAULT_REVIEW_IMAGE`
      in `reviews/models.py`) — shown on postcards with no uploaded image
- [x] Home page — hero (real work photo), about, recent-reviews strip,
      "how we work" (three service options), "what we do" (seven systems)
- [ ] Add photos to the "what we do" cards (currently text only)
- [x] Client reviews — full CRUD, star rating, photo upload, admin approval
      gate, photo-backed postcards
- [x] Work gallery — admin-managed photos, responsive masonry grid,
      category filter, lightbox
- [ ] Gallery follow-ups: per-image ordering by drag, optional captions in
      the lightbox, "load more" if the library gets large
- [x] Custom 404 page
- [ ] Custom 403 / 500 pages (reuse `error.css`)
- [x] Contact us page — admin-managed details, Leaflet coverage map,
      enquiry form (saved + emailed, honeypot spam guard)
- [ ] Contact follow-ups: real photo, rate-limit the form, auto-reply to
      the sender
- [ ] Add the Anthropic API key + the Google Calendar service account to
      switch the two bookings integrations live
- [x] Bookings — AI-assisted free quote (rate card in the admin, Claude
      estimate / follow-ups / refer-to-call, staff email, guard rails)
- [x] Bookings — book a call-back (name + phone + day/time → 30-min Google
      Calendar event + reminders + staff email)
- [ ] Bookings next: a proper availability calendar (real slots, working
      hours, no double-booking)
- [ ] Bookings next: customer portal — active project view, work photos,
      costs, and online payment (Stripe) with a cash "mark as paid" option
- [ ] Rewards scheme
- [ ] **Authenticate a sending domain** (SPF / DKIM / DMARC) for reliable
      deliverability — password reset currently sends via Gmail SMTP from a
      free-domain address, which risks spam-foldering. Switching to a real
      domain (or another provider) is a `.env` change only.
- [ ] Automated test suite (unit + integration) and CI
- [ ] Production settings split and hardening
- [x] Media storage backend for uploads (Cloudinary; set `CLOUDINARY_URL`)
- [ ] Cookie / privacy notice and GDPR data-export/delete tooling

---

## Licence

Proprietary. © J-Noon Flooring Specialist. All rights reserved.

This codebase is not open source. It may not be copied, distributed, or used
to build a derivative site without the written permission of the owner, jodesius the dev.
