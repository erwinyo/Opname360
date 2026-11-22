# Sign-in and roles

A user signs in with a username and password and lands on the home screen for their role. The Owner and Admin see Dasbor and the back-office menu. A Cashier sees "Halo, <name>" with Kasir and Hitung Stok. The Owner creates, edits and deactivates staff accounts, and a deactivated user is signed out at once.

## Sub-features

- `signin-ok` signs in and lands on the role's home screen.
- `signin-deep-link` returns to the screen that was asked for before signing in.
- `roles-menu` shows each role only its menu entries.
- `roles-guard` sends a user who opens another role's screen back to their home.
- `users-create` creates a staff account with a role.
- `users-deactivate` deactivates an account and ends its sessions.

## How to get to it (user POV)

- Open any page while signed out: the sign-in form appears.
- Sidebar `Pengguna` (Owner only) lists staff accounts.
- Sign out with the button at the bottom of the sidebar.

## Driving it with Playwright

Preconditions:

- Baseline instance; `demo` is the only account.

- **Sign in.** `signIn(page)`, or by hand: `page.getByLabel('Nama pengguna').fill('demo')`, `page.getByLabel('Kata sandi').fill('demo-pemilik-1')`, `page.getByRole('button', { name: 'Masuk' }).click()`. Heading `Dasbor` is visible.
- **Create a Cashier.** `openMenu(page, 'Pengguna')`, then `page.getByRole('button', { name: 'Tambah pengguna' }).click()`. Fill `getByLabel('Nama lengkap')`, `getByLabel('Nama pengguna')` and `getByLabel('Kata sandi')`, and choose the role through `getByLabel('Peran')`. Click `getByRole('button', { name: 'Buat akun' })`. A row named after the user appears. Faster as a precondition: `api(page.request, 'users/', { username, full_name, role: 'cashier', password })`.
- **Cashier home.** In a new context, `signIn(page2, username, password)`. Heading `Halo, <full name>` is visible. The sidebar has `Beranda`, `Kasir` and `Hitung Stok`, and no `Laporan` section.
- **Guard.** As the Cashier, `page2.goto('/pengguna')`. The home heading is shown again, not `Pengguna`.
- **Deactivate.** As the Owner, `getByRole('button', { name: 'Tindakan untuk <username>' }).click()`, then `getByRole('menuitem', { name: 'Nonaktifkan' }).click()` and `getByRole('button', { name: 'Nonaktifkan' }).click()`. The Cashier's next action shows the sign-in form with an alert.
- **Proof.** Call `proof()` on the Cashier home and on the user list. Second view: `sql.sh "SELECT username, role, is_active FROM \"user\""`.

## Gotchas

- Five failed sign-ins lock an account for 15 minutes. A journey that tests wrong passwords should use its own account, never `demo`.
- Usernames are case-insensitive and unique (`SARI` collides with `sari`).
- The last active Owner can't be deactivated, so leave `demo` alone.
- Use a separate browser context per user (`browser.newContext()`). One context shares one session cookie.
