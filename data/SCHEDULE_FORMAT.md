# Pantry schedule format

Each pantry's messy `hours_text` (from `pantries.csv`) becomes one structured
`schedule` object. `backend/hours.py` reads this format.

## The shape

```json
{
  "type": "scheduled",
  "rules": [
    {
      "days": ["tue", "thu"],
      "weeks": [1, 3],
      "months": [1, 2, 3],
      "windows": [{ "start": "09:00", "end": "11:30" }],
      "appointment": false
    }
  ],
  "appointment_available": false
}
```

### Top level

| Field | Meaning |
|---|---|
| `type` | `"scheduled"` (has rules), `"appointment_only"` (no set hours, must call), `"always_open"` (24/7), or `"unknown"` ("Call for hours") |
| `rules` | List of rules. Only used when `type` is `"scheduled"`. |
| `appointment_available` | Optional. `true` when the text says "...or appointment": outside the listed hours, you can still call to book. |

### Each rule

| Field | Required? | Meaning |
|---|---|---|
| `days` | yes | Lowercase 3-letter days: `mon tue wed thu fri sat sun` |
| `windows` | yes | One or more time windows, 24-hour `"HH:MM"`. `start` is inclusive, `end` is exclusive (at exactly `end` the pantry counts as closed). |
| `weeks` | no | Which occurrence of the day in the month: `1`–`5` and/or `"last"`. Leave out for "every week". |
| `months` | no | Month numbers `1`–`12`. Leave out for "every month". |
| `appointment` | no | `true` if these hours need an appointment. Default `false`. |

A pantry is open at a moment if **any** rule matches the date and **any** of
its windows contains the time.

## Real examples from pantries.csv

**"Mon 9am-12pm; Wed 9am-2pm; Thu 4:30-6:30pm"**: one rule per distinct time
```json
{"type": "scheduled", "rules": [
  {"days": ["mon"], "windows": [{"start": "09:00", "end": "12:00"}]},
  {"days": ["wed"], "windows": [{"start": "09:00", "end": "14:00"}]},
  {"days": ["thu"], "windows": [{"start": "16:30", "end": "18:30"}]}
]}
```

**"Tue & Thu 9-11:30am, 1:30-3:30pm"**: multiple windows (lunch break)
```json
{"type": "scheduled", "rules": [
  {"days": ["tue", "thu"], "windows": [
    {"start": "09:00", "end": "11:30"},
    {"start": "13:30", "end": "15:30"}
  ]}
]}
```

**"2nd & 4th Sat 9-11am"**: nth weekday of the month
```json
{"type": "scheduled", "rules": [
  {"days": ["sat"], "weeks": [2, 4], "windows": [{"start": "09:00", "end": "11:00"}]}
]}
```

**"Wed-Sat 8:30-11:30am; closed 5th Sat"**: "closed on the 5th" = "only weeks 1–4"
```json
{"type": "scheduled", "rules": [
  {"days": ["wed", "thu", "fri"], "windows": [{"start": "08:30", "end": "11:30"}]},
  {"days": ["sat"], "weeks": [1, 2, 3, 4], "windows": [{"start": "08:30", "end": "11:30"}]}
]}
```

**"Jan-Oct 4th Sat, Nov-Dec 2nd Sat, 8am-12pm"**: month ranges
```json
{"type": "scheduled", "rules": [
  {"days": ["sat"], "weeks": [4], "months": [1,2,3,4,5,6,7,8,9,10], "windows": [{"start": "08:00", "end": "12:00"}]},
  {"days": ["sat"], "weeks": [2], "months": [11, 12], "windows": [{"start": "08:00", "end": "12:00"}]}
]}
```

**"Tue 2-6pm; Thu 10am-1pm; Sat 9-11am (appointment)"**: one day needs an appointment
```json
{"type": "scheduled", "rules": [
  {"days": ["tue"], "windows": [{"start": "14:00", "end": "18:00"}]},
  {"days": ["thu"], "windows": [{"start": "10:00", "end": "13:00"}]},
  {"days": ["sat"], "windows": [{"start": "09:00", "end": "11:00"}], "appointment": true}
]}
```

**"Thu 11am-2pm or appointment"**
```json
{"type": "scheduled", "appointment_available": true, "rules": [
  {"days": ["thu"], "windows": [{"start": "11:00", "end": "14:00"}]}
]}
```

**"Mon-Fri by appointment"**: `{"type": "appointment_only"}`

**"24/7 take what you need"**: `{"type": "always_open"}`

**"Call for hours"**: `{"type": "unknown"}`

## Status values (from `status()` in hours.py)

| Status | Meaning |
|---|---|
| `open` | Walk-in hours right now |
| `later_today` | Not open now, but has hours later today |
| `appointment` | Needs an appointment (right now, or can be booked) |
| `closed` | No more hours today |
| `unknown` | We don't know the hours: tell the user to call |
