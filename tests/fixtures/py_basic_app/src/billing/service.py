from repository import InvoiceRepository


class BillingService:
    def generate_invoice(self, order_id: str):
        repository = InvoiceRepository()
        return repository.save(order_id)


def create_service():
    return BillingService()

