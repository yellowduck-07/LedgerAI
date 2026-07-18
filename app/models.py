from sqlalchemy import Boolean, Column, Float, Integer, String

from app.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String, index=True, nullable=False)
    date = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    customer_name = Column(String, default="")
    vendor_name = Column(String, nullable=True)
    is_purchase = Column(Boolean, default=False)
    gstin = Column(String, nullable=True)
    gst_rate = Column(Float, default=0.0)
    place_of_supply = Column(String, default="")
    supply_type = Column(String, default="B2C")
    hsn_sac = Column(String, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    direction = Column(String, nullable=False)
    category = Column(String, nullable=True)
    vendor_name = Column(String, nullable=True)
    pan_available = Column(Boolean, default=False)
    matched_invoice_number = Column(String, nullable=True)
