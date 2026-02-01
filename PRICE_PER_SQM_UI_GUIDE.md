# UI Visual Guide - Price per Square Meter Feature

## Form View - Create/Edit MietObjekt

### Full Form Structure
```
┌──────────────────────────────────────────────────────────────────┐
│ Neues Mietobjekt / Mietobjekt bearbeiten                    [×]  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Grunddaten                                                       │
├──────────────────────────────────────────────────────────────────┤
│ Name *           [_____________________________________]          │
│ Typ *            [Raum                              ▼]          │
│ Standort *       [Berlin                            ▼]          │
│ Beschreibung *   [_____________________________________]          │
│                  [_____________________________________]          │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Abmessungen                                                      │
├──────────────────────────────────────────────────────────────────┤
│ Fläche (m²)  [___________]  Höhe (m)   [___________]            │
│ Breite (m)   [___________]  Tiefe (m)  [___________]            │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Preise & Kosten                                         ⭐ NEW!  │
├──────────────────────────────────────────────────────────────────┤
│ Mietpreis (€) *        €/m²                  Nebenkosten (€)    │
│ [___________]          [___________]         [___________]       │
│                        ↑ NEW FIELD!                              │
│                        Help: Optional: Mietpreis pro            │
│                        Quadratmeter. Kann zur Berechnung des    │
│                        Gesamtmietpreises verwendet werden.      │
│                                                                  │
│ Kaution (€)                                                      │
│ [___________]                                                    │
│ Help: Standard: 3x Mietpreis (wird automatisch vorausgefüllt)  │
└──────────────────────────────────────────────────────────────────┘

[More sections...]

                              [Speichern]  [Abbrechen]
```

## Confirmation Modal (When both €/m² and Fläche are set)

```
┌──────────────────────────────────────────────┐
│ Mietpreis berechnen                     [×]  │
├──────────────────────────────────────────────┤
│                                              │
│ Gesamtmiete aus €/m² und Fläche berechnen   │
│ und übernehmen?                              │
│                                              │
│ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
│ ┃ Berechnung:                           ┃ │
│ ┃ 20.00 €/m² × 50.00 m² = 1,000.00 €   ┃ │
│ ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛ │
│                                              │
├──────────────────────────────────────────────┤
│                     [Nein]  [Ja, übernehmen] │
└──────────────────────────────────────────────┘
```

**User Journey:**
1. User enters price_per_sqm: 20.00
2. User enters fläche: 50.00
3. User clicks "Speichern"
4. ⚡ Modal appears with calculation preview
5. User chooses:
   - "Ja, übernehmen": Mietpreis field is set to 1000.00, form submits
   - "Nein": Mietpreis remains unchanged, form submits

## Detail View - MietObjekt Detail

### Preise & Kosten Section

**Scenario 1: With price_per_sqm set**
```
┌──────────────────────────────────────────────────────────────────┐
│ Preise & Kosten                                                  │
├──────────────────────────────────────────────────────────────────┤
│ Mietpreis:                          1,000.00 €                   │
│                                                                  │
│ €/m² (eingegeben):                  20.00 €/m²  ⭐ NEW!         │
│ ↑ User-entered value                                             │
│                                                                  │
│ Berechneter Preis pro m²:           20.00 €/m²                   │
│ ↑ Auto-calculated: mietpreis ÷ fläche                           │
│                                                                  │
│ Nebenkosten:                        200.00 €                     │
│ Kaution:                            3,000.00 €                   │
└──────────────────────────────────────────────────────────────────┘
```

**Scenario 2: Without price_per_sqm (backward compatible)**
```
┌──────────────────────────────────────────────────────────────────┐
│ Preise & Kosten                                                  │
├──────────────────────────────────────────────────────────────────┤
│ Mietpreis:                          1,000.00 €                   │
│                                                                  │
│ (€/m² row not shown - field is empty)                           │
│                                                                  │
│ Berechneter Preis pro m²:           20.00 €/m²                   │
│                                                                  │
│ Nebenkosten:                        200.00 €                     │
│ Kaution:                            3,000.00 €                   │
└──────────────────────────────────────────────────────────────────┘
```

## Field Validation

### Valid Inputs ✅
- Empty (field is optional)
- 0.00
- 1.50
- 20.00
- 999999.99 (up to 10 digits total, 2 decimal places)

### Invalid Inputs ❌
```
Input: -10.00
Error: "Sicherstellen, dass dieser Wert größer oder gleich 0.00 ist."

Input: abc
Error: "Geben Sie eine Zahl ein."
```

## Browser Compatibility
- ✅ Modern browsers (Chrome, Firefox, Safari, Edge)
- ✅ Bootstrap 5 Modal
- ✅ HTML5 form validation (min="0", step="0.01")
- ✅ JavaScript ES6 features

## Accessibility
- ✅ Proper form labels (for screen readers)
- ✅ Error messages clearly associated with fields
- ✅ Modal keyboard navigation (Esc to close, Tab navigation)
- ✅ Focus management (modal steals focus, returns on close)

## Responsive Design
The form is responsive using Bootstrap 5 grid:

**Desktop (≥992px):**
- Form: 8 columns (66%)
- Sidebar: 4 columns (33%)
- Price fields: 3 fields per row (4 columns each)

**Tablet (768-991px):**
- Form: Full width
- Sidebar: Below form
- Price fields: 2 fields per row (6 columns each)

**Mobile (<768px):**
- Form: Full width
- Sidebar: Below form
- Price fields: 1 field per row (12 columns)

## Color Coding & Visual Hierarchy

```
┌──────────────────────────────────────────────┐
│ Mietpreis:        1,000.00 €        ← Bold  │
│ €/m² (eingegeben): 20.00 €/m²       ← Bold  │
│ Berechneter...     20.00 €/m²       ← Normal│
└──────────────────────────────────────────────┘
```

- User-entered values: **Bold** to emphasize
- Calculated values: Normal weight
- Field labels: Text-muted color
- Required fields: Asterisk (*) suffix

## Example Use Cases

### Use Case 1: Commercial Property Manager
"I manage 50 office spaces. I set the price at €15/m². For a 100m² office, the system calculates €1,500 total rent automatically."

### Use Case 2: Residential Landlord
"I prefer to set total rent directly. I leave €/m² empty and enter €800 for my apartment. The system shows me the calculated €/m² for comparison."

### Use Case 3: Price Adjustment
"I need to increase rent from €10/m² to €12/m². I edit the €/m² field, and the system offers to recalculate the total rent for me."

## Data Flow Diagram

```
User Action                Modal/Confirmation           Database
──────────                ──────────────────           ────────

Enter €/m²: 20                                         
Enter Fläche: 50                                       
                                                       
Click "Speichern"  ───>   ┌─────────────────┐        
                          │ Calculate:       │        
                          │ 20 × 50 = 1000  │        
                          │                 │        
                          │ [Ja] [Nein]     │        
                          └─────────────────┘        
                                   │                 
                          ┌────────┴────────┐        
                          │                 │        
                     [Ja] │            [Nein]│        
                          │                 │        
                          v                 v        
                   Set mietpreis    Keep original    
                   to 1000          mietpreis        
                          │                 │        
                          └────────┬────────┘        
                                   │                 
                                   v                 
                          Save to Database ────>  ✅ Saved
                          - price_per_sqm: 20          
                          - fläche: 50                 
                          - mietpreis: 1000            
```

## Testing Scenarios Covered

1. ✅ Create MietObjekt with price_per_sqm
2. ✅ Create MietObjekt without price_per_sqm
3. ✅ Edit to add price_per_sqm
4. ✅ Edit to remove price_per_sqm
5. ✅ Validation: Negative values rejected
6. ✅ Validation: Zero accepted
7. ✅ Validation: Null/empty accepted
8. ✅ Display in detail view when set
9. ✅ Hidden in detail view when not set
10. ✅ Form includes field with proper styling
11. ✅ Calculation modal shows correct preview
12. ✅ Confirmation applies calculation
13. ✅ Decline keeps original value
14. ✅ No modal when fläche is missing
