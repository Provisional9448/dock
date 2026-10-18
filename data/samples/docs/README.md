# Dock mock shipment documents

**All data in these files is fictional.** Every company, person, address, phone number, email, tax ID, load/PO/container/reference number, plate, permit, amount and date was invented for demo use. Phone numbers use the reserved 555-01xx range, and email addresses use `example.com`. Border crossings named "Arena Sur" and "Puerto Arena" do not exist. Any resemblance to real shipments or parties is coincidental.

The structure, sections and field labels follow generic freight-industry document layouts, informed by real logistics workflows. No real document was copied, renamed or partially redacted.

## Demo cast
- Carrier: Red Kettle Freight. Driver: Luis Ortega. Truck: 1841. Trailer/box: RKF-53R-2207 / ABCU1234567
- Shipper: Northwind Orchards, Fresno CA (the cross-border variant uses a fictional "Valle Claro Packing Annex")
- Consignee: Harbor & Rye Grocery DC, Elizabeth NJ
- Broker (supporting role): Orchard Line Logistics
- Load LL-88421, PO-44190, detention $75/hr after 2 hours free

## Files

### Domestic lane (Fresno, CA to Elizabeth, NJ)
| File | What it is |
|---|---|
| `rate-confirmation.md` | Carrier rate confirmation: stops, linehaul/fuel, accessorial schedule (detention $75/hr), terms and acceptance |
| `delivery-order.md` | Delivery order / pickup instruction: versioned dispatch sheet with pickup/delivery windows, equipment and handling rules |
| `transport-layout-sheet.md` | Transport layout / instruction sheet: the planned inputs (parties, goods, units, equipment) used to prepare the BOL or Carta Porte |
| `bill-of-lading.md` | Straight bill of lading (VICS-style): shipper/consignee/bill-to, order and carrier info tables, signature blocks |
| `packing-list.md` | Packing list: per-pallet SKU, lot, case count, weights and dimensions |
| `proof-of-delivery.md` | POD / delivery receipt: gate and door times, received vs. ordered, OS&D notes, receiver and driver signatures |
| `carrier-invoice.md` | Carrier (supplier) freight invoice: linehaul and fuel, with the supporting-documents checklist |
| `accessorial-detention-invoice.md` | Accessorial invoice for receiver detention, showing the free-time math from POD times. Also lists the other accessorial codes |
| `customer-invoice.md` | Customer invoice / billing packet: all-in charges, detention line and packet checklist |
| `credit-memo.md` | Credit memo / corrected invoice linked to its original line, with the documentary-net balance |

### Cross-border variant (fictional crossing)
| File | What it is |
|---|---|
| `carta-porte-cross-border.md` | Human-readable CFDI with Carta Porte complement: issuer, locations, goods, vehicle, insurance and operator. In real use it is paired with an XML file |
| `doda-crossing-form.md` | DODA crossing dispatch form, linking the truck to its pedimento/COVE, plus clearance status |
| `crossing-manifest.md` | Truck e-manifest summary: trip, conveyance, equipment/seals, crew and shipment control number |
| `entry-summary.md` | US entry summary (7501-style layout): header boxes, HTS line items, totals and broker declaration |

## Notes for demo use
- Times on the POD and detention invoice agree with each other: 3.5 billable hours × $75 = $262.50.
- The cross-border files are a separate scenario. They reuse the load and PO numbers, but they are not meant to reconcile with the domestic BOL.
- Tariff and commodity classification codes are illustrative only and marked "(demo)" where they could be confused with real filings.
