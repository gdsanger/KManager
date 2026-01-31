#!/usr/bin/env python
"""
Demonstration script for Core Report Service

This script demonstrates:
1. How to use the ReportService to generate PDFs
2. How to store reports with context snapshots
3. Multi-page reports with headers, footers, and page numbers
4. Querying stored reports

Run this with: python manage.py shell < demo_report_service.py
Or: python demo_report_service.py (if Django environment is set up)
"""
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kmanager.settings')
django.setup()

from django.contrib.auth.models import User
from core.services.reporting import ReportService, list_templates
from core.models import ReportDocument


def demo_list_templates():
    """Demonstrate listing available report templates"""
    print("=" * 70)
    print("1. LISTING AVAILABLE REPORT TEMPLATES")
    print("=" * 70)
    
    templates = list_templates()
    print(f"Available templates: {templates}")
    print()


def demo_simple_report():
    """Demonstrate generating a simple report"""
    print("=" * 70)
    print("2. GENERATING A SIMPLE REPORT")
    print("=" * 70)
    
    context = {
        'title': 'Demo Change Report',
        'change_id': 'CHG-DEMO-001',
        'date': '2024-01-31',
        'description': 'This is a demonstration change report showcasing the Core Report Service.',
        'items': [
            {'position': '1', 'description': 'Implemented Core Report Service', 'status': 'Completed'},
            {'position': '2', 'description': 'Added ReportDocument model', 'status': 'Completed'},
            {'position': '3', 'description': 'Created change.v1 template', 'status': 'Completed'},
        ],
        'notes': 'All acceptance criteria have been met.',
    }
    
    pdf_bytes = ReportService.render('change.v1', context)
    
    print(f"Generated PDF: {len(pdf_bytes)} bytes")
    print(f"PDF header: {pdf_bytes[:8]}")
    
    # Save to file for inspection
    with open('/tmp/demo_simple_report.pdf', 'wb') as f:
        f.write(pdf_bytes)
    print("Saved to: /tmp/demo_simple_report.pdf")
    print()


def demo_multipage_report():
    """Demonstrate generating a multi-page report with many items"""
    print("=" * 70)
    print("3. GENERATING A MULTI-PAGE REPORT")
    print("=" * 70)
    
    # Create context with many items to force multiple pages
    context = {
        'title': 'Multi-Page Change Report',
        'change_id': 'CHG-DEMO-002',
        'date': '2024-01-31',
        'description': 'This report contains many items to demonstrate multi-page functionality.',
        'items': [
            {
                'position': str(i), 
                'description': f'Change item {i}: Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
                'status': 'Done' if i % 3 == 0 else 'In Progress'
            }
            for i in range(1, 51)  # 50 items
        ],
        'notes': 'This report should span multiple pages with headers, footers, and page numbers.',
    }
    
    pdf_bytes = ReportService.render('change.v1', context)
    
    print(f"Generated multi-page PDF: {len(pdf_bytes)} bytes")
    
    # Save to file for inspection
    with open('/tmp/demo_multipage_report.pdf', 'wb') as f:
        f.write(pdf_bytes)
    print("Saved to: /tmp/demo_multipage_report.pdf")
    print()


def demo_store_report():
    """Demonstrate storing a report with context snapshot"""
    print("=" * 70)
    print("4. STORING A REPORT WITH CONTEXT SNAPSHOT")
    print("=" * 70)
    
    # Get or create a test user
    user, _ = User.objects.get_or_create(
        username='demo_user',
        defaults={
            'email': 'demo@example.com',
            'first_name': 'Demo',
            'last_name': 'User'
        }
    )
    
    context = {
        'title': 'Stored Change Report',
        'change_id': 'CHG-DEMO-003',
        'date': '2024-01-31',
        'description': 'This report will be stored in the database with its context snapshot.',
        'items': [
            {'position': '1', 'description': 'Database persistence implemented', 'status': 'Done'},
            {'position': '2', 'description': 'Context snapshot saved', 'status': 'Done'},
            {'position': '3', 'description': 'SHA256 hash calculated', 'status': 'Done'},
        ],
        'notes': 'Report stored for audit trail and reproducibility.',
    }
    
    metadata = {
        'demo': True,
        'version': '1.0',
        'created_via': 'demo_script'
    }
    
    report = ReportService.generate_and_store(
        report_key='change.v1',
        object_type='change',
        object_id='CHG-DEMO-003',
        context=context,
        metadata=metadata,
        created_by=user
    )
    
    print(f"Report stored with ID: {report.id}")
    print(f"Report key: {report.report_key}")
    print(f"Object type: {report.object_type}")
    print(f"Object ID: {report.object_id}")
    print(f"Created by: {report.created_by.username}")
    print(f"Created at: {report.created_at}")
    print(f"SHA256 hash: {report.sha256}")
    print(f"PDF file path: {report.pdf_file.name}")
    print(f"Context snapshot saved: {len(report.context_json)} keys")
    print(f"Metadata: {report.metadata}")
    print()


def demo_query_reports():
    """Demonstrate querying stored reports"""
    print("=" * 70)
    print("5. QUERYING STORED REPORTS")
    print("=" * 70)
    
    # Query all change reports
    change_reports = ReportDocument.objects.filter(report_key='change.v1')
    print(f"Total change reports: {change_reports.count()}")
    
    # Query by object
    specific_report = ReportDocument.objects.filter(
        object_type='change',
        object_id='CHG-DEMO-003'
    ).first()
    
    if specific_report:
        print(f"\nFound report for CHG-DEMO-003:")
        print(f"  - Created: {specific_report.created_at}")
        print(f"  - Created by: {specific_report.created_by.username if specific_report.created_by else 'N/A'}")
        print(f"  - Context keys: {list(specific_report.context_json.keys())}")
        print(f"  - SHA256: {specific_report.sha256}")
    
    # List recent reports
    recent_reports = ReportDocument.objects.all()[:5]
    print(f"\nRecent reports (up to 5):")
    for report in recent_reports:
        print(f"  - {report}")
    
    print()


def demo_reproducibility():
    """Demonstrate reproducible report generation"""
    print("=" * 70)
    print("6. DEMONSTRATING REPRODUCIBILITY")
    print("=" * 70)
    
    context = {
        'title': 'Reproducibility Test',
        'change_id': 'CHG-REPRO-001',
        'date': '2024-01-31',
        'description': 'Same context should produce consistent PDFs.',
        'items': [
            {'position': '1', 'description': 'Test reproducibility', 'status': 'Done'},
        ],
    }
    
    # Generate twice
    pdf1 = ReportService.render('change.v1', context)
    pdf2 = ReportService.render('change.v1', context)
    
    import hashlib
    hash1 = hashlib.sha256(pdf1).hexdigest()
    hash2 = hashlib.sha256(pdf2).hexdigest()
    
    print(f"First generation:  {len(pdf1)} bytes, SHA256: {hash1}")
    print(f"Second generation: {len(pdf2)} bytes, SHA256: {hash2}")
    print(f"PDFs identical: {hash1 == hash2}")
    
    if hash1 != hash2:
        print("\nNote: PDFs may differ if they include dynamic timestamps.")
        print("For true reproducibility, avoid including current datetime in reports.")
    
    print()


def main():
    """Run all demonstrations"""
    print("\n" + "=" * 70)
    print("CORE REPORT SERVICE DEMONSTRATION")
    print("=" * 70 + "\n")
    
    demo_list_templates()
    demo_simple_report()
    demo_multipage_report()
    demo_store_report()
    demo_query_reports()
    demo_reproducibility()
    
    print("=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("\nGenerated PDFs can be found in /tmp/:")
    print("  - /tmp/demo_simple_report.pdf")
    print("  - /tmp/demo_multipage_report.pdf")
    print()


if __name__ == '__main__':
    main()
