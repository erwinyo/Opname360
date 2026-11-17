import { useQuery } from '@tanstack/react-query'
import { SheetIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { categoriesListCategoriesOptions } from '@/client/@tanstack/react-query.gen'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ALL } from '@/lib/reports'

/** A report's title, what it shows, and its Excel download. */
export function ReportHeader({
  title,
  description,
  excel,
}: {
  title: string
  description: ReactNode
  excel?: string
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-muted-foreground">{description}</p>
      </div>
      {excel && (
        <Button variant="outline" asChild>
          <a href={excel} download>
            <SheetIcon />
            Excel
          </a>
        </Button>
      )}
    </div>
  )
}

export function DateInput({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <Input
      type="date"
      aria-label={label}
      title={label}
      value={value}
      required
      onChange={(event) => event.target.value && onChange(event.target.value)}
      className="w-auto bg-card"
    />
  )
}

/** Category, then its Sub-categories once one is chosen. */
export function CategoryFilter({
  categoryId,
  subCategoryId,
  onChange,
}: {
  categoryId: string
  subCategoryId: string
  onChange: (categoryId: string, subCategoryId: string) => void
}) {
  const categories = useQuery(categoriesListCategoriesOptions())
  const category = categories.data?.find((c) => String(c.id) === categoryId)
  return (
    <>
      <Select
        value={categoryId}
        onValueChange={(value) => onChange(value, ALL)}
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
          onValueChange={(value) => onChange(categoryId, value)}
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
    </>
  )
}

export function Filters({ children }: { children: ReactNode }) {
  return (
    <div className="mt-6 flex flex-wrap items-center gap-2">{children}</div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="mt-4 rounded-xl border border-dashed p-6 text-muted-foreground">
      {children}
    </p>
  )
}
