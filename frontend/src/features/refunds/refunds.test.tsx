import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { makeRefund, page } from '@/features/payment/fixtures'
import type { Refund } from '@/features/payment/api'
import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

function adminReviewing(queue: Refund[] = [makeRefund()], decide?: (action: string, body: Record<string, string>) => Response) {
  const decisions: { action: string; body: Record<string, string> }[] = []
  let waiting = queue
  signedInAs('ADMINISTRATOR')
  server.use(
    http.get(`${API}/payments/refunds/`, ({ request }) => {
      expect(new URL(request.url).searchParams.get('status')).toBe('Pending Approval')
      return HttpResponse.json(page(waiting))
    }),
    http.post(`${API}/payments/refunds/:id/:action/`, async ({ params, request }) => {
      const body = (await request.json()) as Record<string, string>
      const action = String(params.action)
      decisions.push({ action, body })
      if (decide) return decide(action, body)
      waiting = []
      return HttpResponse.json(
        action === 'approve'
          ? makeRefund({ status: 'Issued', decided_by_name: 'Anil Admin' })
          : makeRefund({ status: 'Rejected', rejection_reason: body.reason }),
      )
    }),
  )
  renderApp({ route: '/app/refunds' })
  return decisions
}

describe('refund approval (UC 13 Approve Refund)', () => {
  it('lists each pending refund with its amount, reason, customer and booking', async () => {
    adminReviewing()
    expect(await screen.findByText('1 refund is waiting.')).toBeInTheDocument()
    const row = screen.getByText('Cancelled by the branch').closest('li') as HTMLElement
    expect(row).toHaveTextContent('Asha Rao')
    expect(row).toHaveTextContent('VRMS-20261011-0001')
    expect(row).toHaveTextContent('₹6,372.00 of the rental · Card')
    expect(row).toHaveTextContent('by Ravi Staff')
  })

  it('approves with the password; the refund is issued and the queue empties', async () => {
    const decisions = adminReviewing()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Approve' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('you are recorded as the approver')
    await user.type(within(dialog).getByLabelText('Your password'), 'Test@12345')
    await user.click(within(dialog).getByRole('button', { name: 'Approve and issue' }))

    expect(
      await screen.findByText('Refund of ₹6,372.00 approved and issued to the original payment method.'),
    ).toBeInTheDocument()
    expect(await screen.findByText('Nothing to approve')).toBeInTheDocument()
    expect(decisions).toEqual([{ action: 'approve', body: { password: 'Test@12345' } }])
  })

  it('an approved cash refund is left for the branch to pay out', async () => {
    adminReviewing([makeRefund({ method: 'Cash' })], () => HttpResponse.json(makeRefund({ status: 'Approved' })))
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Approve' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Your password'), 'Test@12345')
    await user.click(within(dialog).getByRole('button', { name: 'Approve and issue' }))
    expect(await screen.findByText('Refund of ₹6,372.00 approved. The branch pays it out in cash.')).toBeInTheDocument()
  })

  it('rejecting needs a reason, which the customer is sent', async () => {
    const decisions = adminReviewing()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Reject' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Your password'), 'Test@12345')
    await user.click(within(dialog).getByRole('button', { name: 'Reject refund' }))
    expect(await within(dialog).findByText('Give the reason for rejecting the refund.')).toBeInTheDocument()
    expect(decisions).toHaveLength(0)

    await user.type(within(dialog).getByLabelText('Reason'), 'The cancellation was after the cut-off.')
    await user.click(within(dialog).getByRole('button', { name: 'Reject refund' }))
    expect(await screen.findByText('Refund rejected. The customer has been told why.')).toBeInTheDocument()
    expect(decisions).toEqual([
      { action: 'reject', body: { reason: 'The cancellation was after the cut-off.', password: 'Test@12345' } },
    ])
  })

  it('a wrong password is shown on its field and nothing changes (SE-9)', async () => {
    adminReviewing(undefined, () => HttpResponse.json({ password: ['That password is not correct.'] }, { status: 400 }))
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Approve' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Your password'), 'wrong')
    await user.click(within(dialog).getByRole('button', { name: 'Approve and issue' }))
    expect(await within(dialog).findByText('That password is not correct.')).toBeInTheDocument()
    expect(within(dialog).getByLabelText('Your password')).toHaveValue('')
  })

  it('says when no refund is waiting', async () => {
    adminReviewing([])
    expect(await screen.findByText('Nothing to approve')).toBeInTheDocument()
  })

  it('is in the Administrator menu', async () => {
    adminReviewing()
    const menu = (await screen.findAllByRole('navigation', { name: 'Main' }))[0]
    expect(within(menu).getByRole('link', { name: /Refunds/ })).toBeInTheDocument()
  })

  it('is closed to other roles (the API refuses them too)', async () => {
    signedInAs('BRANCH_STAFF')
    renderApp({ route: '/app/refunds' })
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
  })
})
