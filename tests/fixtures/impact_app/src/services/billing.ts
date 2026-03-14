import { saveInvoice } from "../storage/repository"

export function generateInvoice(orderId: string) {
  return saveInvoice(orderId)
}
