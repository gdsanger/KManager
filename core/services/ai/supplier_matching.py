"""
Supplier matching service for invoices.

This module provides functionality to match extracted supplier data to existing suppliers
in the database. Uses deterministic matching first, with optional AI-based fallback.
"""
import logging
from typing import Optional, List, Tuple
from difflib import SequenceMatcher

from django.db.models import Q
from django.contrib.auth.models import User

from core.models import Adresse
from core.services.ai.router import AIRouter
from core.services.base import ServiceNotConfigured


logger = logging.getLogger(__name__)


class SupplierMatchingService:
    """Service for matching invoice suppliers to existing Lieferant records."""
    
    # Minimum similarity score for fuzzy matching (0.0 - 1.0)
    SIMILARITY_THRESHOLD = 0.85
    
    # AI matching prompt
    AI_MATCHING_PROMPT = """You are an AI assistant that helps match company names and addresses.
Given a target supplier and a list of existing suppliers, determine if any of them match.

Target supplier:
Name: {target_name}
Address: {target_address}

Existing suppliers:
{existing_suppliers}

Return ONLY a JSON object with these exact fields:
{{
    "match_found": true/false,
    "matched_id": null or the ID of the matched supplier,
    "confidence": 0.0-1.0 (how confident you are in the match),
    "reasoning": "brief explanation of why they match or don't match"
}}

Rules:
- Consider variations in company legal forms (GmbH, AG, etc.)
- Consider abbreviations and full names
- Consider address differences (e.g., different street numbers might still be same company)
- Be conservative - only return match_found: true if you're confident (>0.85)
- Return ONLY the JSON object, no markdown, no explanations outside the JSON
"""
    
    def __init__(self):
        """Initialize the supplier matching service."""
        self.router = AIRouter()
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings using sequence matching.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not str1 or not str2:
            return 0.0
        
        # Normalize strings for comparison
        s1 = str1.lower().strip()
        s2 = str2.lower().strip()
        
        return SequenceMatcher(None, s1, s2).ratio()
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize company name for matching.
        Removes common legal forms and punctuation.
        
        Args:
            name: Company name
            
        Returns:
            Normalized name
        """
        if not name:
            return ""
        
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Remove common legal forms
        legal_forms = [
            'gmbh', 'ag', 'kg', 'ohg', 'gbr', 'ug', 'e.v.', 'ev',
            'limited', 'ltd', 'llc', 'inc', 'corp', 'co.', 'co'
        ]
        for form in legal_forms:
            normalized = normalized.replace(form, '')
        
        # Remove punctuation and extra spaces
        normalized = ''.join(c for c in normalized if c.isalnum() or c.isspace())
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def match_supplier_deterministic(
        self,
        name: str,
        strasse: Optional[str] = None,
        plz: Optional[str] = None,
        ort: Optional[str] = None,
        land: Optional[str] = None
    ) -> Optional[Adresse]:
        """
        Match supplier using deterministic rules.
        
        Matching strategy:
        1. Exact name match (case-insensitive)
        2. Normalized name match (without legal forms)
        3. Fuzzy name match with high similarity threshold
        4. If multiple matches, filter by address data if available
        
        Args:
            name: Supplier name
            strasse: Optional street address
            plz: Optional postal code
            ort: Optional city
            land: Optional country
            
        Returns:
            Matched Adresse (Lieferant) or None if no unique match found
        """
        if not name:
            logger.warning("Cannot match supplier without name")
            return None
        
        logger.info(f"Attempting deterministic match for supplier: {name}")
        
        # Get all suppliers (Lieferant type)
        suppliers = Adresse.objects.filter(adressen_type='LIEFERANT')
        
        # Strategy 1: Exact name match (case-insensitive)
        exact_matches = suppliers.filter(
            Q(name__iexact=name) | Q(firma__iexact=name)
        )
        
        if exact_matches.count() == 1:
            logger.info(f"Found exact match: {exact_matches.first()}")
            return exact_matches.first()
        
        if exact_matches.count() > 1:
            # Multiple exact matches - try to filter by address
            logger.info(f"Found {exact_matches.count()} exact name matches, filtering by address")
            filtered = self._filter_by_address(exact_matches, strasse, plz, ort, land)
            if filtered and filtered.count() == 1:
                logger.info(f"Filtered to single match: {filtered.first()}")
                return filtered.first()
        
        # Strategy 2: Normalized name match
        normalized_target = self._normalize_name(name)
        
        for supplier in suppliers:
            # Check both name and firma fields
            for field in [supplier.name, supplier.firma]:
                if field:
                    normalized_supplier = self._normalize_name(field)
                    if normalized_supplier == normalized_target:
                        logger.info(f"Found normalized match: {supplier}")
                        return supplier
        
        # Strategy 3: Fuzzy matching with high threshold
        candidates: List[Tuple[Adresse, float]] = []
        
        for supplier in suppliers:
            max_similarity = 0.0
            
            # Check similarity with both name and firma
            for field in [supplier.name, supplier.firma]:
                if field:
                    similarity = self._calculate_similarity(name, field)
                    max_similarity = max(max_similarity, similarity)
            
            if max_similarity >= self.SIMILARITY_THRESHOLD:
                candidates.append((supplier, max_similarity))
        
        if len(candidates) == 1:
            logger.info(f"Found fuzzy match: {candidates[0][0]} (similarity: {candidates[0][1]:.2f})")
            return candidates[0][0]
        
        if len(candidates) > 1:
            # Multiple fuzzy matches - try address filtering
            logger.info(f"Found {len(candidates)} fuzzy matches, filtering by address")
            candidate_qs = Adresse.objects.filter(
                id__in=[c[0].id for c in candidates]
            )
            filtered = self._filter_by_address(candidate_qs, strasse, plz, ort, land)
            if filtered and filtered.count() == 1:
                logger.info(f"Filtered to single match: {filtered.first()}")
                return filtered.first()
        
        logger.info("No deterministic match found")
        return None
    
    def _filter_by_address(
        self,
        queryset,
        strasse: Optional[str],
        plz: Optional[str],
        ort: Optional[str],
        land: Optional[str]
    ):
        """
        Filter queryset by address components.
        
        Args:
            queryset: Queryset of Adresse objects
            strasse: Street address
            plz: Postal code
            ort: City
            land: Country
            
        Returns:
            Filtered queryset or None if no filters available
        """
        filters = Q()
        
        if plz:
            filters &= Q(plz__iexact=plz)
        
        if ort:
            filters &= Q(ort__icontains=ort)
        
        if land:
            filters &= Q(land__icontains=land)
        
        if strasse:
            # Fuzzy street matching - extract street name without number
            street_name = ''.join(c for c in strasse if not c.isdigit()).strip()
            if street_name:
                filters &= Q(strasse__icontains=street_name)
        
        if filters:
            return queryset.filter(filters)
        
        return None
    
    def match_supplier_with_ai_fallback(
        self,
        name: str,
        strasse: Optional[str] = None,
        plz: Optional[str] = None,
        ort: Optional[str] = None,
        land: Optional[str] = None,
        user: Optional[User] = None,
        client_ip: Optional[str] = None
    ) -> Optional[Adresse]:
        """
        Match supplier using deterministic matching first, then AI as fallback.
        
        Args:
            name: Supplier name
            strasse: Optional street address
            plz: Optional postal code
            ort: Optional city
            land: Optional country
            user: Optional user making the request
            client_ip: Optional client IP address
            
        Returns:
            Matched Adresse (Lieferant) or None if no match found
        """
        # Try deterministic matching first
        match = self.match_supplier_deterministic(name, strasse, plz, ort, land)
        if match:
            return match
        
        # No deterministic match - try AI fallback if configured
        logger.info("Attempting AI-based supplier matching fallback")
        
        try:
            # Get all suppliers for AI comparison
            suppliers = Adresse.objects.filter(adressen_type='LIEFERANT')[:20]  # Limit to avoid token overflow
            
            if not suppliers:
                logger.info("No suppliers in database for AI matching")
                return None
            
            # Format target address
            target_address = f"{strasse or ''}, {plz or ''} {ort or ''}, {land or ''}".strip(', ')
            
            # Format existing suppliers
            existing_suppliers_text = ""
            for i, supplier in enumerate(suppliers, 1):
                existing_suppliers_text += f"{i}. ID: {supplier.id}, Name: {supplier.full_name()}, "
                existing_suppliers_text += f"Address: {supplier.strasse}, {supplier.plz} {supplier.ort}, {supplier.land}\n"
            
            # Create prompt
            prompt = self.AI_MATCHING_PROMPT.format(
                target_name=name,
                target_address=target_address,
                existing_suppliers=existing_suppliers_text
            )
            
            # Call AI
            response = self.router.generate(
                prompt=prompt,
                user=user,
                client_ip=client_ip,
                agent="core.ai.supplier_matching",
                temperature=0.0
            )
            
            # Parse response
            import json
            response_text = response.text.strip()
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(line for line in lines if not line.startswith('```'))
            
            result = json.loads(response_text)
            
            if result.get('match_found') and result.get('confidence', 0) >= 0.85:
                matched_id = result.get('matched_id')
                if matched_id:
                    try:
                        matched_supplier = Adresse.objects.get(id=matched_id, adressen_type='LIEFERANT')
                        logger.info(f"AI matched supplier: {matched_supplier} (confidence: {result.get('confidence')})")
                        logger.info(f"AI reasoning: {result.get('reasoning')}")
                        return matched_supplier
                    except Adresse.DoesNotExist:
                        logger.warning(f"AI suggested non-existent supplier ID: {matched_id}")
            
            logger.info("AI did not find a confident match")
            return None
            
        except ServiceNotConfigured:
            logger.warning("AI service not configured - skipping AI fallback")
            return None
        
        except Exception as e:
            logger.error(f"AI supplier matching failed: {e}", exc_info=True)
            return None
