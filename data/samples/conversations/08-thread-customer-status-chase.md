# 08 — Thread: customer chasing status

> FICTIONAL SAMPLE. All names, codes and links are invented.

**Channel:** email, customer transportation desk → broker ops
**People:** Tomás Reyes (Harbor & Rye inbound transportation, invented), Sam Okafor (Orchard Line ops)

```
[Oct 14, 10:02] Tomás: Hi Sam, can you confirm status on PO-44190? We have it for Fri 06:00
[Oct 14, 10:30] Sam: Hi Tomás, LL-88421 is in transit, last ping near Omaha NE at 09:58 CT. Driver ETA Fri 05:30–06:00 ET, on track for the 06:00 appt
[Oct 15, 15:20] Tomás: Any update? Our DC wants to know if it's still on for tomorrow
[Oct 15, 15:22] Sam: checking with carrier now
[Oct 15, 16:05] Sam: Confirmed on track. Truck 1841 near Harrisburg PA at 15:48 ET, reefer reading 34F
[Oct 16, 07:00] Tomás: The truck is here but I'm hearing it hasn't been unloaded. Is there a problem?
[Oct 16, 07:10] Sam: It checked in at 06:05, door 17. Your receiving team says they're short on labor. Heads up: carrier detention starts at 08:00 at $75/hr
[Oct 16, 12:00] Sam: Delivered, released 11:30. 4 cases noted damaged on POD; will share POD once we have the clean copy
```

## Patterns shown
- The customer asks by PO, the carrier tracks by load or truck, and the broker matches them up.
- When an update is slow, the customer asks again the same day.
- Each status update includes the source time.
- A possible extra charge is flagged early, before the bill comes.
