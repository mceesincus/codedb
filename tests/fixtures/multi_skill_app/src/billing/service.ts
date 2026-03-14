import { sendInvoiceEmail } from "../notifications/service"

export class BillingService {
  generateInvoice(orderId: string) {
    return sendInvoiceEmail(orderId)
  }
}
