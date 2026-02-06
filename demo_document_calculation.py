#!/usr/bin/env python
"""
Manual verification script for DocumentCalculationService

This script demonstrates the DocumentCalculationService by creating a sample
sales document with lines and calculating totals.

Run with: python manage.py shell < demo_document_calculation.py
"""

from decimal import Decimal
from datetime import date

from auftragsverwaltung.models import DocumentType, SalesDocument, SalesDocumentLine
from auftragsverwaltung.services import DocumentCalculationService
from core.models import Mandant, TaxRate


def demo_calculation():
    """Demonstrate document calculation service"""
    
    print("\n" + "="*60)
    print("DocumentCalculationService Demonstration")
    print("="*60)
    
    # Get or create test data
    company, _ = Mandant.objects.get_or_create(
        name="Demo Company",
        defaults={
            "adresse": "Demo Street 1",
            "plz": "12345",
            "ort": "Demo City"
        }
    )
    
    doc_type, _ = DocumentType.objects.get_or_create(
        key="demo_invoice",
        defaults={
            "name": "Demo Invoice",
            "prefix": "DI",
            "is_invoice": True,
            "is_active": True
        }
    )
    
    tax_rate_19, _ = TaxRate.objects.get_or_create(
        code="DEMO_VAT_19",
        defaults={
            "name": "19% VAT",
            "rate": Decimal('0.19'),
            "is_active": True
        }
    )
    
    tax_rate_7, _ = TaxRate.objects.get_or_create(
        code="DEMO_VAT_7",
        defaults={
            "name": "7% VAT",
            "rate": Decimal('0.07'),
            "is_active": True
        }
    )
    
    # Create a sample document
    document = SalesDocument.objects.create(
        company=company,
        document_type=doc_type,
        number="DEMO-001",
        status="DRAFT",
        issue_date=date.today()
    )
    
    print(f"\nCreated document: {document.number}")
    print(f"Initial totals: Net={document.total_net}, Tax={document.total_tax}, Gross={document.total_gross}")
    
    # Add lines
    line1 = SalesDocumentLine.objects.create(
        document=document,
        position_no=1,
        line_type='NORMAL',
        is_selected=True,
        description="Product A (19% VAT)",
        quantity=Decimal('2.0000'),
        unit_price_net=Decimal('100.00'),
        tax_rate=tax_rate_19
    )
    
    line2 = SalesDocumentLine.objects.create(
        document=document,
        position_no=2,
        line_type='NORMAL',
        is_selected=True,
        description="Product B (7% VAT)",
        quantity=Decimal('3.0000'),
        unit_price_net=Decimal('50.00'),
        tax_rate=tax_rate_7
    )
    
    line3 = SalesDocumentLine.objects.create(
        document=document,
        position_no=3,
        line_type='OPTIONAL',
        is_selected=True,
        description="Optional Service (19% VAT)",
        quantity=Decimal('1.0000'),
        unit_price_net=Decimal('75.00'),
        tax_rate=tax_rate_19
    )
    
    line4 = SalesDocumentLine.objects.create(
        document=document,
        position_no=4,
        line_type='OPTIONAL',
        is_selected=False,
        description="Optional Service - NOT SELECTED (19% VAT)",
        quantity=Decimal('1.0000'),
        unit_price_net=Decimal('999.00'),
        tax_rate=tax_rate_19
    )
    
    print(f"\nAdded {document.lines.count()} lines to the document:")
    for line in document.lines.all():
        included = "✓" if line.is_included_in_totals() else "✗"
        print(f"  {included} Pos {line.position_no}: {line.description}")
        print(f"    Qty={line.quantity}, Price={line.unit_price_net}, Tax={line.tax_rate.rate}")
    
    # Calculate totals without persisting
    print("\n" + "-"*60)
    print("Calculating totals (persist=False)...")
    result = DocumentCalculationService.recalculate(document, persist=False)
    
    print(f"\nCalculated totals:")
    print(f"  Net:   {result.total_net}")
    print(f"  Tax:   {result.total_tax}")
    print(f"  Gross: {result.total_gross}")
    
    # Verify it wasn't persisted
    document.refresh_from_db()
    print(f"\nDocument totals in DB (should be unchanged):")
    print(f"  Net:   {document.total_net}")
    print(f"  Tax:   {document.total_tax}")
    print(f"  Gross: {document.total_gross}")
    
    # Calculate and persist
    print("\n" + "-"*60)
    print("Calculating totals (persist=True)...")
    result = DocumentCalculationService.recalculate(document, persist=True)
    
    # Verify it was persisted
    document.refresh_from_db()
    print(f"\nDocument totals in DB (should be updated):")
    print(f"  Net:   {document.total_net}")
    print(f"  Tax:   {document.total_tax}")
    print(f"  Gross: {document.total_gross}")
    
    # Breakdown by line
    print("\n" + "-"*60)
    print("Line-by-line breakdown:")
    for line in document.lines.all():
        if line.is_included_in_totals():
            print(f"\nPos {line.position_no}: {line.description}")
            print(f"  Qty × Price = {line.quantity} × {line.unit_price_net} = {line.line_net}")
            print(f"  Tax ({line.tax_rate.rate}) = {line.line_tax}")
            print(f"  Gross = {line.line_gross}")
        else:
            print(f"\nPos {line.position_no}: {line.description} [NOT INCLUDED]")
    
    # Clean up
    print("\n" + "-"*60)
    print("Cleaning up demo data...")
    document.delete()
    print("Demo completed successfully!")
    print("="*60 + "\n")


if __name__ == '__main__':
    demo_calculation()
