import {
  Apple,
  Home,
  Package,
  Shirt,
  Smartphone,
  Sprout,
  UtensilsCrossed,
  type LucideIcon,
} from 'lucide-react'

const ICONS: Record<string, LucideIcon> = {
  utensils: UtensilsCrossed,
  shirt: Shirt,
  sprout: Sprout,
  smartphone: Smartphone,
  home: Home,
  package: Package,
  apple: Apple,
}

export function CategoryIcon({ name, className = 'h-6 w-6' }: { name: string; className?: string }) {
  const Icon = ICONS[name] ?? Package
  return <Icon className={className} aria-hidden />
}
