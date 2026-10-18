import { useQuery } from '@tanstack/react-query'
import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { LoadingState } from '@/components/states'
import { formatDateTime } from '@/lib/dates'

import { searchAlternatives, searchParams, type SearchQuery } from './api'
import { alternativesKey } from './keys'

/**
 * Exp 2 UC 2 extension 3a: nothing matches, so offer the nearest alternatives
 * by branch (same dates) or by date (same branch). Each opens that search.
 */
export function Alternatives({ query, base }: { query: SearchQuery; base: string }) {
  const alternatives = useQuery({
    queryKey: alternativesKey(query),
    queryFn: () => searchAlternatives(query),
  })
  if (alternatives.isPending) return <LoadingState label="Looking for the nearest alternatives…" />
  if (alternatives.isError || alternatives.data.length === 0) return null
  const iso = (value: string) => new Date(value).toISOString()
  const sameDates = (row: (typeof alternatives.data)[number]) => iso(row.pickup_datetime) === iso(query.pickup_datetime)
  return (
    <section aria-labelledby="alternatives-heading" className="enter grid gap-3">
      <h3 id="alternatives-heading" className="text-subsection">
        Nearest alternatives
      </h3>
      <ul className="divide-y border-y">
        {alternatives.data.map((row) => {
          const next = searchParams({
            ...query,
            branch: String(row.branch),
            pickup_datetime: iso(row.pickup_datetime),
            return_datetime: iso(row.return_datetime),
          })
          const count = row.vehicles === 1 ? '1 vehicle' : `${row.vehicles} vehicles`
          return (
            <li key={`${row.branch}-${row.pickup_datetime}`}>
              <Link
                to={`${base}/search?${next.toString()}`}
                className="group flex min-h-12 flex-wrap items-center justify-between gap-x-6 gap-y-1 py-3 text-sm"
              >
                <span>
                  {sameDates(row) ? (
                    <>
                      <span className="font-medium">{row.branch_name}</span>, same dates
                    </>
                  ) : (
                    <>
                      <span className="font-medium">{row.branch_name}</span>,{' '}
                      <span className="num">{formatDateTime(row.pickup_datetime)}</span> to{' '}
                      <span className="num">{formatDateTime(row.return_datetime)}</span>
                    </>
                  )}
                </span>
                <span className="flex items-center gap-1.5 text-muted-foreground group-hover:text-primary">
                  {count} free
                  <ArrowRight className="size-4" aria-hidden="true" />
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
