import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { toast } from 'sonner'

import type { ShopSettingsPublic } from '@/client'
import {
  shopSettingsReadSettingsOptions,
  shopSettingsReadSettingsQueryKey,
  shopSettingsSaveSettingsMutation,
} from '@/client/@tanstack/react-query.gen'
import { Field } from '@/components/FormDialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage, queryClient } from '@/lib/api'

export function ShopSettingsPage() {
  const settings = useQuery(shopSettingsReadSettingsOptions())
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Pengaturan Toko</h1>
      <p className="mt-1 text-muted-foreground">
        Dicetak di setiap struk, dan aturan retur di kasir.
      </p>
      {settings.isError && (
        <p className="mt-6 text-destructive">{errorMessage(settings.error)}</p>
      )}
      {settings.data && <SettingsForm settings={settings.data} />}
    </>
  )
}

function SettingsForm({ settings }: { settings: ShopSettingsPublic }) {
  const [name, setName] = useState(settings.name)
  const [address, setAddress] = useState(settings.address ?? '')
  const [footer, setFooter] = useState(settings.receipt_footer ?? '')
  const [opensAt, setOpensAt] = useState(settings.opens_at.slice(0, 5))
  const [closesAt, setClosesAt] = useState(settings.closes_at.slice(0, 5))
  const [returnDays, setReturnDays] = useState(
    String(settings.return_window_days),
  )
  const [checked, setChecked] = useState(false)

  const days = Number(returnDays)
  const errors = {
    name: name.trim() ? undefined : 'Nama toko wajib diisi.',
    hours:
      opensAt && closesAt && opensAt < closesAt
        ? undefined
        : 'Jam buka harus sebelum jam tutup.',
    returnDays:
      returnDays !== '' && Number.isInteger(days) && days >= 0 && days <= 365
        ? undefined
        : 'Isi 0 sampai 365 hari.',
  }
  const save = useMutation({
    ...shopSettingsSaveSettingsMutation(),
    onSuccess: (saved) => {
      queryClient.setQueryData(shopSettingsReadSettingsQueryKey(), saved)
      toast.success('Pengaturan toko disimpan.')
    },
  })
  const submit = (event: FormEvent) => {
    event.preventDefault()
    setChecked(true)
    if (Object.values(errors).some(Boolean)) return
    save.mutate({
      body: {
        name,
        address: address.trim() || null,
        receipt_footer: footer.trim() || null,
        opens_at: opensAt,
        closes_at: closesAt,
        return_window_days: days,
      },
    })
  }

  return (
    <form onSubmit={submit} noValidate className="mt-6 grid max-w-xl gap-5">
      <section className="grid gap-5 rounded-xl border bg-card p-4">
        <h2 className="font-medium">Di struk</h2>
        <Field
          id="shop-name"
          label="Nama toko"
          error={checked ? errors.name : undefined}
        >
          <Input
            id="shop-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={100}
          />
        </Field>
        <Field id="shop-address" label="Alamat dan telepon">
          <Textarea
            id="shop-address"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            maxLength={300}
          />
        </Field>
        <Field
          id="shop-footer"
          label="Catatan kaki struk"
          hint="Misalnya aturan retur atau ucapan terima kasih."
        >
          <Textarea
            id="shop-footer"
            value={footer}
            onChange={(event) => setFooter(event.target.value)}
            maxLength={300}
          />
        </Field>
      </section>

      <section className="grid gap-5 rounded-xl border bg-card p-4">
        <h2 className="font-medium">Jam dan retur</h2>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field id="opens-at" label="Jam buka">
            <Input
              id="opens-at"
              type="time"
              value={opensAt}
              onChange={(event) => setOpensAt(event.target.value)}
            />
          </Field>
          <Field
            id="closes-at"
            label="Jam tutup"
            error={checked ? errors.hours : undefined}
          >
            <Input
              id="closes-at"
              type="time"
              value={closesAt}
              onChange={(event) => setClosesAt(event.target.value)}
            />
          </Field>
        </div>
        <Field
          id="return-days"
          label="Batas waktu retur (hari)"
          hint="Berlaku untuk retur yang dilakukan setelah disimpan."
          error={checked ? errors.returnDays : undefined}
        >
          <Input
            id="return-days"
            value={returnDays}
            onChange={(event) => setReturnDays(event.target.value)}
            inputMode="numeric"
            className="sm:w-32"
          />
        </Field>
      </section>

      {save.isError && (
        <p role="alert" className="text-destructive">
          {errorMessage(save.error)}
        </p>
      )}
      <div>
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? 'Menyimpan…' : 'Simpan'}
        </Button>
      </div>
    </form>
  )
}
