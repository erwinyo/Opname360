import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { SearchIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import {
  categoriesListCategoriesOptions,
  stockListStockOptions,
} from '@/client/@tanstack/react-query.gen'
import { Pager } from '@/components/Pager'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { money, quantity, variantLabel } from '@/lib/format'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 50
const ALL = 'all'

export function StockPage() {
  const navigate = useNavigate()
  const [typed, setTyped] = useState('')
  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState(ALL)
  const [subCategoryId, setSubCategoryId] = useState(ALL)
  const [negativeOnly, setNegativeOnly] = useState(false)
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(typed.trim())
      setOffset(0)
    }, 300)
    return () => clearTimeout(timer)
  }, [typed])

  const categories = useQuery(categoriesListCategoriesOptions())
  const category = categories.data?.find((c) => String(c.id) === categoryId)
  const stock = useQuery({
    ...stockListStockOptions({
      query: {
        search: search || undefined,
        category_id: categoryId === ALL ? undefined : Number(categoryId),
        sub_category_id:
          subCategoryId === ALL ? undefined : Number(subCategoryId),
        negative_only: negativeOnly,
        offset,
        limit: PAGE_SIZE,
      },
    }),
    placeholderData: keepPreviousData,
  })
  const total = stock.data?.total ?? 0
  const filtered = search !== '' || categoryId !== ALL || negativeOnly

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Stok</h1>
          <p className="mt-1 text-muted-foreground">
            Jumlah dan nilai stok tiap SKU menurut sistem, dihitung dari setiap
            barang masuk dan keluar.
          </p>
        </div>
        {stock.data && (
          <div className="sm:text-right">
            <p className="text-sm text-muted-foreground">
              Nilai stok{filtered ? ' (sesuai filter)' : ''}
            </p>
            <p className="text-xl font-semibold tabular-nums">
              {money(stock.data.total_value)}
            </p>
          </div>
        )}
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            placeholder="Cari nama, kode, atau barcode"
            aria-label="Cari stok"
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
        <span className="flex items-center gap-2 px-1">
          <Switch
            id="negative-only"
            checked={negativeOnly}
            onCheckedChange={(checked) => {
              setNegativeOnly(checked)
              setOffset(0)
            }}
          />
          <Label htmlFor="negative-only">Hanya stok minus</Label>
        </span>
      </div>

      {stock.isError && (
        <p className="mt-6 text-destructive">{errorMessage(stock.error)}</p>
      )}
      {stock.data && total === 0 && (
        <p className="mt-4 rounded-xl border border-dashed p-6 text-muted-foreground">
          {negativeOnly && search === '' && categoryId === ALL ? (
            'Tidak ada stok minus.'
          ) : filtered ? (
            'Tidak ada SKU yang cocok.'
          ) : (
            <>
              Belum ada SKU.{' '}
              <Link to="/produk/baru" className="text-primary underline">
                Tambahkan produk
              </Link>{' '}
              dulu.
            </>
          )}
        </p>
      )}

      {total > 0 && (
        <>
          <div className="mt-4 overflow-x-auto rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Barang</TableHead>
                  <TableHead className="hidden md:table-cell">
                    Kategori
                  </TableHead>
                  <TableHead className="text-right">Stok</TableHead>
                  <TableHead className="text-right">Nilai</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stock.data?.items.map((row) => {
                  const amount = Number(row.quantity)
                  return (
                    <TableRow
                      key={row.sku_id}
                      className={cn(
                        'cursor-pointer',
                        !row.is_active && 'text-muted-foreground',
                      )}
                      onClick={() => navigate(`/stok/${row.sku_id}`)}
                    >
                      <TableCell>
                        <Link
                          to={`/stok/${row.sku_id}`}
                          className="font-medium"
                          onClick={(event) => event.stopPropagation()}
                        >
                          {[row.product_name, variantLabel(row)]
                            .filter(Boolean)
                            .join(' · ')}
                        </Link>
                        {!row.is_active && (
                          <Badge variant="outline" className="ml-2">
                            Nonaktif
                          </Badge>
                        )}
                        <span className="block text-sm text-muted-foreground tabular-nums">
                          {row.code} · {row.barcode}
                        </span>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {row.category_name} › {row.sub_category_name}
                      </TableCell>
                      <TableCell
                        className={cn(
                          'text-right whitespace-nowrap tabular-nums',
                          amount < 0 && 'font-semibold text-destructive',
                        )}
                      >
                        {quantity(row.quantity)} {row.stock_unit}
                        {amount < 0 && (
                          <span className="block text-xs font-normal">
                            Stok minus
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap tabular-nums">
                        {money(row.value)}
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
            unit="SKU"
            onChange={setOffset}
          />
        </>
      )}
    </>
  )
}
