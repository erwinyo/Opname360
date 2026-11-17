import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'

import type { AccountRole } from '@/client'
import {
  ledgerAssignRoleMutation,
  ledgerListAccountsOptions,
  ledgerListAccountsQueryKey,
  paymentMethodsListMethodsOptions,
  paymentMethodsListMethodsQueryKey,
  paymentMethodsUpdateMethodMutation,
} from '@/client/@tanstack/react-query.gen'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage, queryClient } from '@/lib/api'

import { AccountSelect } from './shared'

const ROLES: Record<AccountRole, string> = {
  cash_main: 'Kas besar: modal kas shift dan setoran tutup shift',
  cash_drawer: 'Kas kasir: uang di laci',
  bank: 'Bank: pembayaran non-tunai tanpa akun sendiri',
  inventory: 'Persediaan',
  employee_receivable: 'Piutang karyawan',
  accounts_payable: 'Hutang usaha',
  opening_balance: 'Saldo awal',
  retained_earnings: 'Laba ditahan',
  sales: 'Penjualan',
  sales_discount: 'Diskon penjualan',
  sales_return: 'Retur penjualan',
  other_income: 'Pendapatan lain',
  inventory_surplus: 'Selisih lebih persediaan',
  cash_over: 'Selisih lebih kas',
  cogs: 'Harga pokok penjualan',
  inventory_shortage: 'Selisih kurang persediaan',
  damaged_goods: 'Barang rusak',
  cash_short: 'Selisih kurang kas',
  production_cost: 'Biaya produksi dibebankan',
  salary: 'Gaji: ganti rugi yang dipotong dari gaji',
}

/** Pengaturan Akun (Owner): which account plays each role, and where each
 *  Payment Method's money goes. */
export function AccountSettingsPage() {
  const accounts = useQuery(ledgerListAccountsOptions())
  const methods = useQuery(paymentMethodsListMethodsOptions())
  const assign = useMutation({
    ...ledgerAssignRoleMutation(),
    onSuccess: (account) => {
      queryClient.invalidateQueries({ queryKey: ledgerListAccountsQueryKey() })
      toast.success(`${account.name} sekarang dipakai sistem.`)
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  const route = useMutation({
    ...paymentMethodsUpdateMethodMutation(),
    onSuccess: (method) => {
      queryClient.invalidateQueries({
        queryKey: paymentMethodsListMethodsQueryKey(),
      })
      toast.success(`Akun ${method.name} disimpan.`)
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  const holder = (role: AccountRole) =>
    accounts.data?.find((account) => account.role === role)
  const bank = holder('bank')

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Pengaturan Akun</h1>
      <p className="mt-1 text-muted-foreground">
        Akun yang diisi otomatis dari dokumen. Persediaan, kas kasir, hutang
        usaha, dan piutang karyawan tidak bisa dipindah setelah punya jurnal.
      </p>

      <h2 className="mt-8 text-lg font-semibold">Metode pembayaran</h2>
      <div className="mt-3 rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Metode</TableHead>
              <TableHead className="w-80">Uangnya masuk ke</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {methods.data?.map((method) => (
              <TableRow key={method.id}>
                <TableCell className="font-medium">{method.name}</TableCell>
                <TableCell>
                  {method.is_cash ? (
                    <span className="text-muted-foreground">
                      {holder('cash_drawer')?.name ?? 'Kas Kasir'}, lewat laci
                    </span>
                  ) : (
                    <AccountSelect
                      value={method.account_id ? String(method.account_id) : ''}
                      onChange={(id) =>
                        route.mutate({
                          path: { method_id: method.id },
                          body: { account_id: Number(id) },
                        })
                      }
                      filter={(account) =>
                        account.is_cash && account.role !== 'cash_drawer'
                      }
                      placeholder={bank ? `${bank.name} (bawaan)` : 'Bank'}
                      label={`Akun ${method.name}`}
                    />
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <h2 className="mt-8 text-lg font-semibold">Akun sistem</h2>
      <div className="mt-3 rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Peran</TableHead>
              <TableHead className="w-80">Akun</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(Object.keys(ROLES) as AccountRole[]).map((role) => {
              const current = holder(role)
              return (
                <TableRow key={role}>
                  <TableCell>{ROLES[role]}</TableCell>
                  <TableCell>
                    <AccountSelect
                      value={current ? String(current.id) : ''}
                      onChange={(id) =>
                        assign.mutate({
                          path: { role },
                          body: { account_id: Number(id) },
                        })
                      }
                      filter={(account) =>
                        account.id === current?.id ||
                        (!account.role && account.type === current?.type)
                      }
                      label={ROLES[role]}
                    />
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </>
  )
}
