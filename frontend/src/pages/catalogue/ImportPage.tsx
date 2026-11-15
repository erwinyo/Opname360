import { useMutation } from '@tanstack/react-query'
import { DownloadIcon, FileSpreadsheetIcon } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { productsPreviewImport, productsRunImport } from '@/client'
import { BackLink } from '@/components/documents'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage, queryClient } from '@/lib/api'

export function ImportPage() {
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)

  const preview = useMutation({
    mutationFn: async (chosen: File) => {
      const { data } = await productsPreviewImport({
        body: { file: chosen },
        throwOnError: true,
      })
      return data
    },
  })
  const run = useMutation({
    mutationFn: async (chosen: File) => {
      const { data } = await productsRunImport({
        body: { file: chosen },
        throwOnError: true,
      })
      return data
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries()
      toast.success(
        `${result.product_count} produk (${result.sku_count} SKU) diimpor.`,
      )
    },
  })

  const choose = (chosen: File | undefined) => {
    if (!chosen) return
    setFile(chosen)
    run.reset()
    preview.mutate(chosen)
  }
  const result = preview.data
  const ready = result && result.problems.length === 0 && result.sku_count > 0

  return (
    <>
      <BackLink to="/produk" label="Produk" />
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">
        Impor Produk
      </h1>
      <p className="mt-1 text-muted-foreground">
        Masukkan banyak produk sekaligus dari file Excel. Jika ada satu baris
        yang salah, tidak ada yang diimpor.
      </p>

      <ol className="mt-6 grid gap-4">
        <li className="rounded-xl border bg-card p-4">
          <p className="font-medium">1. Unduh template dan isi</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Satu baris untuk tiap ukuran atau warna. Lembar Petunjuk di dalam
            file menjelaskan setiap kolom.
          </p>
          <Button variant="outline" className="mt-3" asChild>
            <a href="/api/v1/products/import/template" download>
              <DownloadIcon />
              Unduh template
            </a>
          </Button>
        </li>
        <li className="rounded-xl border bg-card p-4">
          <p className="font-medium">2. Pilih file yang sudah diisi</p>
          <input
            ref={input}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="sr-only"
            aria-label="File Excel"
            onChange={(event) => {
              choose(event.target.files?.[0])
              event.target.value = ''
            }}
          />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              onClick={() => input.current?.click()}
              disabled={preview.isPending || run.isPending}
            >
              <FileSpreadsheetIcon />
              {file ? 'Pilih file lain' : 'Pilih file'}
            </Button>
            {file && (
              <span className="text-sm text-muted-foreground">{file.name}</span>
            )}
          </div>
        </li>
      </ol>

      {preview.isPending && (
        <p className="mt-6 text-muted-foreground">Memeriksa file…</p>
      )}
      {preview.isError && (
        <p role="alert" className="mt-6 text-destructive">
          {errorMessage(preview.error)}
        </p>
      )}

      {result && result.problems.length > 0 && (
        <section className="mt-6">
          <h2 className="font-semibold text-destructive">
            {result.problems.length} masalah ditemukan. Tidak ada yang
            diimpor.
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Perbaiki di Excel, simpan, lalu pilih file itu lagi.
          </p>
          <div className="mt-3 overflow-x-auto rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-20">Baris</TableHead>
                  <TableHead className="w-40">Kolom</TableHead>
                  <TableHead>Masalah</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.problems.map((problem, index) => (
                  <TableRow key={index}>
                    <TableCell className="tabular-nums">
                      {problem.row ?? '–'}
                    </TableCell>
                    <TableCell>{problem.column ?? '–'}</TableCell>
                    <TableCell>{problem.message}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </section>
      )}

      {result && result.problems.length === 0 && result.sku_count === 0 && (
        <p className="mt-6 rounded-xl border border-dashed p-6 text-muted-foreground">
          File ini belum berisi produk.
        </p>
      )}

      {ready && !run.isSuccess && (
        <section className="mt-6 rounded-xl border bg-card p-4">
          <h2 className="font-semibold">3. Periksa lalu impor</h2>
          <p className="mt-2">
            <span className="font-medium tabular-nums">
              {result.product_count}
            </span>{' '}
            produk dengan{' '}
            <span className="font-medium tabular-nums">{result.sku_count}</span>{' '}
            SKU siap diimpor.
          </p>
          {result.new_categories.length > 0 && (
            <p className="mt-2 text-sm">
              Kategori baru: {result.new_categories.join(', ')}
              <span className="block text-muted-foreground">
                Kategori baru memakai HPP rata-rata. Ubah di menu Kategori
                sebelum ada barang masuk bila perlu FIFO.
              </span>
            </p>
          )}
          {result.new_sub_categories.length > 0 && (
            <p className="mt-2 text-sm">
              Sub-kategori baru: {result.new_sub_categories.join(', ')}
            </p>
          )}
          {run.isError && (
            <p role="alert" className="mt-3 text-sm text-destructive">
              {errorMessage(run.error)}
            </p>
          )}
          <Button
            className="mt-4"
            disabled={run.isPending}
            onClick={() => file && run.mutate(file)}
          >
            {run.isPending ? 'Mengimpor…' : `Impor ${result.sku_count} SKU`}
          </Button>
        </section>
      )}

      {run.isSuccess && (
        <section className="mt-6 rounded-xl border bg-card p-4">
          <h2 className="font-semibold">Selesai</h2>
          <p className="mt-1">
            {run.data.product_count} produk dan {run.data.sku_count} SKU masuk
            katalog
            {run.data.category_count > 0 &&
              `, dengan ${run.data.category_count} kategori baru`}
            .
          </p>
          <Button className="mt-4" asChild>
            <Link to="/produk">Lihat produk</Link>
          </Button>
        </section>
      )}
    </>
  )
}
