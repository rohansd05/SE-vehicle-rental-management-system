import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import type { Licence, LicenceReview } from '@/api/types'
import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { LicenceStatusCard } from './LicenceStatusCard'

const BASE: Licence = {
  id: 7,
  licence_number: 'MH02 20190012345',
  issuing_authority: 'RTO Mumbai (West)',
  issue_date: '2019-06-01',
  expiry_date: '2039-05-31',
  categories: ['Car', 'Two-Wheeler'],
  status: 'Not Submitted',
  rejection_reason: '',
  verified_at: null,
  front_image_url: null,
  back_image_url: null,
  updated_at: '2026-10-01T10:00:00Z',
}

const REVIEW: LicenceReview = {
  ...BASE,
  status: 'Pending Verification',
  front_image_url: 'http://localhost:3000/api/v1/files/front/',
  back_image_url: 'http://localhost:3000/api/v1/files/back/',
  customer: {
    customer_id: 3,
    name: 'Asha Rao',
    email: 'asha@example.com',
    mobile_no: '+919812345678',
    date_of_birth: '1996-04-12',
  },
}

/** A real Not Submitted licence has no details yet. */
const EMPTY: Licence = {
  ...BASE,
  licence_number: '',
  issuing_authority: '',
  issue_date: null,
  expiry_date: null,
  categories: [],
}

const png = (name = 'front.png', bytes = 2048) =>
  new File([new Uint8Array(bytes)], name, { type: 'image/png' })

function customerWith(licence: Licence) {
  signedInAs('CUSTOMER')
  server.use(http.get(`${API}/licence/`, () => HttpResponse.json(licence)))
  renderApp({ route: '/app/licence' })
}

describe('licence status card', () => {
  it.each([
    ['Not Submitted', /haven’t submitted a driving licence/],
    ['Pending Verification', /Our staff are checking your licence/],
    ['Verified', /verified on/],
    ['Rejected', 'Photo is blurred.'],
    ['Expired', /Your licence expired on/],
  ] as const)('renders %s', (status, text) => {
    render(
      <LicenceStatusCard
        licence={{
          ...BASE,
          status,
          rejection_reason: status === 'Rejected' ? 'Photo is blurred.' : '',
          verified_at: status === 'Verified' ? '2026-10-02T10:00:00Z' : null,
        }}
      />,
    )
    expect(screen.getByText(status)).toBeInTheDocument()
    expect(screen.getByText(text)).toBeInTheDocument()
  })
})

describe('licence submission (customer)', () => {
  it('rejects a file of the wrong type before upload', async () => {
    customerWith(EMPTY)
    const user = userEvent.setup({ applyAccept: false })
    const input = await screen.findByLabelText('Front of the licence')
    await user.upload(input, new File(['GIF89a'], 'licence.gif', { type: 'image/gif' }))
    expect(await screen.findByText('Choose a JPG or PNG image.')).toBeInTheDocument()
    expect((input as HTMLInputElement).value).toBe('')
  })

  it('rejects a file over 5 MB before upload', async () => {
    customerWith(EMPTY)
    const user = userEvent.setup()
    const input = await screen.findByLabelText('Back of the licence')
    await user.upload(input, png('back.png', 5 * 1024 * 1024 + 1))
    expect(
      await screen.findByText('This image is larger than 5 MB. Choose a smaller photo.'),
    ).toBeInTheDocument()
  })

  it('submits every field and both images, then shows Pending Verification', async () => {
    let received: FormData | undefined
    customerWith(EMPTY)
    server.use(
      http.post(`${API}/licence/`, async ({ request }) => {
        received = await request.formData()
        return HttpResponse.json({ ...BASE, status: 'Pending Verification' })
      }),
    )
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Licence number'), 'MH02 20190012345')
    await user.type(screen.getByLabelText('Issued by'), 'RTO Mumbai (West)')
    await user.type(screen.getByLabelText('Issue date'), '2019-06-01')
    await user.type(screen.getByLabelText('Expiry date'), '2039-05-31')
    await user.click(screen.getByLabelText('Car'))
    await user.upload(screen.getByLabelText('Front of the licence'), png('front.png'))
    await user.upload(screen.getByLabelText('Back of the licence'), png('back.png'))
    await user.click(screen.getByRole('button', { name: 'Submit for verification' }))

    expect(await screen.findByText(/Your licence has been submitted/)).toBeInTheDocument()
    expect(screen.getByText('Pending Verification')).toBeInTheDocument()
    expect(received?.get('licence_number')).toBe('MH02 20190012345')
    expect(received?.getAll('categories')).toEqual(['Car'])
    // jsdom + Node fetch turn a File into a Blob named "blob"; browsers keep the
    // name. Both images arrive, with their contents.
    expect((received!.get('front_image') as Blob).size).toBe(2048)
    expect((received!.get('back_image') as Blob).size).toBe(2048)
  })

  it('requires both photos', async () => {
    customerWith(EMPTY)
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Licence number'), 'X1')
    await user.type(screen.getByLabelText('Issued by'), 'RTO')
    await user.type(screen.getByLabelText('Issue date'), '2019-06-01')
    await user.type(screen.getByLabelText('Expiry date'), '2039-05-31')
    await user.click(screen.getByLabelText('Two-Wheeler'))
    await user.click(screen.getByRole('button', { name: 'Submit for verification' }))
    expect(await screen.findByText('Add a photo of the front of the licence.')).toBeInTheDocument()
    expect(screen.getByText('Add a photo of the back of the licence.')).toBeInTheDocument()
  })

  it('refuses an already-expired licence (BR-2)', async () => {
    customerWith(EMPTY)
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Expiry date'), '2020-01-01')
    await user.click(screen.getByRole('button', { name: 'Submit for verification' }))
    expect(await screen.findByText('This licence has already expired.')).toBeInTheDocument()
  })

  it('shows the rejection reason and offers resubmission', async () => {
    customerWith({ ...BASE, status: 'Rejected', rejection_reason: 'Back photo unreadable.' })
    expect(await screen.findByText('Back photo unreadable.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Submit your licence again' })).toBeInTheDocument()
  })
})

describe('licence verification (staff)', () => {
  function staffQueue() {
    signedInAs('BRANCH_STAFF')
    server.use(
      http.get(`${API}/licences/`, () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [REVIEW] }),
      ),
    )
  }

  it('lists the pending queue and opens a licence with both images', async () => {
    staffQueue()
    const user = userEvent.setup()
    renderApp({ route: '/app/licences' })
    await user.click(await screen.findByRole('link', { name: /Asha Rao/ }))
    expect(await screen.findByRole('heading', { name: 'Review licence: Asha Rao' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Front of the licence' })).toHaveAttribute('src', REVIEW.front_image_url)
    expect(screen.getByRole('img', { name: 'Back of the licence' })).toHaveAttribute('src', REVIEW.back_image_url)
  })

  it('shows an empty state when nothing is waiting', async () => {
    signedInAs('ADMINISTRATOR')
    server.use(
      http.get(`${API}/licences/`, () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    )
    renderApp({ route: '/app/licences' })
    expect(await screen.findByText('Nothing to check')).toBeInTheDocument()
  })

  it('requires a reason to reject', async () => {
    staffQueue()
    const reject = vi.fn()
    server.use(
      http.post(`${API}/licences/7/reject/`, async ({ request }) => {
        reject(await request.json())
        return HttpResponse.json({ ...REVIEW, status: 'Rejected' })
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/licences/7' })
    await user.click(await screen.findByRole('button', { name: 'Reject' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Reject licence' }))
    expect(await within(dialog).findByText('Give the customer a reason, so they can fix it.')).toBeInTheDocument()
    expect(reject).not.toHaveBeenCalled()

    await user.type(within(dialog).getByLabelText('Reason'), 'Back photo unreadable.')
    await user.click(within(dialog).getByRole('button', { name: 'Reject licence' }))
    expect(await screen.findByText(/Licence rejected for Asha Rao/)).toBeInTheDocument()
    expect(reject).toHaveBeenCalledWith({ reason: 'Back photo unreadable.' })
  })

  it('approves and returns to the queue', async () => {
    staffQueue()
    server.use(
      http.post(`${API}/licences/7/approve/`, () => HttpResponse.json({ ...REVIEW, status: 'Verified' })),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/licences/7' })
    await user.click(await screen.findByRole('button', { name: 'Approve' }))
    expect(await screen.findByText(/Licence approved for Asha Rao/)).toBeInTheDocument()
  })
})
