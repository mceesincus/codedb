import { createInvoiceHandler } from "./handlers/invoice"

export function runInvoice(orderId: string) {
  return createInvoiceHandler(orderId)
}
