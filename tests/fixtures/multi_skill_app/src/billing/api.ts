import { BillingService } from "./service"

export function createInvoiceHandler(orderId: string) {
  const service = new BillingService()
  return service.generateInvoice(orderId)
}
