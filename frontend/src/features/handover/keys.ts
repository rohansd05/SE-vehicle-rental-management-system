export const COLLECTIONS_KEY = ['handover', 'collections'] as const
export const handoverKey = (id: number) => ['handover', 'detail', id] as const
export const RETURNS_KEY = ['handover', 'returns'] as const
export const returnKey = (id: number) => ['handover', 'return', id] as const
