// Light and dark themes follow the operating system setting.

export function followSystemTheme(): () => void {
  const query = window.matchMedia('(prefers-color-scheme: dark)')
  const apply = () => document.documentElement.classList.toggle('dark', query.matches)
  apply()
  query.addEventListener('change', apply)
  return () => query.removeEventListener('change', apply)
}
