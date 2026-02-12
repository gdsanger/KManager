"""
Context builders for Uebergabeprotokoll PDF rendering.

Builds stable, DTO-like contexts for handover protocol templates.
"""

import os
from typing import Any, Optional
from django.conf import settings
from core.printing.interfaces import IContextBuilder


class UebergabeprotokollContextBuilder(IContextBuilder):
    """
    Context builder for Uebergabeprotokoll (Handover Protocol) PDFs.
    
    Builds a stable, DTO-like render context suitable for handover protocol templates.
    No model objects are passed directly to templates.
    """
    
    def build_context(self, obj: Any, *, company: Any = None) -> dict:
        """
        Build template context from Uebergabeprotokoll.
        
        Args:
            obj: Uebergabeprotokoll instance
            company: Optional Mandant instance (defaults to obj's mandant via vertrag/mietobjekt)
            
        Returns:
            Template context dictionary with company, protokoll, vertrag, mietobjekt sections
        """
        from vermietung.models import Uebergabeprotokoll
        
        if not isinstance(obj, Uebergabeprotokoll):
            raise ValueError(f"Expected Uebergabeprotokoll, got {type(obj)}")
        
        protokoll = obj
        company = company or self._get_mandant(protokoll)
        
        # Build context sections
        context = {
            'company': self._build_company_context(company) if company else None,
            'protokoll': self._build_protokoll_context(protokoll),
            'vertrag': self._build_vertrag_context(protokoll.vertrag),
            'mietobjekt': self._build_mietobjekt_context(protokoll.mietobjekt),
            'mieter': self._build_mieter_context(protokoll.vertrag.mieter) if protokoll.vertrag and protokoll.vertrag.mieter else None,
        }
        
        return context
    
    def get_template_name(self, obj: Any) -> str:
        """
        Get template name for handover protocol.
        
        Args:
            obj: Uebergabeprotokoll instance
            
        Returns:
            Template name/path
        """
        return 'printing/uebergabeprotokolle/protokoll.html'
    
    def _get_mandant(self, protokoll):
        """
        Get Mandant (company) for a Uebergabeprotokoll.
        
        Priority: vertrag.mandant → mietobjekt.mandant
        """
        if protokoll.vertrag and hasattr(protokoll.vertrag, 'mandant') and protokoll.vertrag.mandant:
            return protokoll.vertrag.mandant
        if protokoll.mietobjekt and hasattr(protokoll.mietobjekt, 'mandant') and protokoll.mietobjekt.mandant:
            return protokoll.mietobjekt.mandant
        return None
    
    def _build_company_context(self, company) -> dict:
        """Build company/letterhead context."""
        address_lines = []
        if company.adresse:
            address_lines.append(company.adresse)
        if company.plz and company.ort:
            address_lines.append(f"{company.plz} {company.ort}")
        if company.land:
            address_lines.append(company.land)
        
        # Bank info (optional)
        bank_info = []
        if company.kreditinstitut:
            bank_info.append(f"Bank: {company.kreditinstitut}")
        if company.iban:
            bank_info.append(f"IBAN: {company.iban}")
        if company.bic:
            bank_info.append(f"BIC: {company.bic}")
        if company.kontoinhaber and company.kontoinhaber != company.name:
            bank_info.append(f"Kontoinhaber: {company.kontoinhaber}")
        
        # Logo URL - construct absolute file path for WeasyPrint
        logo_url = None
        if company.logo_path:
            # WeasyPrint needs an absolute file path or URL
            logo_file_path = os.path.join(settings.MEDIA_ROOT, company.logo_path)
            if os.path.exists(logo_file_path):
                # Use file:// URL for WeasyPrint
                logo_url = f"file://{logo_file_path}"
        
        return {
            'name': company.name,
            'address_lines': address_lines,
            'logo_url': logo_url,
            'tax_number': company.steuernummer or '',
            'vat_id': company.ust_id_nr or '',
            'managing_director': company.geschaeftsfuehrer or '',
            'commercial_register': company.handelsregister or '',
            'bank_name': company.kreditinstitut or '',
            'iban': company.iban or '',
            'bic': company.bic or '',
            'account_holder': company.kontoinhaber or '',
            'bank_info': bank_info if bank_info else None,
            'phone': company.telefon or '',
            'fax': company.fax or '',
            'email': company.email or '',
            'internet': company.internet or '',
        }
    
    def _build_protokoll_context(self, protokoll) -> dict:
        """Build handover protocol data context."""
        return {
            'id': protokoll.pk,
            'typ': protokoll.typ,
            'typ_display': protokoll.get_typ_display(),
            'uebergabetag': protokoll.uebergabetag,
            'zaehlerstand_strom': protokoll.zaehlerstand_strom,
            'zaehlerstand_gas': protokoll.zaehlerstand_gas,
            'zaehlerstand_wasser': protokoll.zaehlerstand_wasser,
            'anzahl_schluessel': protokoll.anzahl_schluessel,
            'bemerkungen': protokoll.bemerkungen or '',
            'maengel': protokoll.maengel or '',
            'person_vermieter': protokoll.person_vermieter or '',
            'person_mieter': protokoll.person_mieter or '',
        }
    
    def _build_vertrag_context(self, vertrag) -> dict:
        """Build contract context."""
        if not vertrag:
            return None
        
        return {
            'vertragsnummer': vertrag.vertragsnummer,
            'start': vertrag.start,
            'ende': vertrag.ende,
            'miete_kalt': vertrag.miete if hasattr(vertrag, 'miete') else None,
            'miete_warm': None,  # Legacy field no longer exists
            'kaution': vertrag.kaution if hasattr(vertrag, 'kaution') else None,
        }
    
    def _build_mietobjekt_context(self, mietobjekt) -> dict:
        """Build rental object context."""
        if not mietobjekt:
            return None
        
        # Build address from standort
        address_lines = []
        if mietobjekt.standort:
            if mietobjekt.standort.strasse:
                address_lines.append(mietobjekt.standort.strasse)
            if mietobjekt.standort.plz and mietobjekt.standort.ort:
                address_lines.append(f"{mietobjekt.standort.plz} {mietobjekt.standort.ort}")
        
        return {
            'name': mietobjekt.name,
            'type': mietobjekt.type if hasattr(mietobjekt, 'type') else None,
            'type_display': mietobjekt.get_type_display() if hasattr(mietobjekt, 'get_type_display') else '',
            'qm': mietobjekt.fläche if hasattr(mietobjekt, 'fläche') else None,
            'zimmer': None,  # MietObjekt doesn't have a zimmer field
            'address_lines': address_lines,
        }
    
    def _build_mieter_context(self, mieter) -> dict:
        """Build tenant (Kunde) address block context."""
        if not mieter:
            return None
        
        address_lines = []
        
        # Company name or personal name
        if mieter.firma:
            address_lines.append(mieter.firma)
        if mieter.name:
            if hasattr(mieter, 'anrede') and mieter.anrede:
                address_lines.append(f"{mieter.get_anrede_display()} {mieter.name}")
            else:
                address_lines.append(mieter.name)
        
        # Street address
        if mieter.strasse:
            address_lines.append(mieter.strasse)
        
        # City/ZIP
        if mieter.plz and mieter.ort:
            address_lines.append(f"{mieter.plz} {mieter.ort}")
        
        # Country (if not default)
        if hasattr(mieter, 'land') and mieter.land and mieter.land.upper() not in ['DEUTSCHLAND', 'GERMANY', 'DE']:
            address_lines.append(mieter.land)
        
        return {
            'name': mieter.firma or mieter.name,
            'address_lines': address_lines,
            'email': mieter.email if hasattr(mieter, 'email') else '',
            'telefon': mieter.telefon if hasattr(mieter, 'telefon') else '',
        }
