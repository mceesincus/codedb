import { generateInvoice } from "../services/billing"

export function retryInvoiceGeneration(orderId: string) {
  return generateInvoice(orderId)
}
