const FALLBACK_TIMEZONES = [
  "America/Los_Angeles",
  "America/Denver",
  "America/Chicago",
  "America/New_York",
  "UTC",
  "Europe/London",
  "Europe/Paris",
  "Asia/Kolkata",
  "Asia/Tokyo",
  "Australia/Sydney",
]

export function getSupportedTimezones() {
  const supportedValuesOf = (
    Intl as typeof Intl & {
      supportedValuesOf?: (input: "timeZone") => string[]
    }
  ).supportedValuesOf

  if (typeof supportedValuesOf === "function") {
    return supportedValuesOf("timeZone")
  }

  return FALLBACK_TIMEZONES
}

export function getBrowserTimezone(): string | null {
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
  if (!timezone) return null

  return getSupportedTimezones().includes(timezone) ? timezone : null
}

export function timezoneOptionsWithSelected(selectedTimezone: string | null) {
  const options = getSupportedTimezones()
  if (selectedTimezone && !options.includes(selectedTimezone)) {
    return [selectedTimezone, ...options]
  }
  return options
}
