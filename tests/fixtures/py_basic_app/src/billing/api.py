from service import BillingService


def create_invoice_handler(order_id: str):
    service = BillingService()
    return service.generate_invoice(order_id)

