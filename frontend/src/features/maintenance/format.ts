/** Whole kilometres, Indian digit grouping (Appendix A odometer reading). */
export const formatKm = (km: number | null | undefined) =>
  km === null || km === undefined ? '—' : `${new Intl.NumberFormat('en-IN').format(km)} km`
