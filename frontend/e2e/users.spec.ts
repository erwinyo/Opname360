import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

// The Owner account created by tests/e2e_seed.py.
const OWNER = { username: 'demo', password: 'demo-pemilik-1' }

async function signIn(page: Page, username: string, password: string) {
  await page.getByLabel('Nama pengguna').fill(username)
  await page.getByLabel('Kata sandi').fill(password)
  await page.getByRole('button', { name: 'Masuk' }).click()
}

test('the Owner manages staff accounts', async ({ page, browser }) => {
  const sari = page.getByRole('row', { name: /Sari Dewi/ })

  await test.step('a deep link survives signing in', async () => {
    await page.goto('/pengguna')
    await signIn(page, OWNER.username, 'salah-salah')
    await expect(page.getByRole('alert')).toHaveText(
      'Nama pengguna atau kata sandi salah.',
    )
    await signIn(page, OWNER.username, OWNER.password)
    await expect(page.getByRole('heading', { name: 'Pengguna' })).toBeVisible()
    await expect(page).toHaveURL(/\/pengguna$/)
  })

  await test.step('create an account', async () => {
    await page.getByRole('button', { name: 'Tambah pengguna' }).click()
    await page.getByRole('button', { name: 'Buat akun' }).click()
    await expect(page.getByText('Nama lengkap wajib diisi.')).toBeVisible()

    await page.getByLabel('Nama lengkap').fill('Sari Dewi')
    await page.getByLabel('Nama pengguna').fill('Sari')
    await page.getByLabel('Kata sandi').fill('kata-sandi-1')
    await page.getByRole('button', { name: 'Buat akun' }).click()
    await expect(sari).toContainText('Kasir')
  })

  await test.step('a taken username is refused', async () => {
    await page.getByRole('button', { name: 'Tambah pengguna' }).click()
    await page.getByLabel('Nama lengkap').fill('Sari Lain')
    await page.getByLabel('Nama pengguna').fill('SARI')
    await page.getByLabel('Kata sandi').fill('kata-sandi-2')
    await page.getByRole('button', { name: 'Buat akun' }).click()
    await expect(page.getByRole('dialog').getByRole('alert')).toHaveText(
      'Nama pengguna "sari" sudah dipakai.',
    )
    await page.getByRole('button', { name: 'Batal' }).click()
  })

  await test.step('change the role', async () => {
    await page.getByRole('button', { name: 'Tindakan untuk sari' }).click()
    await page.getByRole('menuitem', { name: 'Ubah nama atau peran' }).click()
    await page.getByLabel('Peran').click()
    await page.getByRole('option', { name: 'Admin' }).click()
    await page.getByRole('button', { name: 'Simpan' }).click()
    await expect(sari).toContainText('Admin')
  })

  const staff = await (await browser.newContext()).newPage()

  await test.step("an Admin can't open the Owner's screen", async () => {
    await staff.goto('/')
    await signIn(staff, 'sari', 'kata-sandi-1')
    await expect(
      staff.getByRole('heading', { name: 'Halo, Sari Dewi' }),
    ).toBeVisible()
    await staff.goto('/pengguna')
    await expect(
      staff.getByRole('heading', { name: 'Halo, Sari Dewi' }),
    ).toBeVisible()
    await expect(staff).toHaveURL(/\/$/)
  })

  await test.step('deactivating signs the user out at once', async () => {
    await page.getByRole('button', { name: 'Tindakan untuk sari' }).click()
    await page.getByRole('menuitem', { name: 'Nonaktifkan' }).click()
    await page.getByRole('button', { name: 'Nonaktifkan' }).click()
    await expect(sari).toContainText('Nonaktif')

    await staff.reload()
    await signIn(staff, 'sari', 'kata-sandi-1')
    await expect(staff.getByRole('alert')).toHaveText(
      'Nama pengguna atau kata sandi salah.',
    )
  })

  await test.step('the last Owner cannot be deactivated', async () => {
    await page.getByRole('button', { name: 'Tindakan untuk demo' }).click()
    await page.getByRole('menuitem', { name: 'Nonaktifkan' }).click()
    await page.getByRole('button', { name: 'Nonaktifkan' }).click()
    await expect(page.getByRole('dialog').getByRole('alert')).toHaveText(
      'Harus selalu ada minimal satu Pemilik aktif.',
    )
    await page.getByRole('button', { name: 'Batal' }).click()
  })

  await test.step('signing out shows the sign-in screen', async () => {
    await page.getByRole('button', { name: 'Keluar' }).click()
    await expect(page.getByRole('button', { name: 'Masuk' })).toBeVisible()
    await page.goto('/pengguna')
    await expect(page.getByRole('button', { name: 'Masuk' })).toBeVisible()
  })
})
