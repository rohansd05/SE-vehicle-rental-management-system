import { Upload } from 'lucide-react'
import { useEffect, useMemo } from 'react'

import { Label } from '@/components/ui/label'
import { describedBy } from '@/lib/form'

import { checkLicenceImage, LICENCE_IMAGE_ACCEPT } from './rules'

/**
 * One licence photo: checked in the browser for type and size before any
 * upload, with a preview (HI-1). The server checks again (D3).
 */
export function ImagePicker({
  id,
  label,
  file,
  error,
  onChange,
}: {
  id: string
  label: string
  file: File | null
  error: string | null
  onChange: (file: File | null, error: string | null) => void
}) {
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview)
    },
    [preview],
  )

  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <div className="flex aspect-[85/54] w-full max-w-56 items-center justify-center overflow-hidden rounded-md border bg-muted">
          {preview ? (
            <img src={preview} alt={`Preview: ${label.toLowerCase()}`} className="size-full object-cover" />
          ) : (
            <Upload className="size-6 text-muted-foreground" aria-hidden="true" />
          )}
        </div>
        <div className="grid gap-1">
          <input
            id={id}
            type="file"
            accept={LICENCE_IMAGE_ACCEPT}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy(id, { hint: true, error: Boolean(error) })}
            className="text-sm file:mr-3 file:h-9 file:rounded-md file:border file:bg-background file:px-3 file:text-sm file:font-medium hover:file:bg-muted"
            onChange={(event) => {
              const chosen = event.target.files?.[0] ?? null
              if (!chosen) {
                onChange(null, null)
                return
              }
              const problem = checkLicenceImage(chosen)
              if (problem) {
                event.target.value = '' // never keep a file we would refuse
                onChange(null, problem)
              } else {
                onChange(chosen, null)
              }
            }}
          />
          <p id={`${id}-hint`} className="text-xs text-muted-foreground">
            JPG or PNG, up to 5 MB. Make sure every detail is readable.
          </p>
          {file ? <p className="text-xs text-muted-foreground">Chosen: {file.name}</p> : null}
          {error ? (
            <p id={`${id}-error`} className="text-sm text-destructive">
              {error}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
