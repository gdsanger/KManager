# Vertrag (Contract) - Mietobjekt Assignment Enhancement

## Overview

This document describes the enhanced functionality for assigning rental objects (Mietobjekte) to contracts (Verträge) in the KManager application.

## Previous Behavior

Previously, rental objects were assigned to contracts using a simple multi-select checkbox interface. Each contract could have multiple rental objects, but there was no ability to:
- Set individual prices per object
- Specify quantities
- Track access/departure dates
- Manage status per object

## New Behavior

The rental object assignment has been enhanced with a table-based interface that allows detailed management of each rental object within a contract.

### New Fields in VertragsObjekt

Each rental object assignment now includes:

1. **Preis (Price)**: Individual price for this rental object in the contract
   - Type: Decimal (10,2)
   - Auto-filled from MietObjekt.mietpreis
   - Required field

2. **Anzahl (Quantity)**: Number of units rented
   - Type: Integer
   - Default: 1
   - Must be at least 1

3. **Zugang (Access Date)**: Date when the object was accessed/taken over
   - Type: Date
   - Optional field
   - Useful for tracking move-in dates per object

4. **Abgang (Departure Date)**: Date when the object was returned
   - Type: Date
   - Optional field
   - Must be after Zugang if both are set
   - Useful for tracking move-out dates per object

5. **Status**: Current status of this rental object in the contract
   - Type: Choice field
   - Options: "Aktiv" (Active), "Beendet" (Ended)
   - Default: "Aktiv"

### Calculated Fields

- **Gesamtpreis (Total Price)**: Calculated as `Anzahl × Preis` for each rental object
- **Contract Total**: The contract's `miete` field is now automatically calculated as the sum of all VertragsObjekt items: `Σ(Anzahl × Preis)`

## User Interface

### Contract Form

When creating or editing a contract, the rental objects are managed in a table with the following columns:

| Mietobjekt | Preis (€) | Anzahl | Zugang | Abgang | Status | Löschen |
|------------|-----------|---------|---------|---------|---------|----------|
| [Select]   | 500.00    | 1       | [Date]  | [Date]  | Aktiv   | [ ]      |

Features:
- **Add Row**: Click "Weiteres Mietobjekt hinzufügen" to add more rental objects
- **Auto-calculation**: The total rent is calculated automatically and displayed below the table
- **Auto-fill**: When selecting a rental object, its price is automatically filled from the object's base price
- **Delete**: Check the delete checkbox to remove a rental object from the contract

### Contract Detail View

The contract detail page displays an enhanced table showing all rental objects with their details:

- Rental object name and type
- Individual price and quantity
- Calculated total price (Anzahl × Preis)
- Access and departure dates
- Status badge (Aktiv/Beendet)
- Footer row showing the total contract rent

## Technical Details

### Database Migration

Migration `0012_add_vertragsobjekt_fields.py` adds the new fields to the `VertragsObjekt` model:
- Existing records are automatically populated with `preis` from the related MietObjekt
- Default values are set for `anzahl` (1) and `status` (AKTIV)

### Form Handling

- Uses Django's `inlineformset_factory` to create `VertragsObjektFormSet`
- Minimum 1 rental object required per contract
- JavaScript handles dynamic row addition and total calculation
- Form validation ensures data integrity

### Backwards Compatibility

The changes maintain backwards compatibility:
- The legacy `Vertrag.mietobjekt` field still exists for historical data
- Existing methods like `get_mietobjekte()` work with both old and new relationships
- The `update_mietobjekte_availability()` method handles both relationship types

## Usage Examples

### Creating a Contract with Multiple Objects

1. Navigate to "Verträge" > "Neuer Vertrag"
2. Fill in customer, dates, and other contract details
3. In the "Mietobjekte" table:
   - Row 1: Select "Container A", quantity 2, price 500€ → Total: 1000€
   - Row 2: Select "Lager B", quantity 1, price 800€ → Total: 800€
4. The contract total is automatically calculated: 1800€
5. Save the contract

### Tracking Move-in/Move-out Per Object

For contracts with multiple objects where objects are accessed at different times:
1. Edit the contract
2. For each rental object, set:
   - Zugang: When the customer took possession
   - Abgang: When the customer returned it
   - Status: Mark as "Beendet" when returned

This allows tracking partial contract completion where some objects are still active while others have been returned.

## Benefits

1. **Flexible Pricing**: Different prices can be set per object within the same contract
2. **Quantity Management**: Support for renting multiple units of the same object
3. **Timeline Tracking**: Individual dates for each object's lifecycle
4. **Status Management**: Track which objects are still active vs. ended
5. **Automatic Calculations**: Total rent calculated automatically from all objects
6. **Better Reporting**: More detailed data for invoicing and analytics
