import { X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

/** Accessible dialog: bottom sheet on phones, centered card on larger screens. */
export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const { t } = useTranslation()
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className="m-0 mt-auto w-full max-w-none rounded-t-3xl bg-card p-0 backdrop:bg-black/40 sm:m-auto sm:max-w-md sm:rounded-3xl"
    >
      <div className="flex items-center justify-between border-b border-line px-5 py-4">
        <h2 className="text-base font-semibold">{title}</h2>
        <button type="button" className="btn-ghost !p-1.5" onClick={onClose} aria-label={t('common.close')}>
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="max-h-[75dvh] overflow-y-auto p-5">{open && children}</div>
    </dialog>
  )
}
