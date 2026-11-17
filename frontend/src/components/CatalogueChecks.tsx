import { XIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import type { CategoryPublic } from '@/client'
import { Button } from '@/components/ui/button'

export function Check({
  checked,
  onChange,
  children,
}: {
  checked: boolean
  onChange: () => void
  children: ReactNode
}) {
  return (
    <label className="flex min-h-9 cursor-pointer items-center gap-2.5 rounded-md px-2 hover:bg-muted">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="size-4 accent-primary"
      />
      {children}
    </label>
  )
}

/** Pick Categories. */
export function CategoryChecks({
  categories,
  selected,
  onToggle,
}: {
  categories: CategoryPublic[]
  selected: number[]
  onToggle: (id: number) => void
}) {
  return (
    <fieldset className="grid gap-1 sm:grid-cols-2">
      <legend className="sr-only">Kategori</legend>
      {categories.map((category) => (
        <Check
          key={category.id}
          checked={selected.includes(category.id)}
          onChange={() => onToggle(category.id)}
        >
          {category.name}
        </Check>
      ))}
    </fieldset>
  )
}

/** Pick Sub-categories, grouped under their Category. */
export function SubCategoryChecks({
  categories,
  selected,
  onToggle,
}: {
  categories: CategoryPublic[]
  selected: number[]
  onToggle: (id: number) => void
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {categories.map((category) => (
        <fieldset key={category.id} className="grid gap-1">
          <legend className="mb-1 text-sm font-medium text-muted-foreground">
            {category.name}
          </legend>
          {category.sub_categories.map((sub) => (
            <Check
              key={sub.id}
              checked={selected.includes(sub.id)}
              onChange={() => onToggle(sub.id)}
            >
              {sub.name}
            </Check>
          ))}
        </fieldset>
      ))}
    </div>
  )
}

/** What was picked one by one, each with a button to take it out. */
export function Chips({
  items,
  onRemove,
}: {
  items: { id: number; label: string }[]
  onRemove: (id: number) => void
}) {
  if (items.length === 0) return null
  return (
    <ul className="mt-3 flex flex-wrap gap-2">
      {items.map((item) => (
        <li
          key={item.id}
          className="flex items-center gap-1 rounded-full border bg-background py-0.5 pr-1 pl-3 text-sm"
        >
          {item.label}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-6 rounded-full"
            aria-label={`Hapus ${item.label}`}
            onClick={() => onRemove(item.id)}
          >
            <XIcon />
          </Button>
        </li>
      ))}
    </ul>
  )
}
