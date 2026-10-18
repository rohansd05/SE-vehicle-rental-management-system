import type { SearchQuery } from './api'

export const BRANCHES_KEY = ['fleet', 'branches'] as const
export const CATEGORIES_KEY = ['fleet', 'categories'] as const
export const searchKey = (query: SearchQuery) => ['fleet', 'search', query] as const
export const alternativesKey = (query: SearchQuery) => ['fleet', 'search', 'alternatives', query] as const
