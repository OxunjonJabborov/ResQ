import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ImagePlus, Plus, Trash2, X } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../api/client'
import { sellerApi, type SellerProductInput } from '../../api/endpoints'
import type { Condition, MarkdownRule, MarkdownStep, SellerProduct, Unit } from '../../api/types'
import { ErrorState, InlineError, PageSpinner, Spinner } from '../../components/States'
import { ProductStatusBadge } from '../../components/StatusBadge'
import { toast } from '../../components/Toast'
import { flattenCategories, useCategories } from '../../hooks/queries'
import { formatDate, formatDateTime, formatMoney } from '../../lib/format'

const UNITS: Unit[] = ['piece', 'kg', 'g', 'l', 'ml', 'pack', 'box', 'set']
const CONDITIONS: Condition[] = ['new', 'opened_packaging', 'display_item', 'slight_defect']

interface FormState {
  title: string
  description: string
  category: string
  original_price: string
  current_price: string
  quantity: string
  unit: Unit
  unit_weight_kg: string
  expiry_date: string
  condition: Condition
  condition_note: string
}

const EMPTY: FormState = {
  title: '',
  description: '',
  category: '',
  original_price: '',
  current_price: '',
  quantity: '1',
  unit: 'piece',
  unit_weight_kg: '',
  expiry_date: '',
  condition: 'new',
  condition_note: '',
}

function toForm(p: SellerProduct): FormState {
  return {
    title: p.title,
    description: p.description,
    category: String(p.category),
    original_price: String(p.original_price),
    current_price: String(p.current_price),
    quantity: String(p.quantity),
    unit: p.unit,
    unit_weight_kg: p.unit_weight_kg ?? '',
    expiry_date: p.expiry_date ?? '',
    condition: p.condition,
    condition_note: p.condition_note,
  }
}

function toInput(f: FormState): SellerProductInput {
  return {
    title: f.title.trim(),
    description: f.description,
    category: Number(f.category),
    original_price: Number(f.original_price),
    current_price: Number(f.current_price),
    quantity: Number(f.quantity),
    unit: f.unit,
    unit_weight_kg: f.unit_weight_kg || null,
    expiry_date: f.expiry_date || null,
    condition: f.condition,
    condition_note: f.condition_note,
  }
}

function Images({ product }: { product: SellerProduct }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const refresh = () => void qc.invalidateQueries({ queryKey: ['seller-product', String(product.id)] })
  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      for (const file of files) await sellerApi.uploadImage(product.id, file)
    },
    onSettled: refresh,
  })
  const remove = useMutation({ mutationFn: (imageId: number) => sellerApi.deleteImage(product.id, imageId), onSuccess: refresh })
  return (
    <section className="card space-y-3 p-5">
      <h2 className="font-semibold">{t('productForm.images')}</h2>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
        {product.images.map((img) => (
          <div key={img.id} className="relative aspect-square overflow-hidden rounded-xl bg-surface">
            <img src={img.image} alt="" className="h-full w-full object-cover" />
            <button
              type="button"
              className="absolute right-1 top-1 rounded-full bg-black/60 p-1 text-white"
              onClick={() => remove.mutate(img.id)}
              aria-label={t('common.delete')}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
        {product.images.length < 8 && (
          <label className="flex aspect-square cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-line text-muted hover:border-brand-600 hover:text-brand-700">
            {upload.isPending ? <Spinner /> : <ImagePlus className="h-6 w-6" aria-hidden />}
            <span className="text-xs">{t('productForm.addImages')}</span>
            <input
              type="file"
              className="sr-only"
              accept="image/jpeg,image/png,image/webp"
              multiple
              onChange={(e) => {
                const files = Array.from(e.target.files ?? []).slice(0, 8 - product.images.length)
                if (files.length) upload.mutate(files)
                e.target.value = ''
              }}
            />
          </label>
        )}
      </div>
      <p className="text-xs text-muted">{t('productForm.imagesHint')}</p>
      <InlineError error={upload.error ?? remove.error} />
    </section>
  )
}

function MarkdownEditor({ product }: { product: SellerProduct }) {
  const { t } = useTranslation()
  const key = ['markdown', product.id]
  const rule = useQuery({
    queryKey: key,
    queryFn: () => sellerApi.markdown(product.id).catch((e) => (e instanceof ApiError && e.status === 404 ? null : Promise.reject(e))),
  })
  if (!product.expiry_date) {
    return (
      <section className="card p-5">
        <h2 className="font-semibold">{t('productForm.markdown')}</h2>
        <p className="mt-1 text-sm text-muted">{t('productForm.markdownNeedsExpiry')}</p>
      </section>
    )
  }
  if (rule.isPending) return <Spinner />
  if (rule.isError) return <ErrorState error={rule.error} onRetry={() => void rule.refetch()} />
  return <MarkdownForm key={rule.data ? 'saved' : 'new'} product={product} rule={rule.data} queryKey={key} />
}

function MarkdownForm({ product, rule, queryKey: key }: { product: SellerProduct; rule: MarkdownRule | null; queryKey: unknown[] }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [enabled, setEnabled] = useState(rule?.is_active ?? true)
  const [minPrice, setMinPrice] = useState(() =>
    String(rule ? rule.min_price : Math.round((product.original_price * 0.3) / 100) * 100),
  )
  const [steps, setSteps] = useState<MarkdownStep[]>(
    rule?.steps ?? [
      { days_before_expiry: 3, discount_percent: 30 },
      { days_before_expiry: 1, discount_percent: 50 },
    ],
  )

  const save = useMutation({
    mutationFn: () => sellerApi.saveMarkdown(product.id, { is_active: enabled, min_price: Number(minPrice), steps }),
    onSuccess: (data) => {
      qc.setQueryData(key, data)
      toast(t('common.saved'))
    },
  })
  const remove = useMutation({
    mutationFn: () => sellerApi.deleteMarkdown(product.id),
    onSuccess: () => qc.setQueryData(key, null),
  })

  const setStep = (i: number, patch: Partial<MarkdownStep>) => setSteps((s) => s.map((step, j) => (j === i ? { ...step, ...patch } : step)))

  return (
    <section className="card space-y-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">{t('productForm.markdown')}</h2>
          <p className="text-sm text-muted">{t('productForm.markdownHint')}</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-brand-700" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          {t('productForm.markdownEnabled')}
        </label>
      </div>
      <label className="block max-w-xs">
        <span className="label">{t('productForm.minPrice')}</span>
        <input className="input" inputMode="numeric" value={minPrice} onChange={(e) => setMinPrice(e.target.value.replace(/\D/g, ''))} />
      </label>
      <div className="space-y-2">
        <div className="grid grid-cols-[1fr_1fr_auto] gap-2 text-xs font-medium text-muted">
          <span>{t('productForm.daysBefore')}</span>
          <span>{t('productForm.discountPct')}</span>
          <span className="w-9" />
        </div>
        {steps.map((step, i) => (
          <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2">
            <input className="input" type="number" min={0} max={60} value={step.days_before_expiry} onChange={(e) => setStep(i, { days_before_expiry: Number(e.target.value) })} aria-label={t('productForm.daysBefore')} />
            <input className="input" type="number" min={1} max={99} value={step.discount_percent} onChange={(e) => setStep(i, { discount_percent: Number(e.target.value) })} aria-label={t('productForm.discountPct')} />
            <button type="button" className="btn-ghost !px-2" onClick={() => setSteps((s) => s.filter((_, j) => j !== i))} aria-label={t('common.delete')}>
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        {steps.length < 10 && (
          <button type="button" className="btn-ghost" onClick={() => setSteps((s) => [...s, { days_before_expiry: 0, discount_percent: 70 }])}>
            <Plus className="h-4 w-4" aria-hidden /> {t('productForm.addStep')}
          </button>
        )}
      </div>
      <InlineError error={save.error ?? remove.error} />
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-primary" disabled={save.isPending || !steps.length || !minPrice} onClick={() => save.mutate()}>
          {t('productForm.saveRule')}
        </button>
        {rule && (
          <button type="button" className="btn-ghost text-red-600" onClick={() => remove.mutate()}>
            {t('productForm.deleteRule')}
          </button>
        )}
      </div>
      {rule && rule.preview.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold">{t('productForm.preview')}</h3>
          <div className="flex flex-wrap gap-2">
            {rule.preview.map((row) => (
              <span key={row.date} className="rounded-lg bg-surface px-2.5 py-1.5 text-xs">
                <span className="text-muted">{formatDate(row.date)}:</span> <span className="font-semibold">{formatMoney(row.price)}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

function PriceHistory({ productId }: { productId: number }) {
  const { t } = useTranslation()
  const query = useQuery({ queryKey: ['price-history', productId], queryFn: () => sellerApi.priceHistory(productId) })
  return (
    <section className="card p-5">
      <h2 className="mb-2 font-semibold">{t('productForm.priceHistory')}</h2>
      {query.isPending ? (
        <Spinner />
      ) : !query.data?.length ? (
        <p className="text-sm text-muted">{t('productForm.noHistory')}</p>
      ) : (
        <ul className="divide-y divide-line text-sm">
          {query.data.map((row, i) => (
            <li key={i} className="flex flex-wrap justify-between gap-2 py-2">
              <span className="text-muted">{formatDateTime(row.created_at)}</span>
              <span>
                {formatMoney(row.old_price)} → <span className="font-semibold">{formatMoney(row.new_price)}</span>
              </span>
              <span className="text-xs text-muted">{t(`productForm.reasons.${row.reason}`)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function SellerProductFormPage() {
  const { id } = useParams()
  const product = useQuery({ queryKey: ['seller-product', id], queryFn: () => sellerApi.product(id!), enabled: !!id })
  if (id && product.isPending) return <PageSpinner />
  if (id && product.isError) return <ErrorState error={product.error} onRetry={() => void product.refetch()} />
  // Re-mount when switching between products so the form re-seeds.
  return <ProductForm key={id ?? 'new'} id={id} product={product.data} />
}

function ProductForm({ id, product: loaded }: { id?: string; product?: SellerProduct }) {
  const isNew = !id
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const categories = useCategories()
  // The cached product (updated after saves and image uploads) drives the side panels.
  const product = useQuery({
    queryKey: ['seller-product', id],
    queryFn: () => sellerApi.product(id!),
    enabled: !!id,
    initialData: loaded,
  })
  const [form, setForm] = useState<FormState>(() => (loaded ? toForm(loaded) : EMPTY))

  const flat = useMemo(() => flattenCategories(categories.data), [categories.data])
  const selected = flat.find(([c]) => String(c.id) === form.category)?.[0]
  const expiryRequired = !!selected?.requires_expiry_date
  const discount =
    Number(form.original_price) > 0 && Number(form.current_price) > 0
      ? Math.floor(((Number(form.original_price) - Number(form.current_price)) * 100) / Number(form.original_price))
      : null

  const save = useMutation({
    mutationFn: (publish: boolean) =>
      isNew
        ? sellerApi.createProduct({ ...toInput(form), status: publish ? 'active' : 'draft' })
        : sellerApi.updateProduct(Number(id), toInput(form)).then((p) =>
            publish && p.status !== 'active' && p.status !== 'sold_out' ? sellerApi.setStatus(p.id, 'active') : p,
          ),
    onSuccess: (p) => {
      void qc.invalidateQueries({ queryKey: ['seller-products'] })
      qc.setQueryData(['seller-product', String(p.id)], p)
      void qc.invalidateQueries({ queryKey: ['price-history', p.id] })
      toast(t('common.saved'))
      if (isNew) navigate(`/seller/products/${p.id}`, { replace: true })
    },
  })

  const fieldErrors = save.error instanceof ApiError ? save.error.fieldErrors : {}
  const err = (key: string) => fieldErrors[key] && <span className="mt-1 block text-xs text-red-600">{fieldErrors[key]}</span>
  const set = (key: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))
  const digits = (key: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [key]: e.target.value.replace(/\D/g, '') }))
  const today = new Date().toISOString().slice(0, 10)

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-bold">{isNew ? t('productForm.titleNew') : t('productForm.titleEdit')}</h2>
        {product.data && <ProductStatusBadge status={product.data.status} />}
      </div>
      <form
        className="card space-y-4 p-5"
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          save.mutate(true)
        }}
      >
        <label className="block">
          <span className="label">{t('productForm.name')}</span>
          <input className="input" required maxLength={200} value={form.title} onChange={set('title')} />
          {err('title')}
        </label>
        <label className="block">
          <span className="label">{t('productForm.category')}</span>
          <select className="input" required value={form.category} onChange={set('category')}>
            <option value="">{t('productForm.chooseCategory')}</option>
            {flat.map(([c, depth]) => (
              <option key={c.id} value={c.id}>
                {'  '.repeat(depth * 2)}
                {c.name}
              </option>
            ))}
          </select>
          {err('category')}
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="label">{t('productForm.originalPrice')}</span>
            <input className="input" required inputMode="numeric" value={form.original_price} onChange={digits('original_price')} />
            {err('original_price')}
          </label>
          <label className="block">
            <span className="label">{t('productForm.currentPrice')}</span>
            <input className="input" required inputMode="numeric" value={form.current_price} onChange={digits('current_price')} />
            {discount !== null && discount > 0 && <span className="mt-1 block text-xs font-medium text-deal-700">{t('productForm.discountPreview', { pct: discount })}</span>}
            {err('current_price')}
          </label>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="label">{t('productForm.quantity')}</span>
            <input className="input" required inputMode="numeric" value={form.quantity} onChange={digits('quantity')} />
            {err('quantity')}
          </label>
          <label className="block">
            <span className="label">{t('productForm.unit')}</span>
            <select className="input" value={form.unit} onChange={set('unit')}>
              {UNITS.map((u) => (
                <option key={u} value={u}>
                  {t(`product.units.${u}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">{t('productForm.unitWeight')}</span>
            <input className="input" inputMode="decimal" value={form.unit_weight_kg} onChange={set('unit_weight_kg')} placeholder="0.5" />
            {err('unit_weight_kg')}
          </label>
        </div>
        <label className="block max-w-xs">
          <span className="label">
            {t('productForm.expiryDate')}{' '}
            {expiryRequired ? <span className="font-normal text-deal-700">· {t('productForm.expiryRequired')}</span> : <span className="font-normal text-muted">({t('common.optional')})</span>}
          </span>
          <input className="input" type="date" min={today} required={expiryRequired} value={form.expiry_date} onChange={set('expiry_date')} />
          {err('expiry_date')}
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="label">{t('productForm.condition')}</span>
            <select className="input" value={form.condition} onChange={set('condition')}>
              {CONDITIONS.map((c) => (
                <option key={c} value={c}>
                  {t(`product.conditions.${c}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">{t('productForm.conditionNote')}</span>
            <input className="input" maxLength={255} value={form.condition_note} onChange={set('condition_note')} />
          </label>
        </div>
        <label className="block">
          <span className="label">{t('productForm.description')}</span>
          <textarea className="input min-h-24" value={form.description} onChange={set('description')} />
        </label>
        <InlineError error={save.error && !Object.keys(fieldErrors).length ? save.error : null} />
        <div className="flex flex-col gap-2 sm:flex-row">
          <button type="submit" className="btn-primary flex-1" disabled={save.isPending}>
            {save.isPending && <Spinner className="h-4 w-4 !text-white" />}
            {t('productForm.publish')}
          </button>
          <button type="button" className="btn-secondary" disabled={save.isPending} onClick={() => save.mutate(false)}>
            {isNew ? t('productForm.saveDraft') : t('common.save')}
          </button>
        </div>
      </form>

      {product.data ? (
        <>
          <Images product={product.data} />
          <MarkdownEditor product={product.data} />
          <PriceHistory productId={product.data.id} />
        </>
      ) : (
        <p className="text-sm text-muted">{t('productForm.imagesAfterSave')}</p>
      )}
    </div>
  )
}
