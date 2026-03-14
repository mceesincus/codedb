import { generateInvoice } from "../services/billing"

export function createInvoiceHandler(orderId: string) {
  return generateInvoice(orderId)
}
