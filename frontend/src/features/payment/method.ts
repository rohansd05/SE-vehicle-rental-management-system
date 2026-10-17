// Pay.Method choices and their request fields, shared by the payment and due screens.

import type { Channel, MethodRequest } from './api'

/**
 * Sandbox tokens (SI-1, Testability: "a test mode in which the payment ...
 * integrations use sandbox endpoints"). A live gateway's hosted fields would
 * produce the token instead; no card number ever reaches VRMS (CO-2).
 */
export const TEST_TOKENS = [
  { value: 'tok_visa', label: 'Test card that is approved' },
  { value: 'tok_decline', label: 'Test card that is declined' },
] as const

/** D6: on-line transfer and wallet are channels of one OnlinePayment; sandbox outcomes. */
export const ONLINE_TOKENS = [
  { value: 'tok_online', label: 'Test payment that is approved' },
  { value: 'tok_decline', label: 'Test payment that is declined' },
] as const

export const CHANNELS: readonly { value: Channel; label: string }[] = [
  { value: 'UPI', label: 'UPI' },
  { value: 'Net Banking', label: 'Net banking' },
  { value: 'Wallet', label: 'Wallet' },
]

export type Method = MethodRequest['method']

export interface MethodChoice {
  method: Method
  cardToken: string
  onlineToken: string
  channel: Channel
  upiId: string
}

export const initialChoice = (method: Method = 'card'): MethodChoice => ({
  method,
  cardToken: TEST_TOKENS[0].value,
  onlineToken: ONLINE_TOKENS[0].value,
  channel: 'UPI',
  upiId: '',
})

/** The request fields for the chosen method (Pay.Method). */
export function methodRequest(choice: MethodChoice): MethodRequest {
  if (choice.method === 'online') {
    return {
      method: 'online',
      payment_token: choice.onlineToken,
      channel: choice.channel,
      upi_id: choice.channel === 'UPI' ? choice.upiId.trim() : '',
    }
  }
  if (choice.method === 'cash') return { method: 'cash', payment_token: '', channel: '', upi_id: '' }
  return { method: 'card', payment_token: choice.cardToken, channel: '', upi_id: '' }
}

