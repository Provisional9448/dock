# 05 — Thread: dispatcher ↔ driver check-ins and arrival time

> FICTIONAL SAMPLE. All names, codes and links are invented.

**Channel:** carrier WhatsApp, Red Kettle Freight dispatch ↔ driver
**People:** Dana Whitcomb (dispatch lead), Luis Ortega (driver, truck 1841)

```
[Oct 12, 11:40] Dana: Luis, LL-88421 pickup Northwind Fresno, window 12–15, PU# NWO-PU-40871. Send trailer + seal when loaded
[Oct 12, 12:05] Luis: en Northwind, en puerta, esperando rampa
[Oct 12, 12:50] Luis: rampa 3, ya cargando
[Oct 12, 14:20] Luis: cargado. trailer RKF-53R-2207 sello SL-660291, 22 pallets 34F
[Oct 12, 14:22] Dana: gracias. send BOL photo pls
[Oct 12, 14:25] Luis: [photo: BOL RK-BOL-50318]
[Oct 14, 18:10] Dana: ETA to Elizabeth?
[Oct 14, 18:30] Luis: depende del trafico, jueves temprano. 5:30-6 am
[Oct 15, 21:00] Dana: appt 06:00 tmrw, HR-APT-30957. call receiving 2h before
[Oct 16, 05:48] Luis: llegué a Harbor & Rye, Gate B
```

## Patterns shown
- Separate check-ins for at the gate, door assigned, loading and loaded.
- Truck and equipment identifiers sent along with the document photo.
- ETA given as a range that depends on traffic.
- English and Spanish mixed in the same thread.
