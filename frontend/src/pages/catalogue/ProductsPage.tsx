import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { FileSpreadsheetIcon, PlusIcon, SearchIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import type { ProductPublic } from '@/client'
import {
  categoriesListCategoriesOptions,
  productsListProductsOptions,
} from '@/client/@tanstack/react-query.gen'
import { Pager } from '@/components/Pager'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { rupiah, variantLabel } from '@/lib/format'

const PAGE_SIZE = 50
const ALL = 'all'

function priceRange(product: ProductPublic): string {
  const prices = product.skus.map((sku) => sku.selling_price)
  const low = Math.min(...prices)
  const high = Math.max(...prices)
  return low === high ? rupiah(low) : `${rupiah(low)} – ${rupiah(high)}`
}

function variantSummary(product: ProductPublic): string {
  const labels = product.skus.map(variantLabel).filter(Boolean)
  if (labels.length === 0) return 'Tanpa varian'
  const shown = labels.slice(0, 6).join(' · ')
  return labels.length > 6 ? `${shown} · +${labels.length - 6}` : shown
}

export function ProductsPage() {
  const navigate = useNavigate()
  const [typed, setTyped] = useState('')
  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState(ALL)
  const [subCategoryId, setSubCategoryId] = useState(ALL)
  const [offset, setOffset] = useState(0)

  // Search a moment after typing stops, not on every key.
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(typed.trim())
      setOffset(0)
    }, 300)
    return () => clearTimeout(timer)
  }, [typed])

  const categories = useQuery(categoriesListCategoriesOptions())
  const category = categories.data?.find((c) => String(c.id) === categoryId)
  const products = useQuery({
    ...productsListProductsOptions({
      query: {
        search: search || undefined,
        category_id: categoryId === ALL ? undefined : Number(categoryId),
        sub_category_id:
          subCategoryId === ALL ? undefined : Number(subCategoryId),
        offset,
        limit: PAGE_SIZE,
      },
    }),
    placeholderData: keepPreviousData,
  })

  const total = products.data?.total ?? 0
  const filtered = search !== '' || categoryId !== ALL
  const noCategories = categories.data?.length === 0

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Produk</h1>
          <p className="mt-1 text-muted-foreground">
            Setiap ukuran atau warna yang dijual adalah satu SKU dengan barcode
            sendiri.
          </p>
        </div>
        <span className="flex flex-wrap gap-2">
          <Button variant="outline" asChild>
            <Link to="/produk/impor">
              <FileSpreadsheetIcon />
              Impor dari Excel
            </Link>
          </Button>
          <Button asChild>
            <Link to="/produk/baru">
              <PlusIcon />
              Tambah produk
            </Link>
          </Button>
        </span>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        <div className="relative min-w-56 flex-1">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            placeholder="Cari nama, kode, atau barcode"
            aria-label="Cari produk"
            className="bg-card pl-8"
          />
        </div>
        <Select
          value={categoryId}
          onValueChange={(value) => {
            setCategoryId(value)
            setSubCategoryId(ALL)
            setOffset(0)
          }}
        >
          <SelectTrigger className="bg-card" aria-label="Kategori">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Semua kategori</SelectItem>
            {categories.data?.map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {category && (
          <Select
            value={subCategoryId}
            onValueChange={(value) => {
              setSubCategoryId(value)
              setOffset(0)
            }}
          >
            <SelectTrigger className="bg-card" aria-label="Sub-kategori">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Semua sub-kategori</SelectItem>
              {category.sub_categories.map((sub) => (
                <SelectItem key={sub.id} value={String(sub.id)}>
                  {sub.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {products.isError && (
        <p className="mt-6 text-destructive">{errorMessage(products.error)}</p>
      )}

      {products.data && total === 0 && (
        <p className="mt-4 rounded-xl border border-dashed p-6 text-muted-foreground">
          {filtered ? (
            'Tidak ada produk yang cocok.'
          ) : noCategories ? (
            <>
              Belum ada produk. Buat dulu{' '}
              <Link to="/kategori" className="text-primary underline">
                kategori dan sub-kategorinya
              </Link>
              , lalu tambahkan produk.
            </>
          ) : (
            'Belum ada produk. Tambahkan produk pertama toko ini.'
          )}
        </p>
      )}

      {total > 0 && (
        <>
          <div className="mt-4 overflow-x-auto rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Produk</TableHead>
                  <TableHead className="hidden md:table-cell">Varian</TableHead>
                  <TableHead className="text-right">Harga jual</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {products.data?.items.map((product) => {
                  const inactive = product.skus.filter(
                    (sku) => !sku.is_active,
                  ).length
                  return (
                    <TableRow
                      key={product.id}
                      className="cursor-pointer"
                      onClick={() => navigate(`/produk/${product.id}`)}
                    >
                      <TableCell>
                        <Link
                          to={`/produk/${product.id}`}
                          className="font-medium"
                          onClick={(event) => event.stopPropagation()}
                        >
                          {product.name}
                        </Link>
                        <span className="block text-sm text-muted-foreground">
                          {product.category_name} › {product.sub_category_name}
                        </span>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <span className="text-sm">
                          {product.skus.length} SKU
                        </span>
                        {inactive > 0 && (
                          <Badge variant="outline" className="ml-2">
                            {inactive} nonaktif
                          </Badge>
                        )}
                        <span className="block text-sm text-muted-foreground">
                          {variantSummary(product)}
                        </span>
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap tabular-nums">
                        {priceRange(product)}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
          <Pager
            offset={offset}
            pageSize={PAGE_SIZE}
            total={total}
            unit="produk"
            onChange={setOffset}
          />
        </>
      )}
    </>
  )
}
