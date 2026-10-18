export const VEHICLES_KEY = ['admin', 'vehicles'] as const
export const vehicleKey = (id: number) => ['admin', 'vehicle', id] as const
export const BRANCHES_KEY = ['admin', 'branches'] as const
export const CATEGORIES_KEY = ['admin', 'categories'] as const
export const TARIFFS_KEY = ['admin', 'tariffs'] as const
export const ADD_ONS_KEY = ['admin', 'add-ons'] as const
export const DISCOUNTS_KEY = ['admin', 'discount-codes'] as const
export const STAFF_KEY = ['admin', 'staff'] as const
export const staffKey = (id: number) => ['admin', 'staff-account', id] as const
export const CUSTOMERS_KEY = ['admin', 'customers'] as const
export const customerKey = (id: number) => ['admin', 'customer', id] as const
export const AUDIT_KEY = ['admin', 'audit'] as const
