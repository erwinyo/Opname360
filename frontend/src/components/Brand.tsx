import { cn } from '@/lib/utils'

export function Brand({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <svg viewBox="0 0 32 32" className="size-7 shrink-0" aria-hidden="true">
        <rect width="32" height="32" rx="7" className="fill-primary" />
        <path
          d="M9 16.5l4.5 4.5L23 11.5"
          fill="none"
          stroke="white"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="text-base font-semibold tracking-tight">
        Opname<span className="text-primary">360</span>
      </span>
    </div>
  )
}
