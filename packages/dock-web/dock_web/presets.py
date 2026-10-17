"""Demo clock presets. The labels are the words docs/DEMO.md uses."""

PRESETS = (
    {
        "id": "arrived",
        "label": "Just arrived",
        "as_of": "2026-10-17T18:10:00Z",
    },
    {
        "id": "warning",
        "label": "30 min of free time left",
        "as_of": "2026-10-17T19:36:00Z",
    },
    {
        "id": "accruing",
        "label": "15 min past free time",
        "as_of": "2026-10-17T20:21:00Z",
    },
    {
        "id": "unloaded",
        "label": "Unload started",
        "as_of": "2026-10-17T20:48:00Z",
    },
)

DRIVER_PROMPTS = (
    "I'm at Harbor and Rye door 4. They are not ready to unload.",
    "Still waiting. Door is occupied.",
    "They started unloading.",
)
