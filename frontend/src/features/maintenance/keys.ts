export const JOBS_KEY = ['maintenance', 'jobs'] as const
export const jobKey = (id: number) => ['maintenance', 'job', id] as const
export const CLEARANCES_KEY = ['maintenance', 'clearances'] as const
export const TECHNICIANS_KEY = ['maintenance', 'technicians'] as const
export const VEHICLES_KEY = ['maintenance', 'vehicles'] as const
