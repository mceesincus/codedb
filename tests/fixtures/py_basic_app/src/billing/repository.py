class InvoiceRepository:
    def save(self, order_id: str):
        return {"order_id": order_id}

