import { deliverEmail } from "./email"

export function sendInvoiceEmail(orderId: string) {
  return deliverEmail(orderId)
}
