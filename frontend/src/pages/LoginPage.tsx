import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'

import { authLoginMutation } from '@/client/@tanstack/react-query.gen'
import { Brand } from '@/components/Brand'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { errorMessage, setSignedInUser } from '@/lib/api'

export function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const login = useMutation({
    ...authLoginMutation(),
    onSuccess: setSignedInUser,
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    login.mutate({ body: { username, password } })
  }

  return (
    <main className="grid min-h-svh place-items-center px-4 py-10">
      <div className="w-full max-w-sm">
        <Brand className="mb-8 justify-center" />
        <form
          onSubmit={submit}
          className="rounded-xl border bg-card p-6 shadow-xs"
        >
          <h1 className="text-lg font-semibold">Masuk</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Pakai akun yang dibuatkan Pemilik untuk Anda.
          </p>

          <div className="mt-6 grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="username">Nama pengguna</Label>
              <Input
                id="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                autoCapitalize="none"
                autoFocus
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">Kata sandi</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
          </div>

          {login.isError && (
            <p role="alert" className="mt-4 text-sm text-destructive">
              {errorMessage(login.error)}
            </p>
          )}

          <Button
            type="submit"
            className="mt-6 w-full"
            disabled={login.isPending}
          >
            {login.isPending ? 'Memeriksa…' : 'Masuk'}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          Lupa kata sandi? Minta Pemilik mengatur ulang.
        </p>
      </div>
    </main>
  )
}
