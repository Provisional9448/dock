# CFDI WITH CARTA PORTE COMPLEMENT (CCP) — HUMAN-READABLE REPRESENTATION

> FICTIONAL DEMO DOCUMENT — CROSS-BORDER VARIANT. Every company, tax ID, UUID, plate, permit, place and amount is invented. "Arena Sur" / "Puerto Arena" is a made-up border crossing. In real workflows this PDF travels with a matching XML file; the two must carry the same issued-document identifiers.

## Comprobante (header)
| Field | Value |
|---|---|
| Tipo de comprobante | T — Traslado |
| Serie / Folio | CP-31408 |
| Fecha de emisión | 2026-10-09T08:15:00 |
| Lugar de expedición (CP) | 99001 (demo) |
| Versión CFDI / Complemento | 4.0 / Carta Porte 3.1 |
| Folio fiscal (UUID) | 00000000-DEMO-4C0F-0000-000000088421 |
| Moneda | XXX |
| Total | 0.00 |

## Emisor (issuer — Mexican transport partner)
| Field | Value |
|---|---|
| Nombre | Transportes Brasa Roja S.A. de C.V. (demo partner of Red Kettle Freight) |
| RFC | TBR000000XX0 (demo) |
| Régimen fiscal | 601 |

## Receptor
| Field | Value |
|---|---|
| Nombre | Transportes Brasa Roja S.A. de C.V. (self, traslado) |
| RFC | TBR000000XX0 (demo) |
| Uso CFDI | S01 |

## Complemento Carta Porte
| Field | Value |
|---|---|
| ID CCP | CCC00000-DEMO-0000-0000-000000031408 |
| Transporte internacional | Sí |
| Entrada / Salida de mercancía | Salida |
| País origen / destino | USA |
| Vía entrada / salida | 01 — Autotransporte |
| Total distancia recorrida | 412 km |
| Referencias | Load LL-88421 · PO-44190 |

### Ubicaciones
| Tipo | ID | Remitente / Destinatario | RFC / Tax ID | Fecha-hora | Domicilio | Distancia |
|---|---|---|---|---|---|---:|
| Origen | OR000001 | Northwind Orchards — Valle Claro Packing Annex (fictional) | NWO000000XX1 (demo) | Salida 2026-10-10T05:30:00 | Carretera Huertas km 14, Valle Claro (fictional), CP 99002 (demo) | — |
| Destino | DE000001 | Harbor & Rye Grocery DC | ResidenciaFiscal USA · NumRegIdTrib 00-0000002 (demo) | Llegada 2026-10-10T11:45:00 (border) | Cruce Arena Sur – Puerto Arena (fictional crossing) | 412 km |

### Mercancías
| Field | Value |
|---|---|
| Peso bruto total | 17,963 KGM |
| Número total de mercancías | 2 |

| # | Bienes transp. (clave) | Descripción | Cantidad | Clave unidad | Peso (kg) | Mat. peligroso | Fracción arancelaria | Pedimento ref. |
|---:|---|---|---:|---|---:|---|---|---|
| 1 | 50301500 | Manzanas frescas, cartones 18 kg | 576 | XBX | 9,798 | No | 0808.10.01 (demo) | 26 00 0000 6000123 (demo) |
| 2 | 50302500 | Peras frescas, cartones 18 kg | 480 | XBX | 8,165 | No | 0808.30.01 (demo) | 26 00 0000 6000123 (demo) |

### Autotransporte
| Field | Value |
|---|---|
| Permiso SCT / No. permiso | TPAF01 / 0000DEMO1841 |
| Configuración vehicular | T3S2 |
| Peso bruto vehicular | 36.0 t |
| Placa / Año modelo | 00-RK-1A (demo) / 2022 |
| Aseguradora resp. civil / Póliza | Seguros Ficticios S.A. (demo) / POL-000-88421 |
| Remolque (subtipo / placa) | CTR004 Remolque refrigerado / 00-RK-2B (demo) · Box ABCU1234567 |

### Figura de transporte
| Tipo | Nombre | RFC (demo) | No. licencia (demo) |
|---|---|---|---|
| 01 — Operador | Luis Ortega | OEXL000000XX2 | LF-0000001841 |

Sello digital del CFDI / Sello del SAT / Cadena original: `DEMO-NOT-A-REAL-SEAL` · QR: (placeholder)
